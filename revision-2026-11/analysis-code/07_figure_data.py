"""07_figure_data.py

Data behind the updated Figures 1 and 2 (data only; no rendering):
- fig1_map_points.csv     : one row per sampled tornado (start location, year,
                            era, coast, rating, strong flag) for the sample map
- fig2_annual_counts.csv  : annual tornado counts by coast and pooled, with
                            storm counts (Figure 2a)
- fig2_quadrant_shares.csv: diagonal quadrant shares by era x coast (Figure 2b)
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent.parent
RESULTS = HERE / "results"


def main():
    s = pd.read_parquet(RESULTS / "sample_two_coast.parquet")
    fig1 = s[["tornado_id", "yr", "era", "coast", "slat", "slon", "rating", "strong", "storm_id", "tc_name_clean"]]
    fig1 = fig1.rename(columns={"slat": "lat", "slon": "lon", "yr": "year"})
    fig1.to_csv(RESULTS / "fig1_map_points.csv", index=False)

    by = pd.read_csv(RESULTS / "by_year.csv")
    storms = (s.groupby(["yr", "coast"])["storm_id"].nunique().unstack(fill_value=0)
              .reindex(range(1995, 2024), fill_value=0))
    by["storms_gulf"] = storms.get("gulf", 0).values
    by["storms_atlantic"] = storms.get("atlantic", 0).values
    by["storms_pooled"] = by["storms_gulf"] + by["storms_atlantic"]
    by.to_csv(RESULTS / "fig2_annual_counts.csv", index=False)

    rows = []
    for era in ["study_1995_2015", "extension_2016_2023", "all_1995_2023"]:
        for coast in ["gulf", "atlantic", "pooled"]:
            m = pd.Series(True, index=s.index)
            if era != "all_1995_2023":
                m &= s["era"] == era
            if coast != "pooled":
                m &= s["coast"] == coast
            sub = s[m]
            n = len(sub)
            row = dict(era=era, coast=coast, n=int(n))
            for q in ["NE", "SE", "SW", "NW"]:
                row[f"{q}_count"] = int((sub["quadrant"] == q).sum())
                row[f"{q}_pct"] = round(100 * (sub["quadrant"] == q).mean(), 1) if n else None
            rows.append(row)
    pd.DataFrame(rows).to_csv(RESULTS / "fig2_quadrant_shares.csv", index=False)
    print("figure data written:", len(fig1), "map points")


if __name__ == "__main__":
    main()
