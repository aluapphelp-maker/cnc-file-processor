"""Laser stop-point (MicroJoint) detection for the `[350]` section.

Findings (verified across all 48 laser + 48 punching factory fixtures):

* Section `[350]` is present in **every** laser file and **absent** from every
  punching file. It encodes *MicroJoints* — the ~0.7 mm uncut bridges that hold
  the part to the sheet and act as the laser's periodic stop/relief points
  (the "stops every ~30 cm" behaviour described by the factory).

* Each `[350]` line targets one geometry entity from `[300]`::

      <entity_index> 0 MicroJoint <t> <width> 1 0 1 0 ... ;MicroJoint <t2> ...

  - ``entity_index`` indexes into the `[300]` ``LINES`` list.
  - ``t`` is the parametric position (0..1) along that segment.
  - ``width`` is the bridge width in mm (always ``0.7`` in this dataset).
  - Multiple MicroJoints on one segment are ``;``-separated.

* Across the dataset: 14–24 MicroJoints per part (mean 18), mean spacing
  ~221 mm around the contour perimeter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.dft_parser import RawDFT, RawSection, read_dft
from core.tool_analysis import ToolLine, parse_tool_path

_MICROJOINT = "MicroJoint"


@dataclass
class MicroJoint:
    """A single laser stop bridge on a contour segment."""

    entity_index: int
    t: float
    width: float
    x: float | None = None
    y: float | None = None


@dataclass
class LaserStopSummary:
    has_stops: bool = False
    microjoint_count: int = 0
    widths: dict[float, int] = field(default_factory=dict)
    perimeter: float = 0.0
    mean_spacing: float | None = None


def parse_microjoints(section: RawSection | None) -> list[MicroJoint]:
    """Parse raw `[350]` MicroJoint records (without absolute positions)."""
    joints: list[MicroJoint] = []
    if section is None:
        return joints
    for line in section.lines:
        stripped = line.strip()
        if _MICROJOINT not in stripped:
            continue
        head, rest = stripped.split(_MICROJOINT, 1)
        head_tokens = head.split()
        if not head_tokens:
            continue
        try:
            entity_index = int(head_tokens[0])
        except ValueError:
            continue
        for chunk in (_MICROJOINT + rest).split(";"):
            tokens = chunk.replace(_MICROJOINT, "").split()
            if len(tokens) < 2:
                continue
            try:
                t = float(tokens[0])
                width = float(tokens[1])
            except ValueError:
                continue
            joints.append(MicroJoint(entity_index=entity_index, t=t, width=width))
    return joints


def _locate(joint: MicroJoint, lines: list[ToolLine]) -> None:
    if 0 <= joint.entity_index < len(lines):
        ln = lines[joint.entity_index]
        joint.x = ln.x1 + joint.t * (ln.x2 - ln.x1)
        joint.y = ln.y1 + joint.t * (ln.y2 - ln.y1)


def detect_laser_stops(raw: RawDFT) -> tuple[list[MicroJoint], LaserStopSummary]:
    """Detect laser stop points (MicroJoints) and summarize their spacing."""
    section = raw.first(350)
    joints = parse_microjoints(section)

    sec300 = raw.first(300)
    tool_path = parse_tool_path(sec300) if sec300 is not None else None
    lines = tool_path.lines if tool_path else []
    for joint in joints:
        _locate(joint, lines)

    summary = LaserStopSummary()
    summary.has_stops = bool(joints)
    summary.microjoint_count = len(joints)
    for joint in joints:
        w = round(joint.width, 3)
        summary.widths[w] = summary.widths.get(w, 0) + 1
    summary.perimeter = sum(l.length for l in lines)
    if joints and summary.perimeter > 0:
        summary.mean_spacing = summary.perimeter / len(joints)
    return joints, summary


def analyze_file(path: Path | str) -> tuple[list[MicroJoint], LaserStopSummary]:
    """Convenience wrapper: detect laser stops for one DFT file."""
    return detect_laser_stops(read_dft(path))
