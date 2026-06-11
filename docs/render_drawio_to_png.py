"""Render a draw.io diagram to PNG using Pillow.

A pragmatic fallback for environments without draw.io desktop or a
headless X server (the snap's ``drawio -x`` export needs a display).
Parses each ``<mxCell>`` from the .drawio XML, draws the boxes at
their declared geometry with real font metrics — text is wrapped to
the box width, bold/italic map to the DejaVu face variants, dashed
strokes and rounded corners are honoured — and routes edges
orthogonally between the exit/entry points declared in the edge style.

Output is intentionally not pixel-identical to draw.io's own renderer —
it's a clean, readable preview suitable for GitHub rendering and code
review. To edit the diagram, use draw.io directly on the .drawio file;
this script regenerates the .png after edits.

Usage::

    python render_drawio_to_png.py RMACD_Runtime_Architecture.drawio
    # writes RMACD_Runtime_Architecture.drawio.png next to the input
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCALE = 2  # render at 2x for crisp text on GitHub
PAD = 40.0  # page margin in drawio units

_FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
_FACES = {
    (False, False): _FONT_DIR / "DejaVuSans.ttf",
    (True, False): _FONT_DIR / "DejaVuSans-Bold.ttf",
    (False, True): _FONT_DIR / "DejaVuSans-Oblique.ttf",
    (True, True): _FONT_DIR / "DejaVuSans-BoldOblique.ttf",
}


@dataclass
class Cell:
    id: str
    value: str
    style: dict[str, str]
    is_text_only: bool
    x: float
    y: float
    width: float
    height: float
    is_edge: bool
    source_id: str | None
    target_id: str | None


def parse_style(style: str | None) -> dict[str, str]:
    if not style:
        return {}
    out: dict[str, str] = {}
    for part in style.split(";"):
        if not part:
            continue
        if "=" in part:
            k, _, v = part.partition("=")
            out[k.strip()] = v.strip()
        else:
            out[part.strip()] = "1"  # unkeyed style shape (e.g. "rounded")
    return out


def parse_cells(drawio_path: Path) -> list[Cell]:
    tree = ET.parse(drawio_path)
    cells: list[Cell] = []
    for cell in tree.getroot().iter("mxCell"):
        cell_id = cell.get("id", "")
        if cell_id in {"0", "1"}:
            continue  # synthetic root cells
        raw_style = cell.get("style") or ""
        # ET already decodes XML character references; strip any HTML drawio
        # may embed when html=1 labels were edited in the app.
        value = (
            (cell.get("value") or "")
            .replace("<br>", "\n").replace("<br/>", "\n")
            .replace("&nbsp;", " ")
        )
        geom = cell.find("mxGeometry")
        g = (lambda k: float(geom.get(k) or 0)) if geom is not None else (lambda k: 0.0)
        cells.append(
            Cell(
                id=cell_id,
                value=value,
                style=parse_style(raw_style),
                is_text_only=raw_style.startswith("text"),
                x=g("x"), y=g("y"), width=g("width"), height=g("height"),
                is_edge=cell.get("edge") == "1",
                source_id=cell.get("source"),
                target_id=cell.get("target"),
            )
        )
    return cells


def color(value: str | None, default: str) -> str:
    if not value or value == "none":
        return default
    return value if value.startswith("#") else default


def font_for(style: dict[str, str]) -> ImageFont.FreeTypeFont:
    size = float(style.get("fontSize", "11"))
    fs = style.get("fontStyle", "0")
    bold, italic = fs in {"1", "3"}, fs in {"2", "3"}
    # Fall back through faces — oblique variants are not installed everywhere.
    for face in (_FACES[(bold, italic)], _FACES[(bold, False)], _FACES[(False, False)]):
        if face.exists():
            return ImageFont.truetype(str(face), int(round(size * SCALE)))
    return ImageFont.load_default(int(round(size * SCALE)))


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    """Wrap each hard line to max_width using real glyph metrics."""
    lines: list[str] = []
    for hard in text.split("\n"):
        if not hard:
            lines.append("")
            continue
        words, current = hard.split(" "), ""
        for word in words:
            trial = f"{current} {word}".strip()
            if font.getlength(trial) <= max_width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def dashed_line(draw: ImageDraw.ImageDraw, p1, p2, fill, width, dash=8 * SCALE) -> None:
    (x1, y1), (x2, y2) = p1, p2
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length == 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    while pos < length:
        end = min(pos + dash, length)
        draw.line(
            [(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)],
            fill=fill, width=width,
        )
        pos += dash * 2


def polyline(draw, points, fill, width, dashed) -> None:
    for p1, p2 in zip(points, points[1:]):
        if dashed:
            dashed_line(draw, p1, p2, fill, width)
        else:
            draw.line([p1, p2], fill=fill, width=width)


def arrow_head(draw, p_from, p_to, fill, size=7 * SCALE) -> None:
    (x1, y1), (x2, y2) = p_from, p_to
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 or 1.0
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    base = (x2 - ux * size, y2 - uy * size)
    left = (base[0] - uy * size * 0.5, base[1] + ux * size * 0.5)
    right = (base[0] + uy * size * 0.5, base[1] - ux * size * 0.5)
    draw.polygon([(x2, y2), left, right], fill=fill)


def render(drawio_path: Path, out_path: Path | None = None) -> Path:
    cells = parse_cells(drawio_path)
    by_id = {c.id: c for c in cells}
    boxes = [c for c in cells if not c.is_edge]

    max_x = max((c.x + c.width for c in boxes), default=1000.0)
    max_y = max((c.y + c.height for c in boxes), default=800.0)
    img_w = int(round((max_x + PAD * 2) * SCALE))
    img_h = int(round((max_y + PAD * 2) * SCALE))
    img = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(img)

    def px(v: float) -> float:
        return (v + PAD) * SCALE

    # ----- vertices ---------------------------------------------------------
    for c in boxes:
        x1, y1 = px(c.x), px(c.y)
        x2, y2 = px(c.x + c.width), px(c.y + c.height)
        if not c.is_text_only:
            fill = color(c.style.get("fillColor"), "#FFFFFF")
            stroke = color(c.style.get("strokeColor"), "#444444")
            sw = int(round(float(c.style.get("strokeWidth", "1")) * SCALE))
            fill_arg = None if c.style.get("fillColor") == "none" else fill
            if c.style.get("dashed") == "1":
                if fill_arg:
                    draw.rectangle([x1, y1, x2, y2], fill=fill_arg)
                for p1, p2 in [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
                               ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]:
                    dashed_line(draw, p1, p2, stroke, sw)
            elif c.style.get("rounded") == "1":
                draw.rounded_rectangle(
                    [x1, y1, x2, y2], radius=8 * SCALE,
                    fill=fill_arg, outline=stroke, width=sw,
                )
            else:
                draw.rectangle([x1, y1, x2, y2], fill=fill_arg, outline=stroke, width=sw)

        if not c.value:
            continue

        font = font_for(c.style)
        font_color = color(c.style.get("fontColor"), "#000000")
        inset = 8 * SCALE
        spacing_left = float(c.style.get("spacingLeft", "0")) * SCALE
        spacing_top = float(c.style.get("spacingTop", "0")) * SCALE
        avail = max((x2 - x1) - 2 * inset - spacing_left, 4 * SCALE)
        lines = wrap_text(c.value, font, avail)
        line_h = int(round(font.size * 1.25))
        block_h = line_h * len(lines)

        va = c.style.get("verticalAlign", "middle")
        if va == "top":
            ty = y1 + spacing_top + 2 * SCALE
        elif va == "bottom":
            ty = y2 - block_h - spacing_top - 2 * SCALE
        else:
            ty = (y1 + y2) / 2 - block_h / 2

        ha = c.style.get("align", "center")
        for line in lines:
            lw = font.getlength(line)
            if ha == "left":
                tx = x1 + inset + spacing_left
            elif ha == "right":
                tx = x2 - inset - lw
            else:
                tx = (x1 + x2) / 2 - lw / 2
            draw.text((tx, ty), line, font=font, fill=font_color)
            ty += line_h

    # ----- edges ------------------------------------------------------------
    for c in cells:
        if not c.is_edge:
            continue
        src, tgt = by_id.get(c.source_id or ""), by_id.get(c.target_id or "")
        if not src or not tgt:
            continue

        def anchor(box: Cell, xr: str | None, yr: str | None) -> tuple[float, float]:
            fx = float(xr) if xr is not None else 0.5
            fy = float(yr) if yr is not None else 0.5
            return (px(box.x + box.width * fx), px(box.y + box.height * fy))

        p1 = anchor(src, c.style.get("exitX"), c.style.get("exitY"))
        p2 = anchor(tgt, c.style.get("entryX"), c.style.get("entryY"))
        stroke = color(c.style.get("strokeColor"), "#444444")
        sw = int(round(float(c.style.get("strokeWidth", "1")) * SCALE))
        is_dashed = c.style.get("dashed") == "1"

        # Orthogonal elbow routing matching drawio defaults: when leaving
        # vertically and entering vertically, do V-H-V; when horizontal on
        # both ends, H-V-H; otherwise a straight segment.
        exit_vertical = c.style.get("exitY") in {"0", "1"}
        entry_vertical = c.style.get("entryY") in {"0", "1"}
        if p1[0] == p2[0] or p1[1] == p2[1]:
            points = [p1, p2]
        elif exit_vertical and entry_vertical:
            mid_y = (p1[1] + p2[1]) / 2
            points = [p1, (p1[0], mid_y), (p2[0], mid_y), p2]
        elif not exit_vertical and not entry_vertical:
            mid_x = (p1[0] + p2[0]) / 2
            points = [p1, (mid_x, p1[1]), (mid_x, p2[1]), p2]
        else:  # mixed: single elbow
            points = [p1, (p2[0], p1[1]) if exit_vertical is False else (p1[0], p2[1]), p2]

        polyline(draw, points, stroke, sw, is_dashed)
        if c.style.get("endArrow", "classic") != "none":
            arrow_head(draw, points[-2], points[-1], stroke)

    out = out_path or drawio_path.with_suffix(".drawio.png")
    img.save(out)
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <file.drawio>", file=sys.stderr)
        sys.exit(2)
    out = render(Path(sys.argv[1]))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
