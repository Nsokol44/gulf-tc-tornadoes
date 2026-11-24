# Case results: Idalia (2023) and Florence (2018)

Every number the manuscript's case section (Section 3.5) needs, in the
same form as the existing cases. Method: Sections 2.4-2.5 and the
original pipeline (see `../README.md` for the parameter-by-parameter
fidelity notes and deviations D1-D5). Florence's trajectory is
HLS-equivalent (deviation D2: the Planetary Computer HLS v2 archive
begins 2020-01-01 and the LP DAAC HLS v2.0 archive requires an
Earthdata login; Florence was built from Planetary Computer
Sentinel-2 L2A + Landsat Collection 2 L2 with identical zones,
compositing, windows, masks, indices and statistics). All other
Florence numbers (paths, crossings, clusters, reference) come from the
unmodified original method.

## Table 6 form (case selection and trajectory results)

| Storm | Paths in case window | Footprint (ha) | Marsh crossed (ha) | Paths crossing | Analysed cluster (ha) | Reference (ha) | Veg. pixels (fp/ref) | Immediate anomaly | Slope, months 2-18 (per month) |
|---|---|---|---|---|---|---|---|---|---|
| Idalia 2023 | 13 | 527.0 | 88.8 | 5 | 85.4 salt marsh, GA coast | 2,138.7 | 936 / 23,451 | +0.046 (Sep 2023) | +0.00019 (no drop to recover from) |
| Florence 2018 | 36 | 2,767.7 | 81.4 | 5 | 45.0 salt marsh, NC Pamlico coast | 1,410.0 | 499 / 15,672 | +0.041 (Oct 2018) | +0.00082 (no drop to recover from) |

Immediate anomaly is footprint minus reference NDVI in the first
monthly composite beginning after landfall. Idalia's pre-storm mean
anomaly was +0.016, Florence's +0.029.

## Idalia (2023), AL102023

