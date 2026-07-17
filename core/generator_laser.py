"""Laser DFT generation (contour path + MicroJoint stop-point injection).

Laser `[300]` geometry is encoded identically to punching (shared contour
tool path). The laser-specific behaviour is the `[350]` section: MicroJoints —
the ~0.7 mm uncut bridges injected at a target spacing around the contour so
the laser periodically relieves heat (the factory's "stop every ~30 cm").
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from core.dft_generator import DFTGenerator
from core.generator_punching import _segments_to_dftlines
from core.geometry import Line
from core.models import DFTFile, DFTSection, GeometrySection

DEFAULT_STOP_SPACING_MM = 300.0
DEFAULT_MICROJOINT_WIDTH = 0.7

# Trailing fields on a factory MicroJoint record (after t + width).
_MJ_TAIL = "1 0 1 0 0 0 0 0 0 0.0000 0.0000 0.0000 0.0000 0 0.0000 0.0000"


@dataclass
class PlannedMicroJoint:
    entity_index: int
    t: float
    width: float
    x: float
    y: float


def plan_microjoints(
    segments: list[Line],
    *,
    spacing: float = DEFAULT_STOP_SPACING_MM,
    width: float = DEFAULT_MICROJOINT_WIDTH,
    start_offset: float | None = None,
) -> list[PlannedMicroJoint]:
    """Distribute MicroJoints around the contour every ``spacing`` mm.

    Walks cumulative perimeter length and drops a joint each ``spacing`` mm,
    resolving the owning segment and its parametric position ``t``.
    """
    if spacing <= 0:
        raise ValueError("spacing must be > 0")

    lengths = [seg.length for seg in segments]
    perimeter = sum(lengths)
    if perimeter == 0:
        return []

    # Start half a step in so joints don't cluster at the pierce point.
    offset = start_offset if start_offset is not None else spacing / 2.0

    joints: list[PlannedMicroJoint] = []
    target = offset
    cumulative = 0.0
    while target < perimeter:
        # locate segment containing `target`
        running = 0.0
        for idx, seg in enumerate(segments):
            seg_len = lengths[idx]
            if seg_len == 0:
                continue
            if running + seg_len >= target:
                t = (target - running) / seg_len
                t = min(max(t, 0.0), 1.0)
                x = seg.start.x + t * (seg.end.x - seg.start.x)
                y = seg.start.y + t * (seg.end.y - seg.start.y)
                joints.append(PlannedMicroJoint(entity_index=idx, t=t, width=width, x=x, y=y))
                break
            running += seg_len
        target += spacing
    return joints


def _format_350(joints: list[PlannedMicroJoint]) -> list[str]:
    """Group MicroJoints by entity index into factory-style [350] lines."""
    by_entity: dict[int, list[PlannedMicroJoint]] = {}
    for j in joints:
        by_entity.setdefault(j.entity_index, []).append(j)

    lines: list[str] = []
    # Factory emits highest entity index first; match that ordering.
    for idx in sorted(by_entity, reverse=True):
        records = [f"MicroJoint {j.t:.4f} {j.width:.4f} {_MJ_TAIL}" for j in by_entity[idx]]
        lines.append(f"{idx} 0 " + ";".join(records))
    lines.append("")
    return lines


def generate_laser_dft(
    segments: list[Line],
    *,
    width: float,
    height: float,
    material: str = "YWL_HLB_V3",
    origin_offset: float = 0.0,
    stop_spacing: float = DEFAULT_STOP_SPACING_MM,
    microjoint_width: float = DEFAULT_MICROJOINT_WIDTH,
) -> DFTFile:
    """Generate a laser DFTFile with MicroJoint stops injected every ``stop_spacing`` mm."""
    gen = DFTGenerator("laser")
    dft = gen.generate(
        _segments_to_dftlines(segments, origin_offset),
        width=width,
        height=height,
        material=material,
        origin_offset=origin_offset,
    )

    joints = plan_microjoints(segments, spacing=stop_spacing, width=microjoint_width)
    body = _format_350(joints)

    # Replace the placeholder [350] the generator added.
    dft.other_sections = [s for s in dft.other_sections if s.code != 350]
    dft.other_sections.append(DFTSection(code=350, raw_lines=body))
    return dft


def write_laser_dft(dft: DFTFile, path: Path | str) -> Path:
    return DFTGenerator("laser").write(dft, path)
