import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.video_editor.tools import media_tools
from agents.video_editor.tools.composer_tools import build_card_config, render_composer
from agents.video_editor.tools.media_tools import animate_photo
from agents.video_editor.tools.video_card_tool import confirmation_required, create_video_card
from agents.video_editor.video_card_service import (
    _copy_workspace_template,
    compile_creative_prompt,
    draft_fingerprint,
    merge_draft,
    normalise_rendered_asset,
)
from agents.video_editor.workflow import (
    _collect_assets_from_summary,
    _normalise_render_summary,
    classify_media_path,
    validate_render_environment,
    validate_request_metadata_fields,
    validate_resolved_media,
)
from agents.video_editor.workflow_models import (
    RenderedAsset,
    RenderResult,
    ResolvedMedia,
    UploadedMedia,
    VideoEditorDraft,
    VideoEditorRequest,
)


class FakeInlineData:
    def __init__(self, mime_type: str, data: bytes):
        self.mime_type = mime_type
        self.data = data


class FakePart:
    def __init__(self, text: str | None = None, inline_data: FakeInlineData | None = None):
        self.text = text
        self.inline_data = inline_data


class FakeContent:
    def __init__(self, parts: list[FakePart]):
        self.parts = parts


class FakeEvent:
    def __init__(self, event_id: str, parts: list[FakePart]):
        self.id = event_id
        self.author = "user"
        self.content = FakeContent(parts)


class FakeSession:
    def __init__(self, events: list[FakeEvent]):
        self.id = "test-session"
        self.events = events


class FakeToolContext:
    def __init__(self, state: dict, events: list[FakeEvent]):
        self.state = state
        self.session = FakeSession(events)


