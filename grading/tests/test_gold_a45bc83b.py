"""Gold-first suite for a45bc83b (GCP migration design): the expert deliverables grade to the declared baseline (items
1, 2, 3, 5 pass), every declared variant to its declared map, the extractor's list and PDF detection on their own
(including the regression of an empty typed-bullet glyph that matched every paragraph), critical status with visual-only
criteria, and the production entry grade_run on a run directory built through the real collector (judge disabled): 4
deterministic, 60 judge and 8 visual rows (item 70 is visual; its judge unit is agreement-only). No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_a45bc83b.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest

from docx import Document

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_a45bc83b as CK, extract as X, judge as J
from grading import gold_variants_a45bc83b as GV
from grading.grade import ENGINE_VERSION, _score, code_provenance, grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
PROMPT = open(os.path.join(ROOT, "data", "prompts", f"{GV.TASK}.txt"), encoding="utf-8").read()
TABLE: dict = {}


def grade(final: str, work: str) -> dict:
    ex = X.extract_all(final, work, recalc=False)
    res = CK.run_checks(ex, {}, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "ex": ex, "map": {i: r["verdict"] for i, r in res["items"].items()}, "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def _dump(name):
    out = os.environ.get("GRADING_REGRESSION_LOG_DIR")
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump({"_provenance": {**code_provenance(), "task_grader_version": CK.VERSION, "engine_version": ENGINE_VERSION}, **TABLE}, f, indent=1, default=str)


class GoldAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_a45b_")
        cls.base = os.path.realpath(cls.tmp.name)
        final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, final)
        cls.gold = grade(final, os.path.join(cls.base, "work"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_a45bc83b.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE)
        self.assertEqual(self.gold["critical"], {"C1": "pass", "C2": "not_confirmed", "C3": "not_confirmed"})
        docs = self.gold["res"]["documents"]
        self.assertEqual((docs["summary"], docs["poc"]), (GV.SUMMARY, GV.POC))
        self.assertEqual(self.gold["res"]["items"][3]["evidence"]["steps"]["numbered"], 85)
        self.assertEqual(self.gold["res"]["items"][5]["evidence"]["bullets"], {"paragraphs": 15, "bullets": 15, "share": 1.0, "ok": True})

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["verdicts"], {"1": "pass", "2": "pass", "3": "pass", "5": "pass"})


class ExtractionTests(unittest.TestCase):
    """List and PDF detection of grading/extract.py on constructed documents."""
    def test_list_detection_bullets_numbers_glyphs_and_plain(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.docx"); doc = Document()
            doc.add_paragraph("plain paragraph")
            doc.add_paragraph("styled bullet", style="List Bullet")
            doc.add_paragraph("styled number", style="List Number")
            doc.add_paragraph("• typed bullet")
            doc.add_paragraph(" symbol-font bullet")
            doc.add_paragraph("- dash bullet")
            doc.add_paragraph("A user requests content")  # regression: an empty glyph matched every paragraph
            doc.save(p)
            got = [(x["text"], x["list"]["bullet"], x["list"]["numbered"]) for x in X.extract_docx(p)["paragraphs"]]
        self.assertEqual(got, [("plain paragraph", False, False), ("styled bullet", True, False), ("styled number", False, True), ("• typed bullet", True, False),
                               (" symbol-font bullet", True, False), ("- dash bullet", True, False), ("A user requests content", False, False)])
        self.assertTrue(all(g for g in X.BULLET_GLYPHS))

    def test_word_numbering_formats_on_the_expert_files(self):
        s = X.extract_docx(os.path.join(GV.GOLD_DIR, GV.SUMMARY))["paragraphs"]
        self.assertTrue(all(p["list"]["num_format"] == "bullet" for p in s if p["text"].strip()))
        poc = [p for p in X.extract_docx(os.path.join(GV.GOLD_DIR, GV.POC))["paragraphs"] if p["text"].strip()]
        self.assertEqual((sum(p["list"]["numbered"] for p in poc), sum(p["list"]["bullet"] for p in poc)), (85, 6))

    def test_pdf_extraction_and_inventory_kind(self):
        x = X.extract_pdf(os.path.join(GV.GOLD_DIR, GV.PDF))
        self.assertEqual(x["page_count"], 1); self.assertGreater(x["pages"][0]["drawings"], 0); self.assertIn("Cloud", x["text"])
        with tempfile.TemporaryDirectory() as d:
            shutil.copy(os.path.join(GV.GOLD_DIR, GV.PDF), d)
            self.assertEqual([i["kind"] for i in X.inventory(d)], ["pdf"])


class CriticalScoreTests(unittest.TestCase):
    def test_visual_only_criterion_is_not_confirmed_until_reviewed(self):
        grades = [{"item": 4, "weight": 2, "verdict": "pending_human"}, {"item": 26, "weight": 1, "verdict": "pending_human"}, {"item": 1, "weight": 2, "verdict": "pass"}]
        s = _score(grades, {"C1": {"items": [1], "name": "a"}, "C3": {"items": [], "visual_items": [4, 26], "name": "b"}, "C9": {"items": [], "name": "empty"}})
        self.assertEqual({k: v["status"] for k, v in s["critical"].items()}, {"C1": "pass", "C3": "not_confirmed", "C9": "not_confirmed"})
        self.assertEqual(s["critical"]["C3"]["items"], [4, 26])


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_a45b_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_a45bc83b.json")
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        g = grade(GV.build_variant(name, os.path.join(self.base, "variants")), os.path.join(self.base, "work", name))
        expected = GV.expected_map(name)
        diff = {i: {"expected": expected[i], "actual": g["map"].get(i), "note": g["res"]["items"][i]["note"][:220]} for i in expected if g["map"].get(i) != expected[i]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed": g["map"], "critical": g["critical"], "diff": diff}
        if spec["kind"] == "neutral":
            self.assertNotIn("expected", spec)
        self.assertEqual(diff, {}, f"{name}: " + json.dumps(diff, indent=1, default=str))
        c1 = "fail" if "fail" in expected.values() else "pass" if all(v == "pass" for v in expected.values()) else "not_confirmed"
        self.assertEqual(g["critical"]["C1"], c1)


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_a45b_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "proda45b0000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProdA45b"}
            host = os.path.join(base, "runs", b["uuid"])
            C.bind_run(host, b, "dev", "solver")
            lst, contents = fixture_listing(GV.GOLD_DIR)
            rec = asyncio.run(C.collect_final_outputs(host, "scorer", b, sb=FakeSandbox(lst, contents)))
            C.write_run_outcome(host, b, rec, EXEC_OK)
            out = os.path.join(host, "grading")
            r = grade_run(host, fake_log(b), b["uuid"], task_id=GV.TASK, rubric=RUBRIC, task_prompt=PROMPT, reference={}, out_dir=out, judge=None, recalc=False)
            self.assertEqual((r["gate"], r["graded"], r["pass_kind"]), ("passed", True, "deterministic_only"))
            self.assertEqual(r["grader_version"], f"{ENGINE_VERSION}+{CK.VERSION}")
            rows = [json.loads(l) for l in open(os.path.join(out, "grades.jsonl"), encoding="utf-8")]
            self.assertEqual(sorted(g["item"] for g in rows), list(range(1, len(RUBRIC) + 1)))
            by_src = {s_: [g for g in rows if g["source"] == s_] for s_ in ("D", "J", "V")}
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (4, 60, 8))
            self.assertEqual(sorted(g["item"] for g in by_src["V"]), [4, 26, 27, 28, 29, 30, 70, 72]); self.assertNotIn(70, [g["item"] for g in by_src["J"]])
            self.assertEqual([g["item"] for g in rows].count(70), 1)  # item 70 is scored once (human visual review)
            self.assertEqual(r["judge_agreement_only"], [{"item": 70, "verdict": "pending_judge", "judge_id": None}])
            self.assertTrue(all(g["weight"] == RUBRIC[g["item"] - 1]["score"] for g in rows))
            s_ = r["score"]
            self.assertEqual({k: v["status"] for k, v in s_["critical"].items()}, {"C1": "pass", "C2": "not_confirmed", "C3": "not_confirmed"})
            ex = X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False)
            checks = CK.run_checks(ex, {}, RUBRIC)
            units = J.build_units_a45bc83b(PROMPT, RUBRIC, ex, {}, checks, b["uuid"])
            self.assertEqual(len(units), 61)
            self.assertEqual([x["item"] for x in units if x["agreement_only"]], [70])  # judged for agreement only
            u = {x["item"]: x for x in units}
            self.assertIn(f"[{GV.SUMMARY} p0]", u[51]["deliverable_excerpt"]); self.assertNotIn(GV.POC, u[51]["deliverable_excerpt"])  # summary-only item
            self.assertIn(f"[{GV.POC} p", u[41]["deliverable_excerpt"]); self.assertNotIn(f"[{GV.SUMMARY} p", u[41]["deliverable_excerpt"])  # POC-only item
            self.assertIn("text labels", u[70]["deliverable_excerpt"]); self.assertIn(f"[{GV.SUMMARY} p", u[70]["deliverable_excerpt"])  # diagram or summary
            self.assertIn("Layer 3", u[10]["source_material"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "judge_units": len(units)}


class V1LayoutTests(unittest.TestCase):
    """Engine .6 / builder .3 (Dev calibration 2026-11-01): docx tables keep their body position, and the judge excerpt
    lists each table directly after the paragraph it follows, so a POC step's purpose box and commands stay under it."""

    def test_tables_are_listed_under_the_paragraph_they_follow(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Document()
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "cover box"
            doc.add_paragraph("Step 1.1: Create the VPC")
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "PURPOSE: isolate the tiers"
            doc.add_table(rows=1, cols=1).cell(0, 0).text = "gcloud compute networks create vpc-main"
            doc.add_paragraph("Step 1.2: Create the subnets")
            path = os.path.join(tmp, "poc.docx"); doc.save(path)
            d = X.extract_docx(path)
            self.assertEqual(d["table_after_paragraph"], [None, 0, 0])
            out = J._excerpt_named_docx({"docx": {"poc.docx": d}}, "poc.docx", "POC").splitlines()[1:]
            self.assertEqual([l.split("] ")[0] + "]" for l in out], ["[poc.docx table 1 row 1]", "[poc.docx p0]", "[poc.docx table 2 row 1]", "[poc.docx table 3 row 1]", "[poc.docx p1]"])
            legacy = {k: v for k, v in d.items() if k != "table_after_paragraph"}  # out of scope: an extraction without body order keeps the earlier layout
            old = J._excerpt_named_docx({"docx": {"poc.docx": legacy}}, "poc.docx", "POC").splitlines()[1:]
            self.assertEqual([l.split("] ")[0] + "]" for l in old], ["[poc.docx p0]", "[poc.docx p1]", "[poc.docx table 1 row 1]", "[poc.docx table 2 row 1]", "[poc.docx table 3 row 1]"])


if __name__ == "__main__":
    unittest.main()
