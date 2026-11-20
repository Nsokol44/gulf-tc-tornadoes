#!/usr/bin/env python3
"""Step 3 (point-sampling implementation): HLS NDVI/NDWI trajectories.

Why points: footprint plus reference zones hold only hundreds to thousands of
30 m pixels per storm. Sampling those pixels in each HLS scene (rasterio
sample, block reads) replaces full-tile monthly composites that were too
slow and memory heavy in step3_hls.py (kept in code/ for the record; its
runs were killed by the runtime before finishing any storm).

Zones are identical in definition to step3_hls.py: footprint equals NWI marsh
inside path buffers (largest 15 km cluster), reference equals NWI marsh in the
2 to 10 km ring around the marsh-crossing paths, capped at the larger of
3x footprint area or 300 ha, nearest first, minimum 8 polygons.
Monthly value per pixel is the median across clear scenes in the month;
zone value is the mean across vegetated pixels (pre-storm median NDVI
above 0.2). Checkpoint: each month is appended to
results/trajectories_<storm>_points.csv as it completes.
"""
import json, math, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.ops import unary_union
import rasterio
from rasterio.transform import from_bounds
from rasterio.features import rasterize
from rasterio.warp import transform as wtransform
import pystac_client, planetary_computer

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"; RESULTS = BASE / "results"
CAT = "https://planetarycomputer.microsoft.com/api/stac/v1"
_lf = json.loads((RESULTS / "step1_landfalls.json").read_text())["landfalls"]
LAND = {k.lower(): v["landfall_utc"][:10] for k, v in _lf.items() if v.get("landfall_utc")}
SERVICE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0/query"
MARSH_WHERE = ("ATTRIBUTE LIKE 'E2EM%' OR ATTRIBUTE LIKE 'M2EM%' OR ATTRIBUTE LIKE 'E1EM%' "
               "OR ATTRIBUTE LIKE 'M1EM%' OR ATTRIBUTE LIKE 'E2SS%' OR ATTRIBUTE LIKE 'M2SS%'")

def is_marsh(a):
    a = (a or "").upper()
    return a.startswith(("E2EM", "M2EM", "E1EM", "M1EM", "E2SS", "M2SS"))

