"""Gold-derived variants for 1137e2bb (PO entry audit): the expert deliverables as the anchor, a
values-only twin of the expert workbook as the base of every variant, and a catalog of seeded
corruptions and layout transformations, each with its declared expected verdict transitions.

Every variant is classified from the task requirements (prompt, rubric text, preregistration.md 2.4):
    rubric_relevant  the transformation changes something a rubric item tests; the expected verdicts
                     (overrides relative to the gold baseline) are declared from the rules, item by item
    neutral          the transformation changes layout or presentation only; the full verdict map must
                     equal the gold baseline

The gold baseline (grading-1137e2bb, 2026-11-01): every deterministic item passes except item 21, which
the expert deliverable fails as written (no Case Pack Missing indicator; adjudication A-21). Expected
maps are declared BEFORE the variants are graded; the test suite compares the complete item map, never
a subset, so a corruption that reaches more criteria than declared is a failure of the declaration.

Usage: python -m grading.gold_variants_1137e2bb <out_dir>   (writes every variant and the catalog)
Grader side only: reads private/gold; never model-visible."""
import json
import os
import shutil
import sys
from copy import copy

import openpyxl
from docx import Document
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "PO_Order_Entry_Audit.xlsx"
DOCX = "Deliverable PO Entry audit.docx"
DETAIL, RAW, PIVOT = "Formatted Data", "RawData", "PO Error Details"
# gold detail columns (header row 1): A PO, B SKU, C units, D entered, E expected, F UOM, G case pack, H ship-to,
# I Price Mismatch, J Case Pack Check, K Number of Errors, L Error Type
PO, SKU, UNITS, UOM, PFLAG, CFLAG, TOTAL, TEXT = 1, 2, 3, 6, 9, 10, 11, 12
# gold pivot sheet: header row 3, B label / C total / D price / E case, SKU rows 4-10, grand total row 11
S_LABEL, S_TOTAL, S_PRICE, S_CASE, S_HEADER, S_GRAND = 2, 3, 4, 5, 3, 11

D_ITEMS = [1, 2] + [i for i in range(3, 23) if i != 11] + [25, 26] + list(range(31, 63))
SUMMARY_ITEMS = [12, 13, 14, 15, 16, 17, 22] + list(range(56, 63))
WORKBOOK_ITEMS = [i for i in D_ITEMS if i not in (2, 25, 26)]
GOLD_BASELINE = {i: ("fail" if i == 21 else "pass") for i in D_ITEMS}


def gold_sha256() -> dict:
    import hashlib
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def build_twin(out_dir: str) -> str:
    """final/ with the expert docx unchanged and the expert workbook saved values-only (formulas replaced by
    their cached values; the pivot table, the Excel table and the sheet order are preserved). Loads in 0.1 s
    where the expert file needs about 8 s (two million styled empty cells); grades identically (test)."""
    final = os.path.join(out_dir, "final")
    shutil.rmtree(final, ignore_errors=True)
    os.makedirs(final)
    wb = openpyxl.load_workbook(os.path.join(GOLD_DIR, XLSX), data_only=True)
    wb.save(os.path.join(final, XLSX))
    shutil.copyfile(os.path.join(GOLD_DIR, DOCX), os.path.join(final, DOCX))
    return final


# ----------------------------------------------------------------------------- helpers on the twin
def detail(wb):
    return wb[DETAIL]


def find_row(ws, po, sku, units) -> int:
    for r in range(2, ws.max_row + 1):
        if (ws.cell(r, PO).value, ws.cell(r, SKU).value, ws.cell(r, UNITS).value) == (po, sku, units):
            return r
    raise KeyError((po, sku, units))


def summary_row(ws, label) -> int:
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, S_LABEL).value == label:
            return r
    raise KeyError(label)


def set_line(ws, po, sku, units, *, pflag=None, cflag=None, total=None, text=None):
    r = find_row(ws, po, sku, units)
    for col, v in ((PFLAG, pflag), (CFLAG, cflag), (TOTAL, total), (TEXT, text)):
        if v is not None:
            ws.cell(r, col).value = None if v == "" else v
    return r


def drop_table(ws):
    for name in list(ws.tables):
        del ws.tables[name]


