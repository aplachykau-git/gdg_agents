"""Shared agent initialisation for package and workspace-direct imports."""

try:
    from .gemini_config import load_gemini_environment
except ImportError:
    from gemini_config import load_gemini_environment


def initialise_agent_environment() -> None:
    load_gemini_environment()
