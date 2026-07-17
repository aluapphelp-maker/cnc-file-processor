#!/usr/bin/env python3
"""CLI: compare two CncKad DFT files."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click
from rich.console import Console

from core.validator import compare_dft_files


@click.command()
@click.argument("reference", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("other", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--tolerance", default=0.01, show_default=True, help="Coordinate tolerance (mm).")
@click.option(
    "--geometry-only",
    is_flag=True,
    help="Skip parameter comparison (machine type, material, extents).",
)
@click.option("--quiet", is_flag=True, help="Only print MATCH/DIFF status line.")
@click.option(
    "--unordered",
    is_flag=True,
    help="Match geometry regardless of order (for DXF→DFT vs factory).",
)
@click.option(
    "--min-coverage",
    default=1.0,
    show_default=True,
    help="Required fraction of reference lines found when --unordered.",
)
def main(
    reference: Path,
    other: Path,
    tolerance: float,
    geometry_only: bool,
    quiet: bool,
    unordered: bool,
    min_coverage: float,
) -> None:
    """Compare REFERENCE.dft against OTHER.dft."""
    console = Console()
    result = compare_dft_files(
        reference,
        other,
        tolerance=tolerance,
        check_parameters=not geometry_only,
        unordered=unordered,
        min_coverage=min_coverage,
    )
    if quiet:
        console.print("MATCH" if result.ok else "DIFF")
    else:
        console.print(result.summary())
    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