def row_values(ws, r):
    return [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]


def plain_summary(wb, *, sorted_desc: bool, po_field: bool, auto_filter: bool = False):
    """Replace the pivot sheet by a plain summary table built from the pivot's own values."""
    src = wb[PIVOT]
    rows = [(src.cell(r, S_LABEL).value, src.cell(r, S_PRICE).value, src.cell(r, S_CASE).value, src.cell(r, S_TOTAL).value) for r in range(S_HEADER + 1, S_GRAND)]
    grand = (src.cell(S_GRAND, S_PRICE).value, src.cell(S_GRAND, S_CASE).value, src.cell(S_GRAND, S_TOTAL).value)
    del wb[PIVOT]
    ws = wb.create_sheet("Summary")
    ws.append(["SKU", "Price Mismatch Errors", "Case Pack Errors", "Total Errors"] + (["PO Number"] if po_field else []))
    if sorted_desc:
        rows.sort(key=lambda x: (-x[3], x[0]))
    for sku, p, c, t in rows:
        ws.append([sku, p, c, t] + (["(see detail)"] if po_field else []))
    ws.append(["Grand Total", *grand])
    if auto_filter:
        ws.auto_filter.ref = f"A1:D{len(rows) + 1}"


def docx_replace(final, old, new):
    path = os.path.join(final, DOCX)
    d = Document(path)
    hit = False
    for p in d.paragraphs:
        if old in p.text:
            p.text = p.text.replace(old, new)
            hit = True
    assert hit, old
    d.save(path)


# ----------------------------------------------------------------------------- mutators (workbook-level)
def m_delete_flagged_line(wb, final):
    ws = detail(wb); ws.delete_rows(find_row(ws, "PO1002", "SKU-0103", 120)); drop_table(ws)


def m_duplicate_zero_error_line(wb, final):
    ws = detail(wb); ws.append(row_values(ws, find_row(ws, "PO1005", "SKU-0101", 60)))


def m_duplicate_flagged_case_line(wb, final):
    ws = detail(wb); ws.append(row_values(ws, find_row(ws, "PO1003", "SKU-0111", 52)))


def m_flip_price_flag_consistent(wb, final):
    set_line(detail(wb), "PO1002", "SKU-0103", 120, pflag=0, total=0, text="")


def m_flip_price_flag_only(wb, final):
    set_line(detail(wb), "PO1002", "SKU-0103", 120, pflag=0)


def m_ea_line_case_flag_set(wb, final):
    set_line(detail(wb), "PO1001", "SKU-0106", 7, cflag=1, total=1, text="Case Pack")


def m_case_line_case_flag_cleared(wb, final):
    set_line(detail(wb), "PO1003", "SKU-0111", 52, cflag=0, total=0, text="")


def m_error_value_in_price_flag(wb, final):
    set_line(detail(wb), "PO1002", "SKU-0103", 120, pflag="#VALUE!")


def m_blank_price_flag(wb, final):
    set_line(detail(wb), "PO1002", "SKU-0103", 120, pflag="")


def m_units_changed(wb, final):
    ws = detail(wb); ws.cell(find_row(ws, "PO1002", "SKU-0103", 120), UNITS).value = 121


def m_uom_blank_on_case_line(wb, final):
    ws = detail(wb); ws.cell(find_row(ws, "PO1003", "SKU-0111", 52), UOM).value = None


def m_summary_sku_total_wrong(wb, final):
    ws = wb[PIVOT]; ws.cell(summary_row(ws, "SKU-0107"), S_TOTAL).value = 5


def m_summary_grand_price_wrong(wb, final):
    ws = wb[PIVOT]; ws.cell(S_GRAND, S_PRICE).value = 14


def m_summary_sheet_deleted(wb, final):
    del wb[PIVOT]


def m_total_column_deleted(wb, final):
    ws = detail(wb); ws.delete_cols(TOTAL); drop_table(ws)


def m_summary_text_column_deleted(wb, final):
    ws = detail(wb); ws.delete_cols(TEXT); drop_table(ws)


def m_extra_new_po_zero_error_row(wb, final):
    ws = detail(wb); ws.append(["PO1011", "SKU-0101", 6, 5.09, 5.09, "EA", 6, "Granite Small Co.", 0, 0, 0, None])


