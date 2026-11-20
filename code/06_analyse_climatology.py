"""Compute the climatology tables, summary JSON and provenance log.

Primary sample: results/tc_tornadoes.parquet (TCTOR attributed list
for qualifying Gulf TCs, 1995 to 2023, with the zero width edit of
Moore et al. 2017, plus the broad operational rule, 800 km over the
full track window, for 2024 to 2025, the years the current TCTOR
release does not cover; the Moore and Dixon 2011 rule is retained
as a sensitivity). Sensitivities and agreement checks use
results/tc_tornadoes_op800.parquet, tc_tornadoes_r500.parquet and
tc_tornadoes_md2011.parquet.

Outputs:
  results/climatology_tables.md
  results/climatology_summary.json
  results/climatology_provenance.md

Eras: study 1995 to 2015 (the TCTOR period of Moore, Sokol and
Blume 2017) and extension 2016 to 2025. No resampling is performed;
the project fixed seed, numpy default_rng(20261106), is instantiated
as the standing convention for any future resampling.

Rerunnable: python3 code/06_analyse_climatology.py
"""
import hashlib
import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RNG = np.random.default_rng(20261106)
STUDY, EXT = (1995, 2015), (2016, 2025)
ERAS = ("study_1995_2015", "extension_2016_2025")
NAMED = [("IDA", 2021), ("IAN", 2022), ("HELENE", 2024), ("MILTON", 2024)]


def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def era_of(year):
    if STUDY[0] <= year <= STUDY[1]:
        return "study_1995_2015"
    if EXT[0] <= year <= EXT[1]:
        return "extension_2016_2025"
    return "outside"


def weak_strong(df):
    k = df[df["rating"].notna()]
    weak = int((k["rating"] <= 1).sum())
    strong = int(((k["rating"] >= 2) & (k["rating"] <= 3)).sum())
    denom = max(len(k), 1)
    return {"n": int(len(df)), "n_known": int(len(k)),
            "n_unknown": int(len(df) - len(k)),
            "weak_0_1": weak, "strong_2_3": strong,
            "rating_4plus": int((k["rating"] >= 4).sum()),
            "weak_share_pct": round(100 * weak / denom, 2),
            "strong_share_pct": round(100 * strong / denom, 2)}


def rating_stats(df):
    out = weak_strong(df)
    k = df[df["rating"].notna()]
    for r in range(6):
        out[f"ef{r}"] = int((k["rating"] == r).sum())
    out["ef2plus_n"] = int((k["rating"] >= 2).sum())
    out["ef3plus_n"] = int((k["rating"] >= 3).sum())
    denom = max(len(k), 1)
    out["ef2plus_share_known"] = round(100 * out["ef2plus_n"] / denom, 2)
    out["ef3plus_share_known"] = round(100 * out["ef3plus_n"] / denom, 2)
    return out


def size_stats(s):
    s = s.dropna()
    return {"n": int(len(s)),
            "median": round(float(s.median()), 3) if len(s) else None,
            "q1": round(float(s.quantile(0.25)), 3) if len(s) else None,
            "q3": round(float(s.quantile(0.75)), 3) if len(s) else None,
            "mean": round(float(s.mean()), 3) if len(s) else None,
            "max": round(float(s.max()), 3) if len(s) else None}


def share_table(df, col, order):
    vc = df[col].value_counts()
    tot = max(len(df), 1)
    return {k: {"n": int(vc.get(k, 0)),
                "share_pct": round(100 * int(vc.get(k, 0)) / tot, 2)}
            for k in order}


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |",
             "|" + "|".join([" --- "] * len(headers)) + "|"]
    for r in rows:
        lines.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(lines)


def keyset(df):
    return set(zip(df["datetime_utc"].astype(str),
                   np.round(df["slat"], 2), np.round(df["slon"], 2)))


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))


