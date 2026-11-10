import base64
import datetime
import io
import json
import logging
import mimetypes
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Callable, List, Optional

import requests
from google.adk.tools import ToolContext
from google.genai import types

try:
    from .google_auth import get_google_credentials
except (ImportError, ValueError):
    from agents.receipt_scanner.google_auth import get_google_credentials

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
except ImportError:
    build = None
    MediaFileUpload = None
    MediaIoBaseUpload = None

from agents.common import ui_payloads
from agents.common.event_series import community_currency_from_state

try:
    from .docx_generator import deduplicate_and_compress_proofs, reorder_proofs_for_grouped_receipts
    from .summary import build_receipt_summary, group_and_sort_receipts, normalize_currency_code
except ImportError:
    from agents.receipt_scanner.docx_generator import (
        deduplicate_and_compress_proofs,
        reorder_proofs_for_grouped_receipts,
    )
    from agents.receipt_scanner.summary import (
        build_receipt_summary,
        group_and_sort_receipts,
        normalize_currency_code,
    )
from agents.gemini_config import get_gemini_client, model_for

logger = logging.getLogger(__name__)


def extract_google_drive_folder_id(raw_input: Optional[str]) -> Optional[str]:
    """
    Extracts and validates a Google Drive Folder ID from a raw ID or full Google Drive URL.
    Supports URLs such as:
      - https://drive.google.com/drive/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ
      - https://drive.google.com/drive/u/0/folders/1aBcDeFgHiJkLmNoPqRsTuVwXyZ?usp=sharing
      - https://drive.google.com/open?id=1aBcDeFgHiJkLmNoPqRsTuVwXyZ
      - Raw alphanumeric IDs (e.g. 1aBcDeFgHiJkLmNoPqRsTuVwXyZ)
    """
    if not raw_input or not str(raw_input).strip():
        return None
    val = str(raw_input).strip()

    # If it's a full URL
    if val.startswith("http://") or val.startswith("https://"):
        # Match /folders/<id>
        match = re.search(r"/folders/([a-zA-Z0-9_-]+)", val)
        if match:
            return match.group(1)
        # Match ?id=<id> or &id=<id>
        match_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", val)
        if match_id:
            return match_id.group(1)
        return None

    # If raw ID, validate characters
    if re.match(r"^[a-zA-Z0-9_-]{10,80}$", val):
        return val
    return None


def extract_google_doc_id(raw_input: Optional[str]) -> Optional[str]:
    """
    Extracts and validates a Google Doc ID from a raw ID or full Google Docs URL.
    Supports URLs such as:
      - https://docs.google.com/document/d/1aBcDeFgHiJkLmNoPqRsTuVwXyZ/edit
      - https://docs.google.com/open?id=1aBcDeFgHiJkLmNoPqRsTuVwXyZ
      - Raw alphanumeric IDs (e.g. 1aBcDeFgHiJkLmNoPqRsTuVwXyZ)
    """
    if not raw_input or not str(raw_input).strip():
        return None
    val = str(raw_input).strip()

    if val.startswith("http://") or val.startswith("https://"):
        match = re.search(r"/document/d/([a-zA-Z0-9_-]+)", val)
        if match:
            return match.group(1)
        match_id = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", val)
        if match_id:
            return match_id.group(1)
        return None

    if re.match(r"^[a-zA-Z0-9_-]{10,80}$", val):
        return val
    return None


def _extract_text_from_gdoc(doc_struct: dict) -> str:
    """Extracts all raw text content from a Google Docs document structure."""
    chunks = []

    def _recurse(node):
        if isinstance(node, dict):
            if "content" in node and isinstance(node["content"], str):
                chunks.append(node["content"])
            for v in node.values():
                _recurse(v)
        elif isinstance(node, list):
            for item in node:
                _recurse(item)

    _recurse(doc_struct.get("body", {}))
    return "".join(chunks)


REQUIRED_TEMPLATE_TAGS = [
    "{{TITLE}}",
    "{{Current date}}",
    "{{TOTAL SUM CURR}}",
    "{{TOTAL SUM EUR/USD}}",
    "{{Category}}",
    "{{Desc}}",
    "{{SUM CURR}}",
    "{{SUM EUR/USD}}",
]


def _find_expenses_table_in_gdoc(doc_struct: dict) -> tuple[Optional[int], list[dict]]:
    """Locate the main Expenses Table in a Google Docs document structure."""
    body_content = ((doc_struct or {}).get("body") or {}).get("content") or []
    fallback_match: tuple[Optional[int], list[dict]] = (None, [])
    for element in body_content:
        if not isinstance(element, dict) or "table" not in element:
            continue
        table = element.get("table") or {}
        rows = table.get("tableRows") or []
        table_start = element.get("startIndex")
        table_text = _extract_text_from_gdoc({"body": {"content": [element]}})
        if "Description of Expense" in table_text or "Total Spent" in table_text or "Original Cost" in table_text:
            return table_start, rows
        if fallback_match[0] is None and len(rows) >= 3 and len((rows[0].get("tableCells") or [])) >= 4:
            fallback_match = (table_start, rows)
    return fallback_match


def _diagnose_gdoc_template(doc_struct: dict) -> list[str]:
    """Check a Google Docs template for legacy/missing placeholders and return human-readable notes."""
    text = _extract_text_from_gdoc(doc_struct)
    notes: list[str] = []
    if not text.strip():
        return notes
    if "{{TITLE}}" not in text:
        notes.append("Template is missing '{{TITLE}}' at the top of the document.")
    if "{{Category}}" not in text:
        notes.append(
            "Template 'Category' column uses a Google Docs dropdown ('Choose') instead of '{{Category}}' "
            "(handled automatically by inserting separate table rows)."
        )
    if "{{SUM PL}}" in text or "{{SUM USD}}" in text:
        notes.append(
            "Template uses legacy '{{SUM PL}}' / '{{SUM USD}}' tags instead of '{{SUM CURR}}' / '{{SUM EUR/USD}}' "
            "(handled automatically)."
        )
    if "{{TOTAL SUM PL}}" in text or "{{TOTAL SUM USD}}" in text:
        notes.append(
            "Template uses legacy '{{TOTAL SUM PL}}' / '{{TOTAL SUM USD}}' tags instead of "
            "'{{TOTAL SUM CURR}}' / '{{TOTAL SUM EUR/USD}}' (handled automatically)."
        )
    if "{{APPROVED}}" not in text and "Approved Budget" in text:
        notes.append(
            "Template 'My Approved Budget Limit' row is missing the '{{APPROVED}}' placeholder (handled automatically)."
        )
    return notes


def _cell_has_dropdown(cell: dict) -> bool:
    """Return True if a Google Docs tableCell contains a dropdown smart chip."""
    for content_item in cell.get("content") or []:
        if not isinstance(content_item, dict):
            continue
        para = content_item.get("paragraph") or {}
        for elem in para.get("elements") or []:
            if isinstance(elem, dict) and "dropdown" in elem:
                return True
    return False


