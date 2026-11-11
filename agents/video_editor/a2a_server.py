"""A2A (Agent-to-Agent) entry point exposing the video_editor agent as a standalone microservice."""

import logging
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from agents.common.logging_setup import configure_logging
    from agents.common.runtime import build_a2a_app

    from .agent import video_editor_agent
except (ImportError, ValueError):
    from agents.common.logging_setup import configure_logging
    from agents.common.runtime import build_a2a_app
    from agents.video_editor.agent import video_editor_agent

configure_logging()
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", os.getenv("VIDEO_AGENT_PORT", "8181")))
HOST = os.getenv("VIDEO_AGENT_HOST", "0.0.0.0")
PROTOCOL = os.getenv("VIDEO_AGENT_PROTOCOL", "http")

a2a_app = build_a2a_app(video_editor_agent, local_name="video_editor", host=HOST, port=PORT, protocol=PROTOCOL)

if __name__ == "__main__":
    logger.info("Starting Video Editor A2A server on %s://%s:%s", PROTOCOL, HOST, PORT)
    uvicorn.run("agents.video_editor.a2a_server:a2a_app", host="0.0.0.0", port=PORT, reload=False)
