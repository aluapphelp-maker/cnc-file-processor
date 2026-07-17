"""Data models for CncKad DFT files.

Fields we do not fully reverse-engineer yet are kept as raw token lists
so the parser can store them without guessing semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

MachineType = Literal["punching", "laser", "unknown"]


@dataclass
class DFTHeader:
    """File prologue before section markers."""

    gkad_version: str = ""
    cnckad_version: str = ""
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class MachineConfig:
    """Section [200] machine / sheet settings.

    Known flags:
      /I 0 0 → punching, /I 0 1 → laser
      /E → sheet extent (width, height)
      /X ENDSHEET → end of sheet block
    """

    machine_type: MachineType = "unknown"
    extent_width: float | None = None
    extent_height: float | None = None
    # flag letter → remaining tokens as strings (preserve exact text)
    flags: dict[str, list[str]] = field(default_factory=dict)
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class BendParams:
    """Section [210] bend-related parameters."""

    k_factor: float | None = None
    bend_compensation_factor_mode: int | None = None
    bend_punch_radius: float | None = None
    bend_v_open: float | None = None
    bend_inner_radius: float | None = None
    bend_die_sel_mode: int | None = None
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class MaterialSpec:
    """Section [514] material / tool table reference."""

    name: str = ""
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class ToolParams:
    """Section [203] tool parameter block (opaque for now)."""

    raw_lines: list[str] = field(default_factory=list)


@dataclass
class DFTLine:
    """One geometry row from section [300] LINES.

    Coordinates are the first four numbers on the primary data line.
    Remaining tokens and following metadata lines are kept raw.
    """

    x1: float
    y1: float
    x2: float
    y2: float
    params: list[str] = field(default_factory=list)
    meta_lines: list[str] = field(default_factory=list)


@dataclass
class GeometrySection:
    """Section [300] LINES."""

    line_count: int = 0
    lines: list[DFTLine] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class DFTSection:
    """Any section we have not modeled yet (e.g. [100], [101], [310])."""

    code: int
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class DFTFile:
    """Parsed CncKad DFT document."""

    path: Path | None = None
    header: DFTHeader = field(default_factory=DFTHeader)
    machine_config: MachineConfig = field(default_factory=MachineConfig)
    material: MaterialSpec = field(default_factory=MaterialSpec)
    tool_params: ToolParams = field(default_factory=ToolParams)
    bend_params: BendParams = field(default_factory=BendParams)
    geometry: GeometrySection = field(default_factory=GeometrySection)
    other_sections: list[DFTSection] = field(default_factory=list)

    @property
    def machine_type(self) -> MachineType:
        return self.machine_config.machine_type
