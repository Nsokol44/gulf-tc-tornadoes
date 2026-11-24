#!/usr/bin/env python3
"""Fix table page-overflow in manuscript_pg_revised_merged.docx.

Root cause: tables were built with tblW=auto and no w:tblLayout, so Word and
Google Docs autofit columns to content and wide tables (notably Table 6)
run off the right edge of the page.

Fix (content untouched): for every table set
  - w:tblLayout type="fixed"
  - w:tblW type="dxa" w=<grid total>
  - w:tblGrid gridCol widths from WIDTHS below (twips; total 9936 = 6.9 in,
    the Letter text width with 0.8 in side margins)
  - every cell's w:tcW to its column width (dxa)
Cell text is snapshotted before and asserted identical after.
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Twips

BASE = Path(__file__).resolve().parent.parent
DOCX = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "manuscript_pg_revised_merged.docx"

# Per-table column widths in twips (1440 twips = 1 in). Each sums to 9936.
WIDTHS = {
    # T1: Era, Coast, TC tornadoes, Storms, All US tornadoes, TC share (%)
    1: [1872, 1224, 1728, 1152, 2160, 1800],
    # T2: Storm, HURDAT2 id, Peak wind (kt), TC tornadoes, Basis,
    #     Strong (F/EF2-3), Deaths, Injuries
    2: [1368, 1296, 1368, 1368, 1512, 1512, 720, 792],
    # T3: Group, N rated, F/EF0..F/EF5, Weak 0-1 (%), Strong 2-3 (%), EF2+ (%)
    3: [2304, 792, 648, 648, 648, 648, 648, 648, 1037, 1123, 792],
    # T4: Stratum, Gulf n (%), Atlantic n (%), Pooled n (%)
    4: [3456, 2160, 2232, 2088],
    # T5: Class, Gulf inc, Gulf area, Atl inc, Atl area, Pooled inc, Pooled area
    5: [2304, 1368, 1152, 1440, 1224, 1368, 1080],
    # T6: Storm, Paths in case window, Footprint (ha), Marsh crossed (ha),
    #     Paths crossing, Analyzed cluster (ha), Reference (ha),
    #     Veg. pixels (fp/ref), Immediate anomaly, Slope months 2-18
    6: [950, 950, 1010, 950, 850, 1500, 960, 900, 1000, 866],
}
MAX_TOTAL = 9936  # 6.9 in


def snapshot(doc):
    return [[[c.text for c in row.cells] for row in t.rows] for t in doc.tables]


doc = Document(DOCX)
before = snapshot(doc)
assert len(doc.tables) == 6, f"expected 6 tables, found {len(doc.tables)}"

report = []
for idx, table in enumerate(doc.tables, start=1):
    widths = WIDTHS[idx]
    assert len(widths) == len(table.columns), f"T{idx}: width count mismatch"
    total = sum(widths)
    assert total <= MAX_TOTAL, f"T{idx}: total {total} > {MAX_TOTAL}"
    tbl = table._tbl
    tblPr = tbl.tblPr

    # tblW -> dxa total
    tblW = tblPr.find(qn("w:tblW"))
    if tblW is None:
        tblW = tblPr.makeelement(qn("w:tblW"), {})
        tblPr.append(tblW)
    tblW.set(qn("w:type"), "dxa")
    tblW.set(qn("w:w"), str(total))

    # tblLayout -> fixed (insert in schema position: after tblW/shd, before tblCellMar/tblLook)
    layout = tblPr.find(qn("w:tblLayout"))
    if layout is None:
        layout = tblPr.makeelement(qn("w:tblLayout"), {})
        # find insertion point: before tblCellMar or tblLook if present, else append
        inserted = False
        for tag in ("w:tblCellMar", "w:tblLook", "w:tblCaption", "w:tblDescription"):
            anchor = tblPr.find(qn(tag))
            if anchor is not None:
                anchor.addprevious(layout)
                inserted = True
                break
        if not inserted:
            tblPr.append(layout)
    layout.set(qn("w:type"), "fixed")

    # tblGrid
    grid = tbl.find(qn("w:tblGrid"))
    cols = grid.findall(qn("w:gridCol"))
    assert len(cols) == len(widths)
    for gc, w in zip(cols, widths):
        gc.set(qn("w:w"), str(w))

    # per-cell tcW
    for row in table.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Twips(w)

    report.append((idx, len(widths), total, total / 1440))

after = snapshot(doc)
assert before == after, "CELL TEXT CHANGED during width fix"
doc.save(DOCX)
for idx, ncols, total, inches in report:
    print(f"Table {idx}: {ncols} cols, grid total {total} twips = {inches:.3f} in")
print("Cell text verified identical before/after. Saved", DOCX)
