#!/usr/bin/env python3
"""Figure 5: satellite NDVI chips for the TC-tornado marsh cases.

Reads the monthly median NDVI composites cached by
build_fig5_data.py and renders a rows = storms x columns =
[Pre-storm, Landfall composite, Change] grid. NDVI columns share
viridis 0-0.9; change uses RdBu_r -0.3 to +0.3; no-data in light
grey. Both colourbars and the column headers sit in a band at the
top of the figure. The analysed footprint marsh is outlined on
every chip (black line over a white halo). Rows whose provenance
record lacks either month, or (for the optional Helene / Milton
rows) whose footprint clear-pixel fraction is below 0.5 in either
month, are dropped; the caller passes the final row list via the
provenance JSON written by this script's --report mode or by
editing ROWS after inspecting fig5_provenance.json.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import Normalize
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

HERE = Path(__file__).resolve().parent
REV = HERE.parent
CACHE = HERE / "imagery_cache"
FIGDIR = REV / "figures"
ORIG = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes"
CASES = REV / "analysis/cases_idalia_florence/data"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif"],
    "font.size": 8.5,
    "axes.linewidth": 0.6,
})

# key, row label line 1, line 2 (months), footprint file, pre, impact,
# scale-bar length (m), optional row?
ALL_ROWS = [
    ("ida", "Ida 2021", "Aug / Sep 2021",
     ORIG / "data/footprint_ida.geojson", "202108", "202109", 10000, False),
    ("idalia", "Idalia 2023", "Aug / Sep 2023",
     CASES / "footprint_idalia.geojson", "202308", "202309", 5000, False),
    ("florence", "Florence 2018", "(HLS-equivalent)\nSep / Oct 2018",
     CASES / "footprint_florence.geojson", "201809", "201810", 5000, False),
    ("helene", "Helene 2024", "Sep / Oct 2024",
     ORIG / "data/footprint_helene.geojson", "202409", "202410", 1000, True),
    ("milton", "Milton 2024", "Oct / Nov 2024",
     ORIG / "data/footprint_milton.geojson", "202410", "202411", 1000, True),
]
MIN_CLEAR_OPTIONAL = 0.5


def load_ndvi(storm, label):
    with rasterio.open(CACHE / f"{storm}_{label}_ndvi.tif") as src:
        return src.read(1), src.transform, src.width, src.height


def scale_bar(ax, x0, y0, length_m, res_m=30.0):
    """Alternating black/white scale bar, length_m in metres."""
    px = length_m / res_m
    half = px / 2
    for i, c in enumerate(["black", "white"]):
        ax.add_patch(plt.Rectangle((x0 + i * half, y0), half, px * 0.045,
                                   facecolor=c, edgecolor="black",
                                   linewidth=0.5, zorder=6))
    lab = f"{length_m/1000:g} km" if length_m >= 1000 else f"{length_m:g} m"
    ax.text(x0 + px / 2, y0 + px * 0.10, lab, ha="center", va="bottom",
            fontsize=7, color="black", zorder=6,
            bbox=dict(facecolor="white", alpha=0.65, edgecolor="none",
                      pad=0.6))


def main():
    prov = json.loads((CACHE / "fig5_provenance.json").read_text())
    rows = []
    dropped = {}
    for key, lab1, lab2, fp_file, pre, imp, bar_m, optional in ALL_ROWS:
        m = prov.get(key, {}).get("months", {})
        if pre not in m or imp not in m or not m[pre].get("n_scenes") \
                or not m[imp].get("n_scenes"):
            dropped[key] = "missing composite for one or both months"
            continue
        if optional:
            cf = [m[pre].get("clear_frac_footprint"),
                  m[imp].get("clear_frac_footprint")]
            if any(c is None or c < MIN_CLEAR_OPTIONAL for c in cf):
                dropped[key] = (f"footprint clear fraction {cf} below "
                                f"{MIN_CLEAR_OPTIONAL} in at least one month")
                continue
        rows.append((key, lab1, lab2, fp_file, pre, imp, bar_m))
    print("rows included:", [r[0] for r in rows])
    print("rows dropped:", dropped)

    # Geometry: chip width fixed; each row's height follows its
    # window aspect ratio.
    chip_w = 1.78
    label_w = 1.28
    col_gap = 0.07
    row_gap = 0.16
    top_band = 0.92
    bottom = 0.12
    fig_w = label_w + 3 * chip_w + 2 * col_gap + 0.08
    aspects, data = [], {}
    for key, lab1, lab2, fp_file, pre, imp, bar_m in rows:
        a_pre, tr, W, H = load_ndvi(key, pre)
        a_imp, _, _, _ = load_ndvi(key, imp)
        data[key] = (a_pre, a_imp, tr, W, H)
        aspects.append(H / W)
    heights = [chip_w * a for a in aspects]
    fig_h = top_band + sum(heights) + row_gap * (len(rows) - 1) + bottom

    fig = plt.figure(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor("white")

    ndvi_norm = Normalize(0, 0.9)
    chg_norm = Normalize(-0.3, 0.3)
    cmap_ndvi = plt.get_cmap("viridis").copy()
    cmap_ndvi.set_bad("#d9d9d9")
    cmap_chg = plt.get_cmap("RdBu_r").copy()
    cmap_chg.set_bad("#d9d9d9")

    # ---- top band: column headers + colourbars
    x_cols = [label_w + i * (chip_w + col_gap) for i in range(3)]
    headers = ["Pre-storm", "Landfall composite", "Change (impact $-$ pre-storm)"]
    for xc, htxt in zip(x_cols, headers):
        fig.text((xc + chip_w / 2) / fig_w, (fig_h - 0.24) / fig_h, htxt,
                 ha="center", va="center", fontsize=9)
    # NDVI colourbar spanning columns 1-2, change colourbar over column 3
    cax1 = fig.add_axes([x_cols[0] / fig_w, (fig_h - 0.62) / fig_h,
                         (2 * chip_w + col_gap - 0.14) / fig_w, 0.13 / fig_h])
    cb1 = fig.colorbar(plt.cm.ScalarMappable(norm=ndvi_norm, cmap=cmap_ndvi),
                       cax=cax1, orientation="horizontal",
                       ticks=[0, 0.3, 0.6, 0.9])
    cb1.set_label("NDVI", fontsize=8, labelpad=1)
    cb1.ax.tick_params(labelsize=7, length=2)
    cax2 = fig.add_axes([(x_cols[2] + 0.07) / fig_w, (fig_h - 0.62) / fig_h,
                         (chip_w - 0.07) / fig_w, 0.13 / fig_h])
    cb2 = fig.colorbar(plt.cm.ScalarMappable(norm=chg_norm, cmap=cmap_chg),
                       cax=cax2, orientation="horizontal",
                       ticks=[-0.3, -0.15, 0, 0.15, 0.3])
    cb2.set_label("$\\Delta$NDVI", fontsize=8, labelpad=1)
    cb2.ax.tick_params(labelsize=7, length=2)

    y_top = fig_h - top_band
    for ri, (key, lab1, lab2, fp_file, pre, imp, bar_m) in enumerate(rows):
        h_in = heights[ri]
        y0 = y_top - h_in  # bottom of this row, inches from figure bottom
        a_pre, a_imp, tr, W, H = data[key]
        chg = a_imp - a_pre
        extent = [tr.c, tr.c + tr.a * W, tr.f + tr.e * H, tr.f]
        fp = gpd.read_file(fp_file).to_crs(5070)
        for ci, (arr, cmap, norm) in enumerate(
                [(a_pre, cmap_ndvi, ndvi_norm), (a_imp, cmap_ndvi, ndvi_norm),
                 (chg, cmap_chg, chg_norm)]):
            ax = fig.add_axes([(x_cols[ci]) / fig_w, y0 / fig_h,
                               chip_w / fig_w, h_in / fig_h])
            ax.set_facecolor("#d9d9d9")
            ax.imshow(arr, cmap=cmap, norm=norm, extent=extent,
                      interpolation="nearest", origin="upper")
            # footprint outline: white halo under a black line
            fp.boundary.plot(ax=ax, color="white", linewidth=1.9, zorder=5)
            fp.boundary.plot(ax=ax, color="black", linewidth=0.9, zorder=6)
            ax.set_xlim(extent[0], extent[1])
            ax.set_ylim(extent[2], extent[3])
            ax.set_xticks([])
            ax.set_yticks([])
            for s in ax.spines.values():
                s.set_color("#666666")
            if ci == 0:
                scale_bar(ax, extent[0] + W * 30 * 0.055,
                          extent[2] + H * 30 * 0.05, bar_m)
        # row label
        fig.text((label_w - 0.10) / fig_w, (y0 + h_in / 2) / fig_h,
                 f"{lab1}\n{lab2}", ha="right", va="center", fontsize=8.5)
        y_top = y0 - row_gap

    out_png = FIGDIR / "fig5_satellite_imagery.png"
    out_pdf = FIGDIR / "fig5_satellite_imagery.pdf"
    fig.savefig(out_png, dpi=300, facecolor="white")
    fig.savefig(out_pdf, facecolor="white")
    print("wrote", out_png, out_pdf)
    (CACHE / "fig5_rows.json").write_text(json.dumps(
        {"included": [r[0] for r in rows], "dropped": dropped}, indent=2))


if __name__ == "__main__":
    main()
