#!/usr/bin/env python3
"""Simple Streamlit demo UI for showing DXF → DFT conversion.

Run from the repo root:
    streamlit run tools/demo_app.py
"""

from __future__ import annotations

import base64
import io
import sys
import tempfile
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

from core.dft_parser import read_dft
from core.dxf_reader import read_dxf_geometry
from core.dxf_to_dft import convert_dxf_to_dft_file, dxf_to_dft
from core.generator_laser import plan_microjoints
from core.laser_analysis import detect_laser_stops
from core.transform import to_sheet_space
from core.validator import compare_dft_files

FIXTURES_DXF = _ROOT / "tests" / "fixtures" / "dxf"
FIXTURES_PUNCH = _ROOT / "tests" / "fixtures" / "punching"
FIXTURES_LASER = _ROOT / "tests" / "fixtures" / "laser"

_PREVIEW_SIZE = (4.0, 4.0)
_PREVIEW_SIZE_COMPACT = (3.2, 3.2)
_EXPANDED_SIZE = (10, 10)
_EXPANDED_DPI = 150


def _list_samples() -> list[str]:
    return sorted(p.stem for p in FIXTURES_DXF.glob("*.dxf"))


def _find_ref(folder: Path, stem: str) -> Path | None:
    matches = list(folder.glob(f"* {stem}.dft")) + list(folder.glob(f"{stem}.dft"))
    return matches[0] if matches else None


def _convert_one(
    dxf_path: Path,
    *,
    stem: str,
    machine_type: str,
    stop_spacing: float,
    source: str,
) -> dict:
    """Convert a single DXF and return a result dict for the UI."""
    world = read_dxf_geometry(dxf_path)
    sheet, _tf = to_sheet_space(world)
    dft = dxf_to_dft(
        dxf_path,
        machine_type=machine_type,  # type: ignore[arg-type]
        stop_spacing=stop_spacing,
    )
    out_dir = _ROOT / "output" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{stem}_{machine_type}.dft"
    convert_dxf_to_dft_file(
        dxf_path,
        out_path,
        machine_type=machine_type,  # type: ignore[arg-type]
        stop_spacing=stop_spacing,
        dft=dft,
    )

    detected = None
    laser_caption = ""
    if machine_type == "laser":
        joints = plan_microjoints(sheet, spacing=stop_spacing)
        raw = read_dft(out_path)
        detected, summary = detect_laser_stops(raw)
        laser_caption = (
            f"Planned {len(joints)} · detected {summary.microjoint_count} · "
            f"mean ≈ {(summary.mean_spacing or 0):.0f} mm"
        )

    compare_msg = None
    compare_ok = None
    ref_folder = FIXTURES_PUNCH if machine_type == "punching" else FIXTURES_LASER
    ref = _find_ref(ref_folder, stem) if source == "Factory sample" else None
    if ref is not None:
        cmp = compare_dft_files(
            ref,
            out_path,
            unordered=True,
            min_coverage=0.90,
            tolerance=0.05,
        )
        compare_ok = cmp.ok
        compare_msg = (
            f"MATCH — {cmp.matched_lines}/{cmp.reference_line_count} "
            f"({100 * cmp.reference_coverage:.1f}% coverage)"
            if cmp.ok
            else cmp.summary()
        )

    return {
        "stem": stem,
        "out_path": str(out_path),
        "machine_type": dft.machine_type,
        "line_count": dft.geometry.line_count,
        "material": dft.material.name or "—",
        "extent": (
            f"{dft.machine_config.extent_width:.0f}"
            f"×{dft.machine_config.extent_height:.0f}"
        ),
        "detected": detected,
        "laser_caption": laser_caption,
        "result_title": (
            f"{stem} laser — stops every {stop_spacing:g} mm"
            if machine_type == "laser"
            else f"{stem} punching — contour tool path"
        ),
        "compare_ok": compare_ok,
        "compare_msg": compare_msg,
        "download_name": out_path.name,
        "download_bytes": out_path.read_bytes(),
    }