def m_summary_plain_sorted_no_po(wb, final):
    plain_summary(wb, sorted_desc=True, po_field=False)


def m_summary_plain_unsorted_no_filter(wb, final):
    plain_summary(wb, sorted_desc=False, po_field=False)


def m_split_detail_over_two_sheets(wb, final):
    ws = detail(wb); drop_table(ws)
    moved = [row_values(ws, r) for r in range(ws.max_row - 2, ws.max_row + 1)]  # last three data rows (PO1010: incl. a flagged case line)
    ws.delete_rows(ws.max_row - 2, 3)
    t = wb.create_sheet(f"{DETAIL} (2)"); t.append(row_values(ws, 1))
    for row in moved:
        t.append(row)


# neutral
def n_footer_total_row(wb, final):
    ws = detail(wb); ws.append(["Total", None, None, None, None, None, None, None, 15, 10, 25, None])


def n_legend_notes_rows(wb, final):
    ws = detail(wb); ws.append([]); ws.append(["Legend: 1 = error present, 0 = no error"]); ws.append(["Note: EA lines may ship individually and are exempt from the case-pack check"])


def n_grouped_subtotals(wb, final):
    ws = detail(wb); drop_table(ws)
    r = 2
    while r <= ws.max_row:
        po = ws.cell(r, PO).value
        end = r
        while end + 1 <= ws.max_row and ws.cell(end + 1, PO).value == po:
            end += 1
        sums = [sum((ws.cell(k, c).value or 0) for k in range(r, end + 1)) for c in (PFLAG, CFLAG, TOTAL)]
        ws.insert_rows(end + 1)
        ws.cell(end + 1, PO).value = f"{po} Total"
        for c, v in zip((PFLAG, CFLAG, TOTAL), sums):
            ws.cell(end + 1, c).value = v
        r = end + 2


def n_hidden_rows_outline(wb, final):
    ws = detail(wb)
    for r in range(2, 8):
        ws.row_dimensions[r].hidden = True; ws.row_dimensions[r].outlineLevel = 1
    ws.sheet_properties.outlinePr.summaryBelow = True


def n_lowercase_ids(wb, final):
    ws = detail(wb)
    for r in range(2, 14):
        ws.cell(r, PO).value = str(ws.cell(r, PO).value).lower(); ws.cell(r, SKU).value = str(ws.cell(r, SKU).value).lower()


def n_extra_sheets(wb, final):
    notes = wb.create_sheet("Notes", 0)
    for line in ("PO entry audit - working notes", "Checks: price mismatch (entered vs expected), case pack (CASE lines only)", "Prepared for Order Management"):
        notes.append([line])
    backup = wb.copy_worksheet(wb[RAW]); backup.title = "Backup"


def n_merged_title_row(wb, final):
    ws = detail(wb); drop_table(ws); ws.insert_rows(1); ws.cell(1, 1).value = "PO Entry Audit - line-level checks"; ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=12)


def n_two_level_merged_header(wb, final):
    ws = detail(wb); drop_table(ws); ws.insert_rows(1)
    ws.cell(1, PFLAG).value = "Error Flags"; ws.merge_cells(start_row=1, start_column=PFLAG, end_row=1, end_column=CFLAG)
    ws.cell(1, TOTAL).value = "Totals"; ws.merge_cells(start_row=1, start_column=TOTAL, end_row=1, end_column=TEXT)


def n_rubric_header_names(wb, final):
    ws = detail(wb)
    for c, h in ((PFLAG, "Price Mismatch Flag"), (CFLAG, "Case Pack Error Flag"), (TOTAL, "Total Errors"), (TEXT, "Error Summary")):
        ws.cell(1, c).value = h


def n_alternative_header_names(wb, final):
    ws = detail(wb)
    for c, h in ((PFLAG, "Price Mismatch Error"), (CFLAG, "Case Pack Violation"), (TOTAL, "# of Errors"), (TEXT, "Error Description"), (UNITS, "Qty Ordered"), (UOM, "Unit Order Multiple (UOM)")):
        ws.cell(1, c).value = h


