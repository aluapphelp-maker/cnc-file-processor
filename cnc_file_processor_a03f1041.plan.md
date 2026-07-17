---
name: CNC File Processor
overview: Build a system to read, analyze, generate, and validate CncKad DFT files (punching/laser) from DXF inputs, learning from factory examples to enable automated CNC file generation.
todos:
  - id: setup_project
    content: 🟢 SIMPLE | Create project structure, requirements.txt, initial README
    status: completed
  - id: copy_factory_files
    content: 🟢 SIMPLE | Copy factory files to tests/fixtures/ (48 DXF, 48 punching, 54 laser)
    status: completed
  - id: dft_models
    content: 🟢 SIMPLE | Create dataclasses for DFT sections (DFTFile, MachineConfig, BendParams)
    status: completed
  - id: dft_parser_basic
    content: 🟡 MEDIUM | Implement UTF-16 LE file reader and section marker extraction
    status: completed
  - id: dft_parser_sections
    content: 🟡 MEDIUM | Parse [200], [210], [514] sections into models
    status: completed
  - id: dft_parser_geometry
    content: 🟡 MEDIUM | Parse [300] LINES section (coordinates only, defer tool analysis)
    status: completed
  - id: test_parser_all_files
    content: 🟢 SIMPLE | Write pytest to parse all 48+54 factory DFT files without errors
    status: completed
  - id: analyze_factory_basic
    content: 🟡 MEDIUM | Build analyzer to extract parameter patterns (machine type, dimensions, materials)
    status: pending
  - id: geometry_models
    content: 🟢 SIMPLE | Create geometry dataclasses (Point, Line, Polyline) - reuse from panel-engine
    status: pending
  - id: dxf_reader
    content: 🟡 MEDIUM | Implement DXF contour reader (KNA layer filtering with ezdxf)
    status: pending
  - id: comparison_tool_structure
    content: 🟢 SIMPLE | Create CLI structure for compare_dft.py with click
    status: pending
  - id: comparison_tool_logic
    content: 🟡 MEDIUM | Implement geometry comparison with tolerance checking
    status: pending
  - id: tool_path_analysis
    content: 🔴 COMPLEX | Reverse-engineer punching tool encoding in [300] section
    status: pending
  - id: laser_stop_detection
    content: 🔴 COMPLEX | Identify laser stop-point patterns in geometry
    status: pending
  - id: dft_generator_basic
    content: 🟡 MEDIUM | Build DFT writer (UTF-16 LE) with header/section generation
    status: pending
  - id: dft_generator_punching
    content: 🔴 COMPLEX | Implement punching tool path generation with overlap calculation
    status: pending
  - id: dft_generator_laser
    content: 🔴 COMPLEX | Implement laser path with 30cm stop-point injection
    status: pending
  - id: dxf_to_dft_cli
    content: 🟢 SIMPLE | Create CLI wrapper for DXF→DFT conversion
    status: pending
  - id: batch_validation
    content: 🟡 MEDIUM | Build batch processor to validate all factory files
    status: pending
  - id: documentation
    content: 🟢 SIMPLE | Write format spec and findings report
    status: pending
isProject: false
---

# CNC File Processor - Phase 1 & 2

## 🎯 Execution Roadmap (Start Here)

### Task Complexity Legend
- **🟢 SIMPLE** - Basic Python/file operations, boilerplate code → Use any model (GPT-4o mini, Claude Haiku OK)
- **🟡 MEDIUM** - Parsing, pattern matching, standard algorithms → Claude 3.5 Sonnet recommended
- **🔴 COMPLEX** - Spatial reasoning, reverse-engineering, algorithm design → Claude 3.5 Sonnet or o1 REQUIRED

### Recommended Execution Order

#### Week 1: Foundation (🟢 Simple Tasks)
1. **setup_project** - Scaffold directories, requirements.txt, README, .gitignore
2. **copy_factory_files** - Organize factory files into tests/fixtures/
3. **dft_models** - Define dataclasses for all DFT sections
4. **geometry_models** - Copy/adapt Point, Line, Polyline from panel-engine

