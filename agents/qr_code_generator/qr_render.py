"""Rounded ("liquid") QR codes as one flat SVG path and a matching PNG.

Framework-independent: the ADK tool, the MCP server and tests all call :func:`build_qr`.

Geometry (in module units, quiet zone included):
- data modules are unit squares whose outer corners are rounded where both neighbours
  on that corner are light, so single modules become dots and runs become pills;
- concave corners between touching modules get a small fillet, so shapes flow together;
- the three finder "eyes" are a rounded ring plus a rounded centre.
Everything is emitted into a single SVG ``<path>`` (nonzero fill; the eye holes use the
opposite winding), so the file is one flat shape in one colour. The PNG is rasterised from
the same geometry with Pillow (4x supersampling), no native SVG renderer needed.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass

import segno
from PIL import Image, ImageDraw

HEX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
MAX_DATA_LENGTH = 2000
_SUPERSAMPLE = 4


@dataclass(frozen=True)
class QrStyle:
    color: str = "#000000"
    background: str = "#FFFFFF"
    transparent: bool = False
    eye_color: str | None = None  # None = same as ``color``
    radius: float = 0.5  # corner radius of data modules, 0..0.5 module
    fillet: float = 0.25  # concave fillet radius, 0..0.5 module
    margin: int = 4  # quiet zone in modules (the QR spec asks for 4)
    error: str = "m"  # l / m / q / h, boosted automatically when it fits the same size

    def validated(self) -> "QrStyle":
        for name in ("color", "background", "eye_color"):
            value = getattr(self, name)
            if value is not None and not HEX_COLOR.match(value):
                raise ValueError(f"{name} must be a hex colour like #1A73E8, got {value!r}")
        if self.error.lower() not in {"l", "m", "q", "h"}:
            raise ValueError("error must be one of L, M, Q, H")
        if not 0 <= self.radius <= 0.5 or not 0 <= self.fillet <= 0.5:
            raise ValueError("radius and fillet must be between 0 and 0.5")
        if not 0 <= self.margin <= 10:
            raise ValueError("margin must be between 0 and 10 modules")
        return self


@dataclass(frozen=True)
class QrResult:
    data: str
    svg: str
    png: bytes
    modules: int  # modules per side without the quiet zone
    version: int
    error: str


def normalize_link(text: str) -> str:
    """Trim the link and add https:// to a bare domain ("gdg.community.dev/x")."""
    value = (text or "").strip().strip("<>").strip()
    if not value:
        raise ValueError("The link is empty.")
    if len(value) > MAX_DATA_LENGTH:
        raise ValueError(f"The link is too long for a readable QR code (max {MAX_DATA_LENGTH} characters).")
    has_scheme = re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) and not re.match(r"^[^/:]+:\d+(/|$)", value)
    if not has_scheme and re.match(r"^(www\.)?[\w-]+(\.[\w-]+)+([/?#:].*)?$", value):
        value = "https://" + value
    return value


# --------------------------------------------------------------------------- geometry


def _is_finder(r: int, c: int, n: int) -> bool:
    return (r < 7 and c < 7) or (r < 7 and c >= n - 7) or (r >= n - 7 and c < 7)


def _fmt(v: float) -> str:
    text = f"{v:.3f}".rstrip("0").rstrip(".")
    return text if text not in {"-0", ""} else "0"


def _rounded_rect(x: float, y: float, w: float, h: float, radii: tuple[float, float, float, float], ccw: bool = False):
    """Subpath of a rectangle with per-corner radii (tl, tr, br, bl); ``ccw`` reverses the winding."""
    tl, tr, br, bl = radii
    if not ccw:
        cmds = [f"M{_fmt(x + tl)} {_fmt(y)}", f"H{_fmt(x + w - tr)}"]
        if tr:
            cmds.append(f"A{_fmt(tr)} {_fmt(tr)} 0 0 1 {_fmt(x + w)} {_fmt(y + tr)}")
        cmds.append(f"V{_fmt(y + h - br)}")
        if br:
            cmds.append(f"A{_fmt(br)} {_fmt(br)} 0 0 1 {_fmt(x + w - br)} {_fmt(y + h)}")
        cmds.append(f"H{_fmt(x + bl)}")
        if bl:
            cmds.append(f"A{_fmt(bl)} {_fmt(bl)} 0 0 1 {_fmt(x)} {_fmt(y + h - bl)}")
        cmds.append(f"V{_fmt(y + tl)}")
        if tl:
            cmds.append(f"A{_fmt(tl)} {_fmt(tl)} 0 0 1 {_fmt(x + tl)} {_fmt(y)}")
    else:
        cmds = [f"M{_fmt(x + tl)} {_fmt(y)}"]
        if tl:
            cmds.append(f"A{_fmt(tl)} {_fmt(tl)} 0 0 0 {_fmt(x)} {_fmt(y + tl)}")
        cmds.append(f"V{_fmt(y + h - bl)}")
        if bl:
            cmds.append(f"A{_fmt(bl)} {_fmt(bl)} 0 0 0 {_fmt(x + bl)} {_fmt(y + h)}")
        cmds.append(f"H{_fmt(x + w - br)}")
        if br:
            cmds.append(f"A{_fmt(br)} {_fmt(br)} 0 0 0 {_fmt(x + w)} {_fmt(y + h - br)}")
        cmds.append(f"V{_fmt(y + tr)}")
        if tr:
            cmds.append(f"A{_fmt(tr)} {_fmt(tr)} 0 0 0 {_fmt(x + w - tr)} {_fmt(y)}")
    cmds.append("Z")
    return "".join(cmds)


