#!/usr/bin/env python3
"""Ida marsh placebo test (design and amendment logged in
BUILD_LOG.md, 2026-11-07, before this script was run).

Pseudo-footprints in the untouched reference marsh: 200 draws, each
a spatially coherent patch of 716 vegetated reference pixels (a
random seed pixel plus its 715 nearest vegetated neighbours, UTM
Euclidean), scored with the pipeline's own swing arithmetic
(September 2021 footprint-minus-reference NDVI anomaly minus the
February to August 2021 mean anomaly). The observed Ida swing is
-0.0736 (trajectory table: -0.0386 minus +0.0350).

Pixel values are the pipeline's own arrays (results/pixels_ida.npz;
footprint block = rows 0..716, reference block = rows 717..7306,
the split verified exactly against the pipeline's vegetated pixel
counts). Coordinates for patch coherence
come from a grid rebuilt with the same construction as
code/step3c_points.py build_zones (copied here in build_zones_local
to avoid that module's Earth Engine import), paired to npz
reference rows by scan-order rank, per the logged amendment: the
pipeline's exact grid could not be reproduced because
step3c_points.py was edited after the extraction run (rebuild:
723/6,585 points vs the pipeline's 716/6,591). Value-side checks
run before any draw: the step3e vegetation mask recomputed from
the npz returns exactly 6,508 vegetated reference pixels, and
monthly reference zone means recomputed from the npz reproduce
results/trajectories_ida.csv.

Seed: numpy default_rng(20261107). Outputs:
results/placebo_ida.json and results/placebo_ida_swings.csv.
"""
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio.features
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"

LANDFALL = pd.Timestamp("2021-08-29")
N_DRAWS = 200
SEED = 20261107
PATCH_N = 716
N_FP_ROWS = 717          # npz footprint block (717 points, 716 of
                         # them vegetated; split verified exactly
                         # against the pipeline's vegetated counts)
MONTHS = [f"2021-{m:02d}" for m in range(2, 10)]  # Feb..Sep 2021


