"""Convert a DXF contour into a punching or laser DFT file."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from core.dxf_reader import read_dxf_geometry
from core.generator_laser import generate_laser_dft, write_laser_dft
from core.generator_punching import generate_punching_dft, write_punching_dft
from core.models import DFTFile
from core.transform import to_sheet_space


def dxf_to_dft(
    dxf_path: Path | str,
    *,
    machine_type: Literal["punching", "laser"],
    material: str = "YWL_HLB_V3",
    stop_spacing: float = 300.0,
) -> DFTFile:
    """Read DXF contour, translate to sheet space, generate a DFTFile."""
    world = read_dxf_geometry(dxf_path)
    if not world:
        raise ValueError(f"no contour geometry in {dxf_path}")
    sheet, tf = to_sheet_space(world)

    if machine_type == "punching":
        return generate_punching_dft(
            sheet,
            width=tf.width,
            height=tf.height,
            material=material,
            origin_offset=tf.origin_offset,
        )
    if machine_type == "laser":
        return generate_laser_dft(
            sheet,
            width=tf.width,
            height=tf.height,
            material=material,
            origin_offset=tf.origin_offset,
            stop_spacing=stop_spacing,
        )
    raise ValueError(f"machine_type must be punching|laser, got {machine_type!r}")


def convert_dxf_to_dft_file(
    dxf_path: Path | str,
    output_path: Path | str,
    *,
    machine_type: Literal["punching", "laser"],
    material: str = "YWL_HLB_V3",
    stop_spacing: float = 300.0,
    dft: DFTFile | None = None,
) -> Path:
    if dft is None:
        dft = dxf_to_dft(
            dxf_path,
            machine_type=machine_type,
            material=material,
            stop_spacing=stop_spacing,
        )
    if machine_type == "punching":
        return write_punching_dft(dft, output_path)
    return write_laser_dft(dft, output_path)
