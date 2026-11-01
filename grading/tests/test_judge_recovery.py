"""Per-item judge infrastructure recovery (engine .7) on a synthetic interrupted pass, plus the engine .7 verdict labels,
visual-review flags and the append-only evidence correction. No provider call."""
import csv
import hashlib
import json
import os
import tempfile
import unittest

from grading import grade as G, judge as J, judge_recovery as JR, review as RV

TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
RUN = "RUNRECOVERY0000000000"
BASE = "pass-20261101T000000000000Z-aaaa"
BASE_UNIT = f"{RUN}:judge:20261101T000000000000Z-aaaa"


def unit(item):
    return {"unit_id": J.unit_id(TASK, item), "run_uuid": RUN, "task_id": TASK, "item": item, "weight": 1, "criterion": f"criterion {item}", "task_requirement": "req",
            "source_material": "src", "deliverable_excerpt": f"excerpt {item}", "excerpt_kind": "docs", "assembled_at": "2026-11-01T00:00:00+00:00"}


def req_sha(u):
    return hashlib.sha256((J.JUDGE_SYSTEM_PROMPT + "\n" + J.render_unit(u)).encode("utf-8")).hexdigest()


class FakeJudge:
    """Answers pass for every item except those listed in ``fail_items`` (provider failure, usage uncertain)."""
    judge_id = "fake@test"

    def __init__(self, fail_items=()):
        self.calls, self.fail_items, self.judge_unit = [], set(fail_items), f"{RUN}:judge:recovery"

    def __call__(self, u):
        rec = {"unit_id": u["unit_id"], "item": u["item"], "request_sha256": req_sha(u)}
        if u["item"] in self.fail_items:
            rec.update({"status": "provider_error", "error": {"class": "RetryError"}, "raw_response": None, "usage": None, "usage_status": "uncertain"})
        else:
            rec.update({"status": "ok", "error": None, "usage": {"input_tokens": 100, "output_tokens": 10, "cache_read_tokens": 0, "cache_write_tokens": 0}, "usage_status": "ok",
                        "raw_response": json.dumps({"verdict": "pass", "evidence": [{"file": "f", "location": "l", "quote": "q"}], "rationale": "r"})})
        self.calls.append(rec)
        return rec


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.out = self.tmp.name
        units = {i: unit(i) for i in (6, 69, 71)}
        rows = [{"run_uuid": RUN, "task_id": TASK, "item": 1, "weight": 1, "criterion": "c1", "source": "D", "verdict": "pass", "evidence": {}, "grader_version": "v1", "grading_pass": BASE},
                {"run_uuid": RUN, "task_id": TASK, "item": 6, "weight": 2, "criterion": "c6", "source": "J", "verdict": "fail", "evidence": [], "error_class": None, "call_status": "ok", "grader_version": "v1", "grading_pass": BASE},
                {"run_uuid": RUN, "task_id": TASK, "item": 69, "weight": 1, "criterion": "c69", "source": "J", "verdict": "cannot_assess", "evidence": [], "error_class": "provider_error", "call_status": "provider_error", "grader_version": "v1", "grading_pass": BASE},
                {"run_uuid": RUN, "task_id": TASK, "item": 71, "weight": 1, "criterion": "c71", "source": "J", "verdict": "cannot_assess", "evidence": [], "error_class": "not_attempted", "call_status": "not_attempted", "grader_version": "v1", "grading_pass": BASE}]
        with open(os.path.join(self.out, "grades.jsonl"), "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in rows))
        base = {"run": {"uuid": RUN}, "task_id": TASK, "grading_pass": BASE, "graded": True, "judge_mode": "real", "judge_unit": BASE_UNIT, "judge_verdicts": 3, "grader_version": "v1",
                "engine_version": "engine-2026-11-01.6", "score": {"critical": {}}, "review_materials": {"items": "x"}}
        with open(os.path.join(self.out, "results.jsonl"), "w") as f:
            f.write(json.dumps(base) + "\n")
        calls = [{"item": 6, "status": "ok", "request_sha256": req_sha(units[6])}, {"item": 69, "status": "provider_error", "request_sha256": req_sha(units[69])},
                 {"item": 71, "status": "not_attempted", "request_sha256": req_sha(units[71])}]
        json.dump({"unit_id": BASE_UNIT, "calls": calls}, open(os.path.join(self.out, f"judge_calls_{RUN}_x.json"), "w"))
        json.dump({"run_uuid": RUN, "grading_pass": BASE, "units": list(units.values())}, open(os.path.join(self.out, f"judge_units_{RUN}_{BASE}.json"), "w"))
        self.base_rows = open(os.path.join(self.out, "grades.jsonl")).read()

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_infrastructure_failures_are_eligible_and_a_completed_call_never_is(self):
        d = JR.recovery_plan(self.out, RUN, BASE, [6, 69, 71, 1])["decision"]
        self.assertEqual((d[69]["eligible"], d[71]["eligible"], d[6]["eligible"], d[1]["eligible"]), (True, True, False, False))
        self.assertIn("never re-judged", d[6]["reason"])
        with self.assertRaises(JR.RecoveryError):
            JR.recovery_pass(self.out, RUN, TASK, BASE, [6], FakeJudge())  # no verdict shopping on a completed call

    def test_recovery_pass_copies_the_base_rows_and_records_each_attempt(self):
        rec = JR.recovery_pass(self.out, RUN, TASK, BASE, [69, 71], FakeJudge())
        self.assertEqual((rec["pass_kind"], rec["base_pass"], rec["judge_completeness"], rec["judge_call_summary"]["recovered_items"]), ("judge_item_recovery", BASE, "complete", [69, 71]))
        self.assertTrue(open(os.path.join(self.out, "grades.jsonl")).read().startswith(self.base_rows))  # the base rows are untouched (append-only)
        new = {r["item"]: r for r in map(json.loads, open(os.path.join(self.out, "grades.jsonl"))) if r["grading_pass"] == rec["grading_pass"]}
        self.assertEqual((new[1]["verdict"], new[6]["verdict"], new[69]["verdict"], new[71]["verdict"]), ("pass", "fail", "pass", "pass"))
        self.assertEqual((new[69]["recovery"]["base_call_status"], new[71]["recovery"]["rule"]), ("provider_error", "first evaluation (never attempted)"))
        record = json.load(open(rec["recovery"]["record"]))
        self.assertEqual([a["item"] for a in record["attempts"]], [71, 69])  # the never-attempted item first
        self.assertTrue(all(a["same_request_as_base"] for a in record["attempts"]))
        sel = G.select_pass(G.grading_passes(self.out, RUN), attempts=[{"unit_id": BASE_UNIT, "state": "settled", "at": "a", "has_pass": True},
                                                                       {"unit_id": f"{RUN}:judge:recovery", "state": "settled", "at": "b", "has_pass": True}])
        self.assertEqual(sel["pass"]["grading_pass"], rec["grading_pass"])
        d = JR.recovery_plan(self.out, RUN, BASE, [69, 71])["decision"]
        self.assertFalse(d[69]["eligible"] or d[71]["eligible"])  # bounded: one recovery attempt per item, ever

    def test_a_failed_recovery_stays_provider_error_or_not_run(self):
        rec = JR.recovery_pass(self.out, RUN, TASK, BASE, [69, 71], FakeJudge(fail_items={71}))
        new = {r["item"]: r for r in map(json.loads, open(os.path.join(self.out, "grades.jsonl"))) if r["grading_pass"] == rec["grading_pass"]}
        self.assertEqual((new[71]["verdict"], new[69]["verdict"], rec["judge_completeness"]), ("provider_error", "pass", "partial"))
        self.assertEqual(rec["score"]["judge_infrastructure"], {"provider_error": [71], "not_run": []})

    def test_changed_evidence_is_refused_before_any_call(self):
        units = json.load(open(os.path.join(self.out, f"judge_units_{RUN}_{BASE}.json")))
        units["units"][1]["deliverable_excerpt"] = "edited"
        json.dump(units, open(os.path.join(self.out, f"judge_units_{RUN}_{BASE}.json"), "w"))
        j = FakeJudge()
        with self.assertRaises(JR.RecoveryError):
            JR.recovery_pass(self.out, RUN, TASK, BASE, [69, 71], j)
        self.assertEqual(j.calls, [])


class EngineSevenTests(unittest.TestCase):
    def test_infrastructure_verdicts_and_visual_review_flags(self):
        self.assertEqual([G.judge_row_verdict(v) for v in ({"verdict": "cannot_assess", "error_class": "provider_error"}, {"verdict": "cannot_assess", "error_class": "not_attempted"},
                                                            {"verdict": "cannot_assess", "error_class": "judge_parse_error"}, {"verdict": "cannot_assess", "error_class": None}, None)],
                         ["provider_error", "not_run", "cannot_assess", "cannot_assess", "pending_judge"])
        rows = [{"item": 4, "weight": 2, "verdict": "cannot_assess", "evidence": {"unassessable": [{"kind": "unknown", "field": "chart", "visual_review": "picture_chart"}]}},
                {"item": 5, "weight": 2, "verdict": "cannot_assess", "evidence": {"unassessable": [{"kind": "unknown", "field": "chart"}]}},  # out of scope: not an image
                {"item": 6, "weight": 1, "verdict": "pass", "evidence": {}}]
        sc = G._score(rows, {"C1": {"items": [4, 5, 6], "name": "c"}})
        self.assertEqual((sc["visual_review_required"], sc["critical"]["C1"]["visual_review_required"], sc["critical"]["C1"]["status"]), ([4], [4], "not_confirmed"))


class EvidenceCorrectionTests(unittest.TestCase):
    def write(self, path, rows):
        with open(path, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["run_uuid", "item", "weight", "criterion", "independent_judgment", "evidence", "judged_at_utc", "reviewer"])
            w.writerows(rows)

    def test_only_evidence_text_may_change_and_the_original_stays(self):
        with tempfile.TemporaryDirectory() as d:
            orig, fixed, bad = (os.path.join(d, n) for n in ("o.csv", "f.csv", "b.csv"))
            self.write(orig, [["R", 57, 1, "c57", "pass", "slide 2", "t", "h"], ["R", 59, 1, "c59", "pass", "slide 2", "t", "h"]])
            cp = RV.save_label_checkpoint(d, "R", orig, "h")
            self.write(bad, [["R", 57, 1, "c57", "pass", "slide 2", "t", "h"], ["R", 59, 1, "c59", "fail", "slide 4", "t", "h"]])
            with self.assertRaises(ValueError):
                RV.save_evidence_correction(d, "R", bad, "h", cp["checkpoint"], [59], "typo", "assistant")  # a judgment never changes
            self.write(fixed, [["R", 57, 1, "c57", "pass", "slide 2", "t", "h"], ["R", 59, 1, "c59", "pass", "slide 4", "t", "h"]])
            with self.assertRaises(ValueError):
                RV.save_evidence_correction(d, "R", fixed, "h", cp["checkpoint"], [57], "typo", "assistant")  # the changed item must be named
            new = RV.save_evidence_correction(d, "R", fixed, "h", cp["checkpoint"], [59], "typo", "assistant")
            self.assertEqual((new["correction"]["post_reveal"], new["correction"]["items"], new["correction"]["corrects_sha256"]), (True, [59], cp["sha256"]))
            self.assertEqual(json.load(open(cp["checkpoint"]))["sha256"], cp["sha256"])  # the original checkpoint is unchanged
            self.assertEqual(len(open(os.path.join(d, "labels", "checkpoints.jsonl")).readlines()), 2)


if __name__ == "__main__":
    unittest.main()
