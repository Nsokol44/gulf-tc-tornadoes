#!/usr/bin/env python3
"""Figure 5 data build: monthly median NDVI composites for the five
TC-tornado marsh cases, on per-storm windows around the analysed
footprint marsh.

Retrieval approach is reused exactly from the case analyses:
  - HLS storms (Ida, Idalia, Helene, Milton): Planetary Computer
    hls2-s30 + hls2-l30, assets B04 (red), B8A (S30) / B05 (L30) NIR,
    Fmask bits 0-4 masked (cirrus, cloud, adjacent cloud, cloud
    shadow, snow), NDVI = (NIR - Red) / (NIR + Red), monthly median
    of clear scenes (code/step3_hls.py, code/fetch_ida_imagery.py,
    analysis/cases_idalia_florence/code/build_cases.py).
  - Florence 2018 (HLS-equivalent): the PC hls2 archive begins in
    2020, so as in build_florence_equiv.py the same sensor families
    are taken from sentinel-2-l2a (B04 red, B8A NIR, SCL classes
    3, 8, 9, 10, 11 masked) and landsat-c2-l2 (assets red / nir08,
    scale 0.0000275, offset -0.2, QA_PIXEL bits 1-5 masked).

Grids: EPSG:5070, 30 m, one window per storm shared by both months.
Windows: footprint bounding box expanded by 1.75 km per side. For
Helene and Milton the footprint polygons are elongated / split along
the shore, so the window is centred on the dominant sub-cluster
(polygons within 3.5 km of the largest polygon), expanded by at
least 1.75 km per side and to at least 4 km in each dimension:
  - Helene: the footprint file holds two sub-groups ~18 km apart
    (3.30 ha north, 2.68 ha south); the window covers the northern
    (larger) sub-group.
  - Milton: one 30.35 ha polygon plus 1.79 ha ~2.8 km north are in
    the window; a 0.10 ha sliver ~5.4 km north is outside it.

Outputs (figures_src/imagery_cache/):
  <storm>_<yyyymm>_ndvi.tif  float32 NDVI composite, NaN nodata
  fig5_provenance.json       windows, scene counts, sensor mix,
                             clear-pixel fractions over the footprint
"""
import gc
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import planetary_computer
import rasterio
from pystac_client import Client
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

REV = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / "imagery_cache"
CACHE.mkdir(parents=True, exist_ok=True)
ORIG = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes"
CASES = REV / "analysis/cases_idalia_florence/data"
CRS5070 = CRS.from_epsg(5070)
RES = 30.0
CATALOG = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")

# storm: (footprint file, [(label, y, m) pre, (label, y, m) impact], route, focus)
STORMS = {
    "ida": (ORIG / "data/footprint_ida.geojson",
            [("202108", 2021, 8), ("202109", 2021, 9)], "hls", False),
    "idalia": (CASES / "footprint_idalia.geojson",
               [("202308", 2023, 8), ("202309", 2023, 9)], "hls", False),
    "florence": (CASES / "footprint_florence.geojson",
                 [("201809", 2018, 9), ("201810", 2018, 10)], "equiv", False),
    "helene": (ORIG / "data/footprint_helene.geojson",
               [("202409", 2024, 9), ("202410", 2024, 10)], "hls", True),
    "milton": (ORIG / "data/footprint_milton.geojson",
               [("202410", 2024, 10), ("202411", 2024, 11)], "hls", True),
}
MARGIN = 1750.0


def snap(v0, v1):
    return np.floor(v0 / RES) * RES, np.ceil(v1 / RES) * RES


def window_for(fp_path, focus):
    """Return (window bounds in EPSG:5070, footprint GeoDataFrame 5070,
    windowed-footprint GeoDataFrame 5070)."""
    fp = gpd.read_file(fp_path).to_crs(5070)
    sel = fp
    if focus:
        areas = fp.geometry.area
        big = fp.loc[areas.idxmax()].geometry
        bc = big.centroid
        sel = fp[fp.geometry.centroid.distance(bc) <= 3500.0]
    b = sel.total_bounds
    x0, x1 = snap(b[0] - MARGIN, b[2] + MARGIN)
    y0, y1 = snap(b[1] - MARGIN, b[3] + MARGIN)
    # at least 4 km in each dimension (Helene minimum-window rule)
    if x1 - x0 < 4000:
        c = (x0 + x1) / 2
        x0, x1 = snap(c - 2000, c + 2000)
    if y1 - y0 < 4000:
        c = (y0 + y1) / 2
        y0, y1 = snap(c - 2000, c + 2000)
    return (x0, y0, x1, y1), fp, sel


