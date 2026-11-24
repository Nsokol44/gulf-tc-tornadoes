"""02_build_sample.py

Build the verified-years (TCTOR 1995-2023) two-coast sample.

Domain (author's design, 2026-11-23):
- Gulf (paper Section 2.2, unchanged): HURDAT2 landfall (L) fix with longitude
  in [-98.5, -81.0] and latitude <= 31.5 N, OR a classified fix (status in
  TD/TS/SS/SD/ST/HU) inside the near-coast Gulf box lat [24, 31.5],
  lon [-98.5, -81.0].
- Atlantic (mirror image): L fix with longitude in [-81.0, -66.0] and
  latitude <= 41.5 N, OR a classified fix inside the near-coast Atlantic box
  lat [24, 41.5], lon [-81.0, -66.0].
- Coast assignment (author decision, 2026-11-24; the latitude-restricted
  rule is now primary and the original first-landfall-anywhere rule is the
  reported sensitivity):
  * Single-qualifier storms take their only coast.
  * Dual-qualifier storms (qualifying under both coast definitions) take
    the coast of their earliest qualifying landfall fix at latitude
    >= 24.0 N (qualifying = in the Gulf or Atlantic landfall sets defined
    above). A same-timestamp tie is assigned to the Gulf (a fix at exactly
    81.0 W satisfies both landfall rules).
  * A dual-qualifier storm with NO qualifying landfall at >= 24.0 N falls
    back to the previous earliest-qualifying-landfall assignment (box
    fallback if it has no landfall fixes at all); such storms are logged
    explicitly in the build log (key
    "coast_assignment_fallback_storms_1995plus").
  * Box-only storms (no landfall fixes) take the coast of their earliest
    qualifying box fix, as before.
  The old first-landfall-anywhere assignment is retained per storm as
  "coast_first_landfall_anywhere"; the tornadoes whose stratum would
  change under that old rule are written to
  results/coast_assignment_sensitivity.csv (the sensitivity table).
- Sample edit (as in the paper): records with zero recorded width are dropped
  (count logged). Geometry (quadrants, halves, coast distance, DPI) follows
  the original pipeline step 05 exactly, using TCTOR's own centre-relative
  distance/bearing/DPI.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
ORIG_DATA = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes/data"

TROPICAL = {"TD", "TS", "SS", "SD", "ST", "HU"}
GULF_LON, ATL_LON = (-98.5, -81.0), (-81.0, -66.0)
GULF_LAT_MAX, ATL_LAT_MAX = 31.5, 41.5
BOX_LAT_MIN = 24.0


def qualify_storms(hur: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sid, g in hur.groupby("storm_id"):
        g = g.sort_values("datetime")
        name = g["storm_name"].iloc[0]
        year = int(g["datetime"].dt.year.iloc[0])
        L = g[g["record_id"] == "L"]
        gulf_L = L[(L["lon"] >= GULF_LON[0]) & (L["lon"] <= GULF_LON[1]) & (L["lat"] <= GULF_LAT_MAX)]
        atl_L = L[(L["lon"] >= ATL_LON[0]) & (L["lon"] <= ATL_LON[1]) & (L["lat"] <= ATL_LAT_MAX)]
        trop = g[g["status"].isin(TROPICAL)]
        gulf_box = trop[(trop["lat"] >= BOX_LAT_MIN) & (trop["lat"] <= GULF_LAT_MAX)
                        & (trop["lon"] >= GULF_LON[0]) & (trop["lon"] <= GULF_LON[1])]
        atl_box = trop[(trop["lat"] >= BOX_LAT_MIN) & (trop["lat"] <= ATL_LAT_MAX)
                       & (trop["lon"] >= ATL_LON[0]) & (trop["lon"] <= ATL_LON[1])]
        qual_gulf = len(gulf_L) > 0 or len(gulf_box) > 0
        qual_atl = len(atl_L) > 0 or len(atl_box) > 0
        if not (qual_gulf or qual_atl):
            continue
        # Previous rule (now the sensitivity): earliest qualifying landfall
        # anywhere; box fixes only if no L.
        coast_old, basis_old, first_lf_old = None, None, None
        cand = []
        if len(gulf_L):
            cand.append((gulf_L["datetime"].iloc[0], "gulf"))
        if len(atl_L):
            cand.append((atl_L["datetime"].iloc[0], "atlantic"))
        if cand:
            cand.sort(key=lambda x: x[0])
            first_lf_old = cand[0][0]
            coast_old = cand[0][1]
            # Same-timestamp tie at exactly 81 W: Gulf wins (both rules match).
            if len(cand) == 2 and cand[0][0] == cand[1][0]:
                coast_old = "gulf"
            basis_old = "landfall"
        else:
            bcand = []
            if len(gulf_box):
                bcand.append((gulf_box["datetime"].iloc[0], "gulf"))
            if len(atl_box):
                bcand.append((atl_box["datetime"].iloc[0], "atlantic"))
            bcand.sort(key=lambda x: x[0])
            coast_old, basis_old = bcand[0][1], "box_only"
        # Primary rule (2026-11-24): dual-qualifier storms are assigned by
        # their earliest qualifying landfall at latitude >= 24.0 N; if they
        # have none, fall back to the previous assignment (logged).
        coast, basis, first_lf = coast_old, basis_old, first_lf_old
        fallback_ge24 = False
        if qual_gulf and qual_atl:
            gulf_L24 = gulf_L[gulf_L["lat"] >= BOX_LAT_MIN]
            atl_L24 = atl_L[atl_L["lat"] >= BOX_LAT_MIN]
            cand24 = []
            if len(gulf_L24):
                cand24.append((gulf_L24["datetime"].iloc[0], "gulf"))
            if len(atl_L24):
                cand24.append((atl_L24["datetime"].iloc[0], "atlantic"))
            if cand24:
                cand24.sort(key=lambda x: x[0])
                first_lf = cand24[0][0]
                coast = cand24[0][1]
                # Same-timestamp tie at exactly 81 W: Gulf wins.
                if len(cand24) == 2 and cand24[0][0] == cand24[1][0]:
                    coast = "gulf"
                basis = "landfall_ge24"
            else:
                fallback_ge24 = True
        out.append(dict(
            storm_id=sid, storm_name=name, year=year,
            qual_gulf=bool(qual_gulf), qual_atlantic=bool(qual_atl),
            dual_qualifier=bool(qual_gulf and qual_atl),
            coast=coast, coast_basis=basis,
            first_qualifying_landfall=(first_lf.isoformat() if first_lf is not None else None),
            coast_first_landfall_anywhere=coast_old,
            coast_basis_first_landfall_anywhere=basis_old,
            first_qualifying_landfall_anywhere=(first_lf_old.isoformat() if first_lf_old is not None else None),
            coast_assignment_fallback_ge24=bool(fallback_ge24),
        ))
    return pd.DataFrame(out)


def add_geometry(sample: pd.DataFrame) -> pd.DataFrame:
    b = sample["bearing_deg"] % 360.0
    sample["quadrant"] = np.select(
        [(b >= 0) & (b < 90), (b >= 90) & (b < 180), (b >= 180) & (b < 270), (b >= 270)],
        ["NE", "SE", "SW", "NW"], default=None)
    sample["quadrant_offset45"] = np.select(
        [((b >= 315) | (b < 45)), (b >= 45) & (b < 135), (b >= 135) & (b < 225), (b >= 225) & (b < 315)],
        ["NoC", "EoC", "SoC", "WoC"], default=None)
    sample["half_ew"] = np.where((b >= 0) & (b < 180), "E", "W")
    sample["half_ns"] = np.where(((b >= 270) | (b < 90)), "N", "S")
    sample["lat_band"] = pd.cut(sample["slat"], bins=[-np.inf, 30, 32, 34, np.inf],
                                labels=["<30", "30-32", "32-34", ">34"]).astype(str)
    sample["scale"] = np.where(sample["yr"] <= 2006, "F", "EF")
    sample["era"] = np.where(sample["yr"] <= 2015, "study_1995_2015", "extension_2016_2023")
    sample["strong"] = sample["rating"] >= 2
    return sample


def add_coast_distance(sample: pd.DataFrame) -> pd.DataFrame:
    coast = gpd.read_file(ORIG_DATA / "ne_10m_coastline.zip").to_crs(5070)
    pts = gpd.GeoDataFrame(
        sample, geometry=[Point(xy) for xy in zip(sample["slon"], sample["slat"])], crs=4326
    ).to_crs(5070)
    joined = gpd.sjoin_nearest(pts, coast[["geometry"]], distance_col="coast_m")
    joined = joined[~joined.index.duplicated(keep="first")]
    sample["coast_km"] = joined["coast_m"].reindex(sample.index) / 1000.0
    sample["coast_bin"] = pd.cut(sample["coast_km"], bins=[-0.1, 100, 200, 300, np.inf],
                                 labels=["0-100", "100-200", "200-300", ">300"]).astype(str)
    return sample


def main():
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    tc = pd.read_parquet(DATA / "tctor.parquet")
    log = {}

    qual = qualify_storms(hur)
    qual.to_csv(RESULTS / "qualifying_storms_two_coast.csv", index=False)
    dual = qual[(qual["dual_qualifier"]) & (qual["year"] >= 1995)]
    log["dual_qualifier_storms_1995plus"] = dual[["storm_id", "storm_name", "year", "coast", "coast_basis"]].to_dict("records")
    log["box_only_storms_1995plus"] = qual[(qual["coast_basis"] == "box_only") & (qual["year"] >= 1995)][["storm_id", "storm_name", "year", "coast"]].to_dict("records")
    # Dual-qualifier storms with no qualifying landfall at >= 24 N: these
    # fell back to the previous first-landfall-anywhere assignment.
    log["coast_assignment_fallback_storms_1995plus"] = qual[
        (qual["coast_assignment_fallback_ge24"]) & (qual["year"] >= 1995)][
        ["storm_id", "storm_name", "year", "coast", "coast_basis"]].to_dict("records")
    log["qualifying_storms_1995_2023"] = qual[qual["year"].between(1995, 2023)].groupby("coast").size().to_dict()

    # Map TCTOR storm name + year to HURDAT2 storm_id (as original step 05).
    # TCTOR names carry a two-digit year suffix, e.g. "IDA-21".
    tc["tc_name_clean"] = tc["tc_name"].str.replace(r"-\d{2}$", "", regex=True)
    hmap = {}
    for sid, g in hur.groupby("storm_id"):
        hmap[(str(g["storm_name"].iloc[0]).strip().upper(), int(g["datetime"].dt.year.iloc[0]))] = sid
    tc["storm_id"] = [hmap.get((n, int(y))) for n, y in zip(tc["tc_name_clean"], tc["yr"])]
    log["tctor_rows_total"] = int(len(tc))
    log["tctor_rows_unmatched_to_hurdat2"] = int(tc["storm_id"].isna().sum())
    unmatched_names = sorted(tc.loc[tc["storm_id"].isna(), "tc_name_clean"].unique().tolist())
    log["unmatched_tc_names"] = unmatched_names

    sample = tc.merge(qual[["storm_id", "coast", "coast_basis", "qual_gulf", "qual_atlantic",
                            "dual_qualifier", "coast_first_landfall_anywhere"]], on="storm_id", how="inner")
    log["sample_before_width_edit"] = int(len(sample))
    log["sample_before_width_edit_by_coast"] = sample["coast"].value_counts().to_dict()
    zero_w = sample["wid_m"] <= 0
    log["zero_width_dropped"] = int(zero_w.sum())
    log["zero_width_dropped_by_coast"] = sample.loc[zero_w, "coast"].value_counts().to_dict()
    sample = sample[~zero_w].copy()

    sample = add_geometry(sample)
    sample = add_coast_distance(sample)
    sample = sample.sort_values(["yr", "storm_id", "slat", "slon"]).reset_index(drop=True)
    sample["tornado_id"] = np.arange(1, len(sample) + 1)

    # Sensitivity table (reverse direction): tornadoes whose stratum would
    # change if the OLD first-landfall-anywhere rule were used instead of
    # the primary >= 24 N rule for dual-qualifier storms.
    flipped = sample[sample["coast"] != sample["coast_first_landfall_anywhere"]]
    sens = (flipped.groupby(["tc_name_clean", "yr"]).size()
            .reset_index(name="tornadoes_flipped")
            .rename(columns={"yr": "yr"})
            .sort_values("tc_name_clean").reset_index(drop=True))
    sens.to_csv(RESULTS / "coast_assignment_sensitivity.csv", index=False)
    log["coast_assignment_sensitivity_old_rule"] = sens.to_dict("records")
    log["coast_assignment_sensitivity_old_rule_total"] = int(len(flipped))

    cols = ["tornado_id", "yr", "era", "st", "rating", "scale", "strong", "inj", "fat",
            "slat", "slon", "elat", "elon", "len_km", "wid_m", "dpi",
            "tc_name", "tc_name_clean", "storm_id", "coast", "coast_basis", "qual_gulf", "qual_atlantic",
            "dual_qualifier", "tc_lat", "tc_lon", "distance_km", "bearing_deg",
            "quadrant", "quadrant_offset45", "half_ns", "half_ew", "lat_band",
            "coast_km", "coast_bin"]
    sample = sample[cols]
    sample.to_parquet(RESULTS / "sample_two_coast.parquet", index=False)
    sample.to_csv(RESULTS / "sample_two_coast.csv", index=False)
    log["sample_final"] = int(len(sample))
    log["sample_by_coast"] = sample["coast"].value_counts().to_dict()
    log["sample_by_era"] = sample["era"].value_counts().to_dict()
    log["sample_by_coast_era"] = sample.groupby(["coast", "era"]).size().to_dict()
    log["sample_by_coast_era"] = {f"{k[0]}|{k[1]}": int(v) for k, v in log["sample_by_coast_era"].items()}
    log["storms_by_coast_era"] = {
        f"{k[0]}|{k[1]}": int(v) for k, v in
        sample.groupby(["coast", "era"])["storm_id"].nunique().to_dict().items()}
    with open(RESULTS / "sample_build_log.json", "w") as f:
        json.dump(log, f, indent=2, default=str)
    print(json.dumps(log, indent=2, default=str))


if __name__ == "__main__":
    main()
