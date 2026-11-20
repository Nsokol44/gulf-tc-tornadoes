"""Parse HURDAT2 and the SPC tornado CSV into tidy tables.

Outputs (in data/):
  hurdat2_tidy.parquet   one row per best track fix
  spc_tornadoes_tidy.parquet  one row per tornado (whole track form)

Timezone convention, stated explicitly:
  HURDAT2 date and time fields are UTC.
  SPC tornado date and time fields are recorded in Central Standard
  Time (CST, fixed UTC-06:00, no daylight saving shift). The tz code
  is 3 (CST) for 73,421 of the 73,458 records in the downloaded
  file, and for every record in the 1995 to 2025 analysis window
  used here. The 37 records with other tz codes (0, 6 or 9) all fall
  in 1956 to 1994, outside the analysis window; they are converted
  with the same CST offset in this tidy table and are flagged in the
  tz column, and no result in this project uses them. SPC times with
  tz code 3 are converted to UTC by adding 6 hours, so that tornado
  times and HURDAT2 times share one clock.
  The original SPC date, time and year are kept in the output so the
  conversion can be audited. Grouping by year in the analysis uses
  the SPC recorded year, which for tropical cyclone season months
  (June to November) is the same as the UTC year except for events
  within 6 hours of 1 January, which do not occur for the storms
  studied here.

Unit conversions: SPC path length is in miles and is converted to
kilometres (1 mile = 1.609344 km). SPC path width is in yards and is
converted to metres (1 yard = 0.9144 m). HURDAT2 winds are in knots
and central pressure in millibars (hPa), with -999 treated as missing.
SPC end coordinates of 0.0 are a missing value code and are set to NaN.
SPC rating mag of -9 is the unknown rating code and is set to NaN in
the cleaned rating column while the raw value is retained.

Rerunnable: python3 code/02_parse_data.py
"""
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

HURDAT_FILE = DATA / "hurdat2-1851-2025-092326.txt"
SPC_FILE = DATA / "1950-2025_actual_tornadoes.csv"

RNG = np.random.default_rng(20261106)  # fixed seed, see project notes


def parse_lat(text):
    text = text.strip()
    hemi = text[-1]
    val = float(text[:-1])
    return -val if hemi in "SW" else val


def parse_hurdat(path):
    rows = []
    storm_id, name = None, None
    with open(path) as fh:
        for line in fh:
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3 and parts[0].startswith("AL") and parts[2].isdigit():
                storm_id, name = parts[0], parts[1]
                continue
            if len(parts) < 7 or storm_id is None:
                continue
            rows.append({
                "storm_id": storm_id,
                "name": name,
                "date_raw": parts[0],
                "time_raw": parts[1].zfill(4),
                "record_id": parts[2],
                "status": parts[3],
                "lat": parse_lat(parts[4]),
                "lon": parse_lat(parts[5]),
                "max_wind_kt": float(parts[6]),
                "pressure_mb": float(parts[7]) if len(parts) > 7 else np.nan,
            })
    df = pd.DataFrame(rows)
    df["datetime_utc"] = pd.to_datetime(
        df["date_raw"] + df["time_raw"], format="%Y%m%d%H%M", utc=True)
    df.loc[df["pressure_mb"] == -999, "pressure_mb"] = np.nan
    df["year"] = df["datetime_utc"].dt.year
    return df.sort_values(["storm_id", "datetime_utc"]).reset_index(drop=True)


def parse_spc(path):
    df = pd.read_csv(path, low_memory=False)
    df["datetime_cst"] = pd.to_datetime(
        df["date"] + " " + df["time"].astype(str), errors="coerce")
    # CST is a fixed UTC-06:00 offset in the SPC recording convention.
    df["datetime_utc"] = (
        df["datetime_cst"].dt.tz_localize("Etc/GMT+6").dt.tz_convert("UTC"))
    df["rating_raw"] = df["mag"]
    df["rating"] = df["mag"].where(df["mag"] >= 0, np.nan)
    # The F scale applies before 1 February 2007 and the EF scale from
    # that date, the implementation date of the Enhanced Fujita scale.
    df["scale"] = np.where(
        df["datetime_cst"] < pd.Timestamp("2007-02-01"), "F", "EF")
    for col in ("elat", "elon"):
        df[col] = df[col].where(df[col] != 0.0, np.nan)
    df["len_km"] = df["len"] * 1.609344
    df["wid_m"] = df["wid"] * 0.9144
    keep = ["om", "yr", "mo", "dy", "date", "time", "tz", "st",
            "datetime_cst", "datetime_utc", "rating", "rating_raw",
            "scale", "inj", "fat", "loss", "closs", "slat", "slon",
            "elat", "elon", "len", "len_km", "wid", "wid_m", "ns", "sn"]
    return df[keep].sort_values("datetime_utc").reset_index(drop=True)


