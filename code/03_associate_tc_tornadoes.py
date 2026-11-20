"""Associate SPC tornadoes with tropical cyclones (TC tornadoes).

Recovered rule (Moore, Sokol and Blume 2017, Atmosphere 8:160, and
the SPC TCTOR database README by Edwards that the paper draws on):
  Moore et al. (2017) did not apply an automated distance rule. They
  used the SPC tropical cyclone tornado (TCTOR) database, in which
  each candidate tornado from the SPC one tornado database was
  examined individually against surface and upper air maps, archived
  satellite imagery and/or NEXRAD Level II data, and was retained if
  it lay within the circulation envelope of a classified or remnant
  tropical cyclone. TCTOR states explicitly that events were logged
  "without regard to fixed radii from TC center, inland extent,
  temporal cutoffs before or after landfall, or other such arbitrary
  and readily automatable thresholds". The TCTOR sample in Moore
  et al. (2017) covers 1995 to 2015, held 1296 tornadoes, and 1285
  after 11 tornadoes with a recorded path width of 0 m were removed.
  Five of the 1285 had a range from TC centre greater than 800 km
  (paper Figure 3 note). Centre positions at tornado time came from
  linear interpolation between 6 hourly HURDAT fixes, distances are
  great circle distances from the tornado start point, and bearings
  and quadrants are defined relative to true north (paper Figure 1).

Operational rule implemented here (closest reproducible rule, with
deviations logged in results/climatology_provenance.md):
  1. Tornado time must fall between the first and last HURDAT2 fix
     of the candidate TC (no remnant extension, because remnant
     centres after the end of HURDAT2 are subjective analyses that
     cannot be recovered from the downloaded files).
  2. The TC centre at tornado time is linearly interpolated in time
     between the surrounding HURDAT2 fixes. All fixes in the file are
     used, so the extra fixes at 3 hourly spacing that HURDAT2
     carries around landfall enter the interpolation.
  3. Great circle (haversine) distance from the interpolated centre
     to the tornado start point must be 800 km or less. This radius
     is an operational stand-in for the TCTOR circulation envelope:
     only 5 of the 1285 TCTOR tornadoes in Moore et al. (2017)
     exceeded 800 km from centre.
  4. If more than one TC qualifies for one tornado, the tornado is
     assigned to the TC with the smallest centre distance.
  5. Gulf restriction (below): only TCs that made a Gulf Coast
     landfall or otherwise affected the Gulf Coast are candidates.
  A sensitivity run repeats steps 1 to 5 with a 500 km radius and is
  saved separately.

Gulf Coast domain, operational definition:
  A TC qualifies if either
   (a) it has a HURDAT2 fix carrying the landfall identifier "L" at
       longitude 98.5 W to 81.0 W and latitude 31.5 N or less (the
       Gulf Coast from northeastern Mexico and Texas around the Gulf
       to the Florida Big Bend and the west coast of Florida,
       including the Yucatan Peninsula and the Florida Keys west of
       81 W), or
   (b) it has at least one fix inside the near coast Gulf box
       (latitude 24.0 to 31.5 N, longitude 98.5 to 81.0 W) while
       classified as a tropical or subtropical system (status TD,
       TS, SS, SD, ST or HU), which captures Gulf affecting storms
       that brushed or paralleled the US Gulf Coast, crossed the
       Florida Peninsula from the Gulf, or entered northern Mexico
       close to Texas without a coded Gulf landfall fix.
  TCs whose only US landfalls are on the Atlantic coast do not
  qualify. This Gulf restriction follows Moore and Dixon (2011),
  whose climatology covered Gulf Coast landfalling hurricanes, and
  the tasking for this manuscript. It is narrower than the all US
  sample of Moore et al. (2017), and that difference is a stated
  deviation in the provenance file.

Scope: tornadoes with SPC recorded years 1995 through the last year
of the SPC archive (2025) are tested. Earlier years are not tested
because the comparison eras are the Moore et al. (2017) study
period 1995 to 2015 and the extension period that follows it.

Outputs:
  results/tc_tornadoes_op800.parquet  broad operational rule (800 km)
  results/tc_tornadoes_r500.parquet   sensitivity rule (500 km)
  data/qualifying_gulf_tcs.csv        candidate TC list with the
                                      qualifying criterion met
These operational files are sensitivities and agreement checks. The
primary attributed table, results/tc_tornadoes.parquet, is built by
code/05_build_primary_sample.py from the TCTOR list (its covered
years) plus the Moore and Dixon (2011) rule for 2024 to 2025.

Rerunnable: python3 code/03_associate_tc_tornadoes.py
"""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

RNG = np.random.default_rng(20261106)  # fixed seed, project standard
EARTH_R_KM = 6371.0088
FIRST_YEAR = 1995
TROPICAL_STATUSES = {"TD", "TS", "SS", "SD", "ST", "HU"}


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


def quadrant_true_north(bearing):
    bins = [0, 90, 180, 270, 360.0001]
    labels = ["NE", "SE", "SW", "NW"]
    return pd.cut(bearing, bins=bins, labels=labels, right=False).astype(str)


def quadrant_offset45(bearing):
    # North of centre, east of centre, south of centre, west of centre
    # scheme of Moore et al. (2017) Figure 1b, also relative to north.
    shifted = (bearing + 45) % 360
    bins = [0, 90, 180, 270, 360.0001]
    labels = ["NoC", "EoC", "SoC", "WoC"]
    return pd.cut(shifted, bins=bins, labels=labels, right=False).astype(str)


