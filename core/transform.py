"""Coordinate helpers: DXF world space → DFT sheet space."""

from __future__ import annotations

from dataclasses import dataclass

from core.geometry import Line, Point


@dataclass
class SheetTransform:
    """Translate so the contour bbox min corner becomes the sheet origin (0, 0)."""

    origin_x: float
    origin_y: float
    width: float
    height: float

    @property
    def origin_offset(self) -> float:
        """Factory ``3DToolPathPoint`` X offset ≈ -origin_x when origin is negative."""
        return -self.origin_x


def bbox_of(segments: list[Line]) -> tuple[float, float, float, float]:
    if not segments:
        raise ValueError("no segments")
    xs = [c for s in segments for c in (s.start.x, s.end.x)]
    ys = [c for s in segments for c in (s.start.y, s.end.y)]
    return min(xs), min(ys), max(xs), max(ys)


def sheet_transform_from_segments(segments: list[Line]) -> SheetTransform:
    min_x, min_y, max_x, max_y = bbox_of(segments)
    return SheetTransform(
        origin_x=min_x,
        origin_y=min_y,
        width=max_x - min_x,
        height=max_y - min_y,
    )


def to_sheet_space(segments: list[Line], transform: SheetTransform | None = None) -> tuple[list[Line], SheetTransform]:
    """Return segments translated into sheet space and the transform used."""
    tf = transform or sheet_transform_from_segments(segments)
    out = [
        Line(
            Point(s.start.x - tf.origin_x, s.start.y - tf.origin_y),
            Point(s.end.x - tf.origin_x, s.end.y - tf.origin_y),
        )
        for s in segments
    ]
    return out, tf
