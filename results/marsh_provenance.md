# Marsh damage and recovery pipeline: provenance log

Task C, angle2 TC tornadoes manuscript. All data are real downloads or live
service queries made on 2026-11-06 (America/New_York). No simulated or
invented values appear anywhere in this pipeline. Scripts are in code/
(step1_paths.py, step2_overlap.py, step3_hls.py) and run with the interpreter
~/workspace/papers-finish/urban-heat-tac/.venv/bin/python (Python 3.12.3,
geopandas 1.2.0, rasterio, xarray, pystac_client, planetary_computer).

## Step 1: candidate paths

### HURDAT2

- URL: https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-092326.txt
- The latest Atlantic HURDAT2 file in the NHC directory listing at access
  time (1851 to 2025 seasons, file suffix 092326). Downloaded 2026-11-06,
  7,071,568 bytes, saved as data/hurdat2.txt.
- Landfall fixes are the HURDAT2 record identifier L. The Gulf landfall used
  for each storm is the first L fix on the continental Gulf or Florida coast,
  defined as latitude at or north of 25 N and longitude between 97 W and
  79 W. This rule excludes the Cuba landfalls of Ida and Ian and selects:
  - Ida (AL092021): 2021-08-29 16:55 UTC, 29.1 N, 90.2 W, 130 kt (Port
    Fourchon, Louisiana). Other L fixes: Cuba 2021-08-27 18:00 and 23:25 UTC.
  - Ian (AL092022): 2022-09-28 19:05 UTC, 26.7 N, 82.2 W, 130 kt (Cayo Costa,
    Florida). Other L fixes: Cuba 2022-09-27 08:30 UTC, 2022-09-28 02:00 UTC,
    a second Florida fix 2022-09-28 20:35 UTC, South Carolina 2022-09-30
    18:05 UTC.
  - Helene (AL092024): 2024-09-27 03:10 UTC, 30.0 N, 83.7 W, 120 kt (Big Bend,
    Florida). Only L fix.
  - Milton (AL142024): 2024-10-10 00:30 UTC, 27.4 N, 82.6 W, 100 kt (Siesta
    Key, Florida). Only L fix.

### SPC tornado database

- URL: https://www.spc.noaa.gov/wcm/data/1950-2025_actual_tornadoes.csv
- Latest file on the SPC WCM data page at access time (1950 to 2025).
  Downloaded 2026-11-06, 9,023,445 bytes, 73,458 rows, saved as
  data/spc_torn.csv. Every row carries sg equal to 1 in this release, so the
  file is already single-track (whole tornadoes, no state segments) and no
  deduplication was applied.
- Time handling: SPC date and time fields are local clock times at the
  tornado location. The selection window is landfall minus 24 h to landfall
  plus 72 h, widened by 8 h on each side to absorb the local to UTC offset,
  and each selected tornado carries an in_core_window flag for the unwidened
  window. This widening is a known approximation and is stated here so the
  paper does not overclaim timing precision.
- TC association filter: a tornado is kept only if its start or end point
  lies within 800 km of the HURDAT2 storm centre interpolated to the tornado
  time (SPC local time used as an approximation to UTC for the interpolation;
  the centre moves at most one 6 h fix in that span, small against 800 km).
  This removes tornadoes from unrelated weather systems inside the window
  (for example, the unfiltered Ida window contained Iowa tornadoes).
- Path geometry: straight segment from SPC start to end lat/lon (end point
  falls back to the start point when SPC records 0), buffered by half the
  recorded path width on each side with flat caps. Widths convert from yards
  to metres at 0.9144. Where width is missing or zero, the median width of
  the tornado's decade is substituted and wid_flag_median is set true in the
  GeoJSON. Areas are computed in EPSG:5070 (CONUS Albers, metres).
- Resulting path sets (time window count, then after the 800 km filter):
  - Ida: 53 in window, 36 kept, total footprint 3,508.6 ha.
  - Ian: 16 in window, 16 kept, total footprint 773.1 ha.
  - Helene: 38 in window, 29 kept, total footprint 9,550.6 ha.
  - Milton: 45 in window, 45 kept, total footprint 13,366.6 ha.
