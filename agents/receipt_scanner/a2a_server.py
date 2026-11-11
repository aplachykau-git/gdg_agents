"""A2A (Agent-to-Agent) entry point exposing the receipt_scanner agent as a standalone microservice."""

import logging
import os

import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    from agents.common.logging_setup import configure_logging
    from agents.common.runtime import build_a2a_app

    from .agent import receipt_agent
except (ImportError, ValueError):
    from agents.common.logging_setup import configure_logging
    from agents.common.runtime import build_a2a_app
    from agents.receipt_scanner.agent import receipt_agent

configure_logging()
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", os.getenv("RECEIPT_AGENT_PORT", "8082")))
HOST = os.getenv("RECEIPT_AGENT_HOST", "0.0.0.0")
PROTOCOL = os.getenv("RECEIPT_AGENT_PROTOCOL", "http")

a2a_app = build_a2a_app(receipt_agent, local_name="receipt_scanner", host=HOST, port=PORT, protocol=PROTOCOL)

if __name__ == "__main__":
    logger.info("Starting Receipt Scanner A2A server on %s://%s:%s", PROTOCOL, HOST, PORT)
    uvicorn.run("agents.receipt_scanner.a2a_server:a2a_app", host="0.0.0.0", port=PORT, reload=False)
