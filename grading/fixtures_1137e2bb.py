"""Positive and negative deliverable fixtures for 1137e2bb (PO entry audit). The positive
deliverable is built from the original input workbook and the independently verified values of
scripts/recalc/task_1137e2bb_po_audit.py (private/checks/recalc/<task>.json); the expert
deliverable is not used. Negatives plant one specific error each, of kinds that occur naturally
in this task. Usage: python -m grading.fixtures_1137e2bb <out_dir>"""
import json
import os
import shutil
import sys

import openpyxl
from docx import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
INPUT = os.path.join(ROOT, "data", "inputs", TASK, "Reference_PO Data.xlsx")
REFERENCE = os.path.join(ROOT, "private", "checks", "recalc", f"{TASK}.json")
NEGATIVES = ("one_line_flag_wrong", "one_sku_total_wrong", "grand_total_off_by_one", "case_ea_conversion_error", "detail_summary_mismatch", "docx_missing")


def load_reference() -> dict:
    with open(REFERENCE, encoding="utf-8") as f:
        return json.load(f)


def _summary_text(pf: int, cf: int) -> str:
    return "Price Mismatch; Case Pack" if pf and cf else "Price Mismatch" if pf else "Case Pack" if cf else "No Error"


def build_workbook(ref: dict, path: str, *, mutate: str | None = None) -> None:
    wb = openpyxl.load_workbook(INPUT)
    ws = wb["RawData"]
    headers = ["Price Mismatch Flag", "Case Pack Error Flag", "Case Pack Missing", "Total Errors", "Error Summary"]
    for j, h in enumerate(headers, start=9):
        ws.cell(row=1, column=j, value=h)
    by_key = {(l["po"], l["sku"], int(l["units"])): l for l in ref["lines"]}
    for r in range(2, ws.max_row + 1):
        po, sku, units = ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value
        if po is None:
            continue
        l = by_key[(po, sku, int(units))]
        pf, cf = l["price_mismatch_2dp"], l["case_pack"]
        if mutate == "one_line_flag_wrong" and (po, sku, units) == ("PO1002", "SKU-0103", 120):
            pf = 0
        if mutate == "case_ea_conversion_error" and (po, sku, units) == ("PO1001", "SKU-0106", 7):
            cf = 1  # EA line wrongly treated as CASE
        ws.cell(r, 9, pf); ws.cell(r, 10, cf); ws.cell(r, 11, l["case_pack_missing"]); ws.cell(r, 12, pf + cf); ws.cell(r, 13, _summary_text(pf, cf))
    # Summary sheet: per-SKU counts (reference values), grand total, auto-filter, PO drill-down block
    sm = wb.create_sheet("Summary")
    sm.append(["SKU", "Price Mismatch Errors", "Case Pack Errors", "Total Errors"])
    skus = sorted({l["sku"] for l in ref["lines"]})
    rows = []
    for sku in skus:
        v = ref["by_sku"].get(sku, {"price": 0, "case": 0, "total": 0})
        rows.append([sku, v["price"], v["case"], v["total"]])
    rows.sort(key=lambda r: (-r[3], r[0]))
    for row in rows:
        if mutate == "one_sku_total_wrong" and row[0] == "SKU-0107":
            row = [row[0], row[1], row[2], row[3] - 1]
        sm.append(row)
    gt_price, gt_case, gt_total = ref["total_price_mismatch"], ref["total_case_pack"], ref["total_errors"]
    if mutate == "grand_total_off_by_one":
        gt_total -= 1
    if mutate == "detail_summary_mismatch":
        gt_price -= 1
    sm.append(["Grand Total", gt_price, gt_case, gt_total])
    sm.auto_filter.ref = f"A1:D{len(rows) + 1}"
    start = len(rows) + 4
    sm.cell(start, 1, "PO drill-down (lines with errors)")
    sm.append([]) if False else None
    hdr = ["SKU", "PO Number", "Price Mismatch Flag", "Case Pack Error Flag", "Total Errors"]
    for j, h in enumerate(hdr, start=1):
        sm.cell(start + 1, j, h)
    r = start + 2
    for l in sorted(ref["lines"], key=lambda x: (x["sku"], x["po"])):
        if l["total"]:
            for j, v in enumerate([l["sku"], l["po"], l["price_mismatch_2dp"], l["case_pack"], l["total"]], start=1):
                sm.cell(r, j, v)
            r += 1
    wb.save(path)


def build_docx(ref: dict, path: str) -> None:
    d = Document()
    d.add_heading("PO Entry Audit - Summary of Findings", 1)
    d.add_paragraph("Two validation checks were applied to the 41 purchase-order lines in the export. "
                    "Price Mismatch: the Entered Unit Price differs from the Expected Unit Price for the line. "
                    "Case Pack: for lines with a UOM of CASE, the Ordered Units are not a multiple of the Case Pack, "
                    "which violates the fulfillment policy; EA lines may ship individually and are not subject to this check.")
    d.add_paragraph(f"Results: {ref['total_price_mismatch']} Price Mismatch errors and {ref['total_case_pack']} Case Pack errors were identified, "
                    f"{ref['total_errors']} errors in total. Each line in the workbook carries both flags, the total per line and an error summary; "
                    "the Summary tab aggregates errors by SKU with a PO-level drill-down.")
    top = sorted(ref["by_sku"].items(), key=lambda kv: (-kv[1]["total"], kv[0]))
    d.add_heading("SKUs with the highest error frequency", 2)
    t = d.add_table(rows=1, cols=4)
    for j, h in enumerate(["SKU", "Price Mismatch", "Case Pack", "Total"]):
        t.rows[0].cells[j].text = h
    for sku, v in top:
        cells = t.add_row().cells
        cells[0].text, cells[1].text, cells[2].text, cells[3].text = sku, str(v["price"]), str(v["case"]), str(v["total"])
    d.add_heading("Recommendations", 2)
    d.add_paragraph("Begin with SKU-0103 and SKU-0112, the high-priority SKUs: every one of their purchase orders shows a price mismatch. "
                    "Review the pricing setup and master data for SKU-0103 and SKU-0112 (entered price versus expected price) before the next billing cycle.")
    d.add_paragraph("SKU-0107 and SKU-0108 also show repeated price mismatches; SKU-0107, SKU-0111 and SKU-0118 carry case-pack violations, "
                    "so confirm their case-pack configuration and the order-entry validation for CASE items.")
    d.save(path)


def build_fixture(out_dir: str, variant: str = "positive") -> dict:
    """Write final/<deliverables> for the variant into out_dir (fresh directory). Returns a manifest."""
    ref = load_reference()
    final = os.path.join(out_dir, "final")
    if os.path.exists(final):
        shutil.rmtree(final)
    os.makedirs(final)
    mutate = None if variant == "positive" else variant
    build_workbook(ref, os.path.join(final, "PO_Audit.xlsx"), mutate=mutate if mutate != "docx_missing" else None)
    if variant != "docx_missing":
        build_docx(ref, os.path.join(final, "PO_Audit_Summary.docx"))
    manifest = {"variant": variant, "files": sorted(os.listdir(final)), "planted_error": None if variant == "positive" else variant,
                "reference": os.path.relpath(REFERENCE, ROOT), "expert_gold_used": False}
    with open(os.path.join(out_dir, "fixture.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    return manifest


if __name__ == "__main__":
    out = sys.argv[1]
    for v in ("positive",) + NEGATIVES:
        print(build_fixture(os.path.join(out, v), v))
