import datetime
import mimetypes
import os
import re
from pathlib import Path

import requests
from google import genai
from google.adk.tools import ToolContext
from google.genai import types

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
        search_dirs = [Path(os.getcwd())]
        for parent in Path(os.getcwd()).parents:
            if "Experiments" in parent.parts or "gdg_krakow_tool" in parent.parts:
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

        # Initialize Google GenAI client
        client = genai.Client()

        # Perform native multimodal OCR and data extraction using gemini-2.5-pro
        prompt = (
            "You are a professional OCR assistant. Recognize and extract all text and structured data "
            "from this document (receipt/invoice). List all itemized positions, quantities, unit prices, "
            "taxes (VAT/GST), total sums, document currency, dates, and issuer details. "
            "Perform this extraction with maximum accuracy and detail."
        )

        model = "gemini-2.5-pro"
        response = client.models.generate_content(
            model=model, contents=[types.Part.from_bytes(data=raw_bytes, mime_type=mime_type), prompt]
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
    folder_id: str = None,
    template_id: str = None,
    exchange_rate: float = None,
    receipts_data: list = None,
    target_currency: str = "USD",
    approved_budget: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """
    Creates a new Google Doc in your Google Drive by copying a template and populating it.

    Args:
        title: Title of the Google Doc to create
        folder_id: Optional Google Drive Folder ID.
        template_id: Optional Google Docs Template ID.
        exchange_rate: Optional Pekao bank exchange rate.
        receipts_data: Optional structured list of dicts with keys: desc, sum_pln, sum_usd, image_path.
        target_currency: Optional target approved currency for the report ("USD" or "EUR").

    Returns:
        dict: Success status, document ID, and view link.
    """
    scopes = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
    try:
        import google.auth
        from googleapiclient.discovery import build

        # Check for service account JSON keys or personal OAuth client credentials
        root_dir = Path(__file__).resolve().parent.parent

        sa_file = None
        for p in [
            root_dir / "configs" / "service_account.json",
            root_dir / "service_account.json",
            Path.cwd() / "configs" / "service_account.json",
            Path.cwd() / "service_account.json",
        ]:
            if p.exists():
                sa_file = p
                break

        client_secrets_file = None
        for p in [
            root_dir / "configs" / "credentials.json",
            root_dir / "credentials.json",
            Path.cwd() / "configs" / "credentials.json",
            Path.cwd() / "credentials.json",
        ]:
            if p.exists():
                client_secrets_file = p
                break

        credentials = None
        if sa_file:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(str(sa_file), scopes=scopes)
        elif client_secrets_file:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Check for token.json in configs folder first, fallback to root
            token_path = root_dir / "configs" / "token.json"
            if not token_path.exists() and (root_dir / "token.json").exists():
                token_path = root_dir / "token.json"
            elif not token_path.parent.exists():
                token_path = root_dir / "token.json"

            if token_path.exists():
                try:
                    credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
                except Exception as load_err:
                    print(f"Warning: Failed to load token.json: {load_err}")
                    credentials = None

            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    try:
                        credentials.refresh(Request())
                    except Exception as refresh_err:
                        print(f"Warning: Failed to refresh token: {refresh_err}")
                        credentials = None
                        if token_path.exists():
                            try:
                                os.unlink(token_path)
                                print("Stale configs/token.json deleted successfully.")
                            except Exception as del_err:
                                print(f"Warning: Failed to delete stale token.json: {del_err}")

                if not credentials:
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_file), scopes=scopes)
                        credentials = flow.run_local_server(port=0)
                        # Cache authorized credentials to token.json
                        with open(token_path, "w") as token_file:
                            token_file.write(credentials.to_json())
                    except Exception as flow_err:
                        print(f"Warning: OAuth flow failed: {flow_err}")
                        credentials = None

            # Fallback to default credentials if client secrets flow is unconfigured or failed
            if not credentials:
                print("Falling back to default credentials (gcloud application-default)...")
                credentials, project = google.auth.default(scopes=scopes)
        else:
            credentials, project = google.auth.default(scopes=scopes)

        docs_service = build("docs", "v1", credentials=credentials)
        drive_service = build("drive", "v3", credentials=credentials)

        target_folder = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")

        # Resolve active template ID from .gdoc file if not provided as argument
        if not template_id:
            try:
                gdoc_path = root_dir / "receipt_scanner" / "assets" / "Expense_report_template.gdoc"
                if gdoc_path.exists():
                    import json

                    with open(gdoc_path, "r") as f:
                        gdoc_data = json.load(f)
                        template_id = gdoc_data.get("doc_id")
            except Exception as ex:
                print(f"Warning: Failed to load doc_id from .gdoc asset: {ex}")

        active_template = template_id or os.getenv("GOOGLE_DOCS_TEMPLATE_ID")

        # ----------------------------------------------------
        # Python-based Currency Calculations and Normalization
        # ----------------------------------------------------
        target_currency = target_currency.upper().strip()

        # Check if conversion is required (if any receipt is in a different currency)
        conversion_required = False
        local_curr_code = ""
        if receipts_data:
            for item in receipts_data:
                item_curr = item.get("currency", "USD").upper().strip()
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
                        amount_in_target = amount_in_pln / rate_val

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

        doc_id = None

        if active_template:
            # 1a. Copy the template document directly to the target folder
            copy_body = {"name": title}
            if target_folder:
                copy_body["parents"] = [target_folder]

            copied_file = drive_service.files().copy(fileId=active_template, body=copy_body).execute()
            doc_id = copied_file.get("id")

            # Fetch document data to locate placeholders and tables
            doc_data = docs_service.documents().get(documentId=doc_id).execute()

            def find_placeholder_index(content, placeholder):
                for element in content:
                    if "paragraph" in element:
                        elements = element["paragraph"].get("elements", [])
                        for el in elements:
                            if "textRun" in el:
                                text = el["textRun"].get("content", "")
                                if placeholder in text:
                                    return el.get("startIndex")
                    elif "table" in element:
                        table_rows = element["table"].get("tableRows", [])
                        for row in table_rows:
                            cells = row.get("tableCells", [])
                            for cell in cells:
                                cell_index = find_placeholder_index(cell.get("content", []), placeholder)
                                if cell_index is not None:
                                    return cell_index
                return None

            # Helper to retrieve text from paragraph element
            def get_paragraph_text(paragraph_element):
                return "".join(el.get("textRun", {}).get("content", "") for el in paragraph_element.get("elements", []))

            # If no conversion is required, delete the currency conversion section
            if not conversion_required:
                delete_ranges = []
                for element in doc_data.get("body", {}).get("content", []):
                    if "paragraph" in element:
                        text = get_paragraph_text(element["paragraph"])
                        if (
                            "currency conversion" in text.lower()
                            or "{{current exchange rate}}" in text.lower()
                            or "{{local currency code}}" in text.lower()
                        ):
                            delete_ranges.append((element["startIndex"], element["endIndex"]))

                if delete_ranges:
                    delete_ranges.sort(key=lambda r: r[0], reverse=True)
                    requests = []
                    for start, end in delete_ranges:
                        requests.append({"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}})
                    try:
                        docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
                    except Exception as delete_err:
                        print(f"Warning: Failed to delete conversion paragraphs: {delete_err}")

                    # Refetch doc_data to update structural indices
                    doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # ----------------------------------------------------
            # 1. EXPENSES TABLE HANDLING (2. List of Expenses)
            # ----------------------------------------------------
            def find_table_with_placeholder(content, placeholder):
                for element in content:
                    if "table" in element:
                        for row in element["table"].get("tableRows", []):
                            for cell in row.get("tableCells", []):
                                for cell_el in cell.get("content", []):
                                    if "paragraph" in cell_el:
                                        for part in cell_el["paragraph"].get("elements", []):
                                            if "textRun" in part:
                                                if placeholder in part["textRun"].get("content", ""):
                                                    return element
                return None

            placeholder_table = find_table_with_placeholder(doc_data.get("body", {}).get("content", []), "{{Desc}}")

            if placeholder_table and receipts_data and len(receipts_data) > 1:
                table_start_index = placeholder_table.get("startIndex")

                # Insert empty rows below row 1
                for i in range(len(receipts_data) - 1):
                    docs_service.documents().batchUpdate(
                        documentId=doc_id,
                        body={
                            "requests": [
                                {
                                    "insertTableRow": {
                                        "tableCellLocation": {
                                            "tableStartLocation": {"index": table_start_index},
                                            "rowIndex": 1 + i,
                                            "columnIndex": 0,
                                        },
                                        "insertBelow": True,
                                    }
                                }
                            ]
                        },
                    ).execute()

                # Fetch updated document structural indices
                doc_data = docs_service.documents().get(documentId=doc_id).execute()

                # Locate table in the updated document
                updated_table = None
                for el in doc_data.get("body", {}).get("content", []):
                    if "table" in el and el.get("startIndex") == table_start_index:
                        updated_table = el
                        break

                if updated_table:
                    cell_inserts = []
                    # Populate newly created rows with index 1 to N-1 (rows 2 to N in document)
                    for k in range(1, len(receipts_data)):
                        row = updated_table["table"]["tableRows"][1 + k]
                        cells = row["tableCells"]

                        texts_to_write = [
                            str(1 + k),
                            "",  # Leave Category cell empty to not override dropdown manually
                            receipts_data[k].get("desc", ""),
                            receipts_data[k].get("sum_curr", ""),
                            receipts_data[k].get("sum_target", ""),
                        ]

                        for col_idx, text_to_write in enumerate(texts_to_write):
                            if col_idx < len(cells):
                                cell = cells[col_idx]
                                if cell.get("content") and "paragraph" in cell["content"][0]:
                                    elements = cell["content"][0]["paragraph"].get("elements", [])
                                    if elements:
                                        start_idx = elements[0].get("startIndex")
                                        if text_to_write:
                                            cell_inserts.append(
                                                {
                                                    "insertText": {
                                                        "location": {"index": start_idx},
                                                        "text": text_to_write,
                                                    }
                                                }
                                            )

                    # Sort inserts in descending order of startIndex to prevent offset shift invalidation
                    if cell_inserts:
                        cell_inserts.sort(key=lambda x: x["insertText"]["location"]["index"], reverse=True)
                        docs_service.documents().batchUpdate(
                            documentId=doc_id, body={"requests": cell_inserts}
                        ).execute()

                # Refetch document content
                doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # ----------------------------------------------------
            # 2. GLOBAL METADATA REPLACEMENTS
            # ----------------------------------------------------
            today_str = datetime.date.today().strftime("%d.%m.%Y")

            from collections import defaultdict

            sums_by_currency = defaultdict(float)
            total_target = 0.0
            if receipts_data:
                for r in receipts_data:
                    try:
                        curr_str = r.get("sum_curr", "0.00 PLN")
                        parts = curr_str.split()
                        val = float(parts[0])
                        cur = parts[1]
                        sums_by_currency[cur] += val
                    except Exception:
                        pass

                    try:
                        target_str = r.get("sum_target", f"0.00 {target_currency}")
                        parts = target_str.split()
                        val = float(parts[0])
                        total_target += val
                    except Exception:
                        pass

            total_curr_parts = [f"{amt:.2f} {cur}" for cur, amt in sums_by_currency.items()]
            total_curr_str = ", ".join(total_curr_parts)
            total_target_str = f"{total_target:.2f} {target_currency}"

            global_replaces = [
                ("{{TITLE}}", title),
                ("{{Current date}}", today_str),
                ("{{EUR/USD}}", target_currency),
                ("{{Current exchange rate}}", f"{rate_val:.4f}"),
                ("{{Local Currency Code}}", local_curr_code),
                ("{{TOTAL SUM CURR}}", total_curr_str),
                ("{{TOTAL SUM EUR/USD}}", total_target_str),
                ("{{APPROVED}}", approved_budget or ""),
            ]
            if receipts_data:
                global_replaces.extend(
                    [
                        ("{{Desc}}", receipts_data[0].get("desc", "Expense")),
                        ("{{SUM CURR}}", receipts_data[0].get("sum_curr", "")),
                        ("{{SUM EUR/USD}}", receipts_data[0].get("sum_target", "")),
                    ]
                )

            metadata_requests = []
            for placeholder, val in global_replaces:
                metadata_requests.append(
                    {"replaceAllText": {"containsText": {"text": placeholder, "matchCase": True}, "replaceText": val}}
                )

            try:
                docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": metadata_requests}).execute()
            except Exception as e:
                print(f"Warning: Failed to replace metadata tags: {e}")

            # Refetch doc_data to get updated indices after first replacements
            doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # 2.2 Linkify the {{Bank link}} placeholder
            target_link_url = rate_url or "https://www.pekao.com.pl/kursy-walut.html"
            link_placeholder = "{{Bank link}}"
            link_index = find_placeholder_index(doc_data.get("body", {}).get("content", []), link_placeholder)
            if link_index is not None:
                link_text = target_link_url
                try:
                    docs_service.documents().batchUpdate(
                        documentId=doc_id,
                        body={
                            "requests": [
                                {
                                    "deleteContentRange": {
                                        "range": {
                                            "startIndex": link_index,
                                            "endIndex": link_index + len(link_placeholder),
                                        }
                                    }
                                },
                                {
                                    "insertText": {
                                        "location": {
                                            "index": link_index,
                                        },
                                        "text": link_text,
                                    }
                                },
                                {
                                    "updateTextStyle": {
                                        "range": {
                                            "startIndex": link_index,
                                            "endIndex": link_index + len(link_text),
                                        },
                                        "textStyle": {
                                            "link": {
                                                "url": target_link_url,
                                            },
                                            "underline": True,
                                            "foregroundColor": {
                                                "color": {
                                                    "rgbColor": {
                                                        "blue": 0.8,
                                                        "green": 0.3,
                                                        "red": 0.1,
                                                    }
                                                }
                                            },
                                        },
                                        "fields": "link,underline,foregroundColor",
                                    }
                                },
                            ]
                        },
                    ).execute()
                except Exception as link_e:
                    print(f"Warning: Failed to format bank link: {link_e}")

            # Fetch updated doc data for subsequent steps
            doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # ----------------------------------------------------
            # 3. PROOFS (RECEIPTS IMAGES/PDFs) INSERTION
            # ----------------------------------------------------
            proofs_placeholder = "{{PROOFS}}"
            proofs_index = find_placeholder_index(doc_data.get("body", {}).get("content", []), proofs_placeholder)

            if proofs_index is not None:
                # Delete the {{PROOFS}} placeholder text
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "deleteContentRange": {
                                    "range": {
                                        "startIndex": proofs_index,
                                        "endIndex": proofs_index + len(proofs_placeholder),
                                    }
                                }
                            }
                        ]
                    },
                ).execute()

                # Helper to upload local scan files to Google Drive
                def upload_file_to_drive(drive_service, file_path, folder_dest=None):
                    import mimetypes

                    from googleapiclient.http import MediaFileUpload

                    f_path = Path(file_path)
                    if not f_path.exists():
                        return None

                    mime, _ = mimetypes.guess_type(str(f_path))
                    if not mime:
                        mime = "application/octet-stream"

                    meta = {"name": f_path.name}
                    if folder_dest:
                        meta["parents"] = [folder_dest]

                    try:
                        media = MediaFileUpload(str(f_path), mimetype=mime, resumable=True)
                        up_file = (
                            drive_service.files()
                            .create(
                                body=meta, media_body=media, fields="id, webContentLink, webViewLink, thumbnailLink"
                            )
                            .execute()
                        )

                        fid = up_file.get("id")
                        # Share publicly so Docs API can read the image data
                        try:
                            drive_service.permissions().create(
                                fileId=fid, body={"role": "reader", "type": "anyone"}
                            ).execute()
                        except Exception as share_e:
                            print(f"Warning: Failed to make file public: {share_e}")

                        up_file["mime_type"] = mime
                        return up_file
                    except Exception as upload_e:
                        print(f"Warning: Failed to upload scan file: {upload_e}")
                        return None

                if receipts_data:
                    # Collect session attachments in chronological order
                    session_attachments = []
                    if tool_context and tool_context.session:
                        events = tool_context.session.events or []
                        for event in events:
                            if event.author == "user" and event.content and event.content.parts:
                                for part in event.content.parts:
                                    if part.inline_data and part.inline_data.data:
                                        session_attachments.append(
                                            {
                                                "data": part.inline_data.data,
                                                "mime_type": part.inline_data.mime_type or "image/jpeg",
                                            }
                                        )

                    # Insert in reversed order so they appear chronologically at proofs_index
                    for i, receipt in reversed(list(enumerate(receipts_data))):
                        path_str = receipt.get("image_path")
                        temp_file_path = None

                        # Check if file exists locally
                        file_exists = False
                        if path_str:
                            try:
                                resolved = Path(path_str).expanduser().resolve()
                                file_exists = resolved.exists()
                            except Exception:
                                file_exists = False

                        if not file_exists and i < len(session_attachments):
                            # Self-healing: Extract from session events!
                            attachment = session_attachments[i]
                            mime = attachment["mime_type"]
                            ext_map = {
                                "image/png": ".png",
                                "image/jpeg": ".jpg",
                                "image/webp": ".webp",
                                "application/pdf": ".pdf",
                            }
                            ext = ext_map.get(mime, ".jpg")

                            assets_dir = Path(__file__).resolve().parent / "assets"
                            assets_dir.mkdir(exist_ok=True)

                            temp_file_path = assets_dir / f"uploaded_receipt_{i}{ext}"
                            with open(temp_file_path, "wb") as f:
                                f.write(attachment["data"])

                            path_str = str(temp_file_path)
                            print(f"[DEBUG] Self-healed missing local file using session attachment {i}: {path_str}")

                        if not path_str:
                            continue

                        is_pdf = path_str.lower().endswith(".pdf")
                        temp_files_to_cleanup = []  # local temp files created by helpers
                        if temp_file_path:
                            temp_files_to_cleanup.append(str(temp_file_path))

                        if is_pdf:
                            # Convert PDF first page to PNG screenshot (never copies the PDF)
                            png_path = _pdf_to_png_screenshot(path_str)
                            if png_path:
                                upload_path = png_path
                                temp_files_to_cleanup.append(png_path)
                            else:
                                print(f"[WARNING] Skipping PDF (could not render): {path_str}")
                                continue
                        else:
                            # Auto-rotate image by EXIF if needed
                            rotated_path = _auto_rotate_image(path_str)
                            upload_path = rotated_path
                            if rotated_path != path_str:
                                temp_files_to_cleanup.append(rotated_path)

                        uploaded = upload_file_to_drive(drive_service, upload_path, target_folder)

                        # Clean up local temp files regardless of upload outcome
                        for tf in temp_files_to_cleanup:
                            try:
                                os.unlink(tf)
                            except Exception:
                                pass

                        if uploaded:
                            # Always treat as image (PNG from PDF or rotated photo)
                            docs_service.documents().batchUpdate(
                                documentId=doc_id,
                                body={
                                    "requests": [
                                        {
                                            "insertInlineImage": {
                                                "uri": uploaded.get("thumbnailLink", "").replace("=s220", "=s2000")
                                                if uploaded.get("thumbnailLink")
                                                else uploaded.get("webContentLink"),
                                                "objectSize": {"width": {"magnitude": 220, "unit": "PT"}},
                                                "location": {"index": proofs_index},
                                            }
                                        },
                                        {"insertText": {"location": {"index": proofs_index}, "text": "\n"}},
                                    ]
                                },
                            ).execute()
                            # Clean up the temporary uploaded image from Google Drive
                            try:
                                drive_service.files().delete(fileId=uploaded.get("id")).execute()
                                print(f"[DEBUG] Successfully deleted temp Drive file {uploaded.get('id')}.")
                            except Exception as cleanup_e:
                                print(f"[WARNING] Failed to cleanup temp Drive file: {cleanup_e}")

                # Fetch updated doc data
                doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # Check if template has {{CONTENT}} fallback and remove it if present
            placeholder_content = "{{CONTENT}}"
            content_index = find_placeholder_index(doc_data.get("body", {}).get("content", []), placeholder_content)

            if content_index is not None:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={
                        "requests": [
                            {
                                "deleteContentRange": {
                                    "range": {
                                        "startIndex": content_index,
                                        "endIndex": content_index + len(placeholder_content),
                                    }
                                }
                            }
                        ]
                    },
                ).execute()
        else:
            return {"success": False, "error": "No template ID provided. Raw text export is disabled."}

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {
            "success": True,
            "document_id": doc_id,
            "document_url": doc_url,
            "message": "Google Doc populated from template successfully!",
        }

    except Exception as e:
        error_msg = str(e)
        if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in error_msg or "403" in error_msg or "invalid_grant" in error_msg:
            return {
                "success": False,
                "error": (
                    "Authentication token has expired, been revoked, or has insufficient scopes.\n"
                    "To fix this, please run the following command in your terminal:\n\n"
                    'gcloud auth application-default login --scopes="https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/drive"\n\n'
                    "After running this command, restart the ADK web server and the permissions will automatically update!"
                ),
            }
        return {"success": False, "error": error_msg}
