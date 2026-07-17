"""Smoke tests for DFT dataclasses (no file I/O)."""

from core.models import (
    BendParams,
    DFTFile,
    DFTHeader,
    DFTLine,
    GeometrySection,
    MachineConfig,
)


def test_default_dft_file():
    dft = DFTFile()
    assert dft.machine_type == "unknown"
    assert dft.geometry.line_count == 0
    assert dft.path is None


def test_machine_config_punching():
    cfg = MachineConfig(
        machine_type="punching",
        extent_width=750.0,
        extent_height=871.0,
        flags={"I": ["0", "0"]},
    )
    dft = DFTFile(machine_config=cfg)
    assert dft.machine_type == "punching"
    assert dft.machine_config.extent_width == 750.0


def test_geometry_line():
    line = DFTLine(x1=0.0, y1=0.0, x2=100.0, y2=50.0, params=["4", "0"])
    geo = GeometrySection(line_count=1, lines=[line])
    assert geo.lines[0].x2 == 100.0
    assert len(geo.lines[0].params) == 2


def test_bend_params():
    bend = BendParams(k_factor=0.4, bend_punch_radius=1.0)
    assert bend.k_factor == 0.4


def test_header():
    h = DFTHeader(gkad_version="gKad 25.00", cnckad_version="cncKad Version 23.3.346")
    assert "25.00" in h.gkad_version
