"""Build the primary attributed TC tornado table.

Primary sample design (see manuscript/methods_recovery.md and
results/climatology_provenance.md):
  1. For the years TCTOR covers (1995 to 2023), the sample is the SPC
     TCTOR attributed list itself, restricted to tornadoes whose TC
     is a qualifying Gulf Coast landfalling or Gulf affecting TC
     (the candidate set of code/03_associate_tc_tornadoes.py), with
     the Moore et al. (2017) sample edit applied: records with a
     recorded path width of 0 m are dropped and the drop count is
     printed. Distance and bearing for these rows are the values
     computed by TCTOR (its own linear interpolation of HURDAT
     centres), not recomputed values. Recomputed values are carried
     as extra columns so the analysis can verify them.
  2. For 2024 and 2025, which the current TCTOR release does not
     cover, attribution uses the broad operational rule computed by
     code/03_associate_tc_tornadoes.py (800 km from the interpolated
     centre, tornado time inside the storm's full HURDAT2 track
     window, qualifying Gulf TCs of any classified stage). On the
     overlap years 1995 to 2023 this rule recovers 93.9 percent of
     Gulf TCTOR tornadoes, against 33.7 percent for the narrower
     Moore and Dixon (2011) rule (400 km, landfall day minus 1 to
     plus 1, hurricanes only), which is therefore retained only as
     a sensitivity (results/tc_tornadoes_md2011.parquet). The 2024
     to 2025 rows are flagged in attribution_source.

Added geometry and derived variables, following Moore et al. (2017):
  quadrant (true north diagonal), quadrant_offset45 (cardinal scheme
  offset by 45 degrees), half_ns and half_ew, distance from the
  coastline in the paper bins (0-100, 100-200, 200-300, over 300 km,
  from the Natural Earth 1:10m coastline, distances computed in the
  CONUS Albers projection EPSG:5070), latitude band of the tornado
  start point (below 30, 30-32, 32-34, above 34 degrees N), and DPI
  (TCTOR value for TCTOR rows; area times (rating + 1) for the 2024
  to 2025 rows, with path area from SPC length and width).

Output: results/tc_tornadoes.parquet

Rerunnable: python3 code/05_build_primary_sample.py
"""
import pathlib

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
EARTH_R_KM = 6371.0088

COMMON = ["yr", "datetime_utc", "st", "rating", "inj", "fat",
          "slat", "slon", "elat", "elon", "len_km", "wid_m",
          "storm_id", "storm_name", "tc_lat_interp", "tc_lon_interp",
          "distance_km", "bearing_deg", "attribution_source", "dpi"]


