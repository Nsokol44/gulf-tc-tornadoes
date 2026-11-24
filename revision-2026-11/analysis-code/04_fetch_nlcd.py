"""04_fetch_nlcd.py

Build every sampled tornado's footprint (paper Section 2.4: SPC start-to-end
segment buffered by half the recorded width, EPSG:5070) and download NLCD
2021 land cover for exactly the areas the footprints touch, via the MRLC
WCS (the classic CONUS zip endpoint is retired: HTTP 404 on 2026-11-23).

Vintage decision (documented per author's currency instruction): MRLC's WCS
serves NLCD 2021 Land Cover L48 as its newest epoch land-cover coverage;
the Annual NLCD product line is served there only as 1985-2023 change
summary products, not land-cover rasters. NLCD 2021 uses the same class
codes the design groups, so it is used here and the vintage is logged.

Tiles are requested on the native NLCD grid (origin -2493045, 3310005;
30 m pixels, EPSG:5070) over 1x1-degree blocks intersected by footprints,
expanded by 3 km, and stored as individual tiles in data/nlcd_tiles/
(05_landcover.py reads them on the shared grid; no single mosaic is built
because the union rectangle is ~8 Gpx).
"""
import json
import subprocess
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import LineString, Point, box

HERE = Path(__file__).resolve().parent.parent
DATA, RESULTS = HERE / "data", HERE / "results"
TILES = DATA / "nlcd_tiles"
TILES.mkdir(parents=True, exist_ok=True)

WCS = "https://www.mrlc.gov/geoserver/mrlc_download/wcs"
COVERAGE = "mrlc_download__NLCD_2021_Land_Cover_L48"
GRID_X0, GRID_Y0, RES = -2493045.0, 3310005.0, 30.0


def build_footprints(sample: pd.DataFrame) -> gpd.GeoDataFrame:
    geoms = []
    for r in sample.itertuples():
        if r.slat == r.elat and r.slon == r.elon:
            # Zero-length path (point tornado): the buffered segment is a disc.
            geoms.append(Point(r.slon, r.slat))
        else:
            geoms.append(LineString([(r.slon, r.slat), (r.elon, r.elat)]))
    g = gpd.GeoDataFrame(sample[["tornado_id", "yr", "era", "coast", "storm_id", "wid_m"]].copy(),
                         geometry=geoms, crs=4326).to_crs(5070)
    # Flat caps for segments (as step1_paths); point paths take round caps
    # (a flat-cap buffer of a point is empty in GEOS/shapely 2.x).
    g["geometry"] = [geom.buffer(w / 2.0, cap_style=2) if geom.geom_type == "LineString"
                     else geom.buffer(w / 2.0)
                     for geom, w in zip(g.geometry, g["wid_m"])]
    g["footprint_area_ha"] = g.geometry.area / 1e4
    return g


def snap_out(minv, maxv, origin, res, axis):
    if axis == "x":
        lo = origin + np.floor((minv - origin) / res) * res
        hi = origin + np.ceil((maxv - origin) / res) * res
    else:  # y origin is the TOP edge; grid runs downward, same arithmetic works
        lo = origin + np.floor((minv - origin) / res) * res
        hi = origin + np.ceil((maxv - origin) / res) * res
    return lo, hi


def tile_valid(path: Path) -> bool:
    """A tile counts as valid only if its full band reads back: WCS downloads
    have twice arrived truncated in ways a header check cannot see."""
    if not path.exists() or path.stat().st_size <= 10000:
        return False
    try:
        with rasterio.open(path) as ds:
            if ds.width == 0 or ds.height == 0:
                return False
            arr = ds.read(1)
            return arr.size > 0
    except Exception:
        return False


