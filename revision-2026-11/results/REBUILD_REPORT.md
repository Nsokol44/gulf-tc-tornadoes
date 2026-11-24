# Rebuild report: "Gulf Coast tropical-cyclone tornadoes revisited" (Physical Geography revision)

Analysis rebuild under the author's design decisions of 2026-11-23 (two-coast
domain, verified years only, NLCD land-cover stratification, four retained
satellite cases, screening table only for new cases), with the currency
addendum of 2026-11-23 20:28 EST and the endpoint confirmation of
2026-11-23 20:43 EST applied. All numbers below are computed by the pipeline
in `code/` (one-command rerun: `code/run_all.py`); the original project and
the submitted package were not modified.

## 1. Data currency (checked 2026-11-23)

| Source | Status | Consequence |
|---|---|---|
| TCTOR (SPC) | Latest release is the **2024 Version, data thru 2023**. The live `tctor.xls` downloaded 2026-11-23 is byte-identical (MD5 `290c46a2c8030f64eedbdfc9cce93142`) to the archived copy. | **Verified endpoint is 2023.** No TCTOR release covering 2024 exists, so Helene and Milton do NOT enter through TCTOR; they remain SPC case-window cases (Section 5). |
| HURDAT2 | `hurdat2-1851-2025-092326.txt` (release 2025-09-23). Re-downloaded 2026-11-23; MD5 identical to the archived copy. | Current release already in use. |
| SPC severe database | Archived CSVs as in the original project. Counts for years up to 2023 are final. | No climatology number uses 2024-2025 records anywhere (author decision, 2026-11-23 20:43 EST: no preliminary 2025 data, no screened 2025 stratum). |
| NLCD | **NLCD 2021 Land Cover L48** (MRLC), pulled 2026-11-23 via the MRLC WCS. The classic CONUS zip URL is retired (HTTP 404 on both mirrors). The Annual NLCD line is served by the MRLC WCS only as 1985-2023 change-summary coverages, not land-cover rasters; NLCD 2021 is the newest epoch land-cover coverage served and uses the same class codes the design groups. | Vintage documented here and in `data/PROVENANCE.json`. If the author prefers Annual NLCD 2024, it must come through a different USGS channel; the grouped-class results would not be expected to change materially. |
| NWI | Esri Living Atlas "USA Wetlands" feature service (the paper's existing route), queried 2026-11-23. | Screening only. |

## 2. Design as implemented

- **Domain.** Gulf definition unchanged from the paper's Section 2.2.
  Atlantic mirror added: landfall fix between 81.0 W and 66.0 W at latitude
  41.5 N or below, or a classified fix inside the near-coast Atlantic box
  (24-41.5 N, 81-66 W). Sample = TCTOR tornadoes of storms qualifying under
  either definition.
- **Validation of the Gulf arm.** Storms qualifying under the Gulf
  definition contribute exactly **1,569** TCTOR tornadoes for 1995-2023,
  matching the submitted sample's TCTOR count for those years record for
  record in aggregate. The Atlantic definition adds 1,146 tornadoes from
  Atlantic-qualifying storms; 943 tornadoes belong to dual-qualifier storms.
- **Coast assignment.** By the storm's earliest qualifying landfall fix;
  box-only storms (24 sampled storms, e.g. Gustav 2002, Nestor 2019) take
  the coast of their earliest qualifying box fix. A fix at exactly 81.0 W
  satisfies both landfall rules; a same-timestamp tie is assigned to the
  Gulf.
- **Verified years only.** TCTOR 1995-2023. Eras: study 1995-2015,
  extension 2016-2023. The sample edit of the paper is retained: 11
  zero-width records dropped (8 Gulf stratum, 3 Atlantic stratum).
- **Sample.** **1,772 tornadoes from 114 storms** (Gulf stratum 991 / 72
  storms; Atlantic stratum 781 / 42 storms). By era: study 1,287 (Gulf 730,
  Atlantic 557); extension 485 (Gulf 261, Atlantic 224).

### Judgment calls the author should see

1. **Caribbean first landfalls decide the stratum for 41 sampled storms.**
   The landfall rules as written carry no lower latitude bound (true of the
   paper's Gulf rule as well: Yucatan and Central America landfalls already
   decided Gulf membership for storms such as Emily 2005 and Nate 2017).
   Applied symmetrically, storms whose first qualifying landfall was in the
   Caribbean but whose main United States landfall was on the Gulf coast
   land in the **Atlantic** stratum: Dennis 2005, Fay 2008, Georges 1998,
   Gustav 2008, Ike 2008, Irma 2017, Isaac 2012, Laura 2020, Lili 2002,
   Fred 2021. Katrina 2005 is Atlantic stratum because its first landfall
   was in Florida (26 N). Sensitivity: assigning dual-qualifier storms
   instead by their first landfall at 24 N or above flips **322 of 1,702**
   tornadoes (19 percent) between strata, all but 2 of them Atlantic to
   Gulf (`results/coast_assignment_sensitivity.csv`). The implemented rule
   is the author's stated rule; the alternative is a one-line change and an
   author decision.
2. **Atlantic box latitude cap.** The box is implemented as 24.0-41.5 N,
   the mirror of the Gulf box with the landfall rule's 41.5 N cap.
3. **Zero-length paths.** 659 sampled tornadoes (37 percent) have identical
   start and end coordinates. Their Section 2.4 footprints are discs of
   radius half the recorded width (a flat-cap buffer of a point is empty in
   GEOS, so these use round caps; segment footprints keep flat caps).
4. **Sub-pixel footprints.** 228 footprints are smaller than one 30 m NLCD
   pixel and contain no pixel centre. Area shares use the centre-rule
   rasterization (standard zonal statistics); the "intersects" shares use
   an all-touched rasterization, so a sub-pixel footprint still registers
   the classes it touches. Every sampled footprint intersects at least one
   NLCD class.
5. **Screening window adaptation** (Section 6): multi-landfall storms are
   screened over the span of all their landfall episodes, because the
   single assigned-coast anchor leaves Irma, Laura, Fred, Dorian and Sally
   with no usable window. For single-landfall storms the window is exactly
   the paper's.

## 3. New headline numbers

### Table 1 analogue: era totals and national shares

| Era | Coast | Tornadoes | Storms | All US tornadoes | Share of US (%) |
|---|---|---|---|---|---|
| Study 1995-2015 | Gulf | 730 | 49 | 26,080 | 2.8 |
| Study 1995-2015 | Atlantic | 557 | 27 | 26,080 | 2.1 |
| Study 1995-2015 | Pooled | 1,287 | 76 | 26,080 | 4.9 |
| Extension 2016-2023 | Gulf | 261 | 23 | 9,996 | 2.6 |
| Extension 2016-2023 | Atlantic | 224 | 15 | 9,996 | 2.2 |
| Extension 2016-2023 | Pooled | 485 | 38 | 9,996 | 4.9 |
| All 1995-2023 | Gulf | 991 | 72 | 36,076 | 2.7 |
| All 1995-2023 | Atlantic | 781 | 42 | 36,076 | 2.2 |
| All 1995-2023 | Pooled | 1,772 | 114 | 36,076 | 4.9 |

Peak years (pooled): 2004 (317 tornadoes, 17.4 percent of the US total),
2005 (237, 18.8 percent), 2008 (138), 2017 (124), 2020 (113). Largest
storms, study era: Ivan 2004 (Gulf stratum, 118), Frances 2004 (Atlantic,
103), Rita 2005 (Gulf, 97), Katrina 2005 (Atlantic, 59). Extension era:
Harvey 2017 (Gulf, 52), Florence 2018 (Atlantic, 44), Isaias 2020
(Atlantic, 39), Ida 2021 (Gulf, 36). Full per-storm table:
`results/by_storm.csv`.

### Table 3 analogue: intensity

Rating distribution (percent of rated tornadoes) and weak/strong split:

| Era | Coast | n rated | F/EF0 | F/EF1 | F/EF2 | F/EF3 | F/EF4 | F/EF5 | Weak (%) | Strong (%) |
|---|---|---|---|---|---|---|---|---|---|---|
| Study | Gulf | 730 | 61.9 | 30.5 | 7.3 | 0.3 | 0.0 | 0.0 | 92.5 | 7.5 |
| Study | Atlantic | 557 | 68.2 | 26.8 | 4.8 | 0.2 | 0.0 | 0.0 | 95.0 | 5.0 |
| Study | Pooled | 1,287 | 64.6 | 28.9 | 6.2 | 0.2 | 0.0 | 0.0 | 93.6 | 6.4 |
| Extension | Gulf | 254 | 66.1 | 29.1 | 4.3 | 0.4 | 0.0 | 0.0 | 95.3 | 4.7 |
| Extension | Atlantic | 221 | 58.4 | 34.8 | 6.3 | 0.5 | 0.0 | 0.0 | 93.2 | 6.8 |
| Extension | Pooled | 475 | 62.5 | 31.8 | 5.3 | 0.4 | 0.0 | 0.0 | 94.3 | 5.7 |

Ten extension-era tornadoes carry no rating (7 Gulf, 3 Atlantic); no
study-era tornado is unrated. No tornado in the verified sample is rated
F/EF4 or F/EF5.

Two-proportion tests, strong share, extension minus study (Newcombe 95
percent CI, two-sided z test):

| Group | Study strong (%) | Extension strong (%) | Difference (pts) | 95% CI (pts) | p |
|---|---|---|---|---|---|
| Pooled | 6.4 | 5.7 | -0.8 | -3.1 to +2.0 | 0.56 |
| Gulf | 7.5 | 4.7 | -2.8 | -5.7 to +0.9 | 0.13 |
| Atlantic | 5.0 | 6.8 | +1.8 | -1.6 to +6.1 | 0.33 |

The submitted paper's era contrast (a small, non-significant rise driven by
the rule-based 2024-2025 records) does not survive the verified-only
design: pooled, the strong share is flat to slightly down, and the two
coasts move in opposite directions, neither significantly.