def parse_tctor(path):
    """Parse the SPC TCTOR workbook (Full List sheet) into a tidy table.

    The workbook has a title row and a header row, then one row per
    attributed TC tornado, then a footer block of summary rows. Data
    rows are identified by a numeric Year between 1995 and 2023 and a
    non-empty TC Name; the workbook footer itself states a total of
    1783 data rows, which the parser output is checked against in the
    analysis script. TCTOR longitudes for the TC centre are stored
    without a minus sign (degrees west) and are converted to signed
    longitudes here. Tornado longitudes are already signed.
    """
    raw = pd.read_excel(path, sheet_name="Full List", header=1)
    raw.columns = [str(c) for c in raw.columns]
    col = {c: c for c in raw.columns}
    year = pd.to_numeric(raw["Year"], errors="coerce")
    mask = year.between(1995, 2023) & raw["TC Name"].notna()
    d = raw[mask].copy()
    d["yr"] = year[mask].astype(int)
    utc_time = d["UTC time"].astype(str).str.slice(0, 8)
    d["datetime_utc"] = pd.to_datetime(
        d["yr"].astype(str) + "-" + d["UTC-Mo."].astype(int).astype(str)
        + "-" + d["UTC-Date"].astype(int).astype(str) + " " + utc_time,
        errors="coerce", utc=True)
    d["datetime_cst"] = d["datetime_utc"] - pd.Timedelta(6, "h")
    d["tc_name_raw"] = d["TC Name"].astype(str).str.strip()
    d["tc_name"] = d["tc_name_raw"].str.rsplit("-", n=1).str[0].str.upper()
    out = pd.DataFrame({
        "yr": d["yr"],
        "datetime_utc": d["datetime_utc"],
        "datetime_cst": d["datetime_cst"],
        "st": d["State"].astype(str),
        "rating": pd.to_numeric(d["F or EF"], errors="coerce"),
        "inj": pd.to_numeric(d["Injured"], errors="coerce"),
        "fat": pd.to_numeric(d["Killed"], errors="coerce"),
        "slat": pd.to_numeric(d["LAT-start (path)"], errors="coerce"),
        "slon": pd.to_numeric(d["LON-start (path)"], errors="coerce"),
        "elat": pd.to_numeric(d["LAT-end (path)"], errors="coerce"),
        "elon": pd.to_numeric(d["LON-end (path)"], errors="coerce"),
        "len_km": pd.to_numeric(d["Length-km"], errors="coerce"),
        "wid_m": pd.to_numeric(d["Width-m"], errors="coerce"),
        "dpi_tctor": pd.to_numeric(d["DPI"], errors="coerce"),
        "tc_name": d["tc_name"],
        "tc_name_raw": d["tc_name_raw"],
        "tc_cat": d["TC Cat"].astype(str),
        "tc_lat_interp": pd.to_numeric(d["InterpLat"], errors="coerce"),
        "tc_lon_interp": -pd.to_numeric(d["InterpLon"], errors="coerce"),
        "bearing_tctor": pd.to_numeric(
            d["Bearing from Center (deg) from Worksheet"], errors="coerce"),
        "distance_tctor_km": pd.to_numeric(
            d["Tor-Center Dist km (from Worksheet)"], errors="coerce"),
    })
    return out.sort_values("datetime_utc").reset_index(drop=True)


if __name__ == "__main__":
    tct = parse_tctor(DATA / "tctor.xls")
    tct.to_parquet(DATA / "tctor_tidy.parquet", index=False)
    print(f"TCTOR rows: {len(tct)} years: {tct['yr'].min()} to "
          f"{tct['yr'].max()} storms: {tct['tc_name_raw'].nunique()}")
    print(f"TCTOR rows 1995-2015: {int((tct['yr'] <= 2015).sum())} "
          f"zero width 1995-2015: "
          f"{int(((tct['wid_m'] == 0) & (tct['yr'] <= 2015)).sum())}")
    hur = parse_hurdat(HURDAT_FILE)
    hur.to_parquet(DATA / "hurdat2_tidy.parquet", index=False)
    print(f"HURDAT2 fixes: {len(hur)} storms: {hur['storm_id'].nunique()} "
          f"years: {hur['year'].min()} to {hur['year'].max()}")
    print(f"HURDAT2 record_id values: {sorted(hur['record_id'].unique())}")
    spc = parse_spc(SPC_FILE)
    spc.to_parquet(DATA / "spc_tornadoes_tidy.parquet", index=False)
    print(f"SPC tornadoes: {len(spc)} years: {spc['yr'].min()} to "
          f"{spc['yr'].max()} tz codes: {sorted(spc['tz'].unique())}")
    print(f"SPC unknown ratings (mag -9): {int((spc['rating_raw'] == -9).sum())}")
    print(f"SPC zero widths: {int((spc['wid'] == 0).sum())}")
