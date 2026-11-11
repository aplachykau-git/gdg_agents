"""Structured UI payloads ("ui" contract) shared by all agents.

The web UI renders rich cards (post variants, agenda timeline, e-mail draft, meetup dates,
documents, videos) from a small JSON payload instead of guessing them from free text with
regular expressions. A payload always has a ``type`` and travels in one of two ways:

* inside a tool result: ``{"...": ..., "ui": {"type": "document", ...}}``
* on a model text event: ``event.custom_metadata["ui"]`` — added by :func:`text_ui_callback`
  for agents whose deliverable is the model's own text (LinkedIn posts, agendas).

Every payload type is documented by the builder functions below; the frontend adapters in
``frontend/src/lib/ui/payloads.js`` mirror them.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Sequence

logger = logging.getLogger(__name__)

UI_KEY = "ui"
UiPayload = dict[str, Any]


# --------------------------------------------------------------------------- builders


def post_variants(variants: Sequence[dict[str, Any]], intro: str = "") -> UiPayload:
    """``variants``: [{"number": 1, "name": "The Architect", "body": "..."}]."""
    return {"type": "post_variants", "intro": intro, "variants": list(variants)}


def agenda(text: str, items: Sequence[dict[str, str]]) -> UiPayload:
    """``text``: copy-paste agenda; ``items``: [{"emoji": "🎤", "time": "18:10", "title": "..."}]."""
    return {"type": "agenda", "text": text, "items": list(items)}


def email_draft(subject: str, body: str, intro: str = "") -> UiPayload:
    return {"type": "email_draft", "subject": subject, "body": body, "intro": intro}


def meetup_dates(dates: Sequence[dict[str, Any]], event_title: str = "", location: str = "") -> UiPayload:
    """``dates``: [{"date": "2026-10-14", "weekday": "Wednesday", "reason": "...", "primary": True}]."""
    return {"type": "meetup_dates", "event_title": event_title, "location": location, "dates": list(dates)}


def document(
    url: str,
    *,
    title: str,
    kind: str,
    file_type: str,
    filename: str = "",
    extra_urls: dict[str, str] | None = None,
    roster_text: str | None = None,
) -> UiPayload:
    """A downloadable deliverable. ``kind``: "registration_roster" | "expense_report"."""
    return {
        "type": "document",
        "kind": kind,
        "url": url,
        "title": title,
        "file_type": file_type,
        "filename": filename or os.path.basename(url.split("?")[0]),
        "extra_urls": extra_urls or {},
        "roster_text": roster_text,
    }


def media(assets: Sequence[dict[str, Any]], speaker: dict[str, Any] | None = None, notice: str = "") -> UiPayload:
    """Rendered video card. ``assets``: [{"label": ..., "url": ...}] as produced by the renderer."""
    by_kind: dict[str, str] = {}
    for asset in assets:
        url = asset.get("url") or ""
        if not url or asset.get("availability", "available") != "available":
            continue
        lower = url.lower().split("?")[0]
        label = (asset.get("label") or "").lower()
        if lower.endswith((".mp4", ".webm", ".mov")):
            by_kind.setdefault("video_4k" if "4k" in label else "video", url)
        elif lower.endswith(".gif"):
            by_kind.setdefault("gif", url)
        elif "avatar" in lower or "avatar" in label:
            by_kind.setdefault("avatar", url)
        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            by_kind.setdefault("poster", url)
    if "video" not in by_kind and "video_4k" in by_kind:
        by_kind["video"] = by_kind["video_4k"]
    return {"type": "media", "urls": by_kind, "assets": list(assets), "speaker": speaker or {}, "notice": notice}


def video_output_choice(speaker: dict[str, Any], media_kind: str = "image", avatar_url: str | None = None) -> UiPayload:
    """Interactive choice card asking whether to create only a static 4K cover photo or an animated video."""
    payload: UiPayload = {
        "type": "video_output_choice",
        "speaker": dict(speaker or {}),
        "media_kind": media_kind or "image",
    }
    if avatar_url:
        payload["avatar_url"] = avatar_url
    return payload


def qr_code(
    link: str, *, svg_url: str, png_url: str, filename: str, color: str, background: str, transparent: bool
) -> UiPayload:
    """QR code with its flat SVG and PNG downloads."""
    return {
        "type": "qr_code",
        "link": link,
        "svg_url": svg_url,
        "png_url": png_url,
        "filename": filename,
        "color": color,
        "background": "transparent" if transparent else background,
    }


def receipt_summary(summary: dict[str, Any]) -> UiPayload:
    """What the receipt scanner recognised: per-receipt line items, totals, conversion, budget.

    ``summary`` comes from ``agents.receipt_scanner.summary.build_receipt_summary`` and carries a
    plain-text version in ``summary["text"]`` for copying.
    """
    return {"type": "receipt_summary", **summary}


def post_plan(plan: dict[str, Any]) -> UiPayload:
    """Countdown post plan from ``agents.linkedin_post_generator.countdown.validate_posts``:
    dated slots with the chosen networks, the written posts per network, and a CSV for Sheets."""
    return {"type": "post_plan", **plan}


def event_profile(
    profile: dict[str, Any], *, missing: Sequence[str] = (), persist: bool = False, updated_at: str = ""
) -> UiPayload:
    """Editable event details card (name, date, website, venue, highlights, hashtags, social
    profiles, countdown). ``persist``: the frontend stores ``profile`` for future sessions;
    ``missing``: fields the user still has to fill in."""
    return {
        "type": "event_profile",
        "profile": profile,
        "missing": list(missing),
        "persist": persist,
        "updated_at": updated_at,
    }


# --------------------------------------------------------------------------- text parsers

VARIANT_HEADER = re.compile(r"(?m)^###\s*Variant\s+([1-9]\d*)\s*:\s*([^\n]+?)\s*$")


def parse_post_variants(text: str) -> UiPayload | None:
    matches = list(VARIANT_HEADER.finditer(text))
    if len(matches) < 2:
        return None
    variants = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        variants.append(
            {"number": int(match.group(1)), "name": match.group(2).strip(), "body": text[match.end() : end].strip()}
        )
    return post_variants(variants, intro=text[: matches[0].start()].strip())


AGENDA_ITEM = re.compile(r"(?m)^\s*(\S{1,3})?\s*(\d{1,2}:\d{2})\s*[-–—]\s*(.+?)\s*$")


def parse_agenda(text: str) -> UiPayload | None:
    if not re.search(r"(?m)^\s*AGENDA\s*$", text):
        return None
    items = [
        {"emoji": (m.group(1) or "").strip(), "time": m.group(2), "title": m.group(3).strip()}
        for m in AGENDA_ITEM.finditer(text)
    ]
    if len(items) < 3:
        return None
    return agenda(text.strip(), items)


# --------------------------------------------------------------------------- ADK callback


def _response_text(llm_response: Any) -> str:
    content = getattr(llm_response, "content", None)
    parts = getattr(content, "parts", None) or []
    return "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))


def text_ui_callback(*parsers: Callable[[str], UiPayload | None]):
    """``after_model_callback`` that attaches the first matching payload to final text responses."""

    def callback(callback_context: Any, llm_response: Any) -> Any:
        if getattr(llm_response, "partial", False):
            return None
        text = _response_text(llm_response)
        if not text.strip():
            return None
        for parser in parsers:
            try:
                payload = parser(text)
            except Exception:
                logger.exception("UI payload parser %s failed", getattr(parser, "__name__", parser))
                continue
            if payload:
                llm_response.custom_metadata = {**(llm_response.custom_metadata or {}), UI_KEY: payload}
                return llm_response
        return None

    return callback