### Size and DPI (medians, IQR in the CSV)

| Era | Coast | Median length (km) | Median width (m) | Median DPI |
|---|---|---|---|---|
| Study | Pooled | 1.61 | 45.7 | 0.03 |
| Extension | Pooled | 2.04 | 68.6 | 0.06 |
| Study | Gulf | 1.61 | 45.7 | 0.03 |
| Extension | Gulf | 1.80 | 68.6 | 0.05 |
| Study | Atlantic | 1.24 | 45.7 | 0.02 |
| Extension | Atlantic | 2.28 | 57.1 | 0.07 |

### Table 4 analogue: geometry (percent of tornadoes)

Pooled, all years 1995-2023 (era and coast splits in
`results/table4_geometry.csv`): quadrants NE 68.2, SE 26.7, SW 0.6, NW 4.4;
east half 95.0; north half 72.6; coast-distance bins 0-100 km 62.4,
100-200 km 14.3, 200-300 km 9.9, over 300 km 13.4; median centre range
304 km. Study era median range 327 km; extension era 252 km. The Atlantic
stratum is more strongly northeast-quadrant concentrated than the Gulf
stratum (NE 72.5 vs 64.9 percent) and sits farther north relative to the
centre (north half 78.0 vs 68.4 percent).

## 4. New land-cover table (NLCD 2021)

