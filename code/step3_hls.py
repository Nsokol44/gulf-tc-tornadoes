#!/usr/bin/env python3
"""Step 3: HLS NDVI trajectories via Planetary Computer hls2-s30 / hls2-l30.
Design (compute-feasible, honest):
- Per storm: footprint sample = marsh polygons inside path buffers (from step2);
  reference sample = NWI marsh polygons in ring 2-10 km from paths within same bbox
  region (re-query NWI over expanded bbox).
- Raster approach on a 30 m grid over a CLIPPED study extent: union of footprint
  marsh extent + reference marsh polygons SUBSET (nearest reference polygons up to
  area cap) to keep grids tractable. Monthly median composites from all HLS scenes
  in month; Fmask masking; vegetated mask = pre-storm median NDVI > 0.2.
- Zones: footprint mask vs reference mask rasterized on same grid.
Outputs results/marsh_trajectories.csv, results/marsh_summary.json,
data/footprint_<storm>.geojson, data/reference_<storm>.geojson
"""
import json, math, time
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from rasterio.warp import transform_bounds
import pystac_client, planetary_computer

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"; RESULTS = BASE / "results"
CAT = "https://planetarycomputer.microsoft.com/api/stac/v1"

_lf = json.loads((RESULTS / "step1_landfalls.json").read_text())["landfalls"]
LAND = {k.lower(): v["landfall_utc"][:10] for k, v in _lf.items() if v.get("landfall_utc")}

def month_starts(d0, d1):
    out = []
    y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(datetime(y, m, 1))
        m += 1
        if m == 13: y, m = y + 1, 1
    return out

def signed_href(item, key):
    s = planetary_computer.sign(item)
    return s.assets[key].href if key in s.assets else None

def read_win(href, bounds_wgs, shape, transform):
    """Read asset resampled/windowed onto target grid via rasterio WarpedVRT-like read.
    Uses rasterio.open + read with out_shape and window approximated by bounds transform."""
    from rasterio.vrt import WarpedVRT
    from rasterio.crs import CRS
    with rasterio.open(href) as src:
        vrt_opts = dict(crs="EPSG:4326", transform=transform, width=shape[1], height=shape[0],
                        resampling=rasterio.enums.Resampling.nearest)
        with WarpedVRT(src, **vrt_opts) as vrt:
            return vrt.read(1)

