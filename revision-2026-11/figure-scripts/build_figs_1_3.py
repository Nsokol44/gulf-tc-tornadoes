"""Build Figures 1, 2 and 3 for the Physical Geography revision.

Revision-era figures only. Inputs are the prepared figure-data CSVs in
analysis/results/ plus Natural Earth 1:10m zips from the original
project's data/ folder (read-only). Outputs are 300 dpi PNG and vector
PDF files in figures/.

Helper functions (basemap / graticule / scale_bar / north_arrow / save),
the rcParams block and the Okabe-Ito palette are copied and adapted from
the original project's code/make_figures.py (not imported).

Font: Liberation Serif, a metric-compatible substitute for Times New
Roman.
"""
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer
from shapely.geometry import box

REV = Path(__file__).resolve().parent.parent
RES = REV / "analysis" / "results"
FIG = REV / "figures"
FIG.mkdir(exist_ok=True)
NE_DATA = REV.parent / "angle2-tc-tornadoes" / "data"

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

# Okabe and Ito colourblind safe palette
BLUE = "#0072B2"
ORANGE = "#E69F00"
VERMILLION = "#D55E00"
GREEN = "#009E73"
GREY = "#666666"
LIGHTGREY = "#BBBBBB"

CRS_PROJ = "EPSG:5070"
TO_P = Transformer.from_crs(4326, CRS_PROJ, always_xy=True)
FROM_P = Transformer.from_crs(CRS_PROJ, 4326, always_xy=True)

LAND_LL = gpd.read_file(NE_DATA / "ne_10m_land.zip")
STATES_LL = gpd.read_file(NE_DATA / "ne_10m_admin_1_states_provinces.zip")
COAST = gpd.read_file(NE_DATA / "ne_10m_coastline.zip")

LAND_FILL = "#f7f4ec"
WATER_FILL = "#e9eff3"
STATE_EDGE = "#a3a3a3"
COAST_EDGE = "#545454"
GRAT = "#c3d0d7"

# Eastern US extent used by Figures 1 and 3 (lon0, lat0, lon1, lat1)
EXTENT = (-107.0, 24.0, -65.0, 50.0)


def proj(lon, lat):
    return TO_P.transform(lon, lat)


def basemap(ax, lonlat_box, land=True):
    """Draw land, state boundaries and coastline for a lon/lat box."""
    clip = box(*lonlat_box)
    ax.set_facecolor(WATER_FILL)
    if land:
        gpd.clip(LAND_LL, clip).to_crs(CRS_PROJ).plot(
            ax=ax, facecolor=LAND_FILL, edgecolor="none", zorder=0)
    st = gpd.clip(STATES_LL, clip)
    st.to_crs(CRS_PROJ).plot(ax=ax, facecolor="none",
                             edgecolor=STATE_EDGE, linewidth=0.4,
                             zorder=1)
    gpd.clip(COAST, clip).to_crs(CRS_PROJ).plot(
        ax=ax, color=COAST_EDGE, linewidth=0.55, zorder=2)


def graticule(ax, lons, lats, lon_range, lat_range, labelsize=7.5,
              fmt=lambda v: f"{v:.0f}"):
    """Draw a graticule and set coordinate tick labels on the
    bottom (longitude) and left (latitude) edges."""
    for lon in lons:
        la = np.linspace(lat_range[0], lat_range[1], 120)
        x, y = proj(np.full_like(la, lon, dtype=float), la)
        ax.plot(x, y, color=GRAT, lw=0.45, zorder=0.4)
    for lat in lats:
        lo = np.linspace(lon_range[0], lon_range[1], 120)
        x, y = proj(lo, np.full_like(lo, lat, dtype=float))
        ax.plot(x, y, color=GRAT, lw=0.45, zorder=0.4)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    xt, xl = [], []
    for lon in lons:
        la = np.linspace(lat_range[0], lat_range[1], 400)
        x, y = proj(np.full_like(la, lon, dtype=float), la)
        if y.min() <= y0 <= y.max():
            xt.append(np.interp(y0, y, x))
            xl.append(f"{fmt(abs(lon))}°W")
    yt, yl = [], []
    for lat in lats:
        lo = np.linspace(lon_range[0], lon_range[1], 400)
        x, y = proj(lo, np.full_like(lo, lat, dtype=float))
        if x.min() <= x0 <= x.max():
            yt.append(np.interp(x0, x, y))
            yl.append(f"{fmt(abs(lat))}°N")
    ax.set_xticks(xt)
    ax.set_xticklabels(xl, fontsize=labelsize)
    ax.set_yticks(yt)
    ax.set_yticklabels(yl, fontsize=labelsize)