Shares pooled over all 1,772 footprints (total footprint area 89,877 ha).
(a) = percent of tornadoes whose footprint intersects the class at all;
(b) = percent of total footprint area in the class.

| Class (NLCD codes) | Pooled (a) | Pooled (b) | Gulf (a) | Gulf (b) | Atlantic (a) | Atlantic (b) |
|---|---|---|---|---|---|---|
| Wetlands (90, 95) | 52.5 | 14.5 | 51.0 | 13.7 | 54.5 | 15.8 |
| Developed (21-24) | 74.5 | 21.0 | 74.5 | 20.0 | 74.5 | 22.8 |
| Forest (41-43) | 58.7 | 30.2 | 57.5 | 30.5 | 60.2 | 29.6 |
| Agriculture (81, 82) | 55.0 | 22.1 | 54.0 | 22.4 | 56.2 | 21.5 |
| Water (11) | 33.0 | 4.9 | 34.6 | 5.2 | 31.0 | 4.2 |
| Other | 47.1 | 7.4 | 48.6 | 8.1 | 45.1 | 6.1 |

Era split (pooled): wetlands incidence rises from 48.1 percent in the study
era to 64.3 percent in the extension era, while the wetlands area share is
nearly flat (15.0 vs 13.7 percent); developed incidence rises from 67.8 to
92.2 percent and its area share from 17.1 to 26.1 percent. The incidence
rises track the extension era's larger median footprint (longer and wider
paths intersect more classes), not a change in where tornadoes occur: the
area shares, which are size-weighted, move much less. Full table including
coast by era cells: `results/landcover_summary.csv`; per-tornado class
areas and flags: `results/sample_with_landcover.csv`.

Narrative for the manuscript: TC tornado footprints are predominantly
rural in area (forest 30.2 percent, agriculture 22.1 percent) but
majority-developed in incidence (74.5 percent touch developed land),
because paths that reach towns cross developed pixels even when most of
their length is rural. Wetlands are the signature coastal class: over half
of all footprints (52.5 percent) touch wetlands and 14.5 percent of
footprint area is wetland, the quantitative link between the climatology
and the marsh case studies that the Associate Editor asked for.

