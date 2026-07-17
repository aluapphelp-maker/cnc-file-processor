"""Tests for DFT comparison / validator."""

from pathlib import Path

from click.testing import CliRunner

from core.validator import compare_dft_files
from tools.compare_dft import main as compare_cli

FIXTURES = Path(__file__).parent / "fixtures"
PUNCH = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"
PUNCH_OTHER = FIXTURES / "punching" / "(haz-26-643) 1BE02.dft"


def test_compare_identical_file():
    result = compare_dft_files(PUNCH, PUNCH)
    assert result.ok
    assert result.matched_lines == result.reference_line_count
    assert not result.parameter_diffs
    assert not result.geometry_mismatches


def test_compare_punch_vs_laser_same_part_geometry_only():
    """Same part: geometry matches; machine parameters differ."""
    result = compare_dft_files(PUNCH, LASER, check_parameters=True)
    assert not result.ok
    assert any("machine_type" in d for d in result.parameter_diffs)
    geo_only = compare_dft_files(PUNCH, LASER, check_parameters=False)
    assert geo_only.ok
    assert geo_only.matched_lines == geo_only.reference_line_count


def test_compare_different_parts_differ():
    result = compare_dft_files(PUNCH, PUNCH_OTHER, check_parameters=False)
    assert not result.ok
    assert result.geometry_mismatches


def test_compare_cli_match():
    runner = CliRunner()
    result = runner.invoke(compare_cli, [str(PUNCH), str(PUNCH), "--quiet"])
    assert result.exit_code == 0
    assert "MATCH" in result.output


def test_compare_cli_diff():
    runner = CliRunner()
    result = runner.invoke(compare_cli, [str(PUNCH), str(LASER), "--quiet"])
    assert result.exit_code == 1
    assert "DIFF" in result.output
