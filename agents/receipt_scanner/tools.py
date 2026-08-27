import datetime
import json
import mimetypes
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import google.auth
import requests
from google import genai
from google.adk.tools import ToolContext
from google.auth.transport.requests import Request
from google.genai import types
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    InstalledAppFlow = None

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except ImportError:
    build = None
    MediaFileUpload = None

from agents.common.storage import upload_bytes_to_storage
from agents.gemini_config import get_gemini_client

from .docx_generator import generate_expense_report_docx
from .utils import _auto_rotate_image, _pdf_to_png_screenshot

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
    and natively processes it using gemini-2.5-pro multimodal capability.

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

        # Perform native multimodal OCR and data extraction using gemini-2.5-pro
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
        project_root = agent_dir.parent.parent

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

        # Gather session attachments (raw image bytes) if available
        session_images = []
        if tool_context and hasattr(tool_context, "session") and tool_context.session:
            events = getattr(tool_context.session, "events", []) or []
            for event in events:
                if (
                    getattr(event, "author", "") == "user"
                    and getattr(event, "content", None)
                    and getattr(event.content, "parts", None)
                ):
                    for part in event.content.parts:
                        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
                            session_images.append(part.inline_data.data)

        # Generate DOCX document bytes
        results_dir = agent_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        safe_title = re.sub(r"[^a-zA-Z0-9_\-]", "_", title).strip("_") or "Expense_Report"
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        docx_filename = f"{safe_title}_{timestamp_str}.docx"
        local_docx_path = str(results_dir / docx_filename)

        community_name = os.getenv("COMMUNITY_NAME", "Community")
        template_docx_path = Path(__file__).resolve().parent / "assets" / "expense_report_template.docx"
        resolved_template = str(template_docx_path) if template_docx_path.exists() else None

        docx_bytes = generate_expense_report_docx(
            title=title,
            receipts_data=receipts_data,
            target_currency=target_currency,
            exchange_rate=rate_val or 1.0,
            rate_source=rate_source_name,
            rate_url=rate_url,
            approved_budget=approved_budget,
            community_name=community_name,
            session_images=session_images,
            output_path=local_docx_path,
            template_path=resolved_template,
        )

        # Upload generated DOCX directly to Google Cloud Storage
        cloud_docx_url = upload_bytes_to_storage(
            data=docx_bytes,
            destination_blob_name=f"reports/{docx_filename}",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # Also generate CSV backup
        total_curr_str, total_target_str = calculate_receipt_totals(receipts_data, target_currency)
        cloud_csv_url = None
        if receipts_data:
            try:
                csv_lines = ["Description,Original Amount,Target Currency Amount (" + target_currency + ")"]
                for r in receipts_data:
                    d = r.get("desc", "Expense").replace('"', '""')
                    sc = r.get("sum_curr", "")
                    st = r.get("sum_target", "")
                    csv_lines.append(f'"{d}","{sc}","{st}"')
                csv_lines.append(f'"TOTAL","{total_curr_str}","{total_target_str}"')
                csv_content = "\n".join(csv_lines).encode("utf-8")
                cloud_csv_url = upload_bytes_to_storage(
                    data=csv_content,
                    destination_blob_name=f"reports/{safe_title}_{timestamp_str}.csv",
                    content_type="text/csv",
                )
            except Exception as storage_err:
                print(f"⚠️ [Cloud Storage Notice] {storage_err}")

        primary_url = cloud_docx_url or f"/results/{docx_filename}"

        return {
            "success": True,
            "file_name": docx_filename,
            "document_id": docx_filename,
            "document_url": primary_url,
            "docx_url": primary_url,
            "download_url": primary_url,
            "storage_file_url": cloud_csv_url,
            "target_currency": target_currency,
            "exchange_rate": rate_val,
            "receipts_count": len(receipts_data or []),
            "message": f"Successfully generated Expense Reimbursement DOCX report: [{docx_filename}]({primary_url})",
        }

    except Exception as e:
        return {"success": False, "error": f"Failed to generate expense report: {str(e)}"}


# Alias export_summary_to_docx for direct semantic calling
export_summary_to_docx = export_summary_to_google_doc
