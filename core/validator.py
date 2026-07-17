"""Compare two DFT files (parameters + geometry with tolerance)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.dft_parser import parse_dft
from core.geometry import Line, Point
from core.models import DFTFile


@dataclass
class GeometryMismatch:
    index: int
    reference: tuple[float, float, float, float]
    other: tuple[float, float, float, float] | None
    detail: str


@dataclass
class ComparisonResult:
    reference_path: str
    other_path: str
    tolerance: float
    parameter_diffs: list[str] = field(default_factory=list)
    geometry_mismatches: list[GeometryMismatch] = field(default_factory=list)
    reference_line_count: int = 0
    other_line_count: int = 0
    matched_lines: int = 0
    match_mode: str = "positional"  # or "unordered"

    @property
    def ok(self) -> bool:
        return not self.parameter_diffs and not self.geometry_mismatches

    @property
    def reference_coverage(self) -> float:
        if self.reference_line_count == 0:
            return 1.0
        return self.matched_lines / self.reference_line_count

    def summary(self) -> str:
        status = "MATCH" if self.ok else "DIFF"
        lines = [
            f"[{status}] {self.reference_path}  vs  {self.other_path}",
            f"  tolerance: {self.tolerance}  mode: {self.match_mode}",
            f"  lines: ref={self.reference_line_count} other={self.other_line_count} matched={self.matched_lines}"
            f" ({100 * self.reference_coverage:.1f}% of ref)",
        ]
        if self.parameter_diffs:
            lines.append("  parameter diffs:")
            lines.extend(f"    - {d}" for d in self.parameter_diffs)
        if self.geometry_mismatches:
            lines.append(f"  geometry mismatches: {len(self.geometry_mismatches)}")
            for m in self.geometry_mismatches[:20]:
                lines.append(f"    - [{m.index}] {m.detail}")
            if len(self.geometry_mismatches) > 20:
                lines.append(f"    ... ({len(self.geometry_mismatches) - 20} more)")
        return "\n".join(lines)


def _dft_lines(dft: DFTFile) -> list[Line]:
    return [
        Line(Point(seg.x1, seg.y1), Point(seg.x2, seg.y2))
        for seg in dft.geometry.lines
    ]


def _compare_parameters(ref: DFTFile, other: DFTFile, *, extent_tol: float = 0.05) -> list[str]:
    diffs: list[str] = []
    if ref.machine_type != other.machine_type:
        diffs.append(f"machine_type: {ref.machine_type!r} vs {other.machine_type!r}")
    if ref.material.name != other.material.name:
        diffs.append(f"material: {ref.material.name!r} vs {other.material.name!r}")
    for label, a, b in (
        ("extent_width", ref.machine_config.extent_width, other.machine_config.extent_width),
        ("extent_height", ref.machine_config.extent_height, other.machine_config.extent_height),
        ("k_factor", ref.bend_params.k_factor, other.bend_params.k_factor),
    ):
        if a is None or b is None:
            if a != b:
                diffs.append(f"{label}: {a!r} vs {b!r}")
        elif abs(float(a) - float(b)) > extent_tol:
            diffs.append(f"{label}: {a} vs {b}")
    return diffs


def match_lines_unordered(
    reference: list[Line],
    other: list[Line],
    *,
    tolerance: float = 0.01,
) -> tuple[int, list[int], list[int]]:
    """Match lines regardless of order (bidirectional).

    Returns (matched_count, unmatched_ref_indices, unmatched_other_indices).
    """
    used = [False] * len(other)
    unmatched_ref: list[int] = []
    matched = 0
    for i, ref_line in enumerate(reference):
        found = False
        for j, other_line in enumerate(other):
            if used[j]:
                continue
            if ref_line.almost_equal(other_line, tolerance):
                used[j] = True
                matched += 1
                found = True
                break
        if not found:
            unmatched_ref.append(i)
    unmatched_other = [j for j, u in enumerate(used) if not u]
    return matched, unmatched_ref, unmatched_other


def compare_dft_files(
    reference_path: Path | str,
    other_path: Path | str,
    *,
    tolerance: float = 0.01,
    check_parameters: bool = True,
    unordered: bool = False,
    min_coverage: float = 1.0,
) -> ComparisonResult:
    """Compare two DFT files.

    ``unordered=True`` matches geometry as a set (needed when DXF→DFT emits
    extra contour segments). ``min_coverage`` is the fraction of *reference*
    lines that must be found in other for geometry to pass when unordered.
    """
    ref_path = Path(reference_path)
    oth_path = Path(other_path)
    ref = parse_dft(ref_path)
    other = parse_dft(oth_path)

    result = ComparisonResult(
        reference_path=str(ref_path),
        other_path=str(oth_path),
        tolerance=tolerance,
        reference_line_count=len(ref.geometry.lines),
        other_line_count=len(other.geometry.lines),
        match_mode="unordered" if unordered else "positional",
    )
    if check_parameters:
        result.parameter_diffs = _compare_parameters(ref, other)

    ref_lines = _dft_lines(ref)
    other_lines = _dft_lines(other)

    if unordered:
        matched, miss_ref, miss_other = match_lines_unordered(
            ref_lines, other_lines, tolerance=tolerance
        )
        result.matched_lines = matched
        coverage = result.reference_coverage
        if coverage + 1e-12 < min_coverage:
            for i in miss_ref[:50]:
                r = ref_lines[i]
                result.geometry_mismatches.append(
                    GeometryMismatch(
                        index=i,
                        reference=(r.start.x, r.start.y, r.end.x, r.end.y),
                        other=None,
                        detail="reference line not found in other",
                    )
                )
            if len(miss_ref) > 50:
                result.geometry_mismatches.append(
                    GeometryMismatch(
                        index=-1,
                        reference=(0, 0, 0, 0),
                        other=None,
                        detail=f"... {len(miss_ref) - 50} more unmatched reference lines",
                    )
                )
        # Extra lines in other (DXF often has more) are noted but do not fail
        # when coverage of the reference is sufficient.
        if miss_other and coverage >= min_coverage:
            result.geometry_mismatches.append(
                GeometryMismatch(
                    index=-1,
                    reference=(0, 0, 0, 0),
                    other=None,
                    detail=f"info: {len(miss_other)} extra lines in other (not failing)",
                )
            )
            # Strip info-only notes so ok stays True
            result.geometry_mismatches = [
                m for m in result.geometry_mismatches if not m.detail.startswith("info:")
            ]
        return result

    n = max(len(ref_lines), len(other_lines))
    matched = 0
    for i in range(n):
        if i >= len(ref_lines):
            o = other_lines[i]
            result.geometry_mismatches.append(
                GeometryMismatch(
                    index=i,
                    reference=(0, 0, 0, 0),
                    other=(o.start.x, o.start.y, o.end.x, o.end.y),
                    detail="extra line in other",
                )
            )
            continue
        if i >= len(other_lines):
            r = ref_lines[i]
            result.geometry_mismatches.append(
                GeometryMismatch(
                    index=i,
                    reference=(r.start.x, r.start.y, r.end.x, r.end.y),
                    other=None,
                    detail="missing line in other",
                )
            )
            continue
        r, o = ref_lines[i], other_lines[i]
        if r.almost_equal(o, tolerance):
            matched += 1
        else:
            result.geometry_mismatches.append(
                GeometryMismatch(
                    index=i,
                    reference=(r.start.x, r.start.y, r.end.x, r.end.y),
                    other=(o.start.x, o.start.y, o.end.x, o.end.y),
                    detail=(
                        f"coords differ beyond {tolerance}: "
                        f"{r.as_tuple()} vs {o.as_tuple()}"
                    ),
                )
            )
    result.matched_lines = matched
    return result