def scale_bar(ax, x, y, total_km, nseg=2, labelsize=7.5, backdrop=True):
    """Alternating black and white scale bar at data coords (x, y)."""
    seg = total_km * 1000.0 / nseg
    if backdrop:
        ax.add_patch(Rectangle((x - total_km * 70, y - total_km * 300),
                               total_km * 1000.0 + total_km * 640,
                               total_km * 370, facecolor="white", alpha=0.55,
                               edgecolor="none", zorder=8.5))
    for i in range(nseg):
        ax.add_patch(Rectangle((x + i * seg, y), seg, total_km * 28,
                               facecolor="black" if i % 2 == 0 else "white",
                               edgecolor="black", lw=0.7, zorder=9))
    for i in range(nseg + 1):
        ax.text(x + i * seg, y - total_km * 160, f"{int(i * total_km / nseg)}",
                ha="center", va="top", fontsize=labelsize, zorder=9)
    ax.text(x + total_km * 1000.0 + total_km * 230, y - total_km * 160,
            "km", ha="left", va="top", fontsize=labelsize, zorder=9)


def north_arrow(ax, fx=0.955, fy=0.845, length_frac=0.085):
    """True-north arrow: direction follows the local meridian."""
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
    ax.text(ex + d[0] * span * 0.42, ey + d[1] * span * 0.42, "N",
            fontsize=10, fontweight="bold", ha="center", va="center",
            zorder=10)


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)
    print("wrote", name)


def map_limits(extent=EXTENT, pad=20000):
    corners = [proj(lon, lat) for lon in (extent[0], extent[2])
               for lat in (extent[1], extent[3])]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return (min(xs) - pad, max(xs) + pad), (min(ys) - pad, max(ys) + pad)


def finish_map_panel(ax, xlim, ylim, ylabel=True):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    graticule(ax, [-100, -90, -80, -70], [30, 35, 40, 45],
              (EXTENT[0], EXTENT[2]), (EXTENT[1], EXTENT[3]),
              labelsize=7.5)
    # The graticule helper only labels lines that cross the bottom/left
    # edges inside the window; at this wide extent several do not, so
    # set the edge tick positions directly (meridians sampled near the
    # bottom edge, parallels near the left edge).
    xt = [proj(lon, 25.5)[0] for lon in (-100, -90, -80, -70)]
    ax.set_xticks(xt)
    ax.set_xticklabels([f"{abs(lon)}°W" for lon in (-100, -90, -80, -70)],
                       fontsize=7.5)
    yt = [proj(-106.0, lat)[1] for lat in (30, 35, 40, 45)]
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{lat}°N" for lat in (30, 35, 40, 45)],
                       fontsize=7.5)
    if not ylabel:
        ax.set_yticklabels([])
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude" if ylabel else "")
    bx, by = proj(-106.0, 25.6)
    scale_bar(ax, bx, by, 500, nseg=2, labelsize=7.5, backdrop=False)
    north_arrow(ax, fx=0.96, fy=0.80)