def build_zones(storm):
    paths = gpd.read_file(DATA / f"paths_{storm}.geojson")
    fp_marsh_all = gpd.read_file(DATA / f"marsh_in_paths_{storm}.geojson")
    _fm = fp_marsh_all.to_crs("EPSG:5070")
    _union = unary_union(_fm.geometry.buffer(15000).values)
    _comps = list(_union.geoms) if _union.geom_type == "MultiPolygon" else [_union]
    assign = []
    for g_ in _fm.geometry:
        for ci, comp in enumerate(_comps):
            if g_.buffer(15000).intersects(comp):
                assign.append(ci); break
        else:
            assign.append(-1)
    _fm = _fm.assign(cluster=assign)
    areas = _fm.geometry.area.groupby(_fm["cluster"]).sum()
    best = int(areas.idxmax())
    cluster_info = {"n_clusters": int(len(areas)), "chosen_cluster_ha": round(float(areas.max()) / 1e4, 3),
                    "excluded_cluster_ha": round(float((areas.sum() - areas.max())) / 1e4, 3),
                    "total_marsh_ha": round(float(areas.sum()) / 1e4, 3)}
    fp_marsh = fp_marsh_all[_fm["cluster"].values == best].copy()
    paths5070 = paths.to_crs("EPSG:5070")
    marsh_union = unary_union(fp_marsh.to_crs("EPSG:5070").geometry.values)
    crossing = paths5070[paths5070.geometry.intersects(marsh_union)]
    fp_union5070 = unary_union(crossing.geometry.values)
    ring_tmp = fp_union5070.buffer(10000)
    ring_wgs = gpd.GeoSeries([ring_tmp], crs="EPSG:5070").to_crs("EPSG:4326").iloc[0]
    rx0, ry0, rx1, ry1 = ring_wgs.bounds
    feats, seen = [], set()
    tile = 0.25; tx = rx0
    while tx < rx1:
        ty = ry0
        while ty < ry1:
            bb = (tx, ty, min(tx + tile, rx1), min(ty + tile, ry1)); offset = 0
            while True:
                params = {"where": MARSH_WHERE, "geometry": f"{bb[0]},{bb[1]},{bb[2]},{bb[3]}",
                          "geometryType": "esriGeometryEnvelope", "inSR": "4326", "outSR": "4326",
                          "spatialRel": "esriSpatialRelIntersects",
                          "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE,SYSTEM_NAME,CLASS_NAME",
                          "returnGeometry": "true", "f": "geojson",
                          "resultOffset": str(offset), "resultRecordCount": "2000",
                          "orderByFields": "OBJECTID"}
                req = urllib.request.Request(SERVICE + "?" + urllib.parse.urlencode(params),
                                             headers={"User-Agent": "Mozilla/5.0 research"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    gj = json.load(r)
                got = gj.get("features", [])
                for f_ in got:
                    oid = (f_.get("properties") or {}).get("OBJECTID")
                    if oid in seen: continue
                    seen.add(oid); feats.append(f_)
                if len(got) < 2000 or not gj.get("exceededTransferLimit"): break
                offset += 2000
            ty += tile
        tx += tile
    nwi = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    nwi5070 = nwi.to_crs("EPSG:5070")
    ring = fp_union5070.buffer(10000).difference(fp_union5070.buffer(2000))
    ref = nwi5070[nwi5070.geometry.intersects(ring)].copy()
    ref["geometry"] = ref.geometry.intersection(ring)
    ref = ref[ref.geometry.area > 100]
    fp_area = float(fp_marsh.to_crs("EPSG:5070").geometry.area.sum())
    if len(ref):
        ref["dist"] = ref.geometry.distance(fp_union5070)
        ref = ref.sort_values("dist")
        cum = ref.geometry.area.cumsum()
        cap = max(fp_area * 3, 300 * 1e4)
        keep = ref[(cum - ref.geometry.area < cap) | (ref.index.isin(ref.index[:8]))]
        ref = keep if len(keep) else ref.head(20)
    ref_wgs = ref.to_crs("EPSG:4326")
    ref_wgs.to_file(DATA / f"reference_{storm}.geojson", driver="GeoJSON")
    fp_marsh.to_file(DATA / f"footprint_{storm}.geojson", driver="GeoJSON")
    print(f"zones: fp {fp_area/1e4:.2f} ha ({len(fp_marsh)} polys), ref {ref.geometry.area.sum()/1e4:.2f} ha ({len(ref)} polys), clusters {cluster_info}", flush=True)
    # 30 m grid over union bounds in local UTM
    union_wgs = pd.concat([fp_marsh, ref_wgs]) if len(ref_wgs) else fp_marsh
    minx, miny, maxx, maxy = union_wgs.total_bounds
    minx -= 0.005; miny -= 0.005; maxx += 0.005; maxy += 0.005
    cx = (minx + maxx) / 2
    utm_epsg = 32600 + int((cx + 180) // 6) + 1
    from rasterio.warp import transform_bounds as tb
    ux0, uy0, ux1, uy1 = tb("EPSG:4326", f"EPSG:{utm_epsg}", minx, miny, maxx, maxy)
    res = 30.0
    W = int(math.ceil((ux1 - ux0) / res)); H = int(math.ceil((uy1 - uy0) / res))
    tr = from_bounds(ux0, uy0, ux1, uy1, W, H)
    fp_utm = fp_marsh.to_crs(f"EPSG:{utm_epsg}"); ref_utm = ref_wgs.to_crs(f"EPSG:{utm_epsg}")
    fp_mask = rasterize([(g, 1) for g in fp_utm.geometry], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    ref_mask = rasterize([(g, 1) for g in ref_utm.geometry], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    ref_mask = ref_mask & ~fp_mask
    rows_f, cols_f = np.where(fp_mask); rows_r, cols_r = np.where(ref_mask)
    xs, ys = rasterio.transform.xy(tr, np.concatenate([rows_f, rows_r]), np.concatenate([cols_f, cols_r]))
    xs = np.array(xs); ys = np.array(ys)
    lons, lats = wtransform(f"EPSG:{utm_epsg}", "EPSG:4326", list(xs), list(ys))
    zone = np.array(["footprint"] * len(rows_f) + ["reference"] * len(rows_r))
    print(f"points: footprint {len(rows_f)}, reference {len(rows_r)}, grid {W}x{H} UTM{utm_epsg}", flush=True)
    return np.array(lons), np.array(lats), zone, cluster_info, fp_area / 1e4, float(ref.geometry.area.sum()) / 1e4, [minx, miny, maxx, maxy]

def month_starts(d0, d1):
    out = []; y, m = d0.year, d0.month
    while (y, m) <= (d1.year, d1.month):
        out.append(datetime(y, m, 1)); m += 1
        if m == 13: y, m = y + 1, 1
    return out

def sample_scene(args):
    it, pts = args
    lons, lats = pts
    coll = it.properties.get("_coll", "")
    is_s30 = "s30" in it.id.lower() or coll == "hls2-s30"
    nir_key = "B8A" if is_s30 else "B05"
    signed = planetary_computer.sign(it)
    def href(k): return signed.assets[k].href if k in signed.assets else None
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

def main():
    storms = sys.argv[1:] if len(sys.argv) > 1 else ["ida", "helene", "milton"]
    cat = pystac_client.Client.open(CAT)
    overlap = json.loads((RESULTS / "step2_overlap.json").read_text())
    for storm in storms:
        o = overlap.get(storm, {})
        if o.get("marsh_ha_in_paths", 0) < 1.0:
            (RESULTS / f"summary_{storm}.json").write_text(json.dumps({storm: {"storm": storm, "status": "dropped_insufficient_marsh", "marsh_ha": o.get("marsh_ha_in_paths")}}, indent=2))
            print(f"{storm}: dropped, marsh {o.get('marsh_ha_in_paths')} ha", flush=True); continue
        landfall = LAND[storm]; lf = datetime.fromisoformat(landfall)
        print(f"\n===== {storm} landfall {landfall} =====", flush=True)
        lons, lats, zone, cluster_info, fp_ha, ref_ha, bbox = build_zones(storm)
        pts = (lons, lats)
        ckpt = RESULTS / f"trajectories_{storm}_points.csv"
        done_months = set()
        if ckpt.exists():
            done_months = set(pd.read_csv(ckpt)["month"].astype(str))
            print(f"resuming: {len(done_months)} months already done", flush=True)
        months = month_starts(lf - timedelta(days=183), lf + timedelta(days=731))
        # First pass: gather per-month per-pixel values, checkpointing zone stats per month.
        # Pixel-level monthly medians are recomputed in a second lightweight pass from a
        # cached npz so the veg mask can be applied without re-sampling.
        cache = RESULTS / f"pixels_{storm}.npz"
        monthly_pix = {}
        if cache.exists():
            z = np.load(cache)
            monthly_pix = {}
            for k in list(z.files):
                if k.endswith("__ndvi"):
                    lab = k[: -len("__ndvi")]
                    monthly_pix[lab] = (z[k], z[lab + "__ndwi"])
            print(f"pixel cache loaded: {len(monthly_pix)} months", flush=True)
        mix = {"S30": 0, "L30": 0}
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
                    for it in got: it.properties["_coll"] = coll
                    items.extend(got)
                except Exception as e:
                    print(f"  search {coll} {rng} failed: {e}", flush=True)
            seen = set(); uniq = []
            for it in items:
                if it.id in seen: continue
                seen.add(it.id); uniq.append(it)
            items = uniq
            if not items:
                monthly_pix[label] = (np.full(len(lons), np.nan), np.full(len(lons), np.nan))
                print(f"  {label}: no scenes", flush=True); continue
            ndvi_list, ndwi_list = [], []
            with ThreadPoolExecutor(max_workers=8) as ex:
                futs = {ex.submit(sample_scene, (it, pts)): it for it in items}
                for fut, it in futs.items():
                    try:
                        r = fut.result()
                    except Exception as e:
                        print(f"    scene {it.id} failed: {type(e).__name__}: {e}", flush=True); continue
                    if r is None: continue
                    ndvi_list.append(r[0]); ndwi_list.append(r[1]); mix["S30" if r[2] else "L30"] += 1
            if ndvi_list:
                with np.errstate(all="ignore"):
                    monthly_pix[label] = (np.nanmedian(np.stack(ndvi_list), axis=0), np.nanmedian(np.stack(ndwi_list), axis=0))
            else:
                monthly_pix[label] = (np.full(len(lons), np.nan), np.full(len(lons), np.nan))
            np.savez_compressed(cache, **{f"{k}__ndvi": v[0] for k, v in monthly_pix.items()},
                                **{f"{k}__ndwi": v[1] for k, v in monthly_pix.items()})
            print(f"  {label}: {len(ndvi_list)} scenes sampled", flush=True)
        # Veg mask from pre-storm months
        pre = [monthly_pix[m][0] for m in monthly_pix if datetime.fromisoformat(m + "-01") < lf]
        with np.errstate(all="ignore"):
            pre_med = np.nanmedian(np.stack(pre), axis=0) if pre else np.full(len(lons), np.nan)
        veg = pre_med > 0.2
        print(f"veg pixels: footprint {int((veg & (zone=='footprint')).sum())}, reference {int((veg & (zone=='reference')).sum())}", flush=True)
        rows = []
        for ms in months:
            label = ms.strftime("%Y-%m")
            ndvi_p, ndwi_p = monthly_pix.get(label, (np.full(len(lons), np.nan), np.full(len(lons), np.nan)))
            rec = {"storm": storm, "month": label, "month_offset": round((ms - lf).days / 30.44, 2)}
            for zname, zkey in [("footprint", "footprint"), ("reference", "reference")]:
                m_ = veg & (zone == zname)
                fv = ndvi_p[m_]; fv = fv[np.isfinite(fv)]
                fw = ndwi_p[m_]; fw = fw[np.isfinite(fw)]
                rec[f"{zkey}_ndvi"] = float(np.mean(fv)) if len(fv) >= 10 else None
                rec[f"{zkey}_n"] = int(len(fv))
                rec[f"{zkey}_ndwi"] = float(np.mean(fw)) if len(fw) else None
            rec["anomaly"] = (rec["footprint_ndvi"] - rec["reference_ndvi"]) if (rec["footprint_ndvi"] is not None and rec["reference_ndvi"] is not None) else None
            rec["n_scenes"] = None
            rec["note"] = "" if rec["anomaly"] is not None else "insufficient_clear_pixels_or_no_scenes"
            rows.append(rec)
        sdf = pd.DataFrame(rows)
        sdf.to_csv(RESULTS / f"trajectories_{storm}.csv", index=False)
        post = sdf[(sdf["month_offset"] >= 0) & (sdf["month_offset"] <= 1.5) & sdf["anomaly"].notna()]
        rec_df = sdf[(sdf["month_offset"] >= 2) & (sdf["month_offset"] <= 18) & sdf["anomaly"].notna()]
        slope = r2 = None
        if len(rec_df) >= 4:
            x = rec_df["month_offset"].values; y = rec_df["anomaly"].values
            A = np.polyfit(x, y, 1); slope = float(A[0])
            pred = np.polyval(A, x); r2 = float(1 - ((y - pred) ** 2).sum() / max(((y - y.mean()) ** 2).sum(), 1e-12))
        summ = {"storm": storm, "landfall": landfall, **cluster_info,
                "immediate_anomaly": float(post.iloc[0]["anomaly"]) if len(post) else None,
                "immediate_month": str(post.iloc[0]["month"]) if len(post) else None,
                "recovery_slope_per_month": slope, "recovery_r2": r2, "recovery_n_months": int(len(rec_df)),
                "sensor_mix_note": "per-scene mix counted during sampling; see storm log",
                "cloud_gap_months": [str(r["month"]) for r in rows if r["anomaly"] is None],
                "footprint_marsh_ha_cluster": round(fp_ha, 3), "reference_marsh_ha": round(ref_ha, 3),
                "veg_pixels_fp": int((veg & (zone == "footprint")).sum()), "veg_pixels_ref": int((veg & (zone == "reference")).sum()),
                "method": "point sampling at 30 m zone pixels, monthly median per pixel, zone mean; step3c_points.py"}
        (RESULTS / f"summary_{storm}.json").write_text(json.dumps({storm: summ}, indent=2))
        print(json.dumps(summ, indent=2), flush=True)
    # Merge
    merged_rows, merged_summ = [], {}
    for storm in ["ida", "ian", "helene", "milton"]:
        pf = RESULTS / f"trajectories_{storm}.csv"; sf = RESULTS / f"summary_{storm}.json"
        if pf.exists(): merged_rows.extend(pd.read_csv(pf).to_dict("records"))
        if sf.exists(): merged_summ.update(json.loads(sf.read_text()))
    if merged_rows: pd.DataFrame(merged_rows).to_csv(RESULTS / "marsh_trajectories.csv", index=False)
    (RESULTS / "marsh_summary.json").write_text(json.dumps(merged_summ, indent=2))
    print("STEP3C DONE", flush=True)

if __name__ == "__main__":
    main()
