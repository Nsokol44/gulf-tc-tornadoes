"""06_case_screening.py

SCREENING TABLE ONLY (author correction, 2026-11-23): rank verified-era
(2016-2023) storms in the new two-coast sample by crossed herbaceous marsh
area. No new HLS trajectory analysis is built; additional cases are an
author decision after the rebuild report.

Method (paper Section 2.4 / original step1_paths + step2_overlap):
- Candidate storms: sampled storms, 2016-2023, with >= 10 TCTOR tornadoes
  in the new sample (threshold stated here; all such storms are screened).
- Case window: tornadoes from 24 h before to 72 h after the storm's first
  landfall (first HURDAT2 L fix at lat >= 25 N within the assigned coast's
  longitude range: Gulf [-97, -79], Atlantic [-81, -66]), within 800 km of
  the contemporaneous interpolated centre (min of start/end point distance).
  SPC times are CST (UTC-6); selection uses an additional +/-8 h slack at
  the window edges, as in the original screening.
  SCREENING ADAPTATION (documented): five high-production storms (Irma,
  Laura, Fred, Dorian, Sally) have no usable single anchor under the
  assigned-coast rule (an early Florida or Caribbean crossing, or a main
  landfall on the other coast), so the screening window spans all of the
  storm's landfall episodes: from 24 h before the first to 72 h after the
  last HURDAT2 L fix at lat >= 25 N in the union range [-97, -66]. For
  single-landfall storms this is exactly the paper's window.
- Footprints: SPC start-to-end segment buffered by half the recorded width
  (EPSG:5070, flat caps); zero/missing width replaced by the SPC
  decade-median width, as in step1_paths; zero-length paths become discs.
- Marsh: NWI polygons from the Esri Living Atlas USA Wetlands feature
  service, queried per path bounding box (0.03 deg pad), classified by
  Cowardin ATTRIBUTE: herbaceous = emergent codes E2EM, M2EM, E1EM, M1EM;
  woody = scrub-shrub E2SS, M2SS; stratum = herbaceous + woody.
- Ida benchmark recomputed from the ORIGINAL project's saved NWI/footprint
  geojsons with the same classifier, for an apples-to-apples comparison
  against the submitted 79.7 ha total-stratum figure.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
ORIG = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes"
NWI_DIR = DATA / "nwi_screening"
NWI_DIR.mkdir(parents=True, exist_ok=True)

NWI_URL = ("https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
           "USA_Wetlands/FeatureServer/0/query")
HERB = ("E2EM", "M2EM", "E1EM", "M1EM")
WOODY = ("E2SS", "M2SS")
MIN_TCTOR_TORNADOES = 10
UNION_LON = (-97.0, -66.0)  # screening anchor range: both coasts (see header)


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1); dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def classify(attr: str) -> str:
    a = str(attr)
    if a.startswith(HERB):
        return "herbaceous"
    if a.startswith(WOODY):
        return "woody"
    return "other"


def _nwi_query_once(minx, miny, maxx, maxy, offset):
    params = {
        "where": "1=1",
        "geometry": f"{minx},{miny},{maxx},{maxy}",
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE,SYSTEM_NAME,CLASS_NAME",
        "returnGeometry": "true", "f": "geojson",
        "resultOffset": offset, "resultRecordCount": 2000,
    }
    url = NWI_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read().decode("utf-8"))


def nwi_for_bbox(minx, miny, maxx, maxy, cache_path: Path) -> gpd.GeoDataFrame:
    if cache_path.exists():
        return gpd.read_file(cache_path)
    feats, offset = [], 0
    while True:
        payload, last_err = None, None
        for attempt in range(5):
            try:
                payload = _nwi_query_once(minx, miny, maxx, maxy, offset)
                break
            except Exception as e:  # noqa: BLE001 - retry transient service errors
                last_err = e
                time.sleep(8 * (attempt + 1))
        if payload is None:
            # Deterministic fallback: split the envelope along its longer
            # axis and combine (dense wetland bboxes can return multi-MB
            # payloads that drop mid-transfer).
            if (maxx - minx) > (maxy - miny):
                mid = (minx + maxx) / 2
                a = nwi_for_bbox(minx, miny, mid, maxy, cache_path.with_suffix(".a.geojson"))
                b = nwi_for_bbox(mid, miny, maxx, maxy, cache_path.with_suffix(".b.geojson"))
            else:
                mid = (miny + maxy) / 2
                a = nwi_for_bbox(minx, miny, maxx, mid, cache_path.with_suffix(".a.geojson"))
                b = nwi_for_bbox(minx, mid, maxx, maxy, cache_path.with_suffix(".b.geojson"))
            gdf = gpd.GeoDataFrame(pd.concat([a, b], ignore_index=True), crs=4326) \
                if len(a) or len(b) else gpd.GeoDataFrame(geometry=[], crs=4326)
            if len(gdf):
                gdf = gdf.drop_duplicates(subset=["OBJECTID"]) if "OBJECTID" in gdf else gdf
                gdf.to_file(cache_path, driver="GeoJSON")
            return gdf
        batch = payload.get("features", [])
        feats.extend(batch)
        if len(batch) < 2000:
            break
        offset += 2000
    gdf = gpd.GeoDataFrame.from_features(feats, crs=4326)
    if len(gdf):
        gdf.to_file(cache_path, driver="GeoJSON")
    return gdf


def interp_center(track: pd.DataFrame, when: pd.Timestamp):
    tr = track.sort_values("datetime")
    t = (when - tr["datetime"].iloc[0]).total_seconds()
    ts = (tr["datetime"] - tr["datetime"].iloc[0]).dt.total_seconds().to_numpy()
    lat = np.interp(t, ts, tr["lat"].to_numpy())
    lon = np.interp(t, ts, tr["lon"].to_numpy())
    return lat, lon


def case_paths(storm_id, coast, hur, spc_year, decade_median_wid_m):
    g = hur[hur["storm_id"] == storm_id].sort_values("datetime")
    lo, hi = UNION_LON
    L = g[(g["record_id"] == "L") & (g["lat"] >= 25.0) & (g["lon"] >= lo) & (g["lon"] <= hi)]
    if not len(L):
        return None, "no landfall anchor (no L fix >= 25 N in union range [-97, -66])"
    t_first, t_last = L["datetime"].iloc[0], L["datetime"].iloc[-1]
    win_lo, win_hi = t_first - pd.Timedelta(hours=24), t_last + pd.Timedelta(hours=72)
    cand = spc_year.copy()
    cand["utc"] = cand["dt_naive"] + pd.Timedelta(hours=6)  # SPC CST -> UTC
    cand = cand[(cand["utc"] >= win_lo - pd.Timedelta(hours=8))
                & (cand["utc"] <= win_hi + pd.Timedelta(hours=8))]
    keep = []
    for r in cand.itertuples():
        clat, clon = interp_center(g, r.utc)
        d = min(haversine_km(r.slat, r.slon, clat, clon),
                haversine_km(r.elat if r.elat != 0 else r.slat,
                             r.elon if r.elon != 0 else r.slon, clat, clon))
        if d <= 800:
            keep.append(r._asdict() | {"dist_km": float(d)})
    if not keep:
        return None, "no SPC tornadoes in case window"
    note = (f"landfall anchors {t_first.isoformat()} to {t_last.isoformat()} "
            f"({len(L)} L fix(es) >= 25 N in union range)")
    rows = pd.DataFrame(keep)
    geoms = []
    for r in rows.itertuples():
        elat = r.elat if r.elat != 0 else r.slat
        elon = r.elon if r.elon != 0 else r.slon
        w_m = r.wid * 0.9144
        if not w_m or np.isnan(w_m) or w_m <= 0:
            w_m = decade_median_wid_m
        base = Point(r.slon, r.slat) if (elat == r.slat and elon == r.slon) \
            else LineString([(r.slon, r.slat), (elon, elat)])
        geoms.append((base, w_m))
    paths = gpd.GeoDataFrame(rows, geometry=[b for b, _ in geoms], crs=4326).to_crs(5070)
    paths["geometry"] = [geom.buffer(w / 2.0, cap_style=2) if geom.geom_type == "LineString"
                         else geom.buffer(w / 2.0)
                         for geom, (_, w) in zip(paths.geometry, geoms)]
    return paths, note


def crossed_areas(paths: gpd.GeoDataFrame, storm_key: str):
    import hashlib
    total = herb = woody = 0.0
    for i, geom in enumerate(paths.geometry):
        p = paths.iloc[[i]].to_crs(4326)
        minx, miny, maxx, maxy = p.geometry.total_bounds
        # Cache key includes the path bbox hash: a bare storm+index key would
        # silently reuse another path's polygons if the path set changes.
        h = hashlib.md5(f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}".encode()).hexdigest()[:10]
        cache = NWI_DIR / f"{storm_key}_path{i}_{h}.geojson"
        nwi = nwi_for_bbox(minx - 0.03, miny - 0.03, maxx + 0.03, maxy + 0.03, cache)
        if not len(nwi):
            continue
        nwi = nwi.to_crs(5070)
        nwi["stratum"] = nwi["ATTRIBUTE"].map(classify)
        sel = nwi[nwi["stratum"] != "other"]
        if not len(sel):
            continue
        inter = sel.geometry.intersection(geom)
        areas = inter.area / 1e4
        for sname, a in zip(sel["stratum"], areas):
            if sname == "herbaceous":
                herb += a
            elif sname == "woody":
                woody += a
        total += float(areas.sum())
        time.sleep(0.1)
    return total, herb, woody


def ida_benchmark():
    paths = gpd.read_file(ORIG / "data/paths_ida.geojson").to_crs(5070)
    nwi = gpd.read_file(ORIG / "data/nwi_bbox_ida.geojson").to_crs(5070)
    nwi["stratum"] = nwi["ATTRIBUTE"].map(classify)
    sel = nwi[nwi["stratum"] != "other"]
    inter = gpd.overlay(sel, paths, how="intersection")
    inter["ha"] = inter.geometry.area / 1e4
    agg = inter.groupby("stratum")["ha"].sum()
    return float(agg.sum()), float(agg.get("herbaceous", 0.0)), float(agg.get("woody", 0.0))


def main():
    sample = pd.read_parquet(RESULTS / "sample_two_coast.parquet")
    hur = pd.read_parquet(DATA / "hurdat2_tidy.parquet")
    spc = pd.read_csv(ORIG / "data/1950-2025_torn.csv",
                      usecols=["yr", "mo", "dy", "time", "slat", "slon", "elat", "elon", "wid", "mag"])
    spc["dt_naive"] = pd.to_datetime(spc["yr"].astype(str) + "-" + spc["mo"].astype(str).str.zfill(2)
                                     + "-" + spc["dy"].astype(str).str.zfill(2) + " " + spc["time"])
    spc["decade"] = (spc["yr"] // 10) * 10
    decade_median = (spc[spc["wid"] > 0].groupby("decade")["wid"].median() * 0.9144).to_dict()

    cand = (sample[sample["yr"].between(2016, 2023)]
            .groupby(["storm_id", "tc_name_clean", "yr", "coast"])
            .size().rename("tctor_tornadoes").reset_index())
    cand = cand[cand["tctor_tornadoes"] >= MIN_TCTOR_TORNADOES].sort_values("yr")
    print(f"candidate storms (>= {MIN_TCTOR_TORNADOES} TCTOR tornadoes, 2016-2023): {len(cand)}")

    ida_total, ida_herb, ida_woody = ida_benchmark()
    print(f"Ida benchmark from original geojsons: total {ida_total:.1f} ha, "
          f"herbaceous {ida_herb:.1f} ha, woody {ida_woody:.1f} ha (submitted total: 79.7 ha)")

    rows = []
    for r in cand.itertuples():
        key = f"{r.tc_name_clean.lower()}{r.yr}"
        paths, note = case_paths(r.storm_id, r.coast, hur,
                                 spc[spc["yr"] == r.yr], decade_median.get((r.yr // 10) * 10, 91.44))
        if paths is None:
            rows.append(dict(storm=r.tc_name_clean, year=r.yr, coast=r.coast,
                             tctor_tornadoes=r.tctor_tornadoes, case_window_paths=0,
                             total_stratum_ha=np.nan, herbaceous_ha=np.nan, woody_ha=np.nan,
                             note=note))
            continue
        try:
            total, herb, woody = crossed_areas(paths, key)
        except Exception as e:  # noqa: BLE001 - record, do not kill the screen
            rows.append(dict(storm=r.tc_name_clean, year=r.yr, coast=r.coast,
                             tctor_tornadoes=r.tctor_tornadoes,
                             case_window_paths=int(len(paths)),
                             total_stratum_ha=np.nan, herbaceous_ha=np.nan,
                             woody_ha=np.nan, note=f"SCREENING FAILED: {e}"))
            print(f"  {r.tc_name_clean} {r.yr}: FAILED ({e})")
            continue
        rows.append(dict(storm=r.tc_name_clean, year=r.yr, coast=r.coast,
                         tctor_tornadoes=r.tctor_tornadoes, case_window_paths=int(len(paths)),
                         total_stratum_ha=round(total, 1), herbaceous_ha=round(herb, 1),
                         woody_ha=round(woody, 1), note=note))
        print(f"  {r.tc_name_clean} {r.yr} ({r.coast}): {len(paths)} paths, "
              f"total {total:.1f} ha, herbaceous {herb:.1f} ha")

    out = pd.DataFrame(rows).sort_values("herbaceous_ha", ascending=False, na_position="last")
    out.to_csv(RESULTS / "case_screening_2016_2023.csv", index=False)
    bench = dict(ida_total_stratum_ha=round(ida_total, 1), ida_herbaceous_ha=round(ida_herb, 1),
                 ida_woody_ha=round(ida_woody, 1), ida_submitted_total_ha=79.7)
    with open(RESULTS / "case_screening_benchmark.json", "w") as f:
        json.dump(bench, f, indent=2)
    print(out.to_string(index=False))
    print(bench)


if __name__ == "__main__":
    main()
