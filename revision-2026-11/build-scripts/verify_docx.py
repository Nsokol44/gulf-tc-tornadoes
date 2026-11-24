"""Verify a built DOCX against house format by inspecting its XML.
Reports counts of w:color values, w:rFonts ascii values, and w:sz values
in word/document.xml, plus a font/color audit of word/styles.xml and the
list of embedded media. Usage: python build/verify_docx.py [docx]
"""
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCX = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "manuscript_pg_revised_merged.docx"

z = zipfile.ZipFile(DOCX)
doc_xml = z.read("word/document.xml").decode("utf-8")
styles_xml = z.read("word/styles.xml").decode("utf-8")

colors = Counter(re.findall(r'<w:color w:val="([0-9A-Fa-f]+)"', doc_xml))
theme_colors = re.findall(r"<w:color[^>]*w:themeColor", doc_xml)
fonts = Counter(re.findall(r'<w:rFonts[^>]*w:ascii="([^"]+)"', doc_xml))
fonts_hansi = Counter(re.findall(r'<w:rFonts[^>]*w:hAnsi="([^"]+)"', doc_xml))
sizes = Counter(re.findall(r'<w:sz w:val="(\d+)"', doc_xml))
print("document.xml w:color values:", dict(colors), "| themeColor attrs:", len(theme_colors))
print("document.xml rFonts ascii:", dict(fonts))
print("document.xml rFonts hAnsi:", dict(fonts_hansi))
print("document.xml w:sz values (half-points):", dict(sizes))

s_colors = Counter(re.findall(r'<w:color w:val="([0-9A-Fa-f]+)"', styles_xml))
s_fonts = Counter(re.findall(r'<w:rFonts[^>]*w:ascii="([^"]+)"', styles_xml))
s_sizes = Counter(re.findall(r'<w:sz w:val="(\d+)"', styles_xml))
print("styles.xml w:color values:", dict(s_colors))
print("styles.xml rFonts ascii:", dict(s_fonts))
print("styles.xml w:sz values:", dict(s_sizes))

media = [n for n in z.namelist() if n.startswith("word/media/")]
print(f"embedded media ({len(media)}):", media)
core = z.read("docProps/core.xml").decode("utf-8")
print("core.xml creator/description present:", "python-docx" in core or "python-docx" in doc_xml,
      "| dc:creator:", re.findall(r"<dc:creator>([^<]*)</dc:creator>", core))

ok = (set(colors) <= {"000000"} and not theme_colors and set(fonts) <= {"Times New Roman"}
      and set(fonts_hansi) <= {"Times New Roman"} and set(sizes) <= {"24"})
print("HOUSE FORMAT (document.xml runs):", "PASS" if ok else "FAIL")
