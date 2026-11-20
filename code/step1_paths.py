#!/usr/bin/env python3
"""Step 1: Download HURDAT2 + SPC tornado CSV, find Gulf landfalls,
filter tornadoes -24h to +72h around landfall, build buffered path segments.
Real data only. Outputs data/hurdat2.txt, data/spc_torn.csv,
data/paths_<storm>.geojson, results/step1_landfalls.json
"""
import json, math, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"; RESULTS = BASE / "results"
DATA.mkdir(parents=True, exist_ok=True); RESULTS.mkdir(parents=True, exist_ok=True)

STORMS = {"Ida": "AL092021", "Ian": "AL092022", "Helene": "AL092024", "Milton": "AL142024"}

def download(url, dest):
    if dest.exists() and dest.stat().st_size > 10000:
        print(f"exists {dest} {dest.stat().st_size}")
        return dest
    print(f"downloading {url} -> {dest}")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk: break
            f.write(chunk)
    print(f"done {dest.stat().st_size}")
    return dest

# HURDAT2 candidates (latest first)
hurdat_urls = [
    "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt",
    "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-091226.txt",
    "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-02272026.txt",
    "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2024-040425.txt",
]
hurdat_path = DATA / "hurdat2.txt"
hurdat_used = None
if not hurdat_path.exists():
    for u in hurdat_urls:
        try:
            download(u, hurdat_path); hurdat_used = u; break
        except Exception as e:
            print(f"failed {u}: {e}")
else:
    hurdat_used = "cached local copy"
print("HURDAT2:", hurdat_path, hurdat_path.stat().st_size if hurdat_path.exists() else "MISSING")

# SPC: try yearly consolidated files
spc_urls = [
    "https://www.spc.noaa.gov/wcm/data/1950-2025_actual_tornadoes.csv",
    "https://www.spc.noaa.gov/wcm/data/1950-2024_actual_tornadoes.csv",
    "https://www.spc.noaa.gov/wcm/data/1950-2023_actual_tornadoes.csv",
]
spc_path = DATA / "spc_torn.csv"
spc_used = None
if not spc_path.exists():
    for u in spc_urls:
        try:
            download(u, spc_path); spc_used = u; break
        except Exception as e:
            print(f"failed {u}: {e}")
else:
    spc_used = "cached local copy"
print("SPC:", spc_path, spc_path.stat().st_size if spc_path.exists() else "MISSING")

# Parse HURDAT2
def parse_lat(s):
    s = s.strip()
    return float(s[:-1]) * (1 if s[-1] == "N" else -1)
def parse_lon(s):
    s = s.strip()
    return float(s[:-1]) * (-1 if s[-1] == "W" else 1)

