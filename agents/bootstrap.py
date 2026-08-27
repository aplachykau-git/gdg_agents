import os
import sys

try:
    from .gemini_config import load_gemini_environment
except ImportError:
    from gemini_config import load_gemini_environment


def initialise_agent_environment() -> None:
    # Ensure common binary paths (e.g. Homebrew on macOS) are present in PATH for ffmpeg/ffprobe/node
    for path_dir in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        if os.path.isdir(path_dir) and path_dir not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = f"{path_dir}{os.pathsep}{os.environ.get('PATH', '')}"

    load_gemini_environment()

    # Pre-build ADK and GenAI Pydantic models to prevent 'MockValSer' SchemaSerializer errors
    try:
        from google.adk.events.event import Event
        from google.adk.events.event_actions import EventActions

        EventActions.model_rebuild()
        Event.model_rebuild()
    except Exception:
        pass