def _zip_results(results: list[dict]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in results:
            zf.writestr(item["download_name"], item["download_bytes"])
    return buf.getvalue()


def _plot_png(
    segments,
    *,
    joints=None,
    title: str = "",
    figsize=_PREVIEW_SIZE,
    dpi: int = 120,
) -> bytes:
    """Render contour to PNG bytes (reliable in Streamlit dialogs)."""
    fig, ax = plt.subplots(figsize=figsize)
    try:
        large = figsize[0] >= 10
        lw = 1.8 if large else 1.25
        ms = 48 if large else 28
        for seg in segments:
            ax.plot(
                [seg.start.x, seg.end.x],
                [seg.start.y, seg.end.y],
                color="#1f4e79",
                linewidth=lw,
            )
        if joints:
            xs = [j.x for j in joints if j.x is not None]
            ys = [j.y for j in joints if j.y is not None]
            if xs:
                ax.scatter(xs, ys, c="#c45c26", s=ms, zorder=5, label="MicroJoints (stops)")
                ax.legend(loc="best", fontsize=10 if large else 8)
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_box_aspect(1)
        label_size = 11 if large else 7
        ax.tick_params(labelsize=label_size)
        ax.set_xlabel("X (mm)", fontsize=label_size + 1)
        ax.set_ylabel("Y (mm)", fontsize=label_size + 1)
        if title:
            ax.set_title(title, fontsize=label_size + 2)
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.15,
            facecolor="white",
        )
        return buf.getvalue()
    finally:
        plt.close(fig)


@st.dialog("Expanded preview", width="large")
def _expanded_preview() -> None:
    """Show the large preview from session state via base64 HTML."""
    title = st.session_state.get("expand_title") or ""
    png = st.session_state.get("expand_png") or b""
    if not png:
        st.warning("Preview image missing — try Expand again.")
        return
    b64 = base64.b64encode(png).decode("ascii")
    alt = title.replace('"', "'")
    st.html(
        f'<img alt="{alt}" src="data:image/png;base64,{b64}" '
        'style="width:100%;max-height:78vh;height:auto;object-fit:contain;display:block;margin:0;" />'
    )


def _open_expand(segments, *, joints=None, title: str = "") -> None:
    st.session_state["expand_title"] = title
    st.session_state["expand_png"] = _plot_png(
        segments,
        joints=joints,
        title=title,
        figsize=_EXPANDED_SIZE,
        dpi=_EXPANDED_DPI,
    )
    _expanded_preview()


