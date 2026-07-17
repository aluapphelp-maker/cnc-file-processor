"""Reverse-engineered CncKad tool-path encoding for the `[300]` section.

Findings (verified across all 48 punching + 48 laser factory fixtures):

* The `[300]` section body is **byte-identical** between the punching and
  laser version of the same part. Machine selection (punch vs laser) is
  therefore encoded at the *file* level (`[200]` `/I`, `/V`, `/S` flags and
  the laser-only `[350]` section), NOT per geometry entity.

* `[300]` groups geometry into keyword subsections: ``LINES``, ``POINTS``,
  ``CIRCLES``, ``ARCS`` (each preceded by a declared count). Every entity is
  followed by exactly two ``3DToolPathPoint`` lines, which we use as a robust
  record delimiter.

* **LINES** entity encoding::

      x1 y1 x2 y2 <22 params: param[0]=4 (=line), rest 0, last 1>
      <dir_code> <slope> <length> 0 <tool_id> 0
      3DToolPathPoint1 = <origin_offset> 0 0 ...
      3DToolPathPoint2 = <origin_offset> 0 0 ...

  - ``dir_code`` (verified octant): 1=E 2=W 3=N 4=S 5=NE 6=SE 7=NW 8=SW
  - ``length`` matches the Euclidean segment length exactly (0 mismatches
    over 2088 segments).
  - ``tool_id`` is constant ``15`` in this dataset (the contour tool in the
    ``[505]`` / ``[203]`` tool table).

* **CIRCLES** entity encoding::

      cx cy radius <tool_id> 0 3 0 0 0 -1 0

  All factory circles are radius ``1.5`` (Ø3 mm round-tool hits), tool id
  ``15``.

The ``3DToolPathPoint`` leading value equals the part's machine-bed X origin
offset (it matches the DXF world-coordinate translation), constant per file.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from core.dft_parser import RawDFT, RawSection, parse_dft, read_dft
from core.models import DFTFile

# dir_code -> compass octant (reverse-engineered from segment geometry)
DIRECTION_CODES: dict[int, str] = {
    1: "E",
    2: "W",
    3: "N",
    4: "S",
    5: "NE",
    6: "SE",
    7: "NW",
    8: "SW",
}


def encode_direction(dx: float, dy: float, *, axis_tol_deg: float = 1.0) -> tuple[int, float]:
    """Inverse of ``DIRECTION_CODES``: map a segment delta to (dir_code, slope).

    Factory data is rectilinear + 45° only, so we snap near-axis segments to
    the axis codes 1-4 (slope 0). Diagonals use codes 5-8 with slope = dy/dx
    (which is ±1 for 45°). Matches all 96 factory files.
    """
    tol = math.tan(math.radians(axis_tol_deg))
    if abs(dy) <= abs(dx) * tol:  # horizontal
        return (1, 0.0) if dx >= 0 else (2, 0.0)
    if abs(dx) <= abs(dy) * tol:  # vertical
        return (3, 0.0) if dy >= 0 else (4, 0.0)
    slope = dy / dx
    if dx > 0 and dy > 0:
        return 5, slope  # NE
    if dx > 0 and dy < 0:
        return 6, slope  # SE
    if dx < 0 and dy > 0:
        return 7, slope  # NW
    return 8, slope  # SW

_TP_PREFIX = "3DToolPathPoint"
_SUBSECTION_KEYWORDS = ("LINES", "POINTS", "CIRCLES", "ARCS")


@dataclass
class ToolLine:
    x1: float
    y1: float
    x2: float
    y2: float
    direction_code: int
    slope: float
    length: float
    tool_id: int
    origin_offset: float | None = None

    @property
    def direction(self) -> str:
        return DIRECTION_CODES.get(self.direction_code, "?")


@dataclass
class ToolCircle:
    cx: float
    cy: float
    radius: float
    tool_id: int
    origin_offset: float | None = None

    @property
    def diameter(self) -> float:
        return self.radius * 2.0


@dataclass
class RawEntity:
    """An entity we count but do not fully model yet (ARCS, POINTS)."""

    keyword: str
    primary: str
    extra: list[str] = field(default_factory=list)


@dataclass
class ToolPath:
    """Structured decode of a `[300]` section."""

    lines: list[ToolLine] = field(default_factory=list)
    circles: list[ToolCircle] = field(default_factory=list)
    arcs: list[RawEntity] = field(default_factory=list)
    points: list[RawEntity] = field(default_factory=list)
    declared_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class ToolUsageSummary:
    tool_ids: set[int] = field(default_factory=set)
    line_segment_count: int = 0
    circle_hit_count: int = 0
    arc_count: int = 0
    point_count: int = 0
    total_line_length: float = 0.0
    circle_diameters: dict[float, int] = field(default_factory=dict)
    direction_histogram: dict[str, int] = field(default_factory=dict)


def _origin_offset(tp_line: str) -> float | None:
    if "=" not in tp_line:
        return None
    rhs = tp_line.split("=", 1)[1].split()
    if not rhs:
        return None
    try:
        return float(rhs[0])
    except ValueError:
        return None


def _iter_records(body: list[str]) -> list[tuple[str, list[str]]]:
    """Split a subsection body into (primary, following_lines) records.

    A record spans from a primary data line up to and including its second
    ``3DToolPathPoint`` line (every entity has exactly two).
    """
    records: list[tuple[str, list[str]]] = []
    i = 0
    n = len(body)
    while i < n:
        primary = body[i]
        if not primary.strip():
            i += 1
            continue
        following: list[str] = []
        j = i + 1
        tp_seen = 0
        while j < n and tp_seen < 2:
            line = body[j]
            following.append(line)
            if line.strip().startswith(_TP_PREFIX):
                tp_seen += 1
            j += 1
        records.append((primary, following))
        i = j
    return records


def _split_subsections(section: RawSection) -> list[tuple[str, int, list[str]]]:
    """Return (keyword, declared_count, body_lines) for each subsection."""
    out: list[tuple[str, int, list[str]]] = []
    lines = section.lines
    i = 0
    while i < len(lines):
        kw = lines[i].strip()
        if kw in _SUBSECTION_KEYWORDS:
            count = 0
            if i + 1 < len(lines):
                try:
                    count = int(lines[i + 1].strip())
                except ValueError:
                    count = 0
            # collect body until next keyword
            body: list[str] = []
            j = i + 2
            while j < len(lines) and lines[j].strip() not in _SUBSECTION_KEYWORDS:
                body.append(lines[j])
                j += 1
            out.append((kw, count, body))
            i = j
        else:
            i += 1
    return out


def parse_tool_path(section: RawSection) -> ToolPath:
    """Decode a raw `[300]` section into structured tool-path entities."""
    path = ToolPath()
    for kw, count, body in _split_subsections(section):
        path.declared_counts[kw] = count
        records = _iter_records(body)
        for primary, following in records:
            tokens = primary.split()
            tp_offset = next(
                (_origin_offset(f) for f in following if f.strip().startswith(_TP_PREFIX)),
                None,
            )
            if kw == "LINES":
                meta = next(
                    (f.split() for f in following if not f.strip().startswith(_TP_PREFIX) and f.strip()),
                    [],
                )
                if len(tokens) >= 4 and len(meta) >= 6:
                    path.lines.append(
                        ToolLine(
                            x1=float(tokens[0]),
                            y1=float(tokens[1]),
                            x2=float(tokens[2]),
                            y2=float(tokens[3]),
                            direction_code=int(float(meta[0])),
                            slope=float(meta[1]),
                            length=float(meta[2]),
                            tool_id=int(float(meta[4])),
                            origin_offset=tp_offset,
                        )
                    )
            elif kw == "CIRCLES":
                if len(tokens) >= 4:
                    path.circles.append(
                        ToolCircle(
                            cx=float(tokens[0]),
                            cy=float(tokens[1]),
                            radius=float(tokens[2]),
                            tool_id=int(float(tokens[3])),
                            origin_offset=tp_offset,
                        )
                    )
            elif kw == "ARCS":
                extra = [f for f in following if not f.strip().startswith(_TP_PREFIX) and f.strip()]
                path.arcs.append(RawEntity(keyword=kw, primary=primary, extra=extra))
            elif kw == "POINTS":
                path.points.append(RawEntity(keyword=kw, primary=primary))
    return path


def summarize_tools(path: ToolPath) -> ToolUsageSummary:
    summary = ToolUsageSummary()
    summary.line_segment_count = len(path.lines)
    summary.circle_hit_count = len(path.circles)
    summary.arc_count = len(path.arcs)
    summary.point_count = len(path.points)

    for line in path.lines:
        summary.tool_ids.add(line.tool_id)
        summary.total_line_length += line.length
        d = line.direction
        summary.direction_histogram[d] = summary.direction_histogram.get(d, 0) + 1
    for circle in path.circles:
        summary.tool_ids.add(circle.tool_id)
        dia = round(circle.diameter, 3)
        summary.circle_diameters[dia] = summary.circle_diameters.get(dia, 0) + 1
    return summary


def parse_tool_table(raw: RawDFT) -> list[str]:
    """Extract tool/model references from the `[505]` section."""
    sec = raw.first(505)
    if sec is None:
        return []
    refs: list[str] = []
    for line in sec.lines:
        if '"M=' in line:
            refs.append(line.strip())
    return refs


def analyze_file(path: Path | str) -> tuple[DFTFile, ToolPath, ToolUsageSummary]:
    """Full tool-path analysis for one DFT file."""
    raw = read_dft(path)
    dft = parse_dft(path)
    sec300 = raw.first(300)
    tool_path = parse_tool_path(sec300) if sec300 is not None else ToolPath()
    summary = summarize_tools(tool_path)
    return dft, tool_path, summary
