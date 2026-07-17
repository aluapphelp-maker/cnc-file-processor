# CncKad DFT Format Spec (reverse-engineered)

Scope: the sections needed to read/compare punching & laser DFTs and to
understand tool-path + laser-stop encoding. Derived from 48 punching + 48
laser factory fixtures. See `docs/findings.md` for dataset statistics.

## File encoding

- UTF-16 LE, usually with a BOM, CRLF line endings.
- A prologue (`gKad …`, `cncKad Version …`) precedes the first marker.
- Body is a sequence of `[NNN]` section markers.
- The final `[9000]` section is a **raw binary** preview bitmap (not UTF-16);
  decode the file with `errors="replace"` and treat sections containing
  U+FFFD as opaque.

## Machine-level sections

### `[200]` — machine / sheet config (flag lines `/X …`)

| Flag | Meaning | Punching | Laser |
|------|---------|----------|-------|
| `/I` | machine type | `0 0` | `0 1` |
| `/E` | sheet extent (…, width, height) | shared | shared |
| `/V` | technology variant | `0 2 0 1 1` | `1 2 0 1 1` |
| `/S` | sheet params; token[11] speed-like | ~`110000` | ~`79999` |
| `/X` | `ENDSHEET` terminator | — | — |

### `[514]` — material: quoted name, e.g. `YWL_HLB_V3`.
### `[210]` — bend params: `KFactor`, `BendPunchRadius`, `BendVOpen`, etc.
### `[505]` / `[203]` — tool/model table (`YWL_HLB_V3.MDL`, `E6-XML.MDL`, …).

## `[300]` — geometry + tool path

> **Key finding:** the `[300]` body is *byte-identical* between the punching
> and laser version of the same part. Machine selection is file-level
> (`[200]` + laser-only `[350]`), not per-entity.

Structure: keyword subsections, each with a declared count, then entities.
Every entity ends with exactly two `3DToolPathPoint` lines (record delimiter).
The `3DToolPathPoint` leading value is the part's machine-bed X origin offset
(matches the DXF world→sheet translation), constant per file.

### `LINES` entity (4 lines)

```
x1 y1 x2 y2 <22 params: param[0]=4 (=line type), …, last=1>
<dir_code> <slope> <length> 0 <tool_id> 0
3DToolPathPoint1 = <origin_offset> 0 0 …
3DToolPathPoint2 = <origin_offset> 0 0 …
```

- `length` == Euclidean segment length (verified: 0 mismatches / 2088 segments).
- `tool_id` == `15` throughout (contour tool from the `[505]`/`[203]` table).
- `dir_code` octants (reverse-engineered from geometry):

  | code | dir | code | dir |
  |------|-----|------|-----|
  | 1 | E | 5 | NE |
  | 2 | W | 6 | SE |
  | 3 | N | 7 | NW |
  | 4 | S | 8 | SW |

### `CIRCLES` entity (3 lines)

```
cx cy radius <tool_id> 0 3 0 0 0 -1 0
3DToolPathPoint1 = …
3DToolPathPoint2 = …
```

- All factory circles: `radius = 1.5` (Ø3 mm round-tool hits), `tool_id = 15`.

### `ARCS`, `POINTS`

Counted and delimited the same way; kept raw (not yet fully modeled).

Decoder: `core/tool_analysis.py` (`parse_tool_path`, `summarize_tools`).

## `[350]` — laser stop points (MicroJoints)

Present in **every** laser file, **absent** from every punching file. Encodes
the ~0.7 mm uncut bridges that hold the part to the sheet and act as the
laser's periodic stop/relief points.

```
<entity_index> 0 MicroJoint <t> <width> 1 0 1 0 … ;MicroJoint <t2> <width> …
```

- `entity_index` → index into the `[300]` `LINES` list.
- `t` = parametric position (0..1) along that segment; absolute point is
  `p1 + t·(p2−p1)`.
- `width` = bridge width in mm (always `0.7`).
- Multiple MicroJoints on one segment are `;`-separated.

Dataset: 14–24 MicroJoints per part (mean 18); mean spacing ≈ 221 mm around
the perimeter (the factory's "stop every ~30 cm", same order of magnitude).

Decoder: `core/laser_analysis.py` (`parse_microjoints`, `detect_laser_stops`).

## Generation (Phase 2)

- `core/dft_generator.py` — UTF-16 LE + BOM/CRLF writer, section formatting,
  `DFTGenerator` scaffold.
- `core/generator_punching.py` — contour `[300]` LINES with faithful meta
  (`encode_direction` reproduces all 4176 factory direction codes), plus
  `nibble_positions()` overlap calculation (consecutive hits ≤ tool diameter)
  and optional Ø3 hole CIRCLES.
- `core/generator_laser.py` — same geometry + `plan_microjoints()` injecting
  `[350]` stops at a configurable spacing (default 300 mm). Round-trips through
  `detect_laser_stops`.

## DXF → DFT pipeline

1. Read `KNA - Contour` segments (`core/dxf_reader.py`).
2. Translate world → sheet: subtract contour bbox min
   (`core/transform.py`). Sheet size = bbox width × height.
3. Emit punching or laser DFT (`core/dxf_to_dft.py`, CLIs in `tools/`).
4. Validate vs factory with **unordered** geometry match
   (`--unordered --min-coverage 0.9`): DXF often has a few extra contour
   segments; pass if ≥90% of factory lines are present.

Batch result on this fixture set: **96/96** (48 punch + 48 laser), mean
coverage **96.1%** — see `output/validation/report.md` after running
`python tools/batch_process.py`.
