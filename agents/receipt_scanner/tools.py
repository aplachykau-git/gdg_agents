import base64
import datetime
import io
import json
import mimetypes
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests
from google import genai
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

from agents.common.storage import upload_bytes_to_storage
from agents.gemini_config import get_gemini_client

from .docx_generator import generate_expense_report_docx
from .utils import _auto_rotate_image, _pdf_to_png_screenshot


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
    pekao_url = "https://www.pekao.com.pl/kursy-walut.html"
    try:
        print("[DEBUG] Attempting to fetch USD/PLN rate from Pekao bank...")
        resp = requests.get(
            pekao_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        html = resp.text

        # Find USD section, then extract the first cr-buy value
        usd_idx = html.find('alt="USD"')
        if usd_idx == -1:
            usd_idx = html.find(">USD / PLN")
        if usd_idx == -1:
            raise ValueError("USD block not found on Pekao page")

        # Search for cr-buy rate after the USD section
        snippet = html[usd_idx : usd_idx + 1200]
        match = re.search(r"cr-buy[^>]*>.*?<span[^>]*>\s*([\d,\.]+)\s*</span>", snippet, re.S)
        if not match:
            raise ValueError("Could not parse rate from Pekao page snippet")

        rate_str = match.group(1).replace(",", ".")
        rate = float(rate_str)

        return {
            "success": True,
            "rate": rate,
            "source": "Pekao Bank kupuje USD/PLN",
            "url": pekao_url,
        }

    except Exception as pekao_err:
        print(f"[WARNING] Pekao rate fetch failed: {pekao_err}. Falling back to NBP API...")

        # Fallback: Official NBP API (Table C contains buy/sell rates)
        nbp_url = "http://api.nbp.pl/api/exchangerates/rates/c/usd/today/?format=json"
        try:
            resp = requests.get(nbp_url, timeout=5)
            # If today's rates aren't published yet (e.g. weekend), get the last 5 rates
            if resp.status_code == 404:
                nbp_url = "http://api.nbp.pl/api/exchangerates/rates/c/usd/last/5/?format=json"
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
# Helper: get_eur_pln_rate
# ---------------------------------------------------------------------------


def get_eur_pln_rate() -> dict:
    """
    Fetches the current EUR/PLN 'Bank kupuje' (bank buy) exchange rate
    from Pekao bank website (https://www.pekao.com.pl/kursy-walut.html).
    Falls back to NBP Exchange API (Table C).
    """
    pekao_url = "https://www.pekao.com.pl/kursy-walut.html"
    try:
        print("[DEBUG] Attempting to fetch EUR/PLN rate from Pekao bank...")
        resp = requests.get(
            pekao_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        resp.raise_for_status()
        html = resp.text

        # Find EUR section, then extract the first cr-buy value
        eur_idx = html.find('alt="EUR"')
        if eur_idx == -1:
            eur_idx = html.find(">EUR / PLN")
        if eur_idx == -1:
            raise ValueError("EUR block not found on Pekao page")

        snippet = html[eur_idx : eur_idx + 1200]
        match = re.search(r"cr-buy[^>]*>.*?<span[^>]*>\s*([\d,\.]+)\s*</span>", snippet, re.S)
        if not match:
            raise ValueError("Could not parse rate from Pekao page snippet")

        rate_str = match.group(1).replace(",", ".")
        rate = float(rate_str)

        return {
            "success": True,
            "rate": rate,
            "source": "Pekao Bank kupuje EUR/PLN",
            "url": pekao_url,
        }

    except Exception as pekao_err:
        print(f"[WARNING] Pekao EUR rate fetch failed: {pekao_err}. Falling back to NBP API...")

        nbp_url = "http://api.nbp.pl/api/exchangerates/rates/c/eur/today/?format=json"
        try:
            resp = requests.get(nbp_url, timeout=5)
            if resp.status_code == 404:
                nbp_url = "http://api.nbp.pl/api/exchangerates/rates/c/eur/last/5/?format=json"
                resp = requests.get(nbp_url, timeout=5)

            resp.raise_for_status()
            data = resp.json()
            latest_rate = data["rates"][-1]
            rate = float(latest_rate["bid"])

            return {
                "success": True,
                "rate": rate,
                "source": f"NBP Bid rate ({latest_rate['effectiveDate']})",
                "url": nbp_url,
            }
        except Exception as nbp_err:
            return {
                "success": False,
                "error": f"Both Pekao and NBP EUR rate fetches failed. Pekao: {pekao_err}. NBP: {nbp_err}",
            }


# ---------------------------------------------------------------------------
# Helper: get_nbp_rate
# ---------------------------------------------------------------------------


def get_nbp_rate(currency: str) -> float:
    """
    Fetches the average exchange rate for the given currency code to PLN
    from the Narodowy Bank Polski (NBP) API (Table A).
    Returns 1.0 if the currency is PLN.
    """
    currency = currency.upper().strip()
    if currency == "PLN":
        return 1.0

    # NBP API for A table (middle exchange rates)
    nbp_url = f"http://api.nbp.pl/api/exchangerates/rates/a/{currency.lower()}/today/?format=json"
    try:
        resp = requests.get(nbp_url, timeout=5)
        # If today's rates are not published (e.g. weekend or early morning)
        if resp.status_code == 404:
            nbp_url = f"http://api.nbp.pl/api/exchangerates/rates/a/{currency.lower()}/last/5/?format=json"
            resp = requests.get(nbp_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return float(data["rates"][-1]["mid"])
    except Exception as err:
        print(
            f"[WARNING] Failed to fetch {currency}/PLN rate from NBP Table A: {err}. Falling back to default/cached values."
        )
        # Common defaults in case NBP is entirely offline (rough estimates)
        defaults = {
            "EUR": 4.30,
            "USD": 4.00,
            "GBP": 5.10,
        }
        return defaults.get(currency, 1.0)


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
# Tool: read_receipt_file
# ---------------------------------------------------------------------------


def read_receipt_file(file_path: str) -> dict:
    """
    Reads a receipt or invoice file (image or PDF) from the local filesystem
    and natively processes it using gemini-3.7-flash multimodal capability.

    Args:
        file_path: Absolute or relative path to the file (jpg, png, pdf, etc.)

    Returns:
        A dict with the extraction success status, file name, and extracted content text.
    """
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        print(f"[DEBUG] File not found at resolved path: {path}")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")

        # Self-healing search across the workspace and parent directories
        found_path = None
        search_dirs = [Path.cwd()]
        for parent in list(Path.cwd().parents)[:3]:
            search_dirs.append(parent)

        target_name = Path(file_path).name

        for sd in search_dirs:
            print(f"[DEBUG] Searching for '{target_name}' in {sd}...")
            try:
                matches = list(sd.rglob(target_name))
                if matches:
                    # Sort matches by modification time descending
                    matches.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
                    found_path = matches[0]
                    print(f"[DEBUG] Self-healing path resolution! Located at: {found_path}")
                    path = found_path
                    break
            except Exception as search_err:
                print(f"[DEBUG] Search error in {sd}: {search_err}")

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

        # Perform native multimodal OCR and data extraction using gemini-3.7-flash
        prompt = (
            "You are a professional OCR assistant. Recognize and extract all text and structured data "
            "from this document (receipt/invoice). List all itemized positions, quantities, unit prices, "
            "taxes (VAT/GST), total sums, document currency, dates, and issuer details. "
            "Perform this extraction with maximum accuracy and detail."
        )

        model = os.getenv("RECEIPT_SCANNER_MODEL", "gemini-3.7-flash")
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
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """
    Generates a professional DOCX expense reimbursement report, embeds receipts,
    and uploads the finalized document to Google Cloud Storage.

    Args:
        title: Title of the expense report document.
        folder_id: Optional Drive Folder ID (maintained for signature backwards compatibility).
        template_id: Optional template ID (maintained for signature backwards compatibility).
        exchange_rate: Optional banking exchange rate.
        receipts_data: Optional structured list of dicts with keys: category, desc, sum_curr, sum_target, image_path.
        target_currency: Target approved currency for the report ("USD", "EUR", "PLN").
        approved_budget: Optional approved budget annotation.
        tool_context: ADK tool context for accessing session event attachments.

    Returns:
        dict: Success status, file name, download link, and summary details.
    """
    try:
        agent_dir = Path(__file__).resolve().parent

        target_currency = (target_currency or "USD").upper().strip()

        # Check if conversion is required (if any receipt is in a different currency)
        conversion_required = False
        local_curr_code = ""
        if receipts_data:
            for item in receipts_data:
                item_curr = str(item.get("currency", "USD")).upper().strip()
                if item_curr != target_currency:
                    conversion_required = True
                    local_curr_code = item_curr
                    break
        if not local_curr_code:
            local_curr_code = "PLN"

        rate_val = exchange_rate
        rate_source_name = "Manual / Provided"
        rate_url = ""
        if not rate_val:
            if conversion_required:
                if target_currency == "USD":
                    rate_info = get_usd_pln_rate()
                    if rate_info.get("success"):
                        rate_val = rate_info["rate"]
                        rate_source_name = rate_info["source"]
                        rate_url = rate_info.get("url", "https://www.pekao.com.pl/kursy-walut.html")
                    else:
                        rate_val = 4.00
                        rate_source_name = "Fallback (4.00)"
                        rate_url = "https://www.pekao.com.pl/kursy-walut.html"
                elif target_currency == "EUR":
                    rate_info = get_eur_pln_rate()
                    if rate_info.get("success"):
                        rate_val = rate_info["rate"]
                        rate_source_name = rate_info["source"]
                        rate_url = rate_info.get("url", "https://www.pekao.com.pl/kursy-walut.html")
                    else:
                        rate_val = 4.30
                        rate_source_name = "Fallback (4.30)"
                        rate_url = "https://www.pekao.com.pl/kursy-walut.html"
                elif target_currency == "PLN":
                    rate_val = 1.0
                    rate_source_name = "N/A"
                    rate_url = ""
                else:
                    rate_val = get_nbp_rate(target_currency)
                    rate_source_name = "NBP Table A"
                    rate_url = f"http://api.nbp.pl/api/exchangerates/rates/a/{target_currency.lower()}/"
            else:
                rate_val = 1.0
                rate_source_name = "N/A"
                rate_url = ""

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

                    curr_code = str(currency).upper().strip()

                    # Convert original currency to target currency
                    if curr_code == target_currency:
                        amount_in_target = amount_val
                    else:
                        pln_rate = get_nbp_rate(curr_code)
                        amount_in_pln = amount_val * pln_rate
                        amount_in_target = amount_in_pln / (rate_val or 1.0)

                    sum_curr_str = f"{amount_val:.2f} {curr_code}"
                    sum_target_str = f"{amount_in_target:.2f} {target_currency}"
                else:
                    sum_curr_str = item.get("sum_curr") or item.get("sum_pln") or "0.00 PLN"
                    sum_target_str = item.get("sum_target") or item.get("sum_usd") or f"0.00 {target_currency}"

                normalized_receipts.append(
                    {
                        "category": category,
                        "desc": desc,
                        "sum_curr": sum_curr_str,
                        "sum_target": sum_target_str,
                        "image_path": image_path,
                    }
                )

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
                    print("🔑 [Google Drive Auth] Successfully loaded user's personal Google OAuth access token!")
                except Exception as oauth_err:
                    print(f"⚠️ [Google Drive Auth] Failed to initialize user OAuth credentials: {oauth_err}")

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
                print(f"📁 [Google Docs Export] Target Drive Folder: {target_folder}, Template ID: {active_template}")

                copy_body = {"name": doc_title}
                if target_folder:
                    copy_body["parents"] = [target_folder]

                new_file = (
                    drive_service.files().copy(fileId=active_template, body=copy_body, supportsAllDrives=True).execute()
                )
                google_doc_id = new_file.get("id")
                google_doc_url = f"https://docs.google.com/document/d/{google_doc_id}/edit"

                # Validate required placeholders in the copied document
                try:
                    initial_doc = docs_service.documents().get(documentId=google_doc_id).execute()
                    initial_text = _extract_text_from_gdoc(initial_doc)
                    missing_tags = [tag for tag in REQUIRED_TEMPLATE_TAGS if tag not in initial_text]
                    if missing_tags:
                        print(
                            f"⚠️ [Template Validation Warning] Template {active_template} is missing required tags: {', '.join(missing_tags)}"
                        )
                    else:
                        print(
                            f"✅ [Template Validation] All required template tags verified in template {active_template}"
                        )
                except Exception as val_err:
                    print(f"Notice: Template tag pre-check: {val_err}")

                try:
                    drive_service.permissions().create(
                        fileId=google_doc_id,
                        body={"type": "anyone", "role": "writer"},
                        fields="id",
                        supportsAllDrives=True,
                    ).execute()
                except Exception as perm_err:
                    print(f"Notice: Public link permission creation: {perm_err}")

                today_str = datetime.date.today().strftime("%d.%m.%Y")
                total_curr_str, total_target_str = calculate_receipt_totals(receipts_data, target_currency)

                # Upload receipt proof images to Google Drive alongside the doc and embed into Google Doc
                uploaded_proof_ids = []
                for idx, raw_img in enumerate(session_images):
                    try:
                        img_b = raw_img
                        if isinstance(img_b, str):
                            if os.path.exists(img_b):
                                with open(img_b, "rb") as f:
                                    img_b = f.read()
                            elif img_b.startswith("data:") and "," in img_b:
                                img_b = base64.b64decode(img_b.split(",", 1)[1])
                            else:
                                img_b = base64.b64decode(img_b)

                        if (
                            img_b
                            and isinstance(img_b, (bytes, bytearray))
                            and len(img_b) > 10
                            and drive_service
                            and MediaIoBaseUpload
                        ):
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
                                except Exception:
                                    pass
                                uploaded_proof_ids.append(proof_id)
                    except Exception as upload_err:
                        print(f"⚠️ [Google Drive Proof Upload Notice] {upload_err}")

                global_replaces = [
                    ("{{TITLE}}", title),
                    ("{{Current date}}", today_str),
                    ("{{EUR/USD}}", target_currency),
                    ("{{Current exchange rate}}", f"{rate_val:.4f}"),
                    ("{{Local Currency Code}}", local_curr_code),
                    ("{{TOTAL SUM CURR}}", total_curr_str),
                    ("{{TOTAL SUM EUR/USD}}", total_target_str),
                    ("{{APPROVED}}", approved_budget or ""),
                    ("{{Bank link}}", rate_url or (f"({rate_source_name})" if rate_source_name != "N/A" else "")),
                    ("{{PROOFS}}", ""),
                ]
                if receipts_data:
                    global_replaces.extend(
                        [
                            ("{{Category}}", receipts_data[0].get("category", "")),
                            ("{{Desc}}", receipts_data[0].get("desc", "Expense")),
                            ("{{SUM CURR}}", receipts_data[0].get("sum_curr", "")),
                            ("{{SUM EUR/USD}}", receipts_data[0].get("sum_target", "")),
                        ]
                    )

                gdoc_requests = [
                    {"replaceAllText": {"containsText": {"text": k, "matchCase": True}, "replaceText": v}}
                    for k, v in global_replaces
                ]
                docs_service.documents().batchUpdate(
                    documentId=google_doc_id, body={"requests": gdoc_requests}
                ).execute()
                print(f"✅ [Google Docs API] Successfully populated template text: {google_doc_url}")

                # Directly embed inline images into the Google Doc
                for idx, proof_id in enumerate(uploaded_proof_ids):
                    try:
                        # Direct Google Drive CDN thumbnail / content URI
                        image_uri = f"https://lh3.googleusercontent.com/d/{proof_id}"
                        image_req = {
                            "insertInlineImage": {
                                "endOfSegmentLocation": {},
                                "uri": image_uri,
                                "objectSize": {
                                    "width": {"magnitude": 450, "unit": "PT"},
                                    "height": {"magnitude": 300, "unit": "PT"},
                                },
                            }
                        }
                        docs_service.documents().batchUpdate(
                            documentId=google_doc_id, body={"requests": [image_req]}
                        ).execute()
                        print(f"✅ [Google Docs API] Embedded inline proof image #{idx + 1} directly into doc.")
                    except Exception as embed_err:
                        print(f"⚠️ [Google Docs Image Embed Notice] {embed_err}")
                        try:
                            fallback_uri = f"https://drive.google.com/uc?export=download&id={proof_id}"
                            docs_service.documents().batchUpdate(
                                documentId=google_doc_id,
                                body={
                                    "requests": [
                                        {"insertInlineImage": {"endOfSegmentLocation": {}, "uri": fallback_uri}}
                                    ]
                                },
                            ).execute()
                            print(f"✅ [Google Docs API] Embedded inline proof image #{idx + 1} using fallback URI.")
                        except Exception as fb_err:
                            print(f"⚠️ [Google Docs Image Fallback Notice] {fb_err}")
        except Exception as gdoc_err:
            print(f"⚠️ [Google Docs API Error] {gdoc_err}")
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
            "message": f"Successfully generated Expense Reimbursement report in Google Docs: [{title}]({google_doc_url})",
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to generate expense report: {str(e)}"}


# Alias export_summary_to_docx for direct semantic calling
export_summary_to_docx = export_summary_to_google_doc
