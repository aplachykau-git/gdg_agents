import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.video_editor.tools.composer_tools import build_card_config
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

        failure = validate_resolved_media(
            ResolvedMedia(source_path=image_path, media_type="image")
        )

        self.assertEqual(failure.code, "invalid_image")

    def test_validate_resolved_media_uses_webp_image_validation(self):
        with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as image:
            image.write(b"not a WebP")
            image_path = image.name
        self.addCleanup(Path(image_path).unlink, missing_ok=True)

        failure = validate_resolved_media(
            ResolvedMedia(source_path=image_path, media_type="image")
        )

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
