"""Shared Gemini backend configuration for agents and direct SDK tool calls."""

import os

from dotenv import load_dotenv
from google import genai


class GeminiConfigurationError(RuntimeError):
    """Raised when the selected Gemini backend is not fully configured."""


def load_gemini_environment() -> None:
    """Load workspace configuration and validate Gemini API mode early."""
    load_dotenv()
    api_key = (
        os.getenv("GOOGLE_API_KEY", "").strip()
        or os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_GENAI_API_KEY", "").strip()
    )
    if api_key:
        os.environ["GOOGLE_API_KEY"] = api_key
        os.environ["GEMINI_API_KEY"] = api_key
        os.environ["GOOGLE_GENAI_API_KEY"] = api_key
    if not use_vertex_ai():
        get_gemini_api_key()


def use_vertex_ai() -> bool:
    """Return the backend selected by GOOGLE_GENAI_USE_VERTEXAI."""
    value = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "1").strip().lower()
    if value in {"1", "true"}:
        return True
    if value in {"0", "false"}:
        return False
    raise GeminiConfigurationError(
        "GOOGLE_GENAI_USE_VERTEXAI must be 1/true for Vertex AI or 0/false for the Gemini API."
    )


def get_gemini_api_key() -> str:
    """Return the configured Gemini Developer API key."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigurationError(
            "GOOGLE_API_KEY or GEMINI_API_KEY is required when GOOGLE_GENAI_USE_VERTEXAI=0. "
            "Set an API key or enable Vertex AI with GOOGLE_GENAI_USE_VERTEXAI=1."
        )
    return api_key


def get_gemini_client() -> genai.Client:
    """Create a Gen AI client for the configured inference backend."""
    if not use_vertex_ai():
        return genai.Client(api_key=get_gemini_api_key(), vertexai=False)

    client_args: dict[str, str | bool] = {"vertexai": True}
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "").strip()
    if project:
        client_args["project"] = project
    if location:
        client_args["location"] = location
    return genai.Client(**client_args)


def require_vertex_ai(feature_name: str) -> None:
    """Fail clearly when a Vertex-only feature is selected in Gemini API mode."""
    if not use_vertex_ai():
        raise GeminiConfigurationError(
            f"{feature_name} requires Vertex AI. Set GOOGLE_GENAI_USE_VERTEXAI=1, "
            "or use VIDEO_ENGINE=omni with GOOGLE_API_KEY or GEMINI_API_KEY."
        )
