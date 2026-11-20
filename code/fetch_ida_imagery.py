"""Fetch HLS S30 monthly median composites for the Ida marsh footprint.

Same data source and composite definition as the trajectory analysis
(code/step3c_points.py): Harmonized Landsat and Sentinel-2 version 2.0,
Sentinel-2 (S30) collection on the Microsoft Planetary Computer, monthly
median of Fmask-clear scenes. Two composites are built per footprint
group on EPSG:5070 30 m grids: August 2021 (the pre-landfall month;
landfall 29 August 2021) and September 2021 (the first monthly
composite beginning after landfall, the composite that carries the
reported -0.039 anomaly).

The footprint's 18 polygons form three alongshore groups (Pearl River
mouth in the west, a middle group, and a Bay St. Louis group in the
east). Composites are built per group window rather than over the
full 55 km span because the shared VM cannot hold the full-span stack
in memory (a full-span attempt on 2026-11-06 was OOM-killed); the
west window uses the figure margins, the other two a small margin,
and footprint statistics are accumulated exactly across groups.

Outputs: results/hls_ida_<group>_aug2021.tif and _sep2021.tif
(bands B02, B03, B04, B8A, float32 surface reflectance), and
results/hls_ida_scenes.json (scene provenance plus footprint checks).
"""
import gc
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import planetary_computer
import rasterio
from pystac_client import Client
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.features import geometry_mask
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RES = ROOT / "results"
RES_M = 30.0
BANDS = ["B02", "B03", "B04", "B8A"]
MONTHS = {"aug2021": ("2021-08-01", "2021-08-31"),
          "sep2021": ("2021-09-01", "2021-09-30")}
CRS5070 = CRS.from_epsg(5070)
TO_LL = Transformer.from_crs(5070, 4326, always_xy=True)

CATALOG = Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")


def snap(x0, y0, x1, y1):
    return (np.floor(x0 / RES_M) * RES_M, np.floor(y0 / RES_M) * RES_M,
            np.ceil(x1 / RES_M) * RES_M, np.ceil(y1 / RES_M) * RES_M)


