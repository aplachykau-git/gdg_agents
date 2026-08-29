"""
A2A (Agent-to-Agent) Service-to-Service Authentication for Google Cloud Run.
Injects Google Cloud OIDC ID tokens into remote A2A calls when communicating over HTTPS.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from a2a.types import Message as A2AMessage
from google.adk.a2a.agent.config import (
    A2aCardRequestConfig,
    A2aRemoteAgentConfig,
    CardRequestInterceptor,
    ParametersConfig,
    RequestInterceptor,
)
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import _add_request_headers
from google.adk.events.event import Event

logger = logging.getLogger(__name__)


def get_a2a_auth_headers(target_url: str) -> dict[str, str]:
    """Generates Google Cloud OIDC ID token authorization headers for Cloud Run service-to-service calls.

    For local development URLs (http://localhost or http://127.0.0.1), returns an empty dictionary.
    """
    if not target_url or not target_url.startswith("https://"):
        return {}

    parsed = urlparse(target_url)
    audience = f"{parsed.scheme}://{parsed.netloc}"

    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        auth_req = google.auth.transport.requests.Request()
        token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
        if token:
            return {"Authorization": f"Bearer {token}"}
    except Exception as e:
        logger.debug("OIDC ID token fetch for %s was skipped or failed: %s", audience, e)

    return {}


def create_authenticated_a2a_config(target_url: str) -> A2aRemoteAgentConfig:
    """Creates an A2aRemoteAgentConfig with request and card-request interceptors

    that automatically authenticate against private Cloud Run A2A services.
    """

    async def before_card_request(_ctx: InvocationContext) -> A2aCardRequestConfig:
        headers = get_a2a_auth_headers(target_url)
        return A2aCardRequestConfig(headers=headers or None)

    async def before_request(
        _ctx: InvocationContext,
        a2a_request: A2AMessage,
        parameters: ParametersConfig,
    ) -> tuple[A2AMessage | Event, ParametersConfig]:
        headers = get_a2a_auth_headers(target_url)
        if headers:
            _add_request_headers(parameters, headers)
        return a2a_request, parameters

    return A2aRemoteAgentConfig(
        card_request_interceptors=[CardRequestInterceptor(before_request=before_card_request)],
        request_interceptors=[RequestInterceptor(before_request=before_request)],
    )
