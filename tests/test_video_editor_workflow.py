import asyncio
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

from agents.video_editor.tools import media_tools
from agents.video_editor.tools.composer_tools import build_card_config, render_composer, update_composer
from agents.video_editor.tools.media_tools import _safe_b64decode, animate_photo
from agents.video_editor.tools.video_card_tool import (
    confirmation_required,
    create_video_card,
    format_render_success_message,
)
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
    ValidationFailure,
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

    def test_validate_request_metadata_fields_accepts_title_up_to_110_chars(self):
        title_93 = "Say No. Convince. Apologize. Three Conversations They Never Taught You in Engineering School"
        result = validate_request_metadata_fields(
            VideoEditorRequest(title=title_93, name="Mateusz Kulka", position_company="Product Owner, Aquiva")
        )
        self.assertEqual(result.title, title_93)

        title_110 = "T" * 110
        result_110 = validate_request_metadata_fields(
            VideoEditorRequest(title=title_110, name="Jane Doe", position_company="Role")
        )
        self.assertEqual(result_110.title, title_110)

    def test_validate_request_metadata_fields_rejects_long_title(self):
        result = validate_request_metadata_fields(
            VideoEditorRequest(title="T" * 111, name="Jane", position_company="Role")
        )
        self.assertEqual(result.code, "field_too_long")
        self.assertEqual(result.field, "title")
        self.assertIn("110", result.message)

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

    def test_workspace_template_copies_build_with_ai(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "workspace"
            workspace.mkdir()

            _copy_workspace_template(workspace, template_name="build_with_ai")
            index_content = (workspace / "index.html").read_text(encoding="utf-8")
            self.assertIn("BUILD WITH AI", index_content)

    def test_workspace_template_copies_devfest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory) / "workspace"
            workspace.mkdir()

            _copy_workspace_template(workspace, template_name="devfest")
            index_content = (workspace / "index.html").read_text(encoding="utf-8")
            self.assertIn("DEVFEST", index_content)

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
                    selected_scenario_id="scenario_1",
                    tool_context=context,
                )
            )

        self.assertEqual(result["status"], "awaiting_confirmation")
        self.assertEqual(result["requested_action"], "confirm_render")

    @patch("agents.video_editor.tools.video_card_tool.generate_creative_scenarios")
    def test_tool_renders_after_confirmation(self, mock_gen_scenarios):
        from agents.video_editor.prompt_director import _build_fallback_scenarios

        mock_gen_scenarios.return_value = _build_fallback_scenarios("Talk", "Jane Doe")
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
                selected_id = first["scenarios"][0]["id"]
                result = asyncio.run(
                    create_video_card(
                        talk_title="Talk",
                        name="Jane Doe",
                        position_company="Developer Advocate, Example",
                        media_type="image",
                        selected_scenario_id=selected_id,
                        confirm_render=True,
                        tool_context=context,
                    )
                )

        self.assertEqual(first["status"], "awaiting_confirmation")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["assets"][0]["url"], "https://example.com/video.mp4")
        self.assertEqual(context.state["video_editor_draft"], {})

    @patch("agents.video_editor.tools.video_card_tool.generate_creative_scenarios")
    def test_confirmation_is_invalidated_by_changed_creative_direction(self, mock_gen_scenarios):
        from agents.video_editor.prompt_director import _build_fallback_scenarios

        mock_gen_scenarios.return_value = _build_fallback_scenarios("Talk", "Jane Doe")
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

        with patch("agents.video_editor.tools.media_tools.shutil.copy2") as mock_copy:
            result = animate_photo(vid_path, "prompt", tool_context=mock_context)
            self.assertEqual(result, "assets/Video_example.mp4")
            mock_copy.assert_called_once()

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

    def test_update_composer_devfest_template_randomizes_brackets_and_dots_colors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            devfest_template_path = (
                Path(__file__).resolve().parent.parent / "agents" / "video_editor" / "templates" / "devfest.html"
            )
            target_index = Path(tmp_dir) / "index.html"
            target_index.write_text(devfest_template_path.read_text(encoding="utf-8"), encoding="utf-8")

            with patch("agents.video_editor.tools.composer_tools.resolve_path", return_value=str(target_index)):
                result = update_composer(
                    video_path="assets/Video_example.mp4",
                    title="Testing DevFest Template",
                    name="Jane Doe",
                    position_company="Tech Lead, ACME",
                    duration_seconds=8,
                )

            self.assertIn("Successfully updated index.html", result)
            self.assertIn("breaks:", result)
            self.assertIn("dots:", result)
            content = target_index.read_text(encoding="utf-8")
            self.assertIn("Jane Doe", content)
            self.assertIn("Testing DevFest Template", content)
            # Krakow pill badge must stay white
            self.assertIn(
                'id="krakow_pill" x="926.7" y="241" width="428" height="57" rx="28.5" fill="#FFFFFF"', content
            )

            # Brackets and dots must have been updated
            import re

            m_b1 = re.search(r'<path\s+id="break_1"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            m_b2 = re.search(r'<path\s+id="break_2"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            m_d1 = re.search(r'<circle\s+id="dot_1"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            m_d2 = re.search(r'<circle\s+id="dot_2"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            m_d3 = re.search(r'<circle\s+id="dot_3"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            self.assertIsNotNone(m_b1)
            self.assertIsNotNone(m_b2)
            self.assertIsNotNone(m_d1)
            self.assertIsNotNone(m_d2)
            self.assertIsNotNone(m_d3)
            self.assertEqual(m_b1.group(1), m_b2.group(1))
            self.assertEqual(m_d1.group(1), m_d2.group(1))
            self.assertEqual(m_d2.group(1), m_d3.group(1))

    def test_update_composer_devfest_template_respects_theme_colors(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            devfest_template_path = (
                Path(__file__).resolve().parent.parent / "agents" / "video_editor" / "templates" / "devfest.html"
            )
            target_index = Path(tmp_dir) / "index.html"
            target_index.write_text(devfest_template_path.read_text(encoding="utf-8"), encoding="utf-8")

            with patch("agents.video_editor.tools.composer_tools.resolve_path", return_value=str(target_index)):
                result = update_composer(
                    video_path="assets/Video_example.mp4",
                    title="Testing DevFest Template",
                    name="Jane Doe",
                    position_company="Tech Lead, ACME",
                    duration_seconds=8,
                    theme_colors={"break_color": "#EA4335", "dots_color": "#4285F4"},
                )

            self.assertIn("breaks: #EA4335, dots: #4285F4", result)
            content = target_index.read_text(encoding="utf-8")
            import re

            m_b1 = re.search(r'<path\s+id="break_1"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            m_d1 = re.search(r'<circle\s+id="dot_1"[^>]*?fill="(#[0-9a-fA-F]{6})"', content)
            self.assertEqual(m_b1.group(1), "#EA4335")
            self.assertEqual(m_d1.group(1), "#4285F4")
            # Krakow pill badge remains white
            self.assertIn(
                'id="krakow_pill" x="926.7" y="241" width="428" height="57" rx="28.5" fill="#FFFFFF"', content
            )

    def test_update_composer_handles_unicode_escapes_and_special_chars(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            devfest_template_path = (
                Path(__file__).resolve().parent.parent / "agents" / "video_editor" / "templates" / "devfest.html"
            )
            target_index = Path(tmp_dir) / "index.html"
            target_index.write_text(devfest_template_path.read_text(encoding="utf-8"), encoding="utf-8")

            with patch("agents.video_editor.tools.composer_tools.resolve_path", return_value=str(target_index)):
                # Test with unicode escape sequences in path and Polish/Cyrillic characters in name
                result = update_composer(
                    video_path="assets/dominika_zaj\\u0105c.png",
                    title="Architektura Wielu Agentów",
                    name="Dominika Zając",
                    position_company="Tech Lead, Google Developer Groups",
                    duration_seconds=10,
                )

            self.assertIn("Successfully updated index.html", result)
            content = target_index.read_text(encoding="utf-8")
            self.assertIn("Dominika", content)
            self.assertIn("Architektura", content)
            self.assertIn("dominika_zaj", content)

    def test_validation_failure_supports_render_failed_and_ignores_extra_fields(self):
        failure = ValidationFailure(
            code="render_failed",
            message="Failed to render video composition: timeout",
            missing_fields=[],
        )
        self.assertEqual(failure.code, "render_failed")
        self.assertEqual(failure.requested_action, "retry")
        self.assertTrue(failure.retryable)

    def test_render_video_card_returns_validation_failure_on_render_composer_error(self):
        draft = VideoEditorDraft(
            title="Architektura Wielu Agentów",
            name="Dominika Zając",
            position_company="Tech Lead, Google Developer Groups",
            confirmed=True,
            media=UploadedMedia(event_id="evt_123", part_index=0, mime_type="video/mp4"),
        )
        mock_context = MagicMock()
        mock_context.session.id = "session_123"
        mock_context.session.state = {"video_template": "devfest"}
        with (
            patch("agents.video_editor.video_card_service._review_metadata", return_value=None),
            patch("agents.video_editor.video_card_service.workflow.validate_render_environment", return_value=None),
            patch("agents.video_editor.video_card_service.isolated_workspace"),
            patch("agents.video_editor.video_card_service._workspace_tool_paths"),
            patch(
                "agents.video_editor.video_card_service.media_tools.stage_uploaded_media",
                return_value="assets/Video_example.mp4",
            ),
            patch("agents.video_editor.video_card_service.workflow.validate_resolved_media", return_value=None),
            patch("agents.video_editor.video_card_service.workflow._read_video_duration", return_value=10),
            patch("agents.video_editor.video_card_service.shutil.copy2"),
            patch("agents.video_editor.video_card_service.composer_tools.update_composer"),
            patch(
                "agents.video_editor.video_card_service.composer_tools.render_composer",
                side_effect=RuntimeError("HyperFrames render crashed"),
            ),
        ):
            from agents.video_editor.video_card_service import render_video_card

            result = asyncio.run(render_video_card(draft, mock_context))

        self.assertIsInstance(result, ValidationFailure)
        self.assertEqual(result.code, "render_failed")
        self.assertIn("HyperFrames render crashed", result.message)
        self.assertEqual(result.requested_action, "retry")

    def test_render_video_card_rejects_image_when_video_generation_disabled_in_state(self):
        draft = VideoEditorDraft(
            title="Architektura Wielu Agentów",
            name="Dominika Zając",
            position_company="Tech Lead, Google Developer Groups",
            confirmed=True,
            media=UploadedMedia(event_id="evt_123", part_index=0, mime_type="image/png"),
        )
        mock_context = MagicMock()
        mock_context.session.id = "session_123"
        mock_context.session.state = {
            "enable_video_generation": False,
        }
        with (
            patch("agents.video_editor.video_card_service._review_metadata", return_value=None),
            patch("agents.video_editor.video_card_service.workflow.validate_render_environment", return_value=None),
            patch("agents.video_editor.video_card_service.isolated_workspace"),
            patch("agents.video_editor.video_card_service._workspace_tool_paths"),
            patch(
                "agents.video_editor.video_card_service.media_tools.stage_uploaded_media",
                return_value="portrait.png",
            ),
            patch("agents.video_editor.video_card_service.workflow.validate_resolved_media", return_value=None),
        ):
            from agents.video_editor.video_card_service import render_video_card

            result = asyncio.run(render_video_card(draft, mock_context))

        self.assertIsInstance(result, ValidationFailure)
        self.assertEqual(result.code, "model_unavailable")
        self.assertIn("Image-to-video generation is disabled", result.message)
        self.assertEqual(result.requested_action, "replace_media")

    def test_safe_b64decode_handles_standard_urlsafe_and_data_urls(self):
        # Standard base64
        self.assertEqual(_safe_b64decode("aGVsbG8="), b"hello")
        # Unpadded base64
        self.assertEqual(_safe_b64decode("aGVsbG8"), b"hello")
        # Urlsafe base64 (- and _)
        import base64

        raw = b"\xfb\xff\xfe\x00\x01test"
        urlsafe_encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        self.assertEqual(_safe_b64decode(urlsafe_encoded), raw)
        # Data URL prefix
        data_url = f"data:image/png;base64,{urlsafe_encoded}"
        self.assertEqual(_safe_b64decode(data_url), raw)

    def test_format_render_success_message_with_notice(self):
        assets = [
            RenderedAsset(label="Static Card Poster", path="card.png", url="/media/card.png", mime_type="image/png"),
        ]
        msg = format_render_success_message(assets, notice="⚠️ API Quota Notice")
        self.assertTrue(msg.startswith("⚠️ API Quota Notice\n\nGeneration complete."))
        self.assertIn("[Static Card Poster](/media/card.png)", msg)

        # Without notice
        msg_no_notice = format_render_success_message(assets)
        self.assertTrue(msg_no_notice.startswith("Generation complete."))

    def test_reopen_existing_card_preserves_exact_scenarios(self):
        from agents.video_editor.prompt_director import CreativeScenario, VideoShot
        from agents.video_editor.tools.video_card_tool import LAST_RENDERED_DRAFT_KEY

        existing_shots = [
            VideoShot(
                shot_number=1,
                time_range="00:00 - 00:02",
                action="Protagonist inspects antique camera.",
                camera="Close-up macro.",
                lighting_atmosphere="Warm amber daylight.",
            ),
            VideoShot(
                shot_number=2,
                time_range="00:02 - 00:04",
                action="Gears click and turn.",
                camera="Rack focus.",
                lighting_atmosphere="Golden haze.",
            ),
        ]
        sample_sc = CreativeScenario(
            id="sc_1",
            title="Clockwork Voyage",
            genre="Steampunk Industrial",
            concept="Mechanical discovery.",
            shots=existing_shots,
            omni_prompt="Cinematic 9:16 Steampunk. Shot 1: Protagonist inspects antique camera.",
        )
        prior_draft = {
            "title": "Architecting Agents",
            "name": "Alex",
            "position_company": "Lead AI Engineer",
            "media": {"event_id": "upload_1", "part_index": 0, "mime_type": "image/png"},
            "suggested_scenarios": [sample_sc.model_dump()],
        }
        context = FakeToolContext(
            {
                LAST_RENDERED_DRAFT_KEY: prior_draft,
                "video_editor_draft": {},
            },
            [],
        )

        # Reopen with reopen_existing_card=True
        result = asyncio.run(
            create_video_card(
                talk_title="Architecting Agents",
                name="Alex",
                position_company="Lead AI Engineer",
                media_type="image",
                reopen_existing_card=True,
                tool_context=context,
            )
        )
        self.assertEqual(result["status"], "awaiting_confirmation")
        self.assertEqual(result["requested_action"], "select_scenario")
        self.assertEqual(len(result["scenarios"]), 1)
        self.assertEqual(result["scenarios"][0]["title"], "Clockwork Voyage")
        self.assertIn("Clockwork Voyage", result["message"])

        # Reopen with natural language keyword "повторить карточку"
        result2 = asyncio.run(
            create_video_card(
                talk_title="Architecting Agents",
                name="Alex",
                position_company="Lead AI Engineer",
                media_type="image",
                creative_direction="повтори карточку из ui пожалуйста",
                tool_context=context,
            )
        )
        self.assertEqual(result2["status"], "awaiting_confirmation")
        self.assertEqual(result2["requested_action"], "select_scenario")
        self.assertEqual(result2["scenarios"][0]["title"], "Clockwork Voyage")

    @patch("agents.video_editor.tools.media_tools.get_gemini_api_key", return_value="test_key")
    @patch("agents.video_editor.tools.media_tools.requests.post")
    def test_generate_with_omni_retries_on_400_content_blocked(self, mock_post, mock_key):
        resp_blocked = MagicMock()
        resp_blocked.status_code = 400
        resp_blocked.text = '{"error":{"message":"Input blocked","code":"content_blocked"}}'

        fake_video_b64 = base64.b64encode(b"FAKE_MP4_VIDEO_BYTES").decode("utf-8")
        resp_ok = MagicMock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"steps": [{"content": [{"type": "video", "data": fake_video_b64}]}]}

        mock_post.side_effect = [resp_blocked, resp_ok]

        with patch("builtins.open", mock_open(read_data=b"PNG_IMAGE_DATA")):
            result = media_tools._generate_with_omni("test_image.png", "A prompt with risky tokens")

        self.assertEqual(result, "assets/Video_example.mp4")
        self.assertEqual(mock_post.call_count, 2)
        initial_payload = mock_post.call_args_list[0][1]["json"]
        self.assertEqual(initial_payload["response_format"]["duration"], "10s")
        # Check retry payload used the safe scenario and 10s duration
        retry_payload = mock_post.call_args_list[1][1]["json"]
        self.assertEqual(retry_payload["response_format"]["duration"], "10s")
        self.assertIn("modern architectural space", retry_payload["input"][0]["text"])

    @patch("agents.video_editor.tools.media_tools.get_gemini_api_key", return_value="test_key")
    @patch("agents.video_editor.tools.media_tools.requests.post")
    def test_generate_with_omni_raises_on_429(self, mock_post, mock_key):
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.text = '{"error":{"message":"You exceeded your spend-based rate limit","code":"too_many_requests"}}'
        mock_post.return_value = resp_429

        with patch("builtins.open", mock_open(read_data=b"PNG_DATA")):
            with self.assertRaises(RuntimeError) as cm:
                media_tools._generate_with_omni("test_image.png", "A standard prompt")
            self.assertIn("429", str(cm.exception))
            self.assertIn("spend-based rate limit", str(cm.exception))

    @patch("agents.video_editor.tools.media_tools.video_generation_enabled", return_value=True)
    @patch("agents.video_editor.tools.media_tools.get_gemini_client")
    @patch("agents.video_editor.tools.media_tools.outpaint_to_9_16", return_value="assets/portrait_outpainted.png")
    @patch(
        "agents.video_editor.tools.media_tools._generate_with_omni",
        side_effect=RuntimeError("Gemini Omni Flash generation failed (429): spend-based rate limit"),
    )
    def test_animate_photo_records_failure_state_when_omni_fails(
        self, mock_omni, mock_outpaint, mock_client, mock_enabled
    ):
        tool_context = FakeToolContext({"ENABLE_VIDEO_GENERATION": True}, [])
        res = animate_photo("assets/portrait_outpainted.png", "A nice prompt", tool_context=tool_context)
        self.assertTrue(res.endswith(".png"))
        self.assertIn("video_generation_failure", tool_context.state)
        self.assertIn("429", tool_context.state["video_generation_failure"])

    def test_render_video_card_sets_notice_when_falling_back_to_static_image_with_429(self):
        draft = VideoEditorDraft(
            title="Architektura Wielu Agentów",
            name="Dominika Zając",
            position_company="Tech Lead, Google Developer Groups",
            confirmed=True,
            media=UploadedMedia(event_id="evt_123", part_index=0, mime_type="image/png"),
        )
        mock_context = MagicMock()
        mock_context.session.id = "session_123"
        mock_context.session.state = {"enable_video_generation": True}
        mock_context.state = {
            "video_generation_failure": "Gemini Omni Flash generation failed (429): spend-based rate limit exceeded",
        }
        with (
            patch("agents.video_editor.video_card_service._review_metadata", return_value=None),
            patch("agents.video_editor.video_card_service.workflow.validate_render_environment", return_value=None),
            patch("agents.video_editor.video_card_service.isolated_workspace"),
            patch("agents.video_editor.video_card_service._workspace_tool_paths"),
            patch(
                "agents.video_editor.video_card_service.media_tools.stage_uploaded_media", return_value="portrait.png"
            ),
            patch("agents.video_editor.video_card_service.workflow.validate_resolved_media", return_value=None),
            patch("agents.video_editor.video_card_service._review_face", return_value=None),
            patch(
                "agents.video_editor.video_card_service.media_tools.outpaint_to_9_16",
                return_value="assets/portrait_outpainted.png",
            ),
            patch(
                "agents.video_editor.video_card_service.media_tools.animate_photo",
                return_value="assets/portrait_outpainted.png",
            ),
            patch("agents.video_editor.video_card_service.workflow._read_video_duration", return_value=8),
            patch("agents.video_editor.video_card_service.composer_tools.update_composer"),
            patch(
                "agents.video_editor.video_card_service.composer_tools.render_composer",
                return_value="Generated renders/dominika_zajac_4k.mp4",
            ),
            patch(
                "agents.video_editor.video_card_service.normalise_rendered_assets",
                return_value=[
                    RenderedAsset(kind="video", label="1080p MP4", availability="available", url="file:///test.mp4")
                ],
            ),
        ):
            from agents.video_editor.video_card_service import render_video_card

            result = asyncio.run(render_video_card(draft, mock_context))

        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.notice)
        self.assertIn("429", result.notice)
        self.assertIn("spend-based rate limit", result.notice)
        self.assertIn("расширенного портрета", result.notice)
        self.assertIn("статичное фото", result.notice)

    def test_render_video_card_sets_notice_when_content_blocked(self):
        draft = VideoEditorDraft(
            title="Architektura Wielu Agentów",
            name="Dominika Zając",
            position_company="Tech Lead, Google Developer Groups",
            confirmed=True,
            media=UploadedMedia(event_id="evt_123", part_index=0, mime_type="image/png"),
        )
        mock_context = MagicMock()
        mock_context.session.id = "session_123"
        mock_context.session.state = {"enable_video_generation": True}
        mock_context.state = {
            "video_generation_failure": "Gemini Omni Flash generation failed (400): content_blocked",
        }
        with (
            patch("agents.video_editor.video_card_service._review_metadata", return_value=None),
            patch("agents.video_editor.video_card_service.workflow.validate_render_environment", return_value=None),
            patch("agents.video_editor.video_card_service.isolated_workspace"),
            patch("agents.video_editor.video_card_service._workspace_tool_paths"),
            patch(
                "agents.video_editor.video_card_service.media_tools.stage_uploaded_media", return_value="portrait.png"
            ),
            patch("agents.video_editor.video_card_service.workflow.validate_resolved_media", return_value=None),
            patch("agents.video_editor.video_card_service._review_face", return_value=None),
            patch(
                "agents.video_editor.video_card_service.media_tools.outpaint_to_9_16",
                return_value="assets/portrait_outpainted.png",
            ),
            patch(
                "agents.video_editor.video_card_service.media_tools.animate_photo",
                return_value="assets/portrait_outpainted.png",
            ),
            patch("agents.video_editor.video_card_service.workflow._read_video_duration", return_value=8),
            patch("agents.video_editor.video_card_service.composer_tools.update_composer"),
            patch(
                "agents.video_editor.video_card_service.composer_tools.render_composer",
                return_value="Generated renders/dominika_zajac_4k.mp4",
            ),
            patch(
                "agents.video_editor.video_card_service.normalise_rendered_assets",
                return_value=[
                    RenderedAsset(kind="video", label="1080p MP4", availability="available", url="file:///test.mp4")
                ],
            ),
        ):
            from agents.video_editor.video_card_service import render_video_card

            result = asyncio.run(render_video_card(draft, mock_context))

        self.assertEqual(result.status, "completed")
        self.assertIsNotNone(result.notice)
        self.assertIn("prompt content blocked", result.notice)
        self.assertIn("расширенного портрета", result.notice)
        self.assertIn("статичное фото", result.notice)

    def test_read_video_duration_defaults_to_10_seconds(self):
        from agents.video_editor.workflow import _read_video_duration

        with (
            patch("shutil.which", return_value="/usr/bin/ffprobe"),
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_sub,
        ):
            mock_sub.return_value = MagicMock(returncode=0, stdout="6.0\n")
            # Even for a 6s probed file or Video_example.mp4, standard card timeline is 10s
            duration = _read_video_duration("assets/Video_example.mp4")
            self.assertEqual(duration, 10)

    def test_read_video_duration_respects_longer_custom_video(self):
        from agents.video_editor.workflow import _read_video_duration

        with (
            patch("shutil.which", return_value="/usr/bin/ffprobe"),
            patch("os.path.exists", return_value=True),
            patch("subprocess.run") as mock_sub,
        ):
            mock_sub.return_value = MagicMock(returncode=0, stdout="14.8\n")
            duration = _read_video_duration("assets/custom_longer_talk.mp4")
            self.assertEqual(duration, 15)


if __name__ == "__main__":
    unittest.main(verbosity=2)
