"""Build the review DOCX from the merged manuscript MD, with figures embedded,
then normalize to house format: every run black (000000), Times New Roman, 12 pt.

Usage: .figvenv/bin/python build/build_docx.py [src.md] [dst.docx]
Normalization is applied at build time (runs and styles) and verified by
inspecting the DOCX XML afterwards (see build/verify_docx.py).
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

BASE = Path(__file__).resolve().parent.parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / "manuscript_pg_revised_merged.md"
DST = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / "manuscript_pg_revised_merged.docx"

FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)


def style_run(run, bold=False, italic=False):
    run.bold = bold
    run.italic = italic
    f = run.font
    f.name = FONT
    f.size = Pt(12)
    f.color.rgb = BLACK
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = rPr.makeelement(qn("w:rFonts"), {})
        rPr.insert(0, rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(attr), FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rFonts.get(qn(attr)) is not None:
            del rFonts.attrib[qn(attr)]
    color = rPr.find(qn("w:color"))
    if color is not None:
        for attr in ("w:themeColor", "w:themeTint", "w:themeShade"):
            if color.get(qn(attr)) is not None:
                del color.attrib[qn(attr)]
        color.set(qn("w:val"), "000000")


def add_runs(par, text, force_bold=False):
    parts = re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            style_run(par.add_run(part[2:-2]), bold=True)
        elif part.startswith("*") and part.endswith("*"):
            style_run(par.add_run(part[1:-1]), italic=True)
        else:
            style_run(par.add_run(part), bold=force_bold)


doc = Document()
for section in doc.sections:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    for attr in ("left_margin", "right_margin"):
        setattr(section, attr, Inches(0.8))
    section.top_margin = Inches(0.9)
    section.bottom_margin = Inches(0.9)

# Normalize every style in the template up front.
for style in doc.styles:
    try:
        style.font.name = FONT
        style.font.size = Pt(12)
        style.font.color.rgb = BLACK
        if style.element is not None:
            rPr = style.element.find(qn("w:rPr"))
            if rPr is not None:
                rFonts = rPr.find(qn("w:rFonts"))
                if rFonts is not None:
                    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                        rFonts.set(qn(attr), FONT)
                    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
                        if rFonts.get(qn(attr)) is not None:
                            del rFonts.attrib[qn(attr)]
    except Exception:
        pass

lines = SRC.read_text(encoding="utf-8").split("\n")
i = 0
n_images = 0
while i < len(lines):
    line = lines[i]
    m_img = re.match(r"^!\[.*\]\(([^)]+)\)\s*$", line)
    if m_img:
        img_path = (SRC.parent / m_img.group(1)).resolve()
        assert img_path.exists(), f"missing image: {img_path}"
        par = doc.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = par.add_run()
        run.add_picture(str(img_path), width=Inches(6.85))
        n_images += 1
        i += 1
        continue
    if line.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(set(c) <= set("-: ") for c in cells):
                rows.append(cells)
            i += 1
        if rows:
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.style = "Table Grid"
            for ri, row in enumerate(rows):
                for ci, cell in enumerate(row):
                    cell_par = table.cell(ri, ci).paragraphs[0]
                    add_runs(cell_par, cell, force_bold=(ri == 0))
        doc.add_paragraph()
        continue
    m = re.match(r"^(#{1,3})\s+(.*)$", line)
    if m:
        level = len(m.group(1))
        par = doc.add_paragraph()
        if level == 1:
            par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_runs(par, m.group(2), force_bold=True)
        i += 1
        continue
    if line.strip() == "":
        i += 1
        continue
    buf = [line]
    i += 1
    while (i < len(lines) and lines[i].strip() != "" and not lines[i].startswith("|")
           and not lines[i].startswith("#") and not lines[i].startswith("![")):
        buf.append(lines[i])
        i += 1
    par = doc.add_paragraph()
    add_runs(par, " ".join(buf))

cp = doc.core_properties
cp.author = "Nicholas J. Sokol"
cp.last_modified_by = "Nicholas J. Sokol"
cp.title = ("Gulf and Atlantic Coast tropical-cyclone tornadoes revisited: spatial "
            "distributions, intensity, land cover, and satellite-observed marsh "
            "damage and recovery")
cp.comments = ""
cp.description = ""
cp.keywords = ""
cp.category = ""

doc.save(DST)
print(f"wrote {DST} with {n_images} images embedded")
