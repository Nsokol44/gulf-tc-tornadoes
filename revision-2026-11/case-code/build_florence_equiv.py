#!/usr/bin/env python3
"""Florence (2018) HLS-equivalent trajectory build.

WHY THIS FILE EXISTS (documented deviation): the original pipeline's
route, HLS v2.0 collections hls2-s30 / hls2-l30 on the Microsoft
Planetary Computer, has a temporal extent beginning 2020-01-01 (checked
against the PC STAC collection metadata on 2026-11-24), so no HLS scene
exists on that route for Florence's 2018-2020 window. The authoritative
archive (NASA LP DAAC Earthdata Cloud) serves the same HLS v2.0
granules only behind an Earthdata login, which is not available in
this environment. Florence is therefore built from the same two
sensor families on the same platform (Planetary Computer), with every
other element of the original method unchanged:

  - Sentinel-2 L2A (sentinel-2-l2a): bands B03 (green), B04 (red),
    B8A (NIR, the same narrow NIR band HLS S30 uses). Cloud handling:
    the SCL scene-classification asset, masking cloud shadow (3),
    cloud medium/high probability (8, 9), cirrus (10) and snow (11),
    the SCL analogue of the HLS Fmask bits 0-4. Reflectance in the
    2018-2020 window carries no additive offset (the ESA radiometric
    offset arrived with processing baseline 04.00 in January 2022),
    so band ratios from the stored values equal reflectance ratios.
  - Landsat Collection 2 Level-2 (landsat-c2-l2): bands SR_B3
    (green), SR_B4 (red), SR_B5 (NIR), with the collection's published
    scale (0.0000275) and offset (-0.2) applied before ratios. Cloud
    handling: QA_PIXEL bits 1 (dilated cloud), 2 (cirrus), 3 (cloud),
    4 (cloud shadow), 5 (snow), the direct analogue of Fmask bits 0-4.

What is NOT identical to HLS: no BRDF normalisation, no spectral
bandpass adjustment between sensors, and Landsat C2's own atmospheric
correction rather than the HLS one. Monthly median compositing, the
-6/+24 month window, the 30 m point grid, the vegetated mask
(pre-storm median NDVI > 0.2), the NDVI/NDWI definitions, the anomaly,
the recovery slope, the companion scar share and the placebo protocol
are exactly those of build_cases.py / step3c_points.py, whose zone
construction this script reuses unchanged.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from rasterio.warp import transform as wtransform
from rasterio.warp import transform_bounds as tb
import planetary_computer
import pystac_client

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_cases as B

HERE = B.HERE
DATA, RESULTS = B.DATA, B.RESULTS
STORM = "florence"


def sample_s2(args):
    it, pts = args
    lons, lats = pts
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    if not all([href("B04"), href("B8A"), href("B03"), href("SCL")]):
        return None
    out = {}
    # The sentinel2l2a01 blob host's TLS chain is intercepted by this
    # environment's egress proxy (self-signed CA); GDAL must not verify.
    with rasterio.Env(GDAL_HTTP_UNSAFESSL="YES"):
        for key, name in [("B04", "red"), ("B8A", "nir"), ("B03", "grn"), ("SCL", "scl")]:
            with rasterio.open(href(key)) as src:
                xs, ys = wtransform("EPSG:4326", src.crs, list(lons), list(lats))
                out[name] = np.array([v[0] for v in src.sample(zip(xs, ys))], dtype=np.float64)
    red, nir, grn, scl = out["red"], out["nir"], out["grn"], out["scl"]
    bad = np.isin(scl, [3, 8, 9, 10, 11]) | np.isnan(scl)
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid, (nir - red) / (nir + red + 1e-9), np.nan)
    ndwi = np.where(valid & (grn > 0), (grn - nir) / (grn + nir + 1e-9), np.nan)
    return ndvi, ndwi, True


def sample_l2(args):
    it, pts = args
    lons, lats = pts
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    # Planetary Computer landsat-c2-l2 asset keys are the EO common
    # names (red = SR_B4, nir08 = SR_B5, green = SR_B3, qa_pixel).
    if not all([href("red"), href("nir08"), href("green"), href("qa_pixel")]):
        return None
    out = {}
    with rasterio.Env(GDAL_HTTP_UNSAFESSL="YES"):
        for key, name in [("red", "red"), ("nir08", "nir"), ("green", "grn"), ("qa_pixel", "qa")]:
            with rasterio.open(href(key)) as src:
                xs, ys = wtransform("EPSG:4326", src.crs, list(lons), list(lats))
                out[name] = np.array([v[0] for v in src.sample(zip(xs, ys))], dtype=np.float64)
    red = out["red"] * 0.0000275 - 0.2
    nir = out["nir"] * 0.0000275 - 0.2
    grn = out["grn"] * 0.0000275 - 0.2
    qa = np.nan_to_num(out["qa"], nan=65535).astype(int)
    bad = ((qa & 2) != 0) | ((qa & 4) != 0) | ((qa & 8) != 0) | ((qa & 16) != 0) | ((qa & 32) != 0)
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid, (nir - red) / (nir + red + 1e-9), np.nan)
    ndwi = np.where(valid & (grn > 0), (grn - nir) / (grn + nir + 1e-9), np.nan)
    return ndvi, ndwi, False


def main():
    tracks = B.parse_hurdat()
    spc = pd.read_csv(B.ORIG / "data/1950-2025_torn.csv", low_memory=False)
    spc["dt_naive"] = pd.to_datetime(spc["date"].astype(str) + " " + spc["time"].astype(str), errors="coerce")
    spc["wid_num"] = pd.to_numeric(spc["wid"], errors="coerce")
    med = spc.groupby((spc["yr"] // 10) * 10)["wid_num"].median()
    cfg = B.STORMS[STORM]
    paths, pinfo = B.build_paths(STORM, tracks, spc, float(med.loc[(cfg["year"] // 10) * 10] * 0.9144))
    marsh, cinfo = B.crossings(STORM, paths)
    fp_marsh, ref_wgs, cluster_info, fp_ha, ref_ha, n_cross = B.build_zones(STORM, paths, marsh)
    landfall_date = pinfo["landfall_utc"][:10]
    lf = datetime.fromisoformat(landfall_date)

    union_wgs = pd.concat([fp_marsh, ref_wgs])
    minx, miny, maxx, maxy = union_wgs.total_bounds
    minx -= 0.005; miny -= 0.005; maxx += 0.005; maxy += 0.005
    bbox = [minx, miny, maxx, maxy]
    cx = (minx + maxx) / 2
    utm_epsg = 32600 + int((cx + 180) // 6) + 1
    ux0, uy0, ux1, uy1 = tb("EPSG:4326", f"EPSG:{utm_epsg}", minx, miny, maxx, maxy)
    W = int(np.ceil((ux1 - ux0) / 30.0)); H = int(np.ceil((uy1 - uy0) / 30.0))
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
    print(f"florence equiv: points fp {len(rows_f)} ref {len(rows_r)} UTM{utm_epsg}", flush=True)

    cat = pystac_client.Client.open(B.CAT)
    months = B.month_starts(lf - timedelta(days=183), lf + timedelta(days=731))
    cache = RESULTS / "pixels_florence_equiv.npz"
    monthly_pix = {}
    if cache.exists():
        z = np.load(cache)
        monthly_pix = {k[:-6]: (z[k], z[k[:-6] + "__ndwi"]) for k in list(z.files) if k.endswith("__ndvi")}
        print(f"equiv cache {len(monthly_pix)} months", flush=True)
    mix = {"S30_equiv_S2": 0, "L30_equiv_LC2": 0}
    scene_counts = {}
    for mi, ms in enumerate(months):
        label = ms.strftime("%Y-%m")
        if label in monthly_pix:
            continue
        me = (months[mi + 1] if mi + 1 < len(months) else ms + timedelta(days=31))
        rng = f"{ms.strftime('%Y-%m-%d')}/{me.strftime('%Y-%m-%d')}"
        jobs = []
        for coll, fn in [("sentinel-2-l2a", sample_s2), ("landsat-c2-l2", sample_l2)]:
            try:
                s = cat.search(collections=[coll], bbox=bbox, datetime=rng, max_items=200)
                for it in s.items():
                    jobs.append((fn, it))
            except Exception as e:
                print(f"  search {coll} {rng} failed: {e}", flush=True)
        ndvi_list, ndwi_list = [], []
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fn, (it, (lons, lats))): it for fn, it in jobs}
            for fut, it in futs.items():
                try:
                    r = fut.result()
                except Exception as e:
                    print(f"    scene {it.id} failed: {type(e).__name__}: {e}", flush=True)
                    continue
                if r is None:
                    continue
                ndvi_list.append(r[0]); ndwi_list.append(r[1])
                mix["S30_equiv_S2" if r[2] else "L30_equiv_LC2"] += 1
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
        rec = {"storm": STORM, "month": label, "month_offset": round((ms - lf).days / 30.44, 2),
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
    sdf.to_csv(RESULTS / "trajectories_florence.csv", index=False)
    np.savez_compressed(RESULTS / "points_florence.npz", xy=xy, zone=zone, veg=veg, pre_med=pre_med,
                        lons=np.array(lons), lats=np.array(lats))
    extra = {**pinfo, **cinfo, **cluster_info, "footprint_marsh_ha_cluster": round(fp_ha, 3),
             "reference_marsh_ha": round(ref_ha, 3), "cluster_crossing_paths": n_cross,
             "sensor_mix_sampled_scenes": mix,
             "imagery_route": "HLS-EQUIVALENT: Planetary Computer sentinel-2-l2a + landsat-c2-l2 (PC hls2 archive starts 2020-01-01; LP DAAC HLS v2.0 requires Earthdata login). See build_florence_equiv.py header."}
    summ, _, _ = B.summarise(STORM, sdf, monthly_pix, zone, veg, xy, landfall_date, extra)
    swings = B.placebo(STORM, monthly_pix, zone, veg, xy, landfall_date, summ["immediate_month"], summ["veg_pixels_fp"])
    obs = summ["swing"]
    summ["placebo"] = {"n_draws": B.N_PLACEBOS, "seed": B.PLACEBO_SEED, "patch_n_pixels": summ["veg_pixels_fp"],
                       "observed_swing": obs, "median": float(np.median(swings)),
                       "q1": float(np.percentile(swings, 25)), "q3": float(np.percentile(swings, 75)),
                       "p2_5": float(np.percentile(swings, 2.5)), "p97_5": float(np.percentile(swings, 97.5)),
                       "min": float(swings.min()), "max": float(swings.max()),
                       "share_at_or_below_observed": float((swings <= obs).mean()),
                       "empirical_p_le_0.005_form": (1 + int((swings <= obs).sum())) / (B.N_PLACEBOS + 1),
                       "sd": float(swings.std(ddof=1)), "detectable_swing_95": float(np.percentile(swings, 2.5))}
    pd.DataFrame({"draw": np.arange(B.N_PLACEBOS), "swing": swings}).to_csv(RESULTS / "placebo_florence_swings.csv", index=False)
    (RESULTS / "summary_florence.json").write_text(json.dumps(summ, indent=2, default=str))
    print(json.dumps(summ, indent=2, default=str), flush=True)
    print("FLORENCE EQUIV DONE", flush=True)


if __name__ == "__main__":
    main()
