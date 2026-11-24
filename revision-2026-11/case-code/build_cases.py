#!/usr/bin/env python3
"""Build HLS marsh case studies for Idalia (2023) and Florence (2018).

Faithful replication of the original angle2 pipeline:
  step1_paths.py  -> case-window SPC footprints (buffered start-to-end
                     segments, half recorded width, flat caps, EPSG:5070;
                     decade-median width for zero/missing widths)
  06_case_screening.py (validated against Ida's 79.7 ha) -> the exact
                     case-window selection used here: SPC CST (UTC-6) to
                     UTC, window -24 h to +72 h around the landfall anchor
                     (first to last HURDAT2 L fix at lat >= 25 N in the
                     union longitude range [-97, -66]), +/-8 h edge slack,
                     800 km from the interpolated centre (min of start/end)
  step2_overlap.py -> NWI marsh crossings via the Esri Living Atlas USA
                     Wetlands service (NWI republication), per-path bbox
                     queries (0.03 deg pad), Cowardin classification:
                     marsh stratum = E2EM/M2EM/E1EM/M1EM (herbaceous) +
                     E2SS/M2SS (woody scrub-shrub, tracked separately in
                     the screening table; in the original step2 both are
                     in the marsh stratum and forested FO is separate)
  step3c_points.py -> largest 15 km-linkage cluster as the analysis
                     footprint; reference = NWI marsh 2-10 km from the
                     cluster's marsh-crossing paths, capped at the larger
                     of 3x footprint area or 300 ha, nearest first, min 8
                     polygons; HLS v2.0 (hls2-s30 + hls2-l30) via the
                     Microsoft Planetary Computer; 30 m UTM point grid;
                     monthly per-pixel median composites, -6 to +24
                     months; Fmask bits 0-4 masked; vegetated mask =
                     pre-storm median NDVI > 0.2; NDVI (NIR-Red)/(NIR+Red),
                     NIR = B8A (S30) / B05 (L30); McFeeters NDWI
                     (Green-NIR)/(Green+NIR); anomaly = footprint minus
                     reference; recovery slope = OLS of anomaly over
                     months 2-18.
  placebo_ida.py  -> 200 coherent pseudo-footprint patches in the
                     untouched reference marsh (seed pixel + nearest
                     vegetated neighbours), patch pixels removed from
                     the reference before differencing, swing estimand
                     identical to the case swing. Seed fixed below.
  Companion within-path score (Sokol 2026, angle1 02e/03 definition):
                     share of vegetated footprint pixels whose
                     control-relative NDVI drop (pre-storm mean to the
                     landfall composite, minus the reference mean drop)
                     is >= 0.15. Reported with the 0.10 detection
                     threshold used in the companion study.

Inputs are read (never modified) from the original project and the
revision screening cache. All outputs land under this directory.
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import transform as wtransform
from rasterio.warp import transform_bounds as tb
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
import planetary_computer
import pystac_client

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
DATA.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)
ORIG = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes"
REV = Path.home() / "workspace/moore-pitch/angle2-revision-2026-11/analysis"
NWI_CACHE = REV / "data/nwi_screening"
SERVICE = ("https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/"
           "USA_Wetlands/FeatureServer/0/query")
CAT = "https://planetarycomputer.microsoft.com/api/stac/v1"
HERB = ("E2EM", "M2EM", "E1EM", "M1EM")
WOODY_SS = ("E2SS", "M2SS")
MARSH_WHERE = ("ATTRIBUTE LIKE 'E2EM%' OR ATTRIBUTE LIKE 'M2EM%' OR ATTRIBUTE LIKE 'E1EM%' "
               "OR ATTRIBUTE LIKE 'M1EM%' OR ATTRIBUTE LIKE 'E2SS%' OR ATTRIBUTE LIKE 'M2SS%'")
PLACEBO_SEED = 20261124
N_PLACEBOS = 200

STORMS = {
    "idalia": {"sid": "AL102023", "year": 2023, "key": "idalia2023"},
    "florence": {"sid": "AL062018", "year": 2018, "key": "florence2018"},
}


# ---------------------------------------------------------------- HURDAT2
def parse_hurdat():
    tracks = {}
    cur = None
    import re
    with open(ORIG / "data/hurdat2.txt") as f:
        for line in f:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and re.match(r"^(AL|CP|EP)\d+$", parts[0]):
                cur = parts[0]
                tracks[cur] = []
            elif cur and len(parts) >= 8 and re.match(r"^\d{8}$", parts[0]):
                def plat(s):
                    return float(s[:-1]) * (1 if s[-1] == "N" else -1)

                def plon(s):
                    return float(s[:-1]) * (-1 if s[-1] == "W" else 1)

                tracks[cur].append({
                    "dt": datetime.strptime(parts[0] + parts[1], "%Y%m%d%H%M"),  # naive UTC, as in the screening code
                    "record_id": parts[2], "lat": plat(parts[4]), "lon": plon(parts[5])})
    return tracks


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def center_at(pts, when):
    if when <= pts[0]["dt"]:
        return pts[0]["lat"], pts[0]["lon"]
    if when >= pts[-1]["dt"]:
        return pts[-1]["lat"], pts[-1]["lon"]
    for a, b in zip(pts, pts[1:]):
        if a["dt"] <= when <= b["dt"]:
            f = (when - a["dt"]).total_seconds() / max((b["dt"] - a["dt"]).total_seconds(), 1)
            return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (b["lon"] - a["lon"])


# ------------------------------------------------------------------- paths
def build_paths(storm, tracks, spc, decade_med_m):
    cfg = STORMS[storm]
    pts = tracks[cfg["sid"]]
    L = [p for p in pts if "L" in p["record_id"] and p["lat"] >= 25.0 and -97.0 <= p["lon"] <= -66.0]
    t_first, t_last = L[0]["dt"], L[-1]["dt"]
    landfall = t_first  # single anchor for both storms (screening note)
    win_lo, win_hi = t_first - timedelta(hours=24), t_last + timedelta(hours=72)
    cand = spc[spc["yr"] == cfg["year"]].copy()
    cand["utc"] = cand["dt_naive"] + pd.Timedelta(hours=6)
    cand = cand[(cand["utc"] >= win_lo - timedelta(hours=8)) & (cand["utc"] <= win_hi + timedelta(hours=8))]
    keep = []
    for r in cand.itertuples():
        c = center_at(pts, r.utc.to_pydatetime())
        elat = r.elat if r.elat != 0 else r.slat
        elon = r.elon if r.elon != 0 else r.slon
        d = min(haversine_km(r.slat, r.slon, c[0], c[1]), haversine_km(elat, elon, c[0], c[1]))
        if d <= 800:
            keep.append(r)
    rows = pd.DataFrame([k._asdict() for k in keep])
    geoms = []
    for r in rows.itertuples():
        elat = r.elat if r.elat != 0 else r.slat
        elon = r.elon if r.elon != 0 else r.slon
        w_m = r.wid * 0.9144
        if not w_m or np.isnan(w_m) or w_m <= 0:
            w_m = decade_med_m
        base = Point(r.slon, r.slat) if (elat == r.slat and elon == r.slon) else LineString([(r.slon, r.slat), (elon, elat)])
        geoms.append((base, w_m))
    paths = gpd.GeoDataFrame(rows, geometry=[b for b, _ in geoms], crs=4326).to_crs(5070)
    paths["geometry"] = [g.buffer(w / 2.0, cap_style=2) if g.geom_type == "LineString" else g.buffer(w / 2.0)
                         for g, (_, w) in zip(paths.geometry, geoms)]
    info = {"storm_id": cfg["sid"], "landfall_utc": landfall.isoformat(),
            "landfall_lat": L[0]["lat"], "landfall_lon": L[0]["lon"],
            "n_landfall_fixes_union": len(L), "n_paths": int(len(paths)),
            "footprint_ha": round(float(paths.geometry.area.sum()) / 1e4, 2)}
    print(f"{storm}: landfall {landfall} paths {len(paths)} footprint {info['footprint_ha']} ha", flush=True)
    return paths, info


# --------------------------------------------------------------------- NWI
def classify(attr):
    a = str(attr)
    if a.startswith(HERB):
        return "herbaceous"
    if a.startswith(WOODY_SS):
        return "woody"
    return "other"


def nwi_query(bbox, where="1=1"):
    feats, offset = [], 0
    while True:
        params = {"where": where, "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
                  "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
                  "spatialRel": "esriSpatialRelIntersects",
                  "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE,SYSTEM_NAME,CLASS_NAME",
                  "returnGeometry": "true", "f": "geojson",
                  "resultOffset": str(offset), "resultRecordCount": "2000",
                  "orderByFields": "OBJECTID"}
        url = SERVICE + "?" + urllib.parse.urlencode(params)
        payload = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
                with urllib.request.urlopen(req, timeout=300) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                break
            except Exception:
                time.sleep(8 * (attempt + 1))
        if payload is None:
            raise RuntimeError(f"NWI query failed for bbox {bbox}")
        batch = payload.get("features", [])
        feats.extend(batch)
        if len(batch) < 2000 or not payload.get("exceededTransferLimit"):
            break
        offset += 2000
    return feats


def crossings(storm, paths):
    """Per-path NWI intersections; reuses the screening cache files."""
    key = STORMS[storm]["key"]
    pieces = []
    total = herb = woody = 0.0
    crossing_paths = 0
    for i, geom in enumerate(paths.geometry):
        p4326 = paths.iloc[[i]].to_crs(4326)
        minx, miny, maxx, maxy = p4326.geometry.total_bounds
        h = hashlib.md5(f"{minx:.4f},{miny:.4f},{maxx:.4f},{maxy:.4f}".encode()).hexdigest()[:10]
        cache = NWI_CACHE / f"{key}_path{i}_{h}.geojson"
        if cache.exists():
            nwi = gpd.read_file(cache)
        else:
            feats = nwi_query((minx - 0.03, miny - 0.03, maxx + 0.03, maxy + 0.03))
            nwi = gpd.GeoDataFrame.from_features(feats, crs=4326) if feats else gpd.GeoDataFrame(geometry=[], crs=4326)
            if len(nwi):
                nwi.to_file(DATA / f"nwi_{key}_path{i}.geojson", driver="GeoJSON")
        if not len(nwi):
            continue
        nwi = nwi.to_crs(5070)
        nwi["stratum"] = nwi["ATTRIBUTE"].map(classify)
        sel = nwi[nwi["stratum"] != "other"]
        if not len(sel):
            continue
        inter = sel.geometry.intersection(geom)
        areas = inter.area / 1e4
        path_ha = float(areas.sum())
        if path_ha * 1e4 > 1:
            crossing_paths += 1
        for sname, a in zip(sel["stratum"], areas):
            if a <= 0:
                continue
            if sname == "herbaceous":
                herb += a
            else:
                woody += a
        total += path_ha
        keep = inter[inter.area > 0]
        if len(keep):
            g = gpd.GeoDataFrame({"ATTRIBUTE": sel.loc[keep.index, "ATTRIBUTE"].values,
                                  "stratum": sel.loc[keep.index, "stratum"].values},
                                 geometry=keep.values, crs=5070)
            pieces.append(g)
    marsh = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs=5070) if pieces else gpd.GeoDataFrame(geometry=[], crs=5070)
    info = {"total_marsh_ha": round(total, 3), "herbaceous_ha": round(herb, 3),
            "woody_ha": round(woody, 3), "paths_crossing_marsh": crossing_paths}
    print(f"{storm} crossings: {info}", flush=True)
    return marsh, info


# ------------------------------------------------------------------- zones
def build_zones(storm, paths, marsh):
    _fm = marsh.copy()
    _union = unary_union(_fm.geometry.buffer(15000).values)
    _comps = list(_union.geoms) if _union.geom_type == "MultiPolygon" else [_union]
    assign = []
    for g_ in _fm.geometry:
        for ci, comp in enumerate(_comps):
            if g_.buffer(15000).intersects(comp):
                assign.append(ci)
                break
        else:
            assign.append(-1)
    _fm = _fm.assign(cluster=assign)
    areas = _fm.geometry.area.groupby(_fm["cluster"]).sum()
    best = int(areas.idxmax())
    cluster_info = {"n_clusters": int(len(areas)), "chosen_cluster_ha": round(float(areas.max()) / 1e4, 3),
                    "excluded_cluster_ha": round(float((areas.sum() - areas.max())) / 1e4, 3),
                    "total_marsh_ha_clusters": round(float(areas.sum()) / 1e4, 3),
                    "cluster_herbaceous_ha": round(float(_fm[_fm.cluster == best].query("stratum=='herbaceous'").geometry.area.sum()) / 1e4, 3),
                    "cluster_woody_ha": round(float(_fm[_fm.cluster == best].query("stratum=='woody'").geometry.area.sum()) / 1e4, 3)}
    fp_marsh = _fm[_fm["cluster"] == best].to_crs(4326)
    marsh_union = unary_union(_fm[_fm["cluster"] == best].geometry.values)
    crossing = paths[paths.geometry.intersects(marsh_union)]
    fp_union5070 = unary_union(crossing.geometry.values)
    ring_tmp = fp_union5070.buffer(10000)
    ring_wgs = gpd.GeoSeries([ring_tmp], crs=5070).to_crs(4326).iloc[0]
    rx0, ry0, rx1, ry1 = ring_wgs.bounds
    feats, seen = [], set()
    tile = 0.25
    tx = rx0
    while tx < rx1:
        ty = ry0
        while ty < ry1:
            bb = (tx, ty, min(tx + tile, rx1), min(ty + tile, ry1))
            for f_ in nwi_query(bb, where=MARSH_WHERE):
                oid = (f_.get("properties") or {}).get("OBJECTID")
                if oid in seen:
                    continue
                seen.add(oid)
                feats.append(f_)
            ty += tile
        tx += tile
    nwi = gpd.GeoDataFrame.from_features(feats, crs=4326)
    nwi5070 = nwi.to_crs(5070)
    ring = fp_union5070.buffer(10000).difference(fp_union5070.buffer(2000))
    ref = nwi5070[nwi5070.geometry.intersects(ring)].copy()
    ref["geometry"] = ref.geometry.intersection(ring)
    ref = ref[ref.geometry.area > 100]
    fp_area = float(_fm[_fm["cluster"] == best].geometry.area.sum())
    if len(ref):
        ref["dist"] = ref.geometry.distance(fp_union5070)
        ref = ref.sort_values("dist")
        cum = ref.geometry.area.cumsum()
        cap = max(fp_area * 3, 300 * 1e4)
        keep = ref[(cum - ref.geometry.area < cap) | (ref.index.isin(ref.index[:8]))]
        ref = keep if len(keep) else ref.head(20)
    ref_wgs = ref.to_crs(4326)
    fp_marsh.to_file(DATA / f"footprint_{storm}.geojson", driver="GeoJSON")
    ref_wgs.to_file(DATA / f"reference_{storm}.geojson", driver="GeoJSON")
    print(f"{storm} zones: {cluster_info}; ref {ref.geometry.area.sum()/1e4:.2f} ha ({len(ref)} polys)", flush=True)
    return fp_marsh, ref_wgs, cluster_info, fp_area / 1e4, float(ref.geometry.area.sum()) / 1e4, int(len(crossing))


# --------------------------------------------------------------------- HLS
def month_starts(d0, d1):
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(datetime(y, m, 1))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def sample_scene(args):
    it, pts = args
    lons, lats = pts
    coll = it.properties.get("_coll", "")
    is_s30 = "s30" in it.id.lower() or coll == "hls2-s30"
    nir_key = "B8A" if is_s30 else "B05"
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    if not all([href("B04"), href(nir_key), href("Fmask"), href("B03")]):
        return None
    out = {}
    for key, name in [("B04", "red"), (nir_key, "nir"), ("B03", "grn"), ("Fmask", "fm")]:
        with rasterio.open(href(key)) as src:
            xs, ys = wtransform("EPSG:4326", src.crs, list(lons), list(lats))
            vals = np.array([v[0] for v in src.sample(zip(xs, ys))], dtype=np.float64)
            nod = src.nodata
        if nod is not None:
            vals[vals == nod] = np.nan
        out[name] = vals
    red, nir, grn, fm = out["red"], out["nir"], out["grn"], out["fm"]
    fm_i = np.nan_to_num(fm, nan=255).astype(int)
    bad = ((fm_i & 1) != 0) | ((fm_i & 2) != 0) | ((fm_i & 4) != 0) | ((fm_i & 8) != 0) | ((fm_i & 16) != 0)
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid, (nir - red) / (nir + red + 1e-9), np.nan)
    ndwi = np.where(valid & (grn > 0), (grn - nir) / (grn + nir + 1e-9), np.nan)
    return ndvi, ndwi, is_s30


def run_hls(storm, fp_marsh, ref_wgs, landfall_date):
    lf = datetime.fromisoformat(landfall_date)
    union_wgs = pd.concat([fp_marsh, ref_wgs]) if len(ref_wgs) else fp_marsh
    minx, miny, maxx, maxy = union_wgs.total_bounds
    minx -= 0.005; miny -= 0.005; maxx += 0.005; maxy += 0.005
    bbox = [minx, miny, maxx, maxy]
    cx = (minx + maxx) / 2
    utm_epsg = 32600 + int((cx + 180) // 6) + 1
    ux0, uy0, ux1, uy1 = tb("EPSG:4326", f"EPSG:{utm_epsg}", minx, miny, maxx, maxy)
    res = 30.0
    W = int(np.ceil((ux1 - ux0) / res)); H = int(np.ceil((uy1 - uy0) / res))
    tr = from_bounds(ux0, uy0, ux1, uy1, W, H)
    fp_utm = fp_marsh.to_crs(f"EPSG:{utm_epsg}")
    ref_utm = ref_wgs.to_crs(f"EPSG:{utm_epsg}")
    fp_mask = rasterize([(g, 1) for g in fp_utm.geometry], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    ref_mask = rasterize([(g, 1) for g in ref_utm.geometry], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    ref_mask = ref_mask & ~fp_mask
    rows_f, cols_f = np.where(fp_mask)
    rows_r, cols_r = np.where(ref_mask)
    xs, ys = rasterio.transform.xy(tr, np.concatenate([rows_f, rows_r]), np.concatenate([cols_f, cols_r]))
    xs = np.array(xs); ys = np.array(ys)
    lons, lats = wtransform(f"EPSG:{utm_epsg}", "EPSG:4326", list(xs), list(ys))
    zone = np.array(["footprint"] * len(rows_f) + ["reference"] * len(rows_r))
    xy = np.column_stack([xs, ys])
    print(f"{storm}: points fp {len(rows_f)} ref {len(rows_r)} UTM{utm_epsg}", flush=True)

    cat = pystac_client.Client.open(CAT)
    months = month_starts(lf - timedelta(days=183), lf + timedelta(days=731))
    cache = RESULTS / f"pixels_{storm}.npz"
    monthly_pix = {}
    if cache.exists():
        z = np.load(cache)
        monthly_pix = {k[:-6]: (z[k], z[k[:-6] + "__ndwi"]) for k in list(z.files) if k.endswith("__ndvi")}
        print(f"{storm}: pixel cache {len(monthly_pix)} months", flush=True)
    mix = {"S30": 0, "L30": 0}
    scene_counts = {}
    for mi, ms in enumerate(months):
        label = ms.strftime("%Y-%m")
        if label in monthly_pix:
            continue
        me = (months[mi + 1] if mi + 1 < len(months) else ms + timedelta(days=31))
        rng = f"{ms.strftime('%Y-%m-%d')}/{me.strftime('%Y-%m-%d')}"
        items = []
        for coll in ["hls2-s30", "hls2-l30"]:
            try:
                s = cat.search(collections=[coll], bbox=bbox, datetime=rng, max_items=200)
                got = list(s.items())
                for it in got:
                    it.properties["_coll"] = coll
                items.extend(got)
            except Exception as e:
                print(f"  search {coll} {rng} failed: {e}", flush=True)
        seen = set(); uniq = []
        for it in items:
            if it.id in seen:
                continue
            seen.add(it.id); uniq.append(it)
        items = uniq
        ndvi_list, ndwi_list = [], []
        if items:
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {ex.submit(sample_scene, (it, (lons, lats))): it for it in items}
                for fut, it in futs.items():
                    try:
                        r = fut.result()
                    except Exception as e:
                        print(f"    scene {it.id} failed: {type(e).__name__}: {e}", flush=True)
                        continue
                    if r is None:
                        continue
                    ndvi_list.append(r[0]); ndwi_list.append(r[1])
                    mix["S30" if r[2] else "L30"] += 1
        scene_counts[label] = len(ndvi_list)
        if ndvi_list:
            with np.errstate(all="ignore"):
                monthly_pix[label] = (np.nanmedian(np.stack(ndvi_list), axis=0),
                                      np.nanmedian(np.stack(ndwi_list), axis=0))
        else:
            monthly_pix[label] = (np.full(len(lons), np.nan), np.full(len(lons), np.nan))
        _tmp = cache.with_suffix(".tmp.npz")
        np.savez_compressed(_tmp, **{f"{k}__ndvi": v[0] for k, v in monthly_pix.items()},
                            **{f"{k}__ndwi": v[1] for k, v in monthly_pix.items()})
        _tmp.replace(cache)  # atomic: a killed run cannot corrupt prior months
        print(f"  {label}: {len(ndvi_list)} scenes", flush=True)

    pre_labels = [m for m in monthly_pix if datetime.fromisoformat(m + "-01") < lf]
    with np.errstate(all="ignore"):
        pre_med = np.nanmedian(np.stack([monthly_pix[m][0] for m in pre_labels]), axis=0)
    veg = pre_med > 0.2
    rows = []
    for ms in months:
        label = ms.strftime("%Y-%m")
        ndvi_p, ndwi_p = monthly_pix[label]
        rec = {"storm": storm, "month": label, "month_offset": round((ms - lf).days / 30.44, 2),
               "n_scenes": scene_counts.get(label)}
        for zname in ["footprint", "reference"]:
            m_ = veg & (zone == zname)
            fv = ndvi_p[m_]; fv = fv[np.isfinite(fv)]
            fw = ndwi_p[m_]; fw = fw[np.isfinite(fw)]
            rec[f"{zname}_ndvi"] = float(np.mean(fv)) if len(fv) >= 10 else None
            rec[f"{zname}_n"] = int(len(fv))
            rec[f"{zname}_ndwi"] = float(np.mean(fw)) if len(fw) else None
        rec["anomaly"] = (rec["footprint_ndvi"] - rec["reference_ndvi"]) if (rec["footprint_ndvi"] is not None and rec["reference_ndvi"] is not None) else None
        rec["note"] = "" if rec["anomaly"] is not None else "insufficient_clear_pixels_or_no_scenes"
        rows.append(rec)
    sdf = pd.DataFrame(rows)
    sdf.to_csv(RESULTS / f"trajectories_{storm}.csv", index=False)
    np.savez_compressed(RESULTS / f"points_{storm}.npz", xy=xy, zone=zone, veg=veg,
                        pre_med=pre_med, lons=np.array(lons), lats=np.array(lats))
    return sdf, monthly_pix, zone, veg, xy, mix


# -------------------------------------------------------------- statistics
def summarise(storm, sdf, monthly_pix, zone, veg, xy, landfall_date, extra):
    lf = datetime.fromisoformat(landfall_date)
    pre = sdf[(sdf["month_offset"] < 0) & sdf["anomaly"].notna()]
    pre_mean_anom = float(pre["anomaly"].mean())
    pre_fp_ndvi = float(pre["footprint_ndvi"].mean())
    pre_ref_ndvi = float(pre["reference_ndvi"].mean())
    last_pre = pre.iloc[-1]
    post = sdf[(sdf["month_offset"] >= 0) & (sdf["month_offset"] <= 1.5) & sdf["anomaly"].notna()]
    imm = post.iloc[0]
    imm_anom = float(imm["anomaly"])
    swing = imm_anom - pre_mean_anom
    next_row = sdf[sdf["month"] > imm["month"]].iloc[0] if (sdf["month"] > imm["month"]).any() else None
    rec_df = sdf[(sdf["month_offset"] >= 2) & (sdf["month_offset"] <= 18) & sdf["anomaly"].notna()]
    slope = r2 = None
    if len(rec_df) >= 4:
        x = rec_df["month_offset"].values; y = rec_df["anomaly"].values
        A = np.polyfit(x, y, 1); slope = float(A[0])
        pred = np.polyval(A, x)
        r2 = float(1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12))
    # NDWI change across landfall (last pre month -> immediate month)
    ndwi = {"footprint_pre": float(last_pre["footprint_ndwi"]), "footprint_post": float(imm["footprint_ndwi"]),
            "reference_pre": float(last_pre["reference_ndwi"]), "reference_post": float(imm["reference_ndwi"])}
    # Companion within-path scar share: pre-storm mean per pixel vs immediate month
    pre_stack = np.stack([monthly_pix[m][0] for m in monthly_pix if datetime.fromisoformat(m + "-01") < lf])
    with np.errstate(all="ignore"):
        pre_pix = np.nanmean(pre_stack, axis=0)
    imm_pix = monthly_pix[str(imm["month"])][0]
    fp_m = veg & (zone == "footprint")
    ref_m = veg & (zone == "reference")
    drop_fp = pre_pix[fp_m] - imm_pix[fp_m]
    drop_ref = pre_pix[ref_m] - imm_pix[ref_m]
    ctrl_drop = float(np.nanmean(drop_ref))
    rel = drop_fp - ctrl_drop
    valid = np.isfinite(rel)
    scar_share = float((rel[valid] >= 0.15).mean()) if valid.sum() else None
    companion = {"scar_share_ge_0.15": scar_share, "n_valid_footprint_pixels": int(valid.sum()),
                 "control_mean_drop": ctrl_drop, "detected_at_0.10_threshold": bool(scar_share is not None and scar_share >= 0.10),
                 "definition": "share of vegetated footprint pixels whose NDVI drop (pre-storm mean to landfall composite) exceeds the reference mean drop by >= 0.15 (Sokol 2026 companion definition)"}
    summ = {"storm": storm, "landfall": landfall_date, **extra,
            "pre_storm_mean_anomaly": pre_mean_anom, "pre_storm_n_months": int(len(pre)),
            "pre_storm_footprint_ndvi_mean": pre_fp_ndvi, "pre_storm_reference_ndvi_mean": pre_ref_ndvi,
            "last_pre_month": str(last_pre["month"]), "last_pre_footprint_ndvi": float(last_pre["footprint_ndvi"]),
            "last_pre_reference_ndvi": float(last_pre["reference_ndvi"]),
            "immediate_month": str(imm["month"]), "immediate_anomaly": imm_anom,
            "immediate_footprint_ndvi": float(imm["footprint_ndvi"]), "immediate_reference_ndvi": float(imm["reference_ndvi"]),
            "swing": swing,
            "next_month": (str(next_row["month"]) if next_row is not None else None),
            "next_month_anomaly": (float(next_row["anomaly"]) if next_row is not None and pd.notna(next_row["anomaly"]) else None),
            "ndwi": ndwi, "ndwi_anomaly_change": (ndwi["footprint_post"] - ndwi["reference_post"]) - (ndwi["footprint_pre"] - ndwi["reference_pre"]),
            "recovery_slope_per_month": slope, "recovery_r2": r2, "recovery_n_months": int(len(rec_df)),
            "cloud_gap_months": [str(r["month"]) for _, r in sdf.iterrows() if r["anomaly"] is None],
            "veg_pixels_fp": int((veg & (zone == "footprint")).sum()),
            "veg_pixels_ref": int((veg & (zone == "reference")).sum()),
            "companion_within_path_score": companion}
    return summ, pre_pix, imm_pix


def placebo(storm, monthly_pix, zone, veg, xy, landfall_date, imm_month, patch_n):
    """200 coherent pseudo-footprints in the untouched reference marsh."""
    from scipy.spatial import cKDTree
    lf = datetime.fromisoformat(landfall_date)
    ref_idx = np.where(veg & (zone == "reference"))[0]
    cand_xy = xy[ref_idx]
    tree = cKDTree(cand_xy)
    rng = np.random.default_rng(PLACEBO_SEED)
    labels = sorted(monthly_pix.keys())
    pre_labels = [m for m in labels if datetime.fromisoformat(m + "-01") < lf]

    def zmean(arr, idx):
        v = arr[idx]
        v = v[np.isfinite(v)]
        return float(v.mean()) if len(v) else np.nan

    swings = []
    for _ in range(N_PLACEBOS):
        seed_i = int(rng.integers(0, len(ref_idx)))
        _, nn = tree.query(cand_xy[seed_i], k=min(patch_n, len(ref_idx)))
        patch = ref_idx[np.sort(nn)]
        rest = np.setdiff1d(ref_idx, patch)
        anoms_pre = [zmean(monthly_pix[m][0], patch) - zmean(monthly_pix[m][0], rest) for m in pre_labels]
        anom_imm = zmean(monthly_pix[imm_month][0], patch) - zmean(monthly_pix[imm_month][0], rest)
        swings.append(anom_imm - float(np.mean(anoms_pre)))
    swings = np.array(swings)
    return swings


def main():
    only = sys.argv[1:] or ["idalia", "florence"]
    tracks = parse_hurdat()
    spc = pd.read_csv(ORIG / "data/1950-2025_torn.csv", low_memory=False)
    spc["dt_naive"] = pd.to_datetime(spc["date"].astype(str) + " " + spc["time"].astype(str), errors="coerce")
    spc["wid_num"] = pd.to_numeric(spc["wid"], errors="coerce")
    med_by_decade = spc.groupby((spc["yr"] // 10) * 10)["wid_num"].median()
    summaries = {}
    for storm in only:
        cfg = STORMS[storm]
        dec_med_m = float(med_by_decade.loc[(cfg["year"] // 10) * 10] * 0.9144)
        paths, pinfo = build_paths(storm, tracks, spc, dec_med_m)
        paths.to_crs(4326).to_file(DATA / f"paths_{storm}.geojson", driver="GeoJSON")
        marsh, cinfo = crossings(storm, paths)
        marsh.to_crs(4326).to_file(DATA / f"marsh_in_paths_{storm}.geojson", driver="GeoJSON")
        fp_marsh, ref_wgs, cluster_info, fp_ha, ref_ha, n_cross_paths = build_zones(storm, paths, marsh)
        landfall_date = pinfo["landfall_utc"][:10]
        sdf, monthly_pix, zone, veg, xy, mix = run_hls(storm, fp_marsh, ref_wgs, landfall_date)
        extra = {**pinfo, **cinfo, **cluster_info, "footprint_marsh_ha_cluster": round(fp_ha, 3),
                 "reference_marsh_ha": round(ref_ha, 3), "cluster_crossing_paths": n_cross_paths,
                 "sensor_mix_sampled_scenes": mix}
        summ, _, _ = summarise(storm, sdf, monthly_pix, zone, veg, xy, landfall_date, extra)
        # Placebo distribution (used as the positive-case test when the
        # swing is negative, and as the noise/power scale otherwise).
        swings = placebo(storm, monthly_pix, zone, veg, xy, landfall_date,
                         summ["immediate_month"], summ["veg_pixels_fp"])
        obs = summ["swing"]
        p_emp = float((swings <= obs).mean())
        summ["placebo"] = {"n_draws": N_PLACEBOS, "seed": PLACEBO_SEED, "patch_n_pixels": summ["veg_pixels_fp"],
                           "observed_swing": obs, "median": float(np.median(swings)),
                           "q1": float(np.percentile(swings, 25)), "q3": float(np.percentile(swings, 75)),
                           "p2_5": float(np.percentile(swings, 2.5)), "p97_5": float(np.percentile(swings, 97.5)),
                           "min": float(swings.min()), "max": float(swings.max()),
                           "share_at_or_below_observed": p_emp,
                           "empirical_p_le_0.005_form": (1 + int((swings <= obs).sum())) / (N_PLACEBOS + 1),
                           "sd": float(swings.std(ddof=1)),
                           "detectable_swing_95": float(np.percentile(swings, 2.5))}
        pd.DataFrame({"draw": np.arange(N_PLACEBOS), "swing": swings}).to_csv(RESULTS / f"placebo_{storm}_swings.csv", index=False)
        summaries[storm] = summ
        (RESULTS / f"summary_{storm}.json").write_text(json.dumps(summ, indent=2, default=str))
        print(json.dumps(summ, indent=2, default=str), flush=True)
    (RESULTS / "summaries.json").write_text(json.dumps(summaries, indent=2, default=str))
    print("BUILD CASES DONE", flush=True)


if __name__ == "__main__":
    main()