def build_zones_local(fp_path, ref_path, step_m=30.0):
    """Same construction as step3c_points.py build_zones, minus the
    Earth Engine scene counting. Returns reference-zone pixel
    coordinates only (the placebo does not use the footprint)."""
    fp = gpd.read_file(fp_path)
    ref = gpd.read_file(ref_path)
    allg = pd.concat([fp.geometry, ref.geometry])
    minx, miny, maxx, maxy = allg.total_bounds
    pad = 0.005
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    clon = (minx + maxx) / 2.0
    epsg = 32600 + int((clon + 180) // 6) + 1
    fpu = fp.to_crs(epsg)
    refu = ref.to_crs(epsg)
    (ux0, uy0, ux1, uy1) = (
        gpd.GeoSeries(allg, crs=4326).to_crs(epsg).total_bounds)
    xs = np.arange(ux0, ux1 + step_m, step_m)
    ys = np.arange(uy0, uy1 + step_m, step_m)
    W, H = len(xs), len(ys)
    transform = rasterio.transform.from_origin(xs[0], ys[-1], step_m,
                                               step_m)
    fp_r = rasterio.features.rasterize(
        [(g, 1) for g in fpu.geometry], out_shape=(H, W),
        transform=transform, all_touched=False).astype(bool)
    ref_r = rasterio.features.rasterize(
        [(g, 1) for g in refu.geometry], out_shape=(H, W),
        transform=transform, all_touched=False).astype(bool)
    yy, xx = np.mgrid[0:H, 0:W]
    px = xs[xx]
    py = ys[H - 1 - yy]
    fp_m = fp_r.ravel()
    ref_m = ref_r.ravel() & ~fp_m
    coords = np.column_stack([px.ravel(), py.ravel()])
    return coords[fp_m], coords[ref_m], epsg


def main():
    fp_xy, ref_xy, epsg = build_zones_local(
        DATA / "footprint_ida.geojson", DATA / "reference_ida.geojson")
    print(f"rebuilt grid EPSG:{epsg}: footprint {len(fp_xy)}, "
          f"reference {len(ref_xy)} (pipeline: 716 / 6591; see the "
          f"logged amendment)")

    z = np.load(RESULTS / "pixels_ida.npz")
    months_all = sorted({k.split("__")[0] for k in z.files})
    ndvi = {m: z[f"{m}__ndvi"].astype(float) for m in months_all}
    n_rows = len(ndvi[months_all[0]])
    assert n_rows == 7307, n_rows
    pre_all = [m for m in months_all
               if pd.Timestamp(m + "-01") < LANDFALL]

    ref_block = slice(N_FP_ROWS, None)
    stack = np.vstack([ndvi[m][ref_block] for m in pre_all])
    ref_veg = np.nanmedian(stack, axis=0) > 0.2   # step3e rule
    fp_stack = np.vstack([ndvi[m][:N_FP_ROWS] for m in pre_all])
    fp_veg = np.nanmedian(fp_stack, axis=0) > 0.2
    print(f"vegetated pixels from npz: footprint "
          f"{int(fp_veg.sum())}, reference {int(ref_veg.sum())}")
    assert int(fp_veg.sum()) == 716 and int(ref_veg.sum()) == 6508

    def zone_mean(arr, rows):
        v = arr[rows]
        v = v[np.isfinite(v)]
        return float(v.mean()) if len(v) else np.nan

    ref_veg_rows = N_FP_ROWS + np.where(ref_veg)[0]
    fp_veg_rows = np.where(fp_veg)[0]
    traj = pd.read_csv(RESULTS / "trajectories_ida.csv")
    for m in MONTHS:
        got_r = zone_mean(ndvi[m], ref_veg_rows)
        exp_r = float(traj.loc[traj["month"] == m,
                               "reference_ndvi"].iloc[0])
        got_f = zone_mean(ndvi[m], fp_veg_rows)
        exp_f = float(traj.loc[traj["month"] == m,
                               "footprint_ndvi"].iloc[0])
        assert abs(got_r - exp_r) < 1e-9 and abs(got_f - exp_f) < 1e-9, (
            m, got_f, exp_f, got_r, exp_r)
    print("verification: npz blocks + step3e mask reproduce "
          "trajectories_ida.csv footprint and reference means "
          "exactly, Feb-Sep 2021")

    row = traj[traj["month"] == "2021-09"].iloc[0]
    pre_mean = float(traj[traj["month_offset"] < 0]["anomaly"].mean())
    observed = float(row["anomaly"] - pre_mean)
    print(f"observed swing: {observed:.4f} "
          f"(Sep anomaly {row['anomaly']:.4f} - pre mean {pre_mean:.4f})")

    # Pair rebuilt reference coordinates to npz reference rows by
    # scan-order rank; candidate patch pixels are the paired rows
    # whose npz vegetation flag is set.
    n_pair = min(len(ref_xy), 6590)
    pair_veg = ref_veg[:n_pair]
    cand_xy = ref_xy[:n_pair][pair_veg]
    cand_rows = N_FP_ROWS + np.where(pair_veg)[0]
    print(f"patch candidates: {len(cand_rows)} paired vegetated "
          f"reference pixels")
    tree = cKDTree(cand_xy)
    rng = np.random.default_rng(SEED)

    swings = []
    for d in range(N_DRAWS):
        seed_i = int(rng.integers(0, len(cand_rows)))
        _, nn = tree.query(cand_xy[seed_i], k=PATCH_N)
        patch_rows = cand_rows[np.sort(nn)]
        rest_rows = np.setdiff1d(ref_veg_rows, patch_rows,
                                 assume_unique=False)
        anoms = []
        for m in MONTHS:
            a = zone_mean(ndvi[m], patch_rows)
            b = zone_mean(ndvi[m], rest_rows)
            anoms.append(a - b)
        swings.append(anoms[-1] - float(np.mean(anoms[:-1])))
    swings = np.array(swings)

    out = {
        "design": "200 coherent pseudo-footprint patches of 716 "
                  "vegetated pixels in the untouched reference marsh; "
                  "pipeline npz pixel values; coordinates from the "
                  "rebuilt grid paired by scan-order rank (logged "
                  "amendment); seed numpy default_rng(20261107); "
                  "estimand identical to the pipeline swing",
        "n_draws": N_DRAWS,
        "seed": SEED,
        "observed_swing": observed,
        "placebo_median": float(np.median(swings)),
        "placebo_q1": float(np.percentile(swings, 25)),
        "placebo_q3": float(np.percentile(swings, 75)),
        "placebo_p2_5": float(np.percentile(swings, 2.5)),
        "placebo_p97_5": float(np.percentile(swings, 97.5)),
        "placebo_min": float(swings.min()),
        "placebo_max": float(swings.max()),
        "share_at_or_below_observed": float((swings <= observed).mean()),
        "observed_percentile": float((swings < observed).mean() * 100.0),
        "clears_placebo_at_5pct": bool((swings <= observed).mean() < 0.05),
    }
    (RESULTS / "placebo_ida.json").write_text(json.dumps(out, indent=1))
    pd.DataFrame({"draw": np.arange(N_DRAWS),
                  "swing": swings}).to_csv(
        RESULTS / "placebo_ida_swings.csv", index=False)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
