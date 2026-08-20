"""
A2A (Agent-to-Agent) Server Entry Point for Video Editor Agent.
Exposes the video_editor agent as a standalone A2A microservice.
"""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

from google.adk.a2a.utils.agent_to_a2a import to_a2a

try:
    from .agent import video_editor_agent
except (ImportError, ValueError):
    from agents.video_editor.agent import video_editor_agent

PORT = int(os.getenv("VIDEO_AGENT_PORT", "8081"))
HOST = os.getenv("VIDEO_AGENT_HOST", "localhost")

# Convert the ADK agent to an A2A-compatible Starlette application
a2a_app = to_a2a(
    agent=video_editor_agent,
    host=HOST,
    port=PORT,
    protocol="http",
)

if __name__ == "__main__":
    print(f"🚀 Starting Video Editor A2A Server on http://{HOST}:{PORT}")
    print(f"📄 Agent Card available at: http://{HOST}:{PORT}/.well-known/agent-card.json")
    uvicorn.run("agents.video_editor.a2a_server:a2a_app", host="0.0.0.0", port=PORT, reload=False)