#### Week 2: Parsing (🟡 Medium Tasks)
5. **dft_parser_basic** - UTF-16 LE reader + section marker detection
6. **dft_parser_sections** - Parse [200], [210], [514] into models
7. **dft_parser_geometry** - Parse [300] coordinates (skip tool analysis for now)
8. **test_parser_all_files** - Pytest suite to validate parsing of all 150 files

#### Week 3: Analysis & Reading (🟡 Medium)
9. **analyze_factory_basic** - Extract patterns: machine type, parameters, statistics
10. **dxf_reader** - Extract contours from DXF using ezdxf layer filters
11. **comparison_tool_structure** - CLI skeleton with click
12. **comparison_tool_logic** - Geometry comparison with tolerance

#### Week 4: Complex Analysis (🔴 Complex - Requires Claude 3.5 Sonnet)
13. **tool_path_analysis** - Reverse-engineer how punching tools are encoded
14. **laser_stop_detection** - Identify stop-point patterns in laser files

#### Week 5-6: Generation (Mix of 🟡 Medium and 🔴 Complex)
15. **dft_generator_basic** - UTF-16 LE writer + section generation
16. **dft_generator_punching** - 🔴 Tool overlap calculation and path generation
17. **dft_generator_laser** - 🔴 30cm stop-point injection along curves

#### Week 7: Integration (🟢 Simple + 🟡 Medium)
18. **dxf_to_dft_cli** - CLI wrapper combining all components
19. **batch_validation** - Validate all 48 DXF files against factory references
20. **documentation** - Write final specs and reports

### Incremental Testing Strategy
- After every 🟢 task: Quick manual verification
- After every 🟡 task: Run `pytest tests/test_X.py -v` before proceeding
- Before every 🔴 task: Confirm you're using Claude 3.5 Sonnet or better
- After 🔴 tasks: Run comprehensive validation suite

## Project Overview

Create a new standalone project that processes CNC manufacturing files in **CncKad DFT format**. The factory provided:
- 48 DXF files (original CAD drawings)
- 48 Punching DFT files (CNC nibbling machine instructions)
- 54 Laser DFT files (CNC laser cutting instructions)

The goal: Learn from these examples to automatically generate CNC-ready DFT files from DXF inputs.

## Technical Analysis

### CncKad DFT Format Structure
Format: UTF-16 LE text file with sections:

- **[200]** - Machine metadata
  - `/I 0 0` = Punching, `/I 0 1` = Laser
  - `/E` = Extent/dimensions
  - `/S` = Sheet parameters (includes different values for punch vs laser)
  - `/P`, `/D`, `/M`, `/T`, `/F`, `/U`, `/W`, `/L` = Various machine settings
  
- **[514]** - Material specification (e.g., "YWL_HLB_V3")

- **[210]** - Bend parameters
  - KFactor, bend radius, compensation mode
  
- **[300]** - LINES section
  - Actual geometry: line segments with coordinates
  - Tool path points for each segment
  - This is where punching tools would be encoded (as mentioned in audio)

- **[310]** - Additional geometry/commands

### Key Differences: Punching vs Laser

**Punching** (`/I 0 0`):
- Around the contour, tool markers indicate which punching tools to use
- Tools overlap to create the cut line
- Different tool shapes: circles, rectangles, triangles

**Laser** (`/I 0 1`):
- No tool markers, continuous laser path
- Has periodic stops every ~30cm to prevent overheating/warping
- Different `/S` parameters (79999.99647 vs 110000.00576)
- Different `/V` parameter values

## Project Structure

Create new repository: `cnc-file-processor/`

