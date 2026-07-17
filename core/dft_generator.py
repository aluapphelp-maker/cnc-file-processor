"""Write CncKad DFT files (UTF-16 LE + BOM, CRLF).

Phase-2 basic generator: emit a well-formed DFT from a typed ``DFTFile``
(or a structural ``RawDFT``). Punching/laser tool-path synthesis and
MicroJoint injection live in later modules; this module focuses on encoding
and section formatting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from core.dft_parser import RawDFT, RawSection
from core.models import (
    BendParams,
    DFTFile,
    DFTHeader,
    DFTLine,
    DFTSection,
    GeometrySection,
    MachineConfig,
    MachineType,
    MaterialSpec,
)

_BOM = b"\xff\xfe"

# Canonical emission order for known sections (factory convention).
_SECTION_ORDER = [
    100,
    101,
    200,
    514,
    203,
    210,
    300,
    350,  # laser-only MicroJoints
    310,
    505,
    400,
    410,
    500,
    501,
    502,
    503,
    509,
    320,
    321,
    322,
    995,
    998,
    996,
    3000,
    4010,
    1020,
    1060,
    1150,
    1100,
    1101,
    1102,
    1200,
    1210,
    1705,
    4600,
    4610,
    1700,
    9000,
]

_DEFAULT_HEADER = DFTHeader(
    gkad_version="gKad 25.00",
    cnckad_version="cncKad Version 23.3.346",
    raw_lines=["gKad 25.00", "cncKad Version 23.3.346", "None", ""],
)

_DEFAULT_BEND = BendParams(
    k_factor=0.4,
    bend_compensation_factor_mode=4,
    bend_punch_radius=1.0,
    bend_v_open=1.0,
    bend_inner_radius=0.0,
    bend_die_sel_mode=1,
)

# Factory-derived /S and other [200] flags (token lists, excluding /I /E /X).
_PUNCH_FLAGS: dict[str, list[str]] = {
    "C": ["0", "0", "0", "0", "-1", "0", "0", "0", "0", "0", "0", "-1", "0", "0"],
    "S": [
        "770.00291",
        "956.00306",
        "10",
        "75",
        "2",
        "10",
        "10",
        "0",
        "0",
        "1",
        "20",
        "110000.00576",
        "0",
        "0",
        "1",
        "1",
        "0",
        "3",
        "4",
        "0",
        "20",
        "110000.00576",
        "0",
        "2",
        "0",
        "1",
        "0",
        "-1",
        "0",
        "0",
        "200",
        "0",
        "3",
        "0",
        "3",
        "0",
        "1",
        "0",
        "0",
        "0",
        "0",
        "0",
        "9999999.9",
        "0",
        "0",
        "0",
        "0",
        "0",
        "400",
        "-1",
    ],
    "Z": ["105", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0.5", "0", "0", "0"],
    "P": [],  # filled from extent
    "D": ["10", "75"],
    "M": ["1", "0", "1"],
    "T": ["0", "0"],
    "F": ["0", "0", "0", "0", "0", "0"],
    "U": ["0", "0"],
    "W": ["0", "0", "1"],
    "L": ["0", "600", "600", "300", "0", "0", "2", "0", "0", "0", "0"],
    "A": [
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "0",
        "1",
        "1",
        "1",
        "0",
        "0",
        "0",
        "0",
        "0",
        "1",
        "9999999.9",
        "9999999.9",
        "1",
    ],
    "Q": ["1"],
    "O": ["0", "1", "0", "0"],
    "G": ["0", "0"],
    "K": ["0"],
    "V": ["0", "2", "0", "1", "1"],
    "B": ["0"],
}

_LASER_FLAGS = {
    **{k: list(v) for k, v in _PUNCH_FLAGS.items()},
    "V": ["1", "2", "0", "1", "1"],
    "S": [
        "770.00291",
        "956.00306",
        "10",
        "75",
        "2",
        "10",
        "10",
        "0",
        "0",
        "1",
        "20",
        "79999.99647",
        "0",
        "0",
        "1",
        "1",
        "1",
        "3",
        "4",
        "0",
        "60",
        "79999.99647",
        "0",
        "2",
        "0",
        "1",
        "0",
        "-1",
        "0",
        "0",
        "200",
        "0",
        "3",
        "2",
        "3",
        "0",
        "1",
        "0",
        "0",
        "0",
        "0",
        "0",
        "9999999.9",
        "0",
        "0",
        "0",
        "0",
        "0",
        "400",
        "-1",
    ],
}

_FLAG_ORDER = list("ICESZPDMTFUWLAQOGKVBX")


def _fmt_num(value: float) -> str:
    """Format a float like factory files (trim trailing zeros)."""
    text = f"{value:.5f}".rstrip("0").rstrip(".")
    return text if text else "0"


def encode_dft_bytes(text: str, *, bom: bool = True) -> bytes:
    """Encode DFT text as UTF-16 LE with CRLF endings (optional BOM)."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
    payload = normalized.encode("utf-16-le")
    return (_BOM + payload) if bom else payload


def write_text_dft(path: Path | str, text: str, *, bom: bool = True) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encode_dft_bytes(text, bom=bom))
    return path


