"""
DOCX Expense Report Generator for Receipt Scanner Agent.
Generates styled Microsoft Word (.docx) reimbursement reports populated from
receipt vision scans and template assets.
"""

import base64
import copy
import datetime
import hashlib
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional

try:
    import docx
    from docx import Document
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Inches, Pt, RGBColor
    from PIL import Image, ImageOps
except ImportError:
    docx = None
    Document = None

try:
    from .summary import group_and_sort_receipts
except ImportError:
    from agents.receipt_scanner.summary import group_and_sort_receipts

logger = logging.getLogger(__name__)


def calculate_receipt_totals(receipts_data: List[Dict[str, Any]], target_currency: str = "USD") -> tuple[str, str]:
    """Calculates total original currency and total target currency amounts."""
    total_target = 0.0
    orig_by_curr: Dict[str, float] = {}

    for r in receipts_data or []:
        # Original sum
        raw_sc = r.get("sum_curr") or r.get("sum_pln") or "0"
        m_sc = re.search(r"([\d.,]+)\s*([A-Za-z]+)?", str(raw_sc))
        if m_sc:
            try:
                amt = float(m_sc.group(1).replace(",", "."))
                curr = m_sc.group(2) or "PLN"
                orig_by_curr[curr.upper()] = orig_by_curr.get(curr.upper(), 0.0) + amt
            except ValueError:
                pass

        # Target sum
        raw_st = r.get("sum_target") or r.get("sum_usd") or "0"
        m_st = re.search(r"([\d.,]+)", str(raw_st))
        if m_st:
            try:
                amt = float(m_st.group(1).replace(",", "."))
                total_target += amt
            except ValueError:
                pass

    if orig_by_curr:
        orig_strs = [f"{amt:.2f} {curr}" for curr, amt in orig_by_curr.items()]
        orig_tot_str = " + ".join(orig_strs)
    else:
        orig_tot_str = "0.00 PLN"

    target_tot_str = f"{total_target:.2f} {target_currency.upper()}"
    return orig_tot_str, target_tot_str


def _safe_b64decode(data: str) -> bytes:
    if data.startswith("data:") and "," in data:
        data = data.split(",", 1)[1]
    normalized = data.strip().replace("-", "+").replace("_", "/")
    pad = len(normalized) % 4
    if pad:
        normalized += "=" * (4 - pad)
    return base64.b64decode(normalized)


def _extract_pdf_bytes_if_present(raw_bytes: bytes) -> Optional[bytes]:
    """Return clean PDF bytes if raw_bytes is a PDF or a multipart-wrapped PDF."""
    if not raw_bytes:
        return None
    if raw_bytes.startswith(b"%PDF"):
        return raw_bytes
    idx = raw_bytes.find(b"%PDF-", 0, 2048)
    if idx != -1:
        sliced = raw_bytes[idx:]
        eof_idx = sliced.rfind(b"%%EOF")
        if eof_idx != -1:
            return sliced[: eof_idx + 5]
        return sliced
    return None


def normalize_proof_bytes(raw: Any) -> Optional[bytes]:
    """Decode raw bytes, file path, or base64 data into raw document/image bytes."""
    if not raw:
        return None
    if isinstance(raw, (bytes, bytearray)):
        b = bytes(raw)
        if len(b) <= 10:
            return None
        pdf_b = _extract_pdf_bytes_if_present(b)
        if pdf_b is not None:
            return pdf_b
        return b
    if isinstance(raw, str):
        if os.path.exists(raw):
            try:
                with open(raw, "rb") as f:
                    data = f.read()
                if len(data) <= 10:
                    return None
                return _extract_pdf_bytes_if_present(data) or data
            except Exception as err:
                logger.warning(f"⚠️ [Image Read Error] Could not read {raw}: {err}")
        try:
            decoded = _safe_b64decode(raw)
            if len(decoded) > 10:
                return _extract_pdf_bytes_if_present(decoded) or decoded
        except Exception as err:
            logger.warning(f"⚠️ [Image Decode Error] Could not decode base64 data: {err}")
    return None


