"""Render a draw.io diagram to PNG using matplotlib.

A pragmatic fallback for environments without draw.io desktop or a
headless Chromium. Parses each ``<mxCell>`` from the .drawio XML,
positions the boxes on a figure at their declared geometry, then
renders edges as arrows between the centres of their source and
target boxes. Style attributes (fill/stroke colour, dashed lines,
font sizes) are extracted from the cell's ``style`` attribute when
present and applied to the matplotlib patch.

Output is intentionally not pixel-identical to draw.io's own
renderer — it's a clean, readable preview suitable for GitHub
rendering and code review. To edit the diagram, use draw.io directly
on the .drawio file; this script regenerates the .png after edits.

Usage::

    python render_drawio_to_png.py RMACD_Runtime_Architecture.drawio
    # writes RMACD_Runtime_Architecture.drawio.png next to the input
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch


@dataclass
class Cell:
    id: str
    value: str
    style: dict[str, str]
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
            # Unkeyed style shape (e.g. "rounded") — store as a flag.
            out[part.strip()] = "1"
    return out


def parse_cells(drawio_path: Path) -> list[Cell]:
    tree = ET.parse(drawio_path)
    root = tree.getroot()
    cells: list[Cell] = []
    for cell in root.iter("mxCell"):
        cell_id = cell.get("id", "")
        if cell_id in {"0", "1"}:
            continue  # synthetic root cells
        value = (cell.get("value") or "").replace("&#10;", "\n").replace(
            "&lt;", "<"
        ).replace("&gt;", ">").replace("&amp;", "&")
        style = parse_style(cell.get("style"))
        is_edge = cell.get("edge") == "1"
        source_id = cell.get("source")
        target_id = cell.get("target")
        x = y = width = height = 0.0
        geom = cell.find("mxGeometry")
        if geom is not None:
            x = float(geom.get("x") or 0)
            y = float(geom.get("y") or 0)
            width = float(geom.get("width") or 0)
            height = float(geom.get("height") or 0)
        cells.append(
            Cell(
                id=cell_id,
                value=value,
                style=style,
                x=x,
                y=y,
                width=width,
                height=height,
                is_edge=is_edge,
                source_id=source_id,
                target_id=target_id,
            )
        )
    return cells


def hex_or_default(color: str | None, default: str) -> str:
    if not color or color == "none":
        return default
    if color.startswith("#"):
        return color
    return default


def render(drawio_path: Path, out_path: Path | None = None, dpi: int = 100) -> Path:
    cells = parse_cells(drawio_path)
    by_id = {c.id: c for c in cells}

    # Page extents from the largest declared coordinates
    max_x = max((c.x + c.width for c in cells if not c.is_edge), default=1000.0)
    max_y = max((c.y + c.height for c in cells if not c.is_edge), default=800.0)
    pad = 40.0
    fig_w = (max_x + pad * 2) / 100.0
    fig_h = (max_y + pad * 2) / 100.0

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)
    ax.set_xlim(0, max_x + pad * 2)
    ax.set_ylim(0, max_y + pad * 2)
    ax.invert_yaxis()  # drawio y grows downward
    ax.set_aspect("equal")
    ax.axis("off")

    # Draw vertices first
    for c in cells:
        if c.is_edge:
            continue
        fill = hex_or_default(c.style.get("fillColor"), "#FFFFFF")
        stroke = hex_or_default(c.style.get("strokeColor"), "#444444")
        stroke_width = float(c.style.get("strokeWidth", "1"))
        dashed = c.style.get("dashed") == "1"
        rounded = c.style.get("rounded") == "1"
        font_size = float(c.style.get("fontSize", "11"))
        font_color = hex_or_default(c.style.get("fontColor"), "#000000")
        is_italic = c.style.get("fontStyle", "0") in {"2", "3"}
        is_bold = c.style.get("fontStyle", "0") in {"1", "3"}

        # Boxes with no fillColor and stroke=none act as label-only cells;
        # skip the rectangle for those.
        has_box = c.style.get("fillColor") != "none" or stroke != "#444444"
        if has_box and (fill != "none" or stroke != "none"):
            boxstyle = "round,pad=0,rounding_size=8" if rounded else "square,pad=0"
            patch = patches.FancyBboxPatch(
                (c.x + pad, c.y + pad),
                c.width,
                c.height,
                boxstyle=boxstyle,
                linewidth=stroke_width,
                edgecolor=stroke,
                facecolor=fill,
                linestyle="--" if dashed else "-",
            )
            ax.add_patch(patch)

        if c.value:
            verticalalignment = c.style.get("verticalAlign", "middle")
            va = {"top": "top", "middle": "center", "bottom": "bottom"}.get(
                verticalalignment, "center"
            )
            align = c.style.get("align", "center")
            ha = {"left": "left", "center": "center", "right": "right"}.get(
                align, "center"
            )
            spacing_top = float(c.style.get("spacingTop", "0"))
            spacing_left = float(c.style.get("spacingLeft", "0"))

            text_x = c.x + pad + (
                spacing_left
                if ha == "left"
                else c.width - spacing_left
                if ha == "right"
                else c.width / 2
            )
            text_y = c.y + pad + (
                spacing_top
                if va == "top"
                else c.height - spacing_top
                if va == "bottom"
                else c.height / 2
            )
            weight = "bold" if is_bold else "normal"
            style_val = "italic" if is_italic else "normal"
            ax.text(
                text_x,
                text_y,
                c.value,
                ha=ha,
                va=va,
                fontsize=font_size,
                color=font_color,
                fontweight=weight,
                fontstyle=style_val,
                wrap=True,
            )

    # Draw edges
    for c in cells:
        if not c.is_edge:
            continue
        src = by_id.get(c.source_id or "")
        tgt = by_id.get(c.target_id or "")
        if not src or not tgt:
            continue

        # Compute edge endpoints from exit/entry style ratios when present,
        # else use box centres.
        def _point(box: Cell, x_ratio_key: str, y_ratio_key: str) -> tuple[float, float]:
            xr = c.style.get(x_ratio_key)
            yr = c.style.get(y_ratio_key)
            if xr is not None and yr is not None:
                return (
                    box.x + pad + box.width * float(xr),
                    box.y + pad + box.height * float(yr),
                )
            return (box.x + pad + box.width / 2, box.y + pad + box.height / 2)

        x1, y1 = _point(src, "exitX", "exitY")
        x2, y2 = _point(tgt, "entryX", "entryY")
        stroke_width = float(c.style.get("strokeWidth", "1"))
        stroke = hex_or_default(c.style.get("strokeColor"), "#444444")
        dashed = c.style.get("dashed") == "1"
        arrow = FancyArrowPatch(
            (x1, y1),
            (x2, y2),
            arrowstyle="-|>" if c.style.get("endArrow", "classic") != "none" else "-",
            mutation_scale=12,
            linewidth=stroke_width,
            color=stroke,
            linestyle="--" if dashed else "-",
            shrinkA=2,
            shrinkB=2,
        )
        ax.add_patch(arrow)

    out = out_path or drawio_path.with_suffix(".drawio.png")
    plt.savefig(out, bbox_inches="tight", dpi=dpi, facecolor="white")
    plt.close(fig)
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(f"usage: {sys.argv[0]} <file.drawio>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    out = render(path)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()


# Pyflakes: re is reserved for future style-string parsing extensions.
_ = re, Any
