"""Basic 2D geometry primitives for contour comparison and DXF I/O."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def dist(self, other: Point) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def almost_equal(self, other: Point, tol: float = 0.01) -> bool:
        return self.dist(other) <= tol

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class Line:
    start: Point
    end: Point

    @property
    def length(self) -> float:
        return self.start.dist(self.end)

    def reversed(self) -> Line:
        return Line(self.end, self.start)

    def almost_equal(self, other: Line, tol: float = 0.01, *, bidirectional: bool = True) -> bool:
        same = self.start.almost_equal(other.start, tol) and self.end.almost_equal(other.end, tol)
        if same or not bidirectional:
            return same
        return self.start.almost_equal(other.end, tol) and self.end.almost_equal(other.start, tol)

    def as_tuple(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (self.start.as_tuple(), self.end.as_tuple())


@dataclass
class Polyline:
    """Ordered vertex ring or open chain."""

    points: list[Point] = field(default_factory=list)
    closed: bool = False

    def __len__(self) -> int:
        return len(self.points)

    @property
    def segments(self) -> list[Line]:
        if len(self.points) < 2:
            return []
        segs = [Line(self.points[i], self.points[i + 1]) for i in range(len(self.points) - 1)]
        if self.closed and len(self.points) >= 2:
            segs.append(Line(self.points[-1], self.points[0]))
        return segs

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def total_length(self) -> float:
        return sum(s.length for s in self.segments)
