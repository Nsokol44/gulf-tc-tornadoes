# Build log — Angle 2: Gulf Coast TC tornadoes revisited

Built 2026-11-06. All analysis is real data only; every script is in
`code/` and rerunnable; stochastic steps use
`numpy.random.default_rng(20261106)`.

## Climatology (code/01–06, run_all.py)

- Inputs (data/): HURDAT2 `hurdat2-1851-2025-092326.txt` (through the
  2025 season), SPC tornado CSV 1950–2025, TCTOR public workbook
  `tctor.xls` (1,783 rows, through 2023; no newer public release exists).
- Primary sample: TCTOR rows for qualifying Gulf TCs (landfall fix
  98.5W–81.0W at lat ≤ 31.5N, or classified fix in the Gulf box
  24–31.5N) with the Moore et al. (2017) zero-width edit (8 Gulf records
  dropped); the 2024–2025 seasons are attributed by the Moore and Dixon
  (2011) rule and flagged `attribution_source`. The 2017 paper states no
  numeric association rule of its own (sample inherited from TCTOR);
  see manuscript/methods_recovery.md.
- Outputs: results/tc_tornadoes.parquet (1,701 rows),
  results/climatology_tables.md, results/climatology_summary.json,
  results/climatology_provenance.md.

## Marsh remote sensing (code/step1–step3c)

- Tornado paths from SPC/DAT segments; NWI polygons via the Esri Living
  Atlas USA Wetlands FeatureServer (USFWS state downloads returned 403
  and the legacy mapper 404 from this environment; the Living Atlas
  service republishes NWI with Cowardin codes).
- HLS v2.0 (S30+L30) via Microsoft Planetary Computer STAC, monthly
  median composites from 6 months before to 24 months after landfall,
  Fmask masked, vegetated mask pre-storm NDVI > 0.2; Python environment
  ~/workspace/papers-finish/urban-heat-tac/.venv.
- Outputs: results/marsh_trajectories.csv, results/marsh_summary.json,
  results/marsh_provenance.md, data/footprint_<storm>.geojson,
  data/reference_<storm>.geojson.
- Correction recorded in results/CORRECTION_milton_coast.md: the
  analyzed Milton cluster is on the Atlantic coast (St. Lucie–Martin),
  verified from footprint geometry; an early provenance sentence had
  the coasts swapped. Manuscript follows the geometry.

## Figures (code/make_figures.py)

fig1 climatology map, fig2 era comparison, fig3 case marsh maps,
fig4 NDVI trajectories. Liberation Serif (metric Times New Roman
substitute; the DOCX text itself is Times New Roman throughout),
≤ 6.85 in wide, 300 dpi PNG + PDF, shared legends above multi-panel
figures. All four PNGs were visually inspected on 2026-11-06 (fig1
legend/marker balance and fig3 footprint rendering reviewed; fig4
re-rendered with anomaly axis −0.34 to 0.38 so no point clips).

## Manuscript (manuscript/build_manuscript.py)

- Outputs manuscript/Sokol_TCTornadoes_PhysGeogr_Manuscript.docx/.md.
- Abstract 189 words (limit 200). 26 references, all existence-verified
  (manuscript/references_verified.md) and all cited in text (closure
  checked programmatically). Zero em dashes; semicolons remain only
  inside citation parentheses and one DOI. American spelling (a
  preflight dialect finding of 24 British spellings was corrected in
  the builder and in make_figures.py and re-verified).
- DOCX audit: every font reference in every XML part (document, styles,
  theme, fontTable, math font) is Times New Roman; all text black
  (themeColor stripped, no non-black color values); creator metadata
  "Nicholas J. Sokol"; 6 tables; 4 figures embedded.
- Preflight (Manuscript Builder pf wrapper, profile "nick", check →
  fix → recheck) run 2026-11-06: final audit 0 errors. Remaining
  warnings are storm-name false positives (Harvey 2017, etc.) and one
  reference-order note: pf sorts same-author entries by title, the
  manuscript keeps Taylor & Francis Harvard order (author, then year),
  deliberately. The pf-fixed file was verified text-identical to the
  builder output (148/148 paragraph and table-row texts) and adopted
  as the delivered DOCX.
- Every headline number in the text was cross-checked against
  results/climatology_summary.json and results/marsh_summary.json.

## Figure revision (2026-11-06, Nick's feedback: maps need state
boundaries, proper projections, and a satellite imagery figure)

Figures-only revision: no data, result, table value, or text number
changed. The abstract is unchanged at 189 words.