@dataclass(frozen=True)
class _Geometry:
    size: int  # total modules per side incl. quiet zone
    modules: list[tuple[int, int, tuple[float, float, float, float]]]  # x, y, corner radii
    fillets: list[tuple[int, int, int, int]]  # corner point (x, y) and direction (dx, dy) into the light cell
    eyes: list[tuple[int, int]]  # top-left of each 7x7 finder


def _geometry(matrix: list[list[bool]], style: QrStyle) -> _Geometry:
    n = len(matrix)
    m = style.margin

    def dark(r: int, c: int) -> bool:
        return 0 <= r < n and 0 <= c < n and matrix[r][c] and not _is_finder(r, c, n)

    modules = []
    fillets = []
    rad = style.radius
    for r in range(n):
        for c in range(n):
            if dark(r, c):
                up, down, left, right = dark(r - 1, c), dark(r + 1, c), dark(r, c - 1), dark(r, c + 1)
                radii = (
                    rad if not (up or left) else 0.0,
                    rad if not (up or right) else 0.0,
                    rad if not (down or right) else 0.0,
                    rad if not (down or left) else 0.0,
                )
                modules.append((c + m, r + m, radii))
            elif style.fillet and not (0 <= r < n and 0 <= c < n and _is_finder(r, c, n)):
                # Light cell: fillet each inner corner of an "L" (both edge-neighbours and the
                # diagonal on that corner are dark); a bare diagonal touch stays open.
                for dr, dc in ((-1, -1), (-1, 1), (1, 1), (1, -1)):
                    if dark(r + dr, c) and dark(r, c + dc) and dark(r + dr, c + dc):
                        cx = c + m + (1 if dc > 0 else 0)
                        cy = r + m + (1 if dr > 0 else 0)
                        fillets.append((cx, cy, -dc, -dr))
    eyes = [(m, m), (m + n - 7, m), (m, m + n - 7)]
    return _Geometry(size=n + 2 * m, modules=modules, fillets=fillets, eyes=eyes)


def _fillet_path(x: int, y: int, dx: int, dy: int, f: float) -> str:
    """Concave corner piece at (x, y) growing into the light cell towards (dx, dy)."""
    x1, y1 = x + dx * f, y
    x2, y2 = x, y + dy * f
    sweep = 0 if dx * dy > 0 else 1
    return f"M{_fmt(x)} {_fmt(y)}L{_fmt(x1)} {_fmt(y1)}A{_fmt(f)} {_fmt(f)} 0 0 {sweep} {_fmt(x2)} {_fmt(y2)}Z"


def _eye_paths(x: int, y: int) -> tuple[str, str]:
    ring = _rounded_rect(x, y, 7, 7, (2.4,) * 4) + _rounded_rect(x + 1, y + 1, 5, 5, (1.6,) * 4, ccw=True)
    ball = _rounded_rect(x + 2, y + 2, 3, 3, (1.0,) * 4)
    return ring, ball


# --------------------------------------------------------------------------- output


