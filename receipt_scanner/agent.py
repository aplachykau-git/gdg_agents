"""
Receipt & Invoice Scanner Agent
- Reads receipts and invoices (photos or PDFs) directly using gemini-2.5-pro
- Fetches the USD/PLN rate from the Pekao website
- Calculates amounts in PLN and USD using the Pekao rate
- Exports summary reports to Google Docs with beautiful formatting
"""

import io
import mimetypes
import os
import re
import base64
import tempfile
from pathlib import Path

import requests
from google import genai
from google.genai import types

from google.adk.agents.llm_agent import Agent


# ---------------------------------------------------------------------------
# Tool: get_usd_pln_rate
# ---------------------------------------------------------------------------

def get_usd_pln_rate() -> dict:
    """
    Fetches the current USD/PLN 'Bank kupuje' (bank buy) exchange rate
    from Pekao bank website (https://www.pekao.com.pl/kursy-walut.html).

    Returns:
        dict with keys: 'success', 'rate' (float), 'source', 'error'
    """
    url = "https://www.pekao.com.pl/kursy-walut.html"
    try:
        resp = requests.get(
            url,
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
            return {"success": False, "error": "USD block not found on Pekao page"}

        # Search for cr-buy rate after the USD section
        snippet = html[usd_idx: usd_idx + 1200]
        match = re.search(r'cr-buy[^>]*>.*?<span[^>]*>\s*([\d,\.]+)\s*</span>', snippet, re.S)
        if not match:
            return {"success": False, "error": "Could not parse rate from Pekao page"}

        rate_str = match.group(1).replace(",", ".")
        rate = float(rate_str)

        return {
            "success": True,
            "rate": rate,
            "source": "Pekao Bank kupuje USD/PLN",
            "url": url,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


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
                        if not f.startswith('.'):
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
                )
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

    supported = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}
    if mime_type not in supported:
        return {
            "success": False,
            "error": f"Unsupported file type: {mime_type}. Supported: jpg, png, webp, gif, pdf"
        }

    try:
        raw_bytes = path.read_bytes()
        
        # Initialize Google GenAI client (uses Vertex AI backend under the hood with configured region)
        client = genai.Client()
        
        # Perform native multimodal OCR and data extraction using gemini-2.5-pro
        prompt = (
            "You are a professional OCR assistant. Recognize and extract all text and structured data "
            "from this document (receipt/invoice). List all itemized positions, quantities, unit prices, "
            "taxes (VAT/GST), total sums, document currency, dates, and issuer details. "
            "Perform this extraction with maximum accuracy and detail."
        )
        
        model = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro")
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=raw_bytes, mime_type=mime_type),
                prompt
            ]
        )
        
        return {
            "success": True,
            "file_name": path.name,
            "content_text": response.text
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to natively process document: {str(e)}"}


# ---------------------------------------------------------------------------
# Helpers: image auto-rotate and PDF-to-PNG
# ---------------------------------------------------------------------------

def _auto_rotate_image(img_path: str) -> str:
    """
    Returns a path to an EXIF-corrected copy of the image if rotation is needed,
    otherwise returns the original path unchanged.
    The copy is written to a temp file and should be cleaned up by the caller.
    """
    try:
        from PIL import Image, ExifTags
        img = Image.open(img_path)
        exif = img._getexif() if hasattr(img, '_getexif') else None
        if not exif:
            return img_path
        orientation_key = next(
            (k for k, v in ExifTags.TAGS.items() if v == 'Orientation'), None
        )
        if orientation_key is None or orientation_key not in exif:
            return img_path
        orientation = exif[orientation_key]
        rotation_map = {3: 180, 6: 270, 8: 90}
        if orientation not in rotation_map:
            return img_path
        rotated = img.rotate(rotation_map[orientation], expand=True)
        suffix = Path(img_path).suffix or '.jpg'
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        rotated.save(tmp.name)
        tmp.close()
        print(f"[DEBUG] Auto-rotated image (orientation={orientation}): {tmp.name}")
        return tmp.name
    except Exception as e:
        print(f"[WARNING] Auto-rotate failed: {e}")
        return img_path


def _pdf_to_png_screenshot(pdf_path: str) -> str | None:
    """
    Renders the first page of a PDF to a PNG temp file and returns its path.
    Returns None on failure. The original PDF is never copied or moved.
    """
    try:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(pdf_path)
        page = doc[0]
        bitmap = page.render(scale=2.0)  # 2x scale for decent resolution
        pil_image = bitmap.to_pil()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        pil_image.save(tmp.name, format='PNG')
        tmp.close()
        doc.close()
        print(f"[DEBUG] PDF rendered to PNG screenshot: {tmp.name}")
        return tmp.name
    except Exception as e:
        print(f"[WARNING] PDF-to-PNG failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Tool: export_summary_to_google_doc
# ---------------------------------------------------------------------------

def export_summary_to_google_doc(
    title: str,
    folder_id: str = None,
    template_id: str = None,
    exchange_rate: float = None,
    receipts_data: list = None
) -> dict:
    """
    Creates a new Google Doc in your Google Drive by copying a template and populating it.

    Args:
        title: Title of the Google Doc to create
        folder_id: Optional Google Drive Folder ID.
        template_id: Optional Google Docs Template ID.
        exchange_rate: Optional Pekao bank exchange rate.
        receipts_data: Optional structured list of dicts with keys: desc, sum_pln, sum_usd, image_path.

    Returns:
        dict: Success status, document ID, and view link.
    """
    scopes = [
        'https://www.googleapis.com/auth/documents',
        'https://www.googleapis.com/auth/drive'
    ]
    try:
        from googleapiclient.discovery import build
        import google.auth
        import datetime
        
        # Check for service account JSON keys or personal OAuth client credentials
        root_dir = Path(__file__).resolve().parent.parent
        
        sa_file = None
        for p in [root_dir / "service_account.json", Path.cwd() / "service_account.json"]:
            if p.exists():
                sa_file = p
                break
                
        client_secrets_file = None
        for p in [root_dir / "credentials.json", Path.cwd() / "credentials.json"]:
            if p.exists():
                client_secrets_file = p
                break

        credentials = None
        if sa_file:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                str(sa_file),
                scopes=scopes
            )
        elif client_secrets_file:
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            
            token_path = root_dir / "token.json"
            if token_path.exists():
                credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
                
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(client_secrets_file),
                        scopes=scopes
                    )
                    credentials = flow.run_local_server(port=0)
                
                # Cache authorized credentials to token.json
                with open(token_path, "w") as token_file:
                    token_file.write(credentials.to_json())
        else:
            credentials, project = google.auth.default(scopes=scopes)
        
        docs_service = build('docs', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)
        
        target_folder = folder_id or os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        active_template = template_id or os.getenv("GOOGLE_DOCS_TEMPLATE_ID")
        
        doc_id = None
        insert_index = 1
        
        if active_template:
            # 1a. Copy the template document directly to the target folder
            copy_body = {'name': title}
            if target_folder:
                copy_body['parents'] = [target_folder]
            
            copied_file = drive_service.files().copy(
                fileId=active_template,
                body=copy_body
            ).execute()
            doc_id = copied_file.get('id')
            
            # Fetch document data to locate placeholders and tables
            doc_data = docs_service.documents().get(documentId=doc_id).execute()
            
            def find_placeholder_index(content, placeholder):
                for element in content:
                    if 'paragraph' in element:
                        elements = element['paragraph'].get('elements', [])
                        for el in elements:
                            if 'textRun' in el:
                                text = el['textRun'].get('content', '')
                                if placeholder in text:
                                    return el.get('startIndex')
                    elif 'table' in element:
                        table_rows = element['table'].get('tableRows', [])
                        for row in table_rows:
                            cells = row.get('tableCells', [])
                            for cell in cells:
                                cell_index = find_placeholder_index(cell.get('content', []), placeholder)
                                if cell_index is not None:
                                    return cell_index
                return None

            # ----------------------------------------------------
            # 1. EXPENSES TABLE HANDLING (2. List of Expenses)
            # ----------------------------------------------------
            def find_table_with_placeholder(content, placeholder):
                for element in content:
                    if 'table' in element:
                        for row in element['table'].get('tableRows', []):
                            for cell in row.get('tableCells', []):
                                for cell_el in cell.get('content', []):
                                    if 'paragraph' in cell_el:
                                        for part in cell_el['paragraph'].get('elements', []):
                                            if 'textRun' in part:
                                                if placeholder in part['textRun'].get('content', ''):
                                                    return element
                return None

            placeholder_table = find_table_with_placeholder(doc_data.get('body', {}).get('content', []), "{{Desc}}")
            
            if placeholder_table and receipts_data and len(receipts_data) > 1:
                table_start_index = placeholder_table.get('startIndex')
                
                # Insert empty rows below row 1
                for i in range(len(receipts_data) - 1):
                    docs_service.documents().batchUpdate(
                        documentId=doc_id,
                        body={'requests': [{
                            'insertTableRow': {
                                'tableCellLocation': {
                                    'tableStartLocation': {'index': table_start_index},
                                    'rowIndex': 1 + i,
                                    'columnIndex': 0
                                },
                                'insertBelow': True
                            }
                        }]}
                    ).execute()
                
                # Fetch updated document structural indices
                doc_data = docs_service.documents().get(documentId=doc_id).execute()
                
                # Locate table in the updated document
                updated_table = None
                for el in doc_data.get('body', {}).get('content', []):
                    if 'table' in el and el.get('startIndex') == table_start_index:
                        updated_table = el
                        break
                
                if updated_table:
                    cell_inserts = []
                    # Populate newly created rows with index 1 to N-1 (rows 2 to N in document)
                    for k in range(1, len(receipts_data)):
                        row = updated_table['table']['tableRows'][1 + k]
                        cells = row['tableCells']
                        
                        texts_to_write = [
                            str(1 + k),
                            "",  # Leave Category cell empty to not override dropdown manually
                            receipts_data[k].get('desc', ''),
                            receipts_data[k].get('sum_pln', ''),
                            receipts_data[k].get('sum_usd', '')
                        ]
                        
                        for col_idx, text_to_write in enumerate(texts_to_write):
                            if col_idx < len(cells):
                                cell = cells[col_idx]
                                if cell.get('content') and 'paragraph' in cell['content'][0]:
                                    elements = cell['content'][0]['paragraph'].get('elements', [])
                                    if elements:
                                        start_idx = elements[0].get('startIndex')
                                        if text_to_write:
                                            cell_inserts.append({
                                                'insertText': {
                                                    'location': {'index': start_idx},
                                                    'text': text_to_write
                                                }
                                            })
                    
                    # Sort inserts in descending order of startIndex to prevent offset shift invalidation
                    if cell_inserts:
                        cell_inserts.sort(key=lambda x: x['insertText']['location']['index'], reverse=True)
                        docs_service.documents().batchUpdate(
                            documentId=doc_id,
                            body={'requests': cell_inserts}
                        ).execute()
                
                # Refetch document content
                doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # ----------------------------------------------------
            # 2. GLOBAL METADATA REPLACEMENTS
            # ----------------------------------------------------
            today_str = datetime.date.today().strftime("%d.%m.%Y")
            rate_val = exchange_rate or 1.0

            # Compute real totals from all receipts
            def _parse_amount(s: str) -> float:
                """Extract numeric value from a string like '124.50 PLN' or '31.28 USD'."""
                try:
                    return float(re.sub(r'[^\d.]', '', s.split()[0]))
                except Exception:
                    return 0.0

            total_pln = 0.0
            total_usd = 0.0
            if receipts_data:
                for r in receipts_data:
                    total_pln += _parse_amount(r.get('sum_pln', '0'))
                    total_usd += _parse_amount(r.get('sum_usd', '0'))

            total_pln_str = f"{total_pln:.2f} PLN"
            total_usd_str = f"{total_usd:.2f} USD"

            global_replaces = [
                ('{{TITLE}}', title),
                ('{{Current date}}', today_str),
                ('{{Current exchange rate}}', f"{rate_val:.4f}"),
                ('{{TOTAL SUM USD}}', total_usd_str),
                ('{{TOTAL SUM PL}}', total_pln_str),
            ]
            if receipts_data:
                global_replaces.extend([
                    ('{{Desc}}', receipts_data[0].get('desc', 'Expense')),
                    ('{{SUM PL}}', receipts_data[0].get('sum_pln', '0.00 PLN')),
                    ('{{SUM USD}}', receipts_data[0].get('sum_usd', '0.00 USD')),
                ])
                
            metadata_requests = []
            for placeholder, val in global_replaces:
                metadata_requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': placeholder,
                            'matchCase': True
                        },
                        'replaceText': val
                    }
                })
                
            try:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': metadata_requests}
                ).execute()
            except Exception as e:
                print(f"Warning: Failed to replace metadata tags: {e}")
                
            # Fetch updated doc data
            doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # ----------------------------------------------------
            # 3. PROOFS (RECEIPTS IMAGES/PDFs) INSERTION
            # ----------------------------------------------------
            proofs_placeholder = "{{PROOFS}}"
            proofs_index = find_placeholder_index(doc_data.get('body', {}).get('content', []), proofs_placeholder)
            
            if proofs_index is not None:
                # Delete the {{PROOFS}} placeholder text
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': [{
                        'deleteContentRange': {
                            'range': {
                                'startIndex': proofs_index,
                                'endIndex': proofs_index + len(proofs_placeholder)
                            }
                        }
                    }]}
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
                        
                    meta = {'name': f_path.name}
                    if folder_dest:
                        meta['parents'] = [folder_dest]
                        
                    try:
                        media = MediaFileUpload(str(f_path), mimetype=mime, resumable=True)
                        up_file = drive_service.files().create(
                            body=meta,
                            media_body=media,
                            fields='id, webContentLink, webViewLink, thumbnailLink'
                        ).execute()
                        
                        fid = up_file.get('id')
                        # Share publicly so Docs API can read the image data
                        try:
                            drive_service.permissions().create(
                                fileId=fid,
                                body={'role': 'reader', 'type': 'anyone'}
                            ).execute()
                        except Exception as share_e:
                            print(f"Warning: Failed to make file public: {share_e}")
                            
                        up_file['mime_type'] = mime
                        return up_file
                    except Exception as upload_e:
                        print(f"Warning: Failed to upload scan file: {upload_e}")
                        return None

                if receipts_data:
                    # Insert in reversed order so they appear chronologically at proofs_index
                    for receipt in reversed(receipts_data):
                        path_str = receipt.get('image_path')
                        if not path_str:
                            continue

                        is_pdf = path_str.lower().endswith('.pdf')
                        temp_files_to_cleanup = []  # local temp files created by helpers

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
                                body={'requests': [
                                    {
                                        'insertInlineImage': {
                                            'uri': uploaded.get('thumbnailLink', '').replace('=s220', '=s2000') if uploaded.get('thumbnailLink') else uploaded.get('webContentLink'),
                                            'objectSize': {
                                                'width': {'magnitude': 220, 'unit': 'PT'}
                                            },
                                            'location': {'index': proofs_index}
                                        }
                                    },
                                    {
                                        'insertText': {
                                            'location': {'index': proofs_index},
                                            'text': "\n"
                                        }
                                    }
                                ]}
                            ).execute()
                            # Clean up the temporary uploaded image from Google Drive
                            try:
                                drive_service.files().delete(fileId=uploaded.get('id')).execute()
                                print(f"[DEBUG] Successfully deleted temp Drive file {uploaded.get('id')}.")
                            except Exception as cleanup_e:
                                print(f"[WARNING] Failed to cleanup temp Drive file: {cleanup_e}")
                
                # Fetch updated doc data
                doc_data = docs_service.documents().get(documentId=doc_id).execute()

            # Check if template has {{CONTENT}} fallback and remove it if present
            placeholder_content = "{{CONTENT}}"
            content_index = find_placeholder_index(doc_data.get('body', {}).get('content', []), placeholder_content)
            
            if content_index is not None:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': [{
                        'deleteContentRange': {
                            'range': {
                                'startIndex': content_index,
                                'endIndex': content_index + len(placeholder_content)
                            }
                        }
                    }]}
                ).execute()
        else:
            return {"success": False, "error": "No template ID provided. Raw text export is disabled."}

        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        return {
            "success": True,
            "document_id": doc_id,
            "document_url": doc_url,
            "message": "Google Doc populated from template successfully!"
        }
        
    except Exception as e:
        error_msg = str(e)
        if "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in error_msg or "403" in error_msg:
            return {
                "success": False,
                "error": (
                    "403 Insufficient Authentication Scopes.\n"
                    "To fix this, please run the following command in your terminal:\n\n"
                    "gcloud auth application-default login --scopes=\"https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/documents,https://www.googleapis.com/auth/drive\"\n\n"
                    "After running this command, restart the ADK web server and the permissions will automatically update!"
                )
            }
        return {"success": False, "error": error_msg}


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

