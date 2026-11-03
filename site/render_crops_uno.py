"""Export cell ranges of saved workbooks, and whole Word documents, to PDF with LibreOffice UNO.

Runs inside the frozen sandbox image under its system Python (the one with the LibreOffice bindings), with no network,
on copies prepared by site/render_crops.py. Per export: the sheet, the range, whether the grid and the row / column
headers are printed (so a cell crop shows its addresses) and an optional title row printed above the range (the
column-name row). Charts anchored inside a range are exported with it. The page is made large enough that each range
prints on one page at 100% sheet scale.

Usage (inside the container): /usr/bin/python3 -I render_crops_uno.py JOBS.json IN_DIR OUT_DIR
JOBS.json: {"<copy file name>": [{"sheet": "...", "range": "A11:C15", "out": "<name>.pdf", "grid": true,
            "title_row": 4}, ...], "<copy>.docx": [{"out": "<name>.pdf"}], ...}"""
import json
import os
import subprocess
import sys
import time

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.table import CellRangeAddress


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def main():
    jobs, in_dir, out_dir = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], sys.argv[3]
    proc = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore", "--nodefault",
                             "--accept=pipe,name=cropspipe;urp;"], env={**os.environ, "HOME": "/tmp"})
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    ctx = None
    for _ in range(60):
        try:
            ctx = resolver.resolve("uno:pipe,name=cropspipe;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(0.5)
    if ctx is None:
        raise SystemExit("LibreOffice did not start")
    desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    for fn, exports in jobs.items():
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.join(in_dir, fn)), "_blank", 0,
                                           (prop("Hidden", True), prop("ReadOnly", True)))
        if fn.endswith(".docx"):  # a Word document is exported whole; the paragraphs are cropped from the PDF
            for ex in exports:
                out = os.path.join(out_dir, ex["out"])
                doc.storeToURL(uno.systemPathToFileUrl(out), (prop("FilterName", "writer_pdf_Export"),))
                print("wrote", out)
            doc.close(True)
            continue
        for ex in exports:
            sheet = doc.Sheets.getByName(ex["sheet"])
            style = doc.StyleFamilies.getByName("PageStyles").getByName(sheet.PageStyle)
            style.PrintGrid = style.PrintHeaders = bool(ex.get("grid"))
            style.HeaderIsOn = style.FooterIsOn = False
            style.PrintCharts = style.PrintDrawing = True
            style.Width, style.Height, style.IsLandscape = 60000, 42000, False
            for k in ("TopMargin", "BottomMargin", "LeftMargin", "RightMargin"):
                setattr(style, k, 500)
            if ex.get("title_row"):
                title = CellRangeAddress()
                title.Sheet, title.StartColumn = sheet.RangeAddress.Sheet, 0
                title.EndColumn = sheet.getCellRangeByName(ex["range"]).RangeAddress.EndColumn
                title.StartRow = title.EndRow = ex["title_row"] - 1
                sheet.setTitleRows(title)
                sheet.setPrintTitleRows(True)
            else:
                sheet.setPrintTitleRows(False)
            sheet.setPrintTitleColumns(False)
            fd = uno.Any("[]com.sun.star.beans.PropertyValue", (prop("Selection", sheet.getCellRangeByName(ex["range"])),))
            out = os.path.join(out_dir, ex["out"])
            doc.storeToURL(uno.systemPathToFileUrl(out), (prop("FilterName", "calc_pdf_Export"), prop("FilterData", fd)))
            print("wrote", out)
        doc.close(True)
    desktop.terminate()
    proc.wait(timeout=30)


if __name__ == "__main__":
    main()