def n_column_reorder_with_blank_column(wb, final):
    ws = detail(wb); drop_table(ws)
    rows = [row_values(ws, r) for r in range(1, ws.max_row + 1)]
    order = [TEXT - 1, PFLAG - 1, CFLAG - 1, TOTAL - 1, None, 0, 1, 2, 3, 4, 5, 6, 7]  # added columns first, a blank column, then the source columns
    idx = wb.sheetnames.index(DETAIL); del wb[DETAIL]; new = wb.create_sheet(DETAIL, idx)
    for row in rows:
        new.append([None if j is None else row[j] for j in order])


def n_sheet_renames(wb, final):
    wb[DETAIL].title = "Audit"; wb[PIVOT].title = "SKU Summary"; wb[RAW].title = "Source"


def n_formatting_only(wb, final):
    from openpyxl.styles import Font
    ws = detail(wb)
    for c in range(1, 13):
        ws.cell(1, c).font = Font(bold=True); ws.column_dimensions[get_column_letter(c)].width = 18
    for r in range(2, ws.max_row + 1):
        for c in (PFLAG, CFLAG, TOTAL):
            ws.cell(r, c).number_format = "0"
    ws.freeze_panes = "A2"


def n_rows_sorted_by_sku(wb, final):
    ws = detail(wb)
    rows = sorted((row_values(ws, r) for r in range(2, ws.max_row + 1)), key=lambda x: (x[1], x[0], x[2]))
    for i, row in enumerate(rows, start=2):
        for c, v in enumerate(row, start=1):
            ws.cell(i, c).value = v


def n_whitespace_in_ids_and_headers(wb, final):
    ws = detail(wb)
    for r in range(2, 10):
        ws.cell(r, PO).value = f" {ws.cell(r, PO).value} "; ws.cell(r, SKU).value = f"{ws.cell(r, SKU).value} "
    ws.cell(1, PFLAG).value = " Price Mismatch "; ws.cell(1, SKU).value = "SKU "


def n_rawdata_sheet_deleted(wb, final):
    del wb[RAW]


def n_lowercase_uom(wb, final):
    ws = detail(wb)
    for r in range(2, ws.max_row + 1):
        ws.cell(r, UOM).value = str(ws.cell(r, UOM).value).lower()


def n_summary_sheet_first(wb, final):
    wb.move_sheet(PIVOT, offset=-(wb.sheetnames.index(PIVOT)))


def n_summary_values_as_text(wb, final):
    ws = wb[PIVOT]
    for r in range(S_HEADER + 1, S_GRAND + 1):
        for c in (S_TOTAL, S_PRICE, S_CASE):
            ws.cell(r, c).value = str(ws.cell(r, c).value)


# file-level mutators (no workbook change)
def f_docx_deleted(final):
    os.remove(os.path.join(final, DOCX))


def f_docx_price_count_wrong(final):
    docx_replace(final, "15 Price Mismatch errors", "14 Price Mismatch errors")


def f_docx_counts_swapped(final):
    docx_replace(final, "15 Price Mismatch errors and 10 Case Pack errors", "10 Price Mismatch errors and 15 Case Pack errors")


def f_workbook_deleted(final):
    os.remove(os.path.join(final, XLSX))