def grid_of(win):
    x0, y0, x1, y1 = win
    W = int(round((x1 - x0) / RES))
    H = int(round((y1 - y0) / RES))
    return W, H, from_origin(x0, y1, RES, RES)


def search(colls, win, y, m):
    x0, y0, x1, y1 = win
    lon0, lat0, lon1, lat1 = transform_bounds(CRS5070, "EPSG:4326",
                                              x0, y0, x1, y1)
    bbox = [lon0 - 0.02, lat0 - 0.02, lon1 + 0.02, lat1 + 0.02]
    d0 = f"{y:04d}-{m:02d}-01"
    d1 = f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01"
    items = []
    for coll in colls:
        s = CATALOG.search(collections=[coll], bbox=bbox,
                           datetime=f"{d0}/{d1}", max_items=200)
        got = list(s.items())
        for it in got:
            it.properties["_coll"] = coll
        items.extend(got)
    seen, uniq = set(), []
    for it in items:
        if it.id not in seen:
            seen.add(it.id)
            uniq.append(it)
    return uniq


def read_grid(href, transform, W, H, unsafe_ssl=False):
    ctx = rasterio.Env(GDAL_HTTP_UNSAFESSL="YES") if unsafe_ssl \
        else rasterio.Env()
    with ctx:
        with rasterio.open(href) as src:
            with WarpedVRT(src, crs=CRS5070, transform=transform,
                           width=W, height=H,
                           resampling=Resampling.nearest) as vrt:
                return vrt.read(1)


def hls_scene_ndvi(it, transform, W, H):
    coll = it.properties.get("_coll", "")
    is_s30 = "s30" in it.id.lower() or coll == "hls2-s30"
    nir_key = "B8A" if is_s30 else "B05"
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    if not all([href("B04"), href(nir_key), href("Fmask")]):
        return None
    fm = read_grid(href("Fmask"), transform, W, H).astype(np.int32)
    red = read_grid(href("B04"), transform, W, H).astype(np.float32)
    nir = read_grid(href(nir_key), transform, W, H).astype(np.float32)
    bad = (fm & 0b011111) != 0  # Fmask bits 0-4, as in fetch_ida_imagery.py
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid & ((nir + red) != 0),
                    (nir - red) / (nir + red + 1e-9), np.nan)
    return ndvi.astype(np.float32), ("S30" if is_s30 else "L30")


def s2_scene_ndvi(it, transform, W, H):
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    if not all([href("B04"), href("B8A"), href("SCL")]):
        return None
    scl = read_grid(href("SCL"), transform, W, H, unsafe_ssl=True)
    red = read_grid(href("B04"), transform, W, H,
                    unsafe_ssl=True).astype(np.float32)
    nir = read_grid(href("B8A"), transform, W, H,
                    unsafe_ssl=True).astype(np.float32)
    bad = np.isin(scl, [3, 8, 9, 10, 11])
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid & ((nir + red) != 0),
                    (nir - red) / (nir + red + 1e-9), np.nan)
    return ndvi.astype(np.float32), "S2"


def l2_scene_ndvi(it, transform, W, H):
    signed = planetary_computer.sign(it)

    def href(k):
        return signed.assets[k].href if k in signed.assets else None

    # PC landsat-c2-l2 asset keys are the EO common names (as in
    # build_florence_equiv.py): red = SR_B4, nir08 = SR_B5.
    if not all([href("red"), href("nir08"), href("qa_pixel")]):
        return None
    qa = read_grid(href("qa_pixel"), transform, W, H,
                   unsafe_ssl=True).astype(np.int32)
    red = read_grid(href("red"), transform, W, H,
                    unsafe_ssl=True).astype(np.float32) * 0.0000275 - 0.2
    nir = read_grid(href("nir08"), transform, W, H,
                    unsafe_ssl=True).astype(np.float32) * 0.0000275 - 0.2
    bad = ((qa & 2) != 0) | ((qa & 4) != 0) | ((qa & 8) != 0) \
        | ((qa & 16) != 0) | ((qa & 32) != 0)  # QA_PIXEL bits 1-5
    valid = (~bad) & (red > 0) & (nir > 0)
    ndvi = np.where(valid & ((nir + red) != 0),
                    (nir - red) / (nir + red + 1e-9), np.nan)
    return ndvi.astype(np.float32), "LC2"


