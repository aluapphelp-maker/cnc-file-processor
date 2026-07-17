"""Punching DFT generation (contour tool path + nibble/overlap calculation).

Two capabilities:

1. **Faithful contour path** — emit `[300]` ``LINES`` with the reverse-engineered
   meta encoding (direction code + slope + exact length + contour tool id 15),
   producing a re-parseable punching DFT via :class:`core.dft_generator.DFTGenerator`.

2. **Nibble overlap calculation** — for a round/shaped tool, compute the sequence
   of overlapping hit centres needed to cut a line. This is the "tools overlap to
   form the cut line" behaviour from the factory brief. Hits can be emitted as
   `[300]` ``CIRCLES`` (Ø matches the factory Ø3 round-tool convention).

Note: factory punch `[300]` bodies are contour cuts (tool 15), identical to laser;
overlapping nibble hits are provided as a modelled capability + utility, validated
by geometry (spacing ≤ tool diameter), not by byte-for-byte factory match.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from core.dft_generator import DFTGenerator, default_line_params
from core.geometry import Line, Point
from core.models import DFTFile, DFTLine, GeometrySection
from core.tool_analysis import encode_direction

CONTOUR_TOOL_ID = 15
ROUND_TOOL_DIAMETER = 3.0


def _fmt(value: float) -> str:
    text = f"{value:.5f}".rstrip("0").rstrip(".")
    return text if text and text != "-0" else "0"


def _toolpath_lines(origin_offset: float) -> list[str]:
    zeros = " ".join(["0.000000"] * 11)
    off = f"{origin_offset:.6f}"
    return [
        f"3DToolPathPoint1 = {off} {zeros}",
        f"3DToolPathPoint2 = {off} {zeros}",
    ]


def segment_meta_lines(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    tool_id: int = CONTOUR_TOOL_ID,
    origin_offset: float = 0.0,
) -> list[str]:
    """Build the 3 meta lines (dir/slope/length + 2 tool-path points) for a LINES entity."""
    dx, dy = x2 - x1, y2 - y1
    code, slope = encode_direction(dx, dy)
    length = math.hypot(dx, dy)
    meta = f"{code} {_fmt(slope)} {_fmt(length)} 0 {tool_id} 0"
    return [meta, *_toolpath_lines(origin_offset)]


@dataclass
class NibbleHit:
    x: float
    y: float


def nibble_positions(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    tool_diameter: float = ROUND_TOOL_DIAMETER,
    overlap: float = 0.2,
) -> list[NibbleHit]:
    """Overlapping round-tool hit centres to punch a line segment.

    ``overlap`` is the fraction of the tool diameter shared between consecutive
    hits (0 = touching, 0.2 = 20% overlap). Consecutive hit spacing is always
    ``<= tool_diameter`` so the material between hits is removed.
    """
    if tool_diameter <= 0:
        raise ValueError("tool_diameter must be > 0")
    if not (0.0 <= overlap < 1.0):
        raise ValueError("overlap must be in [0, 1)")

    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length == 0:
        return [NibbleHit(x1, y1)]

    step = tool_diameter * (1.0 - overlap)
    n = max(1, math.ceil(length / step))
    return [NibbleHit(x1 + (i / n) * dx, y1 + (i / n) * dy) for i in range(n + 1)]


def _circle_lines(hits: list[NibbleHit], *, diameter: float, tool_id: int, origin_offset: float) -> list[str]:
    radius = diameter / 2.0
    lines: list[str] = []
    for hit in hits:
        lines.append(f"{_fmt(hit.x)} {_fmt(hit.y)} {_fmt(radius)} {tool_id} 0 3 0 0 0 -1 0")
        lines.extend(_toolpath_lines(origin_offset))
    return lines


def _segments_to_dftlines(segments: list[Line], origin_offset: float) -> list[DFTLine]:
    out: list[DFTLine] = []
    for seg in segments:
        out.append(
            DFTLine(
                x1=seg.start.x,
                y1=seg.start.y,
                x2=seg.end.x,
                y2=seg.end.y,
                params=default_line_params(),
                meta_lines=segment_meta_lines(
                    seg.start.x, seg.start.y, seg.end.x, seg.end.y, origin_offset=origin_offset
                ),
            )
        )
    return out


def generate_punching_dft(
    segments: list[Line],
    *,
    width: float,
    height: float,
    material: str = "YWL_HLB_V3",
    origin_offset: float = 0.0,
    holes: list[tuple[float, float]] | None = None,
    hole_diameter: float = ROUND_TOOL_DIAMETER,
) -> DFTFile:
    """Generate a punching DFTFile from contour segments (+ optional round holes)."""
    gen = DFTGenerator("punching")
    dft = gen.generate(
        _segments_to_dftlines(segments, origin_offset),
        width=width,
        height=height,
        material=material,
        origin_offset=origin_offset,
    )

    # Build the [300] body explicitly so we can add CIRCLES for holes.
    geo = dft.geometry
    body: list[str] = ["LINES", str(len(geo.lines))]
    for seg in geo.lines:
        body.append(
            " ".join([_fmt(seg.x1), _fmt(seg.y1), _fmt(seg.x2), _fmt(seg.y2), *seg.params])
        )
        body.extend(seg.meta_lines)

    hole_hits = [NibbleHit(x, y) for (x, y) in (holes or [])]
    body.extend(["POINTS", "0"])
    body.append("CIRCLES")
    body.append(str(len(hole_hits)))
    body.extend(_circle_lines(hole_hits, diameter=hole_diameter, tool_id=CONTOUR_TOOL_ID, origin_offset=origin_offset))
    body.extend(["ARCS", "0", ""])

    dft.geometry = GeometrySection(line_count=geo.line_count, lines=geo.lines, raw_lines=body)
    return dft


def contour_to_lines(points: list[tuple[float, float]], *, closed: bool = True) -> list[Line]:
    """Convert an ordered vertex ring into Line segments."""
    pts = [Point(x, y) for x, y in points]
    segs = [Line(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if closed and len(pts) >= 2:
        segs.append(Line(pts[-1], pts[0]))
    return segs


def write_punching_dft(dft: DFTFile, path: Path | str) -> Path:
    return DFTGenerator("punching").write(dft, path)