def _show_preview(
    segments,
    *,
    joints=None,
    title: str = "",
    key: str = "preview",
    heading: str = "",
    caption: str = "",
    compact: bool = False,
) -> None:
    """Section heading + Expand on one row, then a height-capped preview."""
    head, btn = st.columns([5, 1], vertical_alignment="center")
    with head:
        st.markdown(f"**{heading}**")
        # Always reserve caption height so paired columns stay aligned
        st.caption(caption if caption else "\u00a0")
    with btn:
        if st.button(
            "",
            key=f"expand_{key}",
            icon=":material/open_in_full:",
            help="Expand preview",
        ):
            _open_expand(segments, joints=joints, title=title)
    size = _PREVIEW_SIZE_COMPACT if compact else _PREVIEW_SIZE
    thumb = _plot_png(segments, joints=joints, title=title, figsize=size)
    st.image(thumb, width="stretch")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        /* Streamlit chrome overlaps the first line of content — hide it */
        [data-testid="stHeader"],
        [data-testid="stToolbar"],
        #MainMenu,
        footer {
            display: none !important;
            visibility: hidden !important;
        }
        .block-container {
            padding-top: 1.25rem !important;
            padding-bottom: 0.75rem !important;
            padding-left: 1.75rem !important;
            padding-right: 1.75rem !important;
            max-width: 1040px;
        }
        /* Allow scrolling so a multi-file gallery can show every part */
        .stApp, .stAppViewContainer, section.main {
            overflow-x: hidden !important;
            overflow-y: auto !important;
        }
        section.main > div {
            overflow: visible !important;
        }
        .cnc-header {
            margin: 0 0 0.65rem 0;
            padding-top: 0.15rem;
        }
        .cnc-header h1 {
            font-size: 1.45rem !important;
            font-weight: 700 !important;
            margin: 0 0 0.15rem 0 !important;
            padding: 0 !important;
            line-height: 1.3 !important;
            overflow: visible !important;
        }
        .cnc-header p {
            margin: 0 !important;
            opacity: 0.65;
            font-size: 0.85rem;
            line-height: 1.35;
        }
        .cnc-meta {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 0.35rem 1.25rem;
            padding: 0.45rem 0.75rem;
            margin: 0 0 0.55rem 0;
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 0.45rem;
            font-size: 0.84rem;
            background: rgba(49, 51, 63, 0.03);
        }
        .cnc-meta .ok {
            color: #137333;
            font-weight: 600;
        }
        .cnc-part {
            margin: 0.85rem 0 0.35rem 0;
            padding-bottom: 0.15rem;
            border-bottom: 1px solid rgba(49, 51, 63, 0.12);
            font-size: 1.05rem;
            font-weight: 650;
        }
        /* Cap preview height so both columns fit without page scroll */
        div[data-testid="stImage"] {
            margin: 0 !important;
            min-height: min(36vh, 280px);
            display: flex !important;
            align-items: center;
            justify-content: center;
        }
        div[data-testid="stImage"] img {
            max-height: min(36vh, 280px) !important;
            max-width: 100% !important;
            width: auto !important;
            height: auto !important;
            aspect-ratio: 1 / 1;
            object-fit: contain !important;
            display: block !important;
            margin: 0 auto !important;
            border: 1px solid rgba(49, 51, 63, 0.12);
            border-radius: 0.4rem;
            background: #fff;
        }
        .cnc-download {
            margin: 0.65rem 0 0.85rem 0;
            padding-top: 0.15rem;
        }
        /* Hide Streamlit's built-in image fullscreen control (we have Expand) */
        div[data-testid="stImage"] button {
            display: none !important;
        }
        .stButton button {
            padding: 0.2rem 0.7rem !important;
            min-height: 0 !important;
            font-size: 0.85rem !important;
        }
        div[data-testid="stDialog"] div[role="dialog"] {
            width: min(96vw, 1400px) !important;
            max-width: 96vw !important;
        }
        div[data-testid="stDialog"] img {
            width: 100% !important;
            max-height: 78vh !important;
            height: auto !important;
            object-fit: contain !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="CNC File Processor Demo", layout="wide")
    _inject_styles()

    st.markdown(
        """
        <div class="cnc-header">
          <h1>CNC File Processor</h1>
          <p>DXF contour → punching / laser CncKad DFT · click Expand for a larger view</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Input")
        source = st.radio("Source", ["Factory sample", "Upload DXF"], index=0)
        jobs: list[tuple[Path, str]] = []

        if source == "Factory sample":
            samples = _list_samples()
            default = ["1BE01"] if "1BE01" in samples else (samples[:1] if samples else [])
            choices = st.multiselect("Parts", samples, default=default)
            jobs = [(FIXTURES_DXF / f"{c}.dxf", c) for c in choices]
        else:
            uploaded = st.file_uploader(
                "DXF files",
                type=["dxf"],
                accept_multiple_files=True,
            )
            for item in uploaded or []:
                tmp = Path(tempfile.gettempdir()) / f"cnc_demo_{item.name}"
                tmp.write_bytes(item.getvalue())
                jobs.append((tmp, Path(item.name).stem))

        machine_type = st.radio(
            "Machine type",
            ["punching", "laser"],
            format_func=str.capitalize,
            horizontal=True,
        )
        if machine_type == "laser":
            stop_spacing = st.slider(
                "Laser stop spacing (mm)",
                min_value=100,
                max_value=500,
                value=300,
                step=25,
            )
        else:
            stop_spacing = 300

        n_jobs = len(jobs)
        convert_label = "Convert" if n_jobs <= 1 else f"Convert all ({n_jobs})"
        run = st.button(convert_label, type="primary", width="stretch", disabled=n_jobs == 0)
        if st.button("Clear result", width="stretch"):
            st.session_state.pop("demo_results", None)
            st.rerun()

    stems = tuple(stem for _, stem in jobs)
    input_key = (stems, machine_type, int(stop_spacing), source)
    if st.session_state.get("demo_input_key") != input_key:
        st.session_state["demo_input_key"] = input_key
        st.session_state.pop("demo_results", None)

    if not jobs:
        st.info("Choose one or more factory samples, or upload DXF files to begin.")
        return

    # Load every selected part so the gallery can show them all
    loaded: list[tuple[str, Path, object, object]] = []
    load_errors: list[str] = []
    for dxf_path, stem in jobs:
        try:
            world = read_dxf_geometry(dxf_path)
            sheet, tf = to_sheet_space(world)
            loaded.append((stem, dxf_path, sheet, tf))
        except Exception as exc:
            load_errors.append(f"{stem}: {exc}")
    if load_errors:
        st.error("Could not read some DXF files:\n" + "\n".join(load_errors))
    if not loaded:
        return

    if run:
        label = "Generating DFT…" if n_jobs == 1 else f"Converting {n_jobs} files…"
        results: list[dict] = []
        errors: list[str] = []
        with st.spinner(label):
            for dxf_path, stem in jobs:
                try:
                    results.append(
                        _convert_one(
                            dxf_path,
                            stem=stem,
                            machine_type=machine_type,
                            stop_spacing=float(stop_spacing),
                            source=source,
                        )
                    )
                except Exception as exc:
                    errors.append(f"{stem}: {exc}")
        st.session_state["demo_results"] = results
        if errors:
            st.warning("Some files failed:\n" + "\n".join(errors))

    results = st.session_state.get("demo_results") or []
    results_by_stem = {r["stem"]: r for r in results}
    compact = len(loaded) > 1

    # Status strip (aggregate for multi-file)
    if not results:
        status_html = ""
    elif len(results) == 1:
        r0 = results[0]
        status_html = (
            f'<span class="ok">Output generated successfully: '
            f'{r0["download_name"]}</span>'
            f'<span>{str(r0["machine_type"]).capitalize()} · '
            f'{r0["line_count"]} LINES'
            f' · {r0["material"]} · {r0["extent"]}</span>'
        )
        if r0["compare_msg"] is not None:
            tone = "ok" if r0["compare_ok"] else ""
            status_html += f'<span class="{tone}">{r0["compare_msg"]}</span>'
    else:
        match_n = sum(1 for r in results if r["compare_ok"])
        has_compare = any(r["compare_msg"] is not None for r in results)
        status_html = (
            f'<span class="ok">Output generated successfully: '
            f'{len(results)} files</span>'
            f'<span>{str(results[0]["machine_type"]).capitalize()}</span>'
        )
        if has_compare:
            status_html += f'<span class="ok">{match_n}/{len(results)} MATCH</span>'

    first_sheet, first_tf = loaded[0][2], loaded[0][3]
    if len(loaded) == 1:
        meta_bits = (
            f'<span><strong>Parts</strong> 1</span>'
            f'<span><strong>Segments</strong> {len(first_sheet)}</span>'
            f'<span><strong>Sheet</strong> {first_tf.width:.0f}×{first_tf.height:.0f} mm</span>'
            f'<span><strong>Offset X</strong> {first_tf.origin_offset:.1f}</span>'
        )
    else:
        total_segs = sum(len(s) for _, _, s, _ in loaded)
        meta_bits = (
            f'<span><strong>Parts</strong> {len(loaded)}</span>'
            f'<span><strong>Segments</strong> {total_segs} total</span>'
        )

    st.html(
        f"""
        <div class="cnc-meta">
          {meta_bits}
          {status_html}
        </div>
        """
    )

    for stem, _path, sheet, tf in loaded:
        result = results_by_stem.get(stem)
        if compact:
            st.markdown(
                f'<div class="cnc-part">{stem} · {len(sheet)} seg · '
                f"{tf.width:.0f}×{tf.height:.0f} mm</div>",
                unsafe_allow_html=True,
            )

        left, right = st.columns(2, gap="medium")
        with left:
            _show_preview(
                sheet,
                title=f"{stem} — sheet space",
                key=f"dxf_{stem}",
                heading="1. DXF contour" if not compact else f"{stem} · DXF",
                compact=compact,
            )
        with right:
            if result is None:
                if not compact:
                    st.markdown("**2. Process**")
                    st.caption("\u00a0")
                    st.markdown(
                        "1. Read **KNA - Contour** from DXF  \n"
                        "2. Translate world → sheet  \n"
                        "3. Emit `[200]` + `[300]` LINES  \n"
                        "4. Laser: `[350]` MicroJoints every *N* mm"
                    )
                    st.info(
                        f"Click **Convert all ({n_jobs})** in the sidebar."
                        if n_jobs > 1
                        else "Click **Convert** in the sidebar."
                    )
                else:
                    st.markdown("**Result**")
                    st.caption("\u00a0")
                    st.info("Not converted yet")
            else:
                heading = (
                    "3. Laser MicroJoints"
                    if result["machine_type"] == "laser"
                    else "3. Punching path"
                )
                if compact:
                    heading = (
                        f"{stem} · Laser"
                        if result["machine_type"] == "laser"
                        else f"{stem} · Punching"
                    )
                caption = result["laser_caption"] or ""
                if result["compare_msg"] and compact:
                    caption = (
                        f"{caption} · {result['compare_msg']}"
                        if caption
                        else result["compare_msg"]
                    )
                _show_preview(
                    sheet,
                    joints=result["detected"],
                    title=result["result_title"],
                    key=f"result_{stem}",
                    heading=heading,
                    caption=caption,
                    compact=compact,
                )

        if result is not None and compact:
            st.download_button(
                label=f"Download {result['download_name']}",
                data=result["download_bytes"],
                file_name=result["download_name"],
                mime="application/octet-stream",
                key=f"download_{stem}",
            )

    st.markdown('<div class="cnc-download"></div>', unsafe_allow_html=True)
    if len(results) == 1:
        r0 = results[0]
        st.download_button(
            label=f"Download {r0['download_name']}",
            data=r0["download_bytes"],
            file_name=r0["download_name"],
            mime="application/octet-stream",
            type="primary",
        )
    elif len(results) > 1:
        zip_name = f"dft_{machine_type}_{len(results)}files.zip"
        st.download_button(
            label=f"Download all ({len(results)} files)",
            data=_zip_results(results),
            file_name=zip_name,
            mime="application/zip",
            type="primary",
            key="download_zip",
        )


if __name__ == "__main__":
    main()