def _cell_range(cell: dict) -> Optional[tuple[int, int]]:
    """Return (cell_start, cell_end) character indices for a Google Docs tableCell."""
    content = cell.get("content") or []
    if not content or not isinstance(content[0], dict):
        return None
    start_idx = content[0].get("startIndex")
    end_idx = cell.get("endIndex")
    if start_idx is None or end_idx is None:
        return None
    return int(start_idx), max(int(start_idx), int(end_idx) - 1)


def _populate_gdoc_expenses_table(
    docs_service,
    google_doc_id: str,
    initial_doc: dict,
    receipts_data: list[dict],
    total_curr_str: str,
    total_target_str: str,
    approved_budget: str,
) -> bool:
    """
    Populate the Google Docs Expenses Table with one dedicated row per receipt,
    plus the Total Spent row and Approved Budget Limit row.
    Preserves any existing template rows (and any dropdown smart chips in the Category column)
    and only inserts additional rows if receipts_data has more items than template placeholder rows.
    """
    table_start, rows = _find_expenses_table_in_gdoc(initial_doc)
    n_items = len(receipts_data or [])
    if table_start is None or len(rows) < 3 or n_items == 0:
        return False

    # Count how many item rows already exist in the template between Row 0 (header)
    # and the Total Spent / Approved Budget footer rows at the bottom.
    footer_start_idx = len(rows)
    for r_i in range(1, len(rows)):
        row_txt = _extract_text_from_gdoc({"body": {"content": [rows[r_i]]}})
        if "Total Spent" in row_txt or "Approved Budget" in row_txt or "Budget Limit" in row_txt:
            footer_start_idx = r_i
            break
    existing_item_rows = max(1, footer_start_idx - 1)
    extra_rows_needed = max(0, n_items - existing_item_rows)

    # 1. Insert only the extra rows needed below the last template item row, never deleting
    #    template rows so dropdown smart chips ('Choose ▾') in the Category column stay intact.
    if extra_rows_needed > 0:
        anchor_row_idx = existing_item_rows
        struct_requests = [
            {
                "insertTableRow": {
                    "tableCellLocation": {
                        "tableStartLocation": {"index": table_start},
                        "rowIndex": anchor_row_idx,
                        "columnIndex": 0,
                    },
                    "insertBelow": True,
                }
            }
            for _ in range(extra_rows_needed)
        ]
        docs_service.documents().batchUpdate(
            documentId=google_doc_id,
            body={"requests": struct_requests},
        ).execute()
        updated_doc = docs_service.documents().get(documentId=google_doc_id).execute()
    else:
        updated_doc = initial_doc

    # 2. Populate rows 1 .. n_items (preserving dropdown smart chips in the Category cell when present)
    _, updated_rows = _find_expenses_table_in_gdoc(updated_doc)
    if len(updated_rows) < n_items + 1:
        return False

    cell_edits: list[tuple[int, int, str]] = []

    for idx, item in enumerate(receipts_data):
        r_idx = idx + 1
        if r_idx >= len(updated_rows):
            break
        cells = updated_rows[r_idx].get("tableCells") or []
        row_values = [
            str(idx + 1),
            str(item.get("category") or ""),
            str(item.get("desc") or "Expense"),
            str(item.get("sum_curr") or ""),
            str(item.get("sum_target") or ""),
        ]
        for c_idx, val in enumerate(row_values):
            if c_idx >= len(cells):
                continue
            # If the Category cell (column 1) already has a Google Docs dropdown chip, keep the chip intact!
            if c_idx == 1 and _cell_has_dropdown(cells[c_idx]):
                continue
            rng = _cell_range(cells[c_idx])
            if rng is not None:
                cell_edits.append((rng[0], rng[1], val))

    # Locate Total Spent row and Approved Budget row at the bottom of the table
    total_row_idx = None
    budget_row_idx = None
    for r_idx in range(n_items + 1, len(updated_rows)):
        row_txt = _extract_text_from_gdoc({"body": {"content": [updated_rows[r_idx]]}})
        if "Total Spent" in row_txt and total_row_idx is None:
            total_row_idx = r_idx
        elif ("Approved Budget" in row_txt or "Budget Limit" in row_txt) and budget_row_idx is None:
            budget_row_idx = r_idx

    if total_row_idx is None and len(updated_rows) >= n_items + 2:
        total_row_idx = len(updated_rows) - 2
    if budget_row_idx is None and len(updated_rows) >= n_items + 3:
        budget_row_idx = len(updated_rows) - 1

    if total_row_idx is not None and total_row_idx < len(updated_rows):
        t_cells = updated_rows[total_row_idx].get("tableCells") or []
        if len(t_cells) >= 5:
            rng_curr = _cell_range(t_cells[3])
            rng_targ = _cell_range(t_cells[4])
            if rng_curr is not None:
                cell_edits.append((rng_curr[0], rng_curr[1], total_curr_str))
            if rng_targ is not None:
                cell_edits.append((rng_targ[0], rng_targ[1], total_target_str))

    if budget_row_idx is not None and budget_row_idx < len(updated_rows) and approved_budget:
        b_cells = updated_rows[budget_row_idx].get("tableCells") or []
        if len(b_cells) >= 5:
            rng_bud = _cell_range(b_cells[4])
            if rng_bud is not None:
                cell_edits.append((rng_bud[0], rng_bud[1], str(approved_budget)))

    # Sort descending by cell_start so index mutations never shift earlier cells
    cell_edits.sort(key=lambda x: x[0], reverse=True)
    cell_requests: list[dict] = []
    for c_start, c_end, new_text in cell_edits:
        if c_end > c_start:
            cell_requests.append({"deleteContentRange": {"range": {"startIndex": c_start, "endIndex": c_end}}})
        if new_text:
            cell_requests.append(
                {
                    "insertText": {
                        "location": {"index": c_start},
                        "text": new_text,
                    }
                }
            )

    if cell_requests:
        docs_service.documents().batchUpdate(
            documentId=google_doc_id,
            body={"requests": cell_requests},
        ).execute()
    return True


def _compute_proof_image_size_pt(
    img_bytes: bytes,
    max_w_pt: float = 210.0,
    max_h_pt: float = 300.0,
) -> tuple[float, float]:
    """
    Compute (width_pt, height_pt) preserving image aspect ratio for a 2-per-row layout.
    If the image is a stitched multi-page document (very tall aspect ratio where height > 1.85 * width),
    scales primarily by width (capped at 640 pt height so it always fits on a Google Docs page)
    so every stitched page remains legible instead of shrinking to a narrow strip.
    """
    try:
        from PIL import Image

        with Image.open(io.BytesIO(img_bytes)) as im:
            px_w, px_h = im.size
        if px_w > 0 and px_h > 0:
            aspect = px_h / px_w
            effective_max_h = max(max_h_pt, min(640.0, max_w_pt * aspect)) if aspect > 1.85 else max_h_pt
            scale = min(max_w_pt / px_w, effective_max_h / px_h)
            return round(px_w * scale, 1), round(px_h * scale, 1)
    except Exception:
        pass
    return 205.0, 270.0


