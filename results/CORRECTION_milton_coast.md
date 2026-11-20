# Correction — Milton analysed cluster coast (2026-11-06)

`marsh_provenance.md` (Task C) states that Milton's analysed marsh cluster
(32.24 ha) is on the Florida Gulf coast and that 54.15 ha on the Atlantic
coast was excluded. Geometry verification against the pipeline's own
outputs shows the reverse:

- `data/footprint_milton.geojson` (the zone actually analysed in step 3)
  has bounds −80.377 to −80.366 W, 27.608 to 27.665 N and area 32.244 ha,
  which is the St. Lucie–Martin County coast on the ATLANTIC side.
- `data/reference_milton.geojson` bounds (−80.416 to −80.340 W,
  27.536 to 27.729 N) surround the same Atlantic cluster.
- The excluded 54.15 ha therefore lies in the four remaining clusters,
  including the Sarasota-area crossings on the Gulf coast
  (`data/marsh_in_paths_milton.geojson` spans −82.21 to −80.18 W).

The manuscript text, Table 6, and the Figure 3 caption follow the
geometry (Atlantic coast), not the provenance sentence. All other marsh
numbers are unaffected.