- Cartography pass (code/make_figures.py): Figures 1 and 3 are now
  drawn in the CONUS Albers Equal Area projection (EPSG:5070)
  instead of unprojected longitude-latitude. Both carry state
  boundaries with state labels, a light land/water basemap, a
  graticule with coordinate tick labels, a scale bar, and a
  true-north arrow rotated for meridian convergence at each map's
  centre. Figure 1 adds labelled coastal cities (Houston, New
  Orleans, Mobile, Pensacola, Tampa, Jacksonville, Charleston,
  Atlanta) and a Gulf of Mexico label; its point symbology is
  unchanged. Figure 3 was relaid out to fit the data shapes (Ida's
  alongshore window full width on top, Helene and Milton side by
  side below), with Bay St. Louis, Gulfport and Charleston labelled;
  its layer symbology is unchanged except that the analyzed
  footprint is now a haloed outline only, so the marsh within
  tornado paths stays visible beneath it. Boundary data: Natural
  Earth 1:10m admin-1 states and provinces and 1:10m land,
  downloaded 2026-11-06 from the Natural Earth CDN
  (naciscdn.org) into data/ne_10m_admin_1_states_provinces.zip and
  data/ne_10m_land.zip; the 1:10m coastline from the original build
  is retained.
- New Figure 4, satellite imagery (code/fetch_ida_imagery.py,
  code/make_fig_imagery.py): HLS version 2.0 Sentinel-2 (S30)
  monthly median composites for August 2021 (pre-landfall) and
  September 2021 (first composite beginning after the 29 August
  2021 landfall) from the Microsoft Planetary Computer STAC,
  accessed 2026-11-06, built with the same Fmask masking and
  monthly median definition as the trajectory analysis (Section
  2.5). 19 scenes for August (3 to 30 August) and 20 for September
  (2 to 27 September) across tiles T15RYP and T16RBU; scene list in
  results/hls_ida_scenes.json. Panels: (a) August true colour,
  (b) September true colour with an identical joint stretch,
  (c) NDVI change over vegetated pixels against the August
  composite in grey, with the analyzed footprint, tornado path
  centrelines and reference marsh overlaid, a projected Gulf Coast
  locator inset, a scale bar and a north arrow. The panels show the
  western, Pearl River mouth group of the footprint (8 of 18
  polygons, 30.7 of 64.4 ha), the largest of its three alongshore
  groups, chosen by area before the imagery was inspected.
  Helene and Milton chips were not added: Helene's footprint is 71
  vegetated pixels and Milton's is mangrove with a saturated index,
  so neither can carry a readable pre/post panel at this scale.
- Imagery cross-check (a check, not new results): raster monthly
  medians over the footprint polygons give mean NDVI 0.566 for
  August and 0.492 for September, a change of -0.074, against the
  analysis pipeline's 0.568, 0.487 and -0.074 landfall swing
  (721 versus 716 vegetated pixels; S30-only rasters versus
  S30+L30 point sampling explains the small differences). By
  group, the change is -0.113 west, -0.050 middle, -0.026 east:
  the panelled west group carries the strongest signal.
- Build note: the first fetch attempt over the full 55 km
  footprint span was OOM-killed on this shared VM, and a retry was
  interrupted by a runtime restart after writing the west August
  composite; the delivered fetch composites per group window and
  resumes from written TIFFs. Composites are in results/hls_ida_*.
- Integration: the NDVI trajectory figure is renumbered from
  Figure 4 to Figure 5 (files renamed fig5_ndvi_trajectories),
  the Ida results paragraph now cites Figures 4 and 5, and the
  captions of Figures 1 and 3 gained projection and boundary
  source sentences (plus a capitalization fix in the Figure 1
  caption). figures/captions.md updated to match. Nothing else in
  the text was touched.
- QA: all five figures visually inspected at full size (legend
  placement, label collisions, panel alignment, inset labels all
  checked; two rounds of fixes). Preflight (pf, profile "nick",
  check, fix, recheck): 0 errors, and the pf-fixed DOCX was
  verified text-identical to the builder output (150 of 150
  paragraph and table-row texts); remaining warnings are the
  pre-existing classes from the original build (typed bullets in
  the Conclusions list, inline italic, metadata). DOCX XML audit:
  every font reference is Times New Roman (the only other tokens
  are en-US and ja-JP language tags), all text black, creator
  Nicholas J. Sokol. The rebuilt DOCX was also rendered to PDF
  and its figure pages inspected.