def process_storm(cat, storm, landfall):
    print(f"\n===== {storm} landfall {landfall} =====", flush=True)
    marsh_fp_file = DATA / f"marsh_in_paths_{storm}.geojson"
    paths = gpd.read_file(DATA / f"paths_{storm}.geojson")
    if not marsh_fp_file.exists():
        return {"storm": storm, "status": "dropped_no_marsh_file"}
    fp_marsh_all = gpd.read_file(marsh_fp_file)  # EPSG:4326 footprint marsh polygons
    if len(fp_marsh_all) == 0:
        return {"storm": storm, "status": "dropped_no_marsh_area"}
    # Cluster footprint marsh (15 km linkage in EPSG:5070); process the largest
    # cluster only so the 30 m grid stays tractable when a storm's marsh crossings
    # span two coasts. Excluded cluster area is recorded in the summary.
    _fm5070 = fp_marsh_all.to_crs("EPSG:5070")
    _union = unary_union(_fm5070.geometry.buffer(15000).values)
    _comps = list(_union.geoms) if _union.geom_type == "MultiPolygon" else [_union]
    _assign = []
    for g_ in _fm5070.geometry:
        for ci, comp in enumerate(_comps):
            if g_.buffer(15000).intersects(comp):
                _assign.append(ci); break
        else:
            _assign.append(-1)
    _fm5070 = _fm5070.assign(cluster=_assign)
    _areas = _fm5070.geometry.area.groupby(_fm5070["cluster"]).sum()
    best_cluster = int(_areas.idxmax())
    cluster_info = {"n_clusters": int(len(_areas)), "chosen_cluster_ha": round(float(_areas.max()) / 1e4, 3),
                    "excluded_cluster_ha": round(float((_areas.sum() - _areas.max())) / 1e4, 3),
                    "total_marsh_ha": round(float(_areas.sum()) / 1e4, 3)}
    print("clusters:", cluster_info)
    fp_marsh = fp_marsh_all[_fm5070["cluster"].values == best_cluster].copy()
    print(f"chosen cluster polys: {len(fp_marsh)}")
    paths5070 = paths.to_crs("EPSG:5070")
    # Reference ring is built around the MARSH-CROSSING paths only (the coastal
    # cluster), not the whole storm path set (e.g. Ida NJ tornadoes have no marsh).
    fp_marsh5070 = fp_marsh.to_crs("EPSG:5070")
    marsh_union = unary_union(fp_marsh5070.geometry.values)
    crossing = paths5070[paths5070.geometry.intersects(marsh_union)]
    print(f"marsh-crossing paths for reference ring: {len(crossing)}")
    fp_union5070 = unary_union(crossing.geometry.values)
    # Query NWI (Esri USA Wetlands, NWI-sourced) tiled over the ring bounds.
    import urllib.request, urllib.parse
    SERVICE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0/query"
    ring_tmp = fp_union5070.buffer(10000)
    ring_wgs = gpd.GeoSeries([ring_tmp], crs="EPSG:5070").to_crs("EPSG:4326").iloc[0]
    rx0, ry0, rx1, ry1 = ring_wgs.bounds
    def is_marsh(a):
        a = (a or "").upper()
        return a.startswith("E2EM") or a.startswith("M2EM") or a.startswith("E1EM") or a.startswith("M1EM") or a.startswith("E2SS") or a.startswith("M2SS")
    feats, seen = [], set()
    MARSH_WHERE = ("ATTRIBUTE LIKE 'E2EM%' OR ATTRIBUTE LIKE 'M2EM%' OR ATTRIBUTE LIKE 'E1EM%' "
                   "OR ATTRIBUTE LIKE 'M1EM%' OR ATTRIBUTE LIKE 'E2SS%' OR ATTRIBUTE LIKE 'M2SS%'")
    tile = 0.25
    tx = rx0
    while tx < rx1:
        ty = ry0
        while ty < ry1:
            bb = (tx, ty, min(tx + tile, rx1), min(ty + tile, ry1))
            offset = 0
            while True:
                params = {"where": MARSH_WHERE, "geometry": f"{bb[0]},{bb[1]},{bb[2]},{bb[3]}",
                          "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
                          "spatialRel": "esriSpatialRelIntersects",
                          "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE,SYSTEM_NAME,CLASS_NAME",
                          "returnGeometry": "true", "f": "geojson",
                          "resultOffset": str(offset), "resultRecordCount": "2000",
                          "orderByFields": "OBJECTID"}
                url = SERVICE + "?" + urllib.parse.urlencode(params)
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    gj = json.load(r)
                got = gj.get("features", [])
                for f_ in got:
                    oid = (f_.get("properties") or {}).get("OBJECTID")
                    if oid in seen: continue
                    seen.add(oid); feats.append(f_)
                if len(got) < 2000 or not gj.get("exceededTransferLimit"): break
                offset += 2000
            print(f"  ring tile {bb}: cumulative {len(feats)}", flush=True)
            ty += tile
        tx += tile
    print(f"ring NWI query: {len(feats)} unique polys", flush=True)
    nwi = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326") if feats else gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    nwi = nwi[nwi["ATTRIBUTE"].apply(is_marsh)].copy() if len(nwi) else nwi
    nwi5070 = nwi.to_crs("EPSG:5070")
    # ring 2-10 km: buffer union 10km minus buffer 2km minus footprint
    ring = fp_union5070.buffer(10000).difference(fp_union5070.buffer(2000))
    ref = nwi5070[nwi5070.geometry.intersects(ring)].copy() if len(nwi5070) else nwi5070
    ref["geometry"] = ref.geometry.intersection(ring)
    ref = ref[ref.geometry.area > 100]
    print(f"reference candidate polys: {len(ref)}, area ha={ref.geometry.area.sum()/1e4:.1f}")
    # Cap reference area to ~3x footprint marsh area by nearest-to-path selection to bound grid
    fp_area = float(fp_marsh.to_crs('EPSG:5070').geometry.area.sum())
    if len(ref):
        ref["dist"] = ref.geometry.distance(fp_union5070)
        ref = ref.sort_values("dist")
        cum = ref.geometry.area.cumsum()
        cap = max(fp_area * 3, 300 * 1e4)  # at least 300 ha of reference marsh
        keep = ref[(cum - ref.geometry.area < cap) | (ref.index.isin(ref.index[:8]))]
        ref = keep if len(keep) else ref.head(20)
    ref_wgs = ref.to_crs("EPSG:4326")
    ref_wgs.to_file(DATA / f"reference_{storm}.geojson", driver="GeoJSON")
    fp_marsh.to_file(DATA / f"footprint_{storm}.geojson", driver="GeoJSON")
    print(f"footprint marsh ha={fp_area/1e4:.2f}, reference marsh ha={ref.geometry.area.sum()/1e4:.2f} ({len(ref)} polys)")

    # Study extent: union bounds of fp + ref, in WGS; grid 30 m approx: use degrees grid aligned to HLS via 0.00027 deg (~30m) - simpler: build UTM grid
    union_wgs = pd.concat([fp_marsh, ref_wgs]) if len(ref_wgs) else fp_marsh
    minx, miny, maxx, maxy = union_wgs.total_bounds
    # Pad small
    minx -= 0.005; miny -= 0.005; maxx += 0.005; maxy += 0.005
    # UTM zone from centroid
    cx = (minx + maxx) / 2
    utm_epsg = 32600 + int((cx + 180) // 6) + 1
    from rasterio.warp import transform_bounds as tb
    ux0, uy0, ux1, uy1 = tb("EPSG:4326", f"EPSG:{utm_epsg}", minx, miny, maxx, maxy)
    res = 30.0
    W = int(math.ceil((ux1 - ux0) / res)); H = int(math.ceil((uy1 - uy0) / res))
    print(f"grid UTM{utm_epsg} {W}x{H} = {W*H/1e6:.2f} Mpix")
    if W * H > 60_000_000:
        return {"storm": storm, "status": "grid_too_large", "W": W, "H": H}
    transform_utm = from_bounds(ux0, uy0, ux1, uy1, W, H)
    # zone masks in UTM
    fp_utm = fp_marsh.to_crs(f"EPSG:{utm_epsg}")
    ref_utm = ref_wgs.to_crs(f"EPSG:{utm_epsg}")
    fp_mask = rasterize([(g, 1) for g in fp_utm.geometry], out_shape=(H, W), transform=transform_utm, fill=0, dtype="uint8").astype(bool)
    ref_mask = rasterize([(g, 1) for g in ref_utm.geometry], out_shape=(H, W), transform=transform_utm, fill=0, dtype="uint8").astype(bool)
    ref_mask = ref_mask & ~fp_mask
    print(f"fp pixels {fp_mask.sum()}, ref pixels {ref_mask.sum()}")
    # WGS bounds of UTM grid for STAC search
    wminx, wminy, wmaxx, wmaxy = tb(f"EPSG:{utm_epsg}", "EPSG:4326", ux0, uy0, ux1, uy1)
    bbox = [wminx, wminy, wmaxx, wmaxy]

    lf = datetime.fromisoformat(landfall)
    start = lf - timedelta(days=183); end = lf + timedelta(days=731)
    months = month_starts(start, end)
    rows = []
    mix = {"S30": 0, "L30": 0}
    pre_stack = []  # collect pre-storm NDVI for veg mask: use first 3 months composites
    monthly_ndvi = {}
    monthly_ndwi = {}
    for mi, ms in enumerate(months):
        me = (months[mi + 1] if mi + 1 < len(months) else ms + timedelta(days=31))
        rng = f"{ms.strftime('%Y-%m-%d')}/{me.strftime('%Y-%m-%d')}"
        items = []
        for coll in ["hls2-s30", "hls2-l30"]:
            try:
                s = cat.search(collections=[coll], bbox=bbox, datetime=rng, max_items=200)
                got = list(s.items())
                for it in got: it.properties["_coll"] = coll
                items.extend(got)
            except Exception as e:
                print(f"  search {coll} {rng} failed: {e}")
        # dedupe by datetime+collection tile id
        seen = set(); uniq = []
        for it in items:
            if it.id in seen: continue
            seen.add(it.id); uniq.append(it)
        items = uniq
        label = ms.strftime("%Y-%m")
        if not items:
            rows.append({"storm": storm, "month": label, "month_offset": round((ms - lf).days / 30.44, 2),
                         "footprint_ndvi": None, "reference_ndvi": None, "anomaly": None,
                         "footprint_n": 0, "reference_n": 0, "footprint_ndwi": None, "reference_ndwi": None,
                         "n_scenes": 0, "note": "no_scenes"})
            monthly_ndvi[label] = None; monthly_ndwi[label] = None
            print(f"  {label}: no scenes"); continue
        def process_scene(it):
            # HLS v2 asset names: B04 red, B8A (S30) / B05 (L30) NIR, B03 green, Fmask
            coll = it.properties.get("_coll", "")
            is_s30 = "s30" in it.id.lower() or coll == "hls2-s30"
            nir_key = "B8A" if is_s30 else "B05"
            signed = planetary_computer.sign(it)
            def href(k): return signed.assets[k].href if k in signed.assets else None
            if not all([href("B04"), href(nir_key), href("Fmask"), href("B03")]):
                return None
            def rd(k):
                with rasterio.open(href(k)) as src:
                    from rasterio.vrt import WarpedVRT
                    with WarpedVRT(src, crs=f"EPSG:{utm_epsg}", transform=transform_utm, width=W, height=H,
                                   resampling=rasterio.enums.Resampling.nearest) as vrt:
                        return vrt.read(1).astype(np.float32)
            red = rd("B04"); nir = rd(nir_key); grn = rd("B03"); fm = rd("Fmask").astype(np.int32)
            # Fmask bits: 0 cirrus,1 cloud,2 adj cloud,3 cloud shadow,4 snow,5 water.
            # Mask cirrus/cloud/adjacent/shadow/snow. Water bit left in; the pre-storm
            # vegetated mask (NDVI above 0.2) is the open water exclusion.
            bad = ((fm & 1) != 0) | ((fm & 2) != 0) | ((fm & 4) != 0) | ((fm & 8) != 0) | ((fm & 16) != 0)
            valid = (~bad) & (red > 0) & (nir > 0)
            ndvi = np.where(valid & ((nir + red) != 0), (nir - red) / (nir + red + 1e-9), np.nan).astype(np.float32)
            ndwi = np.where(valid & ((grn + nir) != 0), (grn - nir) / (grn + nir + 1e-9), np.nan).astype(np.float32)
            return ndvi, ndwi, is_s30
        ndvi_stack, ndwi_stack = [], []
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(process_scene, it): it for it in items}
            for fut, it in futs.items():
                try:
                    r = fut.result()
                except Exception as e:
                    print(f"    scene {it.id} failed: {e}"); continue
                if r is None: continue
                ndvi_stack.append(r[0]); ndwi_stack.append(r[1])
                mix["S30" if r[2] else "L30"] += 1
        if not ndvi_stack:
            rows.append({"storm": storm, "month": label, "month_offset": round((ms - lf).days / 30.44, 2),
                         "footprint_ndvi": None, "reference_ndvi": None, "anomaly": None,
                         "footprint_n": 0, "reference_n": 0, "footprint_ndwi": None, "reference_ndwi": None,
                         "n_scenes": 0, "note": "all_scenes_failed"})
            monthly_ndvi[label] = None; monthly_ndwi[label] = None
            print(f"  {label}: all scenes failed"); continue
        with np.errstate(all="ignore"):
            comp_ndvi = np.nanmedian(np.stack(ndvi_stack), axis=0)
            comp_ndwi = np.nanmedian(np.stack(ndwi_stack), axis=0)
        monthly_ndvi[label] = comp_ndvi; monthly_ndwi[label] = comp_ndwi
        rows.append({"_label": label, "_pending": True, "n_scenes": len(ndvi_stack)})
        print(f"  {label}: {len(ndvi_stack)} scenes composited", flush=True)
    # Vegetated mask from pre-storm composites (months with offset < 0)
    pre = [monthly_ndvi[r["_label"]] for r in rows if r.get("_pending") and monthly_ndvi.get(r["_label"]) is not None and datetime.fromisoformat(r["_label"] + "-01") < lf]
    if pre:
        with np.errstate(all="ignore"):
            pre_med = np.nanmedian(np.stack(pre), axis=0)
        veg = pre_med > 0.2
    else:
        veg = np.ones_like(fp_mask, dtype=bool)
        print("  WARNING: no pre-storm composite; veg mask = all")
    print(f"  veg pixels: fp {(fp_mask & veg).sum()}, ref {(ref_mask & veg).sum()}")
    out_rows = []
    for r in rows:
        if not r.get("_pending"):
            out_rows.append({k: v for k, v in r.items() if not k.startswith("_")}); continue
        label = r["_label"]; comp = monthly_ndvi[label]; compw = monthly_ndwi[label]
        fmask = fp_mask & veg; rmask = ref_mask & veg
        fv = comp[fmask]; rv = comp[rmask]
        fv = fv[np.isfinite(fv)]; rv = rv[np.isfinite(rv)]
        fw = compw[fmask]; rw = compw[rmask]
        fw = fw[np.isfinite(fw)]; rw = rw[np.isfinite(rw)]
        f_mean = float(np.mean(fv)) if len(fv) >= 10 else None
        r_mean = float(np.mean(rv)) if len(rv) >= 10 else None
        anom = (f_mean - r_mean) if (f_mean is not None and r_mean is not None) else None
        ms = datetime.fromisoformat(label + "-01")
        out_rows.append({"storm": storm, "month": label, "month_offset": round((ms - lf).days / 30.44, 2),
                         "footprint_ndvi": f_mean, "reference_ndvi": r_mean, "anomaly": anom,
                         "footprint_n": int(len(fv)), "reference_n": int(len(rv)),
                         "footprint_ndwi": float(np.mean(fw)) if len(fw) else None,
                         "reference_ndwi": float(np.mean(rw)) if len(rw) else None,
                         "n_scenes": r["n_scenes"], "note": "" if anom is not None else "insufficient_clear_pixels"})
    # Summary stats
    s = pd.DataFrame(out_rows)
    post = s[(s["month_offset"] >= 0) & (s["month_offset"] <= 1.5) & s["anomaly"].notna()]
    immediate = float(post.iloc[0]["anomaly"]) if len(post) else None
    immediate_month = str(post.iloc[0]["month"]) if len(post) else None
    rec = s[(s["month_offset"] >= 2) & (s["month_offset"] <= 18) & s["anomaly"].notna()]
    slope = r2 = None; n = len(rec)
    if n >= 4:
        x = rec["month_offset"].values; y = rec["anomaly"].values
        A = np.polyfit(x, y, 1); slope = float(A[0])
        pred = np.polyval(A, x); ss = 1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12); r2 = float(ss)
    gaps = [str(r["month"]) for r in out_rows if r["anomaly"] is None]
    summ = {"storm": storm, "landfall": landfall, **cluster_info, "immediate_anomaly": immediate, "immediate_month": immediate_month,
            "recovery_slope_per_month": slope, "recovery_r2": r2, "recovery_n_months": int(n),
            "sensor_mix_scenes": mix, "cloud_gap_months": gaps,
            "footprint_marsh_ha": round(fp_area / 1e4, 3), "reference_marsh_ha": round(float(ref.geometry.area.sum()) / 1e4, 3),
            "grid_pixels_fp_veg": int((fp_mask & veg).sum()), "grid_pixels_ref_veg": int((ref_mask & veg).sum())}
    print(json.dumps(summ, indent=2))
    return summ, out_rows