if __name__ == "__main__":
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    spc = pd.read_parquet(DATA / "spc_tornadoes_tidy.parquet")
    tct = pd.read_parquet(DATA / "tctor_tidy.parquet")
    qual = pd.read_csv(DATA / "qualifying_gulf_tcs.csv")
    tc = pd.read_parquet(RESULTS / "tc_tornadoes.parquet")
    op8 = pd.read_parquet(RESULTS / "tc_tornadoes_op800.parquet")
    op5 = pd.read_parquet(RESULTS / "tc_tornadoes_r500.parquet")
    md = pd.read_parquet(RESULTS / "tc_tornadoes_md2011.parquet")
    spc["era"] = spc["yr"].map(era_of)
    allus = spc[spc["era"] != "outside"].copy()

    S = {}
    S["eras"] = {"study_1995_2015": list(STUDY),
                 "extension_2016_2025": list(EXT)}
    S["archives"] = {
        "hurdat2_last_year": int(hur["year"].max()),
        "spc_last_year": int(spc["yr"].max()),
        "tctor_last_year": int(tct["yr"].max()),
        "tctor_rows_total": int(len(tct)),
        "tctor_rows_1995_2015_current_release": int((tct["yr"] <= 2015).sum()),
        "spc_total_tornadoes_all_years": int(len(spc)),
        "primary_sample_definition":
            "TCTOR (1995-2023, Gulf qualifying TCs, zero width dropped) "
            "plus broad operational rule, 800 km full track window "
            "(2024-2025)"}

    era_block = {}
    for era in ERAS:
        sub = tc[tc["era"] == era]
        a = allus[allus["era"] == era]
        top = (sub.groupby(["storm_id", "storm_name"]).size()
               .sort_values(ascending=False))
        era_block[era] = {
            "tc_tornadoes": int(len(sub)),
            "storms_with_tc_tornadoes": int(sub["storm_id"].nunique()),
            "all_us_tornadoes": int(len(a)),
            "tc_share_of_all_us_pct": round(100 * len(sub) / max(len(a), 1), 2),
            "fatalities": int(sub["fat"].sum()),
            "injuries": int(sub["inj"].sum()),
            "all_us_fatalities": int(a["fat"].sum()),
            "all_us_injuries": int(a["inj"].sum()),
            "top_storm": f"{top.index[0][1]} {top.index[0][0][-4:]}",
            "top_storm_tornadoes": int(top.iloc[0]),
            "top_storm_share_pct": round(100 * int(top.iloc[0]) / len(sub), 2),
            "by_attribution_source": {
                k: int(v) for k, v in
                sub["attribution_source"].value_counts().items()}}
    S["by_era"] = era_block
    S["totals_1995_2025"] = {
        "tc_tornadoes_primary": int(len(tc)),
        "storms_primary": int(tc["storm_id"].nunique())}

    by_year = {}
    for yr in range(STUDY[0], EXT[1] + 1):
        sub = tc[tc["yr"] == yr]
        a = allus[allus["yr"] == yr]
        by_year[str(yr)] = {
            "tc_tornadoes": int(len(sub)),
            "storms_with_tc_tornadoes": int(sub["storm_id"].nunique()),
            "attribution_source": (
                sub["attribution_source"].iloc[0] if len(sub) else None),
            "all_us_tornadoes": int(len(a)),
            "tc_fatalities": int(sub["fat"].sum()),
            "tc_injuries": int(sub["inj"].sum())}
    S["by_year"] = by_year

    named = {}
    for name, yr in NAMED:
        h = hur[(hur["name"] == name) & (hur["year"] == yr)]
        sid = h["storm_id"].iloc[0] if len(h) else None
        def cnt(frame):
            return int((frame["storm_id"] == sid).sum()) if sid else 0
        sub = tc[tc["storm_id"] == sid]
        named[f"{name.title()} {yr}"] = {
            "hurdat2_id": sid,
            "max_wind_kt": int(h["max_wind_kt"].max()) if len(h) else None,
            "tc_tornadoes_primary": cnt(tc),
            "primary_source": (
                sub["attribution_source"].iloc[0] if len(sub) else None),
            "tc_tornadoes_op800": cnt(op8),
            "tc_tornadoes_r500": cnt(op5),
            "tc_tornadoes_md2011": cnt(md),
            "fatalities_primary": int(sub["fat"].sum()),
            "injuries_primary": int(sub["inj"].sum()),
            "strong_2_3_primary": int(
                ((sub["rating"] >= 2) & (sub["rating"] <= 3)).sum())}
    S["named_storms"] = named

    S["weak_strong_tc_by_era"] = {e: weak_strong(tc[tc["era"] == e])
                                  for e in ERAS}
    S["weak_strong_tc_pooled"] = weak_strong(tc)
    S["weak_strong_all_us_by_era"] = {
        e: weak_strong(allus[allus["era"] == e]) for e in ERAS}
    S["ratings_tc_by_era"] = {e: rating_stats(tc[tc["era"] == e])
                              for e in ERAS}
    S["ratings_all_us_by_era"] = {e: rating_stats(allus[allus["era"] == e])
                                  for e in ERAS}

    size_block = {}
    for era in ERAS:
        sub = tc[tc["era"] == era]
        size_block[era] = {
            "path_length_km": size_stats(sub["len_km"]),
            "path_width_m": size_stats(sub["wid_m"]),
            "dpi": size_stats(sub["dpi"])}
    S["size_tc_by_era"] = size_block

    quad_order = ["NE", "SE", "SW", "NW"]
    S["quadrants_true_north_pooled"] = share_table(tc, "quadrant", quad_order)
    S["quadrants_true_north_by_era"] = {
        e: share_table(tc[tc["era"] == e], "quadrant", quad_order)
        for e in ERAS}
    S["quadrants_offset45_pooled"] = share_table(
        tc, "quadrant_offset45", ["NoC", "EoC", "SoC", "WoC"])
    S["halves_pooled"] = {
        "ns": share_table(tc, "half_ns", ["NH", "SH"]),
        "ew": share_table(tc, "half_ew", ["EH", "WH"])}
    S["coast_bins_pooled"] = share_table(
        tc, "coast_bin", ["0-100", "100-200", "200-300", ">300"])
    S["coast_bins_by_era"] = {
        e: share_table(tc[tc["era"] == e], "coast_bin",
                       ["0-100", "100-200", "200-300", ">300"])
        for e in ERAS}
    S["lat_bands_pooled"] = share_table(
        tc, "lat_band", ["<30", "30-32", "32-34", ">34"])
    ann_order = ["0-100", "100-200", "200-300", "300-400",
                 "400-500", "500-600", "600-700", "700-800"]
    tc_ann = tc.copy()
    tc_ann["annulus_km"] = pd.cut(
        tc_ann["distance_km"],
        bins=[0, 100, 200, 300, 400, 500, 600, 700, np.inf],
        labels=ann_order, right=False).astype(str)
    S["annulus_from_centre_pooled_extra_not_in_2017_paper"] = share_table(
        tc_ann, "annulus_km", ann_order)
    S["distance_km_pooled"] = size_stats(tc["distance_km"])
    S["coast_km_pooled"] = size_stats(tc["coast_km"])

    # Single storm leverage, including the Rita south of centre check
    soc = tc[tc["quadrant_offset45"] == "SoC"]
    rita_soc = int(((soc["storm_name"] == "RITA")).sum())
    S["single_storm_leverage"] = {
        "soc_tornadoes_pooled": int(len(soc)),
        "rita_soc_tornadoes": rita_soc,
        "rita_share_of_soc_pct": round(100 * rita_soc / max(len(soc), 1), 2),
        "rita_total_primary": int((tc["storm_name"] == "RITA").sum()),
        "ivan_total_primary": int((tc["storm_name"] == "IVAN").sum()),
        "note": "Moore et al. (2017), using the TCTOR version of their "
                "day, reported 100 south of centre tornadoes of which "
                "Rita (2005) produced 39, and 98 Rita tornadoes in "
                "total. The current TCTOR release gives Rita 97 "
                "tornadoes in total. Ivan is 118 in both the 2016 "
                "abstract and the current TCTOR release."}

    # Sensitivity totals
    S["sensitivity_rules"] = {}
    for label, frame in (("op800_broad", op8), ("op500", op5),
                         ("md2011_400km_landfall_window", md)):
        S["sensitivity_rules"][label] = {
            e: {"tc_tornadoes": int((frame["era"] == e).sum()),
                "storms": int(frame.loc[frame["era"] == e,
                                        "storm_id"].nunique())}
            for e in ERAS}

    # Agreement: TCTOR (Gulf, all rows incl. zero width, 1995-2023)
    # versus each operational rule on the same years.
    name_map = (hur.drop_duplicates(["name", "year"])
                .set_index(["name", "year"])["storm_id"].to_dict())
    tg = tct.copy()
    tg["storm_id"] = [name_map.get((n, y)) for n, y in
                      zip(tg["tc_name"], tg["yr"])]
    tg = tg[tg["storm_id"].isin(set(qual["storm_id"]))]
    tkeys = keyset(tg)
    agree = {"tctor_gulf_rows_1995_2023": int(len(tg))}
    for label, frame in (("op800", op8), ("op500", op5), ("md2011", md)):
        f = frame[frame["yr"] <= 2023]
        fkeys = keyset(f)
        inter = len(tkeys & fkeys)
        agree[label] = {
            "operational_rows_1995_2023": int(len(f)),
            "matched": inter,
            "tctor_only": int(len(tkeys) - inter),
            "operational_only": int(len(fkeys) - inter),
            "jaccard_pct": round(
                100 * inter / max(len(tkeys | fkeys), 1), 2),
            "share_of_tctor_matched_pct": round(
                100 * inter / max(len(tkeys), 1), 2)}
    S["agreement_tctor_vs_operational"] = agree

    # Verification of our interpolation against TCTOR worksheet values
    tp = tc[tc["attribution_source"] == "TCTOR"].copy()
    recomp = haversine_km(tp["tc_lat_recomputed"], tp["tc_lon_recomputed"],
                          tp["slat"], tp["slon"])
    diff = np.abs(recomp - tp["distance_tctor_km"])
    S["interpolation_check_vs_tctor"] = {
        "n_compared": int(pd.notna(diff).sum()),
        "n_tctor_rows_without_hurdat_window": int(pd.isna(diff).sum()),
        "median_abs_distance_diff_km": round(float(np.nanmedian(diff)), 3),
        "p90_abs_distance_diff_km": round(
            float(np.nanpercentile(diff, 90)), 3)}

    with open(RESULTS / "climatology_summary.json", "w") as fh:
        json.dump(S, fh, indent=2)

    # ------------------------- markdown tables -------------------------
    L = []
    L.append("# TC tornado climatology tables")
    L.append("")
    L.append("Primary sample: the SPC TCTOR attributed list for "
             "qualifying Gulf Coast TCs, 1995 to 2023 (with the zero "
             "width edit of Moore, Sokol and Blume 2017), plus the "
             "broad operational rule (800 km, full track window) for "
             "2024 to 2025, the years the current TCTOR release does "
             "not cover. Study era is 1995 to 2015. Extension era is "
             "2016 to 2025. Operational sensitivity rules are "
             "reported in Section 9. Full provenance, the recovered "
             "rules and every deviation are in "
             "climatology_provenance.md.")
    L.append("")
    L.append("## 1. Era totals (primary sample)")
    rows = []
    for era, lab in zip(ERAS, ("Study 1995-2015", "Extension 2016-2025")):
        b = era_block[era]
        rows.append([lab, b["tc_tornadoes"], b["storms_with_tc_tornadoes"],
                     b["all_us_tornadoes"], b["tc_share_of_all_us_pct"],
                     b["fatalities"], b["injuries"]])
    L.append(md_table(["Era", "TC tornadoes", "Storms with TC tornadoes",
                       "All US tornadoes", "TC share of all US (%)",
                       "TC tornado deaths", "TC tornado injuries"], rows))
    L.append("")
    L.append(f"Pooled 1995 to 2025: {len(tc)} TC tornadoes from "
             f"{tc['storm_id'].nunique()} storms. Attribution sources "
             f"by era: " + "; ".join(
                 f"{lab}: " + ", ".join(
                     f"{k} {v}" for k, v in
                     era_block[e]["by_attribution_source"].items())
                 for e, lab in zip(ERAS, ("study", "extension"))) + ".")
    L.append("")
    L.append("## 2. Counts by year (primary sample)")
    rows = [[y, by_year[str(y)]["tc_tornadoes"],
             by_year[str(y)]["storms_with_tc_tornadoes"],
             by_year[str(y)]["attribution_source"] or "none",
             by_year[str(y)]["all_us_tornadoes"],
             by_year[str(y)]["tc_fatalities"],
             by_year[str(y)]["tc_injuries"]]
            for y in range(STUDY[0], EXT[1] + 1)]
    L.append(md_table(["Year", "TC tornadoes", "Storms with TC tornadoes",
                       "Attribution source", "All US tornadoes",
                       "TC tornado deaths", "TC tornado injuries"], rows))
    L.append("")
    L.append("## 3. Named recent storms")
    rows = [[k, v["hurdat2_id"], v["max_wind_kt"],
             v["tc_tornadoes_primary"], v["primary_source"],
             v["tc_tornadoes_op800"], v["tc_tornadoes_md2011"],
             v["strong_2_3_primary"], v["fatalities_primary"],
             v["injuries_primary"]] for k, v in named.items()]
    L.append(md_table(["Storm", "HURDAT2 id", "Peak wind (kt)",
                       "TC tornadoes (primary)", "Primary source",
                       "TC tornadoes (800 km rule)",
                       "TC tornadoes (MD2011 rule)", "Strong F/EF2-3",
                       "Deaths", "Injuries"], rows))
    L.append("")
    L.append("## 4. Intensity: weak versus strong (the 2017 headline split)")
    L.append("")
    L.append("Moore et al. (2017) summarise intensity as weak F/EF 0-1 "
             "versus strong F/EF 2-3, with a full sample split of 94 "
             "percent weak and 6 percent strong in their 1285 tornado "
             "sample. Shares here are percentages of tornadoes with a "
             "known rating. No tornado in the primary sample is rated "
             "4 or 5 in either era.")
    rows = []
    for lab, st in (("TC primary, study 1995-2015",
                     S["weak_strong_tc_by_era"]["study_1995_2015"]),
                    ("TC primary, extension 2016-2025",
                     S["weak_strong_tc_by_era"]["extension_2016_2025"]),
                    ("TC primary, pooled", S["weak_strong_tc_pooled"]),
                    ("All US, study 1995-2015",
                     S["weak_strong_all_us_by_era"]["study_1995_2015"]),
                    ("All US, extension 2016-2025",
                     S["weak_strong_all_us_by_era"]["extension_2016_2025"])):
        rows.append([lab, st["n"], st["n_unknown"], st["weak_0_1"],
                     st["weak_share_pct"], st["strong_2_3"],
                     st["strong_share_pct"]])
    L.append(md_table(["Group", "N", "Unknown rating", "Weak 0-1",
                       "Weak share (%)", "Strong 2-3",
                       "Strong share (%)"], rows))
    L.append("")
    L.append("Full rating distribution and EF2+ / EF3+ shares "
             "(percentages of known ratings):")
    rows = []
    for lab, st in (("TC primary, study", S["ratings_tc_by_era"]["study_1995_2015"]),
                    ("TC primary, extension", S["ratings_tc_by_era"]["extension_2016_2025"]),
                    ("All US, study", S["ratings_all_us_by_era"]["study_1995_2015"]),
                    ("All US, extension", S["ratings_all_us_by_era"]["extension_2016_2025"])):
        rows.append([lab, st["ef0"], st["ef1"], st["ef2"], st["ef3"],
                     st["ef4"], st["ef5"], st["ef2plus_share_known"],
                     st["ef3plus_share_known"]])
    L.append(md_table(["Group", "F/EF0", "F/EF1", "F/EF2", "F/EF3",
                       "F/EF4", "F/EF5", "EF2+ share (%)",
                       "EF3+ share (%)"], rows))
    L.append("")
    n_unk_tctor = int(((tc["attribution_source"] == "TCTOR")
                       & tc["rating"].isna()).sum())
    n_unk_op = int(((tc["attribution_source"] == "OP800_operational")
                    & tc["rating"].isna()).sum())
    L.append("The F scale applies before 1 February 2007 and the EF "
             "scale from that date. Following Moore et al. (2017), "
             "ratings are pooled across the transition as a single "
             "F/EF variable, which is an assumption of that paper, "
             "not a tested result: the scales were designed to be "
             "consistent, but the damage indicator set and survey "
             "practice changed in 2007, and the study era straddles "
             f"the break. Unknown ratings total "
             f"{S['weak_strong_tc_by_era']['extension_2016_2025']['n_unknown']} "
             f"in the extension era and none in the study era: "
             f"{n_unk_tctor} TCTOR rows for 2019 to 2022 carry a "
             f"blank rating in the workbook, and {n_unk_op} of the "
             f"2024 to 2025 SPC records carry the SPC unknown rating "
             f"code -9. They are excluded from the shares. "
             "For the all US comparison series, note that SPC "
             "unknown ratings become common in recent years (1,525 "
             "of 13,184 extension era records, against 21 of 26,080 "
             "in the study era), so the all US extension era shares "
             "rest on the 88 percent of records with a known rating "
             "and could shift if the unrated records, mostly "
             "tornadoes with no damage survey, were rated.")
    L.append("")
    L.append("## 5. Size (path length, path width, DPI)")
    rows = []
    for era, lab in zip(ERAS, ("Study 1995-2015", "Extension 2016-2025")):
        s = size_block[era]
        rows.append([lab, s["path_length_km"]["median"],
                     s["path_length_km"]["q1"], s["path_length_km"]["q3"],
                     s["path_length_km"]["mean"],
                     s["path_width_m"]["median"], s["path_width_m"]["q1"],
                     s["path_width_m"]["q3"], s["path_width_m"]["mean"],
                     s["dpi"]["median"]])
    L.append(md_table(["Era", "Length median (km)", "Length Q1",
                       "Length Q3", "Length mean (km)",
                       "Width median (m)", "Width Q1", "Width Q3",
                       "Width mean (m)", "DPI median"], rows))
    L.append("")
    L.append("Caveats: path width is the maximum observed width, "
             "recorded as such since 1994, so both eras use maximum "
             "width. Width and length are still survey based damage "
             "measures: survey practice, aerial survey use and the "
             "population of damage indicators changed across 1995 to "
             "2025, and widths where damage indicators are sparse are "
             "prone to understatement, so era differences mix real "
             "change with reporting change. DPI is path area times "
             "(rating + 1); for TCTOR rows the TCTOR value is used, "
             "for 2024 to 2025 rows it is computed from SPC length, "
             "width and rating.")
    L.append("")
    L.append("## 6. Geometry within the TC environment (true north)")
    L.append("")
    L.append("All sectors are relative to true north, the convention "
             "of Moore et al. (2017). Diagonal quadrants: NE bearing "
             "0 to 90 degrees, SE 90 to 180, SW 180 to 270, NW 270 "
             "to 360. Cardinal quadrants are the same scheme offset "
             "by 45 degrees. No motion relative sectors are used in "
             "the 2017 paper; none are used here.")
    rows = []
    for era, lab in (("study_1995_2015", "Study"), ("extension_2016_2025",
                                                    "Extension")):
        q = S["quadrants_true_north_by_era"][era]
        rows.append([lab] + [f"{q[k]['n']} ({q[k]['share_pct']}%)"
                             for k in quad_order])
    q = S["quadrants_true_north_pooled"]
    rows.append(["Pooled"] + [f"{q[k]['n']} ({q[k]['share_pct']}%)"
                              for k in quad_order])
    L.append(md_table(["Era", "NE", "SE", "SW", "NW"], rows))
    L.append("")
    q = S["quadrants_offset45_pooled"]
    L.append("Cardinal quadrants, pooled: " + ", ".join(
        f"{k} {q[k]['n']} ({q[k]['share_pct']}%)"
        for k in ("NoC", "EoC", "SoC", "WoC")) + ".")
    h = S["halves_pooled"]
    L.append(f"Halves, pooled: north half {h['ns']['NH']['n']} "
             f"({h['ns']['NH']['share_pct']}%), south half "
             f"{h['ns']['SH']['n']} ({h['ns']['SH']['share_pct']}%), "
             f"east half {h['ew']['EH']['n']} "
             f"({h['ew']['EH']['share_pct']}%), west half "
             f"{h['ew']['WH']['n']} ({h['ew']['WH']['share_pct']}%).")
    lev = S["single_storm_leverage"]
    L.append(f"Single storm leverage check: south of centre holds "
             f"{lev['soc_tornadoes_pooled']} pooled tornadoes, of "
             f"which Rita (2005) produced {lev['rita_soc_tornadoes']} "
             f"({lev['rita_share_of_soc_pct']} percent). Moore et al. "
             f"(2017) flagged the same pattern in their sample (Rita "
             f"39 of 100 south of centre tornadoes). Era totals are "
             f"also concentrated: the largest single storm contributes "
             f"{era_block['study_1995_2015']['top_storm_share_pct']} "
             f"percent of the study era total "
             f"({era_block['study_1995_2015']['top_storm']}) and "
             f"{era_block['extension_2016_2025']['top_storm_share_pct']} "
             f"percent of the extension era total "
             f"({era_block['extension_2016_2025']['top_storm']}). Era "
             f"comparisons should be read with that concentration in "
             f"mind.")
    L.append("")
    L.append("## 7. Distance from the coastline (the 2017 distance bins)")
    L.append("")
    L.append("Distance is measured from the tornado start point to "
             "the nearest coastline (Natural Earth 1:10m) and binned "
             "as in Moore et al. (2017). The paper does not bin "
             "tornadoes by distance from the TC centre; centre range "
             "annuli are therefore not a headline output here. Pooled "
             "centre distances for reference: median "
             f"{S['distance_km_pooled']['median']} km, interquartile "
             f"range {S['distance_km_pooled']['q1']} to "
             f"{S['distance_km_pooled']['q3']} km.")
    rows = []
    for era, lab in (("study_1995_2015", "Study"),
                     ("extension_2016_2025", "Extension")):
        c = S["coast_bins_by_era"][era]
        rows.append([lab] + [f"{c[k]['n']} ({c[k]['share_pct']}%)"
                             for k in ("0-100", "100-200", "200-300",
                                       ">300")])
    c = S["coast_bins_pooled"]
    rows.append(["Pooled"] + [f"{c[k]['n']} ({c[k]['share_pct']}%)"
                              for k in ("0-100", "100-200", "200-300",
                                        ">300")])
    L.append(md_table(["Era", "0-100 km", "100-200 km", "200-300 km",
                       "Over 300 km"], rows))
    L.append("")
    lb = S["lat_bands_pooled"]
    L.append("Latitude bands of the tornado start point, pooled: "
             + ", ".join(f"{k} N: {lb[k]['n']} ({lb[k]['share_pct']}%)"
                         for k in ("<30", "30-32", "32-34", ">34")) + ".")
    L.append("")
    L.append("## 8. Casualties")
    rows = [[lab, era_block[e]["fatalities"], era_block[e]["injuries"],
             era_block[e]["all_us_fatalities"],
             era_block[e]["all_us_injuries"]]
            for e, lab in zip(ERAS, ("Study 1995-2015",
                                     "Extension 2016-2025"))]
    L.append(md_table(["Era", "TC tornado deaths", "TC tornado injuries",
                       "All US tornado deaths",
                       "All US tornado injuries"], rows))
    L.append("")
    L.append("Casualties are the SPC inj and fat counts on each "
             "tornado record (TCTOR carries the same fields). They "
             "count harm attributed to the tornado itself, not to "
             "other TC hazards.")
    L.append("")
    L.append("## 9. Sensitivity rules and agreement with TCTOR")
    L.append("")
    rows = []
    for label, lab in (("op800_broad", "Operational 800 km, whole "
                        "track window"), ("op500", "Operational 500 km, "
                        "whole track window"),
                       ("md2011_400km_landfall_window",
                        "Moore and Dixon 2011: 400 km, landfall day "
                        "minus 1 to plus 1, Gulf hurricane landfalls")):
        b = S["sensitivity_rules"][label]
        rows.append([lab, b["study_1995_2015"]["tc_tornadoes"],
                     b["extension_2016_2025"]["tc_tornadoes"]])
    rows.append(["Primary sample (TCTOR plus 800 km rule for "
                 "2024-2025)",
                 era_block["study_1995_2015"]["tc_tornadoes"],
                 era_block["extension_2016_2025"]["tc_tornadoes"]])
    L.append(md_table(["Rule", "Study era tornadoes",
                       "Extension era tornadoes"], rows))
    L.append("")
    a = S["agreement_tctor_vs_operational"]
    L.append(f"Agreement on the overlap years 1995 to 2023, Gulf "
             f"domain, matching on UTC time and start position: TCTOR "
             f"lists {a['tctor_gulf_rows_1995_2023']} tornadoes "
             f"(before the zero width edit).")
    rows = []
    for label, lab in (("op800", "800 km rule"), ("op500", "500 km rule"),
                       ("md2011", "MD2011 rule")):
        b = a[label]
        rows.append([lab, b["operational_rows_1995_2023"], b["matched"],
                     b["tctor_only"], b["operational_only"],
                     b["share_of_tctor_matched_pct"], b["jaccard_pct"]])
    L.append(md_table(["Operational rule", "Rule rows 1995-2023",
                       "Matched to TCTOR", "TCTOR only", "Rule only",
                       "Share of TCTOR matched (%)",
                       "Jaccard (%)"], rows))
    L.append("")
    ic = S["interpolation_check_vs_tctor"]
    L.append(f"Interpolation check: for the {ic['n_compared']} primary "
             f"sample TCTOR rows whose tornado time falls inside the "
             f"HURDAT2 track window, the distance recomputed by this "
             f"pipeline differs from the TCTOR worksheet distance by "
             f"a median of {ic['median_abs_distance_diff_km']} km "
             f"(90th percentile {ic['p90_abs_distance_diff_km']} km). "
             f"The remaining {ic['n_tctor_rows_without_hurdat_window']} "
             f"rows are remnant or post classification cases whose "
             f"times fall outside the HURDAT2 window for their storm, "
             f"which is why TCTOR carries subjectively analysed "
             f"remnant centres for them.")
    (RESULTS / "climatology_tables.md").write_text("\n".join(L) + "\n")

    # ------------------------- provenance -------------------------
    files = {
        "hurdat": DATA / "hurdat2-1851-2025-092326.txt",
        "spc": DATA / "1950-2025_actual_tornadoes.csv",
        "seg": DATA / "1950-2025_torn.csv",
        "tctor": DATA / "tctor.xls",
        "coast": DATA / "ne_10m_coastline.zip"}
    P = []
    P.append("# Climatology provenance")
    P.append("")
    P.append("Download date: 2026-11-06. Every number in "
             "climatology_tables.md and climatology_summary.json "
             "comes from the files listed here, processed by the "
             "scripts in code/ (01 download, 02 parse, 03 broad "
             "operational association, 04 Moore and Dixon 2011 rule, "
             "05 primary sample, 06 analysis; code/run_all.py runs "
             "all six in order). No figures were made in this task, "
             "by instruction. Fixed seed for any resampling: numpy "
             "default_rng(20261106). No resampling is used.")
    P.append("")
    P.append("## Sources and archive end dates actually obtained")
    P.append("")
    P.append(f"1. NHC HURDAT2 Atlantic best tracks, file "
             f"hurdat2-1851-2025-092326.txt, from "
             f"https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt "
             f"(latest file in the NHC hurdat directory on the "
             f"download date; NHC describes it as the Atlantic "
             f"hurricane database 1851 to 2025, updated 23 September "
             f"2026). Size {files['hurdat'].stat().st_size} bytes, "
             f"SHA-256 {sha256(files['hurdat'])}. Archive end year "
             f"obtained: {int(hur['year'].max())}.")
    P.append(f"2. SPC severe weather database, tornadoes, whole track "
             f"form, file 1950-2025_actual_tornadoes.csv, from "
             f"https://www.spc.noaa.gov/wcm/data/1950-2025_actual_tornadoes.csv "
             f"(server Last-Modified 24 Apr 2026). Size "
             f"{files['spc'].stat().st_size} bytes, SHA-256 "
             f"{sha256(files['spc'])}. Coverage 1950 to "
             f"{int(spc['yr'].max())}, {len(spc)} records. Archive end "
             f"year obtained: {int(spc['yr'].max())}. The whole track "
             f"file is primary because the state segment form (file "
             f"1950-2025_torn.csv, SHA-256 {sha256(files['seg'])}, "
             f"also downloaded) lists a state crossing tornado once "
             f"per state segment and would double count it.")
    P.append(f"3. SPC TCTOR database (Edwards), file tctor.xls, from "
             f"https://www.spc.noaa.gov/publications/edwards/tctor.xls. "
             f"OBTAINABILITY OUTCOME: the attributed TCTOR list is "
             f"publicly downloadable at that URL, and it was "
             f"downloaded for this task. Size "
             f"{files['tctor'].stat().st_size} bytes, SHA-256 "
             f"{sha256(files['tctor'])}. Workbook last saved 19 March "
             f"2024 (file metadata), matching the 2024 README version "
             f"(data through 2023) at "
             f"https://www.spc.noaa.gov/publications/edwards/readme.txt. "
             f"Parsed data rows: {len(tct)} (the workbook footer "
             f"itself states a total of 1783, which the parser "
             f"reproduces exactly), years 1995 to "
             f"{int(tct['yr'].max())}, 114 named TCs. Archive end year "
             f"obtained: {int(tct['yr'].max())}.")
    P.append(f"4. Natural Earth 1:10m coastline, file "
             f"ne_10m_coastline.zip, from "
             f"https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_coastline.zip, "
             f"SHA-256 {sha256(files['coast'])}, used only for "
             f"distance from coastline.")
    P.append("5. Method sources read in full: Moore, Sokol and Blume "
             "(2017) Atmosphere 8:160, doi 10.3390/atmos8090160 (open "
             "access); the SPC TCTOR README (2024 version); and "
             "manuscript/methods_recovery.md, the parallel methods "
             "recovery for this project, which documents the Moore "
             "and Dixon (2011) rule from Moore (2013) dissertation "
             "sources because the 2011 article is paywalled. The "
             "MD2011 rule is therefore secondhand in the corpus and "
             "is flagged as such wherever it is used.")
    P.append("")
    P.append("## Preliminary status")
    P.append("")
    P.append("The SPC CSV carries no preliminary flag column. SPC "
             "labels daily current year reports preliminary, but "
             "this archive ends with the 2025 season and was posted "
             "in April 2026, after that season closed, so 2025 is "
             "treated as an archived season. TCTOR is a living "
             "database whose entries are open to evidence based "
             "revision (its README says so), and HURDAT2 best tracks "
             "are subject to later reanalysis, so recent season "
             "counts can change in future releases of either file.")
    P.append("")
    P.append("## Timezone convention")
    P.append("")
    P.append("SPC tornado times are recorded in Central Standard "
             "Time: the tz column carries code 3 (CST in the SPC "
             "database description) for 73,421 of 73,458 records and "
             "for every record in the 1995 to 2025 analysis window. "
             "The 37 records with other codes fall in 1956 to 1994, "
             "outside the window. Convention applied: SPC times are "
             "fixed CST (UTC-06:00, no daylight saving shift) and are "
             "converted to UTC by adding 6 hours before matching to "
             "HURDAT2 (UTC) and to TCTOR (whose workbook carries both "
             "UTC and CST fields, which agree with this conversion). "
             "If a local office in fact logged an event in daylight "
             "time, that event carries a one hour timing error into "
             "the interpolated centre position; TCTOR notes the same "
             "class of timing imprecision in the parent data.")
    P.append("")
    P.append("## The recovered rules and the design they produced")
    P.append("")
    P.append("Moore et al. (2017) state no numeric association rule. "
             "Their sample is the TCTOR list: manual, case by case "
             "verification of membership in the circulation envelope "
             "of a classified or remnant TC, with no fixed radius, no "
             "time cutoff and no landfall requirement, covering 1995 "
             "to 2015 in the version they used (1296 tornadoes, 1285 "
             "after removing 11 records with path width 0 m). "
             "Geometry in the 2017 paper is relative to true north: "
             "diagonal quadrants, cardinal quadrants offset by 45 "
             "degrees, and north/south plus east/west halves. Its "
             "distance binning is distance from the coastline "
             "(0-100, 100-200, 200-300, over 300 km), never annuli "
             "from the centre. Its headline intensity contrast is "
             "weak F/EF 0-1 versus strong F/EF 2-3 (94 versus 6 "
             "percent in their sample). The text phrase F/EF 1-2 in "
             "their Section 3.2.4 is a misprint for 2-3 (per the "
             "methods recovery, from their Table 11) and is not used.")
    P.append("Moore and Dixon (2011), recovered secondhand: tornado "
             "within 400 km of the TC centre, from the day before "
             "landfall through the day after landfall, Gulf Coast "
             "landfalling hurricanes only.")
    P.append("Design adopted here, in consequence: (a) TCTOR itself "
             "is the historical sample for its covered years, 1995 "
             "to 2023, restricted to qualifying Gulf TCs and with "
             "the 2017 zero width edit. (b) For 2024 to 2025, the "
             "only years TCTOR does not cover, attribution uses the "
             "broad operational rule (800 km, whole HURDAT2 track "
             "window, Gulf qualifying TCs of any classified stage), "
             "the rule that recovers 93.9 percent of Gulf TCTOR "
             "tornadoes on the overlap years. (c) A 500 km variant "
             "of the same rule and the much narrower Moore and "
             "Dixon (2011) rule (400 km, landfall day minus 1 to "
             "plus 1, Gulf hurricane landfalls only; 33.7 percent "
             "of TCTOR on the overlap years) are run over all years "
             "as sensitivities, and their agreement with TCTOR on "
             "the overlap years is reported in the tables and "
             "summary JSON.")
    P.append("")
    P.append("## Validation checkpoints against the published record")
    P.append("")
    P.append(f"Current TCTOR release, 1995 to 2015 rows: "
             f"{int((tct['yr'] <= 2015).sum())}, against 1296 in the "
             f"version used by Moore et al. (2017); the difference of "
             f"2 is consistent with a living, revised database. Zero "
             f"width rows in 1995 to 2015: 11, exactly as the paper "
             f"reports. Ivan (2004) tornadoes in the current "
             f"release: 118, matching the Moore, Dixon and Sokol "
             f"(2016) abstract (some secondary sources give 117; 118 "
             f"is used, per that abstract and this file). Rita (2005) "
             f"tornadoes in the current release: 97 in total and "
             f"{lev['rita_soc_tornadoes']} of them south of centre in "
             f"the Gulf primary sample, against 98 in total and 39 "
             f"of 100 south of centre in the 2017 paper's version. "
             f"Interpolation check against TCTOR worksheet distances: "
             f"median absolute difference "
             f"{ic['median_abs_distance_diff_km']} km over "
             f"{ic['n_compared']} compared rows.")
    P.append("")
    P.append("## Operational definitions")
    P.append("")
    P.append("Qualifying Gulf TC (used for the TCTOR restriction and "
             "the broad operational rule): a HURDAT2 storm with a "
             "landfall identifier L fix at longitude 98.5 W to 81.0 "
             "W and latitude 31.5 N or less, or with at least one fix "
             "inside the near coast Gulf box (latitude 24.0 to 31.5 "
             "N, longitude 98.5 to 81.0 W) while classified as a "
             "tropical or subtropical system. The candidate list is "
             "saved at data/qualifying_gulf_tcs.csv (180 storms for "
             "1995 to 2025).")
    P.append("Moore and Dixon (2011) rule as implemented: first "
             "HURDAT2 fix with identifier L at hurricane status at "
             "a US Gulf Coast position (longitude 98.5 W to 81.0 W, "
             "latitude 24.0 to 31.5 N) defines the landfall. The "
             "latitude floor matters: Ida (2021) first entered the "
             "wider Gulf box with a Cuban landfall on 27 August, and "
             "anchoring on that fix would place the window two days "
             "before its Louisiana landfall and score it zero "
             "tornadoes. The window "
             "is the UTC calendar dates from one day before to one "
             "day after that date; centre interpolated linearly "
             "between surrounding fixes (all fixes, including the 3 "
             "hourly landfall fixes); distance 400 km or less; "
             "nearest TC wins ties.")
    P.append("Broad operational rule as implemented: tornado time "
             "between the first and last HURDAT2 fix of a qualifying "
             "Gulf TC, interpolated centre, distance 800 km or less "
             "(500 km variant saved separately). The 800 km radius "
             "is a stand-in for the TCTOR circulation envelope: "
             "Moore et al. (2017) Figure 3 notes only 5 of their "
             "1285 tornadoes lay beyond 800 km from centre.")
    P.append("Distance from coastline: nearest distance from the "
             "tornado start point to the Natural Earth 1:10m "
             "coastline, computed in EPSG:5070 (CONUS Albers). This "
             "measures distance to any coastline in the clipped "
             "North American window, which for a small number of "
             "border tornadoes may be a Mexican or Cuban coastline "
             "segment rather than a US one.")
    P.append("")
    P.append("## Deviations and known limits")
    P.append("")
    P.append("1. Gulf restriction. Moore et al. (2017) used an all "
             "US TCTOR sample with no geographic filter. The primary "
             "sample here restricts TCTOR to qualifying Gulf TCs, "
             "following the tasking for this manuscript and the Gulf "
             "focus of Moore and Dixon (2011). Study era totals here "
             "are therefore Gulf subsets and do not equal the 1296 "
             "or 1285 of the 2017 paper.")
    P.append("2. Attribution footing across the extension "
             "boundary. Extension era rows for 2016 to 2023 are "
             "TCTOR attributions (manual, case by case verified), "
             "while 2024 to 2025 rows come from the broad "
             "operational rule (800 km, whole track window). The "
             "2024 to 2025 counts are therefore rule based rather "
             "than verified, and the remaining break in the record "
             "is verified versus operational attribution, not a "
             "change of radius: the broad rule is the same rule as "
             "the homogeneous operational series in Section 9 of "
             "the tables, provided for comparisons that need one "
             "rule throughout. The named storm table shows the "
             "narrower Moore and Dixon (2011) rule alongside, so "
             "the size of the rule dependence is visible (for "
             "example Helene 2024: 31 tornadoes under the broad "
             "rule, 16 under MD2011).")
    P.append("3. Remnant tornadoes. TCTOR includes remnant cases "
             "with subjectively analysed centres after HURDAT "
             "classification ends. Those rows are in the primary "
             "sample with TCTOR geometry, but no operational rule "
             "here can reproduce them, which is part of why the "
             "operational rules match only part of TCTOR (Section 9 "
             "of the tables).")
    P.append("4. TCTOR geometry is taken as published in the "
             "workbook (its bearing and distance columns), rather "
             "than recomputed, for TCTOR rows. The recomputation "
             "check above shows the two agree to a median of "
             f"{ic['median_abs_distance_diff_km']} km, so this "
             "choice does not move any binned result materially.")
    P.append("5. Zero width edit applied to TCTOR rows only, as in "
             "2017. The 2024 to 2025 operational rows keep all "
             "records (none had zero width in those years in the "
             "SPC file attributed set: see the analysis log), and "
             "width statistics use recorded widths as they stand.")
    P.append("6. The MD2011 window is implemented in UTC calendar "
             "days, because the recovered rule is stated in days. A "
             "CST calendar day convention would shift the window by "
             "6 hours at each end and could move a small number of "
             "edge cases.")
    P.append("7. F/EF pooling across the 2007 transition follows the "
             "2017 paper's stated assumption. It is not tested here.")
    P.append("8. Reporting change across 1995 to 2025 (radar, "
             "spotting, cameras) inflates recent weak tornado counts "
             "independently of any climate signal. Era comparisons "
             "are descriptive and are not adjusted for it.")
    P.append("9. Individual distances and bearings inherit the 0.1 "
             "degree rounding of HURDAT2 fixes and SPC timing "
             "imprecision (TCTOR notes 64 percent of 1995 to 2008 "
             "record times end in 0 or 5 minutes). Read them as TC "
             "scale tendencies, not precise per tornado values.")
    (RESULTS / "climatology_provenance.md").write_text("\n".join(P) + "\n")
    print(json.dumps(S["by_era"], indent=2))
    print(json.dumps(S["named_storms"], indent=2))
    print(json.dumps(S["agreement_tctor_vs_operational"], indent=2))
