"""Moore and Dixon (2011) operational association rule.

Recovered rule (Moore 2013 dissertation summary of Moore and Dixon
2011, as documented in manuscript/methods_recovery.md; the 2011
article itself is paywalled, so this rule is secondhand in the
corpus and is flagged as such wherever its results are reported):
  tornadoes associated with Gulf Coast landfalling hurricanes only,
  within 400 km of the TC centre, from the day before landfall
  through the day after landfall.

Operationalisation used here:
  1. A Gulf Coast landfalling hurricane is an Atlantic TC with at
     least one HURDAT2 fix carrying the landfall identifier "L"
     while at hurricane status (HU), at longitude 98.5 W to 81.0 W
     and latitude 24.0 to 31.5 N. The latitude floor restricts the
     anchor landfall to the US Gulf Coast (Florida Keys and north):
     without it, a storm such as Ida (2021), whose first landfall
     inside the wider Gulf box was in Cuba on 27 August, would have
     its window anchored two days before its Louisiana landfall of
     29 August and would score zero tornadoes. Cuban and Yucatan
     landfalls therefore do not anchor the window, which matches
     the US Gulf Coast scope of Moore and Dixon (2011).
  2. The landfall time is the first such fix. The time window runs
     from the UTC calendar date one day before that landfall date
     through the UTC calendar date one day after it, inclusive.
     Calendar dates are used because the recovered rule is stated in
     days ("the day before landfall through the day after
     landfall"), not in hours.
  3. The TC centre at tornado time is linearly interpolated between
     the surrounding HURDAT2 fixes (all fixes, including the 3
     hourly landfall fixes), and the great circle distance from the
     centre to the tornado start point must be 400 km or less.
  4. One tornado, one TC: if two hurricanes qualify, the nearer
     centre wins.

The rule is computed for all years 1995 to 2025 so that it can be
compared with TCTOR on the overlap years. In the primary sample
(code/05_build_primary_sample.py) it supplies only the years TCTOR
does not cover, 2024 and 2025.

Output: results/tc_tornadoes_md2011.parquet

Rerunnable: python3 code/04_md2011_rule.py
"""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
EARTH_R_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(a))


def initial_bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlmb = np.radians(lon2 - lon1)
    x = np.sin(dlmb) * np.cos(p2)
    y = np.cos(p1) * np.sin(p2) - np.sin(p1) * np.cos(p2) * np.cos(dlmb)
    return (np.degrees(np.arctan2(x, y)) + 360) % 360


def quadrant(bearing, offset):
    shifted = (bearing + offset) % 360
    if offset == 0:
        labels = ["NE", "SE", "SW", "NW"]
    else:
        labels = ["NoC", "EoC", "SoC", "WoC"]
    idx = np.minimum((shifted // 90).astype(int), 3)
    return pd.Series(idx).map(dict(enumerate(labels))).astype(str)


def gulf_hurricane_landfalls(hur):
    lf = hur[(hur["record_id"].str.contains("L", na=False))
             & (hur["status"] == "HU")
             & (hur["lon"] >= -98.5) & (hur["lon"] <= -81.0)
             & (hur["lat"] >= 24.0) & (hur["lat"] <= 31.5)].copy()
    first = (lf.sort_values("datetime_utc")
             .groupby("storm_id").first().reset_index())
    return first[["storm_id", "name", "datetime_utc"]].rename(
        columns={"datetime_utc": "landfall_utc", "name": "storm_name"})


if __name__ == "__main__":
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    spc = pd.read_parquet(DATA / "spc_tornadoes_tidy.parquet")
    cand = spc[spc["yr"] >= 1995].copy()
    cand["t_ns"] = cand["datetime_utc"].astype("int64")
    cand["date_utc"] = cand["datetime_utc"].dt.normalize()
    landfalls = gulf_hurricane_landfalls(hur)
    landfalls.to_csv(DATA / "gulf_hurricane_landfalls.csv", index=False)
    print(f"Gulf hurricane landfall storms 1851 to 2025: {len(landfalls)}; "
          f"1995 to 2025: "
          f"{int((landfalls['landfall_utc'].dt.year >= 1995).sum())}")
    hits = []
    tracks = {sid: g.sort_values("datetime_utc")
              for sid, g in hur.groupby("storm_id")}
    for row in landfalls.itertuples():
        grp = tracks[row.storm_id]
        t_ns = grp["datetime_utc"].astype("int64").to_numpy()
        win_lo = (row.landfall_utc.normalize()
                  - pd.Timedelta(1, "D"))
        win_hi = (row.landfall_utc.normalize()
                  + pd.Timedelta(2, "D"))
        lo = cand[(cand["datetime_utc"] >= win_lo)
                  & (cand["datetime_utc"] < win_hi)
                  & (cand["t_ns"] >= t_ns[0]) & (cand["t_ns"] <= t_ns[-1])]
        if lo.empty:
            continue
        clat = np.interp(lo["t_ns"].to_numpy(), t_ns,
                         grp["lat"].to_numpy())
        clon = np.interp(lo["t_ns"].to_numpy(), t_ns,
                         grp["lon"].to_numpy())
        dist = haversine_km(clat, clon, lo["slat"].to_numpy(),
                            lo["slon"].to_numpy())
        ok = dist <= 400
        if not ok.any():
            continue
        sub = lo.loc[ok].copy()
        sub["storm_id"] = row.storm_id
        sub["storm_name"] = row.storm_name
        sub["landfall_utc"] = row.landfall_utc
        sub["tc_lat_interp"] = clat[ok]
        sub["tc_lon_interp"] = clon[ok]
        sub["distance_km"] = dist[ok]
        hits.append(sub)
    out = pd.concat(hits, ignore_index=True)
    out = out.sort_values("distance_km").drop_duplicates(
        subset=["yr", "om", "datetime_utc", "slat", "slon"], keep="first")
    out["bearing_deg"] = initial_bearing_deg(
        out["tc_lat_interp"], out["tc_lon_interp"],
        out["slat"], out["slon"])
    out["quadrant"] = quadrant(out["bearing_deg"], 0).to_numpy()
    out["quadrant_offset45"] = quadrant(out["bearing_deg"], 45).to_numpy()
    out["era"] = np.where(out["yr"] <= 2015,
                          "study_1995_2015", "extension_2016_2025")
    out = out.drop(columns=["t_ns", "date_utc"])
    out = out.sort_values("datetime_utc").reset_index(drop=True)
    out.to_parquet(RESULTS / "tc_tornadoes_md2011.parquet", index=False)
    print(f"MD2011 rule: {len(out)} tornadoes, "
          f"{out['storm_id'].nunique()} storms; "
          f"1995-2015 {int((out['era'] == 'study_1995_2015').sum())}, "
          f"2016-2025 {int((out['era'] == 'extension_2016_2025').sum())}, "
          f"2024-2025 {int((out['yr'] >= 2024).sum())}")
