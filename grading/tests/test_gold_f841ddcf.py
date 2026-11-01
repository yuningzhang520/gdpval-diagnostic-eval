"""Gold-first suite for f841ddcf (June shipment recap): the expert workbook grades to its declared baseline, every
declared variant to its declared map (PO-level tables built from the input log), the extractor reads drawing text
boxes and Excel Table objects, and the production entry grade_run on a run directory built through the real collector
(judge disabled): 51 deterministic, 7 judge and 1 visual rows. No model, judge, provider or Docker call. Observed
transitions go to $GRADING_REGRESSION_LOG_DIR/gold_transitions_f841ddcf.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_f841ddcf as CK, extract as X, judge as J
from grading import gold_variants_f841ddcf as GV
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_f841_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_f841ddcf.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "pass", "C2": "fail", "C3": "not_confirmed", "C4": "pass", "C5": "fail"})
        kinds = [(t["sheet"], t["level"], t["kind"]) for t in self.gold["res"]["extraction_status"]["tables"]]
        self.assertIn(("Summary Table", "account", "june"), kinds); self.assertIn(("Summary Table", "account", "slipped"), kinds)
        self.assertIn(("PO Log", "po", "other"), kinds)  # the copied log spans June and July: no recap table

    def test_narrative_text_box_is_read_and_graded_by_metric(self):
        texts = CK.narrative_texts(self.gold["ex"]["xlsx"][GV.XLSX])
        self.assertTrue(any("Shipped a total of $145,219" in t for t in texts))
        self.assertIn("figure_missing", self.gold["res"]["items"][37]["note"])  # $145,219 and $13,248 are other metrics (K2)
        self.assertIn("145219", self.gold["res"]["items"][55]["note"])

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["declared_before_run"]["fail"], [5, 6, 8, 9, 10, 12, 17, 18, 19, 20, 32, 37, 55])
        self.assertEqual({k: v for k, v in rec["verdicts"].items() if v != "pass"}, {str(i): v for i, v in GV.GOLD_BASELINE.items() if v != "pass"})


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_f841_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_f841ddcf.json")
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
        if name == "R01_po_tables":
            objs = {t["sheet"]: t["table_objects"] for t in g["res"]["extraction_status"]["tables"] if t["level"] == "po" and t["kind"] in ("june", "slipped")}
            self.assertEqual({k: [o["autofilter"] for o in v] for k, v in objs.items()}, {"June Shipments": [True], "Slipped to July": [True]})


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_f841_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prodf8410000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProdF841"}
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
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (51, 7, 1))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            units = J.build_units_f841ddcf(PROMPT, RUBRIC, X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False), REFERENCE, {"task": GV.TASK}, b["uuid"])
            self.assertEqual([u["item"] for u in units], [38, 42, 43, 44, 45, 46, 58])
            self.assertIn("JUNE PURCHASE ORDER SUMMARY", units[0]["deliverable_excerpt"]); self.assertIn("text box", units[0]["deliverable_excerpt"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "critical": {k: v["status"] for k, v in r["score"]["critical"].items()}}


class V1LayoutTests(unittest.TestCase):
    """Grader .2 (Dev calibration 2026-11-01): obvious header forms, the June-window cohort among several July PO
    tables, and the completion sentence of item 56."""

    def test_obvious_header_forms_map_to_one_field_and_retail_never_does(self):
        for header, field in (("Ship Start Date", "start"), ("% of Order Shipped", "pct"), ("Short-Shipped ($ Cost)", "short"), ("Total Order Value ($ Cost)", "order_value"),
                              ("Total Shipped Value ($ Cost)", "shipped_value"), ("Ship Start", "start"), ("Ship Date", "actual_ship"), ("Percent of Order Shipped", "pct")):
            self.assertEqual(CK.field_of(header), field, header)
        for header in ("Order Value $ Retail", "Short-Shipped ($ Retail)", "Total", "Status", "Notes"):  # out of scope: another measure, or no field
            self.assertIsNone(CK.field_of(header), header)

    def _sheet(self, rows):
        return {"cells": {}, "rows": rows}

    def test_several_july_po_tables_prefer_the_june_window_cohort(self):
        sheet = {"cells": {"D2": {"literal": "07/15/2025"}, "D3": {"literal": "06/30/2025"}}, "rows": []}
        late = {"kind": "slipped", "level": "po", "sheet": "S", "fields": {"cancel": 3}, "data_rows": [2]}
        window = {"kind": "slipped", "level": "po", "sheet": "S", "fields": {"cancel": 3}, "data_rows": [3]}
        self.assertIs(CK.pick([late, window], "slipped", {"S": sheet}), window)
        self.assertIs(CK.pick([late, window], "slipped"), late)  # without the sheets the earlier behaviour is kept
        no_cancel = {**window, "fields": {}}
        self.assertIs(CK.pick([late, no_cancel], "slipped", {"S": sheet}), late)  # out of scope: no unique June-window table, no preference


if __name__ == "__main__":
    unittest.main()