def _render_pdf_pages_stitched_to_pil(
    pdf_bytes: bytes,
    max_pages: int = 12,
    gap_px: int = 12,
) -> tuple[Optional[Any], int]:
    """
    Render all pages of a PDF receipt/invoice (up to `max_pages`) and stitch them into a
    single composite PIL Image with thin divider lines between pages:
    - 1 page: returned as-is.
    - 2 pages: stitched side-by-side (horizontal) if portrait, or stacked if landscape,
      so a 2-page PDF stays compact and wide enough in a 2-column report layout.
    - 3+ pages: tiled in a 2-column grid (2 pages per row, top-to-bottom, left-to-right)
      so all pages remain large, legible, and fit comfortably on a single Google Docs page.
    Returns `(pil_img, page_count)`.
    """
    try:
        import pypdfium2 as pdfium
        from PIL import ImageDraw

        pdf_doc = pdfium.PdfDocument(pdf_bytes)
        n_pages = min(len(pdf_doc), max_pages)
        if n_pages == 0:
            pdf_doc.close()
            return None, 0

        scale = 1.5 if n_pages <= 4 else (1.25 if n_pages <= 8 else 1.0)
        page_images = []
        for idx in range(n_pages):
            page = pdf_doc[idx]
            bitmap = page.render(scale=scale)
            pil_page = bitmap.to_pil().convert("RGB")
            page_images.append(pil_page)
        pdf_doc.close()

        if len(page_images) == 1:
            return page_images[0], 1

        target_width = max(im.size[0] for im in page_images)
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        normalized_pages = []
        for im in page_images:
            pw, ph = im.size
            if pw != target_width and pw > 0:
                new_h = max(1, int(round(ph * (target_width / pw))))
                im = im.resize((target_width, new_h), resample=resample)
            normalized_pages.append(im)

        total_height = sum(im.size[1] for im in normalized_pages) + gap_px * (len(normalized_pages) - 1)
        stitched = Image.new("RGB", (target_width, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(stitched)

        y_offset = 0
        for idx, im in enumerate(normalized_pages):
            stitched.paste(im, (0, y_offset))
            y_offset += im.size[1]
            if idx + 1 < len(normalized_pages):
                line_y = y_offset + gap_px // 2
                draw.line([(0, line_y), (target_width, line_y)], fill=(210, 214, 220), width=2)
                y_offset += gap_px

        return stitched, len(normalized_pages)
    except Exception as err:
        logger.debug(f"[DEBUG] Could not render PDF proof via pypdfium2: {err}")
        return None, 0


def _render_pdf_first_page_to_pil(pdf_bytes: bytes) -> Optional[Any]:
    """Render a PDF receipt (stitching multiple pages vertically if multi-page) to a PIL Image."""
    pil_img, _ = _render_pdf_pages_stitched_to_pil(pdf_bytes)
    return pil_img


def _heuristic_landscape_rotation_degrees(pil_img: Any) -> int:
    """
    Fast local computer-vision fallback for landscape receipt photos (width > height).
    Compares horizontal vs vertical projection-profile variance of dark text lines:
    if text lines run vertically (high column-to-column variance compared to row-to-row variance),
    returns 270 (90 deg counter-clockwise) to stand the receipt upright into portrait orientation.
    """
    try:
        gray = pil_img.convert("L").copy()
        gray.thumbnail((320, 320))
        gw, gh = gray.size
        if gw <= gh or gw < 16 or gh < 16:
            return 0
        pixels = gray.tobytes()
        # Compute mean darkness per row and per column (invert intensity: 255 - p)
        row_means = [sum(255 - pixels[r * gw + c] for c in range(gw)) / gw for r in range(gh)]
        col_means = [sum(255 - pixels[r * gw + c] for r in range(gh)) / gh for c in range(gw)]
        row_diff_energy = sum(abs(row_means[i + 1] - row_means[i]) for i in range(gh - 1)) / max(gh - 1, 1)
        col_diff_energy = sum(abs(col_means[j + 1] - col_means[j]) for j in range(gw - 1)) / max(gw - 1, 1)
        if col_diff_energy > row_diff_energy * 1.18:
            return 270
    except Exception as err:
        logger.debug(f"[DEBUG] Heuristic landscape orientation check failed: {err}")
    return 0


def detect_landscape_photo_rotation_degrees(pil_img: Any, use_vision_model: bool = True) -> int:
    """
    Intelligently detect if a landscape photo (width > height) is a vertical receipt
    lying on its side, and return the clockwise rotation in degrees (0, 90, 180, or 270)
    needed to make the receipt upright. Never called for PDF documents.
    """
    w, h = pil_img.size
    if w <= h:
        return 0

    if use_vision_model:
        try:
            from google.genai import types

            from agents.gemini_config import get_gemini_client, model_for

            thumb = pil_img.convert("RGB").copy()
            thumb.thumbnail((640, 640))
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=72)

            client = get_gemini_client()
            resp = client.models.generate_content(
                model=model_for("receipt_scanner"),
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    (
                        "This receipt/invoice photo has width > height (landscape). "
                        "Sometimes phone photos of vertical receipts are accidentally saved sideways. "
                        "How many degrees CLOCKWISE (0, 90, 180, or 270) must this image be rotated "
                        "so that the printed receipt text is upright and readable in normal reading orientation? "
                        "Reply with ONLY one number: 0, 90, 180, or 270."
                    ),
                ],
            )
            raw_txt = (resp.text or "").strip()
            m = re.search(r"\b(0|90|180|270)\b", raw_txt)
            if m:
                deg = int(m.group(1))
                logger.info(f"🔄 [Receipt Orientation Check] Landscape photo ({w}x{h}) -> rotate {deg}° CW")
                return deg
        except Exception as err:
            logger.debug(f"[DEBUG] Vision orientation check unavailable, falling back to heuristic: {err}")

    return _heuristic_landscape_rotation_degrees(pil_img)