## 5. Case studies: the verified / case division

The climatology, era comparisons and land-cover stratification are
**verified years only (TCTOR 1995-2023)**. The satellite case section keeps
four storms, with all footprints, NWI crossings, HLS trajectories and
placebo results taken from the original pipeline's outputs **exactly as
submitted** (nothing recomputed):

| Storm | Year | Count basis | Tornadoes (Table 2) | Case-window paths (Table 6) | Marsh crossed (ha) | Cluster analysed (ha) | Status |
|---|---|---|---|---|---|---|---|
| Ida | 2021 | TCTOR | 36 | 36 | 79.7 | 64.4 | Positive case |
| Ian | 2022 | TCTOR | 16 | 16 | 0.25 | none | Documented exclusion |
| Helene | 2024 | SPC 800-km case-window rule (16 in MD2011 subset) | 31 | 29 | 6.0 | 6.0 | Proof-of-concept case, outside the verified climatology |
| Milton | 2024 | SPC 800-km case-window rule (42 in MD2011 subset) | 45 | 45 | 86.4 | 32.2 | Proof-of-concept case, outside the verified climatology |

Helene and Milton sit outside the climatology because TCTOR's current
release ends at 2023 (Section 1); their tornadoes are SPC records screened
by the paper's case-window method, as in the submitted version. The
manuscript should say this in one explicit sentence wherever the cases are
introduced.

## 6. Case screening, 2016-2023 (screening table only)

Method: storms in the new sample from 2016-2023 with at least 10 TCTOR
tornadoes (18 storms). Case-window footprints and NWI marsh crossings per
Section 2.4, ranked by crossed herbaceous (emergent) marsh area. The
screening pipeline reproduces Ida exactly (79.7 ha total, 78.8 ha
herbaceous, against the submitted 79.7 ha) and Ian's exclusion (0.2 ha),
which validates the screen against the paper's own cases. No HLS
trajectory analysis was built for any candidate; case selection is the
author's decision.

| Rank | Storm | Year | Coast stratum | TCTOR tornadoes | Case-window paths | Total stratum (ha) | Herbaceous (ha) | Woody (ha) |
|---|---|---|---|---|---|---|---|---|
| 1 | Irma | 2017 | Atlantic | 28 | 28 | 108.3 | 99.1 | 9.3 |
| 2 | Isaias | 2020 | Atlantic | 39 | 39 | 101.3 | 98.0 | 3.3 |
| 3 | Idalia | 2023 | Gulf | 13 | 13 | 88.8 | 88.7 | 0.2 |
| 4 | Florence | 2018 | Atlantic | 44 | 36 | 81.4 | 81.4 | 0.0 |
| 5 | Ida | 2021 | Gulf | 36 | 37 | 79.7 | 78.8 | 1.0 |
| 6 | Dorian | 2019 | Atlantic | 25 | 25 | 63.1 | 60.2 | 2.9 |
| 7 | Hermine | 2016 | Gulf | 10 | 10 | 56.5 | 56.5 | 0.0 |
| 8 | Elsa | 2021 | Gulf | 16 | 18 | 13.1 | 13.1 | 0.0 |
| 9 | Harvey | 2017 | Gulf | 52 | 52 | 9.8 | 9.8 | 0.0 |
| 10 | Cindy | 2017 | Gulf | 18 | 18 | 7.9 | 7.9 | 0.0 |
| 11 | Ian | 2022 | Gulf | 16 | 16 | 0.2 | 0.2 | 0.0 |
| 12-18 | Laura 2020, Nate 2017, Michael 2018, Delta 2020, Sally 2020, Cristobal 2020, Fred 2021 | | | | | 0.0 | 0.0 | 0.0 |

**Outcome.** Four verified-era storms cross more herbaceous marsh than
Ida (78.8 ha): **Irma 2017 (99.1 ha), Isaias 2020 (98.0 ha), Idalia 2023
(88.7 ha) and Florence 2018 (81.4 ha)**; Dorian 2019 (60.2 ha) and Hermine
2016 (56.5 ha) are the same order of magnitude. The candidate pool for an
expanded case section is therefore real, and it is Atlantic-heavy (four of
the top six), which fits the new two-coast design. Per the author's
instruction, no trajectory analysis was built for any of them; which (if
any) to promote is the author's decision. Two method notes: the screening
window for Ida admits 37 SPC paths against the original Table 6 count of
36 (one extra record inside the plus/minus 8 h selection slack) with
identical crossed area; and Harvey's window spans both of its 2017
landfall episodes (52 paths), which raises its crossed area from 6.1 ha
(single-anchor) to 9.8 ha without changing its rank.