# ---------------------------------------------------------------------------
# Helper: _fetch_pekao_pln_rate (shared by get_usd_pln_rate / get_eur_pln_rate)
# ---------------------------------------------------------------------------


def _fetch_pekao_pln_rate(currency: str) -> dict:
    """
    Fetches the current <currency>/PLN 'Bank kupuje' (bank buy) exchange rate
    from Pekao bank website (https://www.pekao.com.pl/kursy-walut.html).
    If the Pekao website is down or its layout changed, automatically falls
    back to the official NBP (National Bank of Poland) Exchange API (Table C).

    Args:
        currency: Three-letter ISO currency code, e.g. "USD" or "EUR".

    Returns:
        dict with keys: 'success', 'rate' (float), 'source', 'url', and
        'error' when the fetch failed.
    """
    currency = currency.upper().strip()
    pekao_url = "https://www.pekao.com.pl/kursy-walut.html"
    try:
        logger.debug(f"[DEBUG] Attempting to fetch {currency}/PLN rate from Pekao bank...")
        resp = requests.get(
            pekao_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        html = resp.text

        # Find the currency section, then extract the first cr-buy value
        idx = html.find(f'alt="{currency}"')
        if idx == -1:
            idx = html.find(f">{currency} / PLN")
        if idx == -1:
            raise ValueError(f"{currency} block not found on Pekao page")

        # Search for cr-buy rate after the currency section
        snippet = html[idx : idx + 1200]
        match = re.search(r"cr-buy[^>]*>.*?<span[^>]*>\s*([\d,\.]+)\s*</span>", snippet, re.S)
        if not match:
            raise ValueError("Could not parse rate from Pekao page snippet")

        rate_str = match.group(1).replace(",", ".")
        rate = float(rate_str)

        return {
            "success": True,
            "rate": rate,
            "source": f"Pekao Bank kupuje {currency}/PLN",
            "url": pekao_url,
        }

    except Exception as pekao_err:
        logger.warning(f"[WARNING] Pekao {currency} rate fetch failed: {pekao_err}. Falling back to NBP API...")

        # Fallback: Official NBP API (Table C contains buy/sell rates)
        currency_lower = currency.lower()
        nbp_url = f"http://api.nbp.pl/api/exchangerates/rates/c/{currency_lower}/today/?format=json"
        try:
            resp = requests.get(nbp_url, timeout=5)
            # If today's rates aren't published yet (e.g. weekend), get the last 5 rates
            if resp.status_code == 404:
                nbp_url = f"http://api.nbp.pl/api/exchangerates/rates/c/{currency_lower}/last/5/?format=json"
                resp = requests.get(nbp_url, timeout=5)

            resp.raise_for_status()
            data = resp.json()
            # Get the latest rate entry
            latest_rate = data["rates"][-1]
            rate = float(latest_rate["bid"])  # 'bid' is the buy rate

            return {
                "success": True,
                "rate": rate,
                "source": f"NBP (Narodowy Bank Polski) Bid rate ({latest_rate['effectiveDate']})",
                "url": nbp_url,
            }
        except Exception as nbp_err:
            return {
                "success": False,
                "error": f"Both Pekao and NBP rate fetches failed. Pekao: {pekao_err}. NBP: {nbp_err}",
            }


# ---------------------------------------------------------------------------
# Tool: get_usd_pln_rate
# ---------------------------------------------------------------------------


def get_usd_pln_rate() -> dict:
    """
    Fetches the current USD/PLN 'Bank kupuje' (bank buy) exchange rate
    from Pekao bank website (https://www.pekao.com.pl/kursy-walut.html).
    If Pekao website is down or layout changed, automatically falls back to
    the official NBP (National Bank of Poland) Exchange API.

    Returns:
        dict with keys: 'success', 'rate' (float), 'source', 'error'
    """
    return _fetch_pekao_pln_rate("USD")


# ---------------------------------------------------------------------------
# Helper: get_eur_pln_rate
# ---------------------------------------------------------------------------


def get_eur_pln_rate() -> dict:
    """
    Fetches the current EUR/PLN 'Bank kupuje' (bank buy) exchange rate
    from Pekao bank website (https://www.pekao.com.pl/kursy-walut.html).
    Falls back to NBP Exchange API (Table C).
    """
    return _fetch_pekao_pln_rate("EUR")


# ---------------------------------------------------------------------------
# Helper: get_nbp_rate / fetch_public_rate_to_pln / get_exchange_rate
# ---------------------------------------------------------------------------


def fetch_public_rate_to_pln(currency: str) -> dict:
    """
    Fetches the live public exchange rate for the given currency code to PLN.
    Queries NBP Table A, NBP Table B, ECB / Frankfurter public API, and
    Open Exchange Rates public API. Does NOT use hardcoded fallback rates.
    """
    code = normalize_currency_code(currency, default="PLN")
    if code == "PLN":
        return {"success": True, "rate": 1.0, "source": "Base Currency (PLN)", "url": "https://nbp.pl"}

    code_lower = code.lower()

    # 1. NBP API Table A and Table B (official average rates)
    for table in ("a", "b"):
        for suffix in ("today", "last/5"):
            nbp_url = f"https://api.nbp.pl/api/exchangerates/rates/{table}/{code_lower}/{suffix}/?format=json"
            try:
                resp = requests.get(nbp_url, timeout=5)
                if resp.status_code == 404:
                    continue
                resp.raise_for_status()
                data = resp.json()
                latest = data["rates"][-1]
                rate = float(latest["mid"])
                eff_date = latest.get("effectiveDate", "recent")
                return {
                    "success": True,
                    "rate": rate,
                    "source": f"NBP Table {table.upper()} ({eff_date})",
                    "url": nbp_url,
                }
            except Exception as err:
                logger.debug(f"[DEBUG] NBP Table {table.upper()} ({suffix}) lookup for {code} failed: {err}")

    # 2. ECB / Frankfurter public exchange rate API
    frankfurter_url = f"https://api.frankfurter.dev/v1/latest?from={code}&to=PLN"
    try:
        resp = requests.get(frankfurter_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            pln_rate = (data.get("rates") or {}).get("PLN")
            if pln_rate:
                eff_date = data.get("date", "recent")
                return {
                    "success": True,
                    "rate": float(pln_rate),
                    "source": f"ECB / Frankfurter Public API ({eff_date})",
                    "url": frankfurter_url,
                }
    except Exception as err:
        logger.debug(f"[DEBUG] Frankfurter public API lookup for {code} failed: {err}")

    # 3. Open Exchange Rates public API (covers 160+ world currencies)
    open_er_url = f"https://open.er-api.com/v6/latest/{code}"
    try:
        resp = requests.get(open_er_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            pln_rate = (data.get("rates") or {}).get("PLN")
            if pln_rate:
                return {
                    "success": True,
                    "rate": float(pln_rate),
                    "source": "Open Exchange Rates Public API",
                    "url": open_er_url,
                }
    except Exception as err:
        logger.debug(f"[DEBUG] Open ER public API lookup for {code} failed: {err}")

    err_msg = (
        f"Could not fetch a live exchange rate for {code}/PLN from public sources. "
        f"Please enter the exchange rate manually in a text message (for example: '1 {code} = ... PLN')."
    )
    logger.warning(f"[WARNING] {err_msg}")
    return {
        "success": False,
        "error": err_msg,
    }


def get_nbp_rate(currency: str) -> float:
    """
    Fetches the live public average exchange rate for the given currency code to PLN
    (NBP Table A/B, ECB Frankfurter, or Open Exchange Rates).
    Raises RuntimeError if no live rate can be fetched.
    """
    info = fetch_public_rate_to_pln(currency)
    if not info.get("success") or info.get("rate") is None:
        raise RuntimeError(info.get("error") or f"Could not fetch live exchange rate for {currency}")
    return float(info["rate"])


def get_exchange_rate(currency: str, target_currency: str = "PLN") -> dict:
    """
    Fetches the live public exchange rate from any currency (e.g. GBP, CHF, CZK, EUR, USD, UAH)
    into the target/community currency (defaults to PLN).
    Does NOT use fallback rates; if the live rate is unavailable, returns success=False with an error
    asking the user to provide the exchange rate in a text message.

    Args:
        currency: Source ISO currency code or symbol (e.g. "GBP", "EUR", "USD", "CHF", "CZK").
        target_currency: Target ISO currency code (e.g. "PLN" for GDG Krakow, or "USD", "EUR").

    Returns:
        dict with 'success', 'currency', 'target_currency', 'rate', 'rate_to_pln', 'source', 'url', or 'error'.
    """
    src = normalize_currency_code(currency, default="PLN")
    dst = normalize_currency_code(target_currency, default="PLN")
    if src == dst:
        return {
            "success": True,
            "currency": src,
            "target_currency": dst,
            "rate": 1.0,
            "rate_to_pln": 1.0 if src == "PLN" else None,
            "source": f"Same Currency ({src})",
            "url": "",
        }
    src_info = fetch_public_rate_to_pln(src)
    if not src_info.get("success") or src_info.get("rate") is None:
        return {
            "success": False,
            "currency": src,
            "target_currency": dst,
            "error": src_info.get("error")
            or f"Could not fetch live exchange rate for {src}. Please provide the rate in a text message.",
        }
    dst_info = fetch_public_rate_to_pln(dst)
    if not dst_info.get("success") or dst_info.get("rate") is None:
        return {
            "success": False,
            "currency": src,
            "target_currency": dst,
            "error": dst_info.get("error")
            or f"Could not fetch live exchange rate for {dst}. Please provide the rate in a text message.",
        }
    src_pln = float(src_info["rate"])
    dst_pln = float(dst_info["rate"]) or 1.0
    rate = round(src_pln / dst_pln, 6)
    return {
        "success": True,
        "currency": src,
        "target_currency": dst,
        "rate": rate,
        "rate_to_pln": round(src_pln, 4),
        "source": src_info.get("source", "Public Exchange Rate"),
        "url": src_info.get("url", "https://nbp.pl"),
    }


def normalise_receipts(
    receipts_data: list[dict] | None,
    target_currency: str,
    target_rate_to_pln: float,
    rate_to_pln: Callable[[str], float] = get_nbp_rate,
) -> list[dict]:
    """Normalise source and converted receipt amounts for document export."""
    target_currency = target_currency.upper().strip()
    normalised_receipts = []

    for item in receipts_data or []:
        category = item.get("category", "")
        desc = item.get("desc", "")
        image_path = item.get("image_path", "")
        original_amount = item.get("original_amount")
        currency = item.get("currency")

        if original_amount is not None and currency:
            try:
                amount_value = float(original_amount)
            except (ValueError, TypeError):
                amount_value = 0.0

            currency_code = str(currency).upper().strip()
            if currency_code == target_currency:
                target_amount = amount_value
            else:
                source_amount_pln = amount_value * rate_to_pln(currency_code)
                target_amount = source_amount_pln / target_rate_to_pln

            source_sum = f"{amount_value:.2f} {currency_code}"
            target_sum = f"{target_amount:.2f} {target_currency}"
        else:
            source_sum = item.get("sum_curr") or item.get("sum_pln") or "0.00 PLN"
            target_sum = item.get("sum_target") or item.get("sum_usd") or f"0.00 {target_currency}"

        normalised_receipts.append(
            {
                "category": category,
                "desc": desc,
                "sum_curr": source_sum,
                "sum_target": target_sum,
                "image_path": image_path,
            }
        )

    return normalised_receipts


def calculate_receipt_totals(
    normalised_receipts: list[dict] | None,
    target_currency: str,
) -> tuple[str, str]:
    """Calculate grouped source totals and the displayed target total."""
    sums_by_currency = defaultdict(float)
    target_total = 0.0

    for receipt in normalised_receipts or []:
        try:
            amount, currency = receipt.get("sum_curr", "0.00 PLN").split()
            sums_by_currency[currency] += float(amount)
        except (AttributeError, TypeError, ValueError):
            pass

        try:
            amount, _ = receipt.get("sum_target", f"0.00 {target_currency}").split()
            target_total += float(amount)
        except (AttributeError, TypeError, ValueError):
            pass

    source_total = ", ".join(f"{amount:.2f} {currency}" for currency, amount in sums_by_currency.items())
    return source_total, f"{target_total:.2f} {target_currency}"


# ---------------------------------------------------------------------------
# Tool: show_receipt_summary
# ---------------------------------------------------------------------------


def _build_rate_resolver(
    target_currency: str = "",
    exchange_rate: Optional[float] = None,
    custom_rates: Optional[dict] = None,
) -> Callable[[str], float]:
    """Build a rate_to_pln resolver that honours user-supplied rates before querying public APIs."""
    overrides: dict[str, float] = {"PLN": 1.0}
    if isinstance(custom_rates, dict):
        for raw_k, raw_v in custom_rates.items():
            code = normalize_currency_code(raw_k)
            if code:
                try:
                    val = float(raw_v)
                    if val > 0:
                        overrides[code] = val
                except (TypeError, ValueError):
                    pass
    if exchange_rate is not None and target_currency:
        t_code = normalize_currency_code(target_currency)
        if t_code and t_code != "PLN":
            try:
                val = float(exchange_rate)
                if val > 0:
                    overrides[t_code] = val
            except (TypeError, ValueError):
                pass

    def _resolve(code: str) -> float:
        norm = normalize_currency_code(code, default="PLN")
        if norm in overrides:
            return overrides[norm]
        return get_nbp_rate(norm)

    return _resolve


def show_receipt_summary(
    receipts: List[dict],
    target_currency: str = "",
    approved_budget: str = "",
    exchange_rate: Optional[float] = None,
    custom_rates: Optional[dict] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Show the user exactly what was recognised on the receipts, as a table card with totals.

    Call it ONCE after reading all receipts and BEFORE `export_summary_to_google_doc`. The card
    shows every receipt with its line items, the totals per category and currency, the
    conversion to the community currency and report currency, and the remaining budget.

    Args:
        receipts: One dict per receipt, values copied from the document (never invented):
            "merchant": shop / company name as printed, e.g. "Kaufland".
            "desc": 2-4 word English description, e.g. "Kaufland Grocery".
            "date": "YYYY-MM-DD" when readable, else "".
            "category": one of Transport, Hotel, Food & drinks, Swag, Prizes, Venue.
            "currency": ISO code, e.g. "PLN", "GBP", "EUR", "USD".
            "total": total amount paid as a number, e.g. 124.5.
            "tax": VAT / tax amount if printed, else omit.
            "payment_method": e.g. "card", "cash", if printed.
            "document_number": receipt / invoice number, if printed.
            "items": list of {"name": English item name, "quantity": number, "unit_price": number,
                "total": number} for every printed line item (omit unreadable values).
            "notes": list of short English remarks about unreadable or doubtful parts.
        target_currency: Report currency (e.g. "PLN", "USD", "EUR"); empty = the budget currency
            or the current community currency.
        approved_budget: Approved budget from the user's message, e.g. "500 EUR", or "".
        exchange_rate: Optional user-provided exchange rate to PLN for target_currency (e.g. 3.95).
        custom_rates: Optional dict of user-provided rates to PLN (e.g. {"GBP": 5.08, "USD": 3.95}).
    """
    state = getattr(getattr(tool_context, "session", None), "state", None) or {}
    community_currency = community_currency_from_state(state)
    resolver = _build_rate_resolver(target_currency, exchange_rate, custom_rates)
    grouped_receipts = group_and_sort_receipts(receipts)
    try:
        summary = build_receipt_summary(
            grouped_receipts,
            target_currency,
            approved_budget,
            rate_to_pln=resolver,
            community_currency=community_currency,
        )
    except Exception as exc:
        logger.exception("Receipt summary failed")
        return {"success": False, "error": f"Could not build the receipt summary: {exc}"}
    result = {
        "success": True,
        "receipts_count": len(summary["receipts"]),
        "grand_total": summary["grand_total"],
        "target_currency": summary["target_currency"],
        "community_currency": summary["community_currency"],
        "community_total": summary["community_total"],
        "warnings_count": summary["warnings_count"],
        "message": "The recognised receipts are shown to the user as a table card with a text copy.",
        "ui": ui_payloads.receipt_summary(summary),
    }
    if "Could not get exchange rates" in (summary.get("conversion_note") or ""):
        result["rate_error"] = (
            "Could not fetch live exchange rates from public sources. "
            "Please ask the user to enter their own exchange rate in a text message."
        )
    return result


# ---------------------------------------------------------------------------
# Tool: read_receipt_file
# ---------------------------------------------------------------------------


def read_receipt_file(file_path: str) -> dict:
    """
    Reads a receipt or invoice file (image or PDF) from the local filesystem
    and natively processes it using gemini-3.8-flash multimodal capability.

    Args:
        file_path: Absolute or relative path to the file (jpg, png, pdf, etc.)

    Returns:
        A dict with the extraction success status, file name, and extracted content text.
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        logger.debug(f"[DEBUG] File not found at resolved path: {path}")
        logger.debug(f"[DEBUG] Current working directory: {os.getcwd()}")

        # Self-healing search across the workspace and parent directories
        found_path = None
        search_dirs = [Path.cwd()]
        for parent in list(Path.cwd().parents)[:3]:
            search_dirs.append(parent)

        target_name = Path(file_path).name

        for sd in search_dirs:
            logger.debug(f"[DEBUG] Searching for '{target_name}' in {sd}...")
            try:
                matches = list(sd.rglob(target_name))
                if matches:
                    # Sort matches by modification time descending
                    matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
                    found_path = matches[0]
                    logger.debug(f"[DEBUG] Self-healing path resolution! Located at: {found_path}")
                    path = found_path
                    break
            except Exception as search_err:
                logger.debug(f"[DEBUG] Search error in {sd}: {search_err}")

        if not path.exists():
            # Gather nearby files up to depth 2 for diagnostic feedback
            cwd_files = []
            try:
                for root, dirs, files in os.walk(os.getcwd()):
                    depth = len(Path(root).relative_to(os.getcwd()).parts)
                    if depth > 2:
                        continue
                    for f in files:
                        if not f.startswith("."):
                            cwd_files.append(str(Path(root).name + "/" + f))
            except Exception as walk_err:
                cwd_files = [f"Error listing CWD: {walk_err}"]

            return {
                "success": False,
                "error": (
                    f"File not found at path: {file_path}.\n"
                    f"Attempted resolved path: {path}\n"
                    f"Current Working Directory (CWD): {os.getcwd()}\n"
                    f"Available nearby files (depth 2): {', '.join(cwd_files[:30])}"
                ),
            }

    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        ext = path.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")

    if path.suffix.lower() in [".doc", ".docx", ".docm", ".odt"]:
        return {
            "success": False,
            "error": "Word documents (.doc/.docx) are not supported. Please upload only receipt images or PDFs.",
        }

    supported = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
    if mime_type not in supported:
        return {"success": False, "error": f"Unsupported file type: {mime_type}. Supported: jpg, png, webp, gif, pdf"}

    try:
        raw_bytes = path.read_bytes()

        # Initialize a client for the workspace-selected Gemini backend.
        client = get_gemini_client()

        # Perform native multimodal OCR and data extraction using gemini-3.8-flash
        prompt = (
            "You are a professional OCR assistant. Recognize and extract all text and structured data "
            "from this document (receipt/invoice). List all itemized positions, quantities, unit prices, "
            "taxes (VAT/GST), total sums, document currency, dates, and issuer details. "
            "Perform this extraction with maximum accuracy and detail."
        )

        model = model_for("receipt_ocr", legacy_env="RECEIPT_SCANNER_MODEL")
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=raw_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ],
        )

        extracted_text = response.text or ""
        report_markers = [
            "1. Personal Details",
            "2. List of Expenses",
            "BWAI_report",
            "Expense_report_",
            "List of Expenses",
        ]
        if any(marker in extracted_text for marker in report_markers):
            return {
                "success": False,
                "error": "This document appears to be a previously generated expense report (contains '1. Personal Details'), not a raw receipt or invoice. Processing aborted.",
            }

        return {"success": True, "file_name": path.name, "content_text": extracted_text}
    except Exception as e:
        return {"success": False, "error": f"Failed to natively process document: {str(e)}"}


# ---------------------------------------------------------------------------
# Tool: export_summary_to_google_doc
# ---------------------------------------------------------------------------


def export_summary_to_google_doc(
    title: str,
    folder_id: Optional[str] = None,
    template_id: Optional[str] = None,
    exchange_rate: Optional[float] = None,
    receipts_data: Optional[List[dict]] = None,
    target_currency: str = "USD",
    approved_budget: str = "",
    custom_rates: Optional[dict] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """
    Generates a professional DOCX expense reimbursement report, embeds receipts,
    and uploads the finalized document to Google Cloud Storage.

    Args:
        title: Title of the expense report document.
        folder_id: Optional Drive Folder ID (maintained for signature backwards compatibility).
        template_id: Optional template ID (maintained for signature backwards compatibility).
        exchange_rate: Optional user-provided exchange rate to PLN for target_currency.
        receipts_data: Optional structured list of dicts with keys: category, desc, sum_curr, sum_target, image_path.
        target_currency: Target approved currency for the report ("USD", "EUR", "PLN", "GBP", etc.).
        approved_budget: Optional approved budget annotation.
        custom_rates: Optional dict of user-provided rates to PLN (e.g. {"GBP": 5.08, "USD": 3.95}).
        tool_context: ADK tool context for accessing session event attachments.

    Returns:
        dict: Success status, file name, download link, and summary details.
    """
    try:
        agent_dir = Path(__file__).resolve().parent

        state = getattr(getattr(tool_context, "session", None), "state", None) or {}
        community_currency = community_currency_from_state(state)
        target_currency = normalize_currency_code(target_currency, default=community_currency or "USD")

        # Check if conversion is required (if any receipt is in a different currency)
        conversion_required = False
        local_curr_code = community_currency or "PLN"
        if receipts_data:
            for item in receipts_data:
                item_curr = normalize_currency_code(item.get("currency"), default=local_curr_code)
                if item_curr != target_currency:
                    conversion_required = True
                    break

        rate_resolver = _build_rate_resolver(target_currency, exchange_rate, custom_rates)
        rate_val = exchange_rate
        if not rate_val and isinstance(custom_rates, dict):
            for raw_k, raw_v in custom_rates.items():
                if normalize_currency_code(raw_k) == target_currency:
                    try:
                        rate_val = float(raw_v)
                    except (TypeError, ValueError):
                        pass

        rate_source_name = "Pekao Bank / NBP"
        rate_url = (
            "https://www.pekao.com.pl/kursy-walut.html"
            if target_currency in ("USD", "EUR")
            else ("https://nbp.pl" if conversion_required else "")
        )
        if not rate_val:
            if conversion_required:
                if target_currency == "USD":
                    rate_info = get_usd_pln_rate()
                    if rate_info.get("success") and rate_info.get("rate"):
                        rate_val = float(rate_info["rate"])
                        rate_source_name = rate_info["source"]
                        rate_url = rate_info.get("url", "https://www.pekao.com.pl/kursy-walut.html")
                    else:
                        return {
                            "success": False,
                            "error": "EXCHANGE_RATE_UNAVAILABLE",
                            "message": (
                                f"Could not fetch live exchange rate for {target_currency}/PLN. "
                                f"Please enter the exchange rate manually in a text message (for example: '1 {target_currency} = 3.95 PLN')."
                            ),
                        }
                elif target_currency == "EUR":
                    rate_info = get_eur_pln_rate()
                    if rate_info.get("success") and rate_info.get("rate"):
                        rate_val = float(rate_info["rate"])
                        rate_source_name = rate_info["source"]
                        rate_url = rate_info.get("url", "https://www.pekao.com.pl/kursy-walut.html")
                    else:
                        return {
                            "success": False,
                            "error": "EXCHANGE_RATE_UNAVAILABLE",
                            "message": (
                                f"Could not fetch live exchange rate for {target_currency}/PLN. "
                                f"Please enter the exchange rate manually in a text message (for example: '1 {target_currency} = 4.30 PLN')."
                            ),
                        }
                elif target_currency == "PLN":
                    rate_val = 1.0
                    rate_source_name = "N/A"
                    rate_url = ""
                else:
                    pub_info = fetch_public_rate_to_pln(target_currency)
                    if pub_info.get("success") and pub_info.get("rate"):
                        rate_val = float(pub_info["rate"])
                        rate_source_name = pub_info.get("source", "Public Exchange Rate")
                        rate_url = pub_info.get("url", "")
                    else:
                        return {
                            "success": False,
                            "error": "EXCHANGE_RATE_UNAVAILABLE",
                            "message": pub_info.get("error")
                            or (
                                f"Could not fetch live exchange rate for {target_currency}/PLN. "
                                f"Please enter the exchange rate manually in a text message (for example: '1 {target_currency} = ... PLN')."
                            ),
                        }
            else:
                rate_val = 1.0
                rate_source_name = "N/A"
                rate_url = ""

        # Group related receipts first so the table and proof images share the exact same order
        receipts_data = group_and_sort_receipts(receipts_data or [])

        # Normalize and calculate amounts
        normalized_receipts = []
        if receipts_data:
            for item in receipts_data:
                category = item.get("category", "")
                desc = item.get("desc", "")
                image_path = item.get("image_path", "")

                original_amount = item.get("original_amount")
                currency = item.get("currency")

                if original_amount is not None and currency:
                    try:
                        amount_val = float(original_amount)
                    except (ValueError, TypeError):
                        amount_val = 0.0

                    curr_code = normalize_currency_code(currency, default=local_curr_code)

                    # Convert original currency to target currency
                    if curr_code == target_currency:
                        amount_in_target = amount_val
                    else:
                        try:
                            pln_rate = rate_resolver(curr_code)
                        except RuntimeError as rate_err:
                            return {
                                "success": False,
                                "error": "EXCHANGE_RATE_UNAVAILABLE",
                                "message": str(rate_err),
                            }
                        amount_in_pln = amount_val * pln_rate
                        amount_in_target = amount_in_pln / (rate_val or 1.0)

                    sum_curr_str = f"{amount_val:.2f} {curr_code}"
                    sum_target_str = f"{amount_in_target:.2f} {target_currency}"
                else:
                    sum_curr_str = item.get("sum_curr") or item.get("sum_pln") or f"0.00 {local_curr_code}"
                    sum_target_str = item.get("sum_target") or item.get("sum_usd") or f"0.00 {target_currency}"

                normalized_item = {
                    "category": category,
                    "desc": desc,
                    "sum_curr": sum_curr_str,
                    "sum_target": sum_target_str,
                    "image_path": image_path,
                }
                if "_orig_idx" in item:
                    normalized_item["_orig_idx"] = item["_orig_idx"]
                if "attachment_index" in item:
                    normalized_item["attachment_index"] = item["attachment_index"]
                normalized_receipts.append(normalized_item)

        receipts_data = normalized_receipts

        # Gather session attachments and text blobs
        session_images = []
        session_text_blobs = []
        if tool_context and hasattr(tool_context, "session") and tool_context.session:
            events = getattr(tool_context.session, "events", []) or []
            for event in events:
                if getattr(event, "content", None) and getattr(event.content, "parts", None):
                    for part in event.content.parts:
                        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                            session_images.append(part.inline_data.data)
                        txt = getattr(part, "text", "") or ""
                        if txt:
                            session_text_blobs.append(txt)
        combined_session_text = "\n".join(session_text_blobs)

        # Resolve target Google Drive folder (required)
        target_folder = folder_id
        if not target_folder and tool_context and hasattr(tool_context, "session") and tool_context.session:
            state = getattr(tool_context.session, "state", {}) or {}
            target_folder = state.get("google_drive_folder_id") or state.get("drive_folder_id")
        if not target_folder and combined_session_text:
            m_folder = re.search(r"\[Target Drive Folder:\s*([^\]]+)\]", combined_session_text, re.IGNORECASE)
            if m_folder:
                target_folder = m_folder.group(1).strip()
            if not target_folder:
                m_url = re.search(
                    r"https://drive\.google\.com/drive/(?:u/\d+/)?folders/([a-zA-Z0-9_-]+)", combined_session_text
                )
                if m_url:
                    target_folder = m_url.group(1)
        target_folder = extract_google_drive_folder_id(target_folder)

        if not target_folder:
            return {
                "success": False,
                "error": "MISSING_GOOGLE_DRIVE_FOLDER",
                "message": "Google Drive target folder is not configured. Please specify a Google Drive folder in Settings before scanning receipts.",
            }

        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_base_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", title).strip("_") or "Expense_Report"
        if timestamp_str not in safe_base_title:
            doc_title = f"{safe_base_title}_{timestamp_str}"
        else:
            doc_title = safe_base_title

        # Attempt native Google Docs API creation first
        google_doc_url = None
        google_doc_id = None
        try:
            credentials = None
            if tool_context and hasattr(tool_context, "session") and tool_context.session:
                state = getattr(tool_context.session, "state", {}) or {}
                user_token = (
                    state.get("google_drive_access_token")
                    or state.get("google_drive_token")
                    or state.get("google_oauth_token")
                )
            else:
                user_token = None

            if not user_token and combined_session_text:
                m_tok = re.search(r"\[Google Drive Token:\s*([^\]]+)\]", combined_session_text, re.IGNORECASE)
                if m_tok:
                    user_token = m_tok.group(1).strip()

            if user_token:
                try:
                    from google.oauth2.credentials import Credentials

                    credentials = Credentials(token=user_token)
                    logger.info("🔑 [Google Drive Auth] Successfully loaded user's personal Google OAuth access token!")
                except Exception as oauth_err:
                    logger.warning(f"⚠️ [Google Drive Auth] Failed to initialize user OAuth credentials: {oauth_err}")

            if not credentials:
                credentials = get_google_credentials()

            if credentials:
                docs_service = build("docs", "v1", credentials=credentials)
                drive_service = build("drive", "v3", credentials=credentials)
                active_template = template_id
                if not active_template and tool_context and hasattr(tool_context, "session") and tool_context.session:
                    state = getattr(tool_context.session, "state", {}) or {}
                    active_template = state.get("google_docs_template_id") or state.get("template_id")
                if not active_template and combined_session_text:
                    m_tmpl = re.search(r"\[Target Template:\s*([^\]]+)\]", combined_session_text, re.IGNORECASE)
                    if m_tmpl:
                        active_template = m_tmpl.group(1).strip()
                    if not active_template:
                        m_doc_url = re.search(
                            r"https://docs\.google\.com/document/d/([a-zA-Z0-9_-]+)", combined_session_text
                        )
                        if m_doc_url:
                            active_template = m_doc_url.group(1)
                if not active_template:
                    active_template = os.getenv("GOOGLE_DOCS_TEMPLATE_ID")
                if not active_template:
                    gdoc_path = agent_dir / "assets" / "Expense_report_template.gdoc"
                    if gdoc_path.exists():
                        with open(gdoc_path, "r") as f:
                            active_template = json.load(f).get("doc_id")
                if not active_template:
                    active_template = "1nkT3N6ovmmBJYDK9S9oRRaOZ6sCQkAwve58y7sS2eOw"

                active_template = extract_google_doc_id(active_template) or active_template
                logger.info(
                    f"📁 [Google Docs Export] Target Drive Folder: {target_folder}, Template ID: {active_template}"
                )

                copy_body = {"name": doc_title}
                if target_folder:
                    copy_body["parents"] = [target_folder]

                new_file = (
                    drive_service.files().copy(fileId=active_template, body=copy_body, supportsAllDrives=True).execute()
                )
                google_doc_id = new_file.get("id")
                google_doc_url = f"https://docs.google.com/document/d/{google_doc_id}/edit"

                # Validate required placeholders in the copied document
                initial_doc: dict = {}
                template_warnings: list[str] = []
                try:
                    initial_doc = docs_service.documents().get(documentId=google_doc_id).execute()
                    initial_text = _extract_text_from_gdoc(initial_doc)
                    template_warnings = _diagnose_gdoc_template(initial_doc)
                    missing_tags = [tag for tag in REQUIRED_TEMPLATE_TAGS if tag not in initial_text]
                    if missing_tags:
                        logger.warning(
                            f"⚠️ [Template Validation Warning] Template {active_template} is missing required tags: {', '.join(missing_tags)}"
                        )
                    else:
                        logger.info(
                            f"✅ [Template Validation] All required template tags verified in template {active_template}"
                        )
                except Exception as val_err:
                    logger.warning(f"Notice: Template tag pre-check: {val_err}")

                try:
                    drive_service.permissions().create(
                        fileId=google_doc_id,
                        body={"type": "anyone", "role": "writer"},
                        fields="id",
                        supportsAllDrives=True,
                    ).execute()
                except Exception as perm_err:
                    logger.warning(f"Notice: Public link permission creation: {perm_err}")

                today_str = datetime.date.today().strftime("%d.%m.%Y")
                total_curr_str, total_target_str = calculate_receipt_totals(receipts_data, target_currency)

                # Reorder proof images to match the grouped table rows 1-to-1, then auto-orient and compress
                raw_proof_candidates = reorder_proofs_for_grouped_receipts(receipts_data, session_images)
                compressed_proofs = deduplicate_and_compress_proofs(raw_proof_candidates)

                uploaded_proofs: list[tuple[str, float, float]] = []
                for idx, img_b in enumerate(compressed_proofs):
                    try:
                        if img_b and len(img_b) > 10 and drive_service and MediaIoBaseUpload:
                            img_w_pt, img_h_pt = _compute_proof_image_size_pt(img_b, max_w_pt=210.0, max_h_pt=300.0)
                            media_img = MediaIoBaseUpload(io.BytesIO(img_b), mimetype="image/jpeg", resumable=True)
                            img_drive_body = {"name": f"Receipt_{idx + 1}.jpg"}
                            if target_folder:
                                img_drive_body["parents"] = [target_folder]
                            uploaded_img = (
                                drive_service.files()
                                .create(
                                    body=img_drive_body,
                                    media_body=media_img,
                                    fields="id, webViewLink",
                                    supportsAllDrives=True,
                                )
                                .execute()
                            )
                            proof_id = uploaded_img.get("id")
                            if proof_id:
                                try:
                                    drive_service.permissions().create(
                                        fileId=proof_id,
                                        body={"type": "anyone", "role": "reader"},
                                        supportsAllDrives=True,
                                    ).execute()
                                except Exception as perm_err:
                                    logger.warning(
                                        f"⚠️ [Google Drive Proof Upload Notice] Could not make proof image "
                                        f"'{proof_id}' publicly viewable: {perm_err}"
                                    )
                                uploaded_proofs.append((proof_id, img_w_pt, img_h_pt))
                    except Exception as upload_err:
                        logger.warning(f"⚠️ [Google Drive Proof Upload Notice] {upload_err}")

                # Populate the Expenses Table row-by-row (one row per receipt + Total Spent + Approved Budget)
                table_populated = False
                if receipts_data and initial_doc:
                    try:
                        table_populated = _populate_gdoc_expenses_table(
                            docs_service=docs_service,
                            google_doc_id=google_doc_id,
                            initial_doc=initial_doc,
                            receipts_data=receipts_data,
                            total_curr_str=total_curr_str,
                            total_target_str=total_target_str,
                            approved_budget=approved_budget or "",
                        )
                    except Exception as tbl_err:
                        logger.warning(f"⚠️ [Google Docs Table Population Notice] Falling back to text tags: {tbl_err}")

                global_replaces = [
                    ("{{TITLE}}", title),
                    ("{{Current date}}", today_str),
                    ("\x0b{{EUR/USD}}", f"\x0b1 {target_currency}"),
                    ("{{EUR/USD}}", target_currency),
                    ("{{Current exchange rate}}", f"{rate_val:.4f}"),
                    ("{{Local Currency Code}}", local_curr_code),
                    ("{{TOTAL SUM CURR}}", total_curr_str),
                    ("{{TOTAL SUM PL}}", total_curr_str),
                    ("{{TOTAL SUM PLN}}", total_curr_str),
                    ("{{TOTAL SUM EUR/USD}}", total_target_str),
                    ("{{TOTAL SUM USD}}", total_target_str),
                    ("{{TOTAL SUM EUR}}", total_target_str),
                    ("{{APPROVED}}", approved_budget or ""),
                    ("{{Bank link}}", rate_url or (f"({rate_source_name})" if rate_source_name != "N/A" else "")),
                    ("{{PROOFS}}", ""),
                ]
                if receipts_data and not table_populated:
                    sum_curr_joined = "\n".join(str(r.get("sum_curr", "")) for r in receipts_data)
                    sum_target_joined = "\n".join(str(r.get("sum_target", "")) for r in receipts_data)
                    global_replaces.extend(
                        [
                            ("{{Category}}", "\n".join(str(r.get("category", "")) for r in receipts_data)),
                            ("{{Desc}}", "\n".join(str(r.get("desc", "Expense")) for r in receipts_data)),
                            ("{{SUM CURR}}", sum_curr_joined),
                            ("{{SUM PL}}", sum_curr_joined),
                            ("{{SUM PLN}}", sum_curr_joined),
                            ("{{SUM EUR/USD}}", sum_target_joined),
                            ("{{SUM USD}}", sum_target_joined),
                            ("{{SUM EUR}}", sum_target_joined),
                        ]
                    )

                gdoc_requests = [
                    {"replaceAllText": {"containsText": {"text": k, "matchCase": False}, "replaceText": v}}
                    for k, v in global_replaces
                ]
                docs_service.documents().batchUpdate(
                    documentId=google_doc_id, body={"requests": gdoc_requests}
                ).execute()
                logger.info(f"✅ [Google Docs API] Successfully populated template text: {google_doc_url}")

                # Embed proof images strictly 2 per row, preserving each image's aspect ratio
                for idx, (proof_id, img_w_pt, img_h_pt) in enumerate(uploaded_proofs):
                    separator = "    " if (idx % 2 == 0 and idx + 1 < len(uploaded_proofs)) else "\n"
                    try:
                        image_uri = f"https://lh3.googleusercontent.com/d/{proof_id}"
                        image_reqs = [
                            {
                                "insertInlineImage": {
                                    "endOfSegmentLocation": {},
                                    "uri": image_uri,
                                    "objectSize": {
                                        "width": {"magnitude": img_w_pt, "unit": "PT"},
                                        "height": {"magnitude": img_h_pt, "unit": "PT"},
                                    },
                                }
                            },
                            {
                                "insertText": {
                                    "endOfSegmentLocation": {},
                                    "text": separator,
                                }
                            },
                        ]
                        docs_service.documents().batchUpdate(
                            documentId=google_doc_id, body={"requests": image_reqs}
                        ).execute()
                        logger.info(f"✅ [Google Docs API] Embedded inline proof image #{idx + 1} (2-per-row).")
                    except Exception as embed_err:
                        logger.warning(f"⚠️ [Google Docs Image Embed Notice] {embed_err}")
                        try:
                            fallback_uri = f"https://drive.google.com/uc?export=download&id={proof_id}"
                            docs_service.documents().batchUpdate(
                                documentId=google_doc_id,
                                body={
                                    "requests": [
                                        {
                                            "insertInlineImage": {
                                                "endOfSegmentLocation": {},
                                                "uri": fallback_uri,
                                                "objectSize": {
                                                    "width": {"magnitude": img_w_pt, "unit": "PT"},
                                                    "height": {"magnitude": img_h_pt, "unit": "PT"},
                                                },
                                            }
                                        },
                                        {
                                            "insertText": {
                                                "endOfSegmentLocation": {},
                                                "text": separator,
                                            }
                                        },
                                    ]
                                },
                            ).execute()
                            logger.info(
                                f"✅ [Google Docs API] Embedded inline proof image #{idx + 1} using fallback URI."
                            )
                        except Exception as fb_err:
                            logger.warning(f"⚠️ [Google Docs Image Fallback Notice] {fb_err}")
        except Exception as gdoc_err:
            logger.warning(f"⚠️ [Google Docs API Error] {gdoc_err}")
            return {
                "success": False,
                "error": "GOOGLE_DOCS_ACCESS_ERROR",
                "message": (
                    f"Google Docs generation failed: {gdoc_err}. "
                    "Please ensure that BOTH your target Google Drive folder AND the Google Docs template "
                    "have been shared with Editor permissions with the Service Account email found in Settings."
                ),
            }

        if not google_doc_url:
            return {
                "success": False,
                "error": "GOOGLE_DOCS_NOT_CREATED",
                "message": (
                    "Could not generate Google Doc report. Please make sure your target Google Drive folder "
                    "and Google Docs template are shared with Editor permissions."
                ),
            }

        return {
            "success": True,
            "document_id": google_doc_id,
            "document_url": google_doc_url,
            "google_doc_url": google_doc_url,
            "target_currency": target_currency,
            "exchange_rate": rate_val,
            "receipts_count": len(receipts_data or []),
            "template_warnings": template_warnings,
            "message": f"Successfully generated Expense Reimbursement report in Google Docs: [{title}]({google_doc_url})",
            "ui": ui_payloads.document(
                google_doc_url,
                title=title,
                kind="expense_report",
                file_type="Google Docs",
                filename=title,
            ),
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to generate expense report: {str(e)}"}


# Alias export_summary_to_docx for direct semantic calling
export_summary_to_docx = export_summary_to_google_doc
