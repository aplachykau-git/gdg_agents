"""Unit tests for the selectable Vertex AI and Gemini API inference backends."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from agents import gemini_config
from agents.gemini_config import GeminiConfigurationError
from agents.receipt_scanner.tools import read_receipt_file
from agents.video_editor.tools import media_tools


class TestGeminiBackendConfiguration(unittest.TestCase):
    def test_api_mode_agent_import_smoke_test_needs_no_vertex_credentials(self):
        environment = os.environ.copy()
        environment.update(
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "0",
                "GEMINI_API_KEY": "test-gemini-key",
            }
        )
        environment.pop("GOOGLE_API_KEY", None)
        environment.pop("GOOGLE_CLOUD_PROJECT", None)
        environment.pop("GOOGLE_CLOUD_LOCATION", None)
        project_root = Path(__file__).resolve().parent.parent
        environment["PYTHONPATH"] = str(project_root)

        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, "-c", "from agents.root_agent.agent import root_agent; print(root_agent.name)"],
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("root_agent", result.stdout)

    def test_api_mode_creates_non_vertex_client_with_gemini_key(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "0",
                "GOOGLE_API_KEY": "",
                "GEMINI_API_KEY": "test-gemini-key",
            },
            clear=False,
        ):
            with patch.object(gemini_config.genai, "Client") as client:
                gemini_config.get_gemini_client()

        client.assert_called_once_with(api_key="test-gemini-key", vertexai=False)

    def test_api_mode_prefers_google_api_key(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "0",
                "GOOGLE_API_KEY": "preferred-google-key",
                "GEMINI_API_KEY": "fallback-gemini-key",
            },
            clear=False,
        ):
            with patch.object(gemini_config.genai, "Client") as client:
                gemini_config.get_gemini_client()

        client.assert_called_once_with(api_key="preferred-google-key", vertexai=False)

    def test_api_mode_requires_gemini_key(self):
        with patch.dict(
            os.environ,
            {"GOOGLE_GENAI_USE_VERTEXAI": "0", "GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""},
            clear=False,
        ):
            with self.assertRaisesRegex(GeminiConfigurationError, "GOOGLE_API_KEY or GEMINI_API_KEY is required"):
                gemini_config.get_gemini_client()

    def test_direct_agent_loads_with_google_api_key(self):
        environment = os.environ.copy()
        environment.update(
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "0",
                "GOOGLE_API_KEY": "test-google-key",
            }
        )
        environment.pop("GEMINI_API_KEY", None)
        environment.pop("GOOGLE_CLOUD_PROJECT", None)
        environment.pop("GOOGLE_CLOUD_LOCATION", None)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent / "agents")

        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from linkedin_post_generator.agent import root_agent; print(root_agent.name)",
                ],
                cwd=working_directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("linkedin_post_generator", result.stdout)

    def test_vertex_mode_creates_vertex_client_with_project_and_location(self):
        with patch.dict(
            os.environ,
            {
                "GOOGLE_GENAI_USE_VERTEXAI": "1",
                "GOOGLE_CLOUD_PROJECT": "test-project",
                "GOOGLE_CLOUD_LOCATION": "europe-central2",
            },
            clear=False,
        ):
            with patch.object(gemini_config.genai, "Client") as client:
                gemini_config.get_gemini_client()

        client.assert_called_once_with(
            vertexai=True,
            project="test-project",
            location="europe-central2",
        )

    def test_gemini_api_mode_rejects_veo(self):
        with patch.dict(
            os.environ,
            {"GOOGLE_GENAI_USE_VERTEXAI": "0", "GEMINI_API_KEY": "test-gemini-key"},
            clear=False,
        ):
            with self.assertRaisesRegex(GeminiConfigurationError, "VIDEO_ENGINE=veo requires Vertex AI"):
                media_tools.validate_video_generation_backend("veo")
            media_tools.validate_video_generation_backend("omni")


class TestToolsUseSharedGeminiClient(unittest.TestCase):
    def test_receipt_reader_uses_shared_backend_client(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(b"not-a-real-image")
            image_path = image.name
        self.addCleanup(Path(image_path).unlink, missing_ok=True)

        client = MagicMock()
        client.models.generate_content.return_value.text = "Example receipt"
        with patch("agents.receipt_scanner.tools.get_gemini_client", return_value=client) as factory:
            result = read_receipt_file(image_path)

        factory.assert_called_once_with()
        self.assertTrue(result["success"])

    def test_face_verification_uses_shared_backend_client(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image:
            image.write(b"not-a-real-image")
            image_path = image.name
        self.addCleanup(Path(image_path).unlink, missing_ok=True)

        client = MagicMock()
        client.models.generate_content.return_value.text = "YES"
        with patch("agents.video_editor.tools.media_tools.get_gemini_client", return_value=client) as factory:
            result = media_tools.verify_portrait_photo(image_path)

        factory.assert_called_once_with()
        self.assertEqual(result, "photo")


if __name__ == "__main__":
    unittest.main(verbosity=2)
