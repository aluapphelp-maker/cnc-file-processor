#!/usr/bin/env python3
"""Simple Streamlit demo UI for showing DXF → DFT conversion.

Run from the repo root:
    streamlit run tools/demo_app.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib.pyplot as plt
import streamlit as st

from core.dft_parser import parse_dft, read_dft
from core.dxf_reader import read_dxf_geometry
from core.dxf_to_dft import convert_dxf_to_dft_file, dxf_to_dft
from core.generator_laser import plan_microjoints
from core.laser_analysis import detect_laser_stops
from core.transform import to_sheet_space
from core.validator import compare_dft_files

FIXTURES_DXF = _ROOT / "tests" / "fixtures" / "dxf"
FIXTURES_PUNCH = _ROOT / "tests" / "fixtures" / "punching"
FIXTURES_LASER = _ROOT / "tests" / "fixtures" / "laser"


def _list_samples() -> list[str]:
    return sorted(p.stem for p in FIXTURES_DXF.glob("*.dxf"))


def _find_ref(folder: Path, stem: str) -> Path | None:
    matches = list(folder.glob(f"* {stem}.dft")) + list(folder.glob(f"{stem}.dft"))
    return matches[0] if matches else None


def _plot_segments(segments, *, joints=None, title: str = ""):
    fig, ax = plt.subplots(figsize=(7, 5))
    for seg in segments:
        ax.plot(
            [seg.start.x, seg.end.x],
            [seg.start.y, seg.end.y],
            color="#1f4e79",
            linewidth=1.4,
        )
    if joints:
        xs = [j.x for j in joints if j.x is not None]
        ys = [j.y for j in joints if j.y is not None]
        if xs:
            ax.scatter(xs, ys, c="#c45c26", s=36, zorder=5, label="MicroJoints (stops)")
            ax.legend(loc="best")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    if title:
        ax.set_title(title)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig


def main() -> None:
    st.set_page_config(page_title="CNC File Processor Demo", layout="wide")
    st.title("CNC File Processor")
    st.caption("Demo: DXF contour → punching / laser CncKad DFT")

    with st.sidebar:
        st.header("Input")
        source = st.radio("Source", ["Factory sample", "Upload DXF"], index=0)
        dxf_path: Path | None = None
        stem = "upload"

        if source == "Factory sample":
            samples = _list_samples()
            choice = st.selectbox("Part", samples, index=samples.index("1BE01") if "1BE01" in samples else 0)
            dxf_path = FIXTURES_DXF / f"{choice}.dxf"
            stem = choice
        else:
            uploaded = st.file_uploader("DXF file", type=["dxf"])
            if uploaded is not None:
                tmp = Path(tempfile.gettempdir()) / f"cnc_demo_{uploaded.name}"
                tmp.write_bytes(uploaded.getvalue())
                dxf_path = tmp
                stem = Path(uploaded.name).stem

        machine_type = st.radio("Machine type", ["punching", "laser"], horizontal=True)
        stop_spacing = st.slider(
            "Laser stop spacing (mm)",
            min_value=100,
            max_value=500,
            value=300,
            step=25,
            disabled=machine_type != "laser",
        )
        run = st.button("Convert", type="primary", use_container_width=True)

    if dxf_path is None:
        st.info("Choose a factory sample or upload a DXF to begin.")
        return

    # Always show input preview
    try:
        world = read_dxf_geometry(dxf_path)
        sheet, tf = to_sheet_space(world)
    except Exception as exc:
        st.error(f"Could not read DXF: {exc}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Contour segments", len(sheet))
    col2.metric("Sheet size", f"{tf.width:.1f} × {tf.height:.1f} mm")
    col3.metric("Origin offset X", f"{tf.origin_offset:.1f}")

    left, right = st.columns(2)
    with left:
        st.subheader("1. DXF contour (sheet space)")
        st.pyplot(_plot_segments(sheet, title=f"{stem} — translated to (0,0)"), clear_figure=True)

    with right:
        st.subheader("2. Process")
        st.markdown(
            """
1. Read **KNA - Contour** from DXF  
2. Translate world → sheet (bbox min → origin)  
3. Emit `[200]` machine flags + `[300]` LINES  
4. Laser only: inject `[350]` MicroJoints every *N* mm  
            """
        )
        if not run:
            st.info("Click **Convert** in the sidebar to generate a DFT.")

    if not run:
        return

    with st.spinner("Generating DFT…"):
        dft = dxf_to_dft(
            dxf_path,
            machine_type=machine_type,  # type: ignore[arg-type]
            stop_spacing=float(stop_spacing),
        )
        out_dir = _ROOT / "output" / "demo"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{stem}_{machine_type}.dft"
        convert_dxf_to_dft_file(
            dxf_path,
            out_path,
            machine_type=machine_type,  # type: ignore[arg-type]
            stop_spacing=float(stop_spacing),
            dft=dft,
        )

    st.success(f"Wrote `{out_path.relative_to(_ROOT)}`")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Machine", dft.machine_type)
    m2.metric("LINES", dft.geometry.line_count)
    m3.metric("Material", dft.material.name or "—")
    m4.metric("Extent", f"{dft.machine_config.extent_width:.0f}×{dft.machine_config.extent_height:.0f}")

    joints = []
    if machine_type == "laser":
        joints = plan_microjoints(sheet, spacing=float(stop_spacing))
        raw = read_dft(out_path)
        detected, summary = detect_laser_stops(raw)
        st.subheader("3. Laser MicroJoints (stop points)")
        st.write(
            f"Planned **{len(joints)}** stops · detected in file **{summary.microjoint_count}** · "
            f"mean spacing ≈ **{(summary.mean_spacing or 0):.0f} mm**"
        )
        st.pyplot(
            _plot_segments(sheet, joints=detected, title=f"{stem} laser — stops every {stop_spacing} mm"),
            clear_figure=True,
        )
    else:
        st.subheader("3. Punching path")
        st.pyplot(_plot_segments(sheet, title=f"{stem} punching — contour tool path"), clear_figure=True)

    # Factory compare when using a sample
    ref_folder = FIXTURES_PUNCH if machine_type == "punching" else FIXTURES_LASER
    ref = _find_ref(ref_folder, stem) if source == "Factory sample" else None
    if ref is not None:
        st.subheader("4. Compare to factory reference")
        cmp = compare_dft_files(
            ref,
            out_path,
            unordered=True,
            min_coverage=0.90,
            tolerance=0.05,
        )
        if cmp.ok:
            st.success(
                f"MATCH — {cmp.matched_lines}/{cmp.reference_line_count} factory lines found "
                f"({100 * cmp.reference_coverage:.1f}% coverage)"
            )
        else:
            st.warning(cmp.summary())

    data = out_path.read_bytes()
    st.download_button(
        label=f"Download {out_path.name}",
        data=data,
        file_name=out_path.name,
        mime="application/octet-stream",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
