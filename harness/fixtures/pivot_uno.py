"""Fixture: create a real PivotTable (LibreOffice DataPilot) from the Data sheet of an xlsx and export to
xlsx with pivotTable/pivotCache parts. Runs with Debian's /usr/bin/python3 (python3-uno) and a headless
soffice listening on loopback. Usage: /usr/bin/python3 pivot_uno.py SRC.xlsx OUT.xlsx"""
import os, subprocess, sys, time, zipfile
import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.table import CellAddress, CellRangeAddress
def prop(n, v):
    p = PropertyValue(); p.Name = n; p.Value = v; return p
proc = subprocess.Popen(["soffice", "--headless", "--norestore", "--invisible", "--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext"])
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
ctx = None
for i in range(90):
    try:
        ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(1)
if ctx is None: print("FAIL: could not connect to soffice"); sys.exit(1)
desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(sys.argv[1]), "_blank", 0, (prop("Hidden", True),))
sheets = doc.Sheets; src = sheets.getByName("Data")
cur = src.createCursor(); cur.gotoEndOfUsedArea(False); end = cur.RangeAddress
rng = CellRangeAddress(); rng.Sheet = 0; rng.StartColumn = 0; rng.StartRow = 0; rng.EndColumn = end.EndColumn; rng.EndRow = end.EndRow
sheets.insertNewByName("Pivot", 1); dest = sheets.getByName("Pivot")
dpt = dest.getDataPilotTables(); desc = dpt.createDataPilotDescriptor(); desc.setSourceRange(rng)
ROW = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "ROW"); DATA = uno.Enum("com.sun.star.sheet.DataPilotFieldOrientation", "DATA")
SUM = uno.Enum("com.sun.star.sheet.GeneralFunction", "SUM")
fields = desc.getDataPilotFields()
fields.getByIndex(0).Orientation = ROW; fields.getByIndex(1).Orientation = ROW
f2 = fields.getByIndex(2); f2.Orientation = DATA; f2.Function = SUM
f3 = fields.getByIndex(3); f3.Orientation = DATA; f3.Function = SUM
addr = CellAddress(); addr.Sheet = 1; addr.Column = 0; addr.Row = 0
dpt.insertNewByName("PivotTable1", addr, desc)
doc.storeToURL(uno.systemPathToFileUrl(sys.argv[2]), (prop("FilterName", "Calc MS Excel 2007 XML"),))
doc.close(True)
try: desktop.terminate()
except Exception: pass
proc.wait(timeout=30)
z = zipfile.ZipFile(sys.argv[2]); names = z.namelist()
piv = [n for n in names if "pivot" in n.lower()]
print("xlsx parts with 'pivot':", piv)
for n in piv:
    if n.endswith(".xml") and "pivotTables/pivotTable" in n:
        x = z.read(n).decode("utf8", "replace"); print(n, "bytes", len(x)); print(x[:600])