def quadrant_labels(bearing, offset, labels):
    shifted = (np.asarray(bearing, dtype=float) + offset) % 360
    idx = np.minimum((shifted // 90).astype(int), 3)
    return pd.Series(idx).map(dict(enumerate(labels))).astype(str)


def coastline_distance_km(lats, lons):
    coast = gpd.read_file(DATA / "ne_10m_coastline.zip")
    coast = coast.cx[-101:-66, 15:50].to_crs(5070)
    union = coast.geometry.union_all()
    pts = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy(lons, lats), crs=4326).to_crs(5070)
    return pts.geometry.distance(union).to_numpy() / 1000.0


def add_geometry(df):
    df = df.copy()
    df["quadrant"] = quadrant_labels(
        df["bearing_deg"], 0, ["NE", "SE", "SW", "NW"]).to_numpy()
    df["quadrant_offset45"] = quadrant_labels(
        df["bearing_deg"], 45, ["NoC", "EoC", "SoC", "WoC"]).to_numpy()
    b = df["bearing_deg"].to_numpy()
    df["half_ns"] = np.where((b >= 270) | (b < 90), "NH", "SH")
    df["half_ew"] = np.where((b >= 0) & (b < 180), "EH", "WH")
    df["era"] = np.where(df["yr"] <= 2015,
                         "study_1995_2015", "extension_2016_2025")
    df["lat_band"] = pd.cut(
        df["slat"], bins=[0, 30, 32, 34, 90],
        labels=["<30", "30-32", "32-34", ">34"], right=False).astype(str)
    df["coast_km"] = coastline_distance_km(df["slat"], df["slon"])
    df["coast_bin"] = pd.cut(
        df["coast_km"], bins=[0, 100, 200, 300, np.inf],
        labels=["0-100", "100-200", "200-300", ">300"],
        right=False).astype(str)
    df["scale"] = np.where(
        df["datetime_utc"] < pd.Timestamp("2007-02-01", tz="UTC"),
        "F", "EF")
    return df


def recompute_geometry(tct, hur):
    """Interpolate HURDAT centres for TCTOR rows, for verification."""
    tracks = {sid: g.sort_values("datetime_utc")
              for sid, g in hur.groupby("storm_id")}
    lats = np.full(len(tct), np.nan)
    lons = np.full(len(tct), np.nan)
    t_ns_all = tct["datetime_utc"].astype("int64").to_numpy()
    for idx, sid in enumerate(tct["storm_id"]):
        grp = tracks.get(sid)
        if grp is None:
            continue
        t_ns = grp["datetime_utc"].astype("int64").to_numpy()
        if t_ns[0] <= t_ns_all[idx] <= t_ns[-1]:
            lats[idx] = np.interp(t_ns_all[idx], t_ns,
                                  grp["lat"].to_numpy())
            lons[idx] = np.interp(t_ns_all[idx], t_ns,
                                  grp["lon"].to_numpy())
    return lats, lons


if __name__ == "__main__":
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    tct = pd.read_parquet(DATA / "tctor_tidy.parquet")
    qual = pd.read_csv(DATA / "qualifying_gulf_tcs.csv")
    op8 = pd.read_parquet(RESULTS / "tc_tornadoes_op800.parquet")

    name_map = (hur.drop_duplicates(["name", "year"])
                .set_index(["name", "year"])["storm_id"].to_dict())
    tct["storm_id"] = [name_map.get((n, y)) for n, y in
                       zip(tct["tc_name"], tct["yr"])]
    unmatched = tct[tct["storm_id"].isna()]
    print(f"TCTOR rows unmatched to a HURDAT2 storm id: {len(unmatched)}")
    if len(unmatched):
        print(unmatched["tc_name_raw"].value_counts().to_string())
    tct = tct[tct["storm_id"].notna()].copy()
    tct["storm_name"] = tct["tc_name"]
    n_before = len(tct)
    tct = tct[tct["storm_id"].isin(set(qual["storm_id"]))].copy()
    print(f"TCTOR rows {n_before} total, {len(tct)} for qualifying "
          f"Gulf TCs")
    zero = int((tct["wid_m"] == 0).sum())
    zero_study = int(((tct["wid_m"] == 0) & (tct["yr"] <= 2015)).sum())
    tct = tct[tct["wid_m"] != 0].copy()
    print(f"Zero width TCTOR rows dropped (Moore et al. 2017 edit): "
          f"{zero} (1995-2015: {zero_study})")
    rlats, rlons = recompute_geometry(tct, hur)
    tct["tc_lat_recomputed"] = rlats
    tct["tc_lon_recomputed"] = rlons
    tct["distance_km"] = tct["distance_tctor_km"]
    tct["bearing_deg"] = tct["bearing_tctor"]
    tct["dpi"] = tct["dpi_tctor"]
    tct["attribution_source"] = "TCTOR"
    tctor_part = tct[COMMON + ["tc_lat_recomputed", "tc_lon_recomputed",
                               "distance_tctor_km", "bearing_tctor"]]

    op8_part = op8[op8["yr"] >= 2024].copy()
    op8_part["dpi"] = (op8_part["len_km"] * (op8_part["wid_m"] / 1000.0)
                       * (op8_part["rating"] + 1))
    op8_part.loc[op8_part["rating"].isna(), "dpi"] = np.nan
    op8_part["attribution_source"] = "OP800_operational"
    op8_part["tc_lat_recomputed"] = op8_part["tc_lat_interp"]
    op8_part["tc_lon_recomputed"] = op8_part["tc_lon_interp"]
    op8_part["distance_tctor_km"] = np.nan
    op8_part["bearing_tctor"] = np.nan
    op8_part = op8_part[COMMON + ["tc_lat_recomputed", "tc_lon_recomputed",
                                  "distance_tctor_km", "bearing_tctor"]]
    print(f"OP800 rows for 2024-2025 in primary sample: {len(op8_part)} "
          f"(zero width among them: "
          f"{int((op8_part['wid_m'] == 0).sum())}, kept as recorded, "
          f"as for operational rows throughout)")

    primary = pd.concat([tctor_part, op8_part], ignore_index=True)
    primary = add_geometry(primary)
    primary = primary.sort_values("datetime_utc").reset_index(drop=True)
    primary.to_parquet(RESULTS / "tc_tornadoes.parquet", index=False)
    print(f"Primary sample: {len(primary)} tornadoes, "
          f"{primary['storm_id'].nunique()} storms; "
          f"1995-2015 {int((primary['era'] == 'study_1995_2015').sum())}, "
          f"2016-2025 {int((primary['era'] == 'extension_2016_2025').sum())}")
