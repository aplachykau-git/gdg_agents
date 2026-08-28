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
        import google.genai.types as genai_types
        from pydantic import BaseModel

        types_namespace = vars(genai_types)
        for attr_name in dir(genai_types):
            obj = getattr(genai_types, attr_name)
            if isinstance(obj, type) and issubclass(obj, BaseModel):
                try:
                    obj.model_rebuild(_types_namespace=types_namespace)
                except Exception:
                    pass

        from google.adk.events.event import Event
        from google.adk.events.event_actions import EventActions

        EventActions.model_rebuild()
        Event.model_rebuild()
    except Exception:
        pass
