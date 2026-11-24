"""run_all.py - one-command rerun of the full rebuild pipeline.

Usage (from this code/ directory's parent, the analysis/ folder):

    PYTHONPATH=$HOME/.local/lib/python3.12/site-packages python3 code/run_all.py

The PYTHONPATH prefix is required on this machine: the geospatial stack
(geopandas, rasterio, shapely) lives in ~/.local/lib/python3.12/site-packages
and is not on the default python3 (3.12.3) path.

Steps:
  01 prepare inputs (parse HURDAT2 / TCTOR / SPC from the original project)
  02 build the two-coast verified-years sample
  03 climatology tables (Tables 1-4 analogues)
  04 fetch NLCD 2021 tiles via MRLC WCS and build footprints + mosaic
  05 land-cover stratification
  06 case screening 2016-2023 (NWI via Esri Living Atlas; screening only)
  07 figure data (Figures 1-2)

Network steps (04, 06) are cached: existing tiles / NWI geojsons are reused.
Deterministic: no random number generation anywhere in the pipeline.
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = ["01_prepare_inputs.py", "02_build_sample.py", "03_climatology.py",
         "04_fetch_nlcd.py", "05_landcover.py", "06_case_screening.py",
         "07_figure_data.py"]


def main():
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        r = subprocess.run([sys.executable, str(HERE / step)])
        if r.returncode != 0:
            print(f"FAILED: {step} (exit {r.returncode})")
            sys.exit(r.returncode)
    print("\nAll steps complete. See results/REBUILD_REPORT.md inputs in results/.")


if __name__ == "__main__":
    main()
