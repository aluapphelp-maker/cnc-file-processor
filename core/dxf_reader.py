"""DXF contour reader (KNA layer conventions, via ezdxf).

Adapted from panel-engine's contour extraction, kept lean for CNC use:
collect LINE / LWPOLYLINE segments from ``KNA - Contour`` (with fallbacks).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import ezdxf

from core.geometry import Line, Point, Polyline

DEFAULT_CONTOUR_LAYER = "KNA - Contour"


def _segments_from_entity(entity: Any) -> list[Line]:
    dtype = entity.dxftype()
    if dtype == "LINE":
        start = Point(float(entity.dxf.start.x), float(entity.dxf.start.y))
        end = Point(float(entity.dxf.end.x), float(entity.dxf.end.y))
        return [Line(start, end)]
    if dtype == "LWPOLYLINE":
        pts = [Point(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
        if len(pts) < 2:
            return []
        segs = [Line(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        if getattr(entity, "closed", False):
            segs.append(Line(pts[-1], pts[0]))
        return segs
    return []


def _layer_names(msp: Any) -> set[str]:
    return {str(e.dxf.layer or "") for e in msp}


def resolve_contour_layer(msp: Any, preferred: str = DEFAULT_CONTOUR_LAYER) -> str:
    layers = _layer_names(msp)
    if preferred in layers:
        return preferred
    for name in sorted(layers):
        low = name.lower()
        if "cont" in low and "dim" not in low:
            return name
    raise ValueError(
        f"No contour layer found (wanted {preferred!r}; have {sorted(layers)})"
    )


def read_dxf_segments(
    path: Path | str,
    *,
    layer: str | None = None,
) -> list[Line]:
    """Return contour line segments from a DXF file."""
    path = Path(path)
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    contour_layer = layer or resolve_contour_layer(msp)

    segments: list[Line] = []
    for entity in msp:
        if str(entity.dxf.layer or "") != contour_layer:
            continue
        segments.extend(_segments_from_entity(entity))
    return segments


def read_dxf_polylines(
    path: Path | str,
    *,
    layer: str | None = None,
) -> list[Polyline]:
    """Return LWPOLYLINE contours (plus LINE-only chains as open polylines)."""
    path = Path(path)
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    contour_layer = layer or resolve_contour_layer(msp)

    polylines: list[Polyline] = []
    lone_lines: list[Line] = []

    for entity in msp:
        if str(entity.dxf.layer or "") != contour_layer:
            continue
        if entity.dxftype() == "LWPOLYLINE":
            pts = [Point(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
            if len(pts) >= 2 and pts[0].almost_equal(pts[-1]):
                pts = pts[:-1]
            if len(pts) >= 2:
                polylines.append(Polyline(points=pts, closed=bool(getattr(entity, "closed", False))))
        elif entity.dxftype() == "LINE":
            lone_lines.extend(_segments_from_entity(entity))

    for line in lone_lines:
        polylines.append(Polyline(points=[line.start, line.end], closed=False))
    return polylines


def read_dxf_geometry(path: Path | str, *, layer: str | None = None) -> list[Line]:
    """Public alias used by the plan / CLI tools."""
    return read_dxf_segments(path, layer=layer)