def F(*items):
    return {i: "fail" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


# ----------------------------------------------------------------------------- the catalog
# expected: overrides relative to GOLD_BASELINE (item 21 stays fail unless overridden); attribution: expected
# attribution class of the overridden items where it matters; basis: the rule the expectation follows from.
CATALOG = {
    # --- rubric-relevant corruptions seeded into the gold ------------------------------------------------
    "R01_delete_flagged_line": {"kind": "rubric_relevant", "wb": m_delete_flagged_line,
        "expected": F(5, 6, 15, 17, 18, 20, 32),
        "basis": "PO1002/SKU-0103/120 (price mismatch) removed: row set short by one input line -> C1 through 5 and 6 (approved 2026-10-31); "
                 "named line 32 absent with certainty (no unidentified rows); price-flag sum 14 != 15 (18) and total sum 24 != 25 (20); "
                 "detail sums no longer reconcile to the summary (15, 17); case-pack items and the per-SKU summary values are untouched"},
    "R02_duplicate_zero_error_line": {"kind": "rubric_relevant", "wb": m_duplicate_zero_error_line,
        "expected": F(5, 6),
        "basis": "approved scenario (prereg 2.4): a duplicated zero-error row fails C1 through 5 and 6 only; sums and named lines unchanged"},
    "R03_duplicate_flagged_case_line": {"kind": "rubric_relevant", "wb": m_duplicate_flagged_case_line,
        "expected": F(5, 6, 16, 17, 19, 20),
        "basis": "PO1003/SKU-0111/52 (case error) duplicated: row set (5, 6); case-flag sum 11 != 10 (19) and total sum 26 != 25 (20); reconciliation of case and total (16, 17); "
                 "named line 47 still carries flag 1 on every copy"},
    "R04_flip_price_flag_consistent": {"kind": "rubric_relevant", "wb": m_flip_price_flag_consistent,
        "expected": F(5, 15, 17, 18, 20, 32),
        "basis": "price flag 1 -> 0 with total and text made consistent: flag logic wrong on one line (5), named line 32, sums 14 / 24 (18, 20), reconciliation (15, 17); 8 holds (0 = 0 + 0)"},
    "R05_flip_price_flag_only": {"kind": "rubric_relevant", "wb": m_flip_price_flag_only,
        "expected": F(5, 8, 15, 18, 32),
        "basis": "price flag 1 -> 0, total left at 1: as R04 for 5, 32, 18, 15; total != flag sum on that line (8); the total column still sums to 25 (20, 17 hold)"},
    "R06_ea_line_case_flag_set": {"kind": "rubric_relevant", "wb": m_ea_line_case_flag_set,
        "expected": F(6, 7, 16, 17, 19, 20),
        "basis": "EA line PO1001/SKU-0106/7 given case flag 1 (total and text consistent): case logic (6) and the non-CASE rule (7); case sum 11 (19), total sum 26 (20); reconciliation (16, 17)"},
    "R07_case_line_case_flag_cleared": {"kind": "rubric_relevant", "wb": m_case_line_case_flag_cleared,
        "expected": F(6, 16, 17, 19, 20, 47),
        "basis": "CASE line PO1003/SKU-0111/52 (52 not a multiple of 12) flag 1 -> 0 consistently: case logic (6), named line 47, sums 9 / 24 (19, 20), reconciliation (16, 17); 7 only looks at non-CASE lines"},
    "R08_error_value_in_price_flag": {"kind": "rubric_relevant", "wb": m_error_value_in_price_flag,
        "expected": F(5, 8, 9, 10, 15, 18, 32), "attribution": {5: "model_caused", 10: "model_caused"},
        "basis": "a literal #VALUE! in the price flag of PO1002/SKU-0103/120 is a confirmed invalid value (cell-value rule, APPROVED 2026-10-31): every item whose "
                 "fail_if_invalid lists price_flag fails (5, 8, 9, 15, 18), 10 fails on the error value, the line's own item 32 fails; other named lines read only their own cell; "
                 "the total column is intact so 17 and 20 hold"},
    "R09_blank_price_flag": {"kind": "rubric_relevant", "wb": m_blank_price_flag,
        "expected": F(5, 8, 9, 15, 18, 32),
        "basis": "a blank flag is a confirmed invalid value for the items that read it (cell-value rule); item 10 fails only on spreadsheet error values, so it holds"},
    "R10_units_changed_on_flagged_line": {"kind": "rubric_relevant", "wb": m_units_changed,
        "expected": F(5, 6, 32),
        "basis": "Ordered Units 120 -> 121 on PO1002/SKU-0103: a line's identity is (PO, SKU, quantity); the delivered row resolves to known PO and SKU entities but matches no "
                 "input line (changed row: extra + missing -> 5, 6); no row has an unresolvable id (U = 0), so the named line 32 is absent with certainty and fails "
                 "(same rule as the pinned fractional-quantity regression); flag sums unchanged (18-20, 15-17 hold)"},
    "R11_uom_blank_on_case_line": {"kind": "rubric_relevant", "wb": m_uom_blank_on_case_line,
        "expected": F(5, 6, 7),
        "basis": "UOM cleared on PO1003/SKU-0111/52 while its case flag stays 1: the business row differs from the input (5, 6); rubric 7 (UOM blank -> case flag must be 0) is violated on that line; "
                 "the named line 47 still reads flag 1"},
    "R12_summary_sku_total_wrong": {"kind": "rubric_relevant", "wb": m_summary_sku_total_wrong,
        "expected": F(58),
        "basis": "SKU-0107 total 6 -> 5 on the summary: per-SKU item 58 only; reconciliation items read the grand-total row, which is unchanged"},
    "R13_summary_grand_price_wrong": {"kind": "rubric_relevant", "wb": m_summary_grand_price_wrong,
        "expected": F(15),
        "basis": "grand-total price mismatch count 15 -> 14: the detail column sum no longer reconciles (15); per-SKU rows and the other measures are unchanged"},
    "R14_summary_sheet_deleted": {"kind": "rubric_relevant", "wb": m_summary_sheet_deleted,
        "expected": F(*SUMMARY_ITEMS), "attribution": {i: "model_caused" for i in SUMMARY_ITEMS},
        "basis": "no sheet other than the detail table and the raw-input copy (an identified detail candidate, never a summary): the separate SKU summary is confirmed absent -> every summary item fails (C2)"},
    "R15_total_column_deleted": {"kind": "rubric_relevant", "wb": m_total_column_deleted,
        "expected": F(4, 8, 17, 20),
        "basis": "Number of Errors column removed (every remaining header maps -> confirmed missing): 4 (four functional columns), 8, 20 and the total reconciliation 17; item 10 is not blocked by a missing column"},
    "R16_summary_text_column_deleted": {"kind": "rubric_relevant", "wb": m_summary_text_column_deleted,
        "expected": F(4),
        "basis": "Error Type column removed: only item 4 requires its presence deterministically (11 is a judge item)"},
    "R17_extra_new_po_zero_error_row": {"kind": "rubric_relevant", "wb": m_extra_new_po_zero_error_row,
        "expected": F(5, 6),
        "basis": "a row that is not in the input (PO1011) is an extra row: C1 through 5 and 6; its zero flags leave every sum and the non-CASE rule satisfied"},
    "R18_summary_plain_table_no_po_sorted": {"kind": "rubric_relevant", "wb": m_summary_plain_sorted_no_po,
        "expected": F(14),
        "basis": "pivot replaced by a plain per-SKU table with correct values, no PO field, no pivot: drill-down (14) fails; sorted by total descending satisfies 22"},
    "R19_summary_plain_table_unsorted_no_filter": {"kind": "rubric_relevant", "wb": m_summary_plain_unsorted_no_filter,
        "expected": F(14, 22),
        "basis": "as R18 but in SKU order with no filter, table or pivot: neither sorted nor sortable (22) and no drill-down (14)"},
    "R20_split_detail_over_two_sheets": {"kind": "rubric_relevant", "wb": m_split_detail_over_two_sheets,
        "expected": CA(5, 6, 15, 16, 17), "attribution": {i: "grader_extraction" for i in (5, 6, 15, 16, 17)},
        "basis": "the last three lines moved to a second sheet with the same header: split tables (prereg 2.4, 2026-10-31) - the row-set and reconciliation items are cannot_assess, "
                 "nothing is asserted missing, named lines are found in either sheet, 7 and 18-20 are decided over the rows of every candidate"},
    "R21_docx_deleted": {"kind": "rubric_relevant", "file": f_docx_deleted,
        "expected": F(2, 25, 26),
        "basis": "no Word document: 2 and the two count statements fail as not delivered (C3's deterministic part)"},
    "R22_docx_price_count_wrong": {"kind": "rubric_relevant", "file": f_docx_price_count_wrong,
        "expected": F(25),
        "basis": "the document states 14 price-mismatch errors: 25 fails; the case-pack statement is unchanged"},
    "R23_docx_counts_swapped": {"kind": "rubric_relevant", "file": f_docx_counts_swapped,
        "expected": F(25, 26),
        "basis": "10 price mismatches and 15 case-pack errors stated: both count items fail (each number is bound to the other phrase)"},
    "R24_workbook_deleted": {"kind": "rubric_relevant", "file": f_workbook_deleted,
        "expected": F(*WORKBOOK_ITEMS), "attribution": {1: "model_caused_missing"},
        "basis": "no .xlsx: item 1 and every workbook item fail as not delivered; the document items are graded from the docx"},
    # --- neutral layout and presentation transformations (full map must equal the gold baseline) -----------
    "N01_values_only_twin": {"kind": "neutral", "basis": "formulas replaced by their values: no rubric item of this task tests formulas"},
    "N02_footer_total_row": {"kind": "neutral", "wb": n_footer_total_row, "basis": "a TOTAL row under the detail table carries no PO/SKU identity: not a data row for the row set or the column sums"},
    "N03_legend_notes_rows": {"kind": "neutral", "wb": n_legend_notes_rows, "basis": "legend and note text below the table carry no identity"},
    "N04_grouped_subtotals": {"kind": "neutral", "wb": n_grouped_subtotals, "basis": "Excel-style 'PO1001 Total' roll-up rows between groups: labels are not ids, so they are neither rows nor summed"},
    "N05_hidden_rows_outline": {"kind": "neutral", "wb": n_hidden_rows_outline, "basis": "hidden rows and outline levels are presentation; the cells are still read"},
    "N06_lowercase_ids": {"kind": "neutral", "wb": n_lowercase_ids, "basis": "identity rule (prereg 2.4): case is a legal variant of the same reference entity"},
    "N07_extra_sheets": {"kind": "neutral", "wb": n_extra_sheets, "basis": "a Notes sheet and a Backup copy of the raw input: the detail table is still the sheet with the added columns; the summary is still found"},
    "N08_merged_title_row": {"kind": "neutral", "wb": n_merged_title_row, "basis": "a merged title row above the header: the header row is found by its content, not its position"},
    "N09_two_level_merged_header": {"kind": "neutral", "wb": n_two_level_merged_header, "basis": "group captions merged above the field names: the field-name row is the header"},
    "N10_rubric_header_names": {"kind": "neutral", "wb": n_rubric_header_names, "basis": "the rubric's own column names (names flexible, functions must be present)"},
    "N11_alternative_header_names": {"kind": "neutral", "wb": n_alternative_header_names, "basis": "other reasonable names for the added and source columns"},
    "N12_column_reorder_with_blank_column": {"kind": "neutral", "wb": n_column_reorder_with_blank_column, "basis": "column order never decides; an empty separator column is not a field"},
    "N13_sheet_renames": {"kind": "neutral", "wb": n_sheet_renames, "basis": "sheet names are not fixed by the task"},
    "N14_formatting_only": {"kind": "neutral", "wb": n_formatting_only, "basis": "fonts, widths, number formats, frozen panes"},
    "N15_rows_sorted_by_sku": {"kind": "neutral", "wb": n_rows_sorted_by_sku, "basis": "row order never decides"},
    "N16_whitespace_in_ids_and_headers": {"kind": "neutral", "wb": n_whitespace_in_ids_and_headers, "basis": "outer spaces in ids and headers are normalised"},
    "N17_rawdata_sheet_deleted": {"kind": "neutral", "wb": n_rawdata_sheet_deleted, "basis": "the raw input copy is not a deliverable requirement; the detail sheet carries the source columns (3)"},
    "N18_lowercase_uom": {"kind": "neutral", "wb": n_lowercase_uom, "basis": "rubric 6: UOM compared case-insensitively"},
    "N19_summary_sheet_first": {"kind": "neutral", "wb": n_summary_sheet_first, "basis": "sheet order never decides"},
    "N20_summary_values_as_text": {"kind": "neutral", "wb": n_summary_values_as_text, "basis": "numbers stored as text in the summary are still numbers"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, twin_final: str, out_dir: str) -> str:
    """Copy the twin's final/ and apply the variant's mutators. Returns the variant's final/ directory."""
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(twin_final, final)
    if spec.get("wb"):
        p = os.path.join(final, XLSX)
        wb = openpyxl.load_workbook(p)
        spec["wb"](wb, final)
        wb.save(p)
    if spec.get("file"):
        spec["file"](final)
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_attribution": s.get("attribution", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    twin = build_twin(os.path.join(out, "twin"))
    for n in CATALOG:
        print(n, build_variant(n, twin, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
