"""05_landcover.py

Classify every sampled tornado footprint against NLCD 2021 grouped classes
(author's design, Quiring's named fix):
  wetlands  = NLCD 90, 95
  developed = NLCD 21-24
  forest    = NLCD 41-43
  agriculture = NLCD 81, 82
  water     = NLCD 11
  other     = all remaining classes

Reads the per-block NLCD tiles written by 04_fetch_nlcd.py on their shared
native grid (origin -2493045, 3310005; 30 m; EPSG:5070). For each footprint
a window on the global grid is assembled from whichever tiles cover it
(overlaps carry identical pixels, so pasting is exact), the footprint is
rasterized into the window, and class pixels are counted.

Outputs:
- results/sample_with_landcover.parquet/csv : sample + per-class footprint
  area (ha) and intersection flags
- results/landcover_summary.csv : by pooled / coast / era / coast x era,
  (a) share of tornadoes whose footprint intersects each class at all,
  (b) share of total footprint area in each class.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from rasterio.features import rasterize

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
TILES = DATA / "nlcd_tiles"

GROUPS = {
    "wetlands": [90, 95],
    "developed": [21, 22, 23, 24],
    "forest": [41, 42, 43],
    "agriculture": [81, 82],
    "water": [11],
}
GROUP_NAMES = list(GROUPS.keys()) + ["other"]
PIXEL_HA = 0.09  # 30 m x 30 m
GRID_X0, GRID_Y0, RES = -2493045.0, 3310005.0, 30.0


def global_window(bounds):
    """Integer pixel window (col0, row0, width, height) on the NLCD grid."""
    minx, miny, maxx, maxy = bounds
    col0 = int(np.floor((minx - GRID_X0) / RES))
    col1 = int(np.ceil((maxx - GRID_X0) / RES))
    row0 = int(np.floor((GRID_Y0 - maxy) / RES))
    row1 = int(np.ceil((GRID_Y0 - miny) / RES))
    return col0, row0, col1 - col0, row1 - row0


def main():
    sample = pd.read_parquet(RESULTS / "sample_two_coast.parquet")
    foot = gpd.read_parquet(DATA / "footprints.parquet").set_index("tornado_id")
    index = json.loads((DATA / "nlcd_tile_index.json").read_text())
    tiles = {}
    for fname, meta in index.items():
        b = meta["bounds"]  # [left, bottom, right, top]
        tiles[fname] = dict(left=b[0], bottom=b[1], right=b[2], top=b[3],
                            nodata=meta["nodata"], path=TILES / fname)
    open_cache = {}

    def get_src(fname):
        if fname not in open_cache:
            open_cache[fname] = rasterio.open(tiles[fname]["path"])
        return open_cache[fname]

    records = []
    for tid, geom in foot.geometry.items():
        col0, row0, w, h = global_window(geom.bounds)
        arr = np.full((h, w), 255, dtype=np.uint8)  # 255 = no data sentinel
        win_transform = Affine(RES, 0, GRID_X0 + col0 * RES, 0, -RES, GRID_Y0 - row0 * RES)
        for fname, t in tiles.items():
            # tile pixel range on the global grid
            tc0 = int(round((t["left"] - GRID_X0) / RES))
            tr0 = int(round((GRID_Y0 - t["top"]) / RES))
            tc1 = int(round((t["right"] - GRID_X0) / RES))
            tr1 = int(round((GRID_Y0 - t["bottom"]) / RES))
            ic0, ir0 = max(col0, tc0), max(row0, tr0)
            ic1, ir1 = min(col0 + w, tc1), min(row0 + h, tr1)
            if ic1 <= ic0 or ir1 <= ir0:
                continue
            src = get_src(fname)
            tw = rasterio.windows.Window(ic0 - tc0, ir0 - tr0, ic1 - ic0, ir1 - ir0)
            sub = src.read(1, window=tw)
            if t["nodata"] is not None:
                sub = np.where(sub == t["nodata"], 255, sub)
            arr[ir0 - row0:ir1 - row0, ic0 - col0:ic1 - col0] = sub
        mask = rasterize([(geom, 1)], out_shape=arr.shape, transform=win_transform,
                         fill=0, dtype="uint8").astype(bool)
        vals = arr[mask]
        vals = vals[vals != 255]
        # Incidence ("intersects at all") uses an all-touched rasterization:
        # 228 footprints are smaller than one 30 m pixel and contain no pixel
        # centre, but they still intersect the classes of the pixels they touch.
        tmask = rasterize([(geom, 1)], out_shape=arr.shape, transform=win_transform,
                          fill=0, dtype="uint8", all_touched=True).astype(bool)
        tvals = arr[tmask]
        tvals = tvals[tvals != 255]
        rec = {"tornado_id": tid, "nlcd_pixels": int(len(vals))}
        assigned = np.zeros(len(vals), dtype=bool)
        for gname, codes in GROUPS.items():
            hit = np.isin(vals, codes)
            rec[f"area_{gname}_ha"] = round(float(hit.sum()) * PIXEL_HA, 3)
            rec[f"intersects_{gname}"] = bool(np.isin(tvals, codes).any())
            assigned |= hit
        rec["area_other_ha"] = round(float((~assigned).sum()) * PIXEL_HA, 3)
        rec["intersects_other"] = bool((~np.isin(tvals, sum(GROUPS.values(), []))).any()
                                       and len(tvals) > 0)
        records.append(rec)
    for src in open_cache.values():
        src.close()

    lc = pd.DataFrame(records)
    out = sample.merge(lc, on="tornado_id", how="left")
    out["footprint_area_ha"] = [foot.loc[t, "footprint_area_ha"] for t in out["tornado_id"]]
    out.to_parquet(RESULTS / "sample_with_landcover.parquet", index=False)
    out.to_csv(RESULTS / "sample_with_landcover.csv", index=False)

    rows = []
    scopes = [("pooled", None, None)]
    scopes += [("coast", c, None) for c in ["gulf", "atlantic"]]
    scopes += [("era", None, e) for e in ["study_1995_2015", "extension_2016_2023"]]
    scopes += [("coast_x_era", c, e) for c in ["gulf", "atlantic"]
               for e in ["study_1995_2015", "extension_2016_2023"]]
    for level, coast, era in scopes:
        sub = out
        if coast:
            sub = sub[sub["coast"] == coast]
        if era:
            sub = sub[sub["era"] == era]
        tot_area = sub[[f"area_{g}_ha" for g in GROUP_NAMES]].sum().sum()
        row = dict(level=level, coast=coast or "pooled", era=era or "all_1995_2023",
                   n_tornadoes=int(len(sub)), total_footprint_area_ha=round(float(tot_area), 1))
        for gname in GROUP_NAMES:
            row[f"intersect_{gname}_pct"] = round(100 * float(sub[f"intersects_{gname}"].mean()), 1)
            row[f"area_{gname}_pct"] = round(100 * float(sub[f"area_{gname}_ha"].sum()) / tot_area, 1) if tot_area else np.nan
        rows.append(row)
    summ = pd.DataFrame(rows)
    summ.to_csv(RESULTS / "landcover_summary.csv", index=False)
    print(summ.to_string(index=False))
    print("tornadoes with zero centre-rule NLCD pixels (sub-pixel footprints):",
          int((out["nlcd_pixels"].fillna(0) == 0).sum()))
    print("tornadoes intersecting no class at all (fully offshore / nodata):",
          int((~out[[f"intersects_{g}" for g in GROUP_NAMES]].any(axis=1)).sum()))


if __name__ == "__main__":
    main()
