"""Synthetic fixture files for toolchain smoke tests. Contents are invented and carry no task
answers, rubric text or expert deliverables. Run on the host: .venv/bin/python harness/fixtures/make_fixtures.py"""
import os

import openpyxl
import pymupdf
from docx import Document
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, "notes.txt"), "w", encoding="utf-8") as f:
        f.write("Fixture file for sandbox smoke tests. marker: FIXTURE-7Q2M\n")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "calc"
    ws.append(["qty", "price", "total"])
    for q, p in [(3, 1.5), (5, 2.25), (7, 4.0)]:
        ws.append([q, p, None])
    for r in range(2, 5):
        ws[f"C{r}"] = f"=A{r}*B{r}"
    ws["C5"] = "=SUM(C2:C4)"
    ws["E1"] = "cached"
    ws["E2"] = 42  # literal value, not a formula
    wb.save(os.path.join(HERE, "sample_formulas.xlsx"))  # formulas without cached values
    doc = Document()
    doc.add_heading("Smoke test document", level=1)
    doc.add_paragraph("This paragraph exists only to test conversion and rendering.")
    t = doc.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text = "item", "value"
    t.cell(1, 0).text, t.cell(1, 1).text = "alpha", "12"
    doc.save(os.path.join(HERE, "sample_doc.docx"))
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Smoke test slide"
    cd = CategoryChartData()
    cd.categories = ["A", "B", "C"]
    cd.add_series("share", (0.5, 0.3, 0.2))
    s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(1), Inches(1.5), Inches(5), Inches(4), cd)
    tbl = s.shapes.add_table(2, 2, Inches(6.5), Inches(1.5), Inches(3), Inches(1)).table
    tbl.cell(0, 0).text, tbl.cell(0, 1).text, tbl.cell(1, 0).text, tbl.cell(1, 1).text = "k", "v", "x", "1"
    prs.save(os.path.join(HERE, "sample_deck.pptx"))
    import random
    random.seed(1)
    pw = openpyxl.Workbook(); pws = pw.active; pws.title = "Data"; pws.append(["Store", "Brand", "Qty", "Sales"])
    for st in ["S1", "S2", "S3"]:
        for br in ["Alpha", "Beta"]:
            for _ in range(2):
                pws.append([st, br, random.randint(1, 20), round(random.uniform(10, 200), 2)])
    pw.save(os.path.join(HERE, "pivot_src.xlsx"))
    pdf = pymupdf.open()
    for i in (1, 2):
        pg = pdf.new_page()
        pg.insert_text((72, 72), f"Smoke test PDF page {i}", fontsize=18)
    pdf.save(os.path.join(HERE, "sample.pdf"))
    pdf[0].get_pixmap(dpi=60).save(os.path.join(HERE, "sample.png"))
    for f in sorted(os.listdir(HERE)):
        if f not in ("make_fixtures.py", "pivot_uno.py"):
            print(f, os.path.getsize(os.path.join(HERE, f)), "bytes")


if __name__ == "__main__":
    main()
