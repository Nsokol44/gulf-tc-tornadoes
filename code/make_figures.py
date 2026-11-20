"""Build publication figures for the TC tornado manuscript.

Figures 1 and 3 are projected maps (CONUS Albers Equal Area,
EPSG:5070) with Natural Earth 1:10m state and province boundaries,
labelled states, coastal cities, graticules with coordinate labels,
scale bars and true-north arrows. Figure 2 (bars) and the NDVI
trajectory figure (saved as fig5; Figure 4 in the manuscript is the
satellite imagery figure built by make_fig_imagery.py) are unchanged
in content from the original build.

Inputs are pipeline outputs only (results/ and data/). Outputs are
300 dpi PNG and PDF files in figures/. Font: Liberation Serif, a
metric compatible substitute for Times New Roman, which is not
installed on this machine.
"""
import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer
from shapely.geometry import box

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = ROOT / "results"
FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

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

LAND_LL = gpd.read_file(DATA / "ne_10m_land.zip")
STATES_LL = gpd.read_file(DATA / "ne_10m_admin_1_states_provinces.zip")
COAST = gpd.read_file(DATA / "ne_10m_coastline.zip")

LAND_FILL = "#f7f4ec"
WATER_FILL = "#e9eff3"
STATE_EDGE = "#a3a3a3"
COAST_EDGE = "#545454"
GRAT = "#c3d0d7"


def proj(lon, lat):
    return TO_P.transform(lon, lat)


def basemap(ax, lonlat_box, state_labels=(), cities=(), land=True):
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
    for name, lon, lat, fs in state_labels:
        x, y = proj(lon, lat)
        ax.text(x, y, name, fontsize=fs, color="#555555", ha="center",
                va="center", zorder=6, fontweight="bold",
                path_effects=[pe.withStroke(linewidth=2.2,
                                            foreground=LAND_FILL)])
    for name, lon, lat, dx, dy, ha in cities:
        x, y = proj(lon, lat)
        ax.plot([x], [y], marker="o", ms=3.2, color="#222222",
                mec="white", mew=0.6, zorder=7)
        ax.annotate(name, (x, y), textcoords="offset points",
                    xytext=(dx, dy), fontsize=7.5, color="#222222",
                    ha=ha, va="center", zorder=8,
                    path_effects=[pe.withStroke(linewidth=2.4,
                                                foreground="white")])


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
    """Alternating black and white scale bar at data coords (x, y).
    The caller must place y high enough that the labels below the
    bar stay inside the axes (roughly total_km * 300 m of clearance
    below y)."""
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


def fmt_deg(v, step):
    s = f"{v:.2f}" if step < 0.1 else f"{v:.1f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def state_labels_for_window(xlim, ylim):
    """Postal labels for US states covering a real share of a panel
    window, placed at the representative point of each state's part
    of the window (guaranteed on land, inside the panel)."""
    lon0, lat0 = FROM_P.transform(xlim[0], ylim[0])
    lon1, lat1 = FROM_P.transform(xlim[1], ylim[1])
    ll = box(min(lon0, lon1), min(lat0, lat1),
             max(lon0, lon1), max(lat0, lat1))
    us = STATES_LL[STATES_LL.admin == "United States of America"]
    inter = gpd.clip(us, ll).to_crs(CRS_PROJ)
    waream = (xlim[1] - xlim[0]) * (ylim[1] - ylim[0])
    out = []
    for _, r in inter.iterrows():
        if r.geometry.area > 0.03 * waream:
            p = r.geometry.representative_point()
            out.append((r["postal"], p.x, p.y, 8.5))
    return out


def north_arrow(ax, fx=0.955, fy=0.845, length_frac=0.085):
    """True-north arrow: direction follows the local meridian, so the
    arrow accounts for meridian convergence in the projection."""
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