```
cnc-file-processor/
├── README.md
├── requirements.txt
├── .gitignore
├── core/
│   ├── __init__.py
│   ├── dft_parser.py          # Parse CncKad DFT files
│   ├── dft_generator.py       # Generate DFT from geometry
│   ├── dxf_reader.py          # Read DXF (reuse from panel-engine)
│   ├── geometry.py            # Geometry models (reuse/adapt)
│   ├── models.py              # DFT data models
│   └── validator.py           # Compare generated vs reference
├── tools/
│   ├── analyze_factory_files.py   # Analyze factory dataset
│   ├── compare_dft.py             # Compare two DFT files
│   ├── dxf_to_dft.py             # Convert DXF → DFT
│   └── batch_process.py           # Process multiple files
├── tests/
│   ├── test_parser.py
│   ├── test_generator.py
│   └── fixtures/                  # Copy factory files here
│       ├── dxf/
│       ├── punching/
│       └── laser/
├── output/
│   └── .gitkeep
└── docs/
    ├── dft_format_spec.md         # Reverse-engineered format docs
    └── findings.md                # Analysis of factory files
```

## Reuse from panel-engine

Copy and adapt these modules:
- `engine/core/dxf_geometry_io.py` → `core/dxf_reader.py` (DXF reading with ezdxf)
- `engine/core/models.py` → `core/geometry.py` (basic Point, Line, Polyline models)
- Parts of `engine/core/cad_read.py` if needed

**Do NOT reuse:**
- Flanges, bending, decomposition logic
- BOM, assembly, substructure
- Panel-specific logic

## Phase 1: Read & Learn

### Step 1: Parse DFT Files

Implement [`core/dft_parser.py`](core/dft_parser.py):

```python
class DFTFile:
    header: DFTHeader          # [100], [101]
    machine_config: MachineConfig   # [200] section
    material: str              # [514]
    tool_params: dict          # [203]
    bend_params: BendParams    # [210]
    geometry: list[Line]       # [300] LINES
    
class DFTParser:
    def parse(self, filepath: str) -> DFTFile
    def detect_machine_type(self, dft: DFTFile) -> Literal['punching', 'laser']
```

Handle UTF-16 LE encoding properly.

### Step 2: Analyze Factory Dataset

Create [`tools/analyze_factory_files.py`](tools/analyze_factory_files.py):

- Read all 48+48+54 files
- Extract patterns:
  - Common parameters for punching vs laser
  - Geometry differences (tool markers, stop points)
  - Material/thickness variations
- Generate report: [`docs/findings.md`](docs/findings.md)
  - Parameter ranges
  - Machine type differences
  - Geometry encoding patterns

### Step 3: DXF Reading

Implement [`core/dxf_reader.py`](core/dxf_reader.py):

```python
def read_dxf_geometry(filepath: str) -> list[Line]:
    # Extract contour lines from DXF
    # Focus on KNA - Contour layer (if using KNA convention)
```

Reuse ezdxf code from panel-engine.

### Step 4: Comparison Tool

Create [`tools/compare_dft.py`](tools/compare_dft.py):

```bash
python tools/compare_dft.py reference.dft generated.dft --tolerance 0.01
```

Compare:
- Geometry (line coordinates with tolerance)
- Parameters (machine type, sheet size, material)
- Report differences in human-readable format

### Step 5: Validation Report

Generate validation report showing:
- Successfully parsed files: X/48 DXF, Y/48 punching, Z/54 laser
- Common patterns identified
- Parameter distributions
- Geometry complexity statistics

**Output:** Proof that we can read and understand the format.

## Phase 2: Generate & Validate

### Step 6: DFT Generator

Implement [`core/dft_generator.py`](core/dft_generator.py):

```python
class DFTGenerator:
    def __init__(self, machine_type: Literal['punching', 'laser']):
        self.config = self._load_default_config(machine_type)
    
    def generate(self, geometry: list[Line], params: DFTParams) -> DFTFile:
        # Generate [200] with correct /I based on machine_type
        # Generate [300] LINES from geometry
        # Apply machine-specific parameters
        
    def write(self, dft: DFTFile, filepath: str):
        # Write UTF-16 LE format
```

Use parameters learned from Phase 1 analysis.

### Step 7: DXF to DFT Converter

Create [`tools/dxf_to_dft.py`](tools/dxf_to_dft.py):