def _svg(geo: _Geometry, style: QrStyle, title: str) -> str:
    body = [_rounded_rect(x, y, 1, 1, radii) for x, y, radii in geo.modules]
    body += [_fillet_path(x, y, dx, dy, style.fillet) for x, y, dx, dy in geo.fillets]
    eyes = "".join("".join(_eye_paths(x, y)) for x, y in geo.eyes)
    eye_color = style.eye_color or style.color
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {geo.size} {geo.size}" '
        f'width="{geo.size * 10}" height="{geo.size * 10}" shape-rendering="geometricPrecision">',
        f"<title>{_xml(title)}</title>",
    ]
    if not style.transparent:
        parts.append(f'<rect width="{geo.size}" height="{geo.size}" fill="{style.background}"/>')
    if eye_color.lower() == style.color.lower():
        parts.append(f'<path fill="{style.color}" d="{"".join(body)}{eyes}"/>')
    else:
        parts.append(f'<path fill="{style.color}" d="{"".join(body)}"/>')
        parts.append(f'<path fill="{eye_color}" d="{eyes}"/>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _rgba(color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = color.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha


def _png(geo: _Geometry, style: QrStyle, size_px: int) -> bytes:
    unit = max(4, math.ceil(size_px * _SUPERSAMPLE / geo.size))
    big = geo.size * unit
    body = Image.new("L", (big, big), 0)
    eyes = Image.new("L", (big, big), 0)
    draw, eye_draw = ImageDraw.Draw(body), ImageDraw.Draw(eyes)

    def rrect(d: ImageDraw.ImageDraw, x, y, w, h, radius, fill):
        box = (round(x * unit), round(y * unit), round((x + w) * unit) - 1, round((y + h) * unit) - 1)
        d.rounded_rectangle(box, radius=round(radius * unit), fill=fill)

    for x, y, radii in geo.modules:
        x0, y0 = x * unit, y * unit
        draw.rectangle((x0, y0, x0 + unit - 1, y0 + unit - 1), fill=255)
        # (tl, tr, br, bl): cut the corner square, then add back a quarter of a circle
        for radius, (right, bottom) in zip(radii, ((0, 0), (1, 0), (1, 1), (0, 1))):
            if not radius:
                continue
            rp = round(radius * unit)
            cx0 = x0 + unit - rp if right else x0
            cy0 = y0 + unit - rp if bottom else y0
            draw.rectangle((cx0, cy0, cx0 + rp - 1, cy0 + rp - 1), fill=0)
            ex0 = x0 + unit - 2 * rp if right else x0
            ey0 = y0 + unit - 2 * rp if bottom else y0
            draw.ellipse((ex0, ey0, ex0 + 2 * rp - 1, ey0 + 2 * rp - 1), fill=255)
    f = style.fillet
    for x, y, dx, dy in geo.fillets:
        # square f x f in the corner of the light cell minus a circle of radius f centred f away
        x0, x1 = sorted((x, x + dx * f))
        y0, y1 = sorted((y, y + dy * f))
        draw.rectangle((round(x0 * unit), round(y0 * unit), round(x1 * unit) - 1, round(y1 * unit) - 1), fill=255)
        cx, cy = x + dx * f, y + dy * f
        draw.ellipse(
            (round((cx - f) * unit), round((cy - f) * unit), round((cx + f) * unit) - 1, round((cy + f) * unit) - 1),
            fill=0,
        )
    for x, y in geo.eyes:
        rrect(eye_draw, x, y, 7, 7, 2.4, 255)
        rrect(eye_draw, x + 1, y + 1, 5, 5, 1.6, 0)
        rrect(eye_draw, x + 2, y + 2, 3, 3, 1.0, 255)

    body = body.resize((size_px, size_px), Image.Resampling.LANCZOS)
    eyes = eyes.resize((size_px, size_px), Image.Resampling.LANCZOS)
    bg = (0, 0, 0, 0) if style.transparent else _rgba(style.background)
    image = Image.new("RGBA", (size_px, size_px), bg)
    image.paste(Image.new("RGBA", (size_px, size_px), _rgba(style.color)), mask=body)
    image.paste(Image.new("RGBA", (size_px, size_px), _rgba(style.eye_color or style.color)), mask=eyes)
    # Two colours plus anti-aliased edges fit a small palette: ~4x smaller files, same look.
    image = image.quantize(colors=32, method=Image.Quantize.FASTOCTREE)
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def build_qr(data: str, style: QrStyle | None = None, png_size: int = 1024) -> QrResult:
    """Encode ``data`` and return the rounded QR as SVG text and PNG bytes."""
    style = (style or QrStyle()).validated()
    if not 128 <= png_size <= 4096:
        raise ValueError("png_size must be between 128 and 4096 pixels")
    qr = segno.make(data, error=style.error.lower(), boost_error=True, micro=False)
    matrix = [[bool(v) for v in row] for row in qr.matrix]
    geo = _geometry(matrix, style)
    return QrResult(
        data=data,
        svg=_svg(geo, style, data),
        png=_png(geo, style, png_size),
        modules=len(matrix),
        version=int(qr.version),
        error=str(qr.error).upper(),
    )
