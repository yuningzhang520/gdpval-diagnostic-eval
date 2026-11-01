"""Gold-first suite for c357f0e2 (UAT test plan): the expert workbook grades to its declared baseline (4, 10, 67, 69;
K1), every declared variant to its declared map (counts, blanks, headers per A-2, the first visible sheet,
date formats, wrap and width, browsers, the cross-functional label), and the production entry
grade_run on a run directory built through the real collector (judge disabled): 15 deterministic, 54 judge and 1 visual
rows. No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_c357f0e2.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_c357f0e2 as CK, extract as X, judge as J
from grading import gold_variants_c357f0e2 as GV
from grading.grade import ENGINE_VERSION, code_provenance, grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE: dict = {}  # no figures to recompute for this task
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
        out[cid] = "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed"  # a judge-only criterion has no deterministic items
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_c357_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_c357f0e2.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "fail", "C2": "not_confirmed", "C3": "not_confirmed"})  # C2, C3 are judge criteria
        st = self.gold["res"]["extraction_status"]
        self.assertEqual((st["test_case_sheet"], st["counted_rows"]), ("UAT Test Plan", 75))
        self.assertIn("cross browser testing", self.gold["res"]["items"][69]["evidence"]["component_labels"])

    def test_extractor_reads_visibility_widths_and_wrap(self):
        sh = self.gold["ex"]["xlsx"][GV.XLSX]["sheets"]["UAT Test Plan"]
        self.assertEqual(sh["state"], "visible")
        self.assertEqual(round(sh["column_widths"]["E"], 2), 71.27)
        self.assertTrue(sh["cells"]["E3"].get("wrap"))
        self.assertEqual(CK.find_header(sh)["row"], 2)  # A-2: the template's headers are in row 2

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["declared_before_run"]["fail"], [4, 10, 67, 69])


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_c357_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_c357f0e2.json")
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
        if name == "R10_hidden_sheet_first":
            st = g["res"]["extraction_status"]
            self.assertEqual((st["test_case_sheet"], st["hidden_sheets_with_headers"]), ("UAT Test Plan", ["Old Plan"]))


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_c357_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prodc3570000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProdC357"}
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
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (15, 54, 1))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            ex = X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False)
            units = J.build_units_c357f0e2(PROMPT, RUBRIC, ex, REFERENCE, CK.run_checks(ex, REFERENCE, RUBRIC), b["uuid"])
            self.assertEqual([u["item"] for u in units], CK.J_ITEMS)
            self.assertIn("Test Scenario", {u["item"]: u for u in units}[49]["deliverable_excerpt"]); self.assertIn("Viewers", {u["item"]: u for u in units}[49]["source_material"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "critical": {k: v["status"] for k, v in r["score"]["critical"].items()}}


if __name__ == "__main__":
    unittest.main()