def format_header(header: DFTHeader) -> list[str]:
    if header.raw_lines:
        return list(header.raw_lines)
    lines = []
    if header.gkad_version:
        lines.append(header.gkad_version)
    if header.cnckad_version:
        lines.append(header.cnckad_version)
    lines.extend(["None", ""])
    return lines


def format_machine_config(cfg: MachineConfig) -> list[str]:
    if cfg.raw_lines:
        return list(cfg.raw_lines)

    flags = dict(cfg.flags)
    if "I" not in flags:
        if cfg.machine_type == "laser":
            flags["I"] = ["0", "1"]
        elif cfg.machine_type == "punching":
            flags["I"] = ["0", "0"]
    if "E" not in flags and cfg.extent_width is not None and cfg.extent_height is not None:
        flags["E"] = ["0", "0", _fmt_num(cfg.extent_width), _fmt_num(cfg.extent_height)]
    if "X" not in flags:
        flags["X"] = ["ENDSHEET"]

    lines: list[str] = []
    seen: set[str] = set()
    for letter in _FLAG_ORDER:
        if letter not in flags:
            continue
        tokens = flags[letter]
        if letter == "X":
            lines.append(f"/X {' '.join(tokens)}")
        else:
            # Factory often keeps a trailing space on /E /P /U /G
            joined = " ".join(tokens)
            pad = " " if letter in "EPUG" and joined else ""
            lines.append(f"/{letter} {joined}{pad}" if joined else f"/{letter} ")
        seen.add(letter)
    for letter, tokens in flags.items():
        if letter in seen:
            continue
        lines.append(f"/{letter} {' '.join(tokens)}")
    lines.append("")
    return lines


def format_bend_params(bend: BendParams) -> list[str]:
    if bend.raw_lines:
        return list(bend.raw_lines)
    pairs = [
        ("KFactor", bend.k_factor, "{:.6f}"),
        ("bendCompensationFactorMode", bend.bend_compensation_factor_mode, "{}"),
        ("BendPunchRadius", bend.bend_punch_radius, "{:.6f}"),
        ("BendVOpen", bend.bend_v_open, "{:.6f}"),
        ("BendInnerRadius", bend.bend_inner_radius, "{:.6f}"),
        ("BendDieSelMode", bend.bend_die_sel_mode, "{}"),
    ]
    lines: list[str] = []
    for key, value, fmt in pairs:
        if value is None:
            continue
        lines.append(f"{key} {fmt.format(value)}")
    lines.append("")
    return lines


def format_material(material: MaterialSpec) -> list[str]:
    if material.raw_lines:
        return list(material.raw_lines)
    name = material.name or "YWL_HLB_V3"
    return [f'2 0 1 "{name}" R', ""]


def format_geometry(geometry: GeometrySection) -> list[str]:
    """Emit [300] body. Prefer raw_lines (preserves POINTS/CIRCLES/ARCS)."""
    if geometry.raw_lines:
        return list(geometry.raw_lines)

    lines: list[str] = ["LINES", str(len(geometry.lines))]
    for seg in geometry.lines:
        primary = " ".join(
            [_fmt_num(seg.x1), _fmt_num(seg.y1), _fmt_num(seg.x2), _fmt_num(seg.y2), *seg.params]
        )
        lines.append(primary)
        lines.extend(seg.meta_lines)
    # Minimal empty trailing subsections so re-parsers see a full [300]
    lines.extend(["POINTS", "0", "CIRCLES", "0", "ARCS", "0", ""])
    return lines


def _section_body(dft: DFTFile, code: int) -> list[str] | None:
    if code == 200:
        return format_machine_config(dft.machine_config)
    if code == 210:
        return format_bend_params(dft.bend_params)
    if code == 514:
        return format_material(dft.material)
    if code == 300:
        return format_geometry(dft.geometry)
    for sec in dft.other_sections:
        if sec.code == code:
            return list(sec.raw_lines)
    return None


def assemble_dft_lines(dft: DFTFile, *, skip_binary: bool = True) -> list[str]:
    """Assemble header + ordered section markers into text lines (LF endings)."""
    out = list(format_header(dft.header))
    emitted: set[int] = set()

    other_by_code = {s.code: s for s in dft.other_sections}
    # Prefer first occurrence order from other_sections for unknown codes.
    extra_order = [s.code for s in dft.other_sections if s.code not in _SECTION_ORDER]

    for code in list(_SECTION_ORDER) + extra_order:
        if code in emitted:
            continue
        if skip_binary and code == 9000:
            continue
        body = _section_body(dft, code)
        if body is None:
            continue
        out.append(f"[{code}]")
        out.extend(body)
        emitted.add(code)

    return out


def format_dft_text(dft: DFTFile, *, skip_binary: bool = True) -> str:
    lines = assemble_dft_lines(dft, skip_binary=skip_binary)
    return "\n".join(lines) + ("\n" if lines and not lines[-1].endswith("\n") else "")


