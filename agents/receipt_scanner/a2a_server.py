"""
A2A (Agent-to-Agent) Server Entry Point for Receipt Scanner Agent.
Exposes the receipt_scanner agent as a standalone A2A microservice.
"""

import json
import os

import uvicorn
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

load_dotenv(override=True)

from google.adk.a2a.utils.agent_to_a2a import to_a2a

try:
    from .agent import receipt_agent
except (ImportError, ValueError):
    from agents.receipt_scanner.agent import receipt_agent

PORT = int(os.getenv("PORT", os.getenv("RECEIPT_AGENT_PORT", "8082")))
HOST = os.getenv("RECEIPT_AGENT_HOST", "0.0.0.0")
PROTOCOL = os.getenv("RECEIPT_AGENT_PROTOCOL", "http")

# Convert the ADK agent to an A2A-compatible Starlette application
a2a_app = to_a2a(
    agent=receipt_agent,
    host=HOST,
    port=PORT,
    protocol=PROTOCOL,
)


class DynamicAgentCardOriginMiddleware(BaseHTTPMiddleware):
    """Dynamically aligns the agent card RPC URL with the host/origin the request came from."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path.endswith("/.well-known/agent-card.json"):
            body = [section async for section in response.body_iterator]
            full_body = b"".join(body)
            try:
                data = json.loads(full_body.decode("utf-8"))
                proto = request.headers.get("x-forwarded-proto", request.url.scheme)
                host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
                origin = f"{proto}://{host}"
                for iface in data.get("supportedInterfaces", []):
                    iface["url"] = origin
                new_content = json.dumps(data).encode("utf-8")
                headers = dict(response.headers)
                headers["content-length"] = str(len(new_content))
                return Response(
                    content=new_content,
                    status_code=response.status_code,
                    headers=headers,
                    media_type="application/json",
                )
            except Exception:
                return Response(
                    content=full_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
        return response


a2a_app.add_middleware(DynamicAgentCardOriginMiddleware)

if __name__ == "__main__":
    print(f"🚀 Starting Receipt Scanner A2A Server on {PROTOCOL}://{HOST}:{PORT}")
    print(f"📄 Agent Card available at: {PROTOCOL}://{HOST}:{PORT}/.well-known/agent-card.json")
    uvicorn.run("agents.receipt_scanner.a2a_server:a2a_app", host="0.0.0.0", port=PORT, reload=False)
