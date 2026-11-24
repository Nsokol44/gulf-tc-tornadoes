"""03_climatology.py

Recompute every headline climatology quantity of the submitted paper under
the verified-years two-coast design (TCTOR 1995-2023 only).

Outputs (results/):
- table1_era_totals.csv      era x coast totals, storm counts, national shares
- table3_intensity.csv       rating distribution + weak/strong by era x coast
- table3_two_proportion.csv  strong-share two-proportion tests (study vs ext)
- table3_size_dpi.csv        path length / width / DPI medians and IQRs
- table4_geometry.csv        quadrant / half / coast-distance shares, median range
- by_year.csv                annual counts by coast (+ pooled, + all-US)
- by_storm.csv               per-storm tornado counts (all sampled storms)
- table2_cases.csv           the four case storms with counts from the ORIGINAL
                             pipeline outputs (not recomputed)
- era_peaks.csv              largest storms per era x coast (for Section 3.1 text)
"""
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"

ERAS = ["study_1995_2015", "extension_2016_2023"]
COASTS = ["gulf", "atlantic"]


def pct(x, n):
    return round(100.0 * x / n, 1) if n else np.nan


def sel(df, era=None, coast=None):
    """Boolean mask for an era (None or 'all_1995_2023' = all) and coast
    (None or 'pooled' = all)."""
    m = pd.Series(True, index=df.index)
    if era is not None and era != "all_1995_2023":
        m &= df["era"] == era
    if coast is not None and coast != "pooled":
        m &= df["coast"] == coast
    return m


def two_prop(sample, group_label):
    """Strong-share two-proportion test, extension vs study era."""
    rows = {}
    for era in ERAS:
        s = sample[sample["era"] == era]
        rated = s[s["rating"].notna()]
        rows[era] = (int((rated["rating"] >= 2).sum()), int(len(rated)))
    (x2, n2), (x1, n1) = rows[ERAS[1]], rows[ERAS[0]]
    if min(n1, n2) == 0:
        return dict(group=group_label, n_study=n1, strong_study=x1, n_ext=n2, strong_ext=x2,
                    share_study=np.nan, share_ext=np.nan, diff_pp=np.nan,
                    ci_low_pp=np.nan, ci_high_pp=np.nan, p_value=np.nan)
    count = np.array([x2, x1]); nobs = np.array([n2, n1])
    _, p = proportions_ztest(count, nobs)
    lo, hi = confint_proportions_2indep(x2, n2, x1, n1, method="newcombe")
    return dict(group=group_label, n_study=n1, strong_study=x1, n_ext=n2, strong_ext=x2,
                share_study=pct(x1, n1), share_ext=pct(x2, n2),
                diff_pp=round(100 * (x2 / n2 - x1 / n1), 1),
                ci_low_pp=round(100 * lo, 1), ci_high_pp=round(100 * hi, 1),
                p_value=round(float(p), 3))