def write_dft(dft: DFTFile, path: Path | str, *, skip_binary: bool = True, bom: bool = True) -> Path:
    """Write a typed DFTFile as UTF-16 LE."""
    text = format_dft_text(dft, skip_binary=skip_binary)
    # format_dft_text joins with \n; encode_dft_bytes converts to CRLF
    return write_text_dft(path, text if text.endswith("\n") else text + "\n", bom=bom)


def format_raw_dft_text(raw: RawDFT, *, skip_binary: bool = True) -> str:
    lines = list(raw.header_lines)
    for section in raw.sections:
        if skip_binary and (section.code == 9000 or section.is_binary):
            continue
        lines.append(f"[{section.code}]")
        lines.extend(section.lines)
    return "\n".join(lines) + "\n"


def write_raw_dft(raw: RawDFT, path: Path | str, *, skip_binary: bool = True, bom: bool = True) -> Path:
    """Write a structural RawDFT (text sections only by default)."""
    return write_text_dft(path, format_raw_dft_text(raw, skip_binary=skip_binary), bom=bom)


def default_machine_config(
    machine_type: MachineType,
    *,
    width: float,
    height: float,
) -> MachineConfig:
    """Build a [200] config from factory-derived defaults."""
    if machine_type not in ("punching", "laser"):
        raise ValueError(f"machine_type must be punching|laser, got {machine_type!r}")
    base = _LASER_FLAGS if machine_type == "laser" else _PUNCH_FLAGS
    flags = {k: list(v) for k, v in base.items()}
    flags["I"] = ["0", "1"] if machine_type == "laser" else ["0", "0"]
    flags["E"] = ["0", "0", _fmt_num(width), _fmt_num(height)]
    flags["P"] = [_fmt_num(width), _fmt_num(height), "15", "15"]
    # Keep /S width/height loosely aligned with extent (first two tokens)
    if len(flags["S"]) >= 2:
        flags["S"][0] = _fmt_num(width + 20)
        flags["S"][1] = _fmt_num(height + 85)
    flags["X"] = ["ENDSHEET"]
    return MachineConfig(
        machine_type=machine_type,
        extent_width=width,
        extent_height=height,
        flags=flags,
    )


def default_line_params() -> list[str]:
    return ["4", "0", "0", "0", "-1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "1"]


def default_toolpath_meta(origin_offset: float = 0.0) -> list[str]:
    off = f"{origin_offset:.6f}"
    zeros = " ".join(["0.000000"] * 11)
    return [
        "1 0 0 0 15 0",  # placeholder direction/length; refined by punching/laser generators
        f"3DToolPathPoint1 = {off} {zeros}",
        f"3DToolPathPoint2 = {off} {zeros}",
    ]


class DFTGenerator:
    """Scaffold a DFTFile for a given machine type, then write it."""

    def __init__(self, machine_type: Literal["punching", "laser"]):
        if machine_type not in ("punching", "laser"):
            raise ValueError(f"machine_type must be punching|laser, got {machine_type!r}")
        self.machine_type: MachineType = machine_type

    def generate(
        self,
        segments: list[DFTLine],
        *,
        width: float,
        height: float,
        material: str = "YWL_HLB_V3",
        origin_offset: float = 0.0,
    ) -> DFTFile:
        """Create a minimal typed DFT with header/[200]/[210]/[514]/[300] LINES."""
        lines: list[DFTLine] = []
        for seg in segments:
            meta = list(seg.meta_lines) if seg.meta_lines else default_toolpath_meta(origin_offset)
            params = list(seg.params) if seg.params else default_line_params()
            lines.append(
                DFTLine(
                    x1=seg.x1,
                    y1=seg.y1,
                    x2=seg.x2,
                    y2=seg.y2,
                    params=params,
                    meta_lines=meta,
                )
            )

        geometry = GeometrySection(line_count=len(lines), lines=lines)
        # Force formatter path (no raw) so LINES are regenerated cleanly.
        geometry.raw_lines = []

        other: list[DFTSection] = [
            DFTSection(code=100, raw_lines=["0", ""]),
            DFTSection(code=101, raw_lines=["0", ""]),
            DFTSection(code=203, raw_lines=[""]),
            DFTSection(
                code=310,
                raw_lines=["LINES", "0", "POINTS", "0", "CIRCLES", "0", "ARCS", "0", ""],
            ),
        ]
        if self.machine_type == "laser":
            other.append(DFTSection(code=350, raw_lines=[""]))

        return DFTFile(
            header=_DEFAULT_HEADER,
            machine_config=default_machine_config(self.machine_type, width=width, height=height),
            material=MaterialSpec(name=material),
            bend_params=BendParams(
                k_factor=_DEFAULT_BEND.k_factor,
                bend_compensation_factor_mode=_DEFAULT_BEND.bend_compensation_factor_mode,
                bend_punch_radius=_DEFAULT_BEND.bend_punch_radius,
                bend_v_open=_DEFAULT_BEND.bend_v_open,
                bend_inner_radius=_DEFAULT_BEND.bend_inner_radius,
                bend_die_sel_mode=_DEFAULT_BEND.bend_die_sel_mode,
            ),
            geometry=geometry,
            other_sections=other,
        )

    def write(self, dft: DFTFile, path: Path | str) -> Path:
        return write_dft(dft, path)
