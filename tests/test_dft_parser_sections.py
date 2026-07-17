"""Tests for semantic DFT section parsing ([200], [210], [514])."""

from pathlib import Path

import pytest

from core.dft_parser import (
    parse_bend_params,
    parse_dft,
    parse_machine_config,
    parse_material,
)
from core.models import MachineConfig

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH_SAMPLE = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER_SAMPLE = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"


def test_parse_machine_config_punching_unit():
    cfg = parse_machine_config(
        [
            "/I 0 0",
            "/E 0 0 750.00291 871.00306 ",
            "/S 770 956 10",
            "/V 0 2 0 1 1",
            "/X ENDSHEET",
            "",
        ]
    )
    assert cfg.machine_type == "punching"
    assert cfg.extent_width == pytest.approx(750.00291)
    assert cfg.extent_height == pytest.approx(871.00306)
    assert cfg.flags["I"] == ["0", "0"]
    assert cfg.flags["V"] == ["0", "2", "0", "1", "1"]
    assert cfg.flags["X"] == ["ENDSHEET"]


def test_parse_machine_config_laser_unit():
    cfg = parse_machine_config(["/I 0 1", "/E 0 0 100 200", "/X ENDSHEET"])
    assert cfg.machine_type == "laser"
    assert cfg.extent_width == 100.0
    assert cfg.extent_height == 200.0


def test_parse_bend_params_unit():
    bend = parse_bend_params(
        [
            "KFactor 0.400000",
            "bendCompensationFactorMode 4",
            "BendPunchRadius 1.000000",
            "BendVOpen 1.000000",
            "BendInnerRadius 0.000000",
            "BendDieSelMode 1",
            "",
        ]
    )
    assert bend.k_factor == pytest.approx(0.4)
    assert bend.bend_compensation_factor_mode == 4
    assert bend.bend_punch_radius == pytest.approx(1.0)
    assert bend.bend_v_open == pytest.approx(1.0)
    assert bend.bend_inner_radius == pytest.approx(0.0)
    assert bend.bend_die_sel_mode == 1


def test_parse_material_unit():
    mat = parse_material(['2 0 1 "YWL_HLB_V3" R', ""])
    assert mat.name == "YWL_HLB_V3"
    assert len(mat.raw_lines) == 2


def test_parse_material_missing_quotes():
    mat = parse_material(["2 0 1 YWL_HLB_V3 R"])
    assert mat.name == ""


@pytest.mark.parametrize(
    "sample,expected_type",
    [(PUNCH_SAMPLE, "punching"), (LASER_SAMPLE, "laser")],
)
def test_parse_dft_machine_type(sample: Path, expected_type: str):
    dft = parse_dft(sample)
    assert dft.path == sample
    assert dft.machine_type == expected_type
    assert dft.machine_config.machine_type == expected_type


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_parse_dft_extent_and_flags(sample: Path):
    dft = parse_dft(sample)
    cfg: MachineConfig = dft.machine_config
    assert cfg.extent_width == pytest.approx(750.00291)
    assert cfg.extent_height == pytest.approx(871.00306)
    assert "S" in cfg.flags
    assert "V" in cfg.flags
    assert cfg.flags["X"] == ["ENDSHEET"]


@pytest.mark.parametrize("sample", [PUNCH_SAMPLE, LASER_SAMPLE])
def test_parse_dft_bend_and_material(sample: Path):
    dft = parse_dft(sample)
    assert dft.bend_params.k_factor == pytest.approx(0.4)
    assert dft.bend_params.bend_die_sel_mode == 1
    assert dft.material.name == "YWL_HLB_V3"


def test_parse_dft_header_versions():
    dft = parse_dft(PUNCH_SAMPLE)
    assert "gKad" in dft.header.gkad_version
    assert "cncKad" in dft.header.cnckad_version


def test_parse_dft_other_sections_exclude_parsed():
    dft = parse_dft(PUNCH_SAMPLE)
    codes = {s.code for s in dft.other_sections}
    assert 200 not in codes
    assert 210 not in codes
    assert 300 not in codes
    assert 514 not in codes
    assert 100 in codes
    assert 9000 in codes


def test_punch_vs_laser_sheet_and_v_flags_differ():
    punch = parse_dft(PUNCH_SAMPLE)
    laser = parse_dft(LASER_SAMPLE)
    assert punch.machine_config.flags["V"] == ["0", "2", "0", "1", "1"]
    assert laser.machine_config.flags["V"] == ["1", "2", "0", "1", "1"]
    # /S token that differs between punch (~110000) and laser (~80000)
    punch_s = " ".join(punch.machine_config.flags["S"])
    laser_s = " ".join(laser.machine_config.flags["S"])
    assert "110000" in punch_s
    assert "79999" in laser_s