```bash
python tools/dxf_to_dft.py input.dxf --type laser --output output.dft
python tools/dxf_to_dft.py input.dxf --type punching --output output.dft
```

Flow:
1. Read DXF geometry
2. Extract contour lines
3. Generate DFT with specified machine type
4. Write output file

### Step 8: Batch Processing & Validation

Create [`tools/batch_process.py`](tools/batch_process.py):

Process all factory files:

```bash
python tools/batch_process.py \
  --dxf-dir tests/fixtures/dxf \
  --reference-punch-dir tests/fixtures/punching \
  --reference-laser-dir tests/fixtures/laser \
  --output-dir output/validation
```

For each DXF:
1. Generate punching DFT
2. Generate laser DFT  
3. Compare against factory reference
4. Report differences (geometry tolerance < 0.01mm acceptable)

**Success metric:** Generated files match factory files within tolerance.

### Step 9: Documentation

Write [`docs/dft_format_spec.md`](docs/dft_format_spec.md):
- Complete reverse-engineered format specification
- Section descriptions
- Parameter meanings
- Examples

Update [`README.md`](README.md) with:
- Installation instructions
- Usage examples
- Phase 1 & 2 results

## Key Implementation Details

### Geometry Extraction

From DXF:
- Focus on closed polylines (panel contours)
- Extract as sequence of line segments
- Preserve order (important for tool path)

To DFT:
- Convert to [300] LINES format
- Each line: `x1 y1 x2 y2 [parameters...]`
- Include tool path metadata

### Parameter Learning

Extract from factory files:
- Punching: `/I 0 0`, `/S` value ~110000, `/V 0 2 0 1 1`
- Laser: `/I 0 1`, `/S` value ~79999, `/V 1 2 0 1 1`
- Material defaults, bend parameters, sheet size calculation

### Tool Markers (Punching)

From the factory conversation:
- Tools appear around contour lines
- Each tool has a shape (circle, rectangle, triangle, etc.)
- Tools should connect/overlap to form cut line
- This is likely encoded in the line parameters or additional sections

Need to analyze [300] section more deeply to identify tool encoding.

### Laser Stop Points

From conversation:
- Laser stops every ~30cm to prevent overheating
- This appears as "exits and re-entries" in the cut path
- Likely encoded as breaks in the line segments or special markers
- Parameter-driven (adjustable distance)

## Dependencies

```txt
ezdxf>=1.1.0       # DXF reading/writing (from panel-engine)
numpy>=1.24.0      # Geometry calculations
pytest>=7.4.0      # Testing
click>=8.1.0       # CLI tools
rich>=13.0.0       # Pretty console output
```

## Testing Strategy

1. **Parser tests**: Verify we can read all factory files without errors
2. **Round-trip tests**: Parse → regenerate → compare (should be identical)
3. **Geometry tests**: DXF geometry matches DFT geometry
4. **Validation tests**: Generated files match factory references within tolerance

## Success Criteria - Phase 1

- Parse 100% of factory DFT files successfully
- Extract and document all parameter patterns
- Comparison tool shows geometry matches within 0.01mm
- Clear documentation of format structure

## Success Criteria - Phase 2

- Generate DFT files from DXF inputs
- Match factory file structure exactly
- Geometry accuracy: < 0.01mm deviation
- All 48 DXF files generate valid punching + laser DFTs
- Validation report shows 90%+ match rate with factory references

## Deliverables for Pricing Proposal

After Phase 1 & 2 completion:

1. **Technical Report**:
   - DFT format specification (complete)
   - Analysis of 48 factory examples
   - Proof of successful generation (validation results)

2. **Working Tools**:
   - DXF → Punching DFT converter
   - DXF → Laser DFT converter  
   - Comparison/validation tool

3. **Test Results**:
   - Batch validation report
   - Success rate statistics
   - Known limitations/edge cases

4. **Documentation**:
   - Usage guide
   - API reference for core modules
   - Factory file analysis findings

