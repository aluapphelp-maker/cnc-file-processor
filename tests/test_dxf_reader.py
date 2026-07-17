"""Tests for DXF contour reader."""

from pathlib import Path

import pytest

from core.dxf_reader import read_dxf_geometry, read_dxf_polylines, resolve_contour_layer
import ezdxf

FIXTURES = Path(__file__).parent / "fixtures"
DXF_SAMPLE = FIXTURES / "dxf" / "1BE01.dxf"
ALL_DXF = sorted((FIXTURES / "dxf").glob("*.dxf"))


def test_resolve_contour_layer():
    doc = ezdxf.readfile(str(DXF_SAMPLE))
    assert resolve_contour_layer(doc.modelspace()) == "KNA - Contour"


def test_read_dxf_geometry_sample():
    segs = read_dxf_geometry(DXF_SAMPLE)
    assert len(segs) > 0
    assert all(s.length >= 0 for s in segs)


def test_read_dxf_polylines_sample():
    polys = read_dxf_polylines(DXF_SAMPLE)
    assert any(len(p) >= 2 for p in polys)


@pytest.mark.parametrize("path", ALL_DXF, ids=[p.name for p in ALL_DXF])
def test_read_all_dxf_fixtures(path: Path):
    segs = read_dxf_geometry(path)
    assert len(segs) > 0