def main():
    import sys
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    cat = pystac_client.Client.open(CAT)
    overlap = json.loads((RESULTS / "step2_overlap.json").read_text())
    all_rows, summaries = [], {}
    for storm in ["ida", "ian", "helene", "milton"]:
        if only and storm not in only: continue
        o = overlap.get(storm, {})
        if o.get("marsh_ha_in_paths", 0) < 1.0:
            summaries[storm] = {"storm": storm, "status": "dropped_insufficient_marsh", "marsh_ha": o.get("marsh_ha_in_paths")}
            print(f"{storm}: dropped, marsh {o.get('marsh_ha_in_paths')} ha"); continue
        try:
            res = process_storm(cat, storm, LAND[storm])
            if isinstance(res, tuple):
                summaries[storm], rows = res; all_rows.extend(rows)
                pd.DataFrame(rows).to_csv(RESULTS / f"trajectories_{storm}.csv", index=False)
                (RESULTS / f"summary_{storm}.json").write_text(json.dumps({storm: summaries[storm]}, indent=2))
                print(f"checkpoint written for {storm}", flush=True)
            else:
                summaries[storm] = res
        except Exception as e:
            import traceback; traceback.print_exc()
            summaries[storm] = {"storm": storm, "status": f"failed: {e}"}
    # Checkpoint merge: combine any per-storm files present (including from
    # earlier partial runs) so a killed run never loses finished storms.
    merged_rows, merged_summ = [], {}
    for storm in ["ida", "ian", "helene", "milton"]:
        pf = RESULTS / f"trajectories_{storm}.csv"
        sf = RESULTS / f"summary_{storm}.json"
        if pf.exists():
            merged_rows.extend(pd.read_csv(pf).to_dict("records"))
        if sf.exists():
            merged_summ.update(json.loads(sf.read_text()))
    merged_summ.update(summaries)
    if merged_rows:
        pd.DataFrame(merged_rows).to_csv(RESULTS / "marsh_trajectories.csv", index=False)
    (RESULTS / "marsh_summary.json").write_text(json.dumps(merged_summ, indent=2))
    print("STEP3 DONE")

if __name__ == "__main__":
    main()