# ----------------------------------------------------------------------
# Figure 1: sample map by era
# ----------------------------------------------------------------------
def fig1():
    df = pd.read_csv(RES / "fig1_map_points.csv")
    assert len(df) == 1772, len(df)
    xlim, ylim = map_limits()
    clip_box = (-108.5, 22.5, -63.5, 51.5)

    panels = [("study_1995_2015", "(a) Study era 1995-2015"),
              ("extension_2016_2023", "(b) Extension era 2016-2023")]
    coast_colour = {"gulf": BLUE, "atlantic": VERMILLION}

    fig, axes = plt.subplots(1, 2, figsize=(6.85, 3.7))
    for ax, (era, title) in zip(axes, panels):
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        basemap(ax, clip_box)
        sub = df[df.era == era]
        for coast, colour in coast_colour.items():
            csub = sub[sub.coast == coast]
            weak = csub[~csub.strong]
            strong = csub[csub.strong]
            x, y = proj(weak.lon.to_numpy(), weak.lat.to_numpy())
            ax.scatter(x, y, s=5, c=colour, marker="o", linewidths=0,
                       alpha=0.60, zorder=4)
            x, y = proj(strong.lon.to_numpy(), strong.lat.to_numpy())
            ax.scatter(x, y, s=30, c=colour, marker="o",
                       edgecolors="black", linewidths=0.5, zorder=5)
        finish_map_panel(ax, xlim, ylim, ylabel=(ax is axes[0]))
        ax.set_title(f"{title} (n = {len(sub):,})", loc="left")
        print(f"fig1 {era}: n={len(sub)}, "
              f"strong={int(sub.strong.sum())}")
    handles = [
        Line2D([], [], marker="o", ls="", color=BLUE, markersize=5,
               label="Gulf stratum"),
        Line2D([], [], marker="o", ls="", color=VERMILLION, markersize=5,
               label="Atlantic stratum"),
        Line2D([], [], marker="o", ls="", markerfacecolor="white",
               markeredgecolor="black", markersize=8,
               label="Strong (F/EF2-3)"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "fig1_sample_map")


# ----------------------------------------------------------------------
# Figure 2: era comparison
# ----------------------------------------------------------------------
def fig2():
    annual = pd.read_csv(RES / "fig2_annual_counts.csv")
    quad = pd.read_csv(RES / "fig2_quadrant_shares.csv")

    # Pool the quadrant shares across coasts by summing the coast rows
    # (the file's own pooled rows are used only as a cross-check).
    quads = ["NE", "SE", "SW", "NW"]
    pooled = {}
    for era in ("study_1995_2015", "extension_2016_2023"):
        rows = quad[(quad.era == era) & (quad.coast != "pooled")]
        n = int(rows.n.sum())
        pooled[era] = [100.0 * rows[f"{q}_count"].sum() / n for q in quads]
        chk = quad[(quad.era == era) & (quad.coast == "pooled")].iloc[0]
        assert int(chk.n) == n
        for q, v in zip(quads, pooled[era]):
            assert abs(v - chk[f"{q}_pct"]) < 0.15, (era, q, v)
        print(f"fig2 pooled {era}: n={n}, shares="
              f"{[round(v, 1) for v in pooled[era]]}")
    study = pooled["study_1995_2015"]
    ext = pooled["extension_2016_2023"]

    fig, axes = plt.subplots(2, 1, figsize=(6.85, 5.5),
                             gridspec_kw={"height_ratios": [1.15, 1]})
    ax = axes[0]
    ax.bar(annual.year, annual.gulf, width=0.8, color=BLUE,
           edgecolor="#333333", linewidth=0.3, label="Gulf")
    ax.bar(annual.year, annual.atlantic, width=0.8, bottom=annual.gulf,
           color=VERMILLION, edgecolor="#333333", linewidth=0.3,
           label="Atlantic")
    ax.set_ylabel("TC tornadoes (count)")
    ax.set_xlabel("Year")
    ax.set_xlim(1994.4, 2023.6)
    ax.set_xticks([1995, 1999, 2003, 2007, 2011, 2015, 2019, 2023])
    ax.set_title("(a) Annual TC tornado counts, 1995-2023", loc="left")

    ax = axes[1]
    x = np.arange(len(quads))
    w = 0.38
    ax.bar(x - w / 2, study, w, color=GREEN, edgecolor="#333333",
           linewidth=0.3, label="Study era")
    ax.bar(x + w / 2, ext, w, color=ORANGE, edgecolor="#333333",
           linewidth=0.3, label="Extension era")
    for xi, v in zip(x - w / 2, study):
        ax.text(xi, v + 1.6, f"{v:.1f}", ha="center", fontsize=7.5)
    for xi, v in zip(x + w / 2, ext):
        ax.text(xi, v + 1.6, f"{v:.1f}", ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(["NE", "SE", "SW", "NW"])
    ax.set_xlabel("Quadrant (bearing from TC centre)")
    ax.set_ylabel("Share of sample (%)")
    ax.set_ylim(0, max(study + ext) * 1.18)
    ax.set_title("(b) Diagonal quadrant shares by era, pooled across coasts",
                 loc="left")

    handles = [
        Patch(facecolor=BLUE, edgecolor="#333333", label="Gulf (a)"),
        Patch(facecolor=VERMILLION, edgecolor="#333333",
              label="Atlantic (a)"),
        Patch(facecolor=GREEN, edgecolor="#333333",
              label="Study era 1995-2015 (b)"),
        Patch(facecolor=ORANGE, edgecolor="#333333",
              label="Extension era 2016-2023 (b)"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, "fig2_era_comparison")


# ----------------------------------------------------------------------
# Figure 3: land-cover (wetland) footprint map
# ----------------------------------------------------------------------
def fig3():
    df = pd.read_csv(RES / "sample_with_landcover.csv")
    assert len(df) == 1772, len(df)
    df["clon"] = (df.slon + df.elon) / 2.0
    df["clat"] = (df.slat + df.elat) / 2.0
    df["wet_share"] = 100.0 * df.area_wetlands_ha / df.footprint_area_ha
    wet = df[df.intersects_wetlands]
    print(f"fig3: {len(wet)} of {len(df)} footprints intersect wetlands "
          f"({100.0 * len(wet) / len(df):.1f}%); "
          f"raw wet_share > 100% for {(wet.wet_share > 100).sum()} "
          f"tiny footprints (colour scale saturates at 100%)")

    xlim, ylim = map_limits()
    fig, ax = plt.subplots(figsize=(6.85, 5.6))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    basemap(ax, (-108.5, 22.5, -63.5, 51.5))
    x, y = proj(df.clon.to_numpy(), df.clat.to_numpy())
    ax.scatter(x, y, s=5, c=LIGHTGREY, marker="o", linewidths=0,
               alpha=0.5, zorder=4)
    x, y = proj(wet.clon.to_numpy(), wet.clat.to_numpy())
    sc = ax.scatter(x, y, s=11, c=wet.wet_share.to_numpy(), cmap="viridis",
                    vmin=0, vmax=100, marker="o", linewidths=0,
                    alpha=0.9, zorder=5)
    finish_map_panel(ax, xlim, ylim, ylabel=True)
    cbar = fig.colorbar(sc, ax=ax, pad=0.02, fraction=0.046)
    cbar.set_label("Wetland share of footprint area (%)")
    cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    save(fig, "fig3_landcover_map")


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
