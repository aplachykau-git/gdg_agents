"""Evaluation-only receipt scanner with local export and rate stubs."""

import os

from google.adk import Agent
from google.adk.tools import ToolContext

from agents.receipt_scanner.agent import INSTRUCTION, receipt_agent
from agents.receipt_scanner.tools import read_receipt_file

PRODUCTION_MODEL = str(receipt_agent.model)
EVALUATION_MODEL = os.getenv("RECEIPT_EVAL_MODEL", PRODUCTION_MODEL)


def get_usd_pln_rate() -> dict:
    """Return the fixed USD/PLN rate used by receipt extraction evaluations."""
    return {
        "success": True,
        "rate": 4.0,
        "source": "Receipt evaluation fixture",
        "url": "",
    }


def export_summary_to_google_doc(
    title: str,
    folder_id: str = None,
    template_id: str = None,
    exchange_rate: float = None,
    receipts_data: list = None,
    target_currency: str = "USD",
    approved_budget: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """Capture production-shaped export arguments without contacting Google."""
    del title, folder_id, template_id, exchange_rate, receipts_data
    del target_currency, approved_budget, tool_context
    return {
        "success": True,
        "document_id": "receipt-evaluation-document",
        "document_url": "https://docs.google.com/document/d/receipt-evaluation-document/edit",
        "message": "Receipt evaluation export captured.",
    }


root_agent = Agent(
    model=EVALUATION_MODEL,
    name="receipt_scanner",
    description="Evaluation-only receipt scanner.",
    instruction=INSTRUCTION.replace(str(receipt_agent.model), EVALUATION_MODEL),
    tools=[get_usd_pln_rate, read_receipt_file, export_summary_to_google_doc],
)
