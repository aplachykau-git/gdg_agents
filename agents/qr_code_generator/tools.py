"""Tool of the QR code generator agent: rounded QR as a flat SVG plus a PNG."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from agents.common import ui_payloads

from .qr_render import QrResult, QrStyle, build_qr, normalize_link

logger = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _slug(link: str) -> str:
    parsed = urlparse(link)
    base = (parsed.netloc + parsed.path) if parsed.netloc else link
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()[:40]
    return slug or "link"


def _publish(path: Path, content_type: str) -> str:
    """Public URL of a generated file: Cloud Storage when configured, else the local /results/ route."""
    if os.getenv("GCS_BUCKET_NAME") or os.getenv("K_SERVICE"):
        from agents.common.storage import upload_file_to_storage

        url = upload_file_to_storage(str(path), f"qr_codes/{path.name}", content_type=content_type)
        if url:
            return url
    return f"/results/{path.name}"


def save_qr(result: QrResult, style: QrStyle, out_dir: Path = RESULTS_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{result.data}|{style}".encode()).hexdigest()[:8]
    stem = f"qr_{_slug(result.data)}_{digest}"
    svg_path, png_path = out_dir / f"{stem}.svg", out_dir / f"{stem}.png"
    svg_path.write_text(result.svg, encoding="utf-8")
    png_path.write_bytes(result.png)
    return {"svg": svg_path, "png": png_path}


def generate_qr_code(
    link: str,
    color: str = "",
    background: str = "",
    eye_color: str = "",
    transparent_background: bool = False,
    png_size: int = 1024,
) -> dict:
    """Create a rounded QR code for a link as one flat vector SVG and a PNG, and show it as a card.

    Call once per link. Afterwards reply with one short sentence; the card already has the
    preview and the SVG / PNG downloads, so never paste file contents or long URLs.

    Args:
        link: The link or text to encode, e.g. "https://gdg.community.dev/gdg-krakow/". A bare
            domain gets https:// added.
        color: Hex colour of the modules, e.g. "#1A73E8". Empty = black.
        background: Hex background colour. Empty = white.
        eye_color: Hex colour of the three corner "eyes". Empty = same as color.
        transparent_background: True for a PNG/SVG without background (for placing on designs).
        png_size: PNG width and height in pixels (128-4096). Default 1024.
    """
    try:
        data = normalize_link(link)
        style = QrStyle(
            color=color.strip() or "#000000",
            background=background.strip() or "#FFFFFF",
            eye_color=eye_color.strip() or None,
            transparent=bool(transparent_background),
        )
        result = build_qr(data, style, png_size=int(png_size or 1024))
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    paths = save_qr(result, style)
    svg_url = _publish(paths["svg"], "image/svg+xml")
    png_url = _publish(paths["png"], "image/png")
    logger.info("QR code for %s saved to %s", data, paths["svg"].parent)
    return {
        "status": "success",
        "link": data,
        "svg_url": svg_url,
        "png_url": png_url,
        "qr_version": result.version,
        "error_correction": result.error,
        "message": "The QR card with SVG and PNG downloads is shown to the user.",
        "ui": ui_payloads.qr_code(
            data,
            svg_url=svg_url,
            png_url=png_url,
            filename=paths["svg"].stem,
            color=style.color,
            background=style.background,
            transparent=style.transparent,
        ),
    }
