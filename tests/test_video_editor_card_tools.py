"""Conversation-level tests for the video-editor tools.

No Gemini / Omni / HyperFrames calls: scenario generation uses the deterministic fallback
set and rendering is replaced by a fake that records what would have been rendered.
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from agents.video_editor.card_session import (
    SESSION_STATE_KEY,
    UI_SELECTION_STATE_KEY,
    CardSession,
    load_session,
)
from agents.video_editor.prompt_director import _build_fallback_scenarios
from agents.video_editor.tools import card_tools
from agents.video_editor.workflow_models import PreparedPortrait, RenderedAsset, RenderResult, ValidationFailure
from tests.video_editor_fakes import FakeToolContext, image_upload, user_text, video_upload

SPEAKER = {"talk_title": "Agents in Production", "name": "Jane Doe", "position_company": "GDE, Example"}


def run(coro):
    return asyncio.run(coro)


class FakeRenderer:
    def __init__(self):
        self.drafts = []
        self.failure: ValidationFailure | None = None

    def __call__(self, draft, tool_context):  # patched in as AsyncMock side effect
        self.drafts.append(draft)
        if self.failure:
            return self.failure
        return RenderResult(
            status="completed",
            summary="ok",
            assets=[RenderedAsset(label="1080p MP4", url=f"https://example.com/{len(self.drafts)}.mp4")],
        )


class CardToolsTestCase(unittest.TestCase):
    def setUp(self):
        self.renderer = FakeRenderer()
        self.generated_guidance = []

        self.prepared_portraits = []

        def fake_prepare(draft, tool_context):
            media = draft.media
            key = f"{media.event_id}:{media.part_index}:{media.mime_type}"
            self.prepared_portraits.append(key)
            return PreparedPortrait(
                local_path=f"/tmp/prepared_{len(self.prepared_portraits)}.png",
                preview_url=f"file:///tmp/prepared_{len(self.prepared_portraits)}.png",
                media_key=key,
            )

        def fake_generate(**kwargs):
            self.generated_guidance.append(kwargs.get("creative_guidance"))
            return _build_fallback_scenarios(kwargs["talk_title"], kwargs["speaker_name"])

        patches = [
            patch.object(card_tools, "prepare_portrait_card", side_effect=fake_prepare),
            patch.object(card_tools, "render_video_card", side_effect=self.renderer),
            patch("agents.video_editor.prompt_director.generate_creative_scenarios", side_effect=fake_generate),
            patch.dict(os.environ, {"VIDEO_EDITOR_OFFLINE": "false"}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def photo_context(self) -> FakeToolContext:
        return FakeToolContext({}, [image_upload("photo-1")])

    def session(self, ctx) -> CardSession:
        return load_session(ctx.state)


class TestSpeakerDetails(CardToolsTestCase):
    def test_partial_details_report_only_missing_fields(self):
        ctx = FakeToolContext({}, [user_text("t1", "Card for Jane Doe")])
        result = run(card_tools.update_speaker(name="Jane Doe", tool_context=ctx))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing_fields"], ["talk title", "position and company", "portrait photo or video"])

    def test_details_accumulate_across_turns(self):
        ctx = FakeToolContext({}, [user_text("t1", "hi")])
        run(card_tools.update_speaker(name="Jane Doe", tool_context=ctx))
        run(card_tools.update_speaker(talk_title="Agents", tool_context=ctx))
        ctx.session.events.append(image_upload("photo"))
        result = run(card_tools.update_speaker(position_company="GDE", tool_context=ctx))
        self.assertEqual(result["missing_fields"], [])
        self.assertIn("propose_scenarios", result["next_step"])

    def test_video_upload_skips_scenarios(self):
        ctx = FakeToolContext({}, [video_upload()])
        result = run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        self.assertIn("render_video", result["next_step"])
        rendered = run(card_tools.render_video(tool_context=ctx))
        self.assertEqual(rendered["status"], "success")
        self.assertEqual(self.renderer.drafts[0].media.mime_type, "video/mp4")


class TestScenarioFlow(CardToolsTestCase):
    def test_propose_requires_complete_details(self):
        ctx = FakeToolContext({}, [image_upload()])
        result = run(card_tools.propose_scenarios(tool_context=ctx))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "missing_input")

    def test_propose_returns_scenarios_for_ui_and_compact_message(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        result = run(card_tools.propose_scenarios(tool_context=ctx))
        self.assertEqual(result["status"], "awaiting_scenario_selection")
        self.assertEqual(len(result["scenarios"]), 5)
        # the LLM gets an index, not the full storyboards / JSON blobs
        self.assertNotIn("SCENARIO_STYLES_JSON", result["message"])
        self.assertNotIn("| Shot |", result["message"])
        self.assertLess(len(result["message"]), 2500)

    def test_render_without_choice_asks_which_option(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        result = run(card_tools.render_video(tool_context=ctx))
        self.assertEqual(result["code"], "scenario_not_selected")
        self.assertEqual(self.renderer.drafts, [])

    def test_render_without_scenarios_points_to_propose(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        result = run(card_tools.render_video(tool_context=ctx))
        self.assertEqual(result["code"], "no_scenarios")

    def test_unknown_option_is_reported_with_available_options(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        result = run(card_tools.render_video(option="42", tool_context=ctx))
        self.assertEqual(result["code"], "unknown_option")
        self.assertIn("1.", result["next_step"])

    def test_render_by_number_style_and_id(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        scenarios = run(card_tools.propose_scenarios(tool_context=ctx))["scenarios"]
        run(card_tools.render_video(option="2", tool_context=ctx))
        style = scenarios[2]["styles"][1]
        run(card_tools.render_video(option="3", style_id=style["id"], tool_context=ctx))
        run(card_tools.render_video(option=scenarios[4]["id"], tool_context=ctx))
        ids = [d.selected_scenario_id for d in self.renderer.drafts]
        self.assertEqual(ids, [scenarios[1]["id"], style["id"], scenarios[4]["id"]])
        self.assertTrue(all("Jane Doe" not in (d.creative_direction or "") for d in self.renderer.drafts))

    def test_custom_direction_wins_over_stored_prompt(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        run(card_tools.render_video(option="1", custom_direction="Slow dolly in a neon rain", tool_context=ctx))
        self.assertEqual(self.renderer.drafts[0].creative_direction, "Slow dolly in a neon rain")

    def test_ui_selection_from_deck_is_used_once(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        scenarios = run(card_tools.propose_scenarios(tool_context=ctx))["scenarios"]
        ctx.state[UI_SELECTION_STATE_KEY] = {
            "scenario_id": scenarios[3]["id"],
            "style_id": scenarios[3]["styles"][0]["id"],
            "prompt": "Shot 1 (00:00 - 00:02): edited in the UI",
            "edited": True,
        }
        run(card_tools.render_video(option="4", tool_context=ctx))
        self.assertEqual(self.renderer.drafts[-1].creative_direction, "Shot 1 (00:00 - 00:02): edited in the UI")
        self.assertIsNone(ctx.state[UI_SELECTION_STATE_KEY])
        run(card_tools.render_video(option="4", tool_context=ctx))
        self.assertNotIn("edited in the UI", self.renderer.drafts[-1].creative_direction)

    def test_show_scenarios_reopens_the_same_cards(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        proposed = run(card_tools.propose_scenarios(tool_context=ctx))["scenarios"]
        run(card_tools.render_video(option="1", tool_context=ctx))
        shown = run(card_tools.show_scenarios(tool_context=ctx))
        self.assertEqual([s["id"] for s in shown["scenarios"]], [s["id"] for s in proposed])


class TestSameSpeakerAfterRender(CardToolsTestCase):
    """The bug that made the chat feel broken: everything was forgotten after a render."""

    def test_speaker_photo_and_scenarios_survive_renders(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        self.assertEqual(run(card_tools.render_video(option="1", tool_context=ctx))["status"], "success")

        ctx.session.events.append(user_text("t2", "cool, now option 2 please"))
        second = run(card_tools.render_video(option="2", tool_context=ctx))
        self.assertEqual(second["status"], "success")

        ctx.session.events.append(user_text("t3", "same speaker, but funnier ideas"))
        fresh = run(card_tools.propose_scenarios(creative_guidance="funnier", tool_context=ctx))
        self.assertEqual(fresh["status"], "awaiting_scenario_selection")
        self.assertEqual(self.generated_guidance[-1], "funnier")
        self.assertEqual(run(card_tools.render_video(option="3", tool_context=ctx))["status"], "success")

        self.assertEqual(len(self.renderer.drafts), 3)
        self.assertTrue(all(d.media.event_id == "photo-1" for d in self.renderer.drafts))
        self.assertEqual(len(self.session(ctx).renders), 3)

    def test_changing_title_after_render_keeps_everything_else(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, speaker_bio="Builds agents", tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        run(card_tools.render_video(option="1", tool_context=ctx))
        result = run(card_tools.update_speaker(talk_title="Agents at Scale", tool_context=ctx))
        self.assertIn("regenerate", result["message"])
        run(card_tools.render_video(option="1", tool_context=ctx))
        last = self.renderer.drafts[-1]
        self.assertEqual(last.title, "Agents at Scale")
        self.assertEqual(last.name, "Jane Doe")
        self.assertEqual(last.speaker_bio, "Builds agents")

    def test_new_photo_replaces_only_media(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        ctx.session.events.append(image_upload("photo-2", "image/jpeg"))
        run(card_tools.render_video(option="1", tool_context=ctx))
        self.assertEqual(self.renderer.drafts[-1].media.event_id, "photo-2")
        self.assertEqual(self.renderer.drafts[-1].name, "Jane Doe")

    def test_slightly_different_name_does_not_wipe_the_card(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        run(card_tools.update_speaker(name="Jane A. Doe", tool_context=ctx))
        session = self.session(ctx)
        self.assertEqual(session.speaker.name, "Jane A. Doe")
        self.assertIsNotNone(session.speaker.media)
        self.assertEqual(len(session.scenarios), 5)

    def test_new_speaker_without_photo_asks_for_a_new_photo(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        run(card_tools.render_video(option="1", tool_context=ctx))
        ctx.session.events.append(user_text("t2", "now a card for Maria"))
        result = run(
            card_tools.update_speaker(
                talk_title="Kotlin", name="Maria K", position_company="Dev, ACME", new_speaker=True, tool_context=ctx
            )
        )
        self.assertEqual(result["missing_fields"], ["portrait photo or video"])
        self.assertEqual(self.session(ctx).scenarios, [])
        # the old photo is not silently re-attached by later calls either
        self.assertEqual(
            run(card_tools.get_card_status(tool_context=ctx))["missing_fields"], ["portrait photo or video"]
        )
        ctx.session.events.append(image_upload("maria-photo"))
        self.assertEqual(run(card_tools.get_card_status(tool_context=ctx))["missing_fields"], [])

    def test_new_speaker_with_photo_in_same_message(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        ctx.session.events.append(image_upload("maria-photo"))
        result = run(
            card_tools.update_speaker(
                talk_title="Kotlin", name="Maria K", position_company="Dev, ACME", new_speaker=True, tool_context=ctx
            )
        )
        self.assertEqual(result["missing_fields"], [])
        self.assertEqual(self.session(ctx).speaker.media.event_id, "maria-photo")


class TestErrors(CardToolsTestCase):
    def test_retryable_render_failure_does_not_ask_for_new_photo(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        self.renderer.failure = ValidationFailure(
            code="model_unavailable", message="Omni timed out", requested_action="retry", retryable=True
        )
        result = run(card_tools.render_video(option="1", tool_context=ctx))
        self.assertEqual(result["requested_action"], "retry")
        self.renderer.failure = None
        self.assertEqual(run(card_tools.render_video(option="1", tool_context=ctx))["status"], "success")

    def test_face_rejection_asks_for_new_media(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        run(card_tools.propose_scenarios(tool_context=ctx))
        self.renderer.failure = ValidationFailure(code="face_not_detected", message="No face", retryable=False)
        result = run(card_tools.render_video(option="1", tool_context=ctx))
        self.assertEqual(result["requested_action"], "replace_media")

    def test_scenario_generation_failure_falls_back(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        with patch("agents.video_editor.prompt_director.generate_creative_scenarios", side_effect=RuntimeError("429")):
            result = run(card_tools.propose_scenarios(tool_context=ctx))
        self.assertEqual(len(result["scenarios"]), 5)


class TestOfflineMode(unittest.TestCase):
    def test_offline_mode_runs_whole_flow_without_cloud(self):
        ctx = FakeToolContext({}, [image_upload()])
        with (
            patch.dict(os.environ, {"VIDEO_EDITOR_OFFLINE": "true"}),
            patch.object(card_tools, "render_video_card", side_effect=AssertionError("must not render for real")),
            patch(
                "agents.video_editor.prompt_director.generate_creative_scenarios",
                side_effect=AssertionError("must not call Gemini"),
            ),
        ):
            run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
            run(card_tools.propose_scenarios(tool_context=ctx))
            result = run(card_tools.render_video(option="1", tool_context=ctx))
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["assets"][0]["url"].startswith("file://"))
        self.assertEqual(result["ui"]["type"], "media")
        self.assertTrue(result["ui"]["urls"]["video"].endswith("Video_example.mp4"))
        self.assertEqual(result["ui"]["speaker"]["name"], "Jane Doe")

    def test_offline_mode_render_cover_returns_only_poster(self):
        ctx = FakeToolContext({}, [image_upload()])
        with (
            patch.dict(os.environ, {"VIDEO_EDITOR_OFFLINE": "true"}),
            patch.object(card_tools, "render_cover_card", side_effect=AssertionError("must not render for real")),
            patch.object(card_tools, "render_video_card", side_effect=AssertionError("must not render video")),
        ):
            run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
            result = run(card_tools.render_cover(tool_context=ctx))
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["ui"]["type"], "media")
        self.assertTrue(result["ui"]["urls"]["poster"].endswith(".png"))
        self.assertNotIn("video", result["ui"]["urls"])
        self.assertIn("Do NOT call render_video", result["next_step"])


class TestCoverPhotoFlow(CardToolsTestCase):
    def setUp(self):
        super().setUp()
        self.cover_drafts = []

        def fake_cover_render(draft, tool_context):
            self.cover_drafts.append(draft)
            return RenderResult(
                status="completed",
                summary="4K cover ready",
                assets=[
                    RenderedAsset(
                        label="High-Resolution Card Poster (4K PNG)",
                        url=f"https://example.com/cover_{len(self.cover_drafts)}.png",
                    )
                ],
            )

        p = patch.object(card_tools, "render_cover_card", side_effect=fake_cover_render)
        p.start()
        self.addCleanup(p.stop)

    def test_render_cover_requires_complete_details(self):
        ctx = FakeToolContext({}, [image_upload()])
        result = run(card_tools.render_cover(tool_context=ctx))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "missing_input")
        self.assertEqual(self.cover_drafts, [])

    def test_update_speaker_returns_cover_vs_video_choice_when_complete_and_stops_after_choice(self):
        ctx = self.photo_context()
        res = run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        self.assertEqual(res["missing_fields"], [])
        self.assertIn("ONLY a static 4K cover photo", res["next_step"])
        self.assertIn("ui", res)
        self.assertEqual(res["ui"]["type"], "video_output_choice")
        self.assertEqual(res["ui"]["media_kind"], "image")
        self.assertEqual(res["ui"]["speaker"]["name"], SPEAKER["name"])
        self.assertTrue(res["ui"]["avatar_url"].startswith("file:///tmp/prepared_"))
        self.assertEqual(len(self.prepared_portraits), 1)

        # After a cover is rendered, subsequent updates do not re-emit the initial choice card
        # and reuse the already-prepared portrait without re-outpainting.
        cover = run(card_tools.render_cover(tool_context=ctx))
        self.assertEqual(cover["status"], "success")
        self.assertTrue(self.cover_drafts[0].prepared_avatar_path.startswith("/tmp/prepared_"))
        with patch.object(card_tools.os.path, "isfile", return_value=True):
            res_after = run(card_tools.update_speaker(talk_title="Updated Talk", tool_context=ctx))
        self.assertNotIn("ui", res_after)
        self.assertEqual(len(self.prepared_portraits), 1)

    def test_update_speaker_fails_early_when_portrait_preparation_rejects_face(self):
        ctx = self.photo_context()
        with patch.object(
            card_tools,
            "prepare_portrait_card",
            return_value=ValidationFailure(
                code="face_not_detected",
                message="No face detected.",
                requested_action="replace_media",
                retryable=False,
            ),
        ):
            res = run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["code"], "face_not_detected")
        self.assertEqual(res["requested_action"], "replace_media")
        self.assertNotIn("ui", res)

    def test_render_card_reuses_prepared_avatar_without_double_outpaint(self):
        from io import BytesIO

        from PIL import Image

        from agents.video_editor import video_card_service

        buf = BytesIO()
        Image.new("RGB", (600, 800), (120, 40, 180)).save(buf, format="PNG")
        img_bytes = buf.getvalue()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            Image.new("RGB", (768, 1376), (30, 100, 220)).save(tf.name)
            prepared_file = tf.name
        self.addCleanup(lambda: os.path.exists(prepared_file) and os.remove(prepared_file))

        async def fake_stage() -> str:
            target = os.path.join(video_card_service.media_tools.BASE_DIR, "assets", "staged_media.png")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(img_bytes)
            return "assets/staged_media.png"

        draft = card_tools.VideoEditorDraft(
            title=SPEAKER["talk_title"],
            name=SPEAKER["name"],
            position_company=SPEAKER["position_company"],
            prepared_avatar_path=prepared_file,
        )
        settings = video_card_service.RenderSettings(toggles={"enable_video_generation": False})

        with (
            patch.object(video_card_service.workflow, "validate_render_environment", return_value=None),
            patch.object(video_card_service, "_review_metadata", return_value=None),
            patch.object(
                video_card_service,
                "_review_face",
                side_effect=AssertionError("face check already ran during portrait preparation"),
            ),
            patch.object(
                video_card_service.media_tools,
                "outpaint_to_9_16",
                side_effect=AssertionError("outpaint_to_9_16 must not run twice"),
            ),
            patch.object(video_card_service.composer_tools, "update_composer"),
            patch.object(
                video_card_service.composer_tools,
                "render_cover_poster",
                return_value="4K cover photo generated:\n• High-Resolution Card Poster (4K PNG): /tmp/cover_4k.png",
            ),
        ):
            res = run(
                video_card_service.render_card(
                    draft,
                    settings,
                    stage_media=fake_stage,
                    workspace_label="prepared-cover-test",
                    cover_only=True,
                )
            )
        self.assertIsInstance(res, RenderResult)
        self.assertTrue(res.assets[0].url.endswith("/tmp/cover_4k.png"))

    def test_render_cover_does_not_render_video_and_preserves_state_for_later_approval(self):
        ctx = self.photo_context()
        run(card_tools.update_speaker(**SPEAKER, tool_context=ctx))
        cover = run(card_tools.render_cover(tool_context=ctx))
        self.assertEqual(cover["status"], "success")
        self.assertEqual(len(self.cover_drafts), 1)
        self.assertEqual(self.renderer.drafts, [])
        self.assertEqual(cover["ui"]["urls"]["poster"], "https://example.com/cover_1.png")
        self.assertNotIn("video", cover["ui"]["urls"])
        self.assertIn("render_video", cover["next_step"])

        # After user approves, scenarios + video render continue with the same saved speaker.
        run(card_tools.propose_scenarios(tool_context=ctx))
        video = run(card_tools.render_video(option="2", tool_context=ctx))
        self.assertEqual(video["status"], "success")
        self.assertEqual(len(self.renderer.drafts), 1)
        self.assertEqual(len(self.session(ctx).renders), 2)

    def test_render_card_cover_only_outpaints_and_skips_omni_even_when_video_disabled(self):
        from io import BytesIO

        from PIL import Image

        from agents.video_editor import video_card_service

        buf = BytesIO()
        Image.new("RGB", (600, 800), (120, 40, 180)).save(buf, format="PNG")
        img_bytes = buf.getvalue()

        async def fake_stage() -> str:
            target = os.path.join(video_card_service.media_tools.BASE_DIR, "assets", "staged_media.png")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(img_bytes)
            return "assets/staged_media.png"

        draft = card_tools.VideoEditorDraft(
            title=SPEAKER["talk_title"],
            name=SPEAKER["name"],
            position_company=SPEAKER["position_company"],
        )
        settings = video_card_service.RenderSettings(toggles={"enable_video_generation": False})

        with (
            patch.object(video_card_service.workflow, "validate_render_environment", return_value=None),
            patch.object(video_card_service, "_review_metadata", return_value=None),
            patch.object(video_card_service, "_review_face", return_value=None),
            patch.object(
                video_card_service.media_tools,
                "get_gemini_client",
                return_value=object(),
            ),
            patch.object(
                video_card_service.media_tools,
                "outpaint_to_9_16",
                return_value="assets/portrait_outpainted.png",
            ) as outpaint_mock,
            patch.object(
                video_card_service.media_tools,
                "animate_photo",
                side_effect=AssertionError("animate_photo must not run for cover_only"),
            ),
            patch.object(video_card_service.composer_tools, "update_composer") as update_mock,
            patch.object(
                video_card_service.composer_tools,
                "render_cover_poster",
                return_value="4K cover photo generated:\n• High-Resolution Card Poster (4K PNG): /tmp/cover_4k.png",
            ) as cover_mock,
            patch.object(
                video_card_service.composer_tools,
                "render_composer",
                side_effect=AssertionError("render_composer must not run for cover_only"),
            ),
        ):
            res = run(
                video_card_service.render_card(
                    draft,
                    settings,
                    stage_media=fake_stage,
                    workspace_label="cover-test",
                    cover_only=True,
                )
            )

        self.assertIsInstance(res, RenderResult)
        outpaint_mock.assert_called_once()
        update_mock.assert_called_once()
        cover_mock.assert_called_once()
        self.assertEqual(res.assets[0].label, "High-Resolution Card Poster (4K PNG)")
        self.assertTrue(res.assets[0].url.endswith("/tmp/cover_4k.png"))


class TestLegacyStateMigration(unittest.TestCase):
    def test_old_draft_is_migrated(self):
        state = {
            "video_editor_last_rendered_draft": {
                "title": "Old",
                "name": "Jane",
                "position_company": "GDE",
                "media": {"event_id": "e1", "part_index": 0, "mime_type": "image/png"},
                "suggested_scenarios": [s.model_dump() for s in _build_fallback_scenarios("Old", "Jane")],
            }
        }
        session = load_session(state)
        self.assertEqual(session.speaker.name, "Jane")
        self.assertEqual(session.speaker.media.event_id, "e1")
        self.assertEqual(len(session.scenarios), 5)
        self.assertNotIn(SESSION_STATE_KEY, state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
