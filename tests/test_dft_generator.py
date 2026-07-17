"""Tests for DFT UTF-16 LE writer / basic generator."""

from pathlib import Path

import pytest

from core.dft_generator import (
    DFTGenerator,
    encode_dft_bytes,
    format_dft_text,
    format_machine_config,
    write_dft,
    write_raw_dft,
)
from core.dft_parser import parse_dft, read_dft
from core.models import DFTLine
from core.validator import compare_dft_files

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"


def test_encode_utf16_le_bom_crlf():
    data = encode_dft_bytes("a\nb")
    assert data[:2] == b"\xff\xfe"
    # 'a' \r \n 'b' in UTF-16 LE
    assert b"\r\x00\n\x00" in data


def test_write_raw_roundtrip_text_sections(tmp_path: Path):
    raw = read_dft(PUNCH)
    out = tmp_path / "roundtrip.dft"
    write_raw_dft(raw, out, skip_binary=True)

    # Re-read: BOM + UTF-16, sections present, no binary 9000
    again = read_dft(out)
    assert again.header_lines[0].startswith("gKad")
    assert 200 in again.section_codes
    assert 300 in again.section_codes
    assert 9000 not in again.section_codes

    # Text sections (non-empty) match after stripping trailing empties differences on last
    orig = {s.code: [ln.rstrip("\r") for ln in s.lines if True] for s in raw.sections if s.code != 9000}
    new = {s.code: s.lines for s in again.sections}
    for code, lines in orig.items():
        assert code in new
        # Compare non-trailing-empty content
        a = "\n".join(lines).rstrip("\n")
        b = "\n".join(new[code]).rstrip("\n")
        assert a == b, f"section [{code}] mismatch"


def test_write_parsed_dft_preserves_geometry(tmp_path: Path):
    dft = parse_dft(PUNCH)
    out = tmp_path / "from_model.dft"
    write_dft(dft, out)

    again = parse_dft(out)
    assert again.machine_type == "punching"
    assert again.material.name == "YWL_HLB_V3"
    assert again.geometry.line_count == dft.geometry.line_count
    assert len(again.geometry.lines) == len(dft.geometry.lines)
    for a, b in zip(dft.geometry.lines, again.geometry.lines):
        assert (a.x1, a.y1, a.x2, a.y2) == pytest.approx((b.x1, b.y1, b.x2, b.y2))


def test_write_parsed_compare_geometry_only(tmp_path: Path):
    dft = parse_dft(PUNCH)
    out = tmp_path / "cmp.dft"
    write_dft(dft, out)
    result = compare_dft_files(PUNCH, out, check_parameters=False)
    assert result.ok
    assert result.matched_lines == result.reference_line_count


def test_format_machine_config_from_flags():
    from core.models import MachineConfig

    cfg = MachineConfig(
        machine_type="laser",
        extent_width=100.0,
        extent_height=200.0,
        flags={"I": ["0", "1"], "E": ["0", "0", "100", "200"], "V": ["1", "2", "0", "1", "1"], "X": ["ENDSHEET"]},
    )
    lines = format_machine_config(cfg)
    assert lines[0] == "/I 0 1"
    assert any(ln.startswith("/E ") for ln in lines)
    assert lines[-2] == "/X ENDSHEET" or "/X ENDSHEET" in lines


def test_generator_punching_scaffold(tmp_path: Path):
    gen = DFTGenerator("punching")
    segs = [
        DFTLine(0, 0, 100, 0),
        DFTLine(100, 0, 100, 50),
        DFTLine(100, 50, 0, 50),
        DFTLine(0, 50, 0, 0),
    ]
    dft = gen.generate(segs, width=100, height=50)
    assert dft.machine_type == "punching"
    assert dft.machine_config.flags["I"] == ["0", "0"]
    assert dft.machine_config.flags["V"][0] == "0"
    assert "110000" in " ".join(dft.machine_config.flags["S"])
    assert dft.geometry.line_count == 4

    out = tmp_path / "gen_punch.dft"
    gen.write(dft, out)
    again = parse_dft(out)
    assert again.machine_type == "punching"
    assert again.geometry.line_count == 4
    assert again.bend_params.k_factor == pytest.approx(0.4)
    assert again.material.name == "YWL_HLB_V3"
    assert 350 not in [s.code for s in again.other_sections]


def test_generator_laser_scaffold(tmp_path: Path):
    gen = DFTGenerator("laser")
    segs = [DFTLine(0, 0, 10, 0), DFTLine(10, 0, 10, 10)]
    dft = gen.generate(segs, width=10, height=10)
    assert dft.machine_type == "laser"
    assert dft.machine_config.flags["I"] == ["0", "1"]
    assert "79999" in " ".join(dft.machine_config.flags["S"])
    assert any(s.code == 350 for s in dft.other_sections)

    out = tmp_path / "gen_laser.dft"
    write_dft(dft, out)
    # Structural read must see [350]
    raw = read_dft(out)
    assert 350 in raw.section_codes
    again = parse_dft(out)
    assert again.machine_type == "laser"


def test_format_dft_text_contains_markers():
    dft = parse_dft(LASER)
    text = format_dft_text(dft)
    assert "[200]" in text
    assert "[300]" in text
    assert "[514]" in text
    assert "[9000]" not in text  # skipped binary by default
