# Angle 2 rebuild pipeline (Physical Geography revision, 2026-11)

Rebuilds the analysis of "Gulf Coast tropical-cyclone tornadoes revisited"
under the author's 2026-11-23 design: two-coast domain (Gulf + Atlantic)
with coast strata, verified years only (TCTOR), NLCD land-cover
stratification, and a 2016-2023 case-screening table. The original project
(`~/workspace/moore-pitch/angle2-tc-tornadoes/`) is read-only input; nothing
there is modified.

## Run

```bash
cd ~/workspace/moore-pitch/angle2-revision-2026-11/analysis
PYTHONPATH=$HOME/.local/lib/python3.12/site-packages python3 code/run_all.py
```

The PYTHONPATH prefix is required on this machine: the geospatial stack
(geopandas 1.2.0, rasterio 1.5.2, shapely 2.1.2, pandas 2.3.3, numpy 2.5.3,
statsmodels 0.15.0) is installed under `~/.local/lib/python3.12/site-packages`
and is not on the default python3 (3.12.3) path. The pipeline is
deterministic; no random number generation is used anywhere.

## Steps

| Script | What it does |
|---|---|
| `01_prepare_inputs.py` | Parses HURDAT2, TCTOR, SPC annual counts from the original project's archived raw files into `data/`; writes `data/PROVENANCE.json` with MD5s. |
| `02_build_sample.py` | Qualifying storms under both coast definitions; coast assignment for dual-qualifier storms by earliest qualifying landfall at >= 24.0 N (author decision, 2026-11-24; box-only fallback; the old first-landfall-anywhere rule is written out as the sensitivity table); TCTOR sample 1995-2023; zero-width edit; geometry per original step 05. |
| `03_climatology.py` | Tables 1-4 analogues (era totals/shares, intensity + two-proportion tests, size/DPI, geometry), annual and per-storm tables, case-storm table from original outputs. |
| `04_fetch_nlcd.py` | Builds Section 2.4 footprints; downloads NLCD 2021 tiles from the MRLC WCS over the footprint blocks into `data/nlcd_tiles/` with a tile index (no single mosaic: the union rectangle is ~8 Gpx). |
| `05_landcover.py` | Per-footprint NLCD grouped-class areas and intersection flags; land-cover summary table. |
| `06_case_screening.py` | Screening only: case-window footprints + NWI marsh crossings (Esri Living Atlas) for 2016-2023 storms with >= 10 sampled tornadoes; Ida benchmark recomputed from original geojsons. No HLS analysis. |
| `07_figure_data.py` | CSVs behind updated Figures 1 and 2 (map points, annual counts, quadrant shares). |
| `08_national_comparison.py` | Auxiliary (not in run_all): all-US intensity rows for the manuscript's Table 3 from the original project's SPC tidy file, using step 06's definitions; reproduces the submitted paper's national rows exactly and adds the 2016-2023 extension era. Output: `results/national_intensity.csv`. |

## Data sources, versions, download dates

- **TCTOR** (SPC Tropical Cyclone Tornado database): "2024 Version, Data
  thru 2023" (readme, spc.noaa.gov/publications/edwards/readme.txt).
  Currency checked 2026-11-23: the live `tctor.xls` is byte-identical
  (MD5 290c46a2c8030f64eedbdfc9cce93142) to the archived copy parsed here.
  **The verified climatology endpoint is therefore 2023**; no newer TCTOR
  release covering 2024 exists as of 2026-11-23.
- **HURDAT2**: `hurdat2-1851-2025-092326.txt` (NHC release dated
  2025-09-23). Re-downloaded 2026-11-23; MD5 identical to archived copy
  (2a6ab0d9316f55ff8b41fa232ea54921).
- **SPC severe database** CSVs as archived in the original project
  (`1950-2025_actual_tornadoes.csv` for all-US annual counts;
  `1950-2025_torn.csv` for case-window screening). Counts for years
  <= 2023 are final; nothing in the climatology uses 2024-2025 records.
- **NLCD 2021 Land Cover L48** (MRLC), downloaded 2026-11-23 via the MRLC
  WCS (`mrlc_download__NLCD_2021_Land_Cover_L48`). The classic CONUS zip
  URL is retired (HTTP 404, checked 2026-11-23 on both www.mrlc.gov and
  edcintl.cr.usgs.gov mirrors). The Annual NLCD product line is served by
  the MRLC WCS only as 1985-2023 change-summary coverages, not land-cover
  rasters; NLCD 2021 is the newest epoch land-cover coverage served and
  carries the same class codes the design groups. Tiles are cached in
  `data/nlcd_tiles/`; the mosaic is `data/nlcd_2021_sample_extent.tif`.
- **NWI** (USFWS National Wetlands Inventory) via the Esri Living Atlas
  "USA Wetlands" feature service, the paper's existing route; per-path
  downloads cached in `data/nwi_screening/`, fetched 2026-11-23.
- **Natural Earth 1:10m coastline** (archived zip in the original project),
  used for tornado-to-coast distances exactly as in the original step 05.

## Judgment calls (also flagged in results/REBUILD_REPORT.md)

1. Atlantic near-coast box implemented as lat 24.0-41.5 N, lon 81.0-66.0 W
   (the mirror of the Gulf box with the 41.5 N cap from the landfall rule).
2. Coast assignment (author decision, 2026-11-24): the latitude-restricted
   rule is PRIMARY. Dual-qualifier storms (qualifying under both coast
   definitions) are assigned by their earliest qualifying landfall fix at
   latitude >= 24.0 N, so a Caribbean, Yucatan, or Central America first
   landfall no longer decides the stratum for a dual-qualifier storm.
   Single-qualifier storms keep their only coast; box-only storms keep the
   box fallback; a dual-qualifier storm with no qualifying landfall at
   >= 24.0 N falls back to the previous assignment and is logged in the
   build log. The previously implemented rule (the landfall rules carry no
   lower latitude bound, exactly as written in the paper's Gulf definition,
   so first landfalls anywhere decided the stratum) is now the reported
   SENSITIVITY: `results/coast_assignment_sensitivity.csv` lists the
   tornadoes that would change stratum under that old rule relative to the
   new primary (11 storms, 322 tornadoes; directions are the reverse of
   the pre-2026-11-24 table).
3. A landfall fix at exactly 81.0 W satisfies both landfall rules; ties at
   the same timestamp are assigned to the Gulf.
4. Zero-length TCTOR paths (start = end, 659 records) are buffered as discs
   of radius half the recorded width (a flat-cap buffer of a point is empty
   in GEOS, so round caps are used for these); segment footprints keep the
   paper's flat caps.
5. Screening candidacy threshold: >= 10 TCTOR tornadoes in the new sample
   (18 storms, 2016-2023). The screening is a table only; no HLS trajectory
   analysis was built for any candidate.
6. Screening case windows span all of a storm's landfall episodes (24 h
   before the first to 72 h after the last HURDAT2 L fix at >= 25 N in the
   union longitude range [-97, -66]). The single assigned-coast anchor of
   the original step1 method leaves Irma, Laura, Fred, Dorian and Sally
   with no usable window; for single-landfall storms the screening window
   is exactly the paper's window.