---

## 2026-11-07 — Fix programme (author's review): extension rule swap, Milton ranking, Ida placebo, voice, cross-citation

### Ida marsh placebo: DESIGN (logged before running)

Question. The Ida marsh headline is a single-month swing: the
footprint-minus-reference NDVI anomaly in September 2021 (−0.039)
minus its pre-storm mean over February to August 2021 (+0.035),
a swing of −0.074. It carries no uncertainty statement. The
placebo test asks how large a swing the same arithmetic produces
in marsh that Ida's tornadoes did not touch.

Design (fixed before any placebo output was seen):
- Data: the pipeline's own per-pixel monthly NDVI arrays
  (results/pixels_ida.npz), months 2021-02 to 2021-09, and the
  pipeline's point grid, rebuilt exactly as code/step3c_points.py
  build_zones constructs it from data/footprint_ida.geojson and
  data/reference_ida.geojson. The rebuild is verified before use:
  it must reproduce 716 footprint points and 6,591 reference
  points, and zone means recomputed from the npz arrays with the
  step3e vegetation mask (per-pixel pre-storm median NDVI > 0.2,
  pre-storm = months starting before landfall 2021-08-29) must
  reproduce results/trajectories_ida.csv (footprint 716 and
  reference 6,508 vegetated pixels; Aug 2021 means 0.568/0.548;
  Sep 2021 means 0.487/0.526).
- Pseudo-footprints: 200 draws. Each draw picks one vegetated
  reference pixel uniformly at random (numpy default_rng, seed
  20261107) and takes that pixel and its 715 nearest vegetated
  reference pixels (Euclidean distance in the grid's UTM
  coordinates) as a pseudo-footprint of 716 pixels, the same
  vegetated-pixel count as the observed Ida footprint cluster.
  Scattered random pixels are NOT used: a pseudo-footprint must
  be one spatially coherent patch, as the real footprint is, so
  that spatial correlation inside the patch is preserved.
  Pseudo-reference: the remaining vegetated reference pixels.
- Estimand per draw, identical arithmetic to the pipeline:
  monthly zone means over finite vegetated pixels; anomaly =
  pseudo-footprint mean minus pseudo-reference mean; swing =
  September 2021 anomaly minus the mean anomaly over February
  to August 2021.
- Reporting: median, interquartile range and 2.5 to 97.5
  percentile range of the 200 placebo swings; the percentile of
  the observed swing (−0.0736, computed from the trajectory
  table as −0.0386 minus +0.0350); the share of placebo swings
  at or below the observed value.
- Decision rule, fixed in advance: if fewer than 5 percent of
  placebo swings are at or below the observed swing, the Ida
  swing is reported as clearing the placebo distribution and
  the uncertainty statement says so with the percentile. If
  not, the manuscript claim is reframed to state plainly that
  the observed swing does not clear the placebo distribution,
  and the marsh result is presented as suggestive only.
- Script: code/placebo_ida.py; output:
  results/placebo_ida.json (summary) and
  results/placebo_ida_swings.csv (all 200 draws).

### Amendment to the placebo design (logged before running, same day)

The verification step failed: the pipeline's exact point grid
cannot be reproduced from the current files. code/step3c_points.py
was modified at 16:43 on 2026-11-06, after the extraction run that
wrote results/pixels_ida.npz (16:10), and a rebuild with the
current build_zones construction gives 723 footprint and 6,585
reference points against the pipeline's 716 and 6,591 (grid
variants all_touched, arange endpoint and transform origin were
also tried; none reproduces the counts). The design is therefore
amended in one respect only, the source of patch coordinates:

- Pixel VALUES come from the pipeline's own arrays
  (results/pixels_ida.npz), which are exact pipeline outputs and
  need no grid: the reference block is rows 716 to 7306 (6,591
  pixels). Hard value-side checks, run before any draw: the
  step3e vegetation mask recomputed from the npz (per-pixel
  pre-storm median NDVI > 0.2) returns exactly 6,508 vegetated
  reference pixels, and monthly reference zone means recomputed
  from the npz reproduce results/trajectories_ida.csv.
- COORDINATES for patch coherence come from the rebuilt grid
  (same bounds, 30 m step and scan order as the pipeline
  construction). Its reference set differs from the pipeline's
  by at most 13 of about 6,590 cells, all at polygon edges.
  npz reference rows are paired to rebuilt reference coordinates
  by scan-order rank; the six unpaired npz rows stay in the
  pseudo-reference pool. A patch of 716 pixels can therefore
  include at most a handful of pixels whose coordinates are
  shifted by one cell, each of them a real marsh pixel from the
  same edge. This cannot move a 716-pixel patch mean materially
  and is stated here openly rather than hidden.
