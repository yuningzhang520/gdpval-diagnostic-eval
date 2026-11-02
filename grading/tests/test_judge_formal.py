"""Formal judge runner gates (prepared, not run; no provider call): every gate fails closed, only finalized canonical runs
are listed, and the paid command refuses while a gate is open."""
import json
import os
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from grading import judge_formal as JF


class GateTests(unittest.TestCase):
    def test_paid_run_refuses_until_every_gate_holds(self):
        with mock.patch.object(JF, "gates", return_value={"ok": False, "freeze_tag": {"ok": False}}):
            with self.assertRaisesRegex(SystemExit, "gates not met"):
                JF.run("human", "status entry", scope())

    def test_missing_freeze_tag_and_a_draft_config_fail_closed(self):
        with mock.patch.object(JF.subprocess, "run", return_value=SimpleNamespace(stdout="")):
            g = JF.gates()
        self.assertFalse(g["ok"])
        self.assertEqual((g["freeze_tag"]["ok"], g["config_frozen"]["ok"]), (False, False))
        self.assertTrue(g["judge_formal_config"]["ok"])  # the approved 30 USD, concurrency 1, one pass are configured

    def test_run_requires_the_launch_authorization_and_the_restated_scope(self):
        with mock.patch.object(JF, "gates", return_value={"ok": True}):
            for by, ref, confirm in ((None, "status entry", "x"), ("human", None, "x"), ("human", "status entry", "judge-formal|other|30")):
                with self.assertRaisesRegex(SystemExit, "--authorized-by"):
                    JF.run(by, ref, confirm)


def scope():
    c = JF.cfg()["judge"]
    return f"judge-formal|{c['model']}|{c['formal']['ceiling_usd']}"


class FakeLedger:
    def __init__(self, remaining):
        self.remaining = remaining

    def snapshot(self):
        return {"remaining_usd": str(self.remaining), "settled_usd": "0", "reserved_usd": "0"}


class PassLoopTests(unittest.TestCase):
    """The pass loop with the gates, the ledger, run discovery and grading mocked: no provider call."""

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        for k, v in (("JDIR", self.d.name), ("REGISTRY", os.path.join(self.d.name, "registry.jsonl")), ("SEALED", os.path.join(self.d.name, "sealed"))):
            p = mock.patch.object(JF, k, v); p.start(); self.addCleanup(p.stop)
        p = mock.patch.object(JF, "gates", return_value={"ok": True, "freeze_tag": {"ok": True, "commit": "c0ffee"}}); p.start(); self.addCleanup(p.stop)
        for name, value in (("on_ac_power", True), ("select_project_credential", {"variable": "GOOGLE_API_KEY_VALIDATION", "suffix": "FRML"})):  # 2026-11-02: AC power and the Formal project's key
            p = mock.patch.object(JF, name, return_value=value); p.start(); self.addCleanup(p.stop)
        self.runs = [{"run_uuid": f"R{i}", "task_id": "t", "judge_items": [1, 2], "grading_out": os.path.join(self.d.name, "sealed", f"R{i}")} for i in range(2)]

    def test_each_finalized_run_is_judged_once_and_the_registry_carries_no_verdict(self):
        graded = []
        fake = lambda r, est, log, auth, extra=None, project_suffix=None: graded.append(r["run_uuid"]) or {"rc": 0, "calls": 2, "calls_ok": 2, "provider_error": 0, "not_attempted": 0, "halted": None}
        cfg = JF.cfg(); cfg["batches"]["formal"]["units_total"] = 2
        with mock.patch.object(JF, "finalized_runs", return_value=self.runs), mock.patch.object(JF, "_grade", side_effect=fake), \
             mock.patch.object(JF, "ensure_ledger", return_value=FakeLedger(30)), mock.patch.object(JF, "cfg", return_value=cfg):
            self.assertEqual(JF.run("human", "status entry", scope(), poll_s=0), 0)
            with self.assertRaisesRegex(SystemExit, "already started"):  # exactly one pass
                JF.run("human", "status entry", scope(), poll_s=0)
        self.assertEqual(graded, ["R0", "R1"])
        text = open(JF.REGISTRY, encoding="utf-8").read()
        for word in ("verdict", ': "pass"', ': "fail"', "score"):
            self.assertNotIn(word, text)
        self.assertEqual(oct(os.stat(JF.SEALED).st_mode & 0o777), "0o700")

    def test_budget_exhaustion_stops_and_keeps_the_partial_state(self):
        with mock.patch.object(JF, "finalized_runs", return_value=self.runs), mock.patch.object(JF, "_grade") as g, \
             mock.patch.object(JF, "ensure_ledger", return_value=FakeLedger(JF.one_call_usd() / 2)):
            JF.run("human", "status entry", scope(), poll_s=0)
        g.assert_not_called()
        self.assertEqual(JF.status()["stops"], ["budget_stop"])

    def test_a_grading_error_is_recorded_and_never_retried(self):
        cfg = JF.cfg(); cfg["batches"]["formal"]["units_total"] = 2
        with mock.patch.object(JF, "finalized_runs", return_value=self.runs), mock.patch.object(JF, "_grade", side_effect=RuntimeError("boom")) as g, \
             mock.patch.object(JF, "ensure_ledger", return_value=FakeLedger(30)), mock.patch.object(JF, "cfg", return_value=cfg):
            JF.run("human", "status entry", scope(), poll_s=0)
        self.assertEqual(g.call_count, 2)
        self.assertEqual(JF.status()["errors"], 2)

    def test_reservation_is_capped_at_the_remaining_budget(self):
        self.assertEqual(JF.reservation_usd(50, Decimal("3.10")), Decimal("3.10"))
        self.assertLessEqual(JF.reservation_usd(1, Decimal(30)), Decimal(30))


class FinalizedRunTests(unittest.TestCase):
    def test_only_canonical_finalized_runs_with_an_eval_log_are_listed(self):
        with tempfile.TemporaryDirectory() as d:
            task = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
            log = os.path.join(d, "a.eval"); open(log, "w").write("x")
            for u, final in (("RUNFINAL", True), ("RUNOPEN", False)):
                os.makedirs(os.path.join(d, u))
                json.dump({"final": final}, open(os.path.join(d, u, "run_outcome.json"), "w"))
            os.makedirs(os.path.join(d, "RUNNOOUTCOME"))
            open(os.path.join(d, "canonical_designations.jsonl"), "w").write("".join(json.dumps({"run_uuid": u, "task_id": task, "designation": "canonical", "model": "m"}) + "\n"
                                                                                for u in ("RUNFINAL", "RUNOPEN", "RUNNOOUTCOME")))
            open(os.path.join(d, "run_inventory.jsonl"), "w").write("".join(json.dumps({"run_uuid": u, "log_file": log, "unit_id": u}) + "\n" for u in ("RUNFINAL", "RUNOPEN", "RUNNOOUTCOME")))
            with mock.patch.object(JF, "RUNS", d):
                self.assertEqual([r["run_uuid"] for r in JF.finalized_runs()], ["RUNFINAL"])  # a run still writing (not final) is never read


if __name__ == "__main__":
    unittest.main()
