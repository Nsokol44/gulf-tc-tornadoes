#!/usr/bin/env bash
# One-command rerun for the Idalia + Florence HLS marsh case studies.
# Creates the project venv on first use, then runs both builds.
# Per-month pixel values are cached in results/pixels_<storm>*.npz
# (atomic writes), so an interrupted run resumes where it stopped.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q "numpy==1.26.4" "pandas==2.3.3" geopandas rasterio \
    pystac-client planetary-computer scipy shapely pyproj
fi
.venv/bin/python code/build_cases.py idalia
.venv/bin/python code/build_florence_equiv.py
