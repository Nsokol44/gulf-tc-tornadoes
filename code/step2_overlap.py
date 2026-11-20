#!/usr/bin/env python3
"""Step 2: Wetland overlap. Tries NWI via ArcGIS REST (Wetlands service)
queried by bbox after documenting state-download attempt. Classifies marsh
(E2EM/M2EM etc). Computes per-storm marsh ha inside footprints + paths crossing.
Also pulls ESA WorldCover marsh as cross-check/fallback record.
Outputs results/step2_overlap.json and data/marsh_<storm>.geojson (footprint marsh),
data/refzones etc handled in step3.
"""
import json, math, time, urllib.request, urllib.parse
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"; RESULTS = BASE / "results"

# NWI Wetlands Mapper ArcGIS REST - USFWS Wetlands service layer
# Known service: https://fwshqservices.fws.gov/arcgis/rest/services/NWI/Wetlands/MapServer/0 (Wetlands polygons)
SERVICE = "https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0/query"

def query_nwi(bbox, max_records=2000):
    """bbox (minx,miny,maxx,maxy) EPSG:4326. Paginate."""
    all_feats = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "outSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OBJECTID,ATTRIBUTE,WETLAND_TYPE,SYSTEM_NAME,CLASS_NAME",
            "returnGeometry": "true", "f": "geojson",
            "resultOffset": str(offset), "resultRecordCount": str(max_records),
            "orderByFields": "OBJECTID",
        }
        url = SERVICE + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
        with urllib.request.urlopen(req, timeout=180) as r:
            gj = json.load(r)
        feats = gj.get("features", [])
        all_feats.extend(feats)
        print(f"  offset {offset}: +{len(feats)} (total {len(all_feats)}) exceeded={gj.get('exceededTransferLimit')}")
        if len(feats) < max_records or not gj.get("exceededTransferLimit"):
            break
        offset += max_records
        time.sleep(1)
    return all_feats

def is_marsh(attr):
    a = (attr or "").upper()
    # Estuarine/marine emergent: E2EM, M2EM plus E2SS? Task: E2EM, M2EM and related.
    # Marsh stratum = emergent wetland in estuarine/marine systems + palustrine emergent in coastal context kept separate flag.
    if a.startswith("E2EM") or a.startswith("M2EM") or a.startswith("E1EM") or a.startswith("M1EM"):
        return "marsh_emergent_salt"
    if a.startswith("E2SS") or a.startswith("M2SS"):
        return "scrub_shrub_salt"
    if a.startswith("PEM") or a.startswith("PSS") or a.startswith("PFO"):
        return "fresh_wetland"
    if "FO" in a[1:4] or a.startswith("E2FO") or a.startswith("M2FO"):
        return "woody"
    return "other"

def main():
    storms = ["ida", "ian", "helene", "milton"]
    summary = {}
    for s in storms:
        pf = DATA / f"paths_{s}.geojson"
        if not pf.exists():
            print(f"{s}: no paths file, skip"); summary[s] = {"error": "no paths"}; continue
        paths = gpd.read_file(pf)
        paths5070 = paths.to_crs("EPSG:5070")
        total_fp_ha = float(paths5070.geometry.area.sum()) / 1e4
        # Per-path bbox queries (storm path sets span whole regions, e.g. Ida LA to NJ,
        # so a single bbox query is infeasible). Each path bbox padded 0.03 deg.
        minx, miny, maxx, maxy = paths.total_bounds
        bbox = (minx - 0.05, miny - 0.05, maxx + 0.05, maxy + 0.05)
        print(f"\n=== {s}: {len(paths)} paths, footprint {total_fp_ha:.1f} ha, overall bounds {bbox}")
        feats = []
        seen_ids = set()
        for i, row in paths.iterrows():
            pm = row.geometry.bounds
            pb = (pm[0] - 0.03, pm[1] - 0.03, pm[2] + 0.03, pm[3] + 0.03)
            try:
                got = query_nwi(pb)
            except Exception as e:
                print(f"  path {i} query failed: {e}"); continue
            for f_ in got:
                oid = (f_.get("properties") or {}).get("OBJECTID") or f_.get("id")
                if oid in seen_ids: continue
                seen_ids.add(oid); feats.append(f_)
            print(f"  path {i}: cumulative unique NWI polys {len(feats)}")
        if feats:
            nwi = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
        else:
            nwi = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
        print(f"  NWI polygons in bbox: {len(nwi)}")
        nwi.to_file(DATA / f"nwi_bbox_{s}.geojson", driver="GeoJSON") if len(nwi) else None
        if len(nwi) == 0:
            summary[s] = {"n_paths": int(len(paths)), "footprint_ha": total_fp_ha, "nwi_polys": 0, "marsh_ha_in_paths": 0.0, "paths_crossing_marsh": 0}
            continue
        nwi["stratum"] = nwi["ATTRIBUTE"].apply(is_marsh) if "ATTRIBUTE" in nwi.columns else "unknown"
        print(nwi["stratum"].value_counts().to_string())
        nwi5070 = nwi.to_crs("EPSG:5070")
        marsh = nwi5070[nwi5070["stratum"].isin(["marsh_emergent_salt", "scrub_shrub_salt"])].copy()
        woody = nwi5070[nwi5070["stratum"] == "woody"].copy()
        # intersection with dissolved footprint for area; per-path for crossing count
        from shapely.ops import unary_union
        fp_union = unary_union(paths5070.geometry.values)
        if len(marsh):
            inter = marsh.geometry.intersection(fp_union)
            marsh_ha = float(inter.area.sum()) / 1e4
            marsh_gdf = gpd.GeoDataFrame(geometry=inter[inter.area > 0], crs="EPSG:5070").to_crs("EPSG:4326")
            marsh_gdf.to_file(DATA / f"marsh_in_paths_{s}.geojson", driver="GeoJSON")
            crossing = 0
            for geom in paths5070.geometry:
                if marsh.geometry.intersects(geom).any():
                    # verify actual intersection area > 1 m2 for at least one
                    if (marsh.geometry.intersection(geom).area > 1).any():
                        crossing += 1
        else:
            marsh_ha, crossing = 0.0, 0
        woody_ha = float(woody.geometry.intersection(fp_union).area.sum()) / 1e4 if len(woody) else 0.0
        summary[s] = {"n_paths": int(len(paths)), "footprint_ha": round(total_fp_ha, 2),
                      "nwi_polys_bbox": int(len(nwi)), "marsh_ha_in_paths": round(marsh_ha, 3),
                      "woody_ha_in_paths": round(woody_ha, 3), "paths_crossing_marsh": int(crossing),
                      "bbox": [float(x) for x in bbox]}
        print(f"  -> marsh {marsh_ha:.2f} ha, woody {woody_ha:.2f} ha, crossing {crossing}/{len(paths)}")
    (RESULTS / "step2_overlap.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print("STEP2 DONE")

if __name__ == "__main__":
    main()