## 7. What changes in the manuscript

- **Title and framing.** A two-coast sample no longer supports a
  Gulf-only title; the domain is now "US Gulf and Atlantic coasts" (author
  decision, tied to judgment call 1).
- **Abstract.** Sample size 1,745 tornadoes / 97 storms (1995-2025)
  becomes **1,772 tornadoes / 114 storms (1995-2023)**; era totals,
  intensity and geometry numbers per Section 3; the land-cover result
  (Section 4) is new and belongs in the abstract.
- **Section 2.2.** Add the Atlantic mirror definition and the coast
  assignment rule; state the verified endpoint (TCTOR 2024 version, data
  thru 2023) and the removal of the rule-based 2024-2025 extension.
- **Section 2.4 / new methods text.** NLCD 2021 classification method
  (grouped classes, footprint rasterization, sub-pixel handling).
- **Section 3.1.** Era totals and shares (Table 1 analogue); peak years
  become 2004 and 2005; the 2024-2025 material (including any
  Helene/Milton climatology mentions) is deleted; largest-storm narrative
  now names Frances 2004 and Florence 2018 on the Atlantic side.
- **Section 3.2.** The two-proportion result reverses sign pooled (+1.2
  pts, p = 0.38 becomes -0.8 pts, p = 0.56) and is reported by coast; the
  "extension era is slightly stronger" reading is gone.
- **Section 3.3.** Size and DPI medians per the new table.
- **Section 3.4.** Quadrant, half and coast-distance shares per the new
  table, now by coast; median centre range 316 km becomes 304 km pooled
  (327 study, 252 extension).
- **Table 5 (attribution-rule sensitivity) is meaningless under
  verified-only** and should be deleted. Proposed replacement: the
  coast-assignment sensitivity (322 of 1,702 tornadoes change stratum
  under a first-landfall-at-24 N rule), which is the honest uncertainty
  statement of the new design, or the land-cover table if a fifth table is
  wanted for the stratification instead.
- **New results subsection** for land-cover stratification (Section 4
  numbers), placed between the geometry results and the case studies; it
  is the quantitative bridge the Associate Editor asked for.
- **Section 3.5 / cases.** Ida and Ian unchanged. Helene and Milton stay,
  reframed explicitly as proof-of-concept cases outside the verified
  climatology (Section 5 wording). The screening table (Section 6) can be
  cited in one paragraph as the case-selection audit trail.
- **Figures 1 and 2.** Data replaced (`results/fig1_map_points.csv`,
  `fig2_annual_counts.csv`, `fig2_quadrant_shares.csv`); Figure 1's domain
  now spans both coasts and its caption's storm/tornado counts change;
  Figure 2's annual series ends at 2023.
- **Conclusions.** Every pooled number changes; the era-intensity
  conclusion flips from "no significant change, point estimate up" to "no
  significant change, point estimate down pooled, opposite signs by
  coast"; the land-cover findings and the screening outcome (four
  verified-era storms cross more herbaceous marsh than Ida) are new
  conclusion material.

## 8. Files

- `results/sample_two_coast.parquet` / `.csv`: the 1,772-tornado sample
  with coast strata and full geometry.
- `results/sample_with_landcover.parquet` / `.csv`: sample plus per-class
  footprint areas and intersection flags.
- `results/table1_era_totals.csv`, `table3_intensity.csv`,
  `table3_two_proportion.csv`, `table3_size_dpi.csv`,
  `table4_geometry.csv`, `landcover_summary.csv`, `by_year.csv`,
  `by_storm.csv`, `era_peaks.csv`, `table2_cases.csv`,
  `case_screening_2016_2023.csv`, `case_screening_benchmark.json`,
  `coast_assignment_sensitivity.csv`,
  `sampled_storms_first_landfall.csv`, `qualifying_storms_two_coast.csv`,
  `sample_build_log.json`, `fig1_map_points.csv`,
  `fig2_annual_counts.csv`, `fig2_quadrant_shares.csv`.
- `data/PROVENANCE.json`: source files, MD5s, versions, currency checks.
- `code/`: full pipeline (`run_all.py`), README with sources and the
  environment note.
