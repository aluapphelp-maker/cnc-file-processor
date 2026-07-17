"""Tests for laser stop-point (MicroJoint) detection (laser_stop_detection)."""

from pathlib import Path

import pytest

from core.dft_parser import read_dft
from core.laser_analysis import analyze_file, detect_laser_stops, parse_microjoints

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"
ALL_PUNCH = sorted((FIXTURES / "punching").glob("*.dft"))
ALL_LASER = sorted((FIXTURES / "laser").glob("*.dft"))


def test_punch_has_no_laser_stops():
    joints, summary = analyze_file(PUNCH)
    assert joints == []
    assert not summary.has_stops
    assert summary.microjoint_count == 0


def test_laser_has_stops():
    joints, summary = analyze_file(LASER)
    assert summary.has_stops
    assert summary.microjoint_count > 0
    assert summary.widths == {0.7: summary.microjoint_count}
    assert summary.mean_spacing is not None
    assert 100 < summary.mean_spacing < 400


def test_microjoints_have_positions_and_valid_t():
    joints, _ = analyze_file(LASER)
    for j in joints:
        assert 0.0 <= j.t <= 1.0
        assert j.x is not None and j.y is not None
        assert j.width == 0.7


def test_parse_microjoints_multi_per_segment():
    # A [350] line may carry several ';'-separated MicroJoints for one entity.
    sec = read_dft(LASER).first(350)
    joints = parse_microjoints(sec)
    by_entity: dict[int, int] = {}
    for j in joints:
        by_entity[j.entity_index] = by_entity.get(j.entity_index, 0) + 1
    assert max(by_entity.values()) >= 2  # at least one segment has multiple


@pytest.mark.parametrize("path", ALL_PUNCH, ids=lambda p: p.name)
def test_all_punch_files_have_no_stops(path: Path):
    _, summary = analyze_file(path)
    assert not summary.has_stops


@pytest.mark.parametrize("path", ALL_LASER, ids=lambda p: p.name)
def test_all_laser_files_have_stops(path: Path):
    joints, summary = analyze_file(path)
    assert summary.has_stops
    assert 1 <= summary.microjoint_count
    assert set(summary.widths) == {0.7}
    assert summary.mean_spacing is not None
