"""Tests for [300] LINES geometry parsing (coordinates only)."""

from pathlib import Path

import pytest

from core.dft_parser import parse_dft, parse_geometry

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH_SAMPLE = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER_SAMPLE = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"


def test_parse_geometry_unit():
    geo = parse_geometry(
        [
            "LINES",
            "2",
            "0 0 10 0 4 0 0 0 -1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1",
            "1 0 10 0 15 0",
            "3DToolPathPoint1 = 1 0 0 0 0 0 0 0 0 0 0 0",
            "3DToolPathPoint2 = 2 0 0 0 0 0 0 0 0 0 0 0",
            "10 0 10 20 4 0 0 0 -1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1",
            "3 0 20 0 15 0",
            "3DToolPathPoint1 = 3 0 0 0 0 0 0 0 0 0 0 0",
            "3DToolPathPoint2 = 4 0 0 0 0 0 0 0 0 0 0 0",
            "POINTS",
            "0",
        ]
    )
    assert geo.line_count == 2
    assert len(geo.lines) == 2
    assert geo.lines[0].x1 == 0.0
    assert geo.lines[0].y1 == 0.0
    assert geo.lines[0].x2 == 10.0
    assert geo.lines[0].y2 == 0.0
    assert geo.lines[0].params[0] == "4"
    assert len(geo.lines[0].meta_lines) == 3
    assert geo.lines[0].meta_lines[0].startswith("1 0 10")
    assert "3DToolPathPoint1" in geo.lines[0].meta_lines[1]
    assert geo.lines[1].x1 == 10.0
    assert geo.lines[1].y2 == 20.0


def test_parse_geometry_empty_or_malformed():
    assert parse_geometry([]).line_count == 0
    assert parse_geometry(["POINTS", "1"]).lines == []
    assert parse_geometry(["LINES", "nope"]).lines == []


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_parse_dft_geometry_count_matches(sample: Path):
    dft = parse_dft(sample)
    assert dft.geometry.line_count == 60
    assert len(dft.geometry.lines) == 60


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_parse_dft_first_and_last_coords(sample: Path):
    dft = parse_dft(sample)
    first = dft.geometry.lines[0]
    assert first.x1 == pytest.approx(308.50291)
    assert first.y1 == pytest.approx(226.00306)
    assert first.x2 == pytest.approx(142.50014)
    assert first.y2 == pytest.approx(60.00233)
    # Contour is closed: last endpoint meets an earlier vertex chain; first
    # segment starts at the top-right-ish corner used by both punch & laser.
    assert len(first.params) == 22
    assert len(first.meta_lines) == 3


def test_parse_dft_geometry_has_connected_runs():
    """LINES are polylines: neighbors usually share endpoints, with jumps between contours."""
    dft = parse_dft(PUNCH_SAMPLE)
    lines = dft.geometry.lines
    connected = 0
    breaks = 0
    for prev, cur in zip(lines, lines[1:]):
        if cur.x1 == pytest.approx(prev.x2) and cur.y1 == pytest.approx(prev.y2):
            connected += 1
        else:
            breaks += 1
    assert connected > 0
    assert breaks > 0  # more than one contour in this sample


def test_parse_dft_excludes_300_from_other_sections():
    dft = parse_dft(PUNCH_SAMPLE)
    codes = {s.code for s in dft.other_sections}
    assert 300 not in codes
    assert 200 not in codes
    assert dft.geometry.line_count > 0


def test_punch_and_laser_share_same_line_geometry():
    punch = parse_dft(PUNCH_SAMPLE)
    laser = parse_dft(LASER_SAMPLE)
    assert punch.geometry.line_count == laser.geometry.line_count
    for p, l in zip(punch.geometry.lines, laser.geometry.lines):
        assert (p.x1, p.y1, p.x2, p.y2) == pytest.approx((l.x1, l.y1, l.x2, l.y2))