class TestVideoEditorWorkflow(unittest.TestCase):
    def test_validate_request_metadata_fields_accepts_valid_request(self):
        result = validate_request_metadata_fields(
            VideoEditorRequest(
                title="Practical AI for community organisers",
                name="Jane Doe",
                position_company="Developer Advocate, Example",
            )
        )

        self.assertEqual(result.title, "Practical AI for community organisers")
        self.assertEqual(result.name, "Jane Doe")

    def test_validate_request_metadata_fields_rejects_long_name(self):
        result = validate_request_metadata_fields(
            VideoEditorRequest(title="Talk", name="J" * 51, position_company="Role")
        )

        self.assertEqual(result.code, "field_too_long")
        self.assertEqual(result.field, "name")

    def test_classify_media_path_detects_supported_types(self):
        self.assertEqual(classify_media_path("speaker.png"), "image")
        self.assertEqual(classify_media_path("speaker.mp4"), "video")
        self.assertEqual(classify_media_path("speaker.txt"), "unknown")

    def test_validate_resolved_media_rejects_placeholder(self):
        failure = validate_resolved_media(
            ResolvedMedia(source_path="assets/portrait_outpainted.png", media_type="image", placeholder_used=True)
        )

        self.assertEqual(failure.code, "media_not_found")
        self.assertEqual(failure.requested_action, "replace_media")

    def test_validate_render_environment_rejects_missing_ffmpeg_before_generation(self):
        with patch("agents.video_editor.workflow.shutil.which", return_value=None):
            failure = validate_render_environment()

        self.assertEqual(failure.code, "render_environment_unavailable")
        self.assertFalse(failure.retryable)

    def test_merge_draft_keeps_text_when_media_changes(self):
        draft = VideoEditorDraft(
            title="First talk",
            name="First speaker",
            position_company="First role",
            media=UploadedMedia(event_id="old-upload", part_index=0, mime_type="image/png"),
        )

        merged = merge_draft(
            draft,
            title=None,
            name=None,
            position_company=None,
            creative_direction=None,
            media=UploadedMedia(event_id="new-upload", part_index=0, mime_type="image/png"),
        )

        self.assertEqual(merged.title, "First talk")
        self.assertEqual(merged.name, "First speaker")
        self.assertEqual(merged.media.event_id, "new-upload")

    def test_tool_uses_prior_video_upload_after_later_text_message(self):
        video_event = FakeEvent(
            "video-upload",
            [FakePart(inline_data=FakeInlineData("video/mp4", b"video"))],
        )
        text_event = FakeEvent("details", [FakePart(text="Use my uploaded video.")])
        context = FakeToolContext({}, [video_event, text_event])
        fake_result = RenderResult(
            status="completed",
            summary="Completed.",
            assets=[RenderedAsset(label="Video", url="https://example.com/video.mp4")],
        )

        with patch("agents.video_editor.tools.video_card_tool.render_video_card", return_value=fake_result):
            result = asyncio.run(
                create_video_card(
                    talk_title="Talk",
                    name="Jane Doe",
                    position_company="Developer Advocate, Example",
                    media_type="video",
                    tool_context=context,
                )
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(context.state["video_editor_draft"], {})

    def test_tool_does_not_reuse_media_after_a_completed_render(self):
        upload = FakeEvent("video-upload", [FakePart(inline_data=FakeInlineData("video/mp4", b"video"))])
        context = FakeToolContext({}, [upload])
        rendered = RenderResult(
            status="completed",
            summary="Completed.",
            assets=[RenderedAsset(label="Video", url="https://example.com/video.mp4")],
        )

        with patch("agents.video_editor.tools.video_card_tool.render_video_card", return_value=rendered):
            first = asyncio.run(
                create_video_card(
                    talk_title="First talk",
                    name="First speaker",
                    position_company="First role",
                    media_type="video",
                    tool_context=context,
                )
            )

        self.assertEqual(first["status"], "success")

        second = asyncio.run(
            create_video_card(
                talk_title="Second talk",
                name="Second speaker",
                position_company="Second role",
                media_type="video",
                tool_context=context,
            )
        )

        self.assertEqual(second["status"], "error")
        self.assertEqual(second["code"], "missing_media")

    def test_creative_prompt_includes_user_direction(self):
        draft = VideoEditorDraft(
            title="Reliable AI systems",
            name="Jane Doe",
            position_company="Developer Advocate, Example",
            creative_direction="Warm studio lighting, slow push-in, no neon.",
        )

        prompt = compile_creative_prompt(draft)

        self.assertEqual(prompt, "Warm studio lighting, slow push-in, no neon")

    def test_normalise_rendered_asset_keeps_https_url(self):
        asset = normalise_rendered_asset("Video", "https://example.com/video.mp4")

        self.assertEqual(asset.availability, "available")
        self.assertEqual(asset.url, "https://example.com/video.mp4")

    def test_normalise_rendered_asset_uses_file_url_when_cloud_upload_is_unavailable(self):
        asset = normalise_rendered_asset("Video", "/private/tmp/video.mp4")

        self.assertEqual(asset.availability, "available")
        self.assertEqual(asset.url, "file:///private/tmp/video.mp4")

    def test_workflow_normalises_local_render_paths_to_file_urls(self):
        summary = "• Video: /private/tmp/video.mp4"

        self.assertEqual(_collect_assets_from_summary(summary)[0].url, "file:///private/tmp/video.mp4")
        self.assertEqual(_normalise_render_summary(summary), "• [Video](file:///private/tmp/video.mp4)")

    def test_confirmation_flag_defaults_to_false(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(confirmation_required())

    def test_video_generation_enabled_reads_the_environment_at_call_time(self):
        with patch.dict("os.environ", {"ENABLE_VIDEO_GENERATION": "false"}):
            self.assertFalse(media_tools.video_generation_enabled())
        with patch.dict("os.environ", {"ENABLE_VIDEO_GENERATION": "true"}):
            self.assertTrue(media_tools.video_generation_enabled())

    def test_cinematic_fallback_is_added_to_the_generation_prompt(self):
        with patch("agents.video_editor.tools.media_tools.random.choice", return_value="Soft editorial movement."):
            prompt = media_tools.augment_creative_prompt("Create a polished speaker card")

        self.assertEqual(prompt, "Create a polished speaker card. Soft editorial movement.")

    def test_draft_fingerprint_changes_when_creative_direction_changes(self):
        draft = VideoEditorDraft(title="Talk", name="Jane", position_company="Role")
        before = draft_fingerprint(draft)
        draft.creative_direction = "Cinematic"

        self.assertNotEqual(before, draft_fingerprint(draft))

    def test_workspace_template_accepts_existing_workspace(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "workspace"
            workspace.mkdir()

            _copy_workspace_template(workspace)

        self.assertTrue(True)

    def test_tool_returns_missing_input_without_rendering(self):
        context = FakeToolContext({}, [])

        result = asyncio.run(
            create_video_card(
                talk_title="",
                name="",
                position_company="",
                media_type="image",
                tool_context=context,
            )
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "missing_input")
        self.assertIn("speaker name", result["missing_fields"])

    def test_tool_requires_confirmation_when_enabled(self):
        event = FakeEvent("upload", [FakePart(inline_data=FakeInlineData("image/png", b"image"))])
        context = FakeToolContext({}, [event])
        with patch.dict("os.environ", {"VIDEO_EDITOR_REQUIRE_CONFIRMATION": "true"}):
            result = asyncio.run(
                create_video_card(
                    talk_title="Talk",
                    name="Jane Doe",
                    position_company="Developer Advocate, Example",
                    media_type="image",
                    tool_context=context,
                )
            )

        self.assertEqual(result["status"], "awaiting_confirmation")
        self.assertEqual(result["requested_action"], "confirm_render")

    def test_tool_renders_after_confirmation(self):
        event = FakeEvent("upload", [FakePart(inline_data=FakeInlineData("image/png", b"image"))])
        context = FakeToolContext({}, [event])
        fake_result = RenderResult(
            status="completed",
            summary="Completed.",
            assets=[RenderedAsset(label="Video", url="https://example.com/video.mp4")],
        )
        with patch.dict("os.environ", {"VIDEO_EDITOR_REQUIRE_CONFIRMATION": "true"}):
            with patch("agents.video_editor.tools.video_card_tool.render_video_card", return_value=fake_result):
                first = asyncio.run(
                    create_video_card(
                        talk_title="Talk",
                        name="Jane Doe",
                        position_company="Developer Advocate, Example",
                        media_type="image",
                        tool_context=context,
                    )
                )
                result = asyncio.run(
                    create_video_card(
                        talk_title="Talk",
                        name="Jane Doe",
                        position_company="Developer Advocate, Example",
                        media_type="image",
                        confirm_render=True,
                        tool_context=context,
                    )
                )

        self.assertEqual(first["status"], "awaiting_confirmation")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["assets"][0]["url"], "https://example.com/video.mp4")
        self.assertEqual(context.state["video_editor_draft"], {})

    def test_confirmation_is_invalidated_by_changed_creative_direction(self):
        event = FakeEvent("upload", [FakePart(inline_data=FakeInlineData("image/png", b"image"))])
        context = FakeToolContext({}, [event])
        with patch.dict("os.environ", {"VIDEO_EDITOR_REQUIRE_CONFIRMATION": "true"}):
            first = asyncio.run(
                create_video_card(
                    talk_title="Talk",
                    name="Jane Doe",
                    position_company="Developer Advocate, Example",
                    media_type="image",
                    tool_context=context,
                )
            )
            result = asyncio.run(
                create_video_card(
                    talk_title="Talk",
                    name="Jane Doe",
                    position_company="Developer Advocate, Example",
                    media_type="image",
                    creative_direction="Warm studio lighting.",
                    tool_context=context,
                )
            )

        self.assertEqual(first["status"], "awaiting_confirmation")
        self.assertEqual(result["status"], "awaiting_confirmation")

    def test_render_composer_session_state_blocks_when_all_disabled(self):
        mock_context = MagicMock()
        mock_context.session.state = {
            "render_ordinary": False,
            "render_gif": False,
            "render_4k": False,
        }

        with self.assertRaises(ValueError) as ctx_err:
            render_composer(tool_context=mock_context)
        self.assertIn("All rendering options are disabled", str(ctx_err.exception))

    def test_animate_photo_session_state_disables_video_generation(self):
        mock_context = MagicMock()
        mock_context.session.state = {
            "enable_video_generation": False,
            "generate_avatar": False,
        }

        result = animate_photo("speaker.png", "prompt", tool_context=mock_context)
        self.assertTrue(result.startswith("Error:"))
        self.assertIn("Generative AI video models", result)

    def test_animate_photo_with_video_file_succeeds_without_ai_generation(self):
        mock_context = MagicMock()
        mock_context.session.state = {
            "enable_video_generation": False,
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid:
            vid.write(b"video content")
            vid_path = vid.name
        self.addCleanup(Path(vid_path).unlink, missing_ok=True)

        result = animate_photo(vid_path, "prompt", tool_context=mock_context)
        self.assertEqual(result, "assets/Video_example.mp4")

    def test_outpaint_image_node_invokes_outpainting_for_image(self):
        from agents.video_editor.workflow import outpaint_image_node

        mock_ctx = MagicMock()
        mock_ctx.state = {
            "temp:resolved_media": {
                "source_path": "assets/speaker_sample.png",
                "media_type": "image",
                "placeholder_used": False,
            },
        }

        with patch("agents.video_editor.workflow.get_gemini_client") as mock_client:
            with patch(
                "agents.video_editor.workflow.media_tools.outpaint_to_9_16",
                return_value="assets/outpainted.png",
            ) as mock_outpaint:
                func = getattr(outpaint_image_node, "_func", outpaint_image_node)
                func(mock_ctx)
                mock_outpaint.assert_called_once_with("assets/speaker_sample.png", mock_client.return_value)
                self.assertEqual(mock_ctx.state["temp:outpainted_image_path"], "assets/outpainted.png")

    def test_generate_video_from_image_node_passes_tool_context(self):
        from agents.video_editor.workflow import generate_video_from_image_node

        mock_ctx = MagicMock()
        mock_ctx.state = {
            "enable_video_generation": False,
            "temp:outpainted_image_path": "assets/outpainted.png",
            "temp:creative_prompt": "cinematic presentation",
            "temp:resolved_media": {
                "source_path": "assets/speaker.png",
                "media_type": "image",
                "placeholder_used": False,
            },
        }

        with patch(
            "agents.video_editor.workflow.media_tools.animate_photo",
            return_value="assets/Video_example.mp4",
        ) as mock_animate:
            with patch("agents.video_editor.workflow._read_video_duration", return_value=5.0):
                func = getattr(generate_video_from_image_node, "_func", generate_video_from_image_node)
                func(mock_ctx)
                mock_animate.assert_called_once_with(
                    photo_path="assets/outpainted.png",
                    creative_prompt="cinematic presentation",
                    tool_context=mock_ctx,
                )

    def test_render_composer_accepts_camel_case_session_state(self):
        mock_context = MagicMock()
        mock_context.session.state = {
            "renderOrdinary": False,
            "renderGif": False,
            "render4k": False,
        }

        with self.assertRaises(ValueError) as ctx_err:
            render_composer(tool_context=mock_context)
        self.assertIn("All rendering options are disabled", str(ctx_err.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