def main():
    s = pd.read_parquet(RESULTS / "sample_two_coast.parquet")
    allus = pd.read_csv(DATA / "spc_annual_counts.csv").set_index("yr")["all_us_tornadoes"]

    # ---- Table 1 analogue: era totals and national shares -------------------
    t1 = []
    for era in ERAS:
        yrs = range(1995, 2016) if era == ERAS[0] else range(2016, 2024)
        us = int(allus.loc[list(yrs)].sum())
        for coast in COASTS + ["pooled"]:
            sub = s[sel(s, era, coast)]
            t1.append(dict(era=era, coast=coast, tornadoes=int(len(sub)),
                           storms=int(sub["storm_id"].nunique()), all_us_tornadoes=us,
                           share_of_us_pct=pct(len(sub), us)))
    for coast in COASTS + ["pooled"]:
        sub = s[sel(s, None, coast)]
        us = int(allus.loc[range(1995, 2024)].sum())
        t1.append(dict(era="all_1995_2023", coast=coast, tornadoes=int(len(sub)),
                       storms=int(sub["storm_id"].nunique()), all_us_tornadoes=us,
                       share_of_us_pct=pct(len(sub), us)))
    pd.DataFrame(t1).to_csv(RESULTS / "table1_era_totals.csv", index=False)

    # ---- Table 3 analogue: intensity ---------------------------------------
    t3 = []
    for era in ERAS + ["all_1995_2023"]:
        for coast in COASTS + ["pooled"]:
            sub = s[sel(s, era, coast)]
            rated = sub[sub["rating"].notna()]
            row = dict(era=era, coast=coast, n=int(len(sub)), n_rated=int(len(rated)),
                       n_unknown=int(len(sub) - len(rated)))
            for r in range(6):
                row[f"rating_{r}"] = int((rated["rating"] == r).sum())
                row[f"rating_{r}_pct"] = pct((rated["rating"] == r).sum(), len(rated))
            weak = int((rated["rating"] <= 1).sum()); strong = int((rated["rating"] >= 2).sum())
            row.update(weak=weak, weak_pct=pct(weak, len(rated)),
                       strong=strong, strong_pct=pct(strong, len(rated)),
                       inj=int(sub["inj"].sum()), fat=int(sub["fat"].sum()))
            t3.append(row)
    pd.DataFrame(t3).to_csv(RESULTS / "table3_intensity.csv", index=False)

    tp = [two_prop(s, "pooled"),
          two_prop(s[s["coast"] == "gulf"], "gulf"),
          two_prop(s[s["coast"] == "atlantic"], "atlantic")]
    pd.DataFrame(tp).to_csv(RESULTS / "table3_two_proportion.csv", index=False)

    # ---- Size and DPI --------------------------------------------------------
    sz = []
    for era in ERAS + ["all_1995_2023"]:
        for coast in COASTS + ["pooled"]:
            sub = s[sel(s, era, coast)]
            row = dict(era=era, coast=coast, n=int(len(sub)))
            for col, lab in [("len_km", "len_km"), ("wid_m", "wid_m"), ("dpi", "dpi")]:
                v = sub[col].dropna()
                row[f"{lab}_median"] = round(float(v.median()), 2)
                row[f"{lab}_q1"] = round(float(v.quantile(0.25)), 2)
                row[f"{lab}_q3"] = round(float(v.quantile(0.75)), 2)
                row[f"{lab}_max"] = round(float(v.max()), 2)
            sz.append(row)
    pd.DataFrame(sz).to_csv(RESULTS / "table3_size_dpi.csv", index=False)

    # ---- Table 4 analogue: geometry -----------------------------------------
    t4 = []
    for era in ERAS + ["all_1995_2023"]:
        for coast in COASTS + ["pooled"]:
            sub = s[sel(s, era, coast)]
            n = len(sub)
            row = dict(era=era, coast=coast, n=int(n),
                       median_range_km=round(float(sub["distance_km"].median()), 1))
            for q in ["NE", "SE", "SW", "NW"]:
                row[f"quad_{q}_pct"] = pct((sub["quadrant"] == q).sum(), n)
            for q in ["NoC", "EoC", "SoC", "WoC"]:
                row[f"off45_{q}_pct"] = pct((sub["quadrant_offset45"] == q).sum(), n)
            row["east_half_pct"] = pct((sub["half_ew"] == "E").sum(), n)
            row["north_half_pct"] = pct((sub["half_ns"] == "N").sum(), n)
            for bn in ["0-100", "100-200", "200-300", ">300"]:
                row[f"coastbin_{bn}_pct"] = pct((sub["coast_bin"] == bn).sum(), n)
            for lb in ["<30", "30-32", "32-34", ">34"]:
                row[f"latband_{lb}_pct"] = pct((sub["lat_band"] == lb).sum(), n)
            t4.append(row)
    pd.DataFrame(t4).to_csv(RESULTS / "table4_geometry.csv", index=False)

    # ---- Annual counts --------------------------------------------------------
    by = (s.groupby(["yr", "coast"]).size().unstack(fill_value=0)
          .reindex(range(1995, 2024), fill_value=0))
    by["pooled"] = by.sum(axis=1)
    by["all_us_tornadoes"] = allus.reindex(range(1995, 2024)).values
    by["tc_share_of_us_pct"] = (100 * by["pooled"] / by["all_us_tornadoes"]).round(1)
    by.rename_axis("year").reset_index().to_csv(RESULTS / "by_year.csv", index=False)

    # ---- Per-storm table -------------------------------------------------------
    bs = (s.groupby(["storm_id", "tc_name_clean", "yr", "coast", "era"])
          .agg(tornadoes=("tornado_id", "size"), strong=("strong", "sum"),
               max_rating=("rating", "max"), inj=("inj", "sum"), fat=("fat", "sum"))
          .reset_index().sort_values(["yr", "tornadoes"], ascending=[True, False]))
    bs.to_csv(RESULTS / "by_storm.csv", index=False)

    peaks = (bs.sort_values("tornadoes", ascending=False)
             .groupby(["era", "coast"]).head(5))
    peaks.to_csv(RESULTS / "era_peaks.csv", index=False)

    # ---- Table 2 analogue: case storms, counts from ORIGINAL outputs ---------
    # Values transcribed from the submitted manuscript (Tables 2 and 6) and the
    # original project's results/marsh_summary.json; NOT recomputed here.
    cases = pd.DataFrame([
        dict(storm="Ida", year=2021, coast_stratum="gulf",
             primary_count_basis="TCTOR", primary_tornadoes=36,
             case_window_paths=36, total_marsh_crossed_ha=79.7,
             chosen_cluster_ha=64.4, outcome="positive case (analysed)"),
        dict(storm="Ian", year=2022, coast_stratum="gulf",
             primary_count_basis="TCTOR", primary_tornadoes=16,
             case_window_paths=16, total_marsh_crossed_ha=0.25,
             chosen_cluster_ha=np.nan, outcome="documented exclusion (insufficient marsh)"),
        dict(storm="Helene", year=2024, coast_stratum="outside climatology (2024 case only)",
             primary_count_basis="SPC 800-km case-window rule (MD2011 subset 16)",
             primary_tornadoes=31, case_window_paths=29,
             total_marsh_crossed_ha=6.0, chosen_cluster_ha=6.0,
             outcome="satellite proof-of-concept case (2024, outside verified climatology)"),
        dict(storm="Milton", year=2024, coast_stratum="outside climatology (2024 case only)",
             primary_count_basis="SPC 800-km case-window rule (MD2011 subset 42)",
             primary_tornadoes=45, case_window_paths=45,
             total_marsh_crossed_ha=86.4, chosen_cluster_ha=32.2,
             outcome="satellite proof-of-concept case (2024, outside verified climatology)"),
    ])
    cases.to_csv(RESULTS / "table2_cases.csv", index=False)

    print("Table 1:"); print(pd.DataFrame(t1).to_string(index=False))
    print("\nTwo-proportion tests:"); print(pd.DataFrame(tp).to_string(index=False))


if __name__ == "__main__":
    main()
