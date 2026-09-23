"""Shared Gemini backend configuration for agents and direct SDK tool calls."""

import os

from dotenv import load_dotenv
from google import genai

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_IMAGE_MODEL = "gemini-3.1-flash-lite-image"


def model_for(role: str, default: str = DEFAULT_MODEL, legacy_env: str | None = None) -> str:
    """Model id for an agent or an internal step, configurable without code changes.

    Resolution order: ``MODEL_<ROLE>`` (e.g. ``MODEL_VIDEO_EDITOR``), a legacy variable name if the
    step already had one, ``GEMINI_MODEL`` (for text roles), then ``default``.
    """
    candidates = [f"MODEL_{role.upper()}"]
    if legacy_env:
        candidates.append(legacy_env)
    if default == DEFAULT_MODEL:
        candidates.append("GEMINI_MODEL")
    for name in candidates:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


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
