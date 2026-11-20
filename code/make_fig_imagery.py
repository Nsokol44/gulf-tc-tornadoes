"""Figure 4: satellite imagery for the Ida marsh footprint.

Panels (a) and (b) are true-colour monthly median composites from
the Harmonized Landsat and Sentinel-2 version 2.0 Sentinel-2 (S30)
record for August 2021 (pre-landfall) and September 2021 (the first
composite beginning after the 29 August 2021 landfall), built by
code/fetch_ida_imagery.py with the same Fmask masking and monthly
median definition as the trajectory analysis. Panel (c) is the NDVI
change between the two composites over vegetated pixels (pre-storm
NDVI above 0.2, the analysis mask). The chip window frames the
western, Pearl River mouth group of the analyzed footprint, the
largest of its three alongshore groups (8 of 18 polygons, 30.7 of
64.4 ha); the locator inset in panel (a) shows the full footprint
extent on the Mississippi coast.
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_figures import (BLUE, GREEN, ORANGE, VERMILLION, basemap,  # noqa: E402
                          north_arrow, proj, scale_bar, save)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = ROOT / "results"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif"],
    "font.size": 9,
    "axes.titlesize": 9.5,
})


def read_full(path):
    with rasterio.open(path) as src:
        arr = src.read()
        b = src.bounds
    return arr, (b.left, b.bottom, b.right, b.top)


def stretch(aug, sep):
    """Joint 2 to 98 percentile stretch per RGB band across both
    months, so the two panels are rendered identically."""
    lo = np.nanpercentile(np.stack([aug, sep]), 2, axis=(0, 2, 3))
    hi = np.nanpercentile(np.stack([aug, sep]), 98, axis=(0, 2, 3))
    lo_rgb = lo[[2, 1, 0]]  # reorder to B04, B03, B02
    hi_rgb = hi[[2, 1, 0]]
    def f(arr):
        rgb = np.stack([arr[2], arr[1], arr[0]], axis=-1)  # B04,B03,B02
        out = (rgb - lo_rgb) / (hi_rgb - lo_rgb)
        return np.clip(out, 0, 1)
    return f(aug), f(sep)


def main():
    foot = gpd.read_file(DATA / "footprint_ida.geojson")
    ref = gpd.read_file(DATA / "reference_ida.geojson").to_crs(5070)
    lines = gpd.read_file(DATA / "lines_ida.geojson").to_crs(5070)
    foot_p = foot.to_crs(5070)

    # The west-group composite TIFFs are built on exactly the figure
    # window (footprint group bounds plus a margin) by
    # fetch_ida_imagery.py.
    aug, bb = read_full(RES / "hls_ida_west_aug2021.tif")
    sep, _ = read_full(RES / "hls_ida_west_sep2021.tif")
    bounds = (bb[0], bb[1], bb[2], bb[3])  # x0, y0, x1, y1 in EPSG:5070
    extent = (bounds[0], bounds[2], bounds[1], bounds[3])
    rgb_a, rgb_s = stretch(aug, sep)
    nd_a = (aug[3] - aug[2]) / (aug[3] + aug[2])
    nd_s = (sep[3] - sep[2]) / (sep[3] + sep[2])
    dndvi = nd_s - nd_a
    veg = nd_a > 0.2
    dmap = np.ma.masked_where(~veg | np.isnan(dndvi), dndvi)
    holes = np.isnan(rgb_a[..., 0]) | np.isnan(rgb_s[..., 0])
    print(f"window {bounds}, shape {rgb_a.shape}, "
          f"no-data share {holes.mean():.3f}")

    fig, axes = plt.subplots(1, 3, figsize=(6.85, 3.25))
    titles = ["(a) Pre-landfall composite\nAugust 2021",
              "(b) Post-landfall composite\nSeptember 2021",
              "(c) NDVI change\nSeptember minus August 2021"]
    for ax, title in zip(axes, titles):
        ax.set_title(title, loc="left", fontsize=8.8)
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color("#333333")
            sp.set_linewidth(0.7)
    for ax, rgb in ((axes[0], rgb_a), (axes[1], rgb_s)):
        ax.set_facecolor("#d9d9d9")
        ax.imshow(rgb, extent=extent, origin="upper", zorder=1)
    ax = axes[2]
    grey = np.nanmean(rgb_a, axis=-1)
    ax.set_facecolor("#d9d9d9")
    ax.imshow(grey, extent=extent, origin="upper", cmap="gray",
              vmin=0, vmax=1, alpha=0.55, zorder=1)
    im = ax.imshow(dmap, extent=extent, origin="upper", cmap="RdYlGn",
                   vmin=-0.35, vmax=0.35, zorder=2)
    for ax in axes:
        ax.set_xlim(bounds[0], bounds[2])
        ax.set_ylim(bounds[1], bounds[3])
        ax.set_aspect("equal")
        ref.plot(ax=ax, facecolor="none", edgecolor=GREEN, linewidth=0.9,
                 zorder=4)
        lines.plot(ax=ax, color="black", linewidth=2.0, zorder=5)
        lines.plot(ax=ax, color=ORANGE, linewidth=1.1, zorder=6)
        foot_p.plot(ax=ax, facecolor="none", edgecolor="white",
                    linewidth=2.3, zorder=7)
        foot_p.plot(ax=ax, facecolor="none", edgecolor=BLUE,
                    linewidth=1.2, zorder=8)
        ax.set_xlabel("")
        ax.set_ylabel("")
    # Locator inset in panel (a): Gulf Coast with the full footprint
    # extent (vermillion) and this chip window (blue).
    ins = axes[0].inset_axes([0.03, 0.55, 0.36, 0.38])
    ins.set_xticks([])
    ins.set_yticks([])
    corners = [proj(lon, lat) for lon in (-100.5, -77.5)
               for lat in (23.5, 40.0)]
    ins.set_xlim(min(c[0] for c in corners) - 30000,
                 max(c[0] for c in corners) + 30000)
    ins.set_ylim(min(c[1] for c in corners) - 30000,
                 max(c[1] for c in corners) + 30000)
    basemap(ins, (-100.5, 22.5, -77.5, 40.5))
    fb = foot.total_bounds
    fx0, fy0 = proj(fb[0], fb[1])
    fx1, fy1 = proj(fb[2], fb[3])
    ins.add_patch(Rectangle((fx0, fy0), fx1 - fx0, fy1 - fy0,
                            facecolor="none", edgecolor=VERMILLION,
                            linewidth=1.3, zorder=8))
    ins.add_patch(Rectangle((bounds[0], bounds[1]),
                            bounds[2] - bounds[0], bounds[3] - bounds[1],
                            facecolor="none", edgecolor=BLUE,
                            linewidth=1.3, zorder=9))
    ins.plot([(bounds[0] + bounds[2]) / 2], [(bounds[1] + bounds[3]) / 2],
             marker="o", ms=3, color=BLUE, mec="white", mew=0.6,
             zorder=10)
    ins.set_aspect("equal")
    ins.set_xlabel("")
    ins.set_ylabel("")
    for sp in ins.spines.values():
        sp.set_color("#333333")
        sp.set_linewidth(0.7)
    bx = bounds[0] + 0.04 * (bounds[2] - bounds[0])
    by = bounds[1] + 0.21 * (bounds[3] - bounds[1])
    scale_bar(axes[0], bx, by, 2, nseg=2, labelsize=7.5)
    north_arrow(axes[0], fx=0.90, fy=0.58, length_frac=0.16)
    handles = [
        Line2D([], [], color=BLUE, lw=1.6, label="Analyzed footprint"),
        Line2D([], [], color=ORANGE, lw=1.6, label="Tornado path"),
        Line2D([], [], color=GREEN, lw=1.4, label="Reference marsh"),
        Patch(facecolor="#d9d9d9", edgecolor="#999999",
              label="No clear observation"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0), fontsize=7.8,
               handlelength=1.4, columnspacing=1.1)
    fig.tight_layout(rect=(0, 0.02, 1, 0.90))
    # Colourbar in its own axes under panel (c), aligned to the panel
    # after layout, so the three panels stay identical in size.
    fig.canvas.draw()
    pos = axes[2].get_position()
    cb_ax = fig.add_axes([pos.x0, pos.y0 - 0.085, pos.width, 0.024])
    cb = fig.colorbar(im, cax=cb_ax, orientation="horizontal",
                      ticks=[-0.3, 0, 0.3])
    cb.set_label("NDVI change (unitless)", fontsize=8)
    cb.ax.tick_params(labelsize=7.5)
    save(fig, "fig4_ida_imagery")


if __name__ == "__main__":
    main()
