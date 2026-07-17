#!/usr/bin/env python3
"""CLI: convert a DXF contour to a punching or laser DFT."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click
from rich.console import Console

from core.dxf_to_dft import convert_dxf_to_dft_file, dxf_to_dft


@click.command()
@click.argument("input_dxf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--type",
    "machine_type",
    type=click.Choice(["punching", "laser"], case_sensitive=False),
    required=True,
    help="Target machine type.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output .dft path (default: output/<stem>_<type>.dft).",
)
@click.option("--material", default="YWL_HLB_V3", show_default=True)
@click.option(
    "--stop-spacing",
    default=300.0,
    show_default=True,
    help="Laser MicroJoint spacing in mm (laser only).",
)
def main(
    input_dxf: Path,
    machine_type: str,
    output: Path | None,
    material: str,
    stop_spacing: float,
) -> None:
    """Convert INPUT_DXF contour (KNA) into a CncKad DFT file."""
    console = Console()
    out = output or (_ROOT / "output" / f"{input_dxf.stem}_{machine_type}.dft")
    mtype = machine_type.lower()
    dft = dxf_to_dft(
        input_dxf,
        machine_type=mtype,  # type: ignore[arg-type]
        material=material,
        stop_spacing=stop_spacing,
    )
    path = convert_dxf_to_dft_file(
        input_dxf,
        out,
        machine_type=mtype,  # type: ignore[arg-type]
        material=material,
        stop_spacing=stop_spacing,
        dft=dft,
    )
    console.print(
        f"[green]Wrote[/green] {path}\n"
        f"  type={machine_type}  lines={dft.geometry.line_count}  "
        f"extent={dft.machine_config.extent_width:.3f}x{dft.machine_config.extent_height:.3f}"
    )


if __name__ == "__main__":
    main()
