"""Tools of the office secretary agent."""

from __future__ import annotations

import re

from agents.common import ui_payloads

PLACEHOLDER_DATE = re.compile(r"\[(?:insert\s+)?(?:the\s+)?date[^\]]*\]", re.IGNORECASE)


def present_email_draft(subject: str, body: str) -> dict:
    """Show the finished e-mail to the user as an e-mail card (copy / open in Gmail / mail app).

    Call this once the e-mail is complete. Afterwards reply with one short sentence; do not
    repeat the e-mail text.

    Args:
        subject: E-mail subject line without the "Subject:" prefix.
        body: Full e-mail body, from the greeting to the signature.
    """
    subject = re.sub(r"^\s*subject\s*:\s*", "", subject or "", flags=re.IGNORECASE).strip()
    body = (body or "").strip()
    if not subject or not body:
        return {"status": "error", "message": "Both subject and body are required."}
    if PLACEHOLDER_DATE.search(subject + "\n" + body):
        return {
            "status": "error",
            "message": "The e-mail still contains a date placeholder. Ask the user for the date instead of inventing one.",
        }
    return {
        "status": "ok",
        "message": "The e-mail card is shown to the user.",
        "ui": ui_payloads.email_draft(subject, body),
    }
