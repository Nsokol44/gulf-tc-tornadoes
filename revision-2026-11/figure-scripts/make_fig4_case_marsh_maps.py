"""Build Figure 4: case-study marsh maps (five panels, 3 + 2).

Physical Geography manuscript revision: satellite detection of TC
tornado damage in coastal marsh.

Layers per panel, drawn in order:
  1. Natural Earth 1:10m land (very light grey) + coastline.
  2. Marsh crossed by the storm's tornado paths (muted green fill).
  3. Reference marsh (orange #E69F00, alpha 0.55, thin dark edge).
  4. Analysed footprint marsh (vermillion #D55E00, alpha 0.85, dark edge).
  5. Tornado path footprints (outline only, dark grey, thin).

Projection: CONUS Albers Equal Area, EPSG:5070. Font: Liberation Serif.
One shared legend in a band above the panels.

Extent note: the paths_<storm>.geojson and marsh_in_paths_<storm>.geojson
files contain features along each storm's ENTIRE tornado track (for Ida,
paths reach 39 deg N in the northeastern US), so a literal union of all
features in all files would span half the continent and make the coastal
analysed marsh invisible. The panel extent is therefore the union of the
reference marsh and the analysed footprint (= the local marsh-crossed
cluster; verified: marsh_in_paths features intersecting this window are
geometrically identical to the footprint, symmetric difference 0.0 ha in
every panel), buffered by 12% of width/height on each side. Storm-wide
layers are drawn in full and clipped by the axes, following the approach
of the original project's fig3 code.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer
from shapely.geometry import box

REV = Path(__file__).resolve().parent.parent
OLD_DATA = REV.parent / "angle2-tc-tornadoes" / "data"
NEW_DATA = REV / "analysis" / "cases_idalia_florence" / "data"
FIG = REV / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif"],
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": "#333333",
    "axes.linewidth": 0.7,
})

# Okabe-Ito palette
ORANGE = "#E69F00"
VERMILLION = "#D55E00"
MUTED_GREEN = "#9DC08B"
PATH_EDGE = "#3d3d3d"
LAND_FILL = "#efefef"
COAST_EDGE = "#545454"

CRS_PROJ = "EPSG:5070"
TO_P = Transformer.from_crs(4326, CRS_PROJ, always_xy=True)
FROM_P = Transformer.from_crs(CRS_PROJ, 4326, always_xy=True)

LAND_LL = gpd.read_file(OLD_DATA / "ne_10m_land.zip")
COAST_LL = gpd.read_file(OLD_DATA / "ne_10m_coastline.zip")


def proj(lon, lat):
    return TO_P.transform(lon, lat)


# --- helpers adapted from the original project's make_figures.py ---
def scale_bar(ax, total_km, nseg=2, labelsize=7.5):
    """Alternating black and white scale bar, placed in axes fractions
    (bottom left) so its labels always stay inside the frame. The bar
    length is computed from the panel's data x-span."""
    xspan = ax.get_xlim()[1] - ax.get_xlim()[0]
    fx0, fy0 = 0.05, 0.085
    flen = total_km * 1000.0 / xspan
    seg = flen / nseg
    for i in range(nseg):
        ax.add_patch(Rectangle((fx0 + i * seg, fy0), seg, 0.024,
                               transform=ax.transAxes,
                               facecolor="black" if i % 2 == 0 else "white",
                               edgecolor="black", lw=0.7, zorder=9))
    for i in range(nseg + 1):
        ax.text(fx0 + i * seg, fy0 - 0.018, f"{int(i * total_km / nseg)}",
                transform=ax.transAxes, ha="center", va="top",
                fontsize=labelsize, zorder=9)
    ax.text(fx0 + flen + 0.035, fy0 - 0.018, "km", transform=ax.transAxes,
            ha="left", va="top", fontsize=labelsize, zorder=9)


