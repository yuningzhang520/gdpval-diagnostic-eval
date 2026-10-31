"""Counter-example regressions for the 1137e2bb deterministic checks (Codex review rounds
logs/pilot-a-review-6uxm37u9, logs/pilot-final-review-ogcsjzyp, logs/pilot-closeout-review-wzwtf89y and
logs/extraction-review-0r3d__40: B3, B4, B5, the extraction-pipeline semantics, R1–R5 and the XML cap). Every variant carries the business data of the
positive fixture unless stated. Each test asserts specific criteria, their attribution and the
evidence fields, not only totals. Layout
changes (sheet names, header row, column order, header synonyms) must grade exactly like the
positive fixture; unrecognised layouts and failed recalculations must yield cannot_assess with a
grader-side attribution and never a FAIL; unreadable or missing workbooks are model failures only
when the transfer is verified; wrong row sets and swapped narrative counts must never pass. The
outcome table is also written to $GRADING_REGRESSION_LOG_DIR/layout_table.json when set.
Run: python -m unittest grading.tests.test_layout_regressions -v"""
import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import openpyxl
from docx import Document

from grading import checks_1137e2bb as CK, extract as X
from grading.fixtures_1137e2bb import TASK, build_fixture

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{TASK}.json"), encoding="utf-8"))
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{TASK}.json"), encoding="utf-8"))
DETAIL, SUMMARY = set(CK.DETAIL_ITEMS), set(CK.SUMMARY_ITEMS)
WORKBOOK = DETAIL | SUMMARY
ROWSET_ITEMS = {5, 6}                               # depend on the verified business-row set (approved 2026-10-31: 7 and 18–20 no longer do; 8 and 9 are per-row arithmetic)
IDENTITY_ITEMS = {3, 5, 6, 7} | set(range(31, 56))  # depend on the (PO, SKU, quantity) line identity (18–20 sum the column over all rows: approved 2026-10-31)
FORMULA_ITEMS = {5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 19, 20} | set(range(31, 56))  # read the computed flag columns
XLSX, DOCX = "PO_Audit.xlsx", "PO_Audit_Summary.docx"
CODEX_ALIASES = {"Ordered Units": "Units Ordered", "Entered Unit Price": "Unit Price Entered", "Expected Unit Price": "Unit Price Expected",
                 "Total Errors": "Error Count", "Price Mismatch Errors": "Price Discrepancies", "Case Pack Errors": "Pack Violations"}
ALIASES_2 = {"PO Number": "PO #", "SKU": "Item SKU", "Ordered Units": "Qty Ordered", "Entered Unit Price": "Entered Price", "Expected Unit Price": "Expected Price",
             "UOM": "Unit of Measure", "Case Pack": "Pack Size", "Price Mismatch Flag": "Price Error", "Case Pack Error Flag": "Case Pack Violation",
             "Total Errors": "Errors", "Error Summary": "Issue"}
TABLE: dict[str, dict] = {}


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def rename_headers(wb, mapping):
    for s in wb:
        for c in s[1]:
            if c.value in mapping:
                c.value = mapping[c.value]


def v_sheet_names(wb):
    for i, s in enumerate(wb):
        s.title = f"Audit view {i + 1}"


def v_header_row(wb):
    for s in wb:
        s.insert_rows(1, 3)


def v_column_order(wb):
    for s in wb:
        vals = list(s.values)
        for i, row in enumerate(vals, 1):
            for j, v in enumerate(reversed(row), 1):
                s.cell(i, j, v)


def v_formulas(wb):
    s = wb["RawData"]
    for r in range(2, s.max_row + 1):
        s.cell(r, 9, f"=IF(ROUND(D{r},2)<>ROUND(E{r},2),1,0)")
        s.cell(r, 10, f'=IF(AND(F{r}="CASE",MOD(C{r},G{r})<>0),1,0)')
        s.cell(r, 12, f"=I{r}+J{r}")


def v_dup_missing(wb):
    s = wb["RawData"]
    row2 = [c.value for c in s[2]]
    for j, v in enumerate(row2, 1):
        s.cell(3, j, v)  # row 3 (PO1007 SKU-0101 2 units) replaced by a copy of row 2


def v_dup_extra(wb):
    s = wb["RawData"]
    s.append([c.value for c in s[2]])  # a duplicated zero-error line appended


def v_ambiguous(first):
    """Codex final review (ambiguous_generic_first / ambiguous_alias_first): the same source data plus
    the columns 'Units' (copy), 'Shipped Units' (+5) and 'Units Ordered' (+1); the leading column is
    either the generic or the alias header, so column order would decide if it were allowed to."""
    def mutate(wb):
        s = wb["RawData"]
        rows = list(s.values)
        h = list(rows[0])
        j = h.index("Ordered Units")
        newh = h + ["Units", "Shipped Units", "Units Ordered"]
        newrows = [list(r) + [r[j], r[j] + 5, r[j] + 1] for r in rows[1:]]
        order = list(range(len(newh)))
        lead = len(h) if first == "generic" else len(h) + 2
        order.remove(lead)
        order.insert(0, lead)
        for ri, row in enumerate([newh] + newrows, 1):
            for ci, old in enumerate(order, 1):
                s.cell(ri, ci, row[old])
    return mutate


def v_partial_formula(field):
    """Codex final review (price_formula_only_failed / case_formula_only_failed): only one flag column holds formulas."""
    def mutate(wb):
        s = wb["RawData"]
        col = 9 if field == "price" else 10
        for r in range(2, s.max_row + 1):
            s.cell(r, col, f"=IF(ROUND(D{r},2)<>ROUND(E{r},2),1,0)" if field == "price" else f'=IF(AND(F{r}="CASE",MOD(C{r},G{r})<>0),1,0)')
    return mutate


def v_fractional(wb):
    """Codex final review (fractional_units): one quantity 60 -> 60.5 must be a different business row."""
    s = wb["RawData"]
    s.cell(2, 3, s.cell(2, 3).value + 0.5)


def v_reordered(wb):
    s = wb["RawData"]
    rows = [[c.value for c in r] for r in s.iter_rows(min_row=2)]
    rows.reverse()
    for i, r in enumerate(rows, 2):
        for j, v in enumerate(r, 1):
            s.cell(i, j, v)


def docx_with(paragraphs):
    def build(final):
        d = Document()
        for p in paragraphs:
            d.add_paragraph(p)
        d.save(os.path.join(final, DOCX))
    return build


class LayoutRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="layout_regress_")
        cls.base = os.path.realpath(cls.tmp.name)
        build_fixture(os.path.join(cls.base, "positive"), "positive")
        cls.positive = os.path.join(cls.base, "positive", "final")

    @classmethod
    def tearDownClass(cls):
        out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
        if out:
            os.makedirs(out, exist_ok=True)
            with open(os.path.join(out, "layout_table.json"), "w", encoding="utf-8") as f:
                json.dump(TABLE, f, indent=1, default=str)
        cls.tmp.cleanup()

    def variant(self, name, *, wb_mutate=None, final_mutate=None):
        final = os.path.join(self.base, "variants", name, "final")
        shutil.copytree(self.positive, final)
        if wb_mutate:
            p = os.path.join(final, XLSX)
            wb = openpyxl.load_workbook(p)
            wb_mutate(wb)
            wb.save(p)
        if final_mutate:
            final_mutate(final)
        return final

    def run_checks(self, name, final, *, integrity="verified", recalc=False, runner=None):
        work = os.path.join(self.base, "work", name)
        ex = X.extract_all(final, work, recalc=recalc, runner=runner) if runner else X.extract_all(final, work, recalc=recalc)
        integ = {i["path"]: True for i in ex["inventory"]} if integrity == "verified" else {}
        res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity=integ)
        fails = {i for i, r in res["items"].items() if r["verdict"] == "fail"}
        cannot = {i for i, r in res["items"].items() if r["verdict"] == "cannot_assess"}
        attribution = sorted({r.get("attribution") for r in res["items"].values() if r.get("attribution")})
        TABLE[name] = {"fail": sorted(fails), "cannot_assess": sorted(cannot), "attribution_classes": attribution,
                       "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()},
                       "detail_sheet": res["detail_sheet"], "row_completeness": res["extraction_status"].get("row_completeness", {}) and
                       {k: v for k, v in res["extraction_status"]["row_completeness"].items() if k != "key_fields"}}
        self.assertEqual(set(res["items"]), set(CK.D_ITEMS))
        return ex, res, fails, cannot

    def assert_like_positive(self, name, final):
        _, res, fails, cannot = self.run_checks(name, final)
        self.assertEqual((fails, cannot), (set(), set()), f"{name}: fail {sorted(fails)} cannot {sorted(cannot)}")
        self.assertEqual({k: v["status_from_deterministic"] for k, v in res["critical"].items()}, {"C1": "pass", "C2": "pass", "C3": "not_confirmed"})

    # ---------------------------------------------------------------- B3: layouts that must grade like the positive fixture
    def test_positive_layout(self):
        self.assert_like_positive("positive", self.positive)

    def test_renamed_sheets(self):
        self.assert_like_positive("sheet_names", self.variant("sheet_names", wb_mutate=v_sheet_names))

    def test_header_not_in_row_one(self):
        self.assert_like_positive("header_row", self.variant("header_row", wb_mutate=v_header_row))

    def test_reversed_column_order(self):
        self.assert_like_positive("column_order", self.variant("column_order", wb_mutate=v_column_order))

    def test_header_synonyms_from_the_review(self):
        self.assert_like_positive("header_aliases_codex", self.variant("header_aliases_codex", wb_mutate=lambda wb: rename_headers(wb, CODEX_ALIASES)))

    def test_header_synonyms_second_set(self):
        self.assert_like_positive("header_aliases_2", self.variant("header_aliases_2", wb_mutate=lambda wb: rename_headers(wb, ALIASES_2)))

    def test_units_header_alone(self):
        self.assert_like_positive("units_header_only", self.variant("units_header_only", wb_mutate=lambda wb: rename_headers(wb, {"Ordered Units": "Units"})))

    def test_reordered_rows_are_not_a_failure(self):
        self.assert_like_positive("reordered_rows", self.variant("reordered_rows", wb_mutate=v_reordered))

    # ---------------------------------------------------------------- B3: unrecognised layout → cannot_assess, never FAIL
    def test_unrecognised_headers_are_cannot_assess_with_grader_attribution(self):
        final = self.variant("unrecognised_headers", wb_mutate=lambda wb: rename_headers(wb, {"Ordered Units": "Column C", "Entered Unit Price": "Column D"}))
        _, res, fails, cannot = self.run_checks("unrecognised_headers", final)
        self.assertEqual(fails, set())
        self.assertEqual(cannot, IDENTITY_ITEMS)  # only the items that need the quantity / line identity; the rest is graded from reliably mapped columns
        self.assertTrue(all(res["items"][i]["attribution"] == "grader_extraction" and "extraction_failed" in res["items"][i]["note"] for i in cannot))
        dep = res["extraction_status"]["dependencies"]
        self.assertEqual((dep["ordered_units"]["status"], dep["entered"]["status"], dep["line_identity"]["status"]), ("unmapped", "unmapped", "unmapped"))
        self.assertEqual({res["items"][i]["verdict"] for i in (1, 2, 4, 8, 9, 12, 13, 25, 26)}, {"pass"})
        self.assertEqual(res["critical"]["C1"]["status_from_deterministic"], "not_confirmed")
        # PO or SKU unrecognised: the detail sheet cannot be located and no summary sheet is guessed
        final2 = self.variant("unrecognised_po_sku", wb_mutate=lambda wb: rename_headers(wb, {"PO Number": "Opaque Alpha", "SKU": "Opaque Beta"}))
        _, res2, fails2, cannot2 = self.run_checks("unrecognised_po_sku", final2)
        self.assertEqual(fails2, set()); self.assertEqual(cannot2, WORKBOOK)

    # ---------------------------------------------------------------- B3/B5: formulas without cached values
    def test_formula_workbook_with_failed_recalculation_is_cannot_assess_not_fail(self):
        final = self.variant("formula_recalc_failed", wb_mutate=v_formulas)
        before = sha(os.path.join(final, XLSX))
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        ex, res, fails, cannot = self.run_checks("formula_recalc_failed", final, recalc=True, runner=failing)
        self.assertEqual(ex["xlsx"][XLSX]["recalc"]["status"], "failed")
        self.assertEqual(fails, set(), sorted(fails))
        self.assertEqual(cannot, FORMULA_ITEMS, sorted(cannot ^ FORMULA_ITEMS))
        self.assertTrue(all(res["items"][i]["attribution"] in ("grader_caused_recalculation", "grader_extraction") for i in cannot))
        self.assertEqual(res["extraction_status"]["workbooks"][XLSX]["attribution"], "grader_caused_recalculation")
        self.assertEqual(sha(os.path.join(final, XLSX)), before)  # the deliverable copy is never modified
        self.assertEqual({res["items"][i]["verdict"] for i in (12, 13, 14, 21, 22, 56, 57, 58, 59, 60, 61, 62)}, {"pass"})

    def test_formula_workbook_with_successful_recalculation_passes(self):
        final = self.variant("formula_recalc_ok", wb_mutate=v_formulas)
        positive_xlsx = os.path.join(self.positive, XLSX)

        def converter(cmd, **kw):  # stands in for soffice: writes a recalculated copy into the fresh scratch directory
            scratch = next(a for a in cmd if a.endswith(":/work")).split(":/work")[0]
            shutil.copyfile(positive_xlsx, os.path.join(scratch, "out", "in.xlsx"))
            return SimpleNamespace(returncode=0, stdout="SOFFICE_RC=0\n", stderr="")
        ex, res, fails, cannot = self.run_checks("formula_recalc_ok", final, recalc=True, runner=converter)
        self.assertEqual(ex["xlsx"][XLSX]["recalc"]["status"], "ok")
        self.assertGreater(len(ex["xlsx"][XLSX]["value_sources"]["recalculated_cells"]), 100)
        self.assertEqual((fails, cannot), (set(), set()))

    # ---------------------------------------------------------------- B3: unreadable / missing workbook attribution
    def test_corrupt_workbook_with_verified_transfer_is_a_model_failure(self):
        final = self.variant("corrupt_xlsx_transfer_verified", final_mutate=lambda f: open(os.path.join(f, XLSX), "wb").write(b"synthetic invalid workbook"))
        _, res, fails, cannot = self.run_checks("corrupt_xlsx_transfer_verified", final, integrity="verified")
        self.assertEqual(fails, WORKBOOK | {1}); self.assertEqual(cannot, set())
        self.assertEqual({res["items"][i]["attribution"] for i in fails}, {"model_caused_corrupt"})
        self.assertFalse(res["items"][1]["evidence"]["format_check"]["zip_ok"]); self.assertTrue(res["items"][1]["evidence"]["transfer_integrity"])

    def test_corrupt_workbook_with_unverified_transfer_is_unknown(self):
        final = self.variant("corrupt_xlsx_transfer_unknown", final_mutate=lambda f: open(os.path.join(f, XLSX), "wb").write(b"synthetic invalid workbook"))
        _, res, fails, cannot = self.run_checks("corrupt_xlsx_transfer_unknown", final, integrity="unknown")
        self.assertEqual(fails, set()); self.assertEqual(cannot, WORKBOOK | {1})
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"unknown"})

    def test_missing_workbook_fails_the_workbook_items(self):
        final = self.variant("missing_xlsx", final_mutate=lambda f: os.remove(os.path.join(f, XLSX)))
        _, res, fails, cannot = self.run_checks("missing_xlsx", final)
        self.assertEqual(fails, WORKBOOK | {1}); self.assertEqual(cannot, set())
        self.assertEqual({res["items"][i]["attribution"] for i in fails}, {"model_caused_missing"})
        self.assertEqual({res["items"][i]["verdict"] for i in (2, 25, 26)}, {"pass"})

    # ---------------------------------------------------------------- B4: row multiset
    def test_duplicate_plus_missing_row_fails_with_both_named(self):
        """Codex rounds 1–3 (duplicate_missing). Items 8 and 9 are per-row arithmetic / format checks over
        every row of the table and no longer depend on the row set (round 2 made the dependency sets
        explicit): a duplicated or missing line fails the row-set items 5, 6, 7, 18, 19, 20 only."""
        final = self.variant("duplicate_and_missing_row", wb_mutate=v_dup_missing)
        _, res, fails, cannot = self.run_checks("duplicate_and_missing_row", final)
        self.assertEqual(fails, ROWSET_ITEMS, sorted(fails ^ ROWSET_ITEMS)); self.assertEqual(cannot, set())
        self.assertTrue(set(range(31, 56)) | {7, 8, 9, 18, 19, 20} <= {i for i, r in res["items"].items() if r["verdict"] == "pass"})  # flagged lines present; per-row arithmetic unaffected; approved 2026-10-31: 7 and the column sums (still 15 / 10 / 25) pass
        self.assertEqual(res["critical"]["C1"]["status_from_deterministic"], "fail")
        rc = res["extraction_status"]["row_completeness"]
        self.assertFalse(rc["ok"]); self.assertEqual((rc["reference_rows"], rc["deliverable_rows"]), (41, 41))
        self.assertEqual([m[:3] for m in rc["missing"]], [["PO1007", "SKU-0101", "2"]]); self.assertEqual([d[:3] for d in rc["duplicates"]], [["PO1005", "SKU-0101", "60"]])  # quantities are normalised decimals
        self.assertEqual(res["items"][5]["attribution"], "model_caused"); self.assertIn("confirmed missing >= 1", res["items"][5]["note"]); self.assertIn("duplicated 1", res["items"][5]["note"])
        self.assertEqual((rc["confirmed_missing_lower_bound"], rc["missing_identity_certain"]), (1, True))
        self.assertEqual(res["items"][18]["deliverable_value"], REFERENCE["total_price_mismatch"])  # the sum is still reported; the row set fails the item

    def test_duplicated_zero_error_row_is_an_extra_row_failure(self):
        """Codex round 1 (duplicated_zero_error_row passed everything). The extra row fails the row-set items;
        8 and 9 stay per-row checks (the duplicated zero-error row satisfies total = price + case)."""
        final = self.variant("duplicated_zero_error_row", wb_mutate=v_dup_extra)
        _, res, fails, cannot = self.run_checks("duplicated_zero_error_row", final)
        self.assertEqual(fails, ROWSET_ITEMS, sorted(fails ^ ROWSET_ITEMS)); self.assertEqual(cannot, set())
        # approved 2026-10-31 (old expectation: 5, 6, 7, 18, 19, 20 FAIL): 5 and 6 FAIL and C1 fails through them; 7 and 18–20 PASS
        self.assertEqual({res["items"][i]["verdict"] for i in (7, 18, 19, 20)}, {"pass"}); self.assertEqual(res["critical"]["C1"]["status_from_deterministic"], "fail")
        self.assertEqual((res["items"][18]["deliverable_value"], res["items"][18]["evidence"]["rows_summed"]), (REFERENCE["total_price_mismatch"], 42))
        rc = res["extraction_status"]["row_completeness"]
        self.assertEqual((rc["deliverable_rows"], len(rc["extra"]), len(rc["missing"])), (42, 1, 0))

    # ---------------------------------------------------------------- B3 (Codex final review): synonym conflicts are ambiguous in either column order
    def test_synonym_conflict_is_ambiguous_in_either_column_order(self):
        results = {}
        for first in ("generic", "alias"):
            final = self.variant(f"ambiguous_{first}_first", wb_mutate=v_ambiguous(first))
            _, res, fails, cannot = self.run_checks(f"ambiguous_{first}_first", final)
            results[first] = {i: r["verdict"] for i, r in res["items"].items()}
            self.assertEqual(fails, set(), f"{first}: FAIL from an ambiguous field {sorted(fails)}")
            self.assertEqual(cannot, IDENTITY_ITEMS, sorted(cannot ^ IDENTITY_ITEMS))
            amb = res["detail_sheet"]["ambiguous"]
            self.assertEqual(list(amb), ["ordered_units"])
            self.assertEqual(sorted(c["header"] for c in amb["ordered_units"]), ["ordered units", "units", "units ordered"])  # 'shipped units' is not a candidate
            for i in cannot:
                self.assertEqual(res["items"][i]["attribution"], "grader_extraction"); self.assertIn("ambiguous", res["items"][i]["note"])
                u = res["items"][i]["evidence"]["unassessable"]
                self.assertTrue(u and u[0]["kind"] == "ambiguous" and not res["items"][i]["evidence"]["violations"])
                cands = u[0]["detail"] if u[0]["field"] == "ordered_units" else u[0]["detail"]["ordered_units"]["candidates"]
                self.assertEqual(cands, amb["ordered_units"])  # the candidate columns are the evidence; none of them was read
            for i in {4, 8, 9, 10, 12, 13, 14, 15, 16, 17, 21, 22, 25, 26} | set(range(56, 63)):
                self.assertEqual(res["items"][i]["verdict"], "pass", (first, i))
            self.assertEqual({k: v["status_from_deterministic"] for k, v in res["critical"].items()}, {"C1": "not_confirmed", "C2": "pass", "C3": "not_confirmed"})
        self.assertEqual(results["generic"], results["alias"])  # column order never changes a deterministic verdict

    def test_map_columns_requires_a_unique_mapping(self):
        m = CK.map_columns(["PO Number", "SKU", "Units", "Ordered Units", "Entered Unit Price", "Expected Unit Price", "UOM", "Case Pack"])
        self.assertNotIn("ordered_units", m["cols"]); self.assertEqual([c["header"] for c in m["ambiguous"]["ordered_units"]], ["units", "ordered units"])
        m2 = CK.map_columns(["PO Number", "SKU", "Ordered Units", "Entered Unit Price", "Expected Unit Price", "UOM", "Case Pack", "Price Mismatch Flag", "Case Pack Error Flag", "Total Errors", "Error Summary"])
        self.assertEqual(m2["ambiguous"], {}); self.assertEqual(set(m2["cols"]), {"po", "sku", "ordered_units", "entered", "expected", "uom", "case_pack", "price_flag", "case_flag", "total", "summary_text"})
        m3 = CK.map_columns(["PO Number", "PO", "SKU"])  # two exact PO candidates
        self.assertIn("po", m3["ambiguous"]); self.assertNotIn("po", m3["cols"])
        m4 = CK.map_columns(["SKU", "Total Errors", "Total Errors"])  # the same header twice is ambiguous, not first-wins
        self.assertIn("total", m4["ambiguous"])

    # ---------------------------------------------------------------- B3 (Codex final review): a formula failure propagates to every dependent item
    def test_single_formula_column_failure_propagates_to_items_8_and_9_without_fail(self):
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        expected = {"price": {5, 8, 9, 10, 15, 18} | set(range(31, 46)), "case": {6, 7, 8, 9, 10, 16, 19} | set(range(46, 56))}
        for field in ("price", "case"):
            with self.subTest(field=field):
                final = self.variant(f"{field}_formula_only_failed", wb_mutate=v_partial_formula(field))
                _, res, fails, cannot = self.run_checks(f"{field}_formula_only_failed", final, recalc=True, runner=failing)
                self.assertEqual(fails, set(), sorted(fails)); self.assertEqual(cannot, expected[field], sorted(cannot ^ expected[field]))
                self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_recalculation"})
                self.assertEqual(res["critical"]["C1"]["status_from_deterministic"], "not_confirmed")
                dep = res["extraction_status"]["dependencies"]
                self.assertEqual((dep[f"{field}_flag"]["status"], dep[f"{field}_flag"]["kind"]), ("grader_error", "unrecalculated")); self.assertEqual(dep["case_flag" if field == "price" else "price_flag"]["status"], "ok")
                self.assertEqual(res["items"][8]["dependencies"], ["price_flag", "case_flag", "total"])
                self.assertEqual(res["items"][8]["fail_on_own"], {"missing": ["price_flag", "case_flag", "total"], "invalid": ["price_flag", "case_flag", "total"], "row_set": False,
                                                                   "row_scoped": False, "invalid_kinds": list(CK.INVALID_KINDS)})  # extraction review: the contract names the invalid kinds and the row scope

    # ---------------------------------------------------------------- B4 (Codex final review): quantities are exact decimals
    def test_fractional_quantity_is_a_changed_row(self):
        final = self.variant("fractional_units", wb_mutate=v_fractional)
        _, res, fails, cannot = self.run_checks("fractional_units", final)
        self.assertEqual(fails, ROWSET_ITEMS, sorted(fails ^ ROWSET_ITEMS)); self.assertEqual(cannot, set())
        rc = res["extraction_status"]["row_completeness"]
        self.assertEqual(len(rc["changed"]), 1); ch = rc["changed"][0]
        self.assertEqual((ch["po"], ch["sku"], ch["fields"], ch["reference"]["units"], ch["deliverable"]["units"]), ("PO1005", "SKU-0101", ["units"], "60", "60.5"))
        self.assertEqual(rc["extra_rows"][str(rc["extra"][0])], [2])  # the changed row sits in Excel row 2
        self.assertEqual(res["items"][5]["evidence"]["row_completeness"]["changed"][0]["deliverable"]["units"], "60.5")
        self.assertEqual(res["items"][5]["evidence"]["violations"][0]["kind"], "row_set")

    def test_quantity_normalisation_is_lossless(self):
        self.assertEqual([CK.qty(v) for v in (60, 60.0, "60", 60.5, "60.50", "0060", Decimal("60.000"))], ["60", "60", "60", "60.5", "60.5", "60", "60"])
        self.assertIsNone(CK.qty("sixty")); self.assertIsNone(CK.qty(None))
        k1 = CK.business_key("PO1005", "SKU-0101", 60, 5.09, 5.09, "EA", 6); k2 = CK.business_key("PO1005", "SKU-0101", 60.5, 5.09, 5.09, "EA", 6)
        self.assertNotEqual(k1, k2); self.assertEqual(k1[2], "60"); self.assertEqual(k2[2], "60.5")

    # ---------------------------------------------------------------- B3 (Codex final review): grader-side faults are never model corruption
    def test_parser_exception_on_a_valid_original_is_grader_side(self):
        final = self.variant("parser_fault")
        before = sha(os.path.join(final, XLSX))
        with patch.object(X, "extract_xlsx", side_effect=RuntimeError("synthetic grader parser failure")):
            ex, res, fails, cannot = self.run_checks("parser_fault", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, WORKBOOK)
        self.assertEqual(res["items"][1]["verdict"], "pass")  # zip and XML parts independently valid
        # Codex round 3 semantics: a parser that cannot handle a structurally valid file leaves the file's validity
        # undetermined -> cannot_assess with the reason kept, attribution unknown (not grader-caused, not model-caused)
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"unknown"})
        info = ex["xlsx"][XLSX]
        self.assertEqual((info["error_class"], info["exception_type"], info["copy_verified"], info["format"]["structure_ok"]), ("parser_undetermined", "RuntimeError", True, True))
        self.assertIn("RuntimeError", res["items"][5]["note"]); self.assertEqual(res["extraction_status"]["workbooks"][XLSX]["attribution"], "unknown")
        self.assertEqual(sha(os.path.join(final, XLSX)), before); self.assertTrue(ex["originals_unchanged"])

    def test_damaged_working_copy_is_grader_side_and_the_original_is_untouched(self):
        final = self.variant("copy_fault")
        before = sha(os.path.join(final, XLSX))
        original_copy = X.copy_originals

        def damage_only_the_copy(*a, **kw):
            copies = original_copy(*a, **kw)
            with open(copies[XLSX]["copy"], "wb") as f:
                f.write(b"synthetic grader-copy damage")
            return copies
        with patch.object(X, "copy_originals", side_effect=damage_only_the_copy):
            ex, res, fails, cannot = self.run_checks("copy_fault", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, WORKBOOK); self.assertEqual(res["items"][1]["verdict"], "pass")
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_extraction"})
        info = ex["xlsx"][XLSX]
        self.assertEqual((info["error_class"], info["copy_verified"], info["copy_verified_before_parse"]), ("copy_fault", True, False))  # verified at copy time; damaged afterwards; caught again right before parsing
        self.assertEqual(sha(os.path.join(final, XLSX)), before); self.assertTrue(ex["originals_unchanged"])

    # ---------------------------------------------------------------- Codex round 3 (logs/pilot-closeout-review-wzwtf89y): pipeline semantics
    def test_table_identity_does_not_depend_on_row_coverage(self):
        """missing_rows_keep_5 / threshold_49: a unique detail-table candidate is accepted whatever its
        coverage; the real missing rows then FAIL the row-set items and name every missing line."""
        def keep_rows(n):
            def mutate(wb):
                s = wb["RawData"]; s.delete_rows(n + 2, s.max_row)
                for name in list(wb.sheetnames):
                    if name != "RawData":
                        del wb[name]
            return mutate
        final = self.variant("missing_rows_keep_5", wb_mutate=keep_rows(5))
        _, res, fails, cannot = self.run_checks("missing_rows_keep_5", final)
        self.assertEqual(res["extraction_status"]["pipeline"]["identify_tables"][XLSX]["status"], "ok"); self.assertEqual(cannot, set())
        rs = res["extraction_status"]["row_completeness"]
        self.assertEqual((rs["identified_rows"], rs["unidentified_rows"], rs["missing_count"], rs["confirmed_missing_lower_bound"], rs["missing_identity_certain"]), (5, 0, 36, 36, True))
        self.assertTrue(ROWSET_ITEMS <= fails); self.assertEqual(res["items"][5]["attribution"], "model_caused"); self.assertIn("confirmed missing >= 36", res["items"][5]["note"])
        self.assertEqual(len(rs["missing"]), 36)
        absent_lines = {i for i, (po, sku, u, _) in CK.PER_LINE.items() if (po, sku, CK.qty(u)) not in {(l["po"], l["sku"], CK.qty(l["units"])) for l in REFERENCE["lines"][:5]}}
        self.assertTrue(absent_lines <= fails); self.assertEqual(res["items"][min(absent_lines)]["evidence"]["violations"][0]["kind"], "line_absent")
        self.assertTrue(set(CK.SUMMARY_ITEMS) <= fails)  # no other sheet at all: the absence of a summary is confirmed
        # synthetic 100-line source with 49 / 50 / 51 identified rows: identity ok at every coverage, missing rows confirmed
        ref = copy.deepcopy(REFERENCE); ref["lines"] = []
        for i in range(100):
            line = copy.deepcopy(REFERENCE["lines"][0]); line.update(po=f"PO{9000 + i}", sku=f"SKU-{8000 + i}", units=60, entered=1, expected=1, uom="EA", case=6, price_mismatch_2dp=0, case_pack=0); ref["lines"].append(line)
        for n in (49, 50, 51):
            with self.subTest(rows=n):
                final = os.path.join(self.base, "variants", f"threshold_{n}", "final"); os.makedirs(final)
                wb = openpyxl.Workbook(); ws = wb.active; ws.title = "RawData"
                ws.append(["PO Number", "SKU", "Ordered Units", "Entered Unit Price", "Expected Unit Price", "UOM", "Case Pack", "Ship-to Location", "Price Mismatch Flag", "Case Pack Error Flag", "Case Pack Missing", "Total Errors", "Error Summary"])
                for line in ref["lines"][:n]:
                    ws.append([line["po"], line["sku"], 60, 1, 1, "EA", 6, "synthetic", 0, 0, 0, 0, ""])
                wb.save(os.path.join(final, XLSX))
                ex = X.extract_all(final, os.path.join(self.base, "work", f"threshold_{n}"), recalc=False)
                res = CK.run_checks(ex, ref, RUBRIC, integrity={XLSX: True})
                self.assertEqual(res["extraction_status"]["pipeline"]["identify_tables"][XLSX]["status"], "ok")
                self.assertEqual((res["items"][5]["verdict"], res["extraction_status"]["row_completeness"]["confirmed_missing_lower_bound"]), ("fail", 100 - n))

    def test_unidentified_rows_bound_the_confirmed_missing_count(self):
        """Rows whose id cannot be parsed are kept and counted; only max(0, M - U) missing rows are confirmed."""
        def mutate(wb):
            s = wb["RawData"]; s.cell(2, 1, "INVALID-A"); s.cell(4, 1, "INVALID-B"); s.delete_rows(3)
        final = self.variant("unidentified2_missing1", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("unidentified2_missing1", final)
        rs = res["extraction_status"]["row_completeness"]
        self.assertEqual((rs["unidentified_rows"], rs["missing_count"], rs["confirmed_missing_lower_bound"], rs["missing_identity_certain"]), (2, 3, 1, False))
        self.assertEqual([u["ids"]["po"]["status"] for u in rs["unidentified"]], ["unparseable", "unparseable"])
        self.assertEqual(fails, ROWSET_ITEMS); self.assertEqual(res["items"][5]["attribution"], "model_caused")
        # one unidentified row and one missing row: the bound is 0 -> no confirmed violation, cannot_assess
        def mutate2(wb):
            s = wb["RawData"]; s.cell(2, 1, "INVALID-ID")
        final2 = self.variant("unidentified1_missing1", wb_mutate=mutate2)
        _, res2, fails2, cannot2 = self.run_checks("unidentified1_missing1", final2)
        rs2 = res2["extraction_status"]["row_completeness"]
        self.assertEqual((rs2["unidentified_rows"], rs2["missing_count"], rs2["confirmed_missing_lower_bound"]), (1, 1, 0))
        self.assertEqual(fails2, set()); self.assertEqual(cannot2, ROWSET_ITEMS); self.assertEqual(res2["items"][5]["attribution"], "unknown")

    def test_parsed_but_wrong_ids_are_extra_rows_and_fail(self):
        def mutate(wb):
            s = wb["RawData"]; s.cell(5, 1, "PO1099"); s.cell(6, 2, "SKU-0999")  # rows of lines 32 (PO1002/SKU-0103/120) and 35+48 (PO1004/SKU-0103/14)
        final = self.variant("wrong_po_sku_parsed", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("wrong_po_sku_parsed", final)
        rs = res["extraction_status"]["row_completeness"]
        self.assertEqual((rs["unidentified_rows"], rs["missing_count"], len(rs["extra"]), rs["confirmed_missing_lower_bound"]), (0, 2, 2, 2))
        self.assertEqual(fails, ROWSET_ITEMS | {32, 35, 48}); self.assertEqual(cannot, set())
        self.assertEqual(res["items"][32]["evidence"]["violations"][0]["kind"], "line_absent")

    def test_confirmed_missing_column_fails_and_unknown_header_does_not(self):
        """A deleted case-flag column (no unrecognised header left) is confirmed_missing -> FAIL on its own;
        the same column under a strange name (Case Packaging Validation) is unmapped -> cannot_assess."""
        final = self.variant("case_column_deleted", wb_mutate=lambda wb: wb["RawData"].delete_cols(10))
        _, res, fails, cannot = self.run_checks("case_column_deleted", final)
        self.assertEqual(res["extraction_status"]["dependencies"]["case_flag"]["status"], "confirmed_missing")
        self.assertEqual(fails, {4, 6, 7, 8, 9, 16, 19} | set(range(46, 56))); self.assertEqual(cannot, set())
        self.assertEqual(res["items"][4]["evidence"]["violations"][0]["kind"], "confirmed_missing_column"); self.assertEqual(res["items"][10]["verdict"], "pass")
        final2 = self.variant("strange_case_column_name", wb_mutate=lambda wb: rename_headers(wb, {"Case Pack Error Flag": "Case Packaging Validation"}))
        _, res2, fails2, cannot2 = self.run_checks("strange_case_column_name", final2)
        self.assertEqual(res2["extraction_status"]["dependencies"]["case_flag"]["status"], "unmapped")
        self.assertEqual(fails2, set()); self.assertEqual(cannot2, {4, 6, 7, 8, 9, 10, 16, 19} | set(range(46, 56)))
        self.assertEqual({res2["items"][i]["attribution"] for i in cannot2}, {"grader_extraction"})
        self.assertEqual(res2["items"][4]["evidence"]["unassessable"][0]["detail"], ["case packaging validation"])

    def test_id_format_variants_identify_every_row(self):
        """format_all_* / format_one_*: case, zero padding, outer and inner spaces are source-format rules;
        the normalisation is recorded per row and nothing is a collision."""
        def ids(kind, one):
            def mutate(wb):
                s = wb["RawData"]
                for row in list(s.iter_rows(min_row=2))[:1 if one else s.max_row]:
                    for c in row[:2]:
                        x = c.value
                        c.value = {"lower": x.lower(), "padding": x.replace("PO", "PO0").replace("SKU-", "SKU-0"), "outer_spaces": "  " + x + "  ", "inner_spaces": x.replace("PO", "PO ").replace("SKU-", "SKU - ")}[kind]
            return mutate
        for kind in ("lower", "padding", "outer_spaces", "inner_spaces"):
            for one in (False, True):
                name = f"format_{'one' if one else 'all'}_{kind}"
                with self.subTest(variant=name):
                    final = self.variant(name, wb_mutate=ids(kind, one))
                    _, res, fails, cannot = self.run_checks(name, final)
                    self.assertEqual((fails, cannot), (set(), set()))
                    pr = res["extraction_status"]["pipeline"]["parse_rows"]
                    self.assertEqual(pr["collisions"], []); self.assertTrue(pr["id_normalisation"])
                    self.assertTrue(all(r["raw"] != r["norm"] for r in pr["id_normalisation"]))
        self.assertEqual(CK.normalize_id("po", " po 01005 ")["norm"], "PO1005"); self.assertEqual(CK.normalize_id("sku", "sku - 00101")["norm"], "SKU-0101")
        self.assertEqual(CK.normalize_id("po", "INVALID-ID")["status"], "unparseable")

    def test_legal_id_variant_duplicate_is_a_duplicate_row_not_a_collision(self):
        """Codex extraction review R5 (same_entity_variant_duplicate). Old expectation (close-out round): the lowercase
        duplicate of row 2 was a 'collision' and every identity item was cannot_assess. New expectation: case is a
        legal format variant of the same reference entity, so the appended row is a duplicate business row -> the
        row-set items FAIL under the approved row-set rule (extra 1, duplicated 1), nothing is a collision, the
        variant is recorded, and the named lines pass. Basis: R5 (collision = two distinct REFERENCE entities with one
        normalised id); the approved duplicate-row rule of items 5/6/7/18/19/20. Scoring behaviour changes from
        cannot_assess to FAIL for this layout."""
        def mutate(wb):
            s = wb["RawData"]; vals = [c.value for c in s[2]]; vals[0], vals[1] = vals[0].lower(), vals[1].lower(); s.append(vals)
        final = self.variant("variant_duplicate_lowercase", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("variant_duplicate_lowercase", final)
        pr = res["extraction_status"]["pipeline"]["parse_rows"]
        self.assertEqual(pr["collisions"], []); self.assertEqual(res["extraction_status"]["dependencies"]["line_identity"]["status"], "ok")
        self.assertEqual([(v["kind"], v["norm"], v["originals"]) for v in pr["id_variants"]], [("po", "PO1005", ["PO1005", "po1005"]), ("sku", "SKU-0101", ["SKU-0101", "sku-0101"])])
        self.assertEqual(fails, ROWSET_ITEMS); self.assertEqual(cannot, set())
        rc = res["extraction_status"]["row_completeness"]
        self.assertEqual((rc["deliverable_rows"], len(rc["extra"]), len(rc["duplicates"]), rc["missing_count"]), (42, 1, 1, 0))
        self.assertIn("duplicated 1", res["items"][5]["note"]); self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in range(31, 56)))

    def test_reference_collision_makes_the_affected_identity_items_cannot_assess(self):
        """Codex extraction review R5 (reference_collision_po / _sku): two DISTINCT reference entities whose ids normalise
        to one identifier (synthetic reference; the real source has none). Old behaviour: the second entity's row was
        an extra row and the row-set items FAILed. New: a reference collision is recorded with originals, normalised id,
        entities and rows; the row-set items and the named lines whose ids collide are cannot_assess (grader side:
        the normalisation rules cannot tell the entities apart); nothing is merged, nothing FAILs; unrelated named
        lines and the per-row items are still graded."""
        for kind, affected_lines in (("po", {37, 38, 39, 50}), ("sku", set())):
            with self.subTest(kind=kind):
                ref = copy.deepcopy(REFERENCE); first = ref["lines"][0]; second = copy.deepcopy(first)
                second[kind] = ("PO0" + first["po"][2:]) if kind == "po" else ("SKU-0" + first["sku"][4:]); second["units"] = first["units"] + 1
                ref["lines"].append(second)
                def mutate(wb, second=second):
                    s = wb["RawData"]; row = [c.value for c in s[2]]; row[0], row[1], row[2] = second["po"], second["sku"], second["units"]; s.append(row)
                final = self.variant(f"reference_collision_{kind}", wb_mutate=mutate)
                work = os.path.join(self.base, "work", f"reference_collision_{kind}")
                ex = X.extract_all(final, work, recalc=False)
                res = CK.run_checks(ex, ref, RUBRIC, integrity={XLSX: True})
                fails = {i for i, r in res["items"].items() if r["verdict"] == "fail"}; cannot = {i for i, r in res["items"].items() if r["verdict"] == "cannot_assess"}
                TABLE[f"reference_collision_{kind}"] = {"fail": sorted(fails), "cannot_assess": sorted(cannot), "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}
                col = res["extraction_status"]["pipeline"]["parse_rows"]["collisions"]
                self.assertEqual(len(col), 1); c = col[0]
                self.assertEqual((c["kind"], c["normalised"], c["reference_originals"]), (kind, first[kind], sorted([first[kind], second[kind]])))
                self.assertEqual([e["original"] for e in c["entities"]], sorted([first[kind], second[kind]])); self.assertIn(len(ref["lines"]) - 1, c["reference_rows"])
                self.assertEqual(res["extraction_status"]["dependencies"]["line_identity"]["status"], "collision")
                self.assertEqual(fails, set()); self.assertEqual(cannot, ROWSET_ITEMS | {7} | affected_lines)  # 7 needs the line identity; 18–20 sum the column (approved 2026-10-31)
                self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_extraction"})
                self.assertEqual({res["items"][i]["verdict"] for i in {8, 9, 10, 12, 13, 15, 16, 17, 18, 19, 20} | (set(range(31, 56)) - affected_lines)}, {"pass"})
                if affected_lines:
                    u = res["items"][37]["evidence"]["unassessable"][0]
                    self.assertEqual((u["kind"], u["field"], u["detail"]["reference_collision"]), ("collision", "line_identity", {"po": "PO1005"}))

    def test_whole_sheet_id_variants_resolve_to_the_reference_entities(self):
        """Every PO / SKU written in lowercase: legal variants of the same entities -> graded like the positive fixture."""
        def mutate(wb):
            for row in wb["RawData"].iter_rows(min_row=2):
                for c in row[:2]:
                    c.value = c.value.lower()
        self.assert_like_positive("all_lowercase_ids", self.variant("all_lowercase_ids", wb_mutate=mutate))

    def test_ambiguous_flag_column_with_error_value_makes_item_10_cannot_assess(self):
        """new_price_flag_ambiguity: a second price-flag candidate holding #VALUE! is never read by any check;
        item 10 (no error values in the added columns) cannot be assessed, not passed."""
        def mutate(wb):
            s = wb["RawData"]; j = s.max_column + 1; s.cell(1, j, "Price Error")
            for r in range(2, s.max_row + 1):
                s.cell(r, j, "#VALUE!" if r == 2 else 0)
        final = self.variant("price_flag_ambiguity_error", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("price_flag_ambiguity_error", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, {4, 5, 8, 9, 10, 15, 18} | set(range(31, 46)))
        self.assertEqual(res["items"][10]["attribution"], "grader_extraction"); self.assertEqual(res["items"][10]["evidence"]["unassessable"][0]["field"], "price_flag")
        self.assertEqual([c["header"] for c in res["extraction_status"]["dependencies"]["price_flag"]["candidates"]], ["price mismatch flag", "price error"])

    def test_conjunction_confirmed_violation_plus_unassessable_input_fails(self):
        """new_formula_and_missing_column: price-flag formulas unrecalculated (grader) AND the case-flag column
        deleted (confirmed missing). Item 4 (four columns present) has one confirmed violation -> FAIL even
        though the other input is unassessable; items that need only the price column stay cannot_assess."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        def mutate(wb):
            v_partial_formula("price")(wb); wb["RawData"].delete_cols(10)
        final = self.variant("formula_and_missing_column", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("formula_and_missing_column", final, recalc=True, runner=failing)
        dep = res["extraction_status"]["dependencies"]
        self.assertEqual((dep["price_flag"]["status"], dep["case_flag"]["status"]), ("grader_error", "confirmed_missing"))
        self.assertEqual(res["items"][4]["verdict"], "fail"); self.assertEqual(res["items"][4]["evidence"]["violations"][0]["kind"], "confirmed_missing_column")
        self.assertEqual(res["items"][4]["evidence"]["unassessable"], [])  # presence of the price column is established even without values
        self.assertEqual(fails, {4, 6, 7, 8, 9, 16, 19} | set(range(46, 56)))
        self.assertEqual(cannot, {5, 10, 15, 18} | set(range(31, 46))); self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_recalculation"})
        self.assertEqual(res["items"][8]["evidence"]["violations"][0]["kind"], "confirmed_missing_column"); self.assertTrue(res["items"][8]["evidence"]["unassessable"])

    def test_unrecalculated_source_quantity_is_a_grader_side_unidentified_row(self):
        """source_quantity_formula_failed (Codex extra probe): the quantity cell holds =60 and the converter
        failed; the row is unidentified for a grader-side reason, so 5/6/7/18/19/20 are cannot_assess with
        grader attribution (not a changed row, not a model FAIL); named lines in other rows still pass."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        final = self.variant("source_quantity_formula", wb_mutate=lambda wb: wb["RawData"].cell(2, 3, "=60"))
        _, res, fails, cannot = self.run_checks("source_quantity_formula", final, recalc=True, runner=failing)
        self.assertEqual(fails, set()); self.assertEqual(cannot, ROWSET_ITEMS)
        rs = res["extraction_status"]["row_completeness"]
        self.assertEqual((rs["unidentified_rows"], rs["unidentified_grader_side"], rs["missing_count"], rs["confirmed_missing_lower_bound"]), (1, 1, 1, 0))
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_recalculation"})
        self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in range(31, 56)))

    def test_recalculated_error_values_are_confirmed_invalid(self):
        """A recalculation that succeeds and yields #VALUE! in a flag cell (I2: PO1005/SKU-0101/60, not a named line) is a
        real error value: item 10 and the whole-column items reading that flag FAIL (confirmed invalid), distinct from
        the unrecalculated case. Old expectation (close-out round): the named lines 31–45 also FAILed from the
        column-level status. New expectation (Codex extraction review R3): rubric 31–45 are per-PO/SKU checks and
        read only their own row's cell, so an error in an unrelated row leaves them PASS. Scoring behaviour changes
        from FAIL to PASS for 31–45 in this layout; 5, 8, 9, 10, 15, 18 stay FAIL."""
        positive_xlsx = os.path.join(self.positive, XLSX)

        def converter(cmd, **kw):
            scratch = next(a for a in cmd if a.endswith(":/work")).split(":/work")[0]
            wb = openpyxl.load_workbook(positive_xlsx); wb["RawData"].cell(2, 9, "#VALUE!"); wb.save(os.path.join(scratch, "out", "in.xlsx"))
            return SimpleNamespace(returncode=0, stdout="SOFFICE_RC=0\n", stderr="")
        final = self.variant("recalc_error_value", wb_mutate=v_formulas)
        ex, res, fails, cannot = self.run_checks("recalc_error_value", final, recalc=True, runner=converter)
        self.assertEqual(ex["xlsx"][XLSX]["recalc"]["status"], "ok")
        self.assertEqual(res["extraction_status"]["dependencies"]["price_flag"]["status"], "confirmed_invalid")
        self.assertEqual(res["extraction_status"]["dependencies"]["price_flag"]["error_cells"], ["I2"])
        self.assertEqual(fails, {5, 8, 9, 10, 15, 18}); self.assertEqual(cannot, set())
        self.assertEqual(res["items"][10]["evidence"]["violations"][0]["kind"], "error_values"); self.assertEqual(res["items"][10]["attribution"], "model_caused")
        self.assertTrue(all(res["items"][i]["verdict"] == "pass" and res["items"][i]["evidence"]["row"] != 2 for i in range(31, 46)))  # each named line judged from its own row

    def test_resource_exception_during_format_check_is_grader_caused(self):
        """new_format_fault: MemoryError inside openpyxl.load_workbook during the structural check must not become
        model_caused_corrupt: the zip and XML parts are independently valid -> item 1 passes, the rest is
        cannot_assess with grader attribution."""
        final = self.variant("format_memory_error")
        with patch.object(X.openpyxl, "load_workbook", side_effect=MemoryError("synthetic grader memory exhaustion")):
            ex, res, fails, cannot = self.run_checks("format_memory_error", final)
        info = ex["xlsx"][XLSX]
        self.assertEqual((info["error_class"], info["format"]["error_kind"], info["format"]["structure_ok"]), ("grader_error", "resource_error", True))
        self.assertEqual(fails, set()); self.assertEqual(cannot, WORKBOOK); self.assertEqual(res["items"][1]["verdict"], "pass")
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_extraction"})

    def test_valid_zip_with_malformed_worksheet_xml_is_model_caused(self):
        def corrupt_sheet_xml(final):
            p = os.path.join(final, XLSX); tmp = os.path.join(final, "tmp.xlsx")
            with zipfile.ZipFile(p) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename == "xl/worksheets/sheet1.xml":
                        data = data[: len(data) // 2] + b"<<<broken"
                    zout.writestr(item, data)
            os.replace(tmp, p)
        final = self.variant("corrupt_sheet_xml", final_mutate=corrupt_sheet_xml)
        ex, res, fails, cannot = self.run_checks("corrupt_sheet_xml", final, integrity="verified")
        fmt = ex["xlsx"][XLSX]["format"]
        self.assertEqual((fmt["zip_ok"], fmt["content_types"], fmt["workbook_part"], fmt["xml_parts_ok"], fmt["error_kind"]), (True, True, True, False, "xml_error"))
        self.assertEqual(ex["xlsx"][XLSX]["error_class"], "original_corrupt")
        self.assertEqual(fails, WORKBOOK | {1}); self.assertEqual({res["items"][i]["attribution"] for i in fails}, {"model_caused_corrupt"})
        _, res2, fails2, cannot2 = self.run_checks("corrupt_sheet_xml_unverified", final, integrity="unknown")
        self.assertEqual(fails2, set()); self.assertEqual({res2["items"][i]["attribution"] for i in cannot2}, {"unknown"})

    # ---------------------------------------------------------------- B4: Word counts bound to their category phrase
    def test_swapped_word_counts_do_not_pass(self):
        final = self.variant("swapped_word_counts", final_mutate=docx_with(["The audit identified 10 price mismatch errors and 15 case pack errors."]))
        _, res, fails, cannot = self.run_checks("swapped_word_counts", final)
        self.assertEqual(fails, {25, 26}); self.assertEqual(cannot, set())
        self.assertEqual((res["items"][25]["deliverable_value"], res["items"][26]["deliverable_value"]), (10, 15))
        self.assertTrue(res["items"][25]["evidence"]["quotes"])

    def test_conflicting_word_counts_are_cannot_assess(self):
        final = self.variant("conflicting_word_counts", final_mutate=docx_with(["15 price mismatch errors were identified.", "In total 14 price mismatch errors appear in the export; 10 case pack errors were found."]))
        _, res, fails, cannot = self.run_checks("conflicting_word_counts", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, {25}); self.assertEqual(res["items"][25]["deliverable_value"], [14, 15])
        self.assertEqual(res["items"][26]["verdict"], "pass")

    def test_unbound_numbers_are_cannot_assess_not_pass(self):
        final = self.variant("unbound_word_counts", final_mutate=docx_with(["Totals: 15 and 10 errors were found across the price and case checks."]))
        _, res, fails, cannot = self.run_checks("unbound_word_counts", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, {25, 26})


    # ---------------------------------------------------------------- approved adjudication 2026-10-31 (preregistration 2.4): scope of items 7 and 18–20
    def test_row_set_defects_act_through_items_5_and_6_only(self):
        """Approved 2026-10-31: a missing, extra, duplicated or changed row fails items 5 and 6 (C1 fails through them) and no other
        ordinary item by itself; item 7 checks only the identified non-CASE lines; items 18–20 compare the column sums over all
        delivered rows with 15 / 10 / 25 and are judged independently. Old expectation: 7 and 18–20 failed with the row set.
        A deleted flagged line also fails its own named item and the reconciliation items whose column sum it changes."""
        def delete_line(po, sku, units):
            def mutate(wb):
                s = wb["RawData"]; row = next(r for r in range(2, s.max_row + 1) if (s.cell(r, 1).value, s.cell(r, 2).value, s.cell(r, 3).value) == (po, sku, units)); s.delete_rows(row)
            return mutate
        cases = {"scope_duplicate_zero_error_row": (v_dup_extra, {5, 6}, {7, 18, 19, 20}, (15, 10, 25)),
                 "scope_deleted_price_only_line": (delete_line("PO1001", "SKU-0112", 96), {5, 6, 15, 17, 18, 20, 31}, {7, 19}, (14, 10, 24)),
                 "scope_deleted_case_only_line": (delete_line("PO1003", "SKU-0111", 52), {5, 6, 16, 17, 19, 20, 47}, {7, 18}, (15, 9, 24)),
                 "scope_deleted_zero_error_row": (delete_line("PO1005", "SKU-0101", 60), {5, 6}, {7, 18, 19, 20}, (15, 10, 25))}
        for name, (mutate, exp_fail, exp_pass, sums) in cases.items():
            with self.subTest(case=name):
                final = self.variant(name, wb_mutate=mutate)
                _, res, fails, cannot = self.run_checks(name, final)
                self.assertEqual(fails, exp_fail, sorted(fails ^ exp_fail)); self.assertEqual(cannot, set())
                self.assertEqual({res["items"][i]["verdict"] for i in exp_pass}, {"pass"})
                self.assertEqual(res["critical"]["C1"]["status_from_deterministic"], "fail")
                self.assertEqual(tuple(res["items"][i]["deliverable_value"] for i in (18, 19, 20)), sums)  # the sums over the delivered rows are reported either way
                self.assertEqual(res["items"][5]["evidence"]["violations"][0]["kind"], "row_set")
                for i in (7, 18, 19, 20):
                    self.assertNotIn("row_set", res["items"][i]["dependencies"]); self.assertFalse(res["items"][i]["fail_on_own"]["row_set"])

    # ---------------------------------------------------------------- Codex Stage 3b review (logs/stage3b-review-js7f8gca): item 7 applicability, split-table overlap
    def test_item_7_applies_only_to_non_case_lines_decided_from_the_row_uom(self):
        """item7_case_blank: J5 (case flag of the CASE line PO1002/SKU-0103/120) blank. Before: item 7 FAILed on the blank cell.
        Now: the row's own UOM decides applicability first; a CASE line is outside rubric 7 whatever its flag (6, 8, 9, 16, 19
        still FAIL on the invalid cell). A non-CASE line (EA, or blank UOM) with a blank, text or 1 flag FAILs item 7."""
        def set_case_flag(predicate, value):
            def mutate(wb):
                s = wb["RawData"]; row = next(r for r in range(2, s.max_row + 1) if predicate(s, r)); s.cell(row, 10).value = value
            return mutate
        is_case = lambda s, r: s.cell(r, 6).value == "CASE"
        is_ea = lambda s, r: s.cell(r, 6).value == "EA"
        final = self.variant("item7_case_line_blank_flag", wb_mutate=set_case_flag(is_case, None))
        _, res, fails, cannot = self.run_checks("item7_case_line_blank_flag", final)
        self.assertEqual(fails, {6, 8, 9, 16, 19}); self.assertEqual(cannot, set()); self.assertEqual(res["items"][7]["verdict"], "pass")
        self.assertEqual(res["items"][6]["evidence"]["violations"][0]["kind"], "empty")
        for label, value, kind in (("blank", None, "empty"), ("text", "maybe", "non_binary"), ("one", 1, "wrong_flag")):
            with self.subTest(ea_flag=label):
                final2 = self.variant(f"item7_ea_line_{label}_flag", wb_mutate=set_case_flag(is_ea, value))
                _, res2, fails2, cannot2 = self.run_checks(f"item7_ea_line_{label}_flag", final2)
                self.assertIn(7, fails2); self.assertEqual(cannot2, set()); self.assertEqual(res2["items"][7]["evidence"]["violations"][0]["kind"], kind)
                self.assertNotIn("row_set", res2["items"][7]["dependencies"]); self.assertIn("uom", res2["items"][7]["dependencies"])
        def blank_uom_flag_one(wb):
            s = wb["RawData"]; row = next(r for r in range(2, s.max_row + 1) if s.cell(r, 6).value == "EA"); s.cell(row, 6).value = None; s.cell(row, 10).value = 1
        final3 = self.variant("item7_blank_uom_flag_one", wb_mutate=blank_uom_flag_one)
        _, res3, fails3, _ = self.run_checks("item7_blank_uom_flag_one", final3)
        self.assertIn(7, fails3); self.assertEqual(res3["items"][7]["evidence"]["violations"][0]["kind"], "wrong_flag")  # blank UOM counts as not CASE (rubric text)

    def test_split_tables_with_a_repeated_identity_do_not_double_count_into_a_fail(self):
        """candidate_overlap: the 41 rows split 21 + 20 over two sheets and one price-error line (flags 1 / 0 / total 1) shown
        again in the second sheet. Before: the two sheets were summed as 42 rows (16 / 10 / 26) and 18, 20 FAILed as
        model-caused. Now: the repeated identity is recorded with sheet, row and values; 18 and 20 are cannot_assess
        (grader-side uncertainty about the count scope, both scopes reported); 19 (unaffected column) passes; a repeated
        zero-error line leaves 18–20 reliable; an invalid cell still FAILs its item regardless of the overlap."""
        def split_repeat(selector):
            def mutate(wb):
                s = wb["RawData"]; rows = list(s.values); header, body = rows[0], rows[1:]; s.delete_rows(2, s.max_row)
                for row in body[:21]:
                    s.append(row)
                other = wb.create_sheet("RawData continued"); other.append(header)
                for row in body[21:]:
                    other.append(row)
                other.append(next(row for row in body[:21] if selector(row)))
            return mutate
        final = self.variant("split_overlap_price_error_line", wb_mutate=split_repeat(lambda row: row[8] == 1 and row[9] == 0))
        _, res, fails, cannot = self.run_checks("split_overlap_price_error_line", final)
        self.assertEqual(fails, set()); self.assertEqual(cannot, {5, 6, 15, 16, 17, 18, 20})
        ov = res["extraction_status"]["dependencies"]["cross_sheet_overlap"]
        self.assertEqual(len(ov), 1); self.assertEqual([o["sheet"] for o in ov[0]["occurrences"]], ["RawData", "RawData continued"]); self.assertEqual(ov[0]["occurrences"][0]["values"], {"price_flag": 1, "case_flag": 0, "total": 1})
        u = res["items"][18]["evidence"]["unassessable"][0]
        self.assertEqual((u["kind"], u["detail"]["sum_all_rows"], u["detail"]["sum_one_copy_per_identity"], res["items"][18]["attribution"]), ("split_overlap", 16, 15, "grader_extraction"))
        self.assertEqual((res["items"][19]["verdict"], res["items"][19]["deliverable_value"]), ("pass", 10))
        final2 = self.variant("split_overlap_zero_error_line", wb_mutate=split_repeat(lambda row: row[11] == 0))
        _, res2, fails2, cannot2 = self.run_checks("split_overlap_zero_error_line", final2)
        self.assertEqual(fails2, set()); self.assertEqual(cannot2, {5, 6, 15, 16, 17}); self.assertEqual({res2["items"][i]["verdict"] for i in (18, 19, 20)}, {"pass"})
        def overlap_plus_error(wb):
            split_repeat(lambda row: row[8] == 1 and row[9] == 0)(wb); wb["RawData continued"].cell(3, 9, "#VALUE!")
        final3 = self.variant("split_overlap_plus_error", wb_mutate=overlap_plus_error)
        _, res3, fails3, _ = self.run_checks("split_overlap_plus_error", final3)
        self.assertIn(18, fails3); self.assertEqual(res3["items"][18]["evidence"]["violations"][0]["kind"], "error_value")  # a confirmed invalid cell is not masked by the overlap

    def test_multiple_overlaps_never_infer_a_fail_from_the_two_extreme_scopes(self):
        """Codex stage3b-closeout2 review: with two price-error lines repeated across the split sheets and one other price-only
        line deleted, the price column sums to 16 over all rows and 14 with one copy per repeated identity, while a reading in
        which only one repeat is a listing overlap gives 15. Old code: FAILed item 18 because neither extreme equalled 15. Now:
        18 and 20 are cannot_assess with both extremes recorded as evidence (grader-side uncertainty); 19 (case column
        unaffected) passes on its reliable total; the deleted line's own named item FAILs (confirmed absent, no unidentified row);
        5, 6, 15–17 stay cannot_assess under the split rule."""
        def mutate(wb):
            s = wb["RawData"]; rows = list(s.values); header, body = rows[0], rows[1:]
            price_only = [row for row in body[:21] if row[8] == 1 and row[9] == 0]
            repeat_a, repeat_b, deleted = price_only[0], price_only[1], price_only[2]
            s.delete_rows(2, s.max_row)
            for row in body[:21]:
                if row != deleted:
                    s.append(row)
            other = wb.create_sheet("RawData continued"); other.append(header)
            for row in body[21:]:
                other.append(row)
            other.append(repeat_a); other.append(repeat_b)
            self._deleted_identity = (deleted[0], deleted[1], deleted[2])
        final = self.variant("split_two_overlaps_one_deleted", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("split_two_overlaps_one_deleted", final)
        deleted_item = next(i for i, (po, sku, u, kind) in CK.PER_LINE.items() if (po, sku, u) == self._deleted_identity and kind == "price")
        self.assertEqual(fails, {deleted_item}); self.assertEqual(res["items"][deleted_item]["evidence"]["violations"][0]["kind"], "line_absent")
        self.assertEqual(cannot, {5, 6, 15, 16, 17, 18, 20})
        for i in (18, 20):
            self.assertEqual(res["items"][i]["attribution"], "grader_extraction"); self.assertEqual(res["items"][i]["evidence"]["violations"], [])
            u = res["items"][i]["evidence"]["unassessable"][0]
            self.assertEqual((u["kind"], u["field"], len(u["detail"]["identities"])), ("split_overlap", "price_flag" if i == 18 else "total", 2))
        ov = res["items"][18]["evidence"]["cross_sheet_overlap"]
        self.assertEqual((ov["sum_all_rows"], ov["sum_one_copy_per_identity"], ov["reference"]), (16, 14, 15))
        self.assertEqual({(o["sheet"]) for ident in ov["identities"] for o in ident["occurrences"]}, {"RawData", "RawData continued"})
        self.assertEqual((res["items"][19]["verdict"], res["items"][19]["deliverable_value"]), ("pass", 10))

    # ---------------------------------------------------------------- Codex extraction review (logs/extraction-review-0r3d__40): R1 required numeric cells
    def test_blank_and_non_finite_totals_are_confirmed_invalid_not_skipped(self):
        """R1 (new_blank_total / new_nonfinite_total / blank_nonzero / nan_nonzero): the Total Errors cell of PO1002/SKU-0103/120
        (expected 1) set to blank, 'NaN', 'Infinity' and 'n/a'. Before: the comparison was skipped and 8, 17, 20 PASSED
        (C1 and C2 'pass'). Now: a reliably read cell that is not a finite number where the rubric requires one is a
        confirmed invalid value -> 8, 17, 20 FAIL with the cell and the original value as evidence; no other item moves."""
        def set_total(value):
            def mutate(wb):
                s = wb["RawData"]; row = next(r for r in range(2, s.max_row + 1) if (s.cell(r, 1).value, s.cell(r, 2).value, s.cell(r, 3).value) == ("PO1002", "SKU-0103", 120))
                s.cell(row, 12).value = value
            return mutate
        for label, value, kind in (("blank", None, "empty"), ("nan", "NaN", "non_finite"), ("inf", "Infinity", "non_finite"), ("text", "n/a", "non_numeric")):
            with self.subTest(total=label):
                final = self.variant(f"total_{label}_nonzero_row", wb_mutate=set_total(value))
                _, res, fails, cannot = self.run_checks(f"total_{label}_nonzero_row", final)
                self.assertEqual(fails, {8, 17, 20}); self.assertEqual(cannot, set())
                for i in (8, 17, 20):
                    v = res["items"][i]["evidence"]["violations"][0]
                    self.assertEqual((v["kind"], v["cell"], v["row"], v["value"], res["items"][i]["attribution"]), (kind, "L5", 5, value, "model_caused"))
                self.assertEqual({k: v["status_from_deterministic"] for k, v in res["critical"].items()}, {"C1": "fail", "C2": "fail", "C3": "not_confirmed"})
                self.assertEqual(res["extraction_status"]["dependencies"]["total"]["invalid_cells"][0]["kind"], kind)
        # a blank total on a zero-error row is the same confirmed invalid value (the rubric requires a number on every line)
        def blank_zero(wb):
            wb["RawData"].cell(2, 12).value = None
        final = self.variant("total_blank_zero_row", wb_mutate=blank_zero)
        _, res, fails, cannot = self.run_checks("total_blank_zero_row", final)
        self.assertEqual(fails, {8, 17, 20}); self.assertEqual(res["items"][8]["evidence"]["violations"][0]["cell"], "L2")

    def test_blank_or_text_flag_is_a_confirmed_invalid_value_for_every_item_that_reads_it(self):
        """R1 applied to the flag columns: a blank Price Mismatch flag on a zero-error line (I2) is reliably read and is
        neither 0 nor 1. Rubric 5 ('... and 0 otherwise'), 8, 9 ('binary across all rows'), 15 and 18 all require the
        value, so they FAIL on that cell; the named lines (other rows) and the case-flag items pass. Note: the close-out
        implementation read a blank flag as 0 for 5/6/7/18/19 (an implementation choice never written into the
        preregistration); the extraction review's R1 rule replaces it. A text value that is not a flag ('maybe') behaves
        the same with kind non_binary."""
        for label, value, kind in (("blank", None, "empty"), ("text", "maybe", "non_binary")):
            with self.subTest(flag=label):
                def mutate(wb, value=value):
                    wb["RawData"].cell(2, 9).value = value
                final = self.variant(f"price_flag_{label}_zero_row", wb_mutate=mutate)
                _, res, fails, cannot = self.run_checks(f"price_flag_{label}_zero_row", final)
                self.assertEqual(fails, {5, 8, 9, 15, 18}); self.assertEqual(cannot, set())
                self.assertEqual(res["items"][5]["evidence"]["violations"][0]["kind"], kind); self.assertEqual(res["items"][9]["evidence"]["violations"][0]["cells"], ["I2"])
                self.assertEqual(res["items"][10]["verdict"], "pass")  # not a spreadsheet error value
                self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in range(31, 56)))

    # ---------------------------------------------------------------- R2: formula state of source fields and summary cells
    def test_unrecalculated_source_price_or_case_pack_holds_the_row_by_identity(self):
        """R2 (new_source_price_formula / new_source_case_formula): one source cell (D2 entered price, or G2 case pack) is an
        equal-value formula and the converter fails. Before: the row's business key had None in that field -> 'changed'
        row -> 5/6/7/18/19/20 FAILED as model-caused. Now: the row keeps its identity, is held against its input line
        (not missing, not changed, not zero), the row set is partial for a grader-side reason -> 5/6/7/18/19/20
        cannot_assess (grader_caused_recalculation); 8, 9, 10, 15–17, 31–55 pass."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        for field, col in (("price", 4), ("case_pack", 7)):
            with self.subTest(field=field):
                def mutate(wb, col=col):
                    s = wb["RawData"]; s.cell(2, col, "=" + str(s.cell(2, col).value))
                final = self.variant(f"source_{field}_formula_failed", wb_mutate=mutate)
                _, res, fails, cannot = self.run_checks(f"source_{field}_formula_failed", final, recalc=True, runner=failing)
                self.assertEqual(fails, set()); self.assertEqual(cannot, ROWSET_ITEMS)
                self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_recalculation"})
                rc = res["extraction_status"]["row_completeness"]
                self.assertEqual((rc["status"], rc["identified_rows"], rc["verified_rows"], rc["held_rows"], rc["missing_count"], len(rc["changed"]), len(rc["extra"])), ("partial", 41, 40, 1, 0, 0, 0))
                self.assertEqual(rc["held_by_identity"], [{"row": 2, "identity": ["PO1005", "SKU-0101", "60"], "unrecalculated_cells": [f"{'D' if field == 'price' else 'G'}2"]}])
                self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in {7, 8, 9, 10, 15, 16, 17, 18, 19, 20} | set(range(31, 56))))  # approved 2026-10-31: 7 and the column sums do not need the row set

    def test_unrecalculated_summary_cells_are_grader_side_not_fail_and_not_pass(self):
        """R2 (new_summary_formulas_failed): every summary measure (SKU rows and grand total) is an equal-value formula
        and the converter fails. Before: 56–62 FAILED ('total unreadable') and 15–17 PASSED with zero comparisons.
        Now: every summary cell is read through read_value; 15, 16, 17, 56–62 are cannot_assess (grader side) with
        the cell named; nothing FAILs; the detail items are unaffected."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        def mutate(wb):
            s = wb["Summary"]
            for row in s.iter_rows():
                if isinstance(row[0].value, str) and (row[0].value.startswith("SKU-") or row[0].value == "Grand Total"):
                    for c in row[1:4]:
                        if isinstance(c.value, (int, float)):
                            c.value = "=" + str(c.value)
        final = self.variant("summary_formulas_failed", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("summary_formulas_failed", final, recalc=True, runner=failing)
        self.assertEqual(fails, set()); self.assertEqual(cannot, {15, 16, 17} | set(range(56, 63)))
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_recalculation"})
        u = res["items"][56]["evidence"]["unassessable"][0]
        self.assertEqual((u["kind"], u["field"], u["detail"]["cell"].startswith("Summary!D")), ("grader_error", "summary_measures", True))
        gt = next(r for r in range(1, 40) if openpyxl.load_workbook(os.path.join(final, XLSX))["Summary"].cell(r, 1).value == "Grand Total")
        self.assertEqual(res["items"][15]["evidence"]["unassessable"][0]["detail"]["cell"], f"Summary!B{gt}")  # the grand-total cell (16 SKU rows + header -> row 18)
        self.assertEqual({res["items"][i]["verdict"] for i in {5, 6, 7, 8, 9, 10, 12, 13, 14, 18, 19, 20, 22}}, {"pass"})

    def test_summary_cell_unassessable_plus_confirmed_detail_error_fails_with_both_recorded(self):
        """R2 conjunction: the summary grand-total price cell is an unrecalculated formula (unassessable) and the detail
        price flag of row 5 is #VALUE! (confirmed invalid). Item 15 FAILs on the confirmed violation and keeps the
        unassessable summary cell in its evidence; the named line of row 5 (item 32) FAILs on its own cell."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        def mutate(wb):
            s = wb["Summary"]; gt = next(r for r in range(1, s.max_row + 1) if s.cell(r, 1).value == "Grand Total"); s.cell(gt, 2, "=" + str(s.cell(gt, 2).value))
            wb["RawData"].cell(5, 9, "#VALUE!")
        final = self.variant("summary_unrecalculated_and_detail_error", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("summary_unrecalculated_and_detail_error", final, recalc=True, runner=failing)
        self.assertEqual(fails, {5, 8, 9, 10, 15, 18, 32}); self.assertEqual(cannot, set())
        ev = res["items"][15]["evidence"]
        self.assertEqual([(v["kind"], v["cell"]) for v in ev["violations"]], [("error_value", "I5")])
        gt = next(r for r in range(1, 40) if openpyxl.load_workbook(os.path.join(final, XLSX))["Summary"].cell(r, 1).value == "Grand Total")
        self.assertEqual([(u["kind"], u["field"], u["detail"]["cell"]) for u in ev["unassessable"]], [("grader_error", "summary_measures", f"Summary!B{gt}")])
        self.assertEqual(res["items"][32]["evidence"]["violations"][0]["cell"], "I5"); self.assertEqual(res["items"][31]["verdict"], "pass")

    # ---------------------------------------------------------------- R3: row-precise dependencies; violations and unassessable side by side
    def test_error_value_in_an_unrelated_row_does_not_fail_the_named_lines(self):
        """R3 (new_unrelated_price_error): I2 (PO1005/SKU-0101/60, no named line) holds #VALUE!. Items 31–45 are decided
        from their own row's cell -> PASS; 10 FAILs (confirmed error value); the whole-column items 5, 8, 9, 15, 18 FAIL."""
        final = self.variant("unrelated_price_error", wb_mutate=lambda wb: wb["RawData"].cell(2, 9, "#VALUE!"))
        _, res, fails, cannot = self.run_checks("unrelated_price_error", final)
        self.assertEqual(fails, {5, 8, 9, 10, 15, 18}); self.assertEqual(cannot, set())
        for i in range(31, 46):
            self.assertEqual((res["items"][i]["verdict"], res["items"][i]["deliverable_value"], res["items"][i]["evidence"]["violations"], res["items"][i]["evidence"]["unassessable"]), ("pass", 1, [], []), i)
            self.assertNotEqual(res["items"][i]["evidence"]["row"], 2)
        self.assertTrue(res["items"][31]["fail_on_own"]["row_scoped"])

    def test_error_value_and_unrecalculated_formula_in_one_column_keep_both_records(self):
        """R3 (new_error_and_unrecalculated): I2 = #VALUE! and I3 = '=0' with a failed conversion. Before: the column status
        'grader_error' took precedence and item 10 was cannot_assess. Now the column record carries both lists; item 10
        FAILs on the confirmed error value and records the unrecalculated cell as unassessable; the named line of row 3
        (none) is unaffected; 31–45 pass from their own cells."""
        failing = lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="synthetic converter failure")
        def mutate(wb):
            wb["RawData"].cell(2, 9, "#VALUE!"); wb["RawData"].cell(3, 9, "=0")
        final = self.variant("error_and_unrecalculated", wb_mutate=mutate)
        _, res, fails, cannot = self.run_checks("error_and_unrecalculated", final, recalc=True, runner=failing)
        dep = res["extraction_status"]["dependencies"]["price_flag"]
        self.assertEqual((dep["status"], [c["cell"] for c in dep["invalid_cells"]], [c["cell"] for c in dep["unreliable_cells"]], dep["error_cells"], dep["cells"]), ("confirmed_invalid", ["I2"], ["I3"], ["I2"], ["I3"]))
        self.assertEqual(fails, {5, 8, 9, 10, 15, 18}); self.assertEqual(cannot, set())
        ev = res["items"][10]["evidence"]
        self.assertEqual([(v["kind"], v["cells"]) for v in ev["violations"]], [("error_values", ["I2"])]); self.assertEqual([(u["kind"], u["detail"]["cells"]) for u in ev["unassessable"]], [("grader_error", ["I3"])])
        self.assertEqual([(v["cell"]) for v in res["items"][5]["evidence"]["violations"]], ["I2"]); self.assertEqual([u["cell"] for u in res["items"][5]["evidence"]["unassessable"]], ["I3"])
        self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in range(31, 56)))

    # ---------------------------------------------------------------- R4: complementary detail sheets exit safely
    def test_detail_rows_split_over_two_sheets_are_not_reported_missing(self):
        """R4 (detail_two_sheets): the 41 rows are split 21 + 20 over 'RawData' and 'RawData continued' (same headers).
        Before: one sheet was chosen and 20 delivered rows were FAILed as missing (5/6/7/15–20 and named lines). Now:
        identify_tables reports a 'split' with every candidate and its coverage; the row-set and reconciliation items are
        cannot_assess (no cross-sheet merge), nothing is asserted missing, the named lines are found in either sheet,
        and the per-row items run over both sheets. A confirmed error in the second sheet still FAILs its items."""
        def split(wb):
            s = wb["RawData"]; rows = list(s.values); s.delete_rows(23, s.max_row); t = wb.create_sheet("RawData continued"); t.append(rows[0])
            for r in rows[22:]:
                t.append(r)
        final = self.variant("detail_two_sheets", wb_mutate=split)
        _, res, fails, cannot = self.run_checks("detail_two_sheets", final)
        ident = res["extraction_status"]["pipeline"]["identify_tables"][XLSX]
        self.assertEqual(ident["status"], "split"); self.assertEqual([c["sheet"] for c in ident["candidates"]], ["RawData", "RawData continued"])
        self.assertEqual(set(ident["coverage"]), {"RawData", "RawData continued"}); self.assertTrue(all(v["only_in_this_sheet"] > 0 for v in ident["coverage"].values()))
        self.assertEqual(fails, set()); self.assertEqual(cannot, ROWSET_ITEMS | {15, 16, 17})  # approved 2026-10-31: 7 and 18–20 are decided from the rows of every candidate (old: cannot_assess with the row set)
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_extraction"})
        self.assertEqual(res["items"][5]["evidence"]["unassessable"][0]["kind"], "split_tables"); self.assertNotIn("row_completeness", res["extraction_status"])
        self.assertTrue(all(res["items"][i]["verdict"] == "pass" for i in {3, 4, 8, 9, 10, 12, 13, 14, 22} | set(range(31, 56)) | set(range(56, 63))))
        self.assertEqual(res["items"][45]["evidence"]["sheet"], "RawData continued"); self.assertTrue(res["detail_sheet"]["split"])
        # a confirmed error value in the second sheet is found by the per-row items; a wrong named flag there FAILs its line
        def split_error(wb):
            split(wb); wb["RawData continued"].cell(3, 9, "#VALUE!")
        final2 = self.variant("detail_two_sheets_error", wb_mutate=split_error)
        _, res2, fails2, cannot2 = self.run_checks("detail_two_sheets_error", final2)
        self.assertEqual(fails2, {5, 8, 9, 10, 15, 18}); self.assertEqual(res2["items"][10]["evidence"]["violations"][0]["cells"], ["RawData continued!I3"])
        def split_wrong(wb):
            split(wb); s = wb["RawData continued"]; row = next(r for r in range(2, s.max_row + 1) if (s.cell(r, 1).value, s.cell(r, 2).value) == ("PO1010", "SKU-0112")); s.cell(row, 9, 0)
        final3 = self.variant("detail_two_sheets_wrong_flag", wb_mutate=split_wrong)
        _, res3, fails3, cannot3 = self.run_checks("detail_two_sheets_wrong_flag", final3)
        self.assertEqual(fails3, {5, 8, 18, 45}); self.assertEqual(res3["items"][45]["evidence"]["violations"][0]["kind"], "wrong_flag")  # 18: the price-flag column sums to 14 across both sheets

    def test_full_table_plus_flagged_subset_sheet_selects_the_full_table(self):
        """A second detail-like sheet holding only the flagged lines (a subset) must not make the table ambiguous or split."""
        def subset(wb):
            s = wb["RawData"]; rows = list(s.values); t = wb.create_sheet("Flagged lines"); t.append(rows[0])
            for r in rows[1:]:
                if r[11]:
                    t.append(r)
        final = self.variant("full_plus_flagged_subset", wb_mutate=subset)
        _, res, fails, cannot = self.run_checks("full_plus_flagged_subset", final)
        self.assertEqual(res["extraction_status"]["pipeline"]["identify_tables"][XLSX]["status"], "ok"); self.assertEqual(res["detail_sheet"]["sheet"], "RawData")
        self.assertEqual((fails, cannot), (set(), set()))

    # ---------------------------------------------------------------- XML part validation cap is a grader resource limit
    def test_xml_part_above_the_validation_cap_is_a_grader_resource_limit(self):
        """new_xml_limit: with the grader's XML_PART_LIMIT lowered to 10 bytes every part is 'too large'. Before: this was
        reported as xml_error -> original_corrupt -> 52 model_caused_corrupt FAILs (item 1 included). Now: error_kind
        resource_limit, error_class grader_error, 0 FAIL, item 1 and the workbook items cannot_assess with grader
        attribution; the limit, every part's size and the file size are kept as evidence."""
        final = self.variant("xml_limit")
        with patch.object(X, "XML_PART_LIMIT", 10):
            ex, res, fails, cannot = self.run_checks("xml_limit", final)
        info = ex["xlsx"][XLSX]; fmt = info["format"]
        self.assertEqual((fmt["error_kind"], fmt["structure_ok"], fmt["zip_ok"], fmt["xml_parts_ok"], fmt["xml_parts_checked"]), ("resource_limit", False, True, False, 0))
        self.assertEqual((info["error_class"], info["exception_type"]), ("grader_error", "XmlPartLimit"))
        self.assertTrue(all(p["limit_bytes"] == 10 and p["bytes"] > 10 for p in fmt["resource_limit"])); self.assertEqual(info["file_bytes"], fmt["bytes"])
        self.assertEqual(fails, set()); self.assertEqual(cannot, WORKBOOK | {1})
        self.assertEqual({res["items"][i]["attribution"] for i in cannot}, {"grader_caused_extraction"})
        self.assertEqual(res["items"][1]["evidence"]["resource_limit"][0]["limit_bytes"], 10)
        # a genuinely malformed part is still structural damage, with any over-limit parts recorded next to it
        def corrupt_and_limit(final_dir):
            p = os.path.join(final_dir, XLSX); tmp = os.path.join(final_dir, "tmp.xlsx")
            with zipfile.ZipFile(p) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename == "docProps/core.xml":
                        data = b"<<<broken"
                    zout.writestr(item, data)
            os.replace(tmp, p)
        final2 = self.variant("xml_limit_and_corrupt", final_mutate=corrupt_and_limit)
        with patch.object(X, "XML_PART_LIMIT", 1000):
            ex2, res2, fails2, cannot2 = self.run_checks("xml_limit_and_corrupt", final2)
        self.assertEqual((ex2["xlsx"][XLSX]["format"]["error_kind"], ex2["xlsx"][XLSX]["error_class"]), ("xml_error", "original_corrupt")); self.assertTrue(ex2["xlsx"][XLSX]["format"]["resource_limit"])


