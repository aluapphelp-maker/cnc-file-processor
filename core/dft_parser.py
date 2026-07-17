"""Reading and parsing of CncKad DFT files.

Structural layer (`read_dft` / `split_sections`):
  Split a DFT into header + ordered `[NNN]` sections without interpreting
  contents.

Semantic layer (`parse_dft` and section helpers):
  Interpret [200] machine config, [210] bend params, [514] material, and
  [300] LINES coordinates into the typed models in `core.models`.
  POINTS / CIRCLES / tool encoding inside [300] are left raw for later.

Format notes:
  - Files are UTF-16 (LE), often with a BOM, CRLF line endings.
  - The last section, `[9000]`, is a raw binary preview bitmap and is
    NOT valid UTF-16 text. We decode with errors="replace" so this
    never raises; callers should treat sections containing replacement
    characters (U+FFFD) as opaque/binary rather than parsing them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from core.models import (
    BendParams,
    DFTFile,
    DFTHeader,
    DFTLine,
    DFTSection,
    GeometrySection,
    MachineConfig,
    MaterialSpec,
    MachineType,
)

# Sections fully (or partially) promoted into DFTFile typed fields.
_PARSED_SECTION_CODES = frozenset({200, 210, 300, 514})

_SECTION_RE = re.compile(r"^\[(\d+)\]$")
_FLAG_RE = re.compile(r"^/([A-Za-z])\s*(.*)$")
_MATERIAL_NAME_RE = re.compile(r'"([^"]*)"')
_BOM = b"\xff\xfe"

# [210] key → BendParams field name
_BEND_KEYS = {
    "KFactor": "k_factor",
    "bendCompensationFactorMode": "bend_compensation_factor_mode",
    "BendPunchRadius": "bend_punch_radius",
    "BendVOpen": "bend_v_open",
    "BendInnerRadius": "bend_inner_radius",
    "BendDieSelMode": "bend_die_sel_mode",
}

_INT_BEND_FIELDS = {
    "bend_compensation_factor_mode",
    "bend_die_sel_mode",
}


@dataclass
class RawSection:
    code: int
    lines: list[str] = field(default_factory=list)

    @property
    def is_binary(self) -> bool:
        """Heuristic: any replacement character means non-text payload."""
        return any("\ufffd" in line for line in self.lines)


@dataclass
class RawDFT:
    """Result of splitting a DFT file into header + raw sections."""

    path: Path
    header_lines: list[str]
    sections: list[RawSection]

    def first(self, code: int) -> RawSection | None:
        return next((s for s in self.sections if s.code == code), None)

    def all(self, code: int) -> list[RawSection]:
        return [s for s in self.sections if s.code == code]

    @property
    def section_codes(self) -> list[int]:
        return [s.code for s in self.sections]


def read_dft_text(path: Path | str) -> str:
    """Decode a CncKad DFT file (UTF-16 LE, optional BOM, CRLF)."""
    data = Path(path).read_bytes()
    if data.startswith(_BOM):
        data = data[len(_BOM) :]
    return data.decode("utf-16-le", errors="replace")


def split_sections(text: str) -> tuple[list[str], list[RawSection]]:
    """Split decoded DFT text into header lines + ordered section blocks."""
    lines = text.replace("\r\n", "\n").split("\n")

    header: list[str] = []
    sections: list[RawSection] = []
    current: RawSection | None = None

    for line in lines:
        match = _SECTION_RE.match(line.strip())
        if match:
            current = RawSection(code=int(match.group(1)))
            sections.append(current)
            continue
        if current is None:
            header.append(line)
        else:
            current.lines.append(line)

    return header, sections


def read_dft(path: Path | str) -> RawDFT:
    path = Path(path)
    text = read_dft_text(path)
    header, sections = split_sections(text)
    return RawDFT(path=path, header_lines=header, sections=sections)


def parse_header(lines: list[str]) -> DFTHeader:
    """Parse the prologue before the first `[NNN]` marker."""
    gkad = ""
    cnckad = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("gKad"):
            gkad = stripped
        elif stripped.startswith("cncKad"):
            cnckad = stripped
    return DFTHeader(gkad_version=gkad, cnckad_version=cnckad, raw_lines=list(lines))


def detect_machine_type(i_tokens: list[str]) -> MachineType:
    """Map `/I` tokens to punching / laser.

    Factory convention: `/I 0 0` → punching, `/I 0 1` → laser.
    """
    if not i_tokens:
        return "unknown"
    try:
        last = int(float(i_tokens[-1]))
    except ValueError:
        return "unknown"
    if last == 0:
        return "punching"
    if last == 1:
        return "laser"
    return "unknown"


def parse_machine_config(lines: list[str]) -> MachineConfig:
    """Parse section [200] into MachineConfig."""
    flags: dict[str, list[str]] = {}
    machine_type: MachineType = "unknown"
    extent_width: float | None = None
    extent_height: float | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        match = _FLAG_RE.match(stripped)
        if not match:
            continue
        letter, rest = match.group(1), match.group(2).strip()
        tokens = rest.split() if rest else []
        flags[letter] = tokens

        if letter == "I":
            machine_type = detect_machine_type(tokens)
        elif letter == "E" and len(tokens) >= 2:
            try:
                extent_width = float(tokens[-2])
                extent_height = float(tokens[-1])
            except ValueError:
                pass

    return MachineConfig(
        machine_type=machine_type,
        extent_width=extent_width,
        extent_height=extent_height,
        flags=flags,
        raw_lines=list(lines),
    )


def parse_bend_params(lines: list[str]) -> BendParams:
    """Parse section [210] key/value bend parameters."""
    values: dict[str, float | int] = {}

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        key, raw_value = parts
        field_name = _BEND_KEYS.get(key)
        if field_name is None:
            continue
        try:
            if field_name in _INT_BEND_FIELDS:
                values[field_name] = int(float(raw_value))
            else:
                values[field_name] = float(raw_value)
        except ValueError:
            continue

    return BendParams(raw_lines=list(lines), **values)


def parse_material(lines: list[str]) -> MaterialSpec:
    """Parse section [514] material / tool-table reference."""
    name = ""
    for line in lines:
        match = _MATERIAL_NAME_RE.search(line)
        if match:
            name = match.group(1)
            break
    return MaterialSpec(name=name, raw_lines=list(lines))


def _parse_primary_line(line: str) -> DFTLine | None:
    """Extract x1 y1 x2 y2 (+ remaining params) from a LINES primary row."""
    tokens = line.split()
    if len(tokens) < 4:
        return None
    try:
        x1, y1, x2, y2 = (float(tokens[0]), float(tokens[1]), float(tokens[2]), float(tokens[3]))
    except ValueError:
        return None
    return DFTLine(x1=x1, y1=y1, x2=x2, y2=y2, params=tokens[4:])


def parse_geometry(lines: list[str]) -> GeometrySection:
    """Parse section [300] LINES coordinates (POINTS/CIRCLES left unparsed).

    Factory layout (verified across all fixtures)::

        LINES
        <count N>
        # N blocks of 4 lines:
        x1 y1 x2 y2 <params...>
        <meta...>
        3DToolPathPoint1 = ...
        3DToolPathPoint2 = ...
        POINTS
        ...
    """
    geometry = GeometrySection(raw_lines=list(lines))
    if len(lines) < 2 or lines[0].strip() != "LINES":
        return geometry

    try:
        declared = int(lines[1].strip())
    except ValueError:
        return geometry

    geometry.line_count = declared
    cursor = 2

    for _ in range(declared):
        if cursor >= len(lines):
            break
        primary = _parse_primary_line(lines[cursor])
        if primary is None:
            break
        cursor += 1
        meta_end = min(cursor + 3, len(lines))
        primary.meta_lines = list(lines[cursor:meta_end])
        cursor = meta_end
        geometry.lines.append(primary)

    return geometry


def parse_dft(path: Path | str) -> DFTFile:
    """Parse a DFT file into a typed DFTFile ([200], [210], [514], [300])."""
    raw = read_dft(path)

    machine_config = MachineConfig()
    bend_params = BendParams()
    material = MaterialSpec()
    geometry = GeometrySection()
    other: list[DFTSection] = []

    sec200 = raw.first(200)
    if sec200 is not None:
        machine_config = parse_machine_config(sec200.lines)

    sec210 = raw.first(210)
    if sec210 is not None:
        bend_params = parse_bend_params(sec210.lines)

    sec514 = raw.first(514)
    if sec514 is not None:
        material = parse_material(sec514.lines)

    sec300 = raw.first(300)
    if sec300 is not None:
        geometry = parse_geometry(sec300.lines)

    for section in raw.sections:
        if section.code in _PARSED_SECTION_CODES:
            continue
        other.append(DFTSection(code=section.code, raw_lines=list(section.lines)))

    return DFTFile(
        path=raw.path,
        header=parse_header(raw.header_lines),
        machine_config=machine_config,
        material=material,
        bend_params=bend_params,
        geometry=geometry,
        other_sections=other,
    )
