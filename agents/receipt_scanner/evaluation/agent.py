"""Evaluation-only receipt scanner with local export and rate stubs."""

import os

from google.adk import Agent
from google.adk.tools import ToolContext

from agents.receipt_scanner.agent import INSTRUCTION, receipt_agent
from agents.receipt_scanner.summary import build_receipt_summary
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


FIXTURE_RATES_TO_PLN = {"PLN": 1.0, "USD": 4.0, "EUR": 4.3, "GBP": 5.1, "CHF": 4.5, "CZK": 0.17}


def get_exchange_rate(currency: str, target_currency: str = "PLN") -> dict:
    """Return fixed fixture exchange rate for receipt extraction evaluations."""
    src = (currency or "PLN").strip().upper()
    dst = (target_currency or "PLN").strip().upper()
    src_pln = FIXTURE_RATES_TO_PLN.get(src, 1.0)
    dst_pln = FIXTURE_RATES_TO_PLN.get(dst, 1.0) or 1.0
    return {
        "success": True,
        "currency": src,
        "target_currency": dst,
        "rate": round(src_pln / dst_pln, 6),
        "rate_to_pln": src_pln,
        "source": "Receipt evaluation fixture",
        "url": "",
    }


def show_receipt_summary(
    receipts: list,
    target_currency: str = "",
    approved_budget: str = "",
    exchange_rate: float = None,
    custom_rates: dict = None,
) -> dict:
    """Production-shaped recognition summary with fixed fixture exchange rates."""
    del exchange_rate, custom_rates
    summary = build_receipt_summary(
        receipts,
        target_currency,
        approved_budget,
        rate_to_pln=lambda code: FIXTURE_RATES_TO_PLN.get(code, 1.0),
        community_currency="PLN",
    )
    return {
        "success": True,
        "receipts_count": len(summary["receipts"]),
        "grand_total": summary["grand_total"],
        "target_currency": summary["target_currency"],
        "community_currency": summary["community_currency"],
        "community_total": summary["community_total"],
        "warnings_count": summary["warnings_count"],
        "message": "Receipt evaluation summary captured.",
    }


def export_summary_to_google_doc(
    title: str,
    folder_id: str = None,
    template_id: str = None,
    exchange_rate: float = None,
    receipts_data: list = None,
    target_currency: str = "USD",
    approved_budget: str = "",
    custom_rates: dict = None,
    tool_context: ToolContext = None,
) -> dict:
    """Capture production-shaped export arguments without contacting Google."""
    del title, folder_id, template_id, exchange_rate, receipts_data
    del target_currency, approved_budget, custom_rates, tool_context
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
    tools=[get_usd_pln_rate, get_exchange_rate, read_receipt_file, show_receipt_summary, export_summary_to_google_doc],
)
