"""Tests for DXF→DFT conversion, transform, and batch validation helpers."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from core.dxf_reader import read_dxf_geometry
from core.dxf_to_dft import convert_dxf_to_dft_file, dxf_to_dft
from core.dft_parser import parse_dft, read_dft
from core.transform import to_sheet_space
from core.validator import compare_dft_files, match_lines_unordered
from core.geometry import Line, Point
from tools.dxf_to_dft import main as dxf_cli
from tools.batch_process import find_reference, render_report_md, validate_one, PartResult

FIXTURES = Path(__file__).parent / "fixtures"
DXF = FIXTURES / "dxf" / "1BE01.dxf"
PUNCH_REF = FIXTURES / "punching" / "(haz-26-643) 1BE01.dft"
LASER_REF = FIXTURES / "laser" / "(haz-26-643) 1BE01.dft"


def test_to_sheet_space_zero_origin():
    segs = read_dxf_geometry(DXF)
    sheet, tf = to_sheet_space(segs)
    assert tf.width == pytest.approx(750.003, abs=0.01)
    assert tf.height == pytest.approx(871.003, abs=0.01)
    xs = [c for s in sheet for c in (s.start.x, s.end.x)]
    ys = [c for s in sheet for c in (s.start.y, s.end.y)]
    assert min(xs) == pytest.approx(0.0, abs=1e-6)
    assert min(ys) == pytest.approx(0.0, abs=1e-6)


def test_dxf_to_dft_punching(tmp_path: Path):
    dft = dxf_to_dft(DXF, machine_type="punching")
    assert dft.machine_type == "punching"
    assert dft.geometry.line_count > 0
    assert dft.machine_config.extent_width == pytest.approx(750.003, abs=0.01)

    out = tmp_path / "1BE01_punch.dft"
    convert_dxf_to_dft_file(DXF, out, machine_type="punching", dft=dft)
    again = parse_dft(out)
    assert again.machine_type == "punching"
    assert again.geometry.line_count == dft.geometry.line_count


def test_dxf_to_dft_laser_has_stops(tmp_path: Path):
    out = tmp_path / "1BE01_laser.dft"
    convert_dxf_to_dft_file(DXF, out, machine_type="laser", stop_spacing=200.0)
    raw = read_dft(out)
    assert 350 in raw.section_codes
    assert any("MicroJoint" in ln for ln in raw.first(350).lines)


def test_generated_covers_factory_geometry(tmp_path: Path):
    out = tmp_path / "cov.dft"
    convert_dxf_to_dft_file(DXF, out, machine_type="punching")
    result = compare_dft_files(
        PUNCH_REF,
        out,
        unordered=True,
        min_coverage=0.90,
        check_parameters=True,
        tolerance=0.05,
    )
    assert result.reference_coverage >= 0.90
    assert result.ok


def test_match_lines_unordered_basic():
    a = [Line(Point(0, 0), Point(1, 0)), Line(Point(1, 0), Point(1, 1))]
    b = [Line(Point(1, 1), Point(1, 0)), Line(Point(0, 0), Point(1, 0))]  # reversed order + reverse dir
    matched, miss_a, miss_b = match_lines_unordered(a, b, tolerance=0.01)
    assert matched == 2
    assert miss_a == []
    assert miss_b == []


def test_dxf_cli(tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "cli.dft"
    result = runner.invoke(
        dxf_cli,
        [str(DXF), "--type", "laser", "-o", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_find_reference_and_validate_one(tmp_path: Path):
    ref = find_reference(FIXTURES / "punching", "1BE01")
    assert ref is not None
    r = validate_one(
        DXF,
        machine_type="punching",
        reference_dir=FIXTURES / "punching",
        output_dir=tmp_path,
        tolerance=0.05,
        min_coverage=0.90,
    )
    assert r.ok
    assert r.coverage >= 0.90


def test_render_report_md():
    md = render_report_md(
        [
            PartResult("1BE01", "punching", True, 1.0, 60, 60, 68),
            PartResult("1BE01", "laser", False, 0.5, 30, 60, 68, parameter_diffs=["x"]),
        ]
    )
    assert "Batch Validation Report" in md
    assert "1BE01" in md