- The observed swing is taken from the pipeline's trajectory
  table (-0.0736), not from any rebuilt grid. Draws, patch size,
  estimand, seed and the 5 percent decision rule are unchanged.

### Fix programme outcomes (same day)

FIX 1, extension rule swap. code/05_build_primary_sample.py now
builds the 2024 to 2025 extension rows from the 800 km operational
rule (results/tc_tornadoes_op800.parquet) instead of the Moore and
Dixon rule; code/06_analyse_climatology.py labels and provenance
updated to match; pipeline rerun (05, 06, make_figures). Study era
untouched. Old to new headline numbers (MD2011 primary to 800 km
primary):
- Pooled sample: 1,701 tornadoes / 96 storms to 1,745 / 97.
- Extension era: 501 / 34 storms to 545 / 35; TC share of all US
  tornadoes 3.8 to 4.1 percent; deaths 11 to 12; injuries 77 to 93.
- 2024 total: 132 to 176 (all rule-attributed); 2025 still zero.
- Beryl 2024: 60 (12.0 percent of era) to 68 (12.5 percent), the
  same count the SPC reports nationally.
- Milton 2024 primary: 42 to 45 (MD2011 42; strong 9, deaths 6,
  injuries 14 unchanged).
- Helene 2024 primary: 16 to 31 (MD2011 16; strong 0 to 2,
  injuries 0 to 16, deaths 2 unchanged).
- Extension weak/strong: 93.0/7.0 (487 rated, 14 unrated) to
  92.4/7.6 (528 rated, 17 unrated). EF0 share 55.2 to 54.0
  percent; EF3 count 5 (1.03 percent) to 7 (1.33 percent).
- Extension medians: length 2.61 (0.87 to 6.96) km to 2.54 (0.84
  to 6.94); width 68.6 (45.7 to 146.2) m to 68.6 (45.7 to 137.2);
  DPI median 0.123 unchanged.
- Pooled quadrants: NE 68.1 to 68.2, SE 27.6 to 27.4, SW 0.5 to
  0.6, NW 3.8 unchanged; east half 95.7 to 95.6; east-of-center
  71.1 to 70.8; extension NE 74.5 to 74.3, NW 1.2 to 1.5;
  south-of-center pooled 113 to 115 (Rita 38 unchanged).
- Coast bins pooled: 57.9 to 57.8 (0 to 100 km), 14.8 to 15.1
  (100 to 200), 11.5 unchanged (200 to 300), 15.8 to 15.6 (over
  300); median centre range 312 (204 to 411) km to 316 (207 to
  414). Extension bands: coast 61.5 to 60.9, 100 to 200 km 8.4 to
  9.9, far inland 19.2 to 18.3 percent.
- Figure 1 domain counts: 1,463 of 1,701 in domain (238 out) to
  1,479 of 1,745 (266 out). [Corrected 2026-11-07 after delivery:
  an interim figure-run report of 1,488/257 was used in the first
  rebuilt caption; the figure script's own printed line and a
  direct recount of the primary parquet against the map extent
  (-99 to -79, 24 to 39) both give 1,479 in domain and 266 out.
  Caption, captions.md, manuscript and Drive copies corrected.]
- Tables 1, 2, 3, 4, 5, abstract, Sections 2.2, 3.1 to 3.4,
  Discussion and Conclusions all chased to the new numbers.
  Section 2.2 rewritten: the 800 km rule is now presented as the
  primary extension rule chosen on its 93.9 percent overlap
  recall, MD2011 (33.7 percent) demoted to the sensitivity case,
  and the old "our 2024 to 2025 counts are conservative" framing
  removed. Two consistency catches during the chase: fig2() in
  code/make_figures.py carried HARDCODED quadrant shares from the
  old run (extension 74.45/23.95/0.40/1.20); it now reads
  quadrants_true_north_by_era from the regenerated summary JSON,
  and Figure 2 panel b matches Table 4 exactly (74.3/23.7/0.6/
  1.5). Also corrected a pre-existing slip in Section 3.4 ("ten
  TCTOR years" to "eight TCTOR years"; the extension era has
  eight TCTOR years, 2016 to 2023, plus two rule years).

