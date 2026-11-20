"""Download the raw source files for the TC tornado climatology.

Sources (download date recorded by the caller as 2026-11-06):
  1. NHC HURDAT2 Atlantic best tracks, latest file found in the NHC
     directory listing on 2026-11-06:
     hurdat2-1851-2025-092326.txt (1851 to 2025, revision of
     23 September 2026).
  2. NOAA Storm Prediction Center severe weather database, tornado file
     in "actual tornadoes" (whole track) form:
     1950-2025_actual_tornadoes.csv (1950 to 2025).
     The whole-track file is used instead of the state-segment file
     (1950-2025_torn.csv) so that a tornado crossing a state line is
     counted once, not once per state segment. Both files are the same
     SPC database; the segment file was also requested and its status is
     logged below.

Rerunnable: python3 code/01_download_data.py
Existing files are re-downloaded and their SHA-256 hashes printed.
No em dashes are used in any output of this project.
"""
import hashlib
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(parents=True, exist_ok=True)

FILES = {
    "hurdat2-1851-2025-092326.txt":
        "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt",
    "1950-2025_actual_tornadoes.csv":
        "https://www.spc.noaa.gov/wcm/data/1950-2025_actual_tornadoes.csv",
    # Segment form of the same SPC database, kept for cross checking the
    # whole-track counts. Not used as the primary tornado source.
    "1950-2025_torn.csv":
        "https://www.spc.noaa.gov/wcm/data/1950-2025_torn.csv",
    # SPC TCTOR database (Edwards), the attributed TC tornado list used
    # by Moore, Sokol and Blume (2017). The linked file is a Microsoft
    # Excel workbook; the 2024 README version contains data through
    # 2023. This is the historical sample for its covered years.
    "tctor.xls":
        "https://www.spc.noaa.gov/publications/edwards/tctor.xls",
    # Natural Earth 1:10m coastline, used only to compute each
    # tornado start point distance from the coastline in the bins of
    # Moore et al. (2017).
    "ne_10m_coastline.zip":
        "https://naturalearth.s3.amazonaws.com/10m_physical/ne_10m_coastline.zip",
}


def fetch(name, url):
    out = DATA / name
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = resp.read()
            status = resp.status
            lastmod = resp.headers.get("Last-Modified")
    except Exception as exc:  # log and continue with the other files
        print(f"FAILED {name} {url} error={exc}")
        return
    out.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(f"OK {name} status={status} bytes={len(payload)} "
          f"sha256={digest} last_modified={lastmod} url={url}")


if __name__ == "__main__":
    for fname, furl in FILES.items():
        fetch(fname, furl)
