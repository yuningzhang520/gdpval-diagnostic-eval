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


if __name__ == "__main__":
    unittest.main()
