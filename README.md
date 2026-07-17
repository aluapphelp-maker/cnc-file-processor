# CNC File Processor

Read, analyze, generate, and validate **CncKad DFT** files (punching / laser)
from DXF inputs, using factory examples as the ground truth.

## Status

Phase 1 & 2 complete for this plan:

- Parse / analyze all 96 factory DFTs
- Reverse-engineered tool path + laser MicroJoints
- Generate punching & laser DFTs from DXF
- Batch validation vs factory: **96/96 pass** (≥90% reference coverage,
  mean **96.1%**)

See `docs/dft_format_spec.md` and `docs/findings.md`.

## Layout

```
core/           # Library (parser, generators, DXF, validator)
tools/          # CLIs (analyze, compare, dxf_to_dft, batch_process)
tests/fixtures/ # 48 DXF + 48 punching + 48 laser
docs/           # Format spec + findings
output/         # Generated DFTs / validation reports (gitignored)
```

## Setup

```bash
cd /Users/a/repos/cnc-file-processor
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Demo UI

```bash
streamlit run tools/demo_app.py
```

Opens a browser app: pick a factory DXF (or upload one), choose punching/laser,
preview the contour, convert, see laser stop points, compare to factory refs,
and download the generated DFT.

## Tools

```bash
# Factory parameter patterns → docs/findings.md
python tools/analyze_factory_files.py

# Compare two DFTs
python tools/compare_dft.py ref.dft other.dft --geometry-only
# Unordered match (DXF→DFT vs factory):
python tools/compare_dft.py ref.dft generated.dft --unordered --min-coverage 0.9

# DXF → DFT
python tools/dxf_to_dft.py tests/fixtures/dxf/1BE01.dxf --type punching -o output/1BE01_punch.dft
python tools/dxf_to_dft.py tests/fixtures/dxf/1BE01.dxf --type laser -o output/1BE01_laser.dft

# Batch validate all fixtures → output/validation/report.md
python tools/batch_process.py
```

## Library quick start

```python
from core.dxf_to_dft import dxf_to_dft, convert_dxf_to_dft_file

dft = dxf_to_dft("part.dxf", machine_type="laser")
convert_dxf_to_dft_file("part.dxf", "output/part_laser.dft", machine_type="laser", dft=dft)
```

World→sheet transform: contour bbox min corner becomes sheet origin `(0,0)`.
Generated files include the full DXF contour (often a few extra segments vs
factory); batch validation requires ≥90% of factory lines to be present.

## Factory fixtures

| Folder | Count | Source |
|--------|-------|--------|
| `dxf/` | 48 | `~/Downloads/דימה/DXF/` |
| `punching/` | 48 | `~/Downloads/דימה/ניקוב/` |
| `laser/` | 48 | `~/Downloads/דימה/לייזר/` |

DFT names keep the factory prefix, e.g. `(haz-26-643) 1BE01.dft`.