FIX 2, Milton claim. Verified three ways. The Florida Climate
Center post-storm report (Powell 2024, added to the references)
counts 47 confirmed tornadoes in Florida on 9 October 2024, the
largest TC tornado outbreak in Florida on record, with six EF2
and three EF3, matching this sample's nine strong Milton
tornadoes. Against all-US TCTOR storm totals for 1995 to 2023
(nine storms above 46: Ivan 118, Frances 103, Rita 97, Katrina
59, Harvey 52, Gustav 49, Fay 49, Georges 48, Cindy 48) plus
Beryl's 68 in 2024, Milton's 46 (SPC national count) ranks 11th
since 1995. The Introduction now reads "the largest tropical
cyclone tornado outbreak in Florida on record and roughly the
eleventh most prolific from a United States tropical cyclone
since 1995", and Section 3.1 cites Powell (2024) for the nine
strong tornadoes. (The AccuWeather analysis page itself is
policy-blocked in the sandbox browser and could not be fetched;
the ranking was verified independently from TCTOR and the SPC
2024 counts, which is stronger than citing the article.)

FIX 3, Ida placebo. Ran as designed (code/placebo_ida.py;
results/placebo_ida.json, results/placebo_ida_swings.csv), after
the logged amendment on pixel coordinates (value-side checks
passed exactly: footprint block is 717 npz rows of which 716
vegetated, reference vegetated 6,508, and both zone-mean series
reproduce trajectories_ida.csv to 1e-9 for Feb to Sep 2021).
Outcome: placebo swings (n = 200) median -0.002, IQR -0.011 to
+0.010, range -0.031 to +0.055. The observed swing -0.0736 lies
outside the entire placebo distribution (share at or below
observed = 0.000; empirical p below 0.005). The claim therefore
stands as written, and the uncertainty statement was added in
Section 3.5, the Figure 5 caption, the abstract and Conclusion
4: the swing clears the placebo distribution, so it is not a
draw from ordinary month-to-month marsh variability at this
patch scale.

FIX 4, voice. All authorial we/our/us converted to first-person
singular (about 45 instances) with verb and possessive agreement
checked per instance. Judgment calls: NO community "we" was
retained; every instance in the draft was authorial. (The only
remaining "our" strings in the source are inside "All US
tornadoes" table headers and the US Fish and Wildlife Service
reference.) Verification: grep sweep of the builder and of the
built MD is empty, and the pf audit voice table reports
first-person (we/our/us) = 0 and em dashes = 0. The builder
docstring's style line now reads first-person singular.

FIX 5, cross-citation and wetland reconciliation. New paragraph
at the end of Section 3.5 contrasting the two methods
(within-path per-pixel scar share against a matched control ring
in Angle 1 versus whole-polygon zone-mean NDVI anomaly here),
concluding the per-pixel scar exists in wetland vegetation but
a marsh-zone mean registers it only at footprint scale, with the
Milton mangrove null consistent with both. Angle 1 is cited as
Sokol (2026) with a reference entry in Springer-style
in-pipeline form: "Sokol NJ (2026) Seeing the unreported storm:
Landsat/Sentinel-2 damage-path detection and the observation
bias of the Southeast tornado record. Manuscript submitted to
the International Journal of Remote Sensing." Venue written as
International Journal of Remote Sensing per the tasking; it is
a one-line swap if the venue pick changes.

FIX 6, authorship. Title page (DOCX and MD builders) now carries
the sole author block only (Nicholas J. Sokol, Teaching
Assistant Professor, Department of Geography and
Sustainability, University of Tennessee, Knoxville;
nsokol@utk.edu; ORCID 0000-0002-4798-0056). The "Draft
manuscript prepared for discussion with Todd W. Moore" line is
removed from both builders; verified on the rendered title page.

FIX 7, cover letter. None existed in the package. Drafted
manuscript/Sokol_TCTornadoes_PhysGeogr_CoverLetter.docx (+ .md,
builder build_cover_letter.py). It leads with the marsh half
(satellite audit of marsh crossings, Ida 64.4 ha, one-month
recovery, placebo support, honest detection limits) and frames
the climatology as a replication of Moore, Sokol and Blume
(2017), noting the collaboration's earlier Physical Geography
paper (Moore, Dixon and Sokol 2016). Standard no-grant funding
declaration, GitHub-only availability, no competing interests;
the abstract's numbers are not repeated wholesale (the only
figure carried is the 64.4 ha marsh footprint). Nothing was
submitted anywhere.