def composite(items, fn, transform, W, H):
    stack, used = [], []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fn, it, transform, W, H): it for it in items}
        for fut, it in futs.items():
            try:
                r = fut.result()
            except Exception as e:  # noqa: BLE001
                print(f"    SKIP {it.id}: {type(e).__name__} "
                      f"{str(e)[:100]}", flush=True)
                continue
            if r is None:
                print(f"    SKIP {it.id}: missing assets", flush=True)
                continue
            stack.append(r[0])
            used.append({"id": it.id, "sensor": r[1],
                         "collection": it.properties.get("_coll", "")})
            print(f"    ok {it.id} [{r[1]}]", flush=True)
    if not stack:
        return None, used
    with np.errstate(all="ignore"):
        comp = np.nanmedian(np.stack(stack), axis=0)
    del stack
    gc.collect()
    return comp.astype(np.float32), used


def main():
    only = sys.argv[1:] or list(STORMS)
    prov_path = CACHE / "fig5_provenance.json"
    prov = json.loads(prov_path.read_text()) if prov_path.exists() else {}
    for storm in only:
        fp_path, months, route, focus = STORMS[storm]
        win, fp_all, fp_sel = window_for(fp_path, focus)
        W, H, transform = grid_of(win)
        fp_mask = rasterize(
            [(g, 1) for g in fp_sel.geometry], out_shape=(H, W),
            transform=transform, fill=0, dtype="uint8").astype(bool)
        rec = {"window_5070": [float(v) for v in win],
               "grid": [W, H], "route": route,
               "footprint_ha_total": float(fp_all.geometry.area.sum() / 1e4),
               "footprint_ha_in_window_polys":
                   float(fp_sel.geometry.area.sum() / 1e4),
               "footprint_pixels_in_window": int(fp_mask.sum()),
               "months": {}}
        print(f"\n== {storm}: window {win} grid {W}x{H} "
              f"fp pixels {fp_mask.sum()}", flush=True)
        for label, y, m in months:
            out_path = CACHE / f"{storm}_{label}_ndvi.tif"
            if out_path.exists() and prov.get(storm, {}).get(
                    "months", {}).get(label):
                print(f"  {label}: cached, skipping", flush=True)
                rec["months"][label] = prov[storm]["months"][label]
                continue
            if route == "hls":
                items = search(["hls2-s30", "hls2-l30"], win, y, m)
                fn = hls_scene_ndvi
            else:
                items = (search(["sentinel-2-l2a"], win, y, m)
                         + search(["landsat-c2-l2"], win, y, m))
                fn = None  # dispatched per item below
            print(f"  {label}: {len(items)} items found", flush=True)
            if route == "equiv":
                def fn(it, tr, w, h, _items=items):
                    coll = it.properties.get("_coll", "")
                    if coll == "sentinel-2-l2a":
                        return s2_scene_ndvi(it, tr, w, h)
                    return l2_scene_ndvi(it, tr, w, h)
            comp, used = composite(items, fn, transform, W, H)
            if comp is None:
                rec["months"][label] = {"n_scenes": 0, "scenes": [],
                                        "clear_frac_footprint": None}
                print(f"  {label}: NO composite", flush=True)
                continue
            with rasterio.open(out_path, "w", driver="GTiff",
                               dtype="float32", count=1, width=W,
                               height=H, crs=CRS5070,
                               transform=transform,
                               nodata=float("nan")) as dst:
                dst.write(comp, 1)
            finite_fp = np.isfinite(comp[fp_mask])
            clear = float(finite_fp.mean()) if fp_mask.sum() else None
            from collections import Counter
            mix = dict(Counter(u["sensor"] for u in used))
            rec["months"][label] = {
                "n_scenes": len(used), "sensor_mix": mix,
                "clear_frac_footprint": clear,
                "clear_frac_window": float(np.isfinite(comp).mean()),
                "scenes": used}
            print(f"  {label}: {len(used)} scenes {mix}, "
                  f"clear over footprint {clear}", flush=True)
            del comp
            gc.collect()
        prov[storm] = rec
        prov_path.write_text(json.dumps(prov, indent=2))
    print("\nDATA BUILD DONE", flush=True)


if __name__ == "__main__":
    main()