def annulus(distance_km):
    bins = [0, 100, 200, 300, 400, 500, 600, 700, 800.0001]
    labels = ["0-100", "100-200", "200-300", "300-400",
              "400-500", "500-600", "600-700", "700-800"]
    return pd.cut(distance_km, bins=bins, labels=labels, right=False).astype(str)


def qualifying_gulf_tcs(hur):
    rows = []
    for storm_id, grp in hur.groupby("storm_id"):
        grp = grp.sort_values("datetime_utc")
        landfall = grp[(grp["record_id"].str.contains("L", na=False))
                       & (grp["lon"] >= -98.5) & (grp["lon"] <= -81.0)
                       & (grp["lat"] <= 31.5)]
        nearbox = grp[(grp["lat"] >= 24.0) & (grp["lat"] <= 31.5)
                      & (grp["lon"] >= -98.5) & (grp["lon"] <= -81.0)
                      & (grp["status"].isin(TROPICAL_STATUSES))]
        crit = []
        if len(landfall):
            crit.append("gulf_landfall_L")
        if len(nearbox):
            crit.append("gulf_nearcoast_box")
        if not crit:
            continue
        rows.append({
            "storm_id": storm_id,
            "name": grp["name"].iloc[0],
            "year": int(storm_id[-4:]),
            "criterion": "+".join(crit),
            "first_fix_utc": grp["datetime_utc"].min(),
            "last_fix_utc": grp["datetime_utc"].max(),
            "max_wind_kt": grp["max_wind_kt"].max(),
            "n_fixes": len(grp),
        })
    return pd.DataFrame(rows)


def associate(hur, spc, qual_ids, radius_km):
    cand = spc[(spc["yr"] >= FIRST_YEAR)].copy()
    cand["t_ns"] = cand["datetime_utc"].astype("int64")
    tracks = {}
    for storm_id, grp in hur[hur["storm_id"].isin(qual_ids)].groupby("storm_id"):
        grp = grp.sort_values("datetime_utc")
        tracks[storm_id] = (
            grp["datetime_utc"].astype("int64").to_numpy(),
            grp["lat"].to_numpy(), grp["lon"].to_numpy(),
            grp["name"].iloc[0])
    hits = []
    for storm_id, (t_ns, lats, lons, name) in tracks.items():
        lo = cand[(cand["t_ns"] >= t_ns[0]) & (cand["t_ns"] <= t_ns[-1])]
        if lo.empty:
            continue
        clat = np.interp(lo["t_ns"].to_numpy(), t_ns, lats)
        clon = np.interp(lo["t_ns"].to_numpy(), t_ns, lons)
        dist = haversine_km(clat, clon, lo["slat"].to_numpy(),
                            lo["slon"].to_numpy())
        ok = dist <= radius_km
        if not ok.any():
            continue
        sub = lo.loc[ok].copy()
        sub["storm_id"] = storm_id
        sub["storm_name"] = name
        sub["tc_lat_interp"] = clat[ok]
        sub["tc_lon_interp"] = clon[ok]
        sub["distance_km"] = dist[ok]
        hits.append(sub)
    if not hits:
        return pd.DataFrame()
    allhits = pd.concat(hits, ignore_index=True)
    # One tornado, one TC: keep the smallest centre distance.
    allhits = allhits.sort_values("distance_km").drop_duplicates(
        subset=["yr", "om", "datetime_utc", "slat", "slon"], keep="first")
    allhits["bearing_deg"] = initial_bearing_deg(
        allhits["tc_lat_interp"], allhits["tc_lon_interp"],
        allhits["slat"], allhits["slon"])
    allhits["quadrant"] = quadrant_true_north(allhits["bearing_deg"])
    allhits["quadrant_offset45"] = quadrant_offset45(allhits["bearing_deg"])
    allhits["annulus_km"] = annulus(allhits["distance_km"])
    allhits["era"] = np.where(allhits["yr"] <= 2015,
                              "study_1995_2015", "extension_2016_2025")
    allhits = allhits.drop(columns=["t_ns"])
    return allhits.sort_values("datetime_utc").reset_index(drop=True)


if __name__ == "__main__":
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    spc = pd.read_parquet(DATA / "spc_tornadoes_tidy.parquet")
    qual = qualifying_gulf_tcs(hur)
    qual.to_csv(DATA / "qualifying_gulf_tcs.csv", index=False)
    print(f"Qualifying Gulf TCs 1851 to 2025: {len(qual)}")
    print(f"Qualifying Gulf TCs 1995 to 2025: "
          f"{int(((qual['year'] >= 1995)).sum())}")
    for radius, fname in ((800, "tc_tornadoes_op800.parquet"),
                          (500, "tc_tornadoes_r500.parquet")):
        out = associate(hur, spc, set(qual["storm_id"]), radius)
        out.to_parquet(RESULTS / fname, index=False)
        print(f"radius {radius} km: TC tornadoes {len(out)} "
              f"storms {out['storm_id'].nunique()} "
              f"1995-2015 {int((out['era'] == 'study_1995_2015').sum())} "
              f"2016-2025 {int((out['era'] == 'extension_2016_2025').sum())}")