FIX 8, final QA. Abstract 196 words (builder count, limit 200).
pf preflight (profile nick, run): fix stage leaves only the two
known recurring classes (TYPED-BULLETS in the Conclusions list,
METADATA info); audit 0 errors, 2 warnings (storm-name
author-year false positives), 6 info; the pf-fixed DOCX verified
text-identical to the builder DOCX (152 of 152 paragraph and
table-row texts) and promoted to the deliverable name. DOCX XML
audit of both deliverables: every font reference Times New
Roman at run, style, fontTable and theme level (the only other
tokens are en-US and ja-JP language tags), all text black
(w:color 000000 throughout), metadata creator Nicholas J.
Sokol. One pre-existing audit note, not introduced here: pf
flags the Edwards entries in the reference list as near-
alphabetical (single-author 2024 before multi-author 2013/2022,
the order the list has always carried). Figures 1 and 2 visually
inspected after rebuild (shared legend above the panels, no
collisions; Figure 2 panel b labels now match Table 4).
Title page rendered to PDF and inspected. Deliverables replaced
in the same Drive folder (1xiZmWKj-1ip08zWsi7F3MR2lc318nCrH)
and verified by listing.

---

## 2026-11-08 — Third fix round (author's own review of the Drive copies)

FIX 1, marsh placebo construction audit. The author's concern was
that the 200 pseudo-footprints, drawn from the reference marsh,
might have been differenced against a reference that still
contained their own pixels, damping the placebo swings and
overstating the p-value. Verdict: the construction was already
correct; no rerun was needed and no number moved. Code evidence,
code/placebo_ida.py draw loop: for each draw the patch rows are
removed from the reference pool before differencing
(`rest_rows = np.setdiff1d(ref_veg_rows, patch_rows)`), and the
monthly anomaly is `zone_mean(patch_rows) - zone_mean(rest_rows)`
on those remaining pixels. Leave-one-out differencing was
therefore in force for all 200 draws, and the observed swing
-0.0736 with zero exceedances stands as computed. Section 3.5 now
states the exclusion explicitly ("In each draw the patch's own
pixels were removed from the reference before the differencing,
so no pseudo-footprint was compared against marsh that included
itself").

FIX 2, p-value format. With 200 draws and zero exceedances the
empirical p is (0+1)/(200+1) = 1/201, so "(empirical p below
0.005)" in Section 3.5 now reads "(empirical p ≤ 0.005)". That
was the only p-value instance in the manuscript; the cover letter
carries no p-value and needed no change.

FIX 3, Milton ranking: author's claim checked and NOT sustained;
no change made. The author held that the eleventh-place ranking
covers all hurricanes on record and that Milton ranks higher
since 1995. Recount on the paper's own basis (full TCTOR current
release, all 1,783 rows, storm totals 1995 to 2023, no Gulf
filter): exactly nine storms exceed 46 (Ivan 118, Frances 103,
Rita 97, Katrina 59, Harvey 52, Gustav 49, Fay 49, Georges 48,
Cindy 48; next are Florence 44 and Jeanne 42). Adding Beryl's 68
from 2024 gives ten storms above Milton, so Milton ranks 11th
since 1995, robust for any reported Milton total of 45 to 47
(NHC TCR: 45 on land plus a waterspout; SPC commonly 46; Powell
2024 counts 47 in Florida on 9 October). The count is also
consistent with the contemporaneous SPC-based reporting (USA
TODAY, 19 October 2024, quoting Edwards: 41 confirmed put Milton
13th on the 1995 list including Beryl, 42 made 12th tied with
Jeanne; the final 45 to 46 lifts him past Florence 44 and Jeanne
42 to 11th). All-time compilations put him lower, not at 11th:
the Hurricaneville all-time table (NOAA, NHC, Tornado Project,
Weather Channel sources) lists eleven storms above 46 with
Milton 12th, and fuller merged bases (adding Fay at 49 to 50 and
Cindy at 48 on the TCTOR basis) put him 13th to 14th. The
Introduction sentence "roughly the eleventh most prolific from a
United States tropical cyclone since 1995" is therefore correct
as written and is unchanged.

FIX 4, era strong-share test. Exact counts from
results/climatology_summary.json: study era 77 strong of 1,200
rated (6.42 percent), extension era 40 of 528 rated (7.58
percent). Two-proportion z test: difference +1.16 percentage
points, z = 0.88, two-sided p = 0.38; Newcombe 95 percent
confidence interval for the difference -1.3 to +4.0 points. The
interval includes zero, so Section 3.2 now reports the shares as
statistically indistinguishable with the test stated (difference
+1.2 points, 95 percent confidence interval -1.3 to +4.0,
p = 0.38).