- Outputs: data/paths_ida.geojson, data/paths_ian.geojson,
  data/paths_helene.geojson, data/paths_milton.geojson (buffered footprints),
  data/lines_*.geojson (centre lines), results/step1_landfalls.json,
  results/step1_log.txt.
- Note: files in data/ named hurdat2_tidy.parquet, spc_tornadoes_tidy.parquet,
  qualifying_gulf_tcs.csv and similar were produced by parallel work on other
  angles of this pitch, not by this pipeline, and were not used here.

## Step 2: wetland overlap and case selection

### NWI route taken

Routes were attempted in the order specified in the task:

1. USFWS NWI state downloads (task URL
   https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data).
   The direct state geodatabase URLs under www.fws.gov/wetlands/Data/
   State-Downloads/ (LA_geodatabase_wetlands.zip, FL_geodatabase_wetlands.zip)
   returned HTTP 403 to this environment's client on 2026-11-06, so route 1
   could not be completed from here.
2. NWI ArcGIS REST service (Wetlands Mapper). The legacy service endpoints
   at www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer returned
   HTTP 404 and fwshqservices.fws.gov closed connections from this client.
   The working REST route was the Esri Living Atlas USA Wetlands feature
   service, which republishes the USFWS National Wetlands Inventory with the
   original Cowardin ATTRIBUTE codes:
   https://services.arcgis.com/P3ePLMYs2RVChkJx/arcgis/rest/services/USA_Wetlands/FeatureServer/0
   Queries were run per tornado path bounding box (padded 0.03 degrees) with
   OBJECTID deduplication across paths. This is genuine NWI data served
   through an Esri republication, not the ESA WorldCover proxy, so route 3
   was not needed and no proxy claim issue arises. The manuscript should
   cite the data as USFWS National Wetlands Inventory accessed via the Esri
   Living Atlas USA Wetlands service, with this access route stated.

### Classification

From the NWI ATTRIBUTE (Cowardin) code:

- Marsh stratum (used for overlap): codes beginning E2EM, M2EM, E1EM or M1EM
  (estuarine or marine emergent wetland, labelled marsh_emergent_salt) plus
  E2SS or M2SS (estuarine or marine scrub-shrub, labelled scrub_shrub_salt;
  on the Florida Gulf coast this class is mostly mangrove fringe, which the
  paper should note where it matters).
- Woody wetland (kept separate, not in the marsh stratum): codes containing
  a forested class (FO).
- Fresh wetland (palustrine PEM, PSS, PFO) and all other classes were
  tracked in the logs but excluded from the marsh stratum.

### Overlap results and selection

Marsh area inside path footprints (EPSG:5070 areas) and paths crossing marsh:

| Storm | Paths | Footprint (ha) | Marsh in paths (ha) | Woody in paths (ha) | Paths crossing marsh | Decision |
|---|---|---|---|---|---|---|
| Ida 2021 | 36 | 3,508.6 | 79.75 | 0.00 | 9 | SELECT |
| Ian 2022 | 16 | 773.1 | 0.25 | 0.00 | 2 | DROP |
| Helene 2024 | 29 | 9,550.6 | 5.98 | 0.00 | 3 | SELECT, small sample flagged |
| Milton 2024 | 45 | 13,366.6 | 86.39 | 1.78 | 6 | SELECT |

- Ian is dropped: 0.25 ha of marsh across 2 of 16 paths cannot support a
  trajectory. Ian's tornadoes were concentrated inland and on the Atlantic
  side; the small marsh sliver its paths did cross lies on the North
  Carolina coast (bounds 78.3 W to 76.7 W, 33.9 N to 35.3 N), not in Florida.
