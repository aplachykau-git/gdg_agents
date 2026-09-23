"""Runtime wiring shared by the ADK API server and the A2A microservices.

Sessions (and with them the video-editor card, receipt drafts, chat history) must survive
container restarts and Cloud Run scaling to several instances. They are therefore stored in a
database configured with ``SESSION_SERVICE_URI``:

* production: ``postgresql+asyncpg://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE``
  (Cloud SQL via the Cloud Run unix-socket mount; see terraform/sessions_db.tf)
* local default (unset): a SQLite file per service under ``agents/<agent>/.adk/``
* ``memory://`` keeps the old in-memory behaviour (tests only).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from google.adk.agents.base_agent import BaseAgent
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions.base_session_service import BaseSessionService
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

AGENTS_ROOT = Path(__file__).resolve().parent.parent
SESSION_SERVICE_URI_ENV = "SESSION_SERVICE_URI"


def session_service_uri() -> str | None:
    value = os.getenv(SESSION_SERVICE_URI_ENV, "").strip()
    return value or None


def _redact(uri: str) -> str:
    if "@" in uri and "://" in uri:
        scheme, rest = uri.split("://", 1)
        return f"{scheme}://***@{rest.split('@', 1)[1]}"
    return uri


def build_session_service(local_name: str) -> BaseSessionService:
    """Session service for a standalone service called ``local_name`` (used for the local SQLite file)."""
    from google.adk.cli.utils.service_factory import create_session_service_from_options

    uri = session_service_uri()
    if uri is None:
        db_dir = AGENTS_ROOT / local_name / ".adk"
        db_dir.mkdir(parents=True, exist_ok=True)
        uri = f"sqlite:///{db_dir / 'a2a_sessions.db'}"
    logger.info("Session storage for %s: %s", local_name, _redact(uri))
    return create_session_service_from_options(base_dir=AGENTS_ROOT, session_service_uri=uri)


def build_runner(agent: BaseAgent, local_name: str) -> Runner:
    return Runner(
        app_name=agent.name or local_name,
        agent=agent,
        session_service=build_session_service(local_name),
        artifact_service=InMemoryArtifactService(),
        memory_service=InMemoryMemoryService(),
        credential_service=InMemoryCredentialService(),
    )


class DynamicAgentCardOriginMiddleware(BaseHTTPMiddleware):
    """Rewrites the agent-card RPC URL to the origin the request came from (Cloud Run URLs vary)."""

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if not request.url.path.endswith("/.well-known/agent-card.json"):
            return response
        body = b"".join([section async for section in response.body_iterator])
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        try:
            data = json.loads(body.decode("utf-8"))
            proto = request.headers.get("x-forwarded-proto", request.url.scheme)
            host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
            for iface in data.get("supportedInterfaces", []):
                iface["url"] = f"{proto}://{host}"
            body = json.dumps(data).encode("utf-8")
        except Exception:
            logger.warning("Agent card origin rewrite failed; returning the original card", exc_info=True)
        return Response(content=body, status_code=response.status_code, headers=headers, media_type="application/json")


def build_a2a_app(agent: BaseAgent, *, local_name: str, host: str, port: int, protocol: str) -> Starlette:
    """A2A Starlette app with persistent sessions and origin-aware agent card."""
    from google.adk.a2a.utils.agent_to_a2a import to_a2a

    app = to_a2a(agent=agent, host=host, port=port, protocol=protocol, runner=build_runner(agent, local_name))
    app.add_middleware(DynamicAgentCardOriginMiddleware)
    return app
