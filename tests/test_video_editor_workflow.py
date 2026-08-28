import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents.video_editor.tools.composer_tools import build_card_config, render_composer
from agents.video_editor.tools.media_tools import animate_photo
from agents.video_editor.workflow import (
    classify_media_path,
    validate_render_environment,
    validate_request_metadata_fields,
    validate_resolved_media,
)
from agents.video_editor.workflow_models import ResolvedMedia, VideoEditorRequest


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
            VideoEditorRequest(
                title="Talk",
                name="J" * 51,
                position_company="Role",
            )
        )

        self.assertEqual(result.code, "field_too_long")
        self.assertEqual(result.field, "name")

    def test_validate_request_metadata_fields_requests_missing_name(self):
        result = validate_request_metadata_fields(
            VideoEditorRequest(
                title="Talk",
                position_company=None,
            )
        )

        self.assertEqual(result.code, "missing_field")
        self.assertEqual(result.field, "name")
        self.assertEqual(result.requested_action, "correct_text")

    def test_classify_media_path_detects_supported_types(self):
        self.assertEqual(classify_media_path("speaker.png"), "image")
        self.assertEqual(classify_media_path("speaker.mp4"), "video")
        self.assertEqual(classify_media_path("speaker.txt"), "unknown")

    def test_validate_resolved_media_rejects_placeholder(self):
        failure = validate_resolved_media(
            ResolvedMedia(
                source_path="assets/portrait_outpainted.png",
                media_type="image",
                placeholder_used=True,
            )
        )

        self.assertEqual(failure.code, "media_not_found")
        self.assertEqual(failure.requested_action, "replace_media")

    def test_validate_render_environment_rejects_missing_ffmpeg_before_generation(self):
        with patch("agents.video_editor.workflow.shutil.which", return_value=None):
            failure = validate_render_environment()

        self.assertEqual(failure.code, "render_environment_unavailable")
        self.assertFalse(failure.retryable)

    def test_validate_resolved_media_rejects_corrupt_image(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(b"not a PNG")
            image_path = image.name
        self.addCleanup(Path(image_path).unlink, missing_ok=True)

        failure = validate_resolved_media(ResolvedMedia(source_path=image_path, media_type="image"))

        self.assertEqual(failure.code, "invalid_image")

    def test_validate_resolved_media_uses_webp_image_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as image:
            image.write(b"not a WebP")
            image_path = image.name
        self.addCleanup(Path(image_path).unlink, missing_ok=True)

        failure = validate_resolved_media(ResolvedMedia(source_path=image_path, media_type="image"))

        self.assertEqual(failure.code, "invalid_image")

    def test_card_config_escapes_metadata_for_javascript(self):
        config = build_card_config(
            title='Talk: "quotes"\nnew line',
            name='A "quoted" name',
            position_company="R&D \\ Platform",
            year=2026,
        )

        self.assertIn('title: "Talk: \\"quotes\\"\\nnew line"', config)
        self.assertIn('name: "A \\"quoted\\" name"', config)
        self.assertIn('position_company: "R&D \\\\ Platform"', config)

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
