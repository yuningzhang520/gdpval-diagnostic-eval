"""Unit tests for the execution-budget attribution policy (no Docker, no model).

Policy (harness.collect.grading_decision): an unrecovered collection fault is a harness error;
an execution error or unknown state blocks grading; exhausting a pre-configured budget
(time / working / message / token) keeps execution.status == "limited" and is grading-eligible
when the final collection is complete or no_files_confirmed; other limit types require review.
Run: python -m unittest harness.tests.test_outcome_policy_unit -v"""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest

from harness import collect as c
from harness.tests.test_collect_unit import RUN, FakeSandbox, entry


def limit(kind: str, value=10.0):
    return {"event_uuid": f"evt-{kind}", "type": kind, "limit": value, "message": f"{kind} limit exceeded"}


def execution(status: str, limits=(), errors=(), solver_finished=None):
    limits, errors = list(limits), list(errors)
    finished = (status == "completed") if solver_finished is None else solver_finished
    return {"status": status, "errors": errors, "limits": limits,
            "limit_types": sorted({l["type"] for l in limits}), "solver_finished": finished,
            "collector_scorer_executed": True, "source": "unit", "scope": "unit"}


class OutcomePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="policy_unit_")
        self.host = str(Path(self.tmp.name) / "runs" / RUN["uuid"])
        self.binding = dict(RUN)
        c.bind_run(self.host, self.binding, "unit-label", "solver")

    def tearDown(self):
        self.tmp.cleanup()

    def listing(self, entries=None):
        return {"ok": True, "root": c.FINAL_DIR, "root_state": "dir", "entries": entries or [], "skipped": [], "errors": []}

    def collect(self, entries=None, contents=None, **kw):
        return asyncio.run(c.collect_final_outputs(self.host, "unit pass", self.binding,
                                                   sb=FakeSandbox(self.listing(entries), contents), **kw))

    def complete_collection(self):
        data = b"deliverable bytes"
        return self.collect([entry("/output/final/a.txt", data)], {"/output/final/a.txt": data})

    def partial_collection(self):
        data = {"/output/final/a.txt": b"A", "/output/final/b.txt": b"B"}
        return self.collect([entry(k, v) for k, v in data.items()], data, _simulate_read_failure={"/output/final/b.txt"})

    # grading_decision -----------------------------------------------------------------------
    def test_decision_table(self):
        cases = [
            (execution("completed"), "complete", True, "collected"),
            (execution("completed"), "no_files_confirmed", True, "no_deliverable_files_confirmed"),
            (execution("limited", [limit("time")]), "complete", True, "collected"),
            (execution("limited", [limit("time")]), "no_files_confirmed", True, "no_deliverable_files_confirmed"),
            (execution("limited", [limit("message")]), "complete", True, "collected"),
            (execution("limited", [limit("token")]), "complete", True, "collected"),
            (execution("limited", [limit("working")]), "no_files_confirmed", True, "no_deliverable_files_confirmed"),
            (execution("limited", [limit("time"), limit("message")]), "complete", True, "collected"),
            (execution("limited", [limit("operator", 1)]), "complete", False, "execution_limit_requires_review"),
            (execution("limited", [limit("custom")]), "complete", False, "execution_limit_requires_review"),
            (execution("limited", [limit("time"), limit("operator", 1)]), "complete", False, "execution_limit_requires_review"),
            (execution("limited", []), "complete", False, "execution_limit_requires_review"),
            (execution("limited", [limit("time")]), "partial", False, "requires_adjudication"),  # no attribution given: never an automatic verdict
            (execution("limited", [limit("time")]), "listing_failed", False, "harness_collection_error"),
            (execution("completed"), "partial", False, "requires_adjudication"),
            (execution("limited", [limit("cost", 2.0)]), "complete", True, "collected"),  # Inspect per-sample cost limit is a budget type
            (execution("error", errors=[{"event_uuid": "e1", "message": "boom"}]), "complete", False, "execution_error"),
            (execution("error", [limit("time")], [{"event_uuid": "e1", "message": "boom"}]), "complete", False, "execution_error"),
            (execution("error", errors=[{"event_uuid": "e1", "message": "boom"}]), "no_files_confirmed", False, "execution_error"),
            (execution("unknown", solver_finished=False), "complete", False, "execution_unknown"),
            (execution("unknown", solver_finished=False), "no_files_confirmed", False, "execution_unknown"),
        ]
        for i, (exe, status, eligible, cls) in enumerate(cases):
            with self.subTest(i=i, status=exe["status"], collection=status):
                got_eligible, got_class, basis = c.grading_decision(exe, status)
                self.assertEqual((got_eligible, got_class), (eligible, cls))
                self.assertTrue(basis)
                self.assertIn(got_class, c.OUTCOME_CLASSES)

    def test_execution_status_precedence(self):
        self.assertEqual(c._execution_status([{"m": 1}], [limit("time")], True), "error")
        self.assertEqual(c._execution_status([], [limit("time")], True), "limited")
        self.assertEqual(c._execution_status([], [], True), "completed")
        self.assertEqual(c._execution_status([], [], False), "unknown")

    # write + load round trips -----------------------------------------------------------------
    def test_time_limited_complete_is_eligible_with_evidence(self):
        rec = self.complete_collection()
        out = c.write_run_outcome(self.host, self.binding, rec, execution("limited", [limit("time", 2.0)]))
        self.assertTrue(out["grading_eligible"])
        self.assertEqual(out["execution"]["status"], "limited")
        self.assertEqual(out["collection_status"], "complete")
        self.assertFalse(out["harness_error"])
        self.assertEqual(out["execution"]["limits"][0]["event_uuid"], "evt-time")
        loaded = c.load_run_outcome(self.host, self.binding, for_grading=True)
        self.assertEqual(loaded["outcome_class"], "collected")
        self.assertIn("budget exhausted", loaded["grading_basis"])

    def test_message_limited_no_files_is_eligible(self):
        rec = self.collect()
        out = c.write_run_outcome(self.host, self.binding, rec, execution("limited", [limit("message", 6)]))
        self.assertTrue(out["grading_eligible"])
        self.assertEqual(out["collection_status"], "no_files_confirmed")
        self.assertEqual(out["outcome_class"], "no_deliverable_files_confirmed")
        self.assertEqual(c.load_run_outcome(self.host, self.binding)["execution"]["limit_types"], ["message"])

    def test_limited_with_unresolved_partial_requires_adjudication(self):
        rec = self.partial_collection()  # read_failed: cause undetermined by the reason name alone
        out = c.write_run_outcome(self.host, self.binding, rec, execution("limited", [limit("time")]))
        self.assertFalse(out["harness_error"])
        self.assertFalse(out["grading_eligible"])
        self.assertTrue(out["requires_adjudication"])
        self.assertEqual(out["outcome_class"], "requires_adjudication")
        self.assertEqual(out["execution"]["status"], "limited")
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, self.binding)
        self.assertEqual(c.load_run_outcome(self.host, self.binding, for_grading=False)["outcome_class"], "requires_adjudication")

    def test_operator_limit_requires_review(self):
        rec = self.complete_collection()
        out = c.write_run_outcome(self.host, self.binding, rec, execution("limited", [limit("operator", 1)]))
        self.assertFalse(out["grading_eligible"])
        self.assertEqual(out["outcome_class"], "execution_limit_requires_review")
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, self.binding)

    def test_execution_error_with_complete_collection_is_ineligible(self):
        rec = self.complete_collection()
        err = execution("error", errors=[{"event_uuid": "evt-err", "message": "RuntimeError('provider failed')"}], solver_finished=False)
        out = c.write_run_outcome(self.host, self.binding, rec, err)
        self.assertEqual((out["execution"]["status"], out["grading_eligible"], out["harness_error"], out["outcome_class"]),
                         ("error", False, False, "execution_error"))
        self.assertEqual(out["execution"]["errors"][0]["message"], "RuntimeError('provider failed')")
        with self.assertRaises(c.OutcomeValidationError):
            c.load_run_outcome(self.host, self.binding)

    def test_tampered_limited_outcomes_fail_closed(self):
        rec = self.complete_collection()
        good = c.write_run_outcome(self.host, self.binding, rec, execution("limited", [limit("time")]))
        tampered = [
            {**good, "grading_eligible": False},
            {**good, "outcome_class": "execution_error"},
            {**good, "execution": {**good["execution"], "limits": [limit("operator", 1)], "limit_types": ["operator"]}},
            {**good, "execution": {**good["execution"], "status": "completed"}},
            {**good, "execution": {**good["execution"], "limits": [{"type": "time"}], "limit_types": ["time"]}},
            {**good, "execution": {**good["execution"], "limit_types": ["message"]}},
            {**good, "grading_basis": None},
        ]
        for i, bad in enumerate(tampered):
            with self.subTest(i=i):
                c._atomic_json(self.host, "run_outcome.json", bad)
                with self.assertRaises(c.OutcomeValidationError):
                    c.load_run_outcome(self.host, self.binding, for_grading=False)
        c._atomic_json(self.host, "run_outcome.json", good)
        self.assertTrue(c.load_run_outcome(self.host, self.binding)["grading_eligible"])

    def test_outcome_records_budget_types_and_basis(self):
        rec = self.complete_collection()
        out = c.write_run_outcome(self.host, self.binding, rec, execution("completed"))
        self.assertEqual(out["budget_limit_types"], ["time", "working", "message", "token", "cost"])
        self.assertEqual(json.loads(Path(self.host, "run_outcome.json").read_text())["grading_basis"], out["grading_basis"])


if __name__ == "__main__":
    unittest.main()