class RecalculationPathTests(unittest.TestCase):
    """B5 with a fake converter: the recalculation never returns an earlier result."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="recalc_regress_")
        self.base = os.path.realpath(self.tmp.name)
        build_fixture(os.path.join(self.base, "positive"), "positive")
        self.valid = os.path.join(self.base, "positive", "final", XLSX)
        self.damaged = os.path.join(self.base, "damaged.xlsx")
        with open(self.damaged, "wb") as f:
            f.write(b"synthetic invalid workbook")

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def scratch_of(cmd):
        return next(a for a in cmd if a.endswith(":/work")).split(":/work")[0]

    def test_valid_then_damaged_input_through_the_same_path(self):
        calls = []

        def converter(cmd, **kw):
            calls.append(cmd)
            scratch = self.scratch_of(cmd)
            if len(calls) == 1:
                shutil.copyfile(self.valid, os.path.join(scratch, "out", "in.xlsx"))
                return SimpleNamespace(returncode=0, stdout="SOFFICE_RC=0\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="Error: source file could not be loaded\nSOFFICE_RC=0\n", stderr="")  # LibreOffice exits 0 and writes nothing
        work = os.path.join(self.base, "work")
        rc1 = X.recalculate_xlsx(self.valid, work, runner=converter)
        rc2 = X.recalculate_xlsx(self.damaged, work, runner=converter)
        self.assertEqual(rc1["status"], "ok"); self.assertTrue(rc1["values"]); self.assertEqual(rc1["output_sha256"], sha(self.valid))
        self.assertEqual(rc2["status"], "failed"); self.assertNotIn("values", rc2); self.assertNotIn("recalculated_copy", rc2)
        self.assertNotEqual(rc1["scratch"], rc2["scratch"]); self.assertNotEqual(rc1["input_sha256"], rc2["input_sha256"])
        self.assertEqual(rc2["produced"], []); self.assertIn("no new workbook", rc2["reason"])
        self.assertTrue(os.path.exists(os.path.join(rc1["scratch"], "out", "in.xlsx")))  # the earlier output exists but is never reused

    def test_pre_existing_output_in_the_work_directory_is_not_accepted(self):
        work = os.path.join(self.base, "stale")
        os.makedirs(os.path.join(work, "recalc", "out"))
        shutil.copyfile(self.valid, os.path.join(work, "recalc", "out", "in.xlsx"))  # the review's stale-result probe
        rc = X.recalculate_xlsx(self.damaged, work, runner=lambda *a, **kw: SimpleNamespace(returncode=0, stdout="Error: source could not be loaded\nexisting in.xlsx", stderr=""))
        self.assertEqual(rc["status"], "failed"); self.assertNotIn("values", rc); self.assertIsNone(rc["soffice_rc"])

    def test_nonzero_soffice_status_and_unreadable_output_fail(self):
        work = os.path.join(self.base, "work2")
        rc = X.recalculate_xlsx(self.valid, work, runner=lambda *a, **kw: SimpleNamespace(returncode=1, stdout="SOFFICE_RC=77\n", stderr="x"))
        self.assertEqual((rc["status"], rc["soffice_rc"]), ("failed", 77))

        def garbage(cmd, **kw):
            with open(os.path.join(self.scratch_of(cmd), "out", "in.xlsx"), "wb") as f:
                f.write(b"not a workbook")
            return SimpleNamespace(returncode=0, stdout="SOFFICE_RC=0\n", stderr="")
        rc2 = X.recalculate_xlsx(self.valid, work, runner=garbage)
        self.assertEqual(rc2["status"], "failed"); self.assertIn("unreadable", rc2["reason"]); self.assertNotIn("values", rc2)


if __name__ == "__main__":
    unittest.main()
