"""Parse every factory DFT fixture without errors."""

from pathlib import Path

import pytest

from core.dft_parser import parse_dft

FIXTURES = Path(__file__).parent / "fixtures"
PUNCHING = sorted((FIXTURES / "punching").glob("*.dft"))
LASER = sorted((FIXTURES / "laser").glob("*.dft"))

ALL_DFTS = [(p, "punching") for p in PUNCHING] + [(p, "laser") for p in LASER]


def test_fixture_counts():
    assert len(PUNCHING) == 48
    assert len(LASER) == 48


@pytest.mark.parametrize("path,expected_type", ALL_DFTS, ids=[p.name for p, _ in ALL_DFTS])
def test_parse_all_factory_dfts(path: Path, expected_type: str):
    dft = parse_dft(path)

    assert dft.path == path
    assert dft.machine_type == expected_type
    assert dft.machine_config.extent_width is not None
    assert dft.machine_config.extent_height is not None
    assert dft.material.name
    assert dft.bend_params.k_factor is not None
    assert dft.geometry.line_count > 0
    assert len(dft.geometry.lines) == dft.geometry.line_count
    assert "gKad" in dft.header.gkad_version
    assert "cncKad" in dft.header.cnckad_version

    for line in dft.geometry.lines:
        assert len(line.meta_lines) == 3