def main():
    sample = pd.read_parquet(RESULTS / "sample_two_coast.parquet")
    foot = build_footprints(sample)
    foot.to_parquet(DATA / "footprints.parquet")
    print(f"footprints: {len(foot)}, total area {foot['footprint_area_ha'].sum():.1f} ha")

    # 1x1-degree blocks (lon/lat) intersected by any footprint bounding box.
    fb = foot.to_crs(4326)
    blocks = set()
    for minx, miny, maxx, maxy in fb.geometry.bounds.itertuples(index=False):
        for bx in range(int(np.floor(minx)), int(np.ceil(maxx))):
            for by in range(int(np.floor(miny)), int(np.ceil(maxy))):
                blocks.add((bx, by))
    blocks = sorted(blocks)
    print(f"1-degree blocks to fetch: {len(blocks)}")

    tile_log = []
    for i, (bx, by) in enumerate(blocks):
        blk = gpd.GeoDataFrame(geometry=[box(bx, by, bx + 1, by + 1)], crs=4326).to_crs(5070)
        minx, miny, maxx, maxy = blk.geometry.total_bounds
        minx, maxx = snap_out(minx - 3000, maxx + 3000, GRID_X0, RES, "x")
        miny, maxy = snap_out(miny - 3000, maxy + 3000, GRID_Y0, RES, "y")
        out = TILES / f"nlcd_{bx}_{by}.tif"
        if tile_valid(out):
            tile_log.append(dict(block=[bx, by], file=out.name, cached=True))
            continue
        if out.exists():
            out.unlink()  # stale or corrupt partial download
        url = (f"{WCS}?service=WCS&version=2.0.1&request=GetCoverage"
               f"&coverageId={COVERAGE}"
               f"&subset=X({minx:.0f},{maxx:.0f})&subset=Y({miny:.0f},{maxy:.0f})"
               f"&format=image/tiff")
        for attempt in range(3):
            r = subprocess.run(["curl", "-s", "-A", "Mozilla/5.0 research",
                                "-o", str(out), url], capture_output=True)
            if tile_valid(out):
                break
            if out.exists():
                out.unlink()
            time.sleep(5 * (attempt + 1))
        ok = tile_valid(out)
        tile_log.append(dict(block=[bx, by], file=out.name, bytes=out.stat().st_size if out.exists() else 0, ok=bool(ok)))
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(blocks)} blocks fetched")

    ok_tiles = [t for t in tile_log if t.get("ok") or t.get("cached")]
    print(f"tiles ok: {len(ok_tiles)}/{len(blocks)}")
    # NOTE: no single mosaic is built. The union rectangle of all blocks is
    # ~8 Gpx, which exceeds this machine's memory in rasterio.merge; the
    # tiles are the stored product and 05_landcover.py reads them on the
    # shared NLCD grid (identical pixels; overlaps agree exactly).
    index = {}
    for t in ok_tiles:
        with rasterio.open(TILES / t["file"]) as ds:
            index[t["file"]] = dict(bounds=list(ds.bounds),
                                    transform=list(ds.transform),
                                    width=ds.width, height=ds.height,
                                    crs=str(ds.crs), nodata=ds.nodata)
    with open(DATA / "nlcd_tile_index.json", "w") as f:
        json.dump(index, f, indent=2)
    classes = set()
    for t in ok_tiles[:12]:
        with rasterio.open(TILES / t["file"]) as ds:
            classes.update(np.unique(ds.read(1)).tolist())
    print(f"tile index written for {len(index)} tiles; classes in first 12 tiles: {sorted(classes)}")

    prov_path = DATA / "PROVENANCE.json"
    prov = json.loads(prov_path.read_text())
    prov["sources"]["nlcd"] = {
        "product": "NLCD 2021 Land Cover L48 (MRLC), via MRLC WCS GetCoverage",
        "coverage_id": COVERAGE, "download_date": "2026-11-23",
        "note": ("Classic CONUS zip URL retired (HTTP 404, checked 2026-11-23). "
                 "Annual NLCD land-cover rasters are not served by the MRLC WCS "
                 "(only 1985-2023 change summaries); NLCD 2021 is the newest epoch "
                 "land-cover coverage served and uses the grouped class codes."),
        "tiles": len(tile_log), "storage": "per-block tiles in data/nlcd_tiles/ "
        "(no single mosaic: the union rectangle is ~8 Gpx; 05_landcover.py "
        "reads the tiles on the shared NLCD grid)",
    }
    prov_path.write_text(json.dumps(prov, indent=2))
    with open(DATA / "nlcd_tile_log.json", "w") as f:
        json.dump(tile_log, f, indent=2)


if __name__ == "__main__":
    main()
