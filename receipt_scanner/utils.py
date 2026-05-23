import os
import tempfile
from pathlib import Path
from PIL import Image, ExifTags
import pypdfium2 as pdfium

def _auto_rotate_image(img_path: str) -> str:
    """
    Returns a path to an EXIF-corrected copy of the image if rotation is needed,
    otherwise returns the original path unchanged.
    The copy is written to a temp file and should be cleaned up by the caller.
    """
    try:
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