INSTRUCTION = """
You are an advanced agent designed to recognize receipts and invoices with dynamic currency conversion and templated reporting.
You run on the gemini-2.5-pro model.

⚠️ IMPORTANT: You HAVE a direct tool called `export_summary_to_google_doc` for creating and writing reports in Google Docs. You CAN export reports directly. Never tell the user that you cannot do this! If the user requests an export or document creation, immediately invoke `export_summary_to_google_doc`.

## Workflow Algorithm for Each Request:

**Step 1.** Immediately invoke the tool `get_usd_pln_rate` to fetch the current USD/PLN exchange rate (Bank kupuje) from the Pekao website. Memorize this exchange rate.

**Step 2.** For each file provided by the user, analyze its content to extract all products, services, quantities, unit prices, taxes, totals, dates, and currencies.
- If the user attached files directly in the chat interface, YOU ALREADY SEE THEM. **DO NOT** call the `read_receipt_file` tool for chat attachments. Use your native multimodal vision to analyze the attached files directly.
- **ONLY** invoke the `read_receipt_file` tool if the user provides a local file path as text in the prompt instead of an attachment.

⚠️ CRITICAL DOCUMENT VALIDATION CHECK:
Immediately after reading/analyzing each file, perform a strict validation check:
1. If the document cannot be recognized (text is unreadable, blurred, or the file is empty/corrupted).
2. Or if the document currency is NOT in the allowed list: PLN, EUR, USD (for example, if the currency is AUD, GBP, CAD, CHF, or cannot be determined at all).

In any of these cases, you MUST IMMEDIATELY ABORT execution:
- DO NOT proceed to further steps.
- DO NOT invoke the tool `export_summary_to_google_doc`.
- Output a clear, user-friendly error message in English (e.g., "Error: Document currency (<currency>) is not supported. Only PLN, EUR, and USD are allowed." or "Error: Failed to recognize data on the receipt <filename>.").

**Step 3.** Immediately after successful recognition and validation of all files, export the generated report into Google Docs by calling `export_summary_to_google_doc`.
You MUST automatically determine the title of the document using the following rules:
1. Extract dates from all recognized receipts/invoices.
2. Select the **latest date (closest to today)**.
3. Format the document title strictly as: `BWAI_day_month_year` (where day, month, and year are numeric digits. For example, if the latest receipt date is May 17, 2026, the title must be `BWAI_17_05_2026`; if January 7, 2026, it must be `BWAI_07_01_2026`).
4. To perfectly populate the Google Docs template, you **MUST pass** the following additional arguments to `export_summary_to_google_doc`:
   - `exchange_rate`: The Pekao bank exchange rate fetched in Step 1 (as a float, e.g., `3.98`).
   - `receipts_data`: A list of dictionaries representing each receipt. Each dictionary must contain the following keys:
     - `"category"`: String. The expense category. You **MUST classify** each expense into one of the following exact categories (choose the most suitable one):
       * `Transport` (taxis, Uber, trains, transit tickets, parking)
       * `Hotel` (lodging, hotels, hostels, apartment rentals)
       * `Food & drinks` (restaurants, groceries, cafes, food/water)
       * `Swag` (company merchandise, branded clothing, souvenirs)
       * `Prizes` (cups, prizes, awards, developer gifts)
       * `Venue` (room hire, workspace, venue rentals)
     - `"desc"`: A short description of the expense **strictly in English** (2-4 words, e.g., "Kaufland Grocery", "Uber Ride", "Hotel Accommodation"). Even if the receipt is in Polish, German, Russian, or any other language, you MUST translate the description into English!
     - `"sum_pln"`: The sum in PLN (formatted string, e.g., `"124.50 PLN"`).
     - `"sum_usd"`: The sum in USD based on the exchange rate (formatted string, e.g., `"31.28 USD"`).
      - `"image_path"`: The absolute local path of the receipt file (image or PDF). The tool handles everything: images are auto-rotated, PDFs are rendered to a PNG screenshot automatically. Never skip this field for local paths!
5. Immediately invoke `export_summary_to_google_doc` with all these parameters and display the clickable direct URL to the created document to the user. Perform this export automatically without asking the user for confirmation!

## Rules:
- Round all amounts in PLN and USD to 2 decimal places.
- Do not invent any numbers; use only what is visible on the documents.
- The `{{TOTAL SUM PL}}` and `{{TOTAL SUM USD}}` placeholders in the document are filled automatically by summing all receipts — you do NOT need to pass totals separately.
"""

receipt_agent = Agent(
    model=os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro"),
    name="receipt_scanner",
    description=(
        "Agent for recognizing receipts and invoices. "
        "Natively analyzes images and PDFs using gemini-2.5-pro, "
        "converts to PLN and USD using the Pekao rate, exports reports to Google Docs."
    ),
    instruction=INSTRUCTION,
    tools=[get_usd_pln_rate, read_receipt_file, export_summary_to_google_doc],
)

# ADK 2.0 requires the entry-point agent to be named `root_agent`
root_agent = receipt_agent
