"""
Standalone DOCX Expense Report Generator.
Builds professional Microsoft Word / Google Docs compatible expense reports
with styled tables, exchange rate citations, and embedded receipt image proofs.
"""

import datetime
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from docx import Document
    from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement, parse_xml
    from docx.oxml.ns import nsdecls, qn
    from docx.shared import Inches, Pt, RGBColor
except ImportError:
    Document = None
    WD_TABLE_ALIGNMENT = None
    WD_ALIGN_PARAGRAPH = None
    WD_ALIGN_VERTICAL = None
    OxmlElement = None
    parse_xml = None
    nsdecls = None
    qn = None
    Inches = None
    Pt = None
    RGBColor = None

from PIL import Image, ImageOps


def _set_cell_background(cell, hex_color: str):
    """Sets background shading of a table cell."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def _set_cell_margins(cell, top: int = 120, bottom: int = 120, left: int = 150, right: int = 150):
    """Sets cell padding in twentieths of a point (dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for margin_name, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{margin_name}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def _set_table_borders(table, color_hex: str = "E2E8F0"):
    """Applies subtle border lines to table."""
    tblPr = table._tbl.tblPr
    borders_xml = f"""
    <w:tblBorders {nsdecls("w")}>
        <w:top w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="{color_hex}"/>
        <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
        <w:insideV w:val="none"/>
        <w:left w:val="none"/>
        <w:right w:val="none"/>
    </w:tblBorders>
    """
    tblPr.append(parse_xml(borders_xml))


def generate_expense_report_docx(
    title: str,
    receipts_data: List[Dict[str, Any]],
    target_currency: str = "USD",
    exchange_rate: float = 1.0,
    rate_source: str = "Official Banking Exchange Rates",
    rate_url: str = "",
    approved_budget: str = "",
    community_name: str = "Community",
    session_images: Optional[List[bytes]] = None,
    output_path: Optional[str] = None,
    template_path: Optional[str] = None,
) -> bytes:
    """Generates a styled .docx expense report document.

    If a valid `template_path` is provided, the template is loaded and its
    placeholders, metadata table, expenses table, and proof sections are
    populated with the recognized receipts data.
    """
    if Document is None:
        raise RuntimeError("python-docx is not installed in the current environment.")

    # Base Color Palette & Theme Tokens
    PRIMARY_COLOR = RGBColor(26, 86, 219)  # #1A56DB Community Blue
    TEXT_MAIN = RGBColor(15, 23, 42)  # #0F172A
    TEXT_MUTED = RGBColor(100, 116, 139)  # #64748B
    HEADER_BG_HEX = "F1F5F9"  # Slate-100
    ALT_ROW_BG_HEX = "F8FAFC"  # Slate-50

    col_widths = [Inches(0.4), Inches(1.5), Inches(2.6), Inches(1.2), Inches(1.2)]
    today_str = datetime.date.today().strftime("%d.%m.%Y")
    rate_display = (
        f"1 {target_currency.upper()} = {exchange_rate:.4f} PLN"
        if target_currency.upper() != "PLN"
        else "1.00 (Base PLN)"
    )

    use_existing_template = bool(template_path and os.path.exists(template_path))

    if use_existing_template:
        doc = Document(template_path)
    else:
        doc = Document()
        section = doc.sections[0]
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # 1. Update Title and Branding Header
    if use_existing_template and len(doc.paragraphs) >= 2:
        # Paragraph 0: Brand
        doc.paragraphs[0].text = ""
        r_brand = doc.paragraphs[0].add_run(f"{community_name.upper()} • COMMUNITY AI STUDIO")
        r_brand.font.name = "Arial"
        r_brand.font.size = Pt(9.5)
        r_brand.font.bold = True
        r_brand.font.color.rgb = PRIMARY_COLOR

        # Paragraph 1: Title
        doc.paragraphs[1].text = ""
        r_title = doc.paragraphs[1].add_run(title or "Expense Reimbursement Report")
        r_title.font.name = "Arial"
        r_title.font.size = Pt(20)
        r_title.font.bold = True
        r_title.font.color.rgb = TEXT_MAIN
    elif not use_existing_template:
        p_brand = doc.add_paragraph()
        p_brand.paragraph_format.space_after = Pt(2)
        r_brand = p_brand.add_run(f"{community_name.upper()} • COMMUNITY AI STUDIO")
        r_brand.font.name = "Arial"
        r_brand.font.size = Pt(9.5)
        r_brand.font.bold = True
        r_brand.font.color.rgb = PRIMARY_COLOR

        p_title = doc.add_paragraph()
        p_title.paragraph_format.space_after = Pt(14)
        r_title = p_title.add_run(title or "Expense Reimbursement Report")
        r_title.font.name = "Arial"
        r_title.font.size = Pt(20)
        r_title.font.bold = True
        r_title.font.color.rgb = TEXT_MAIN

    # 2. Metadata Grid (Table 0)
    meta_items = [
        ("Report Date:", today_str, "Target Currency:", target_currency.upper()),
        ("Exchange Rate:", rate_display, "Rate Source:", rate_source),
        ("Approved Budget:", approved_budget or "Standard Event Allocation", "Status:", "Ready for Reimbursement"),
    ]

    if use_existing_template and len(doc.tables) >= 1:
        meta_table = doc.tables[0]
    else:
        meta_table = doc.add_table(rows=3, cols=2)
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        meta_table.autofit = False
        _set_table_borders(meta_table, "E2E8F0")

    for row_idx, (k1, v1, k2, v2) in enumerate(meta_items):
        if row_idx < len(meta_table.rows):
            row = meta_table.rows[row_idx]
            _set_cell_margins(row.cells[0], top=60, bottom=60, left=80, right=80)
            _set_cell_margins(row.cells[1], top=60, bottom=60, left=80, right=80)

            # Left Column
            row.cells[0].text = ""
            p1 = row.cells[0].paragraphs[0]
            p1.paragraph_format.space_after = Pt(0)
            r_k1 = p1.add_run(f"{k1} ")
            r_k1.font.name = "Arial"
            r_k1.font.size = Pt(9.5)
            r_k1.font.bold = True
            r_k1.font.color.rgb = TEXT_MUTED
            r_v1 = p1.add_run(str(v1))
            r_v1.font.name = "Arial"
            r_v1.font.size = Pt(9.5)
            r_v1.font.color.rgb = TEXT_MAIN

            # Right Column
            row.cells[1].text = ""
            p2 = row.cells[1].paragraphs[0]
            p2.paragraph_format.space_after = Pt(0)
            r_k2 = p2.add_run(f"{k2} ")
            r_k2.font.name = "Arial"
            r_k2.font.size = Pt(9.5)
            r_k2.font.bold = True
            r_k2.font.color.rgb = TEXT_MUTED
            r_v2 = p2.add_run(str(v2))
            r_v2.font.name = "Arial"
            r_v2.font.size = Pt(9.5)
            r_v2.font.color.rgb = TEXT_MAIN

    # 3. Itemized Expenses Table (Table 1)
    if use_existing_template and len(doc.tables) >= 2:
        table = doc.tables[1]
        # Remove sample template rows (keep only header row)
        while len(table.rows) > 1:
            table._tbl.remove(table.rows[1]._tr)
    else:
        if not use_existing_template:
            doc.add_paragraph().paragraph_format.space_after = Pt(8)
            p_sec1 = doc.add_paragraph()
            p_sec1.paragraph_format.space_before = Pt(12)
            p_sec1.paragraph_format.space_after = Pt(6)
            r_sec1 = p_sec1.add_run("1. Itemized Expenses & Proofs")
            r_sec1.font.name = "Arial"
            r_sec1.font.size = Pt(13)
            r_sec1.font.bold = True
            r_sec1.font.color.rgb = TEXT_MAIN

        table = doc.add_table(rows=1, cols=5)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        _set_table_borders(table, "CBD5E1")

    # Format Header Row
    headers = ["#", "Category", "Description", "Original Sum", f"Sum ({target_currency.upper()})"]
    header_row = table.rows[0]
    header_row._tr.get_or_add_trPr().append(parse_xml(f"<w:tblHeader {nsdecls('w')}/>"))
    for idx, (cell, h_text) in enumerate(zip(header_row.cells, headers)):
        cell.width = col_widths[idx]
        _set_cell_background(cell, HEADER_BG_HEX)
        _set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        cell.text = ""
        p = cell.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        if idx in [0, 3, 4]:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if idx > 2 else WD_ALIGN_PARAGRAPH.CENTER
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        r = p.add_run(h_text)
        r.font.name = "Arial"
        r.font.size = Pt(9.5)
        r.font.bold = True
        r.font.color.rgb = TEXT_MAIN

    # Populate Data Rows
    total_target_amount = 0.0
    totals_by_curr: Dict[str, float] = {}

    for row_idx, item in enumerate(receipts_data or []):
        row = table.add_row()
        bg_hex = ALT_ROW_BG_HEX if row_idx % 2 == 1 else "FFFFFF"

        cat = item.get("category") or "General Expense"
        desc = item.get("desc") or f"Receipt #{row_idx + 1}"
        sum_curr = item.get("sum_curr") or item.get("sum_pln") or "0.00 PLN"
        sum_target = item.get("sum_target") or item.get("sum_usd") or f"0.00 {target_currency.upper()}"

        try:
            val_t = float(sum_target.split()[0].replace(",", ""))
            total_target_amount += val_t
        except Exception:
            pass

        try:
            parts = sum_curr.split()
            val_c = float(parts[0].replace(",", ""))
            c_code = parts[1] if len(parts) > 1 else "PLN"
            totals_by_curr[c_code] = totals_by_curr.get(c_code, 0.0) + val_c
        except Exception:
            pass

        cells_data = [
            (str(row_idx + 1), WD_ALIGN_PARAGRAPH.CENTER, False),
            (cat, WD_ALIGN_PARAGRAPH.LEFT, False),
            (desc, WD_ALIGN_PARAGRAPH.LEFT, False),
            (sum_curr, WD_ALIGN_PARAGRAPH.RIGHT, False),
            (sum_target, WD_ALIGN_PARAGRAPH.RIGHT, True),
        ]

        for col_idx, (text_val, align, is_bold) in enumerate(cells_data):
            cell = row.cells[col_idx]
            cell.width = col_widths[col_idx]
            _set_cell_background(cell, bg_hex)
            _set_cell_margins(cell, top=80, bottom=80, left=100, right=100)
            cell.text = ""
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.alignment = align
            r = p.add_run(text_val)
            r.font.name = "Arial"
            r.font.size = Pt(9.5)
            r.font.bold = is_bold
            r.font.color.rgb = TEXT_MAIN

    # Format Totals Row
    totals_row = table.add_row()
    for col_idx in range(5):
        cell = totals_row.cells[col_idx]
        cell.width = col_widths[col_idx]
        _set_cell_background(cell, HEADER_BG_HEX)
        _set_cell_margins(cell, top=100, bottom=100, left=100, right=100)
        cell.text = ""

    p_tot_label = totals_row.cells[2].paragraphs[0]
    p_tot_label.paragraph_format.space_after = Pt(0)
    p_tot_label.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_tot_label = p_tot_label.add_run("TOTAL REIMBURSEMENT:")
    r_tot_label.font.name = "Arial"
    r_tot_label.font.size = Pt(10)
    r_tot_label.font.bold = True
    r_tot_label.font.color.rgb = PRIMARY_COLOR

    orig_tot_str = ", ".join(f"{amt:.2f} {curr}" for curr, amt in totals_by_curr.items()) if totals_by_curr else "—"
    p_tot_orig = totals_row.cells[3].paragraphs[0]
    p_tot_orig.paragraph_format.space_after = Pt(0)
    p_tot_orig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_tot_orig = p_tot_orig.add_run(orig_tot_str)
    r_tot_orig.font.name = "Arial"
    r_tot_orig.font.size = Pt(9.5)
    r_tot_orig.font.bold = True

    p_tot_target = totals_row.cells[4].paragraphs[0]
    p_tot_target.paragraph_format.space_after = Pt(0)
    p_tot_target.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_tot_target = p_tot_target.add_run(f"{total_target_amount:.2f} {target_currency.upper()}")
    r_tot_target.font.name = "Arial"
    r_tot_target.font.size = Pt(10.5)
    r_tot_target.font.bold = True
    r_tot_target.font.color.rgb = PRIMARY_COLOR

    # 4. Embedded Receipt Images / Proofs Section
    images_to_embed: List[bytes] = []

    if session_images:
        images_to_embed.extend(session_images)

    for item in receipts_data or []:
        img_p = item.get("image_path")
        if img_p and os.path.exists(img_p):
            try:
                with open(img_p, "rb") as f:
                    images_to_embed.append(f.read())
            except Exception as e:
                print(f"[WARNING] Could not read image file {img_p}: {e}")

    # Remove template placeholder paragraph if images exist
    if use_existing_template and images_to_embed:
        for p in list(doc.paragraphs):
            if "Original receipts verified via Vision OCR." in p.text:
                p._element.getparent().remove(p._element)

    if not use_existing_template:
        doc.add_paragraph().paragraph_format.space_after = Pt(12)
        p_sec2 = doc.add_paragraph()
        p_sec2.paragraph_format.space_before = Pt(16)
        p_sec2.paragraph_format.space_after = Pt(6)
        r_sec2 = p_sec2.add_run("2. Attached Document Proofs")
        r_sec2.font.name = "Arial"
        r_sec2.font.size = Pt(13)
        r_sec2.font.bold = True
        r_sec2.font.color.rgb = TEXT_MAIN

    if not images_to_embed and not use_existing_template:
        p_no_img = doc.add_paragraph()
        r_no = p_no_img.add_run("Original receipts verified via Vision OCR.")
        r_no.font.name = "Arial"
        r_no.font.size = Pt(9.5)
        r_no.font.italic = True
        r_no.font.color.rgb = TEXT_MUTED
    elif images_to_embed:
        for idx, raw_img in enumerate(images_to_embed):
            try:
                img_bytes = raw_img
                if isinstance(img_bytes, str):
                    import base64

                    try:
                        img_bytes = base64.b64decode(img_bytes)
                    except Exception:
                        continue
                pil_img = Image.open(io.BytesIO(img_bytes))
                pil_img = ImageOps.exif_transpose(pil_img)

                if pil_img.mode in ("RGBA", "P"):
                    pil_img = pil_img.convert("RGB")

                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG", quality=90)
                buffer.seek(0)

                p_cap = doc.add_paragraph()
                p_cap.paragraph_format.space_before = Pt(10)
                p_cap.paragraph_format.space_after = Pt(4)
                r_cap = p_cap.add_run(f"Proof #{idx + 1}")
                r_cap.font.name = "Arial"
                r_cap.font.size = Pt(10)
                r_cap.font.bold = True
                r_cap.font.color.rgb = TEXT_MUTED

                p_img = doc.add_paragraph()
                p_img.paragraph_format.space_after = Pt(12)
                p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run_img = p_img.add_run()
                run_img.add_picture(buffer, width=Inches(min(5.2, pil_img.width / 150)))
            except Exception as img_err:
                print(f"[WARNING] Failed to embed proof image #{idx + 1}: {img_err}")

    # Output to buffer or file
    out_buf = io.BytesIO()
    doc.save(out_buf)
    docx_bytes = out_buf.getvalue()

    if output_path:
        out_file = Path(output_path).expanduser().resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(docx_bytes)
        print(f"✅ [DOCX Generator] Successfully saved report to: {out_file}")

    return docx_bytes
