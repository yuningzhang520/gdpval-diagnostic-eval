"""Batch runner (run classes, 2026-11-01): planning from the class inventory. A completed sample and an attempt that
ended in an execution error both block an automatic rerun (the latter with the execution-error reason); --allow-repeat
is the only way to run such a task again. Dry-run units go through the launcher with a fake docker runner; no provider.
Run: harness/tests/run_isolated.sh <root> unittest harness.tests.test_batch_unit -v"""
import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from harness import batch as B, launcher as L

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG = os.path.join(ROOT, "config.json")
TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
MODEL = "google/gemini-3.8-flash"


class BatchPlanningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="batch_unit_")
        self.root = os.path.realpath(self.tmp.name)
        self.runs = os.path.join(self.root, "dev", "runs"); os.makedirs(self.runs)
        self.ledger = os.path.join(self.root, "dev", "ledger.json")
        self.env_file = os.path.join(self.root, "env.test"); open(self.env_file, "w").write("GOOGLE_API_KEY=dummy-test-key-not-real-0005\n")
        image = L.load_config(CONFIG)["sandbox"]["image_id"]
        self.docker = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=f"{image}|arm64|linux|[]\n", stderr="")

    def tearDown(self):
        self.tmp.cleanup()

    def argv(self, *extra):
        return ["--config", CONFIG, "--run-label", "dev", "--model", MODEL, "--runs-root", self.runs, "--ledger", self.ledger, "--env-file", self.env_file, "--tasks", TASK, "--dry-run", *extra]

    def inventory(self, **fields):
        rec = {"kind": "sample", "run_label": "dev", "task_id": TASK, "model": MODEL, "unit_id": "u", "run_uuid": "r1", "dry_run": False, "engineering_failure": None, **fields}
        with open(os.path.join(self.runs, "run_inventory.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")

    def latest_batch_record(self):
        d = os.path.join(self.runs, "batch_records")
        return json.load(open(os.path.join(d, sorted(os.listdir(d))[-1])))

    def test_completed_sample_is_skipped_unless_allow_repeat(self):
        self.inventory()
        self.assertEqual(B.main(self.argv(), docker_runner=self.docker), 0)
        plan = self.latest_batch_record()["plan"]
        self.assertEqual((plan[0]["action"], "completed sample exists" in plan[0]["reason"]), ("skip", True))
        self.assertEqual(B.main(self.argv("--allow-repeat"), docker_runner=self.docker), 0)
        rec = self.latest_batch_record()
        self.assertEqual((rec["plan"][0]["action"], rec["plan"][0]["repeat_of"], rec["status"], len(rec["units"])), ("run", ["r1"], "completed", 1))

    def test_execution_error_is_not_a_completed_sample_and_is_never_rerun_automatically(self):
        self.inventory(engineering_failure="TypeError", inspect_status="success")
        self.assertEqual(B.completed_units(self.runs), {(TASK, MODEL): []})
        self.assertEqual(B.main(self.argv(), docker_runner=self.docker), 0)
        plan = self.latest_batch_record()["plan"]
        self.assertEqual(plan[0]["action"], "skip"); self.assertIn("execution error", plan[0]["reason"]); self.assertIn("TypeError", plan[0]["reason"])
        self.assertEqual(B.main(self.argv("--allow-repeat"), docker_runner=self.docker), 0)
        self.assertEqual(self.latest_batch_record()["plan"][0]["earlier_execution_errors"], ["TypeError"])

    def test_confirm_batch_must_restate_the_batch(self):
        with self.assertRaisesRegex(L.LauncherError, "confirm-batch"):
            B.parse_confirm_batch("dev|google/gemini-3.8-flash|9|5.00", run_label="dev", model=MODEL, units=10, estimate_usd=B.Decimal("5.00"))
        B.parse_confirm_batch("dev|google/gemini-3.8-flash|10|5.00", run_label="dev", model=MODEL, units=10, estimate_usd=B.Decimal("5.00"))


if __name__ == "__main__":
    unittest.main()