def orient_landscape_receipt_photo(pil_img: Any, use_vision_model: bool = True) -> Any:
    """
    If a receipt photo has width > height, check its text orientation and rotate it
    into upright portrait orientation when needed.
    """
    w, h = pil_img.size
    if w <= h:
        return pil_img
    deg = detect_landscape_photo_rotation_degrees(pil_img, use_vision_model=use_vision_model)
    transpose_ns = getattr(Image, "Transpose", Image)
    if deg == 90:
        return pil_img.transpose(getattr(transpose_ns, "ROTATE_270"))
    if deg == 180:
        return pil_img.transpose(getattr(transpose_ns, "ROTATE_180"))
    if deg == 270:
        return pil_img.transpose(getattr(transpose_ns, "ROTATE_90"))
    return pil_img


def compress_receipt_image(
    raw_bytes: bytes,
    max_side: int = 1200,
    quality: int = 70,
    auto_orient: bool = True,
    use_vision_model: bool = True,
) -> Optional[bytes]:
    """
    Downscale and compress a receipt image (or first PDF page) into a compact JPEG
    so documents with many receipts stay lightweight while keeping text legible.
    For non-PDF photos where width > height, checks orientation and rotates sideways
    vertical receipts into upright portrait orientation.
    """
    if not raw_bytes:
        return None
    try:
        pdf_bytes = _extract_pdf_bytes_if_present(raw_bytes)
        is_pdf = pdf_bytes is not None
        pdf_page_count = 1
        if is_pdf:
            pil_img, pdf_page_count = _render_pdf_pages_stitched_to_pil(pdf_bytes)
            if pil_img is None:
                return None
        else:
            pil_img = Image.open(io.BytesIO(raw_bytes))
            pil_img = ImageOps.exif_transpose(pil_img)

        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            rgba = pil_img.convert("RGBA")
            bg = Image.new("RGB", rgba.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[3])
            pil_img = bg
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # Only check orientation on non-PDF photos where width > height
        if not is_pdf and auto_orient and pil_img.size[0] > pil_img.size[1]:
            pil_img = orient_landscape_receipt_photo(pil_img, use_vision_model=use_vision_model)

        w, h = pil_img.size
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        if is_pdf and pdf_page_count > 1:
            # For multi-page stitched PDFs, cap the width to max_side while allowing
            # proportional vertical height (up to max_side * min(pdf_page_count, 6)) so each page stays sharp.
            max_stitched_h = max_side * min(pdf_page_count, 6)
            scale = min(max_side / max(w, 1), max_stitched_h / max(h, 1), 1.0)
            if scale < 1.0:
                pil_img = pil_img.resize(
                    (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
                    resample=resample,
                )
        elif max(w, h) > max_side:
            pil_img.thumbnail((max_side, max_side), resample=resample)

        out = io.BytesIO()
        pil_img.save(out, format="JPEG", quality=quality, optimize=True, progressive=True)
        return out.getvalue()
    except Exception as err:
        logger.warning(f"⚠️ [Receipt Image Compression Notice] {err}")
        return None


def deduplicate_and_compress_proofs(
    raw_items: List[Any],
    max_side: Optional[int] = None,
    quality: Optional[int] = None,
    auto_orient: bool = True,
    use_vision_model: bool = True,
) -> List[bytes]:
    """
    Deduplicate proof attachments by SHA-256 and compress each unique receipt
    with adaptive resolution/quality based on the number of receipts.
    """
    unique_raw: List[bytes] = []
    seen_hashes: set[str] = set()
    for item in raw_items or []:
        raw_b = normalize_proof_bytes(item)
        if not raw_b:
            continue
        digest = hashlib.sha256(raw_b).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        unique_raw.append(raw_b)

    count = len(unique_raw)
    if max_side is None:
        max_side = 1080 if count > 15 else (1200 if count > 6 else 1350)
    if quality is None:
        quality = 68 if count > 15 else (72 if count > 6 else 76)

    compressed_list: List[bytes] = []
    seen_compressed_hashes: set[str] = set()
    for raw_b in unique_raw:
        comp_b = compress_receipt_image(
            raw_b,
            max_side=max_side,
            quality=quality,
            auto_orient=auto_orient,
            use_vision_model=use_vision_model,
        )
        if not comp_b:
            continue
        comp_digest = hashlib.sha256(comp_b).hexdigest()
        if comp_digest in seen_compressed_hashes:
            continue
        seen_compressed_hashes.add(comp_digest)
        compressed_list.append(comp_b)
    return compressed_list


def reorder_proofs_for_grouped_receipts(
    grouped_receipts: Optional[List[Dict[str, Any]]],
    session_images: Optional[List[Any]],
) -> List[Any]:
    """
    Order raw proof images in the exact same sequence as `grouped_receipts` so that
    Row 1..N in the Expenses Table corresponds 1-to-1 with Receipt_1..N in the Proofs section.
    """
    unique_session_proofs: List[bytes] = []
    seen_session_hashes: set[str] = set()
    for raw_item in session_images or []:
        b = normalize_proof_bytes(raw_item)
        if not b:
            continue
        h = hashlib.sha256(b).hexdigest()
        if h in seen_session_hashes:
            continue
        seen_session_hashes.add(h)
        unique_session_proofs.append(b)

    ordered: List[Any] = []
    used_session_indices: set[int] = set()

    for idx, item in enumerate(grouped_receipts or []):
        if not isinstance(item, dict):
            continue
        img_p = item.get("image_path")
        if img_p:
            b = normalize_proof_bytes(img_p)
            if b:
                ordered.append(b)
                continue
        orig_idx = item.get("_orig_idx")
        if orig_idx is None:
            att_idx = item.get("attachment_index")
            if att_idx is not None:
                try:
                    parsed = int(att_idx)
                    if parsed >= 1:
                        orig_idx = parsed - 1
                except (TypeError, ValueError):
                    pass
            if orig_idx is None:
                orig_idx = idx
        if isinstance(orig_idx, int) and 0 <= orig_idx < len(unique_session_proofs):
            ordered.append(unique_session_proofs[orig_idx])
            used_session_indices.add(orig_idx)

    for s_idx, raw_b in enumerate(unique_session_proofs):
        if s_idx not in used_session_indices:
            ordered.append(raw_b)

    return ordered


def _set_row_cells(row, item_num, cat, desc, sc, st):
    """Sets standard expense item row values and formatting."""
    row.cells[0].paragraphs[0].text = str(item_num)
    row.cells[1].paragraphs[0].text = str(cat or "")
    row.cells[2].paragraphs[0].text = str(desc or "")
    row.cells[3].paragraphs[0].text = str(sc or "")
    row.cells[4].paragraphs[0].text = str(st or "")

    for idx, cell in enumerate(row.cells):
        p = cell.paragraphs[0]
        p.alignment = (
            WD_ALIGN_PARAGRAPH.CENTER
            if idx in [0, 1]
            else (WD_ALIGN_PARAGRAPH.RIGHT if idx in [3, 4] else WD_ALIGN_PARAGRAPH.LEFT)
        )
        for r in p.runs:
            r.font.name = "Arial"
            r.font.size = Pt(9.5)


def generate_expense_report_docx(
    title: str,
    receipts_data: List[Dict[str, Any]],
    target_currency: str = "USD",
    exchange_rate: float = 1.0,
    rate_source: str = "Official Banking Exchange Rates",
    rate_url: str = "",
    approved_budget: Optional[str] = None,
    community_name: str = "Community",
    session_images: Optional[List[Any]] = None,
    output_path: Optional[str] = None,
    template_path: Optional[str] = None,
) -> bytes:
    """Generates a styled .docx expense report document from the 1-to-1 template."""
    if Document is None:
        raise RuntimeError("python-docx is not installed in the current environment.")

    use_existing_template = bool(template_path and os.path.exists(template_path))
    if not use_existing_template:
        default_tpl = os.path.join(os.path.dirname(__file__), "assets", "expense_report_template.docx")
        if os.path.exists(default_tpl):
            template_path = default_tpl
            use_existing_template = True

    if use_existing_template:
        doc = Document(template_path)
    else:
        doc = Document()

    receipts_data = group_and_sort_receipts(receipts_data)
    today_str = datetime.date.today().strftime("%d.%m.%Y")
    total_orig_str, total_target_str = calculate_receipt_totals(receipts_data, target_currency)

    # 1. Replace paragraph tags
    rate_bank_text = rate_url if rate_url else (f"({rate_source})" if rate_source and rate_source != "N/A" else "")
    for p in doc.paragraphs:
        if "{{TITLE}}" in p.text:
            p.text = p.text.replace("{{TITLE}}", title or "Expense Reimbursement Report")
            if p.runs:
                p.runs[0].font.name = "Arial"
                p.runs[0].font.size = Pt(18)
                p.runs[0].font.bold = True

        if "{{Current date}}" in p.text or "{{Bank link}}" in p.text:
            p.text = p.text.replace("{{Current date}}", today_str).replace("{{Bank link}}", rate_bank_text).strip()
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.italic = True

        if "{{EUR/USD}}" in p.text or "{{Current exchange rate}}" in p.text:
            rate_str = f"{exchange_rate:.4f}" if exchange_rate else "1.0000"
            p.text = (
                p.text.replace("{{EUR/USD}}", target_currency.upper())
                .replace("{{Current exchange rate}}", rate_str)
                .replace("{{Local Currency Code}}", "PLN")
            )
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.bold = True

    # 2. Populate Expenses Table (Table 0)
    if doc.tables:
        exp_table = doc.tables[0]
        n_items = len(receipts_data or [])

        if n_items > 0 and len(exp_table.rows) >= 4:
            # Row 1 is template
            item0 = receipts_data[0]
            _set_row_cells(
                exp_table.rows[1],
                1,
                item0.get("category", ""),
                item0.get("desc", ""),
                item0.get("sum_curr", ""),
                item0.get("sum_target", ""),
            )

            # Insert additional items
            for i in range(1, n_items):
                item = receipts_data[i]
                new_tr = copy.deepcopy(exp_table.rows[1]._tr)
                total_tr = exp_table.rows[-2]._tr
                total_tr.addprevious(new_tr)

            for i in range(1, n_items):
                item = receipts_data[i]
                _set_row_cells(
                    exp_table.rows[i + 1],
                    i + 1,
                    item.get("category", ""),
                    item.get("desc", ""),
                    item.get("sum_curr", ""),
                    item.get("sum_target", ""),
                )

            # Update Total Spent row
            tot_row = exp_table.rows[-2]
            tot_row.cells[3].paragraphs[0].text = total_orig_str
            tot_row.cells[4].paragraphs[0].text = total_target_str
            for idx in [3, 4]:
                p = tot_row.cells[idx].paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                for r in p.runs:
                    r.font.name = "Arial"
                    r.font.size = Pt(9.5)
                    r.font.bold = True

            # Update Approved Budget row
            bud_row = exp_table.rows[-1]
            bud_str = approved_budget or f"150.00 {target_currency.upper()}"
            bud_row.cells[4].paragraphs[0].text = bud_str
            p = bud_row.cells[4].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            for r in p.runs:
                r.font.name = "Arial"
                r.font.size = Pt(9.5)
                r.font.bold = True

    # 3. Collect, Reorder to match Grouped Table Rows, Deduplicate, and Compress Proof Images
    raw_proof_candidates = reorder_proofs_for_grouped_receipts(receipts_data, session_images)
    images_to_embed = deduplicate_and_compress_proofs(raw_proof_candidates)

    # 4. Handle {{PROOFS}}
    for p in list(doc.paragraphs):
        if "{{PROOFS}}" in p.text:
            if not images_to_embed:
                p.text = "Original receipts verified via Vision OCR."
                if p.runs:
                    p.runs[0].font.name = "Arial"
                    p.runs[0].font.size = Pt(9.5)
                    p.runs[0].font.italic = True
            else:
                p._element.getparent().remove(p._element)

    if images_to_embed:
        n_imgs = len(images_to_embed)
        if n_imgs == 1:
            try:
                p_img = doc.add_paragraph()
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p_img.paragraph_format.space_before = Pt(6)
                p_img.paragraph_format.space_after = Pt(6)
                run_img = p_img.add_run()
                run_img.add_picture(io.BytesIO(images_to_embed[0]), width=Inches(3.4))
            except Exception as e:
                logger.warning(f"⚠️ [DOCX Image Embed Error] {e}")
        else:
            # 2-column grid (2 receipts per row)
            cols = 2
            img_width = Inches(2.9)
            rows_count = (n_imgs + cols - 1) // cols
            grid_table = doc.add_table(rows=rows_count, cols=cols)
            grid_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for idx, img_bytes in enumerate(images_to_embed):
                try:
                    r_idx, c_idx = divmod(idx, cols)
                    cell = grid_table.rows[r_idx].cells[c_idx]
                    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                    p_img = cell.paragraphs[0]
                    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p_img.paragraph_format.space_before = Pt(4)
                    p_img.paragraph_format.space_after = Pt(4)
                    run_img = p_img.add_run()
                    run_img.add_picture(io.BytesIO(img_bytes), width=img_width)
                except Exception as e:
                    logger.warning(f"⚠️ [DOCX Grid Image Embed Error] {e}")

    # Output document
    doc_io = io.BytesIO()
    doc.save(doc_io)
    docx_bytes = doc_io.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(docx_bytes)
        logger.info(f"✅ [DOCX Generator] Successfully saved report to: {output_path}")

    return docx_bytes
