"""Tests for [300] tool-path decoding (tool_path_analysis)."""

import math
from pathlib import Path

import pytest

from core.dft_parser import read_dft
from core.tool_analysis import (
    DIRECTION_CODES,
    analyze_file,
    parse_tool_path,
    parse_tool_table,
    summarize_tools,
)

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"
ALL_PUNCH = sorted((FIXTURES / "punching").glob("*.dft"))
ALL_LASER = sorted((FIXTURES / "laser").glob("*.dft"))


def test_parsed_counts_match_declared():
    dft, path, summary = analyze_file(PUNCH)
    assert path.declared_counts["LINES"] == len(path.lines)
    assert path.declared_counts["CIRCLES"] == len(path.circles)
    assert path.declared_counts["ARCS"] == len(path.arcs)
    assert path.declared_counts["POINTS"] == len(path.points)


def test_line_length_matches_geometry():
    _, path, _ = analyze_file(PUNCH)
    for line in path.lines:
        computed = math.hypot(line.x2 - line.x1, line.y2 - line.y1)
        assert line.length == pytest.approx(computed, abs=0.01)


def test_direction_code_matches_octant():
    _, path, _ = analyze_file(PUNCH)
    for line in path.lines:
        dx = line.x2 - line.x1
        dy = line.y2 - line.y1
        d = line.direction
        # Verify the dominant axis agrees with the decoded compass label.
        if abs(dx) > abs(dy):
            assert "E" in d if dx > 0 else "W" in d
        elif abs(dy) > abs(dx):
            assert "N" in d if dy > 0 else "S" in d


def test_tool_id_constant_and_circles_are_holes():
    _, path, summary = analyze_file(PUNCH)
    assert summary.tool_ids == {15}
    assert summary.circle_diameters == {3.0: 18}
    for circle in path.circles:
        assert circle.radius == 1.5
        assert circle.tool_id == 15


def test_tool_table_extraction():
    refs = parse_tool_table(read_dft(PUNCH))
    assert any("YWL_HLB_V3.MDL" in r for r in refs)
    assert any("E6-XML.MDL" in r for r in refs)


def test_punch_and_laser_section_300_identical():
    """Key finding: [300] geometry+tool encoding is identical punch vs laser."""
    p = read_dft(PUNCH).first(300)
    l = read_dft(LASER).first(300)
    p_body = [ln for ln in p.lines if ln.strip()]
    l_body = [ln for ln in l.lines if ln.strip()]
    assert p_body == l_body


@pytest.mark.parametrize("path", ALL_PUNCH + ALL_LASER, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_all_files_decode_cleanly(path: Path):
    _, tool_path, summary = analyze_file(path)
    assert tool_path.declared_counts.get("LINES", 0) == len(tool_path.lines)
    assert tool_path.declared_counts.get("CIRCLES", 0) == len(tool_path.circles)
    assert summary.tool_ids  # at least one tool referenced
    assert summary.total_line_length > 0


def test_direction_codes_table_complete():
    assert set(DIRECTION_CODES) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert DIRECTION_CODES[1] == "E"
    assert DIRECTION_CODES[8] == "SW"
