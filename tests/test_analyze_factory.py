"""Tests for factory analyzer and findings report."""

from pathlib import Path

from tools.analyze_factory_files import analyze_directory, render_findings_md

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_directory():
    analysis = analyze_directory(FIXTURES)
    assert analysis.file_count == 96
    assert analysis.by_machine["punching"] == 48
    assert analysis.by_machine["laser"] == 48
    assert analysis.materials["YWL_HLB_V3"] == 96
    assert min(analysis.line_counts) >= 1
    assert any("7BE01" in a for a in analysis.anomalies)  # known /V outlier


def test_render_findings_md(tmp_path: Path):
    analysis = analyze_directory(FIXTURES)
    md = render_findings_md(analysis)
    assert "Factory DFT Findings" in md
    assert "YWL_HLB_V3" in md
    assert "/I" in md
    out = tmp_path / "findings.md"
    out.write_text(md, encoding="utf-8")
    assert out.exists()