FIX 5, typo. Introduction: "surface and upper-air analyzes" now
reads "surface and upper-air analyses" (the plural noun; the
instance the author flagged). Consequence noted: the pf check
shows one SPELLING-MIX warning, the single British-form token
against the paper's American profile, which is exactly this
ordered change; "analyses" is also the correct plural noun in
American spelling, where "analyzes" is a verb form.

QA. Abstract recounted from the DOCX at 196 words (limit 200),
unchanged by this round. pf preflight (profile nick, run): 0
audit errors; the pf-fixed DOCX verified text-identical to the
builder DOCX (152 of 152 paragraph and table-row texts) and
promoted to the deliverable name. Remaining warnings are the
known classes (storm-name author-year false positives, the
deliberate Taylor & Francis Harvard reference order, typed
bullets in the Conclusions, metadata info) plus the SPELLING-MIX
token from Fix 5. DOCX XML audit: every font reference Times New
Roman, all run colors 000000 with zero themeColor attributes, no
"python-docx" string, zero em dashes, creator Nicholas J. Sokol.
No voice changes (the singular "I" stands; the cross-paper voice
decision is the author's). No headline numbers moved, so the
abstract, Discussion, Conclusions and cover letter needed no
chase; the cover letter files are unchanged and its Drive copy in
the working-files folder needs no refresh. The rebuilt manuscript
DOCX (2,225,756 B) replaced the content of the existing Drive
file in the Angle 2 folder (file ID
1Z1-qBiSy892C81Fi4DmZJiQRgPN_dEQr) and was verified by listing at
2,225,756 B. Housekeeping note from that listing: the folder also
still lists fig4_ndvi_trajectories.png and .pdf (6 November),
which the 2026-11-07 cleanup's final listing did not show; they
were left untouched.

---

## 2026-11-09 — Voice pass (author's order): genuine prose-and-tone pass

Context. Prior rounds ran only the formatting preflight on this
manuscript; the prose itself had never had the author's voice pass.
The author ordered the real pass on 2026-11-09. Method: scored the
delivered DOCX with `pf voice style` (profile nick, built from the
PPG-20-041 sample) BEFORE editing, revised the prose BY HAND in the
source of record (manuscript/build_manuscript.py; pre-pass backup
kept at build_manuscript.py.prevoice.bak), re-scored, and iterated.
First-person singular preserved exactly throughout (zero we/our/us
tokens before and after; this set's scoped exception stands).

BEFORE score: 23 paragraphs depart from the author's style —
STYLE-LABEL-OPEN x4 (WARN), STYLE-LONG-SENTENCE x5 (WARN),
STYLE-MEAN-LENGTH x6 (INFO), STYLE-SHORT-CLOSER x5 (INFO),
STYLE-STOCK-WORDS x2 (WARN), STYLE-UNIFORM-RHYTHM x6 (INFO).
Longest sentences ran to 81 words by the tool's count (73 by a
direct count); body mean sentence length 25.5 words, nine
sentences over 55 words.

REVISIONS (language editing only; 26 body paragraphs, the Figure 4
caption, and the Table 2 note touched across three hand rounds):
- 27 sentence splits at clause or citation boundaries, every one a
  period, none a semicolon: Introduction paragraphs 2, 3, 4;
  Sections 2.1, 2.2 (both paragraphs), 2.3 (twice), 2.4 (three);
  Sections 3.1 (both paragraphs), 3.2 (three, including the era
  test sentence, which is now two sentences with every number and
  the verdict unchanged), 3.3 (twice), 3.4 (both paragraphs),
  3.5 (recovery sentence, confounds sentence, zone-mean sentence),
  Discussion paragraphs 2 and 3. After: 241 sentences, mean 23.4
  words, longest 52, zero over 55.
- Label openers recast or folded into content sentences:
  Introduction paragraph 3 ("That picture is now a decade old."
  dropped, its content carried by the following sentences),
  Introduction paragraph 5 ("This paper does both jobs." dropped;
  the paragraph now opens with the First/Second structure it
  already had), Section 2.4 paragraph 1 (recast first-person
  active), Section 3.4 paragraph 1 (superlative kept, form
  changed), Section 3.5 Helene and Milton openers (now carry the
  reason: crossing size; saturated canopy), Discussion paragraphs
  1 to 3 (the enumerated "The first/second/third conclusion"
  labels merged into content sentences), and the limitations
  opener ("The limitations are plain." dropped; the paragraph
  opens with the climatology sentence itself).
- One verbless fragment repaired: the placebo sentence in
  Section 3.5 ("Two hundred pseudo-footprints, each a coherent
  patch ... and scored with the same arithmetic over the same
  months.") now has its verb ("were scored").
- Stock words out: "single-storm leverage" (Section 3.1) and
  "a small, leveraged population" (Section 3.4) replaced with
  plain wording ("One storm therefore carries more weight"; "a
  small population dominated by a single storm"). Same claims,
  same numbers.
- American spelling completed: "kilometres" x2 to "kilometers"
  (Introduction), "grey" to "gray" (Figure 4 caption). The one
  remaining SPELLING-MIX token is the ordered "analyses" of the
  third fix round, unchanged.
- The last LABEL-OPEN was isolated by paragraph-removal probes:
  it was the Table 2 note ("Broad rule: ... MD2011 rule: ..."),
  now written as two full sentences with identical content.

AFTER score: all WARN classes cleared (LABEL-OPEN 4 to 0,
LONG-SENTENCE 5 to 0, MEAN-LENGTH 6 to 0, STOCK-WORDS 2 to 0).
Remaining findings are INFO only: STYLE-UNIFORM-RHYTHM x17 and
STYLE-SHORT-CLOSER x4. Justification, recorded rather than chased:
the rhythm count ROSE as a side effect of the splits, because
breaking 60 to 80-word sentences regularized the lengths around
them; the still-flagged paragraphs are the number-dense methods
and results enumerations (sample definitions, geometry bands,
era counts, trajectories), where even pacing follows the content,
and forcing variance there would mean padding or compressing
number-bearing sentences. The four short closers are single
topic sentences ending results paragraphs (e.g. the Figure 2
pointer was merged into its predecessor in Section 3.1; the rest
are of the same kind). The Acknowledgements sentence (45 words,
formulaic thanks) and the Conclusions numbered list were
deliberately left as they stand.

FROZEN-CONTENT GUARDS (programmatic, builder before vs after,
cross-checked against the built MD): numeric-literal multiset
IDENTICAL (1,051 tokens, 395 distinct); parenthetical in-text
citation set IDENTICAL (78 parts, 48 distinct); narrative-citation
authors IDENTICAL; Figure/Table/Section reference set IDENTICAL
(42). The guard caught one real slip during the pass: an early
edit dropped "(27.4" from the Section 3.3 width sentence; it was
restored and the guard re-run clean before delivery. Em dashes 0
before and after. Semicolons 11 before and after, all pre-existing
inside citation parentheses and one DOI; no semicolon was
introduced as an em-dash replacement. Frozen passages verified
untouched in substance: the Section 3.2 era test (difference
+1.2 points, 95 percent CI -1.3 to +4.0, p = 0.38), the
"(empirical p ≤ 0.005)" wording (sentence untouched), and the
Milton ranking sentence (carried verbatim, now its own sentence
after the split before it).

QA. Builder abstract count 196 words; recounted from the final
DOCX at 196 (limit 200). pf preflight (profile nick, run): 0
audit errors; remaining warnings are the known classes
(TYPED-BULLETS in the Conclusions list, SPELLING-MIX for the
ordered "analyses", METADATA info, storm-name author-year false
positives, the deliberate T&F Harvard reference order). The
pf-fixed DOCX was verified text-identical to the builder DOCX
(152 of 152 paragraph and table-row texts) and promoted to the
deliverable name. DOCX XML audit: every font reference Times New
Roman at run, style, fontTable and theme level (only other
tokens are en-US and ja-JP language tags), all run colors 000000,
zero themeColor attributes, creator Nicholas J. Sokol, no
"python-docx" string in any part, zero em dashes, 6 tables,
5 figures.

DELIVERY. The rebuilt manuscript DOCX (2,225,705 B) replaced the
content of the existing Drive file in the Angle 2 folder (file ID
1Z1-qBiSy892C81Fi4DmZJiQRgPN_dEQr, folder
1xiZmWKj-1ip08zWsi7F3MR2lc318nCrH) and was read back at
2,225,705 B, matching the local build. The folder listing before
and after held the manuscript only; no files were added or
removed and no permissions were touched (the folder stays
unshared). The cover letter is unchanged and was not part of
this pass. Nothing was pushed to GitHub.
