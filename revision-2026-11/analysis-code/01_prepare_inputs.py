"""01_prepare_inputs.py

Parse the original project's raw inputs (read by path, never modified) into
tidy parquet files in this workspace's data/ directory, and log provenance.

Sources (all verified current on 2026-11-23):
- TCTOR: SPC Tropical Cyclone Tornado database, "2024 Version, Data thru 2023"
  (readme at spc.noaa.gov/publications/edwards/readme.txt). The live
  tctor.xls downloaded 2026-11-23 is byte-identical (MD5
  290c46a2c8030f64eedbdfc9cce93142) to the archived copy used here, so the
  verified climatology endpoint is 2023.
- HURDAT2: NHC file hurdat2-1851-2025-092326.txt (release dated 2025-09-23).
  The copy re-downloaded from nhc.noaa.gov on 2026-11-23 is byte-identical
  (MD5 2a6ab0d9316f55ff8b41fa232ea54921) to the archived copy used here.
- SPC severe database CSVs archived in the original project (annual all-US
  counts for years <= 2023 are final in the current SPC database).
- Natural Earth 1:10m coastline (archived zip in the original project).
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ORIG = Path.home() / "workspace/moore-pitch/angle2-tc-tornadoes"
HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

SEED = 20261106  # project seed convention (deterministic pipeline; no RNG used here)


def md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_hurdat2(path: Path) -> pd.DataFrame:
    rows = []
    storm_id = storm_name = None
    header_re = re.compile(r"^[A-Z]{2}\d{6}$")
    with open(path) as f:
        for line in f:
            parts = [p.strip() for p in line.split(",")]
            if header_re.match(parts[0]):
                storm_id, storm_name = parts[0], parts[1]
                continue
            if len(parts) < 7 or not parts[0].isdigit():
                continue
            lat = float(parts[4][:-1]) * (1 if parts[4][-1] == "N" else -1)
            lon = float(parts[5][:-1]) * (-1 if parts[5][-1] == "W" else 1)
            rows.append(
                dict(
                    storm_id=storm_id,
                    storm_name=storm_name,
                    datetime=pd.to_datetime(parts[0] + parts[1], format="%Y%m%d%H%M"),
                    record_id=parts[2],
                    status=parts[3],
                    lat=lat,
                    lon=lon,
                    wind_kt=int(parts[6]) if parts[6] not in ("", "-999") else np.nan,
                )
            )
    df = pd.DataFrame(rows)
    df["year"] = df["datetime"].dt.year
    return df


def parse_tctor(path: Path) -> pd.DataFrame:
    t = pd.read_excel(path, sheet_name="Full List", header=1)
    ren = {
        "Year": "yr",
        "F or EF": "rating",
        "Injured": "inj",
        "Killed": "fat",
        "LAT-start (path)": "slat",
        "LON-start (path)": "slon",
        "LAT-end (path)": "elat",
        "LON-end (path)": "elon",
        "Length-km": "len_km",
        "Width-m": "wid_m",
        "DPI": "dpi",
        "TC Name": "tc_name",
        "InterpLat": "tc_lat",
        "InterpLon": "tc_lon",
        "Bearing from Center (deg) from Worksheet": "bearing_deg",
        "Tor-Center Dist km (from Worksheet)": "distance_km",
        "State": "st",
    }
    t = t.rename(columns=ren)
    keep = [c for c in ren.values() if c in t.columns]
    t = t[keep].copy()
    for c in ["yr", "rating", "inj", "fat", "slat", "slon", "elat", "elon",
              "len_km", "wid_m", "dpi", "tc_lat", "tc_lon", "bearing_deg", "distance_km"]:
        if c in t.columns:
            t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["yr"]).copy()
    t["yr"] = t["yr"].astype(int)
    # Drop the sheet's trailing month-summary footer rows (no storm, no path).
    t["tc_name"] = t["tc_name"].astype(str).str.strip().str.upper()
    t = t[(t["yr"] >= 1900) & (~t["tc_name"].isin(["NAN", "NONE", ""])) & t["slat"].notna()].copy()
    # TCTOR centre longitude is stored unsigned (degrees W); make it signed.
    t["tc_lon"] = -t["tc_lon"].abs()
    t["rating"] = pd.to_numeric(t["rating"], errors="coerce")
    t.loc[t["rating"] < 0, "rating"] = np.nan  # -9 = unknown
    for c in ["elat", "elon"]:
        t.loc[t[c] == 0.0, c] = np.nan
    return t


def main():
    prov = {"generated_by": "code/01_prepare_inputs.py", "seed": SEED, "sources": {}}

    hur_path = ORIG / "data/hurdat2-1851-2025-092326.txt"
    hur = parse_hurdat2(hur_path)
    hur.to_parquet(DATA / "hurdat2_tidy.parquet", index=False)
    prov["sources"]["hurdat2"] = {
        "path": str(hur_path), "md5": md5(hur_path),
        "release": "hurdat2-1851-2025-092326 (2025-09-23)",
        "currency_check": "re-downloaded from nhc.noaa.gov 2026-11-23; MD5 identical",
        "rows": int(len(hur)),
    }

    tc_path = ORIG / "data/tctor.xls"
    tc = parse_tctor(tc_path)
    tc.to_parquet(DATA / "tctor.parquet", index=False)
    prov["sources"]["tctor"] = {
        "path": str(tc_path), "md5": md5(tc_path),
        "release": "SPC TCTOR 2024 Version, Data thru 2023",
        "currency_check": "live tctor.xls downloaded 2026-11-23; MD5 identical to archived copy",
        "rows": int(len(tc)),
        "years": [int(tc["yr"].min()), int(tc["yr"].max())],
    }

    spc_path = ORIG / "data/1950-2025_actual_tornadoes.csv"
    spc = pd.read_csv(spc_path, usecols=["yr", "mag"])
    counts = spc.groupby("yr").size().rename("all_us_tornadoes").reset_index()
    counts.to_csv(DATA / "spc_annual_counts.csv", index=False)
    prov["sources"]["spc_actual"] = {
        "path": str(spc_path), "md5": md5(spc_path),
        "note": "SPC severe database as archived; counts for years <= 2023 are final.",
        "years": [int(counts["yr"].min()), int(counts["yr"].max())],
    }

    ne_path = ORIG / "data/ne_10m_coastline.zip"
    prov["sources"]["natural_earth_coastline"] = {
        "path": str(ne_path), "md5": md5(ne_path), "release": "Natural Earth 1:10m coastline",
    }

    with open(DATA / "PROVENANCE.json", "w") as f:
        json.dump(prov, f, indent=2)
    print(f"HURDAT2 rows: {len(hur)}; TCTOR rows: {len(tc)} "
          f"({int(tc['yr'].min())}-{int(tc['yr'].max())}); SPC years {counts['yr'].min()}-{counts['yr'].max()}")
    print("Provenance written to data/PROVENANCE.json")


if __name__ == "__main__":
    main()