def search_items(win, d0, d1):
    x0, y0, x1, y1 = win
    corners = [TO_LL.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    bbox = [min(c[0] for c in corners) - 0.02,
            min(c[1] for c in corners) - 0.02,
            max(c[0] for c in corners) + 0.02,
            max(c[1] for c in corners) + 0.02]
    search = CATALOG.search(collections=["hls2-s30"], bbox=bbox,
                            datetime=f"{d0}T00:00:00Z/{d1}T23:59:59Z")
    return sorted(search.items(), key=lambda i: i.datetime)


def item_rec(it, **extra):
    rec = {"id": it.id, "datetime": str(it.datetime),
           "tile": it.properties.get("hls:tile_id")}
    rec.update(extra)
    return rec


def composite(win, items):
    """Monthly median composite over one window (EPSG:5070 bounds)."""
    x0, y0, x1, y1 = win
    W = int((x1 - x0) / RES_M)
    H = int((y1 - y0) / RES_M)
    transform = from_origin(x0, y1, RES_M, RES_M)
    print(f"  window {W}x{H}: {len(items)} S30 items", flush=True)
    stack = {b: [] for b in BANDS}
    used = []
    for it in items:
        try:
            def read(band):
                href = planetary_computer.sign(it.assets[band].href)
                with rasterio.open(href) as src:
                    with WarpedVRT(src, crs=CRS5070, transform=transform,
                                   width=W, height=H,
                                   resampling=Resampling.nearest) as vrt:
                        return vrt.read(1)
            fmask = read("Fmask")
            bad = (fmask & 0b011111) != 0  # cirrus, cloud, adjacent,
            #                                shadow, snow (bits 0 to 4)
            for b in BANDS:
                arr = read(b).astype(np.float32)
                arr[arr <= -9990] = np.nan
                arr[bad] = np.nan
                stack[b].append(arr)
            used.append(item_rec(it))
            print("    ok", it.id, flush=True)
        except Exception as e:  # noqa: BLE001
            print("    SKIP", it.id, type(e).__name__, str(e)[:120],
                  flush=True)
    out = np.full((len(BANDS), H, W), np.nan, dtype=np.float32)
    for i, b in enumerate(BANDS):
        with np.errstate(all="ignore"):
            out[i] = np.nanmedian(np.stack(stack[b]), axis=0) * 0.0001
        stack[b] = []
    del stack
    gc.collect()
    return out, transform, used


def main():
    foot = gpd.read_file(DATA / "footprint_ida.geojson")
    g = foot.copy()
    g["clon"] = g.geometry.centroid.x
    groups = {"west": g[g.clon < -89.75],
              "middle": g[(g.clon >= -89.75) & (g.clon < -89.45)],
              "east": g[g.clon >= -89.45]}
    margins = {"west": (2100.0, 2050.0), "middle": (500.0, 500.0),
               "east": (500.0, 500.0)}
    scenes = {k: {} for k in MONTHS}
    stats = {}
    tot = {"n": 0, "aug_sum": 0.0, "sep_sum": 0.0, "chg_sum": 0.0}
    for name, sub in groups.items():
        if not len(sub):
            continue
        sub_p = sub.to_crs(5070)
        mx, my = margins[name]
        b = sub_p.total_bounds
        win = snap(b[0] - mx, b[1] - my, b[2] + mx, b[3] + my)
        print(f"group {name}: {len(sub)} polygons, window {win}",
              flush=True)
        comps = {}
        for key, (d0, d1) in MONTHS.items():
            path = RES / f"hls_ida_{name}_{key}.tif"
            items = search_items(win, d0, d1)
            if path.exists():
                # Resume support: a composite written by an earlier
                # (killed) run is reused, not recomputed.
                with rasterio.open(path) as src:
                    arr = src.read()
                    transform = src.transform
                used = [item_rec(it, resumed_from_disk=True)
                        for it in items]
                print(f"  resumed {path.name} from disk "
                      f"({len(items)} searched items)", flush=True)
                for u in used:
                    scenes[key][u["id"]] = u
                comps[key] = (arr, transform)
                continue
            arr, transform, used = composite(win, items)
            for u in used:
                scenes[key][u["id"]] = u
            H, W = arr.shape[1], arr.shape[2]
            with rasterio.open(path, "w", driver="GTiff", dtype="float32",
                               count=len(BANDS), width=W, height=H,
                               crs=CRS5070, transform=transform,
                               nodata=float("nan")) as dst:
                dst.write(arr)
                for i, d in enumerate(
                        ["B02 blue", "B03 green", "B04 red", "B8A NIR"], 1):
                    dst.set_band_description(i, d)
            print("  wrote", path, flush=True)
            comps[key] = (arr, transform)
        (arr_a, tr_a), (arr_s, _) = comps["aug2021"], comps["sep2021"]
        nd_a = (arr_a[3] - arr_a[2]) / (arr_a[3] + arr_a[2])
        nd_s = (arr_s[3] - arr_s[2]) / (arr_s[3] + arr_s[2])
        H, W = nd_a.shape
        m = geometry_mask([s.__geo_interface__ for s in sub_p.geometry],
                          out_shape=(H, W), transform=tr_a, invert=True)
        veg = m & (nd_a > 0.2) & ~np.isnan(nd_a) & ~np.isnan(nd_s)
        n = int(veg.sum())
        st = {"polygons": int(len(sub)), "veg_pixels": n,
              "aug_ndvi": float(np.mean(nd_a[veg])),
              "sep_ndvi": float(np.mean(nd_s[veg])),
              "change": float(np.mean((nd_s - nd_a)[veg]))}
        stats[name] = st
        tot["n"] += n
        tot["aug_sum"] += st["aug_ndvi"] * n
        tot["sep_sum"] += st["sep_ndvi"] * n
        tot["chg_sum"] += st["change"] * n
        print("  stats", st, flush=True)
        del comps
        gc.collect()
    checks = {
        "footprint_veg_pixels": tot["n"],
        "aug2021_footprint_mean_ndvi": tot["aug_sum"] / tot["n"],
        "sep2021_footprint_mean_ndvi": tot["sep_sum"] / tot["n"],
        "mean_ndvi_change": tot["chg_sum"] / tot["n"],
        "groups": stats,
        "note": "S30-only raster monthly medians over footprint "
                "polygons; the analysis used S30+L30 point sampling, "
                "so values should be close to, not identical to, the "
                "reported 0.568 (Aug) and 0.487 (Sep).",
    }
    (RES / "hls_ida_scenes.json").write_text(json.dumps(
        {"scenes": {k: sorted(v.values(), key=lambda u: u["datetime"])
                    for k, v in scenes.items()},
         "checks": checks}, indent=2))
    print(json.dumps(checks, indent=2), flush=True)


if __name__ == "__main__":
    main()