tracks = {}  # id -> list of dicts
cur = None
with open(hurdat_path) as f:
    for line in f:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and re.match(r"^(AL|CP|EP)\d+$", parts[0]):
            cur = parts[0]; tracks[cur] = []
        elif cur and len(parts) >= 8 and re.match(r"^\d{8}$", parts[0]):
            try:
                dt = datetime.strptime(parts[0] + parts[1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                _la, _lo = parse_lat(parts[4]), parse_lon(parts[5])
            except Exception:
                continue
            # HURDAT2 cols: date, time, record_id (L=landfall), status, lat, lon, wind, pres, ...
            tracks[cur].append({"dt": dt, "record_id": parts[2], "status": parts[3],
                                "lat": parse_lat(parts[4]), "lon": parse_lon(parts[5]),
                                "wind": parts[6], "pres": parts[7]})

landfalls = {}
for name, sid in STORMS.items():
    pts = tracks.get(sid, [])
    lf = [p for p in pts if "L" in p["record_id"]]
    print(f"{name} {sid}: {len(pts)} fixes, {len(lf)} landfall fixes")
    for p in lf:
        print("  LF", p["dt"].isoformat(), p["lat"], p["lon"], "wind", p["wind"])
    # Gulf landfall = first L fix on the CONUS Gulf/Florida coast: latitude >= 25 N
    # and longitude between -97 and -79. This excludes the Cuba landfalls of Ida
    # (21.5 N, 22.4 N) and Ian (22.2 N) and Ian's later South Carolina landfall is
    # not first, so the first qualifying fix is the Florida landfall for Ian.
    gulf = [p for p in lf if p["lat"] >= 25.0 and -97.0 <= p["lon"] <= -79.0]
    pick = gulf[0] if gulf else (lf[0] if lf else None)
    if pick:
        landfalls[name] = {"storm_id": sid, "landfall_utc": pick["dt"].isoformat(),
                           "lat": pick["lat"], "lon": pick["lon"],
                           "n_landfall_fixes": len(lf),
                           "all_landfalls": [{"dt": p["dt"].isoformat(), "lat": p["lat"], "lon": p["lon"]} for p in lf]}
    else:
        landfalls[name] = {"storm_id": sid, "landfall_utc": None, "note": "no L status fix found"}

(RESULTS / "step1_landfalls.json").write_text(json.dumps({"hurdat_url": hurdat_used, "spc_url": spc_used, "landfalls": landfalls}, indent=2))
print(json.dumps(landfalls, indent=2))

# SPC tornadoes
df = pd.read_csv(spc_path, low_memory=False)
print("SPC columns:", list(df.columns))
print("SPC rows:", len(df), "years:", df["yr"].min() if "yr" in df else "?", df["yr"].max() if "yr" in df else "?")
# SPC time is local? SPC tornado CSV date/time: 'date' and 'time' in local standard time of tornado location historically; commonly treated as local. We document assumption: use date+time as given converted naively; window is wide (-24/+72h) so timezone offset (<=7h) does not change inclusion materially except at edges. Keep flag.
# Columns expected: om,yr,mo,dy,date,time,tz,fips,st,stf,stn,mag,inj,fat,loss,closs,slat,slon,elat,elon,len,wid,ns,sg,sn,fc
# The 1950-2025 actual-tornadoes file is single-track: every row has sg == 1
# (verified in run log) so no state-segment dedupe is needed or applied.
if "sg" in df.columns:
    print("sg distribution:", df["sg"].value_counts().to_dict())
df["dt_naive"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str), errors="coerce")
print(df[["om","yr","mo","dy","date","time","tz"]].head(3).to_string())

# era median width per decade for missing widths
df["wid_num"] = pd.to_numeric(df["wid"], errors="coerce")
med_by_decade = df.groupby((df["yr"]//10)*10)["wid_num"].median().to_dict()
overall_med = float(df["wid_num"].median())
print("width medians by decade:", med_by_decade, "overall:", overall_med)

def haversine_km(lat1, lon1, lat2, lon2):
    import math as _m
    R = 6371.0
    p1, p2 = _m.radians(lat1), _m.radians(lat2)
    dp = _m.radians(lat2 - lat1); dl = _m.radians(lon2 - lon1)
    a = _m.sin(dp / 2) ** 2 + _m.cos(p1) * _m.cos(p2) * _m.sin(dl / 2) ** 2
    return 2 * R * _m.asin(_m.sqrt(a))

def center_at(sid, when):
    """Linear interpolation of HURDAT2 center at datetime `when` (UTC)."""
    pts = tracks.get(sid, [])
    if not pts: return None
    if when <= pts[0]["dt"]: return pts[0]["lat"], pts[0]["lon"]
    if when >= pts[-1]["dt"]: return pts[-1]["lat"], pts[-1]["lon"]
    for a, b in zip(pts, pts[1:]):
        if a["dt"] <= when <= b["dt"]:
            f = (when - a["dt"]).total_seconds() / max((b["dt"] - a["dt"]).total_seconds(), 1)
            return a["lat"] + f * (b["lat"] - a["lat"]), a["lon"] + f * (b["lon"] - a["lon"])
    return None

TC_RADIUS_KM = 800.0
for name, sid in STORMS.items():
    lf_iso = landfalls[name]["landfall_utc"]
    if not lf_iso: continue
    lf = datetime.fromisoformat(lf_iso)
    t0 = lf - timedelta(hours=24); t1 = lf + timedelta(hours=72)
    # SPC times are local (tz column: 3=CST etc varies). Approximate UTC by adding 6h (central) - but FL tornadoes are ET (+5/+4). Simpler: compare naive local datetime widened by 7h on both sides to be inclusive, then flag edge cases. Instead: use window expanded by 8h for selection, record both.
    sel = df[(df["dt_naive"] >= (t0.replace(tzinfo=None) - timedelta(hours=8))) & (df["dt_naive"] <= (t1.replace(tzinfo=None) + timedelta(hours=8)))].copy()
    # keep only rows whose naive time within core window OR within expanded (mark edge)
    sel["in_core_window"] = (sel["dt_naive"] >= t0.replace(tzinfo=None)) & (sel["dt_naive"] <= t1.replace(tzinfo=None))
    n_time = len(sel)
    # TC-association filter: distance from tornado start/end to contemporaneous TC center.
    # SPC times are local; using them as approximate UTC shifts the center by at most one
    # 6 h fix interval, small against the 800 km radius. Documented in provenance.
    def _dist(r):
        c = center_at(sid, r["dt_naive"].to_pydatetime().replace(tzinfo=timezone.utc))
        if c is None: return None
        d1 = haversine_km(float(r["slat"]), float(r["slon"]), c[0], c[1])
        elat = float(r["elat"]) if pd.notna(r["elat"]) and float(r["elat"]) != 0 else float(r["slat"])
        elon = float(r["elon"]) if pd.notna(r["elon"]) and float(r["elon"]) != 0 else float(r["slon"])
        return min(d1, haversine_km(elat, elon, c[0], c[1]))
    sel["dist_tc_km"] = sel.apply(_dist, axis=1)
    sel = sel[sel["dist_tc_km"] <= TC_RADIUS_KM].copy()
    print(f"{name}: landfall {lf_iso} window {t0}..{t1} -> {n_time} in time window, {len(sel)} within {TC_RADIUS_KM:.0f} km of center (core {sel['in_core_window'].sum()})")
    print(sel[["om","date","time","st","mag","slat","slon","elat","elon","len","wid"]].to_string() if len(sel) else "  none")
    feats = []
    for _, r in sel.iterrows():
        slat, slon = float(r["slat"]), float(r["slon"])
        elat = float(r["elat"]) if pd.notna(r["elat"]) and float(r["elat"]) != 0 else slat
        elon = float(r["elon"]) if pd.notna(r["elon"]) and float(r["elon"]) != 0 else slon
        wid = r["wid_num"]
        flagged = False
        if pd.isna(wid) or wid <= 0:
            dec = (int(r["yr"])//10)*10
            wid = float(med_by_decade.get(dec, overall_med)); flagged = True
        width_m = float(wid) * 0.9144
        line = LineString([(slon, slat), (elon, elat)])
        feats.append({"om": str(r["om"]), "date": str(r["date"]), "time": str(r["time"]),
                      "st": str(r["st"]), "mag": (None if (pd.isna(r["mag"]) or float(r["mag"]) < 0) else float(r["mag"])),
                      "len_mi": (None if pd.isna(r["len"]) else float(r["len"])),
                      "wid_yd": float(wid), "wid_flag_median": bool(flagged),
                      "width_m": width_m, "in_core_window": bool(r["in_core_window"]),
                      "dist_tc_km": (None if pd.isna(r["dist_tc_km"]) else float(r["dist_tc_km"])),
                      "geometry_line": line})
    if feats:
        attrs = [{k: v for k, v in f.items() if k != "geometry_line"} for f in feats]
        lines = [f["geometry_line"] for f in feats]
        g = gpd.GeoDataFrame(attrs, geometry=lines, crs="EPSG:4326")
        g["line_wkt"] = g.geometry.to_wkt()
        # buffer in metres: project to EPSG:5070 (CONUS Albers, metres)
        gp = g.to_crs("EPSG:5070")
        buffered = [geom.buffer(w / 2.0, cap_style=2) for geom, w in zip(gp.geometry, gp["width_m"])]
        out5070 = gpd.GeoDataFrame(attrs + [{}] * 0, geometry=buffered, crs="EPSG:5070")
        out5070["line_wkt"] = g["line_wkt"].values
        # carry all attribute columns across explicitly
        for col in g.columns:
            if col not in out5070.columns and col != g.geometry.name:
                out5070[col] = g[col].values
        tot_area = float(out5070.geometry.area.sum()) / 1e4
        out = out5070.to_crs("EPSG:4326")
        out.to_file(DATA / f"paths_{name.lower()}.geojson", driver="GeoJSON")
        g.to_file(DATA / f"lines_{name.lower()}.geojson", driver="GeoJSON")
        # verify read-back
        chk = gpd.read_file(DATA / f"paths_{name.lower()}.geojson")
        print(f"  saved {len(out)} paths, total footprint {tot_area:.1f} ha; readback bounds {chk.total_bounds}, readback area5070 {float(chk.to_crs('EPSG:5070').geometry.area.sum())/1e4:.1f} ha")
    else:
        print(f"  NO PATHS for {name}")
print("STEP1 DONE")
