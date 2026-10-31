"""Partial-collection attribution regressions (policy approved 2026-10-30): model-caused items
keep the attempt gradable with the rejected files treated as not delivered; any unrecovered
harness/provider-caused item is a run error; undetermined items require adjudication; mixed
cases follow those rules; a separate human adjudication resolves `unknown` items only; the
loader re-derives everything and fails closed on tampering. Fake sandbox, no Docker, no model.
Run: python -m unittest harness.tests.test_attribution_unit -v"""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from harness import collect as c
from harness.tests.test_collect_unit import RUN, FakeSandbox, entry
from harness.tests.test_collect_limits_unit import SlowSandbox, listing

EXEC = {"status": "completed", "errors": [], "limits": [], "limit_types": [], "solver_finished": True, "collector_scorer_executed": True}
A, B = "/output/final/a.txt", "/output/final/b.txt"


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="attrib_unit_")
        self.host = str(Path(os.path.realpath(self.tmp.name)) / "runs" / RUN["uuid"])
        c.bind_run(self.host, dict(RUN), None, "solver")

    def tearDown(self):
        self.tmp.cleanup()

    def collect(self, entries, contents, skipped=(), sb=None, **kw):
        lst = listing(entries); lst["skipped"] = list(skipped)
        sb = sb or FakeSandbox(lst, contents)
        return asyncio.run(c.collect_final_outputs(self.host, "scorer", dict(RUN), sb=sb, **kw))

    def outcome(self, rec, execution=EXEC):
        return c.write_run_outcome(self.host, dict(RUN), rec, execution)

    def test_model_caused_only_is_gradable_with_rejections_recorded(self):
        skipped = [{"path": "/output/final/link", "reason": "symlink", "target": "/etc/hostname"}, {"path": "/output/final/pipe", "reason": "fifo"}]
        rec = self.collect([entry(A, b"a")], {A: b"a"}, skipped=skipped)
        self.assertEqual((rec["status"], rec["attribution"]["class"], rec["harness_error"], rec["outcome_class"]),
                         ("partial", "model_caused", False, "collected_with_model_caused_rejections"))
        out = self.outcome(rec)
        self.assertEqual((out["grading_eligible"], out["harness_error"], out["requires_adjudication"], out["outcome_class"]),
                         (True, False, False, "collected_with_model_caused_rejections"))
        self.assertIn("not delivered", out["grading_basis"])
        items = out["attribution"]["items"]
        self.assertEqual([(i["path"], i["class"], i["evidence"]) for i in items],
                         [("/output/final/link", "model_caused", "collection.json skipped[0]"), ("/output/final/pipe", "model_caused", "collection.json skipped[1]")])
        loaded = c.load_run_outcome(self.host, dict(RUN))  # for_grading=True accepts
        self.assertEqual(loaded["effective"]["outcome_class"], "collected_with_model_caused_rejections")

    def test_harness_caused_deadline_is_run_error(self):
        with patch.dict(c.LIMITS, {"time_budget_s": 0.3}):
            data = {A: b"fast", B: b"slow"}
            rec = self.collect(None, None, sb=SlowSandbox(listing([entry(k, v) for k, v in data.items()]), data, slow={B: 5.0}))
        self.assertEqual(rec["attribution"]["class"], "harness_caused")
        out = self.outcome(rec)
        self.assertEqual((out["grading_eligible"], out["harness_error"], out["outcome_class"]), (False, True, "harness_collection_error"))
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, dict(RUN))
        self.assertEqual(c.load_run_outcome(self.host, dict(RUN), for_grading=False)["effective"]["outcome_class"], "harness_collection_error")

    def test_unknown_read_failure_requires_adjudication(self):
        data = {A: b"a", B: b"b"}
        rec = self.collect([entry(k, v) for k, v in data.items()], data, _simulate_read_failure={B})
        self.assertEqual((rec["attribution"]["class"], rec["attribution"]["requires_adjudication"]), ("unknown", True))
        out = self.outcome(rec)
        self.assertEqual((out["grading_eligible"], out["harness_error"], out["requires_adjudication"], out["outcome_class"]),
                         (False, False, True, "requires_adjudication"))
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, dict(RUN))

    def test_mixed_harness_and_model_is_run_error(self):
        with patch.dict(c.LIMITS, {"time_budget_s": 0.3}):
            data = {A: b"fast", B: b"slow"}
            lst = listing([entry(k, v) for k, v in data.items()]); lst["skipped"] = [{"path": "/output/final/link", "reason": "symlink", "target": "/x"}]
            rec = self.collect(None, None, sb=SlowSandbox(lst, data, slow={B: 5.0}))
        self.assertEqual(rec["attribution"]["counts"], {"model_caused": 1, "harness_caused": 1, "unknown": 0})
        out = self.outcome(rec)
        self.assertEqual(out["outcome_class"], "harness_collection_error")
        self.assertTrue(out["harness_error"])

    def test_mixed_unknown_and_model_requires_adjudication(self):
        data = {A: b"a", B: b"b"}
        rec = self.collect([entry(k, v) for k, v in data.items()], data, skipped=[{"path": "/output/final/pipe", "reason": "fifo"}], _simulate_read_failure={B})
        out = self.outcome(rec)
        self.assertEqual((out["outcome_class"], out["harness_error"]), ("requires_adjudication", False))
        self.assertEqual(out["attribution"]["counts"], {"model_caused": 1, "harness_caused": 0, "unknown": 1})

    def write_adjudication(self, items, run=None):
        adj = {"run": run or dict(RUN), "items": items, "by": "human reviewer", "at": "2026-10-30T23:00:00+00:00",
               "basis": "execution log shows the model deleted the file after writing it"}
        Path(self.host, "adjudication.json").write_text(json.dumps(adj))
        return adj

    def test_adjudication_resolves_unknown_without_touching_the_outcome(self):
        data = {A: b"a", B: b"b"}
        rec = self.collect([entry(k, v) for k, v in data.items()], data, _simulate_read_failure={B})
        out = self.outcome(rec)
        before = Path(self.host, "run_outcome.json").read_bytes()
        self.write_adjudication({B: "model_caused"})
        loaded = c.load_run_outcome(self.host, dict(RUN))  # gate accepts through the effective decision
        self.assertEqual(loaded["outcome_class"], "requires_adjudication")  # stored outcome unchanged
        self.assertEqual(loaded["effective"]["outcome_class"], "collected_with_model_caused_rejections")
        self.assertTrue(loaded["effective"]["grading_eligible"])
        self.assertTrue(loaded["effective"]["attribution"]["adjudicated"])
        self.assertEqual(Path(self.host, "run_outcome.json").read_bytes(), before)
        self.write_adjudication({B: "harness_caused"})
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, dict(RUN))
        self.assertEqual(c.load_run_outcome(self.host, dict(RUN), for_grading=False)["effective"]["outcome_class"], "harness_collection_error")
        self.assertEqual(c.load_run_outcome(self.host, dict(RUN), for_grading=False, apply_adjudication=False)["effective"]["outcome_class"], "requires_adjudication")

    def test_adjudication_cannot_rescue_harness_caused_or_other_run(self):
        with patch.dict(c.LIMITS, {"time_budget_s": 0.3}):
            data = {A: b"fast", B: b"slow"}
            rec = self.collect(None, None, sb=SlowSandbox(listing([entry(k, v) for k, v in data.items()]), data, slow={B: 5.0}))
        self.outcome(rec)
        self.write_adjudication({B: "model_caused"})
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, dict(RUN))
        self.assertEqual(c.load_run_outcome(self.host, dict(RUN), for_grading=False)["effective"]["outcome_class"], "harness_collection_error")
        self.write_adjudication({B: "model_caused"}, run={**RUN, "epoch": 2})
        with self.assertRaisesRegex(c.OutcomeValidationError, "another run|malformed"):
            c.load_run_outcome(self.host, dict(RUN), for_grading=False)

    def test_tampered_attribution_fails_closed(self):
        data = {A: b"a", B: b"b"}
        rec = self.collect([entry(k, v) for k, v in data.items()], data, _simulate_read_failure={B})
        good = self.outcome(rec)
        bad = json.loads(json.dumps(good))
        bad["attribution"]["class"] = "model_caused"; bad["attribution"]["items"][0]["class"] = "model_caused"
        bad["attribution"]["counts"] = {"model_caused": 1, "harness_caused": 0, "unknown": 0}
        bad["grading_eligible"] = True; bad["outcome_class"] = "collected_with_model_caused_rejections"; bad["requires_adjudication"] = False
        c._atomic_json(self.host, "run_outcome.json", bad)
        with self.assertRaisesRegex(c.OutcomeValidationError, "stored attribution disagrees"):
            c.load_run_outcome(self.host, dict(RUN), for_grading=False)

    def test_no_files_confirmed_unchanged(self):
        rec = self.collect([], {})
        out = self.outcome(rec)
        self.assertEqual((out["collection_status"], out["grading_eligible"], out["outcome_class"], out["attribution"]["class"]),
                         ("no_files_confirmed", True, "no_deliverable_files_confirmed", "none"))

    def test_rule_table(self):
        self.assertEqual(c.attribute_item("skipped", "symlink_directory")[0], "model_caused")
        self.assertEqual(c.attribute_item("skipped", "device")[0], "model_caused")
        self.assertEqual(c.attribute_item("rejected", "host_path_component_symlink")[0], "harness_caused")
        self.assertEqual(c.attribute_item("rejected", "path_segment_invalid")[0], "unknown")
        self.assertEqual(c.attribute_item("file", "read_deadline_exceeded")[0], "harness_caused")
        self.assertEqual(c.attribute_item("file", "conflict_existing_differs")[0], "harness_caused")
        for r in ("read_failed:RuntimeError", "integrity_mismatch", "oversized", "file_limit", "total_limit"):
            self.assertEqual(c.attribute_item("file", r)[0], "unknown", r)
        self.assertEqual(c.attribute_item("listing", "listing_exec_failed:returncode=1")[0], "harness_caused")
        self.assertEqual(c.attribute_item("listing", "walk:PermissionError")[0], "unknown")


if __name__ == "__main__":
    unittest.main()