def north_arrow(ax, fx=0.93, fy=0.70, length_frac=0.11):
    """True-north arrow following the local meridian (direction logic
    copied from the original project; label kept close to the tip so
    it stays inside the frame)."""
    inv = ax.transData.inverted()
    bx, by = inv.transform(ax.transAxes.transform((fx, fy)))
    lon, lat = FROM_P.transform(bx, by)
    x2, y2 = proj(lon, lat + 0.25)
    d = np.array([x2 - bx, y2 - by], dtype=float)
    d = d / np.hypot(*d)
    span = (ax.get_ylim()[1] - ax.get_ylim()[0]) * length_frac
    ex, ey = bx + d[0] * span, by + d[1] * span
    ax.annotate("", xy=(ex, ey), xytext=(bx, by),
                arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2,
                                mutation_scale=8.5), zorder=10)
    ax.text(ex + d[0] * span * 0.30, ey + d[1] * span * 0.30, "N",
            fontsize=10, fontweight="bold", ha="center", va="center",
            zorder=10)


CASES = [
    # key, title, data dir, scale bar (km)
    ("ida", "(a) Ida 2021", OLD_DATA, 20),
    ("idalia", "(b) Idalia 2023", NEW_DATA, 10),
    ("florence", "(c) Florence 2018", NEW_DATA, 10),
    ("helene", "(d) Helene 2024", OLD_DATA, 5),
    ("milton", "(e) Milton 2024", OLD_DATA, 5),
]

# Panel cell aspect ratio (width / height) the extents are expanded
# toward, following the target-ratio approach of the original fig3 code;
# expansion of either dimension is capped so no panel's context is
# padded more than 1.9x beyond its 12%-buffered data extent.
TARGET_RATIO = 0.95
MAX_EXPAND = 1.9


def load(data_dir, kind, storm):
    return gpd.read_file(data_dir / f"{kind}_{storm}.geojson").to_crs(CRS_PROJ)


