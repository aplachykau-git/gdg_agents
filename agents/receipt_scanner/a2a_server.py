"""
A2A (Agent-to-Agent) Server Entry Point for Receipt Scanner Agent.
Exposes the receipt_scanner agent as a standalone A2A microservice.
"""

import os
import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

from google.adk.a2a.utils.agent_to_a2a import to_a2a

try:
    from .agent import receipt_agent
except (ImportError, ValueError):
    from agents.receipt_scanner.agent import receipt_agent

PORT = int(os.getenv("RECEIPT_AGENT_PORT", "8082"))
HOST = os.getenv("RECEIPT_AGENT_HOST", "localhost")

# Convert the ADK agent to an A2A-compatible Starlette application
a2a_app = to_a2a(
    agent=receipt_agent,
    host=HOST,
    port=PORT,
    protocol="http",
)

if __name__ == "__main__":
    print(f"🚀 Starting Receipt Scanner A2A Server on http://{HOST}:{PORT}")
    print(f"📄 Agent Card available at: http://{HOST}:{PORT}/.well-known/agent-card.json")
    uvicorn.run("agents.receipt_scanner.a2a_server:a2a_app", host="0.0.0.0", port=PORT, reload=False)
