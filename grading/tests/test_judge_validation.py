"""Judge Validation runner gates (no provider call): the freeze gate fails closed, the per-call guard refuses a call that
could cross the ceiling or would use another key, and a dirty plan refuses the paid run."""
import os
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from grading import judge_validation as JV


class FreezeGateTests(unittest.TestCase):
    def test_missing_tag_or_changed_code_fails_closed(self):
        with mock.patch.object(JV.subprocess, "run", return_value=SimpleNamespace(stdout="")):
            self.assertEqual(JV.frozen_state(), {"ok": False, "reason": f"tag {JV.FREEZE_TAG} does not exist"})
        answers = iter([SimpleNamespace(stdout="abc123\n"), SimpleNamespace(stdout=""), SimpleNamespace(stdout="grading/judge.py\n"), SimpleNamespace(stdout="")])  # tags oldest first, then diff, status
        with mock.patch.object(JV.subprocess, "run", side_effect=lambda *a, **k: next(answers)):
            st = JV.frozen_state()
        self.assertFalse(st["ok"]); self.assertIn("grading/judge.py", st["reason"])

    def test_paid_run_refuses_an_uncommitted_plan_or_an_open_freeze_gate(self):
        with mock.patch.object(JV, "check", return_value={"plan_committed": False, "freeze": {"ok": True}}):
            with self.assertRaisesRegex(SystemExit, "plan must be committed"):
                JV.run()
        with mock.patch.object(JV, "check", return_value={"plan_committed": True, "freeze": {"ok": False, "reason": "frozen paths differ"}}):
            with self.assertRaisesRegex(SystemExit, "freeze gate"):
                JV.run()


class RecoverGateTests(unittest.TestCase):
    def test_recovery_refuses_while_the_ledger_holds_a_unit(self):
        snap = {"review_pending_units": ["u"], "open_reservations": [], "stops": []}
        with mock.patch.object(JV, "check", return_value={"plan_committed": True, "freeze": {"ok": True, "tag_commit": "c"}}), \
             mock.patch.object(JV, "spent", return_value={"snapshot": snap}):
            with self.assertRaisesRegex(SystemExit, "ledger not clear"):
                JV.recover("RUN", [69])


class GuardTests(unittest.TestCase):
    def test_ceiling_and_key_are_checked_before_every_call(self):
        nxt = JV.worst_case_usd(10_000, 16_384, "long")
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "x" + JV.DEV_KEY_SUFFIX}, clear=False):
            for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
                os.environ.pop(k, None)
            holder = {"judge": SimpleNamespace(calls=[])}
            self.assertIsNone(JV.make_guard(holder, 16_384, Decimal("14") - nxt, Decimal("15"))(10_000))
            self.assertRegex(JV.make_guard(holder, 16_384, Decimal("15") - nxt + Decimal("0.01"), Decimal("15"))(10_000) or "", "ceiling 15 USD")
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "another-project-key"}, clear=False):
            self.assertRegex(JV.make_guard({}, 16_384, Decimal(0), Decimal("15"))(10_000) or "", "not the Dev project key")


if __name__ == "__main__":
    unittest.main()