def panel(ax, storm, title, data_dir, bar_km):
    foot = load(data_dir, "footprint", storm)
    ref = load(data_dir, "reference", storm)
    marsh = load(data_dir, "marsh_in_paths", storm)
    paths = load(data_dir, "paths", storm)

    # Extent: union of reference + footprint, buffered 12% per side.
    b = np.vstack([foot.total_bounds, ref.total_bounds])
    xmin, ymin = b[:, :2].min(axis=0)
    xmax, ymax = b[:, 2:].max(axis=0)
    w, h = xmax - xmin, ymax - ymin
    xlim = [xmin - 0.12 * w, xmax + 0.12 * w]
    ylim = [ymin - 0.12 * h, ymax + 0.12 * h]
    # Expand (never crop) the deficient dimension toward the panel
    # aspect ratio, capped at MAX_EXPAND, so panels fill their cells
    # without hiding any data.
    xs, ys = xlim[1] - xlim[0], ylim[1] - ylim[0]
    if xs < TARGET_RATIO * ys:
        new_xs = min(TARGET_RATIO * ys, xs * MAX_EXPAND)
        cx = sum(xlim) / 2
        xlim = [cx - new_xs / 2, cx + new_xs / 2]
    else:
        new_ys = min(xs / TARGET_RATIO, ys * MAX_EXPAND)
        cy = sum(ylim) / 2
        ylim = [cy - new_ys / 2, cy + new_ys / 2]
    xlim, ylim = tuple(xlim), tuple(ylim)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    # 1. Land + coastline (Natural Earth context, clipped to a lon/lat box
    #    slightly larger than the panel).
    corners = [FROM_P.transform(x, y) for x in xlim for y in ylim]
    ll_box = box(min(c[0] for c in corners) - 0.15,
                 min(c[1] for c in corners) - 0.15,
                 max(c[0] for c in corners) + 0.15,
                 max(c[1] for c in corners) + 0.15)
    land = gpd.clip(LAND_LL, ll_box).to_crs(CRS_PROJ)
    land.plot(ax=ax, facecolor=LAND_FILL, edgecolor="none", zorder=0)
    coast = gpd.clip(COAST_LL, ll_box).to_crs(CRS_PROJ)
    coast.plot(ax=ax, color=COAST_EDGE, linewidth=0.55, zorder=1)

    # Clip the vector layers to the panel window for drawing.
    win = box(xlim[0], ylim[0], xlim[1], ylim[1])
    marsh_w = marsh[marsh.geometry.intersects(win)]
    ref_w = ref[ref.geometry.intersects(win)]
    foot_w = foot[foot.geometry.intersects(win)]
    paths_w = paths[paths.geometry.intersects(win)]

    # 2. Marsh crossed by paths: muted green, no edge.
    marsh_w.plot(ax=ax, facecolor=MUTED_GREEN, edgecolor="none", zorder=2)
    # 3. Reference marsh: orange, alpha 0.55, thin dark edge.
    ref_w.plot(ax=ax, facecolor=ORANGE, edgecolor="#333333",
               linewidth=0.35, alpha=0.55, zorder=3)
    # 4. Analysed footprint marsh: vermillion, alpha 0.85, dark edge
    #    (slightly thicker so the small Helene/Milton clusters read).
    foot_w.plot(ax=ax, facecolor=VERMILLION, edgecolor="#7a2e00",
                linewidth=0.8, alpha=0.85, zorder=4)
    # 5. Tornado path footprints: outline only, dark grey.
    paths_w.plot(ax=ax, facecolor="#000000", alpha=0.08,
                 edgecolor=PATH_EDGE, linewidth=0.5, zorder=5)

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, loc="left")

    scale_bar(ax, bar_km, nseg=2, labelsize=7.5)
    north_arrow(ax, fx=0.93, fy=0.70, length_frac=0.11)

    print(f"{storm}: extent x {xlim[0]:.0f}..{xlim[1]:.0f} "
          f"({(xlim[1]-xlim[0])/1000:.1f} km), y {ylim[0]:.0f}..{ylim[1]:.0f} "
          f"({(ylim[1]-ylim[0])/1000:.1f} km); features in window: "
          f"marsh {len(marsh_w)}/{len(marsh)}, reference {len(ref_w)}/{len(ref)}, "
          f"footprint {len(foot_w)}/{len(foot)}, paths {len(paths_w)}/{len(paths)}")


def main():
    fig = plt.figure(figsize=(6.85, 5.9))
    # 3 panels on the top row, 2 centred on the bottom row (6-col grid).
    gs = fig.add_gridspec(2, 6, hspace=0.55, wspace=0.9,
                          left=0.03, right=0.97, top=0.90, bottom=0.03)
    slots = [(0, 0, 2), (0, 2, 4), (0, 4, 6), (1, 1, 3), (1, 3, 5)]
    for (storm, title, data_dir, bar_km), (r, c0, c1) in zip(CASES, slots):
        ax = fig.add_subplot(gs[r, c0:c1])
        panel(ax, storm, title, data_dir, bar_km)

    handles = [
        Patch(facecolor="none", edgecolor=PATH_EDGE, linewidth=0.8,
              label="Path footprints"),
        Patch(facecolor=VERMILLION, edgecolor="#7a2e00", linewidth=0.6,
              label="Analysed footprint marsh"),
        Patch(facecolor=ORANGE, edgecolor="#333333", linewidth=0.5,
              label="Reference marsh"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0), fontsize=7.6,
               handlelength=1.3, handleheight=1.0, columnspacing=1.0)

    fig.savefig(FIG / "fig4_case_marsh_maps.png", dpi=300)
    fig.savefig(FIG / "fig4_case_marsh_maps.pdf")
    plt.close(fig)
    print("wrote", FIG / "fig4_case_marsh_maps.png")
    print("wrote", FIG / "fig4_case_marsh_maps.pdf")


if __name__ == "__main__":
    main()
