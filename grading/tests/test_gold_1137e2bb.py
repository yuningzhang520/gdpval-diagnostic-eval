"""Gold-first verification of the 1137e2bb grader (section 3 of the evaluation architecture):

* anchor: the expert deliverables grade to the declared gold baseline (every deterministic item passes except
  21, the indicator the expert never built; A-21), through extraction without recalculation and - under
  GOLD_RECALC_DOCKER=1 - through the real LibreOffice path in the pinned image;
* the values-only twin grades to exactly the same item map and critical status;
* every catalog variant (grading/gold_variants_1137e2bb.py) grades to its DECLARED full item map: a seeded
  corruption must move exactly the items its basis names (dependencies between items included), a neutral
  transformation must leave the gold map unchanged;
* the critical status the grader reports equals the status implied by the expected map.

The observed transition table is written to $GRADING_REGRESSION_LOG_DIR/gold_transitions_1137e2bb.json.
Run: harness/tests/run_isolated.sh <root> unittest grading.tests.test_gold_1137e2bb"""
import json
import os
import shutil
import tempfile
import unittest

import openpyxl

from grading import checks_1137e2bb as CK, extract as X
from grading import gold_variants_1137e2bb as GV

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{GV.TASK}.json"), encoding="utf-8"))
TABLE: dict = {}


def grade(final: str, work: str, *, recalc: bool = False) -> dict:
    ex = X.extract_all(final, work, recalc=recalc)
    res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "ex": ex, "map": {i: r["verdict"] for i, r in res["items"].items()}, "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def implied_critical(vmap: dict) -> dict:
    out = {}
    for cid, spec in CK.CRITICAL.items():
        vs = [vmap.get(i, "pending") for i in spec["items"]]
        judge_pending = bool(spec.get("judge_items")) or any(i in CK.J_ITEMS for i in spec["items"])
        out[cid] = "fail" if "fail" in vs else ("pass" if all(v == "pass" for v in vs) and not judge_pending else "not_confirmed")
    return out


class GoldAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_1137_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.gold_final = os.path.join(cls.base, "gold", "final")
        shutil.copytree(GV.GOLD_DIR, cls.gold_final)
        cls.twin_final = GV.build_twin(os.path.join(cls.base, "twin"))
        cls.gold = grade(cls.gold_final, os.path.join(cls.base, "work_gold"))
        cls.twin = grade(cls.twin_final, os.path.join(cls.base, "work_twin"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "twin_equal": cls.twin["map"] == cls.gold["map"], "gold_sha256": GV.gold_sha256()}
        cls.tmp.cleanup()

    def test_gold_original_grades_to_the_declared_baseline(self):
        self.assertEqual(set(self.gold["map"]), set(CK.D_ITEMS))
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "pass", "C2": "pass", "C3": "not_confirmed"})
        self.assertEqual(self.gold["res"]["items"][21]["attribution"], "model_caused")  # the expert deliverable lacks the indicator: graded as written (A-21)
        self.assertEqual(self.gold["res"]["detail_sheet"]["sheet"], GV.DETAIL)
        self.assertEqual(self.gold["res"]["detail_sheet"]["column_mapping"]["total"], GV.TOTAL - 1)  # 'Number of Errors' is the total column (fix of 2026-11-01)
        l2 = self.gold["ex"]["xlsx"][GV.XLSX]["sheets"][GV.DETAIL]["cells"]["L2"]
        self.assertEqual((l2["cached"], l2["formula"] is not None), ("", True))  # empty-string formula result kept as a value (fix of 2026-11-01)

    def test_values_only_twin_grades_exactly_like_the_gold(self):
        self.assertEqual(self.twin["map"], self.gold["map"])
        self.assertEqual(self.twin["critical"], self.gold["critical"])
        self.assertEqual(self.twin["res"]["items"][14]["verdict"], "pass")  # the pivot (drill-down) survived the values-only save
        wb = openpyxl.load_workbook(os.path.join(self.twin_final, GV.XLSX))
        self.assertEqual(sum(1 for ws in wb.worksheets for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")), 0)


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_1137_variants_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.twin_final = GV.build_twin(os.path.join(cls.base, "twin"))
        cls.variants_dir = os.path.join(cls.base, "variants")

    @classmethod
    def tearDownClass(cls):
        out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
        if out:
            os.makedirs(out, exist_ok=True)
            from grading.grade import ENGINE_VERSION, code_provenance
            with open(os.path.join(out, "gold_transitions_1137e2bb.json"), "w", encoding="utf-8") as f:
                json.dump({"_provenance": {**code_provenance(), "task_grader_version": CK.VERSION, "engine_version": ENGINE_VERSION}, **TABLE}, f, indent=1, default=str)
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        final = GV.build_variant(name, self.twin_final, self.variants_dir)
        g = grade(final, os.path.join(self.base, "work", name))
        expected = GV.expected_map(name)
        diff = {i: {"expected": expected[i], "actual": g["map"].get(i), "note": (g["res"]["items"][i]["note"] or "")[:200] if i in g["res"]["items"] else None} for i in expected if g["map"].get(i) != expected[i]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed_fail": sorted(i for i, v in g["map"].items() if v == "fail"),
                       "observed_cannot_assess": sorted(i for i, v in g["map"].items() if v == "cannot_assess"), "critical": g["critical"], "diff": diff}
        self.assertEqual(set(g["map"]), set(CK.D_ITEMS))
        self.assertEqual(diff, {}, f"{name} ({spec['kind']}): " + json.dumps(diff, indent=1, default=str))
        for i, a in spec.get("attribution", {}).items():
            self.assertEqual(g["res"]["items"][i].get("attribution"), a, f"{name}: item {i} attribution")
        self.assertEqual(g["critical"], implied_critical(expected), f"{name}: critical status must follow the expected item map")


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


@unittest.skipUnless(os.environ.get("GOLD_RECALC_DOCKER") == "1", "set GOLD_RECALC_DOCKER=1 to run the LibreOffice path in the pinned image")
class GoldRecalcDockerTests(unittest.TestCase):
    """The expert workbook (164 formulas, 21 empty-string results) through the real recalculation, and one
    formula-preserving corruption: the price-flag formula of PO1002/SKU-0103/120 replaced by =1/0 so that the
    recalculated cell is an error value. Expected: every item whose fail_if_invalid lists price_flag (5, 8, 9, 15,
    18), 10 (error value), the line's own item 32, and - because the line's total and text formulas consume the
    error - 17 and 20 (the total column is either short by one or invalid on that line)."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_1137_recalc_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
        if out:
            os.makedirs(out, exist_ok=True)
            from grading.grade import ENGINE_VERSION, code_provenance
            with open(os.path.join(out, "gold_transitions_1137e2bb_recalc.json"), "w", encoding="utf-8") as f:
                json.dump({"_provenance": {**code_provenance(), "task_grader_version": CK.VERSION, "engine_version": ENGINE_VERSION}, **{k: v for k, v in TABLE.items() if k in ("gold_recalc_path", "formula_error_recalc")}}, f, indent=1, default=str)
        cls.tmp.cleanup()

    def test_gold_original_through_recalculation_matches_the_baseline(self):
        final = os.path.join(self.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        g = grade(final, os.path.join(self.base, "work_gold"), recalc=True)
        cmp_ = g["ex"]["xlsx"][GV.XLSX]["recalc_comparison"]
        self.assertEqual((cmp_["formula_cells"], cmp_["equal"], cmp_["differs"], cmp_["cached_missing"], cmp_["recalculation_failed"]), (164, 164, 0, 0, 0))
        self.assertEqual(g["map"], GV.GOLD_BASELINE); self.assertEqual(g["critical"], {"C1": "pass", "C2": "pass", "C3": "not_confirmed"})
        TABLE["gold_recalc_path"] = {"map": g["map"], "recalc_comparison": cmp_}

    def test_formula_producing_an_error_value_after_recalculation(self):
        final = os.path.join(self.base, "formula_error", "final"); shutil.copytree(GV.GOLD_DIR, final)
        p = os.path.join(final, GV.XLSX); wb = openpyxl.load_workbook(p); ws = wb[GV.DETAIL]
        ws.cell(GV.find_row(ws, "PO1002", "SKU-0103", 120), GV.PFLAG).value = "=1/0"
        wb.save(p)  # openpyxl drops every cached value: the whole workbook now depends on the recalculation
        g = grade(final, os.path.join(self.base, "work_formula_error"), recalc=True)
        expected = {**GV.GOLD_BASELINE, **GV.F(5, 8, 9, 10, 15, 17, 18, 20, 32)}
        diff = {i: (expected[i], g["map"].get(i), (g["res"]["items"][i]["note"] or "")[:160]) for i in expected if g["map"].get(i) != expected[i]}
        TABLE["formula_error_recalc"] = {"observed_fail": sorted(i for i, v in g["map"].items() if v == "fail"), "diff": diff}
        self.assertEqual(diff, {}, json.dumps(diff, indent=1, default=str))
        self.assertEqual(g["res"]["items"][10]["attribution"], "model_caused")


class V1LayoutTests(unittest.TestCase):
    """Grader .3 (Dev calibration 2026-11-01)."""

    DETAIL = ["PO Number", "SKU", "Ordered Units", "Entered Unit Price", "Expected Unit Price", "UOM", "Case Pack", "Ship-to Location", "Price Mismatch Error",
              "Case Pack Error", "Total Errors", "Error Type", "Unit Price Variance ($)", "Total Dollar Variance ($)"]

    def test_variance_headers_are_recognised(self):
        m = CK.map_columns(self.DETAIL)
        self.assertEqual(m["field_status"]["case_missing"], "confirmed_missing")  # A-21 can be applied
        self.assertEqual(m["field_status"]["price_flag"], "ok")
        self.assertNotIn("variance_info", CK.map_columns(self.DETAIL[:12] + ["Price Variance Flag"])["cols"])  # a flag column is never claimed as a variance column

    def test_summary_measures_and_workbook_pivot(self):
        d = tempfile.mkdtemp(prefix="v1_1137_"); self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Summary"
        ws.append(["SKU", "UOM", "Case Pack", "Order Lines", "Price Mismatch Errors", "Case Pack Errors", "Total Errors", "Entered Price"])
        ws.append(["SKU-0107", "CASE", 6, 4, 4, 2, 6, 8.59]); ws.append(["SKU-0108", "CASE", 12, 3, 3, 1, 4, 9.1]); ws.append(["Total", None, None, 7, 7, 3, 10, None])
        wb.create_sheet("Pivot")
        p = os.path.join(d, "w.xlsx"); wb.save(p)
        x = X.extract_xlsx(p)
        x["sheets"]["Pivot"]["pivots"] = [{"name": "PT1", "cache_fields": ["SKU", "PO Number", "Price Mismatch Error"], "row_fields": ["SKU", "PO Number"]}]
        summ = CK.locate_summary_sheet(x, set())
        self.assertEqual((summ["cols"]["case"], summ["cols"]["price"]), (5, 4))  # 'Case Pack Errors', not the pack size; 'Price Mismatch Errors', not the price
        self.assertEqual([p_["sheet"] for p_ in summ["workbook_pivots"]], ["Pivot"])


if __name__ == "__main__":
    unittest.main()
