# Gulf Coast tropical-cyclone tornadoes revisited: code and derived tables

Analysis code and derived tables for:

Nicholas J. Sokol, "Gulf Coast tropical-cyclone tornadoes revisited:
spatial distributions, intensity, and satellite-observed marsh damage
and recovery." Submitted to *Physical Geography* on 19 November 2026
(Submission ID 267343579). Sole author.

This repository is the deposit promised in the paper's Data and code
availability statement. It contains the analysis code and the derived
tornado, geometry, and trajectory tables. It does not contain the raw
third-party datasets, which are public and are fetched by the pipeline
from their sources (see below).

## Contents

- `code/` — the full analysis pipeline (Python).
  - `01_download_data.py` to `06_analyse_climatology.py`, orchestrated
    by `run_all.py`: the tropical-cyclone (TC) tornado climatology.
    TCTOR records for qualifying Gulf TCs form the primary sample for
    1995–2023; the 2024–2025 seasons are attributed with the broad
    operational rule (800 km full-track window, `03`) and the Moore and
    Dixon (2011) rule (`04`) as a sensitivity case; `05` builds the
    primary sample and `06` computes the era comparisons, quadrant,
    intensity, size, and coastal-distance distributions reported in
    the paper.
  - `step1_paths.py`, `step2_overlap.py`, `step3_hls.py`,
    `step3c_points.py`: the marsh remote-sensing pipeline. Tornado
    path footprints are intersected with National Wetlands Inventory
    marsh; Harmonized Landsat and Sentinel-2 (HLS v2.0) NDVI
    trajectories are sampled at 30 m pixels inside the footprints and
    in matched reference marsh for Hurricanes Ida (2021), Helene
    (2024), and Milton (2024). (Ian 2022 was assessed and dropped for
    insufficient marsh; see `results/summary_ian.json`.)
  - `placebo_ida.py`: the placebo test for Ida. 200 coherent
    pseudo-footprint patches are drawn in untouched reference marsh
    and run through the same swing estimand as the observed footprint.
  - `fetch_ida_imagery.py`, `make_fig_imagery.py`, `make_figures.py`:
    figure production for the paper.
- `data/` — derived geometry and sample tables produced by the
  pipeline: the qualifying Gulf TC list and landfall table
  (`qualifying_gulf_tcs.csv`, `gulf_hurricane_landfalls.csv`), tornado
  path geometries (`paths_<storm>.geojson`), storm track lines
  (`lines_<storm>.geojson`), marsh inside the paths
  (`marsh_in_paths_<storm>.geojson`), analysed footprints
  (`footprint_<storm>.geojson`), and reference marsh
  (`reference_<storm>.geojson`).
- `results/` — derived result tables and summaries:
  `tc_tornadoes.csv` is the primary derived tornado table (1,745 Gulf
  TC tornadoes from 97 storms, 1995–2025), with the operational-rule
  variants `tc_tornadoes_op800.csv`, `tc_tornadoes_r500.csv`, and
  `tc_tornadoes_md2011.csv`; `climatology_summary.json` and
  `climatology_tables.md` hold the climatology results;
  `marsh_trajectories.csv`, `trajectories_<storm>.csv`,
  `marsh_summary.json`, and `summary_<storm>.json` hold the NDVI
  trajectory results; `placebo_ida.json` and `placebo_ida_swings.csv`
  hold the placebo results; the `*_provenance.md` files and
  `CORRECTION_milton_coast.md` document data provenance and a recorded
  correction.
- `BUILD_LOG.md` — the build log kept during the analysis, including
  methods notes and the recorded Milton coastal correction.

## Data sources (all public; accessed 6 November 2026)

- SPC TCTOR database (tropical-cyclone tornado records, through 2023).
- HURDAT2 (NHC Atlantic hurricane database, through the 2025 season).
- NOAA Storm Prediction Center severe weather database (tornado
  records 1950–2025).
- US Fish and Wildlife Service National Wetlands Inventory (marsh
  polygons, via the Esri Living Atlas republishing of NWI).
- Harmonized Landsat and Sentinel-2 (HLS) version 2.0 surface
  reflectance, via the Microsoft Planetary Computer.
- Natural Earth state and coastline boundaries (figure basemaps only).

`code/01_download_data.py` downloads the climatology inputs into
`data/`; the marsh steps query the NWI service and the Planetary
Computer STAC API directly.

## How to rerun

Climatology (one command, from the repository root):

```bash
python3 code/run_all.py
```

Marsh pipeline (in order):

```bash
python3 code/step1_paths.py
python3 code/step2_overlap.py
python3 code/step3_hls.py
python3 code/step3c_points.py
python3 code/placebo_ida.py
```

Dependencies are listed in `requirements.txt` (Python 3.12;
geopandas, rasterio, shapely, pyproj, pandas, numpy, scipy,
matplotlib, pystac-client, planetary-computer, pyarrow, xlrd).

## Reproducibility

Stochastic steps use fixed seeds: the project standard is
`numpy.random.default_rng(20261106)`, and the Ida placebo test uses
`numpy.random.default_rng(20261107)` (recorded in
`results/placebo_ida.json`). All other steps are deterministic given
the input data.

## Not included

- Raw third-party datasets (TCTOR workbook, HURDAT2 text, SPC tornado
  CSV, NWI polygon extracts, Natural Earth archives). These are public
  source data, fetched by the pipeline; they are not redistributed
  here.
- Intermediate HLS raster scenes (GeoTIFF) and per-pixel sample
  archives (`.npz`) used during the trajectory sampling. The derived
  trajectory tables computed from them are in `results/`.
- The manuscript itself, which is under review at *Physical
  Geography*.
