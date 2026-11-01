"""Gold-first suite for b5d2e6f1 (weekly sales analysis): the expert workbook grades to its declared baseline and
non-rubric critical checks, every declared variant to its declared map, the scorer counts the non-rubric checks in the
critical status, and the production entry grade_run on a run directory built through the real collector (judge
disabled): 31 deterministic rows and 1 visual row. No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_b5d2e6f1.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_b5d2e6f1 as CK, extract as X
from grading import gold_variants_b5d2e6f1 as GV
from grading.grade import ENGINE_VERSION, _score, code_provenance, grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE = json.load(open(os.path.join(ROOT, "private", "checks", "recalc", f"{GV.TASK}.json"), encoding="utf-8"))
PROMPT = open(os.path.join(ROOT, "data", "prompts", f"{GV.TASK}.txt"), encoding="utf-8").read()
TABLE: dict = {}


def grade(final: str, work: str) -> dict:
    ex = X.extract_all(final, work, recalc=False)
    res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "map": {i: r["verdict"] for i, r in res["items"].items()}, "extra": {k: v["verdict"] for k, v in res["critical_extra"].items()},
            "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def implied_critical(vmap: dict, extra: dict) -> dict:
    out = {}
    for cid, spec in CK.CRITICAL.items():
        vs = [vmap[i] for i in spec["items"]] + [extra.get(k) or "pending" for k in spec.get("extra", [])]
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_b5d2_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_extra": cls.gold["extra"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_b5d2e6f1.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["extra"], GV.GOLD_EXTRA)
        self.assertEqual(self.gold["critical"], {"C1": "pass", "C2": "fail", "C3": "pass", "C4": "fail"})
        st = self.gold["res"]["extraction_status"]
        self.assertEqual((st["data"]["rows"], st["data"]["pairs"], len(st["data"]["stores"])), (936, 312, 39))
        self.assertEqual(st["store_tab"]["kinds"], {"pair": 312, "store_subtotal": 39, "store_header": 0, "grand_total": 1, "other": 0, "brand": 0})

    def test_known_gold_defects_are_named(self):
        items, extra = self.gold["res"]["items"], self.gold["res"]["critical_extra"]
        self.assertIn("aggregated as average", items[21]["note"])  # K3
        self.assertIn("vs source", extra["c2_source_totals"]["note"])  # K2: edited Data tab against the source
        self.assertIn("General", items[29]["note"])

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["verdict_counts"], {"fail": 12, "pass": 19})  # before rule A-1: 14 failed on the '(blank)' rows
        self.assertIn("14", rec["observed_unexpected"])


class CriticalExtraTests(unittest.TestCase):
    def test_scorer_counts_non_rubric_checks(self):
        grades = [{"item": 2, "weight": 2, "verdict": "pass"}, {"item": 5, "weight": 2, "verdict": "pass"}]
        spec = {"C1": {"items": [2], "extra": ["c1_columns"], "name": "a"}, "C2": {"items": [5], "extra": ["c2_source_totals"], "name": "b"}}
        s = _score(grades, spec, extra={"c1_columns": {"verdict": "pass"}, "c2_source_totals": {"verdict": "fail"}})
        self.assertEqual({k: v["status"] for k, v in s["critical"].items()}, {"C1": "pass", "C2": "fail"})
        self.assertEqual((s["W"], s["P"]), (4, 4))  # non-rubric checks never enter W, E or P
        s = _score(grades, spec)
        self.assertEqual({k: v["status"] for k, v in s["critical"].items()}, {"C1": "not_confirmed", "C2": "not_confirmed"})


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_b5d2_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_b5d2e6f1.json")
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        g = grade(GV.build_variant(name, os.path.join(self.base, "variants")), os.path.join(self.base, "work", name))
        exp, ee = GV.expected_map(name), GV.expected_extra(name)
        diff = {i: {"expected": exp[i], "actual": g["map"].get(i), "note": g["res"]["items"][i]["note"][:220]} for i in exp if g["map"].get(i) != exp[i]}
        dext = {k: {"expected": ee[k], "actual": g["extra"].get(k)} for k in ee if g["extra"].get(k) != ee[k]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed": g["map"], "extra": g["extra"], "critical": g["critical"], "diff": diff, "diff_extra": dext}
        if spec["kind"] == "neutral":
            self.assertNotIn("expected", spec)
        self.assertEqual((diff, dext), ({}, {}), f"{name}: " + json.dumps({"items": diff, "extra": dext}, indent=1, default=str))
        self.assertEqual(g["critical"], implied_critical(exp, ee))


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_b5d2_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prodb5d20000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProdB5d2"}
            host = os.path.join(base, "runs", b["uuid"])
            C.bind_run(host, b, "dev", "solver")
            lst, contents = fixture_listing(GV.GOLD_DIR)
            rec = asyncio.run(C.collect_final_outputs(host, "scorer", b, sb=FakeSandbox(lst, contents)))
            C.write_run_outcome(host, b, rec, EXEC_OK)
            out = os.path.join(host, "grading")
            r = grade_run(host, fake_log(b), b["uuid"], task_id=GV.TASK, rubric=RUBRIC, task_prompt=PROMPT, reference=REFERENCE, out_dir=out, judge=None, recalc=False)
            self.assertEqual((r["gate"], r["graded"], r["pass_kind"]), ("passed", True, "deterministic_only"))
            self.assertEqual(r["grader_version"], f"{ENGINE_VERSION}+{CK.VERSION}")
            rows = [json.loads(l) for l in open(os.path.join(out, "grades.jsonl"), encoding="utf-8")]
            by_src = {s_: [g for g in rows if g["source"] == s_] for s_ in ("D", "J", "V")}
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (31, 0, 1))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            crit = r["score"]["critical"]
            self.assertEqual({k: v["status"] for k, v in crit.items()}, {"C1": "pass", "C2": "fail", "C3": "pass", "C4": "fail"})
            self.assertEqual(crit["C2"]["extra_checks"], {"c2_source_totals": "fail"})
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "critical": {k: v["status"] for k, v in crit.items()}}


if __name__ == "__main__":
    unittest.main()
