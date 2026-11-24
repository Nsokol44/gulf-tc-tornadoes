#!/usr/bin/env python3
"""Post-build DOCX normalization, run after build_docx.py:
- word/styles.xml and word/stylesWithEffects.xml: every w:color -> 000000
  (including "auto"), the stray w:sz 22 -> 24 in styles.xml, and any
  non-TNR rFonts (the latent Macro Text style's Courier) -> Times New Roman.
- word/theme/theme1.xml: latin major/minor typefaces -> Times New Roman
  (template carries Calibri Light / Calibri / Cambria variants). The theme's
  per-script supplemental font table (Thai, Arabic, Indic, ...) is part of
  every standard Office theme and never cascades to Latin text; left as is.
- word/fontTable.xml: prune font declarations to Times New Roman plus
  Symbol (Symbol is retained solely as the numbering.xml bullet-glyph
  definition, the accepted precedent).
- word/numbering.xml is left untouched (Symbol bullet glyphs only).
All other parts are copied byte-for-byte."""
import re
import shutil
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCX = BASE / "manuscript_pg_revised_merged.docx"
TMP = BASE / "build" / "manuscript_normalized.docx"
TNR = "Times New Roman"

zin = zipfile.ZipFile(DOCX)
zout = zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED)
changed = {}
for item in zin.infolist():
    data = zin.read(item.filename)
    if item.filename in ("word/styles.xml", "word/stylesWithEffects.xml"):
        s = data.decode("utf-8")
        s, n1 = re.subn(r'(<w:color w:val=")([0-9A-Fa-f]{6}|auto)(")',
                        r"\g<1>000000\3", s)
        s, n2 = re.subn(r'((?:w:ascii|w:hAnsi|w:eastAsia|w:cs)=")Courier(")',
                        rf"\g<1>{TNR}\2", s)
        changed[f"{item.filename} colors->000000"] = n1
        changed[f"{item.filename} Courier->TNR"] = n2
        if item.filename == "word/styles.xml":
            s, n3 = re.subn(r'(<w:sz w:val=")22(")', r"\g<1>24\2", s)
            changed["styles.xml sz 22->24"] = n3
        data = s.encode("utf-8")
    elif item.filename == "word/theme/theme1.xml":
        s = data.decode("utf-8")
        for old in ("Calibri Light", "Calibri", "Cambria"):
            s, n = re.subn(rf'typeface="{old}"', f'typeface="{TNR}"', s)
            changed[f"theme latin {old}->TNR"] = n
        data = s.encode("utf-8")
    elif item.filename == "word/fontTable.xml":
        s = data.decode("utf-8")
        fonts = re.findall(r'<w:font [^>]*w:name="([^"]+)"[^>]*/>|'
                           r'<w:font [^>]*w:name="([^"]+)"[^>]*>.*?</w:font>',
                           s, re.S)
        keep = {"Times New Roman", "Symbol"}
        def drop(m):
            name = m.group(1) or m.group(2)
            return m.group(0) if name in keep else ""
        s, n = re.subn(r'<w:font [^>]*w:name="([^"]+)"[^>]*/>|'
                       r'<w:font [^>]*w:name="([^"]+)"[^>]*>.*?</w:font>',
                       drop, s, flags=re.S)
        changed["fontTable pruned entries"] = n
        data = s.encode("utf-8")
    zout.writestr(item, data)
zout.close()
zin.close()
shutil.move(TMP, DOCX)
print("normalized:", changed)
