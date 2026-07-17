"""Tests for structural DFT parsing (header + section split only)."""

from pathlib import Path

import pytest

from core.dft_parser import read_dft, split_sections

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH_SAMPLE = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER_SAMPLE = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"

EXPECTED_CORE_CODES = [100, 101, 200, 514, 203, 210, 300, 310, 9000]


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_read_dft_does_not_raise(sample: Path):
    dft = read_dft(sample)
    assert dft.path == sample
    assert len(dft.sections) > 30


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_core_sections_present_in_order(sample: Path):
    dft = read_dft(sample)
    codes = dft.section_codes
    positions = [codes.index(c) for c in EXPECTED_CORE_CODES]
    assert positions == sorted(positions), "core sections out of order"


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_last_section_is_binary_preview(sample: Path):
    dft = read_dft(sample)
    last = dft.sections[-1]
    assert last.code == 9000
    assert last.is_binary


def test_header_contains_version_strings():
    dft = read_dft(PUNCH_SAMPLE)
    joined = " ".join(dft.header_lines)
    assert "gKad" in joined
    assert "cncKad" in joined


def test_split_sections_header_only_when_no_markers():
    header, sections = split_sections("just\nplain\ntext")
    assert header == ["just", "plain", "text"]
    assert sections == []


def test_split_sections_basic_marker():
    header, sections = split_sections("pre\n[100]\nA\nB\n[200]\nC")
    assert header == ["pre"]
    assert [s.code for s in sections] == [100, 200]
    assert sections[0].lines == ["A", "B"]
    assert sections[1].lines == ["C"]