# ----------------------------------------------------------------------
# Figure 1: climatology map
# ----------------------------------------------------------------------
def fig1():
    df = pd.read_parquet(RES / "tc_tornadoes.parquet")
    extent = (-99, -79, 24, 39)
    inside = df[(df.slon >= extent[0]) & (df.slon <= extent[1])
                & (df.slat >= extent[2]) & (df.slat <= extent[3])]
    print(f"fig1: {len(inside)} of {len(df)} points inside mapped domain")

    corners = [proj(lon, lat) for lon in (extent[0], extent[1])
               for lat in (extent[2], extent[3])]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    xlim = (min(xs) - 30000, max(xs) + 30000)
    ylim = (min(ys) - 30000, max(ys) + 30000)

    fig, ax = plt.subplots(figsize=(6.85, 5.15))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    state_labels = [
        ("TX", -98.2, 33.2, 9), ("OK", -97.4, 35.7, 9),
        ("AR", -92.4, 34.9, 9), ("LA", -92.0, 31.1, 9),
        ("MS", -89.7, 32.7, 9), ("AL", -86.8, 32.8, 9),
        ("TN", -86.4, 35.9, 9), ("KY", -84.9, 37.6, 8),
        ("GA", -83.4, 32.7, 9), ("FL", -82.3, 28.3, 9),
        ("SC", -80.9, 33.9, 8.5), ("NC", -79.3, 35.4, 8.5),
        ("MEXICO", -97.6, 25.3, 8),
    ]
    cities = [
        ("Houston", -95.37, 29.76, 6, 2, "left"),
        ("New Orleans", -90.07, 29.95, 6, 3, "left"),
        ("Mobile", -88.04, 30.69, 6, 2, "left"),
        ("Pensacola", -87.22, 30.42, 6, -6, "left"),
        ("Tampa", -82.46, 27.95, -6, 2, "right"),
        ("Jacksonville", -81.66, 30.33, 6, 2, "left"),
        ("Charleston", -79.93, 32.78, 6, 2, "left"),
        ("Atlanta", -84.39, 33.75, 6, 2, "left"),
    ]
    basemap(ax, (-100.5, 22.5, -77.5, 40.5), state_labels, cities)
    ax.text(*proj(-90.6, 25.75), "Gulf of Mexico", fontsize=9.5,
            style="italic", color="#46606e", ha="center", zorder=3)
    eras = [("study_1995_2015", BLUE, "Study era 1995 to 2015"),
            ("extension_2016_2025", ORANGE, "Extension era 2016 to 2025")]
    for era, colour, _ in eras:
        sub = inside[inside.era == era]
        weak = sub[sub.rating.isna() | (sub.rating < 2)]
        strong = sub[sub.rating >= 2]
        wx, wy = proj(weak.slon.to_numpy(), weak.slat.to_numpy())
        sx, sy = proj(strong.slon.to_numpy(), strong.slat.to_numpy())
        ax.scatter(wx, wy, s=5, c=colour, marker="o",
                   linewidths=0, alpha=0.55, zorder=4)
        ax.scatter(sx, sy, s=42, c=colour, marker="D",
                   edgecolors="black", linewidths=0.5, zorder=5)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    graticule(ax, [-96, -92, -88, -84, -80], [27, 30, 33, 36],
              (extent[0], extent[1]), (extent[2], extent[3]),
              labelsize=8)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    bx, by = proj(-94.5, 24.65)
    scale_bar(ax, bx, by, 200, nseg=2, labelsize=8, backdrop=False)
    north_arrow(ax, fx=0.955, fy=0.83)
    handles = [
        Line2D([], [], marker="o", ls="", color=BLUE, markersize=5,
               label="Study era 1995 to 2015, F/EF0 to 1"),
        Line2D([], [], marker="o", ls="", color=ORANGE, markersize=5,
               label="Extension era 2016 to 2025, F/EF0 to 1 or unrated"),
        Line2D([], [], marker="D", ls="", color=BLUE, markeredgecolor="black",
               markersize=6, label="Study era, strong F/EF2 to 3"),
        Line2D([], [], marker="D", ls="", color=ORANGE, markeredgecolor="black",
               markersize=6, label="Extension era, strong F/EF2 to 3"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    save(fig, "fig1_climatology_map")


# ----------------------------------------------------------------------
# Figure 2: era comparison
# ----------------------------------------------------------------------
def fig2():
    summary = json.loads((RES / "climatology_summary.json").read_text())
    by_year = summary["by_year"]
    years = list(range(1995, 2026))
    counts = [by_year[str(y)]["tc_tornadoes"] if str(y) in by_year else 0
              for y in years]
    # Shares from the regenerated summary (quadrants by era, percent)
    quads = ["NE", "SE", "SW", "NW"]
    qe = summary["quadrants_true_north_by_era"]
    study = [qe["study_1995_2015"][q]["share_pct"] for q in quads]
    ext = [qe["extension_2016_2025"][q]["share_pct"] for q in quads]

    fig, axes = plt.subplots(2, 1, figsize=(6.85, 5.6),
                             gridspec_kw={"height_ratios": [1.25, 1]})
    ax = axes[0]
    colours = [BLUE if y <= 2015 else ORANGE for y in years]
    bars = ax.bar(years, counts, color=colours, width=0.8,
                  edgecolor="#333333", linewidth=0.3)
    for y, b in zip(years, bars):
        if y in (2024, 2025):
            b.set_hatch("///")
            b.set_edgecolor("black")
    for y, c in ((2004, 299), (2005, 237)):
        ax.annotate(f"{y}: {c}", xy=(y, c), xytext=(y + 0.3, c + 22),
                    ha="center", fontsize=8.5,
                    arrowprops=dict(arrowstyle="-", lw=0.6))
    ax.set_ylabel("TC tornadoes (count)")
    ax.set_xlabel("Year")
    ax.set_xlim(1994.4, 2025.6)
    ax.set_xticks(range(1995, 2026, 2))
    ax.set_ylim(0, 335)
    ax.set_title("(a) Annual primary sample TC tornado counts", loc="left")

    ax = axes[1]
    x = np.arange(len(quads))
    w = 0.38
    ax.bar(x - w / 2, study, w, color=BLUE, edgecolor="#333333",
           linewidth=0.3, label="Study era 1995 to 2015")
    ax.bar(x + w / 2, ext, w, color=ORANGE, edgecolor="#333333",
           linewidth=0.3, label="Extension era 2016 to 2025")
    for xi, v in zip(x - w / 2, study):
        ax.text(xi, v + 1.5, f"{v:.1f}", ha="center", fontsize=7.5)
    for xi, v in zip(x + w / 2, ext):
        ax.text(xi, v + 1.5, f"{v:.1f}", ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels(["NE (0 to 90 deg)", "SE (90 to 180 deg)",
                        "SW (180 to 270 deg)", "NW (270 to 360 deg)"])
    ax.set_ylabel("Share of era tornadoes (percent)")
    ax.set_ylim(0, 84)
    ax.set_title("(b) Diagonal quadrant shares by era, bearing from TC center",
                 loc="left")
    handles = [Patch(facecolor=BLUE, edgecolor="#333333",
                     label="Study era 1995 to 2015"),
               Patch(facecolor=ORANGE, edgecolor="#333333",
                     label="Extension era 2016 to 2025"),
               Patch(facecolor="white", hatch="///", edgecolor="black",
                     label="2024 to 2025, operational rule attribution (panel a only)")]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.0))
    fig.tight_layout(rect=(0, 0, 1, 0.91))
    save(fig, "fig2_era_comparison")


# ----------------------------------------------------------------------
# Figure 3: case marsh maps. Layout follows the data shapes: Ida's
# alongshore window spans the full width on top; the two compact
# windows sit side by side below.
# ----------------------------------------------------------------------
FIG3_CITIES = {
    "ida": [("Bay St. Louis", -89.330, 30.309),
            ("Gulfport", -89.093, 30.367)],
    "helene": [("Charleston", -79.933, 32.777)],
    "milton": [("Fort Pierce", -80.325, 27.452),
               ("Port St. Lucie", -80.359, 27.293)],
}
FIG3_TITLES = {
    "ida": ("(a) Ida, landfall 29 Aug 2021", "Peak wind 130 kt"),
    "helene": ("(b) Helene, landfall 27 Sep 2024", "Peak wind 120 kt"),
    "milton": ("(c) Milton, landfall 10 Oct 2024", "Peak wind 155 kt"),
}
# North arrow placement per panel (axes fractions); Helene's arrow
# sits top-left to stay clear of the Charleston label.
FIG3_ARROWS = {"ida": (0.945, 0.70), "helene": (0.075, 0.70),
               "milton": (0.945, 0.70)}


def _fig3_panel(ax, s, target_ratio):
    paths = gpd.read_file(DATA / f"paths_{s}.geojson").to_crs(CRS_PROJ)
    foot = gpd.read_file(DATA / f"footprint_{s}.geojson").to_crs(CRS_PROJ)
    ref = gpd.read_file(DATA / f"reference_{s}.geojson").to_crs(CRS_PROJ)
    mpath_file = DATA / f"marsh_in_paths_{s}.geojson"
    b = np.vstack([foot.total_bounds, ref.total_bounds])
    xmin, ymin = b[:, :2].min(axis=0)
    xmax, ymax = b[:, 2:].max(axis=0)
    mx = max(2500.0, 0.30 * (xmax - xmin))
    my = max(2500.0, 0.30 * (ymax - ymin))
    xspan = (xmax - xmin) + 2 * mx
    yspan = (ymax - ymin) + 2 * my
    if xspan < target_ratio * yspan:
        mx += (target_ratio * yspan - xspan) / 2
    else:
        my += (xspan / target_ratio - yspan) / 2
    xlim = (xmin - mx, xmax + mx)
    ylim = (ymin - my, ymax + my)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    corners = [FROM_P.transform(x, y) for x in xlim for y in ylim]
    ll_box = (min(c[0] for c in corners) - 0.12,
              min(c[1] for c in corners) - 0.12,
              max(c[0] for c in corners) + 0.12,
              max(c[1] for c in corners) + 0.12)
    cities = []
    for name, lon, lat in FIG3_CITIES[s]:
        cx, cy = proj(lon, lat)
        if xlim[0] < cx < xlim[1] and ylim[0] < cy < ylim[1]:
            fx = (cx - xlim[0]) / (xlim[1] - xlim[0])
            dx, ha = (-6, "right") if fx > 0.78 else (6, "left")
            cities.append((name, lon, lat, dx, 2, ha))
    basemap(ax, ll_box, (), cities)
    for postal, px, py, fs in state_labels_for_window(xlim, ylim):
        ax.text(px, py, postal, fontsize=fs, color="#555555", ha="center",
                va="center", zorder=6, fontweight="bold",
                path_effects=[pe.withStroke(linewidth=2.2,
                                            foreground=LAND_FILL)])
    ref.plot(ax=ax, facecolor=GREEN, edgecolor="none", alpha=0.45,
             zorder=3)
    paths.plot(ax=ax, facecolor=ORANGE, edgecolor="#8a5a00",
               linewidth=0.4, alpha=0.75, zorder=4)
    if mpath_file.exists():
        mp = gpd.read_file(mpath_file).to_crs(CRS_PROJ)
        mp.plot(ax=ax, facecolor=VERMILLION, edgecolor=VERMILLION,
                linewidth=0.6, alpha=0.95, zorder=5)
    foot.plot(ax=ax, facecolor="none", edgecolor="white", linewidth=2.4,
              zorder=6)
    foot.plot(ax=ax, facecolor="none", edgecolor=BLUE, linewidth=1.1,
              zorder=7)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal")
    ax.set_xlabel("")
    ax.set_ylabel("")
    lon_lo, lat_lo = FROM_P.transform(xlim[0], ylim[0])
    lon_hi, lat_hi = FROM_P.transform(xlim[1], ylim[1])
    lo_min, lo_max = min(lon_lo, lon_hi), max(lon_lo, lon_hi)
    la_min, la_max = min(lat_lo, lat_hi), max(lat_lo, lat_hi)
    for step in (0.05, 0.1, 0.2, 0.25, 0.5):
        if (lo_max - lo_min) / step <= 4.2 and (la_max - la_min) / step <= 4.2:
            break
    lons = np.arange(np.ceil(lo_min / step) * step, lo_max, step)
    lats = np.arange(np.ceil(la_min / step) * step, la_max, step)
    graticule(ax, lons, lats, (lo_min - 0.05, lo_max + 0.05),
              (la_min - 0.05, la_max + 0.05), labelsize=6.8,
              fmt=lambda v: fmt_deg(v, step))
    ax.tick_params(labelsize=6.8)
    t1, t2 = FIG3_TITLES[s]
    ax.set_title(f"{t1}\n{t2}", loc="left", fontsize=8.6)
    xspan_km = (xlim[1] - xlim[0]) / 1000.0
    bar_km = 20 if xspan_km > 42 else 10
    bx = xlim[0] + 0.035 * (xlim[1] - xlim[0])
    by = ylim[0] + 0.15 * (ylim[1] - ylim[0])
    scale_bar(ax, bx, by, bar_km, nseg=2, labelsize=6.8)
    afx, afy = FIG3_ARROWS[s]
    north_arrow(ax, fx=afx, fy=afy, length_frac=0.13)


def fig3():
    fig = plt.figure(figsize=(6.85, 5.35))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.12],
                          hspace=0.42, wspace=0.16)
    ax_ida = fig.add_subplot(gs[0, :])
    ax_hel = fig.add_subplot(gs[1, 0])
    ax_mil = fig.add_subplot(gs[1, 1])
    _fig3_panel(ax_ida, "ida", 2.55)
    _fig3_panel(ax_hel, "helene", 1.18)
    _fig3_panel(ax_mil, "milton", 1.18)
    handles = [
        Patch(facecolor=ORANGE, edgecolor="#8a5a00", label="Tornado paths"),
        Line2D([], [], color=BLUE, lw=1.4, label="Analyzed footprint"),
        Patch(facecolor=GREEN, alpha=0.45, label="Reference marsh ring"),
        Patch(facecolor=VERMILLION, label="Marsh within tornado paths"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 1.0), fontsize=7.8,
               handlelength=1.4, columnspacing=1.1)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    save(fig, "fig3_case_marsh_maps")


