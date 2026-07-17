"""Tests for punching + laser DFT generation (Phase 2 red tasks)."""

import math
from pathlib import Path

import pytest

from core.dft_parser import parse_dft, read_dft
from core.generator_laser import (
    generate_laser_dft,
    plan_microjoints,
    write_laser_dft,
)
from core.generator_punching import (
    contour_to_lines,
    generate_punching_dft,
    nibble_positions,
    segment_meta_lines,
    write_punching_dft,
)
from core.laser_analysis import detect_laser_stops
from core.tool_analysis import parse_tool_path

# A 100 x 50 rectangle contour.
RECT = contour_to_lines([(0, 0), (100, 0), (100, 50), (0, 50)])


# --- direction/meta encoding ---

def test_segment_meta_horizontal_and_diagonal():
    m = segment_meta_lines(0, 0, 100, 0)
    assert m[0].split()[0] == "1"  # East
    assert m[0].split()[2] == "100"  # length
    assert "3DToolPathPoint1" in m[1]

    d = segment_meta_lines(0, 0, 10, 10)
    assert d[0].split()[0] == "5"  # NE
    assert d[0].split()[1] in ("1", "1.0")


# --- nibble / overlap ---

def test_nibble_overlap_spacing_within_tool():
    hits = nibble_positions(0, 0, 30, 0, tool_diameter=3.0, overlap=0.2)
    assert len(hits) >= 2
    # endpoints included
    assert (hits[0].x, hits[0].y) == (0, 0)
    assert hits[-1].x == pytest.approx(30)
    # consecutive spacing <= tool diameter (material removed)
    for a, b in zip(hits, hits[1:]):
        assert math.hypot(b.x - a.x, b.y - a.y) <= 3.0 + 1e-9


def test_nibble_zero_length():
    hits = nibble_positions(5, 5, 5, 5)
    assert len(hits) == 1


def test_nibble_invalid_args():
    with pytest.raises(ValueError):
        nibble_positions(0, 0, 10, 0, tool_diameter=0)
    with pytest.raises(ValueError):
        nibble_positions(0, 0, 10, 0, overlap=1.0)


# --- punching generation ---

def test_generate_punching_roundtrip(tmp_path: Path):
    dft = generate_punching_dft(RECT, width=100, height=50, holes=[(50, 25)])
    out = tmp_path / "punch.dft"
    write_punching_dft(dft, out)

    again = parse_dft(out)
    assert again.machine_type == "punching"
    assert again.geometry.line_count == 4
    assert again.material.name == "YWL_HLB_V3"

    tp = parse_tool_path(read_dft(out).first(300))
    assert len(tp.lines) == 4
    assert len(tp.circles) == 1  # the hole
    assert tp.circles[0].radius == pytest.approx(1.5)
    # laser stop section must be absent for punching
    assert 350 not in read_dft(out).section_codes


def test_generated_punch_lengths_match_geometry(tmp_path: Path):
    dft = generate_punching_dft(RECT, width=100, height=50)
    out = tmp_path / "punch2.dft"
    write_punching_dft(dft, out)
    tp = parse_tool_path(read_dft(out).first(300))
    for line in tp.lines:
        computed = math.hypot(line.x2 - line.x1, line.y2 - line.y1)
        assert line.length == pytest.approx(computed, abs=0.01)
        assert line.tool_id == 15


# --- laser generation ---

def test_plan_microjoints_spacing():
    joints = plan_microjoints(RECT, spacing=50.0)
    assert len(joints) > 0
    perim = sum(s.length for s in RECT)  # 300
    # roughly perimeter/spacing joints
    assert len(joints) == pytest.approx(perim / 50.0, abs=1)
    for j in joints:
        assert 0.0 <= j.t <= 1.0
        assert j.width == 0.7


def test_generate_laser_roundtrip_with_stops(tmp_path: Path):
    dft = generate_laser_dft(RECT, width=100, height=50, stop_spacing=50.0)
    out = tmp_path / "laser.dft"
    write_laser_dft(dft, out)

    raw = read_dft(out)
    assert 350 in raw.section_codes
    again = parse_dft(out)
    assert again.machine_type == "laser"
    assert again.geometry.line_count == 4

    joints, summary = detect_laser_stops(raw)
    assert summary.has_stops
    assert summary.microjoint_count > 0
    assert set(summary.widths) == {0.7}
    # injected spacing should be near requested
    assert summary.mean_spacing == pytest.approx(50.0, rel=0.5)


def test_laser_stop_spacing_configurable():
    few = plan_microjoints(RECT, spacing=150.0)
    many = plan_microjoints(RECT, spacing=30.0)
    assert len(many) > len(few)


def test_punch_and_laser_generated_geometry_identical(tmp_path: Path):
    """Generated punch & laser share [300] geometry, like the factory."""
    p = generate_punching_dft(RECT, width=100, height=50)
    l = generate_laser_dft(RECT, width=100, height=50)
    p_lines = [(s.x1, s.y1, s.x2, s.y2) for s in p.geometry.lines]
    l_lines = [(s.x1, s.y1, s.x2, s.y2) for s in l.geometry.lines]
    assert p_lines == l_lines