Landfall anchor: 2023-08-30 11:45 UTC, 29.9 N, 83.6 W (Keaton Beach,
Florida; the storm's only HURDAT2 L fix at or above 25 N).

- Tornadoes in the case window: 13 paths; total path footprint 527.0 ha.
- Paths crossing marsh: 5 of 13.
- Total marsh crossed: 88.8 ha (88.7 ha herbaceous emergent, 0.2 ha
  woody scrub-shrub). Matches the screening table (88.8 / 88.7 / 0.2).
- Clusters: 4 at 15 km linkage. Analysed cluster: 85.4 ha (85.2 ha
  herbaceous, 0.2 ha woody) of E2EM salt marsh on the Georgia coast in
  Glynn County, around the Altamaha River delta near Brunswick
  (centroid 81.54 W, 31.20 N), crossed by 2 paths. Excluded crossed
  marsh: 3.4 ha in three smaller clusters.
- Reference area: 2,138.7 ha (8 NWI polygons; the original
  minimum-8-polygons rule overrides the 300 ha cap, deviation D3).
- Vegetated pixels: footprint 936, reference 23,451.
- Pre-storm NDVI (mean of the seven pre-storm composites, Feb-Aug
  2023): footprint 0.427, reference 0.411; pre-storm mean anomaly
  +0.016. In the last pre-storm composite (Aug 2023): footprint 0.446,
  reference 0.436.
- Landfall composite (Sep 2023): footprint NDVI 0.447, reference
  0.401; anomaly +0.046. The footprint did not fall (0.446 to 0.447);
  the anomaly is positive because the reference dipped.
- Swing (immediate anomaly minus pre-storm mean anomaly): +0.031.
- Following month (Oct 2023): anomaly +0.032. No damage dip at any
  horizon.
- NDWI across landfall (Aug to Sep 2023): footprint -0.416 to -0.417,
  reference -0.408 to -0.372; NDWI anomaly change -0.037. No
  submergence signal in the footprint.
- Recovery slope, months 2-18: +0.00019 per month (R squared 0.007,
  n = 16). There is no measured drop, so this is background drift of
  the anomaly, not recovery.
- Companion within-path score: scar share 0.020 (2.0 percent of
  vegetated footprint pixels with a control-relative NDVI drop of at
  least 0.15, pre-storm mean to the Sep 2023 composite; reference mean
  drop +0.010). Below the companion study's 0.10 detection threshold.
- Placebo / power: 200 placebo footprints in the untouched reference
  marsh (seed 20261124) gave swings from -0.055 to +0.057 (median
  -0.005, interquartile range -0.018 to +0.018, SD 0.025). The
  observed swing (+0.031) sits inside that range (86 percent of draws
  at or below it). The detectable swing at the 5 percent level is
  -0.041 (placebo 2.5th percentile): an Ida-magnitude swing (-0.074)
  lies beyond every placebo draw and would have been detected.
- Cloud-gap months: none. Sampled scenes: 173 S30, 219 L30.
- **Classification: null.** A powered null, not an underpowered case:
  85.4 ha analysed and 936 footprint pixels, with a placebo noise
  scale small enough to have caught the Ida signal.

In the form of the existing case paragraphs: Idalia's 13 case-window
paths crossed 88.8 ha of marsh on five paths. The analysed cluster is
85.4 ha of Georgia coast salt marsh (E2EM) near the Altamaha delta,
with a further 3.4 ha crossed in three smaller clusters excluded by
the one-marsh-system rule. Through the 2023 season the footprint marsh
ran slightly greener than the reference (pre-storm mean anomaly
+0.016). In the landfall composite (September 2023) footprint NDVI was
unchanged (0.446 to 0.447) while reference NDVI fell from 0.436 to
0.401, an anomaly of +0.046 and a swing of +0.031 against the
pre-storm offset: there is no damage dip at any horizon, NDWI shows no
footprint submergence signal, and the companion within-path scar share
is 0.020. The null is informative at this footprint scale, because the
placebo distribution for this marsh (200 draws, SD 0.025) would have
detected a swing of -0.041 or larger, and Ida's -0.074 lies beyond all
200 draws.

## Florence (2018), AL062018 — HLS-equivalent trajectory (deviation D2)

Landfall anchor: 2018-09-14 11:15 UTC, 34.2 N, 77.8 W (Wrightsville
Beach, North Carolina; the storm's only HURDAT2 L fix at or above
25 N in the union longitude range).

- Tornadoes in the case window: 36 paths; total path footprint
  2,767.7 ha.
- Paths crossing marsh: 5 of 36.
- Total marsh crossed: 81.4 ha, all herbaceous emergent (0.0 ha
  woody). Matches the screening table (81.4 / 81.4 / 0.0).
- Clusters: 3 at 15 km linkage. Analysed cluster: 45.0 ha of E2EM
  salt marsh on the Pamlico Sound shore in Hyde County, North
  Carolina (centroid 76.34 W, 35.39 N), crossed by 2 paths. Excluded
  crossed marsh: 36.4 ha in two smaller clusters (35.8 ha and 0.6 ha).
- Reference area: 1,410.0 ha (8 NWI polygons; minimum-8-polygons rule,
  deviation D3).
- Vegetated pixels: footprint 499, reference 15,672.
- Pre-storm NDVI (mean of the seven pre-storm composites, Mar-Sep
  2018; the September composite begins before the 14 September
  landfall and is counted pre-storm by the pipeline's month-start
  rule, as with Milton's landfall-month composite in the original):
  footprint 0.452, reference 0.423; pre-storm mean anomaly +0.029.
  In the September 2018 composite itself: footprint 0.510, reference
  0.484, anomaly +0.025.
- First composite beginning after landfall (Oct 2018): footprint NDVI
  0.521, reference 0.480; anomaly +0.041. Footprint NDVI rose through
  landfall (0.510 to 0.521).
- Swing: +0.011.
- Following month (Nov 2018): anomaly +0.035. No damage dip at any
  horizon.
- NDWI across landfall (Sep to Oct 2018): footprint -0.527 to -0.561,
  reference -0.518 to -0.542; NDWI anomaly change -0.009. No
  submergence signal.
- Recovery slope, months 2-18: +0.00082 per month (R squared 0.068,
  n = 16). Background drift, not recovery; there is no measured drop.
- Companion within-path score: scar share 0.006 (0.6 percent;
  reference mean drop -0.057, that is, the reference greened up on
  average). Far below the 0.10 detection threshold.
- Placebo / power: 200 placebo footprints (seed 20261124) gave swings
  from -0.128 to +0.074 (median +0.019, interquartile range -0.024 to
  +0.044, SD 0.047). The observed swing (+0.011) is central (47.5
  percent of draws at or below it). The detectable swing at the
  5 percent level is -0.104 (placebo 2.5th percentile), so this
  marsh's month-to-month heterogeneity is roughly twice Ida's and
  Idalia's, and an Ida-magnitude swing (-0.074) would not have cleared
  the placebo criterion here.
- Cloud-gap months: none. Sampled scenes: 375 Sentinel-2 L2A, 248
  Landsat C2 L2 (the HLS-equivalent mix, deviation D2).
- **Classification: null, with limited sensitivity.** No damage signal
  in the point estimates (positive anomaly and swing, scar share at
  background), on 45.0 ha and 499 footprint pixels; but the wide
  placebo distribution means an Ida-size effect cannot be excluded.
  The case sits between Helene (6.0 ha, 71 pixels, underpowered) and
  Idalia (85.4 ha, 936 pixels, powered null).

In the form of the existing case paragraphs: Florence's 36 case-window
paths crossed 81.4 ha of marsh on five paths. The analysed cluster is
45.0 ha of Pamlico Sound salt marsh (E2EM) in Hyde County, with a
further 36.4 ha crossed in two smaller clusters excluded by the
one-marsh-system rule. The footprint marsh ran greener than its
reference all year (pre-storm mean anomaly +0.029), footprint NDVI
rose through landfall (0.510 in September 2018 to 0.521 in October),
the first post-landfall anomaly is +0.041 with a swing of +0.011, and
NDWI is flat. There is no damage dip at any horizon and the companion
scar share is 0.006. Unlike Idalia, though, the placebo swings for
this marsh are wide (SD 0.047), so the case is reported as a null with
limited sensitivity rather than as evidence that an Ida-size signal
was absent. The trajectory is HLS-equivalent, not HLS (deviation D2),
and the manuscript should say so wherever Florence's numbers are used.

## Files behind these numbers

- `summary_idalia.json`, `summary_florence.json`, `summaries.json` —
  full per-storm summary statistics, including placebo distributions.
- `trajectories_idalia.csv`, `trajectories_florence.csv` — the
  31-month footprint/reference NDVI, NDWI and anomaly series.
- `placebo_idalia_swings.csv`, `placebo_florence_swings.csv` — the
  200 placebo swings per storm (seed 20261124).
- `classifications.json` — classification and basis per storm.
- `../data/` — path footprints, marsh-in-paths, analysed-cluster and
  reference GeoJSONs.