# ----------------------------------------------------------------------
# Figure 5: NDVI trajectories (Figure 4 in the original build; the new
# satellite imagery figure takes the Figure 4 slot)
# ----------------------------------------------------------------------
def fig5():
    traj = pd.read_csv(RES / "marsh_trajectories.csv")
    marsh = json.loads((RES / "marsh_summary.json").read_text())
    storms = [("ida", "Ida"), ("helene", "Helene"), ("milton", "Milton")]
    fig, axes = plt.subplots(1, 3, figsize=(6.85, 3.6), sharey=True)
    for ax, (s, name), label in zip(axes, storms, ["(a)", "(b)", "(c)"]):
        sub = traj[traj.storm == s].sort_values("month_offset")
        ax.plot(sub.month_offset, sub.footprint_ndvi, color=BLUE, lw=1.4,
                marker="o", markersize=2.5)
        ax.plot(sub.month_offset, sub.reference_ndvi, color=ORANGE, lw=1.4,
                marker="s", markersize=2.5)
        ax2 = ax.twinx()
        ax2.scatter(sub.month_offset, sub.anomaly, s=10, color=VERMILLION,
                    alpha=0.75, linewidths=0, zorder=5)
        ax2.set_ylim(-0.34, 0.38)
        ax2.axhline(0, color=VERMILLION, lw=0.5, alpha=0.4)
        if s == "milton":
            ax2.set_ylabel("NDVI anomaly (unitless)", fontsize=8)
        else:
            ax2.set_yticklabels([])
        ax2.tick_params(labelsize=7.5)
        ax.axvline(0, color=GREY, lw=0.9, ls="--")
        info = marsh[s]
        row = sub[sub.month == info["immediate_month"]]
        if len(row):
            r = row.iloc[0]
            ax2.annotate(f"{info['immediate_anomaly']:+.3f}\n{info['immediate_month']}",
                         xy=(r.month_offset, r.anomaly),
                         xytext=(r.month_offset + 3.2, r.anomaly + 0.10),
                         fontsize=7.5, color=VERMILLION,
                         arrowprops=dict(arrowstyle="-", lw=0.6,
                                         color=VERMILLION))
        ax.set_title(f"{label} {name}", loc="left")
        ax.set_xlabel("Months relative to landfall")
        ax.set_xlim(-8, 25)
        ax.set_ylim(0.08, 0.98)
    axes[0].set_ylabel("NDVI (unitless)")
    handles = [
        Line2D([], [], color=BLUE, lw=1.4, marker="o", markersize=3,
               label="Footprint NDVI"),
        Line2D([], [], color=ORANGE, lw=1.4, marker="s", markersize=3,
               label="Reference NDVI"),
        Line2D([], [], color=VERMILLION, ls="", marker="o", markersize=4,
               label="Anomaly, footprint minus reference (right axis)"),
        Line2D([], [], color=GREY, lw=0.9, ls="--", label="Landfall month"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, 1.02))
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    save(fig, "fig5_ndvi_trajectories")


if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig5()