- Geographic notes the paper should not get wrong: Ida's marsh crossings are
  not in Louisiana. Its Louisiana landfall zone produced no E2EM crossings in
  this path set; the 79.75 ha sit on the Mississippi Gulf coast and in
  Mid-Atlantic estuaries (Chesapeake and Delaware Bay salt marsh crossed by
  Ida remnant tornadoes on 2021-09-01). Helene's 5.98 ha are on the South
  Carolina coast near Charleston (about 80.2 W, 32.6 to 32.8 N), not in the
  Big Bend landfall zone. Milton's 86.39 ha span both Florida coasts
  (Sarasota area on the Gulf side and the St Lucie to Martin County area on
  the Atlantic side).
- Helene is retained at 5.98 ha but flagged: at 30 m HLS pixels that is at
  most about 66 footprint pixels before cloud and vegetation masking, so its
  trajectory is low-n by construction and must be reported as such.
- Outputs: data/nwi_bbox_*.geojson (all NWI polygons near each storm's
  paths), data/marsh_in_paths_*.geojson (marsh inside footprints),
  results/step2_overlap.json, results/step2_log.txt.

## Step 3: HLS NDVI trajectories

- Source: Microsoft Planetary Computer STAC
  (https://planetarycomputer.microsoft.com/api/stac/v1), collections
  hls2-s30 and hls2-l30 (HLS version 2.0), accessed 2026-11-06. S30 was
  preferred by design and dominates the available scenes in each zone
  bounding box over each 31 month window (search counts, saved in
  results/hls_sensor_mix.json): Ida S30 650 items, L30 278 (70 percent S30);
  Helene S30 169, L30 101 (63 percent); Milton S30 373, L30 98 (79 percent).
  Both collections enter every monthly median; the mix is therefore recorded
  here at window level rather than per month.
- Implementation note (transparency): the first implementation
  (code/step3_hls.py) built full-tile monthly raster composites and was
  killed by the runtime twice (once by SIGTERM after 2.2 h at 13 of 31 Ida
  months, once by the OOM killer at the same month) because the zones hold
  only hundreds to thousands of pixels while the composites processed whole
  HLS tiles. The delivered implementation (code/step3c_points.py) samples
  each scene at the zone pixels only (rasterio sample reads), which is the
  same monthly median composite restricted to the pixels that enter the
  statistics. Zone definitions are identical in both scripts. Monthly pixel
  values are cached in results/pixels_<storm>.npz so runs resume.
- Zones: footprint equals NWI marsh inside the path buffers. Where a storm's
  crossings form several clusters at 15 km linkage, the largest cluster is
  the analysis footprint and the rest is recorded as excluded: Ida 5 clusters,
  chosen Mississippi Gulf coast cluster 64.43 ha (excluded 15.32 ha in
  Mid-Atlantic estuaries); Milton 5 clusters, chosen Gulf coast cluster
  32.24 ha (excluded 54.15 ha on the Atlantic coast); Helene 1 cluster,
  5.98 ha. Reference equals NWI marsh 2 to 10 km from the marsh-crossing
  paths of the chosen cluster, nearest first, capped at the larger of three
  times the footprint area or 300 ha, minimum 8 polygons: Ida reference
  591.27 ha, Helene 541.36 ha, Milton 335.73 ha.
- Chosen cluster composition by NWI ATTRIBUTE code (from data/nwi_bbox
  files): Ida E2EM1P, E2EM1N, E2EM1Pd (salt marsh) with one E2SS1P polygon;
  Helene E2EM1N and E2EM1P (salt marsh); Milton E2SS3P and E2SS3Pd only,
  which is estuarine scrub-shrub broad-leaved evergreen, in Florida terms
  mangrove. Milton's trajectory is therefore a mangrove canopy trajectory
  (its NDVI runs 0.82 to 0.88), not a herbaceous marsh trajectory, and the
  manuscript must say so.
- Composites: monthly, from 6 months before to 24 months after landfall
  (31 months per storm). Per pixel per month, the median across clear scenes.
  Fmask masking removes cirrus (bit 0), cloud (bit 1), adjacent cloud
  (bit 2), cloud shadow (bit 3) and snow (bit 4). The Fmask water bit is not
  masked directly; instead the analysis mask is vegetated marsh, defined as
  pre-storm median NDVI above 0.2, which excludes open water (NDVI over open
  water is meaningless) and any pixel not vegetated before the storm. HLS
  water handling is therefore: water is excluded by the vegetation mask, and
  the NDWI series is reported alongside as a submergence check.
  NDVI equals (NIR minus Red) / (NIR plus Red) with NIR band B8A for S30 and
  B05 for L30. NDWI here is the McFeeters form (Green minus NIR) /
  (Green plus NIR) from bands B03 and the same NIR band.
  Vegetated pixel counts: Ida footprint 716, reference 6,508; Helene
  footprint 71, reference 5,474; Milton footprint 360, reference 3,734.
- Headline results (full series in results/marsh_trajectories.csv, per storm
  files results/trajectories_<storm>.csv, summary in
  results/marsh_summary.json):
  - Ida: immediate anomaly (first post-landfall composite, 2021-09) minus
    0.039 NDVI. Footprint NDVI fell from 0.568 (2021-08) to 0.487 while the
    reference moved 0.548 to 0.526. Against the pre-storm mean anomaly of
    plus 0.035, the landfall swing is about minus 0.074. Recovery slope over
    months 2 to 18 is minus 0.00006 per month (R2 0.0004, n 16), which reads
    as recovery already complete before the slope window: the anomaly is
    back to 0.000 by 2021-10 and within the pre-storm band thereafter.
    Footprint NDWI rose relative to reference at landfall (footprint minus
    0.550 to minus 0.501 against reference minus 0.552 to minus 0.535 from
    2021-08 to 2021-09), consistent with wetter or debris covered footprint
    pixels in the landfall month. No cloud gap months.
  - Helene: immediate anomaly (2024-10) plus 0.098, against a pre-storm mean
    anomaly of about plus 0.13. Footprint NDVI is flat through landfall
    (0.434 in both 2024-09 and 2024-10) and the reference is flat too. No
    damage signal is detectable. The footprint is only 71 vegetated pixels
    and sits about 0.1 NDVI above the reference marsh all year, so the design
    has low sensitivity for this storm; treat Helene as a null with a wide
    caveat, not as evidence of no effect. Recovery slope minus 0.0003 per
    month (R2 0.0004, n 16). No full cloud gap months, but two months rest on
    thin coverage (2025-08 footprint n 13; 2026-03 footprint n 12, reference
    n 1,474).
  - Milton (mangrove cluster): immediate anomaly (2024-11, the first monthly
    composite starting after the 2024-10-10 landfall) plus 0.012; the landfall
    month composite itself (2024-10, month offset minus 0.30) is minus 0.003.
    Pre-storm mean anomaly minus 0.004. No damage dip at any horizon.
    Recovery slope plus 0.0022 per month (R2 0.31, n 15) is an upward drift of
    the anomaly over months 2 to 18, not recovery from a measured drop.
    NDWI is flat through landfall (footprint about minus 0.77), so no
    submergence signal either. One cloud gap month: 2026-03 (scenes exist but
    too few clear vegetated pixels), recorded as missing in the CSV.
- Ian: dropped at Step 2 (0.25 ha marsh in paths). Recorded in
  results/marsh_summary.json with status dropped_insufficient_marsh.
- Environment note: during Step 3 the shared interpreter's environment broke
  once (system pandas became binary incompatible with a user-site numpy
  upgrade on this VM) and was repaired by installing pandas 2.3.3 into the
  TAC venv itself; this changed no data or method. Two long runs were also
  terminated by the runtime (SIGTERM at about 32 min on 2026-11-06 evening);
  the per month pixel cache made those losses recoverable.
- Outputs: results/marsh_trajectories.csv (93 rows, long form),
  results/marsh_summary.json, data/footprint_<storm>.geojson and
  data/reference_<storm>.geojson for ida, helene and milton,
  results/step3c_*_log.txt run logs, results/pixels_<storm>.npz caches.