This provides a solid foundation for pricing the next phases (integration, automation, production deployment).

## Timeline Estimate

- **Phase 1** (Read & Learn): 3-4 weeks
  - Week 1: Parser + DXF reader
  - Week 2: Analysis tool + documentation
  - Week 3: Comparison tool + validation
  - Week 4: Testing + refinement

- **Phase 2** (Generate & Validate): 3-4 weeks  
  - Week 1: Generator implementation
  - Week 2: DXF to DFT converter
  - Week 3: Batch processing + validation
  - Week 4: Documentation + final testing

**Total**: 6-8 weeks for complete Phase 1 & 2

## 📋 Detailed Task Breakdown by Complexity

### 🟢 SIMPLE Tasks (Use Fast/Cheap Models)
| Task | File | Effort | Notes |
|------|------|--------|-------|
| Project scaffold | `setup.py`, `README.md`, etc. | 30 min | Standard Python project structure |
| Copy factory files | Move files to `tests/fixtures/` | 15 min | File organization only |
| Dataclass models | `core/models.py` | 1 hour | Standard dataclasses, no logic |
| Geometry models | `core/geometry.py` | 30 min | Copy from panel-engine |
| CLI structure | `tools/*.py` | 1 hour | Click argument parsing boilerplate |
| Basic tests | `tests/test_*.py` | 2 hours | Standard pytest patterns |
| Documentation | `docs/*.md`, `README.md` | 2 hours | Markdown writing |

**Total Simple Tasks: ~7 hours** ✅ Safe for any model

### 🟡 MEDIUM Tasks (Claude 3.5 Sonnet Recommended)
| Task | File | Effort | Notes |
|------|------|--------|-------|
| UTF-16 LE reader | `core/dft_parser.py` | 2 hours | Encoding handling + section splitting |
| Section parsing | `core/dft_parser.py` | 4 hours | Regex patterns, parameter extraction |
| Geometry parsing | `core/dft_parser.py` | 3 hours | Coordinate extraction, line segmentation |
| Factory analyzer | `tools/analyze_factory_files.py` | 4 hours | Statistics, pattern detection |
| DXF reader | `core/dxf_reader.py` | 3 hours | ezdxf queries, layer filtering |
| Comparison logic | `tools/compare_dft.py` | 4 hours | Tolerance matching, diff reporting |
| DFT writer | `core/dft_generator.py` | 3 hours | UTF-16 LE output, section formatting |
| Batch processor | `tools/batch_process.py` | 3 hours | File iteration, result aggregation |

**Total Medium Tasks: ~26 hours** ⚠️ Use Claude 3.5 Sonnet

### 🔴 COMPLEX Tasks (Claude 3.5 Sonnet or o1 REQUIRED)
| Task | File | Effort | Notes |
|------|------|--------|-------|
| Tool path reverse-engineering | `core/dft_parser.py` analysis | 6 hours | Decode proprietary tool encoding in [300] |
| Laser stop detection | `core/dft_parser.py` analysis | 4 hours | Identify stop-point patterns in geometry |
| Punching tool generation | `core/dft_generator.py` | 8 hours | Calculate tool overlaps, radius offsets, path optimization |
| Laser stop injection | `core/dft_generator.py` | 6 hours | Inject stops every 30cm along arbitrary curves, preserve continuity |

**Total Complex Tasks: ~24 hours** 🔴 CRITICAL: High-quality model required

### Summary
- **Simple (🟢):** 7 hours - Any model OK
- **Medium (🟡):** 26 hours - Claude 3.5 Sonnet recommended
- **Complex (🔴):** 24 hours - Claude 3.5 Sonnet or o1 required
- **TOTAL:** ~57 hours (7-8 weeks at 1 day/week)

## Next Steps (Start Here!)

**Ready to begin?** Say:
- `"Let's start"` → I'll begin with Task 1: **setup_project** (🟢 SIMPLE)
- `"Skip to task X"` → Jump to a specific task

I'll work incrementally - one small module at a time, with test checkpoints after each step.
