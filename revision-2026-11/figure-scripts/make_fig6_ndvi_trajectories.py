"""Build Figure 6: NDVI trajectories for five TC cases.

Five panels, layout 3 + 2 (two rows), maximum width 6.85 in, white
background, one shared legend in a band above the panels.

Inputs are the trajectory CSVs produced by the analysis pipelines:
  Ida, Helene, Milton:
    ~/workspace/moore-pitch/angle2-tc-tornadoes/results/trajectories_<storm>.csv
  Idalia, Florence:
    ~/workspace/moore-pitch/angle2-revision-2026-11/analysis/
        cases_idalia_florence/results/trajectories_<storm>.csv

Outputs:
  figures/fig6_ndvi_trajectories.png (300 dpi)
  figures/fig6_ndvi_trajectories.pdf (vector)

Font: Liberation Serif, a metric-compatible substitute for Times New
Roman. Colours: Okabe-Ito palette.

Common y range: the specified 0.2 to 0.95 is widened at the bottom to
0.10 to 0.95 because the Helene reference series falls to 0.131,
below 0.2. No other series falls outside 0.2 to 0.95.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

REV = Path(__file__).resolve().parent.parent
ORIG = Path.home() / "workspace" / "moore-pitch" / "angle2-tc-tornadoes"
FIG = REV / "figures"
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

BLUE = "#0072B2"
VERMILLION = "#D55E00"
GREY = "#666666"

YLIM = (0.10, 0.95)  # widened from (0.20, 0.95): Helene reference min 0.131
XLIM = (-7.5, 24.5)

PANELS = [
    ("(a) Ida 2021", ORIG / "results" / "trajectories_ida.csv"),
    ("(b) Idalia 2023",
     REV / "analysis" / "cases_idalia_florence" / "results"
     / "trajectories_idalia.csv"),
    ("(c) Florence 2018 (HLS-equivalent)",
     REV / "analysis" / "cases_idalia_florence" / "results"
     / "trajectories_florence.csv"),
    ("(d) Helene 2024", ORIG / "results" / "trajectories_helene.csv"),
    ("(e) Milton 2024", ORIG / "results" / "trajectories_milton.csv"),
]


def main():
    fig, axes = plt.subplots(2, 3, figsize=(6.85, 4.9),
                             sharex=True, sharey=True)
    axes = axes.ravel()

    for i, (title, path) in enumerate(PANELS):
        ax = axes[i]
        df = pd.read_csv(path).sort_values("month_offset")
        print(f"{title}: rows={len(df)} "
              f"month_offset {df['month_offset'].min():.2f} to "
              f"{df['month_offset'].max():.2f} "
              f"footprint {df['footprint_ndvi'].min():.3f}-"
              f"{df['footprint_ndvi'].max():.3f} "
              f"reference {df['reference_ndvi'].min():.3f}-"
              f"{df['reference_ndvi'].max():.3f}")
        ax.axvline(0, color=GREY, lw=0.8, zorder=1)
        ax.plot(df["month_offset"], df["footprint_ndvi"],
                color=VERMILLION, lw=1.1, marker="o", ms=3.0,
                markeredgewidth=0.4, zorder=3)
        ax.plot(df["month_offset"], df["reference_ndvi"],
                color=BLUE, lw=1.1, ls="--", marker="s", ms=3.0,
                markeredgewidth=0.4, zorder=2)
        ax.set_title(title, loc="left")
        ax.set_xlim(*XLIM)
        ax.set_ylim(*YLIM)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8])
        ax.tick_params(direction="out", length=3, width=0.6)
        for spine in ax.spines.values():
            spine.set_linewidth(0.7)

    # Sixth cell (bottom right) is empty in the 3 + 2 layout.
    axes[5].axis("off")

    # Axis labels: y on the left column only, x on the bottom row only.
    for i in (0, 3):
        axes[i].set_ylabel("NDVI")
    for i in (3, 4):
        axes[i].set_xlabel("Months relative to landfall")

    handles = [
        Line2D([0], [0], color=VERMILLION, lw=1.1, marker="o", ms=3.0,
               label="Footprint marsh"),
        Line2D([0], [0], color=BLUE, lw=1.1, ls="--", marker="s",
               ms=3.0, label="Reference marsh"),
        Line2D([0], [0], color=GREY, lw=0.8, label="Landfall"),
    ]
    fig.legend(handles=handles, loc="upper center", ncol=3,
               frameon=False, bbox_to_anchor=(0.5, 1.0),
               handlelength=2.2, columnspacing=1.6)

    fig.tight_layout(rect=(0, 0, 1, 0.94), h_pad=1.2, w_pad=1.0)

    out_png = FIG / "fig6_ndvi_trajectories.png"
    out_pdf = FIG / "fig6_ndvi_trajectories.pdf"
    fig.savefig(out_png, dpi=300)
    fig.savefig(out_pdf)
    plt.close(fig)
    print(f"wrote {out_png}")
    print(f"wrote {out_pdf}")
    print(f"y range used: {YLIM[0]} to {YLIM[1]}")


if __name__ == "__main__":
    main()
