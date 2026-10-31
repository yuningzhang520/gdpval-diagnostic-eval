"""Launcher and budget-ledger regressions from the Codex review rounds (logs/pilot-a-review-6uxm37u9:
B1, B6, I4, I6, I7; logs/pilot-final-review-ogcsjzyp: B6 usage-source conflict, I4 delayed-create
race, I7 Inspect ModelCost rates, Docker image-ID pre-flight). No model, no Docker daemon call
(the pre-flight is exercised with a fake runner), no network; config.json is read for the
execution settings only and the tests never touch a .env file.
Run: python -m unittest harness.tests.test_launcher_regressions -v"""
import copy
import importlib.util
import json
import multiprocessing
import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from inspect_ai.model import ModelUsage

from harness import budget as b
from harness import launcher as L

CONFIG = os.path.join(L.ROOT, "config.json")
PRICES = {"anthropic/claude-opus-5-5": {"input": 4, "output": 20, "cache_read": 0.20, "cache_write": 8},
          "openai/gpt-6.1-sol": {"input": 2, "output": 10, "cache_read": 0.10, "cache_write": 5}}
MARKERS = ("review-only-fabricated-value-9472", "sk-ant-SYNTHETIC-not-a-real-key-000000", "AIzaSyNTHETIC_not_real_00000000000", "Bearer synthetictoken0000000000000000")


def cfg():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def usage_log(model, usage: ModelUsage, *, calls=None):
    """A returned Inspect log of a successful sample with aggregated usage and optional per-call ModelEvents."""
    events = [SimpleNamespace(event="model", model=model, retries=None, output=SimpleNamespace(usage=u)) for u in (calls or [])]
    sample = SimpleNamespace(model_usage={model: usage}, events=events, uuid="u1", error=None)
    return [SimpleNamespace(status="success", error=None, samples=[sample], location="/synthetic/log.eval")]


def returned_error_log(message="ProviderError: synthetic provider failure"):
    """fail_on_error=False: an error is a normal return value, with an eval-level and a sample-level error and no usage."""
    err = SimpleNamespace(message=message)
    sample = SimpleNamespace(model_usage={}, events=[], uuid="u1", error=err)
    return [SimpleNamespace(status="error", error=err, samples=[sample], location="/synthetic/log.eval")]


def _delayed_first(path, ready, release, q):
    """Codex final review (concurrent_create): the first process holds the creation lock and delays its
    initial write until released; the second must wait for it rather than re-create the ledger."""
    class Delayed(b.BudgetLedger):
        def _write(self, state):
            if not state["entries"] and not os.path.exists(self.path):
                ready.set()
                assert release.wait(15)
            return super()._write(state)
    lg = Delayed(path, 30, PRICES)
    lg.reserve("held", "sample", 20, {"model": "m", "task": "t"})
    q.put(("first", "reserved"))


def _second(path, q, t0):
    import time as _t
    lg = b.BudgetLedger(path, 30, PRICES)
    q.put(("second", "constructed", _t.monotonic() - t0, lg.snapshot()["open_reservations"]))


def _worker(args):  # module level: picklable for the spawn start method
    path, ceiling, unit, estimate = args
    try:
        lg = b.BudgetLedger(path, ceiling, PRICES)
        lg.reserve(unit, "sample", estimate, {"model": "m", "task": "t"})
        return "reserved"
    except b.BudgetExhausted:
        return "exhausted"
    except Exception as ex:  # any other outcome is a defect
        return "error:" + type(ex).__name__


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="launcher_regress_")
        self.root = os.path.realpath(self.tmp.name)
        self.cfg = cfg()

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, ceiling, eval_fn, name="ledger.json"):
        ledger = b.BudgetLedger(os.path.join(self.root, name), ceiling, PRICES)
        return L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger, eval_fn=eval_fn), ledger

    def entries(self, ledger):
        return json.loads(Path(ledger.path).read_text())["entries"]

    def records(self, launcher):
        return {f: Path(launcher.record_dir, f).read_text() for f in sorted(os.listdir(launcher.record_dir))}


# ------------------------------------------------------------------------------------------ B1
class DispatchTests(_Base):
    def test_eval_dispatch_carries_every_approved_setting_and_the_model_name(self):
        seen = []

        def spy(task, **kw):
            seen.append(kw)
            return usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=100))
        launcher, _ = self.make(30, spy)
        models = ("anthropic/claude-opus-5-5", "openai/gpt-6.1-sol")
        for m in models:
            launcher.run_sample(task=SimpleNamespace(name="synthetic"), model=m, unit_id=m, estimate_usd=2)
        g, r1, c = self.cfg["generation"], self.cfg["retries"]["layer_1_inspect_model_request"], self.cfg["concurrency"]["pilot"]
        for kw, m in zip(seen, models):
            self.assertEqual(kw["model"], m)
            self.assertEqual((kw["max_tokens"], kw["attempt_timeout"], kw["token_limit"]), (g["max_tokens_per_request"], r1["attempt_timeout_s"], g["token_limit"]))
            self.assertEqual((kw["max_tokens"], kw["attempt_timeout"], kw["token_limit"]), (16384, 600, 10_000_000))
            self.assertEqual((kw["time_limit"], kw["working_limit"], kw["message_limit"]), (g["time_limit_s"], g["working_limit_s"], g["message_limit"]))
            self.assertEqual((kw["max_retries"], kw["timeout"], kw["model_args"]), (r1["max_retries"], r1["timeout_s"], {"max_retries": self.cfg["retries"]["layer_2_provider_sdk"]["max_retries"]}))
            self.assertEqual((kw["retry_on_error"], kw["fail_on_error"], kw["task_retry_attempts"], kw["epochs"]), (0, False, 0, 1))
            self.assertEqual(kw["cost_limit"], float(g["cost_limit_usd"])); self.assertIn(m, kw["model_cost_config"])
            self.assertTrue(kw["sandbox_prebuilt"]); self.assertTrue(kw["log_images"])
            self.assertEqual((kw["max_samples"], kw["max_tasks"], kw["max_sandboxes"], kw["max_connections"]), (c["max_samples"], c["max_tasks"], c["max_sandboxes"], c["max_connections"]))
            self.assertEqual(kw["log_dir"], launcher.log_dir)

    def test_missing_execution_settings_refuse_before_any_ledger_change(self):
        for path in (("generation", "max_tokens_per_request"), ("retries", "layer_1_inspect_model_request", "attempt_timeout_s"), ("generation", "token_limit")):
            with self.subTest(setting=path[-1]):
                c = copy.deepcopy(self.cfg)
                d = c
                for k in path[:-1]:
                    d = d[k]
                del d[path[-1]]
                called = []
                ledger = b.BudgetLedger(os.path.join(self.root, f"ledger_{path[-1]}.json"), 30, PRICES)
                launcher = L.PilotLauncher(c, runs_root=self.root, ledger=ledger, eval_fn=lambda *a, **k: called.append(1))
                with self.assertRaisesRegex(L.LauncherError, path[-1]):
                    launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=1)
                self.assertEqual(called, [])
                self.assertEqual(self.entries(ledger), [])  # no reservation, no settlement, no failure event
                for bad in (0, -5, "16384", 1.5, True):
                    c2 = copy.deepcopy(self.cfg); c2["generation"]["max_tokens_per_request"] = bad
                    with self.assertRaises(L.LauncherError):
                        L.eval_kwargs(c2, log_dir="/x", model="openai/gpt-6.1-sol")


# ------------------------------------------------------------------------------------------ B6
class EngineeringFailureStopTests(_Base):
    def test_returned_error_logs_are_counted_and_the_third_start_is_refused(self):
        starts = []

        def error_return(task, **kw):
            starts.append(kw["model"])
            return returned_error_log()
        launcher, ledger = self.make(30, error_return)
        results = []
        for i in range(3):
            try:
                results.append(launcher.run_sample(task=SimpleNamespace(name="synthetic"), model="anthropic/claude-opus-5-5", unit_id=f"err{i}", estimate_usd=1)["settlement"]["cost_usd"])
            except b.BudgetExhausted as ex:
                results.append("refused: " + str(ex))
        self.assertEqual(len(starts), 2)
        self.assertEqual(results[:2], ["1.000000", "1.000000"])  # no usage → settled at the reservation (estimated), never zero
        self.assertTrue(results[2].startswith("refused") and "ProviderError" in results[2], results[2])
        self.assertEqual(launcher.engineering_failures, {"ProviderError": 2})
        snap = ledger.snapshot()
        self.assertEqual((snap["settled_units"], snap["open_reservations"], snap["settled_usd"]), (["err0", "err1"], [], "2.000000"))
        entries = self.entries(ledger)
        self.assertEqual([e["type"] for e in entries], ["reservation", "settlement", "engineering_failure"] * 2)  # the refusal added nothing
        self.assertTrue(all(e["estimated"] and e["manual_review_required"] is False for e in entries if e["type"] == "settlement"))
        self.assertTrue(all("synthetic provider failure" in e["detail"] for e in entries if e["type"] == "engineering_failure"))
        refused = [v for k, v in self.records(launcher).items() if "_refused_" in k]
        self.assertEqual(len(refused), 1); self.assertIn("ProviderError", refused[0])
        # a restart keeps the stop condition
        launcher2, ledger2 = L.PilotLauncher(self.cfg, runs_root=self.root, ledger=b.BudgetLedger(ledger.path, 30, PRICES), eval_fn=error_return), None
        with self.assertRaises(b.BudgetExhausted):
            launcher2.run_sample(task=SimpleNamespace(name="synthetic"), model="anthropic/claude-opus-5-5", unit_id="err3", estimate_usd=1)
        self.assertEqual(len(starts), 2)
        self.assertEqual(self.entries(launcher2.ledger)[:6], entries)  # original outcomes unchanged

    def test_cost_above_twice_the_estimate_records_a_stop_that_survives_restart(self):
        def eval_fn(task, **kw):
            return usage_log(kw["model"], ModelUsage(input_tokens=2_500_000, output_tokens=0))  # 5.00 USD at 2 USD/MTok
        launcher, ledger = self.make(30, eval_fn)
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=2)
        self.assertEqual(meta["settlement"]["cost_usd"], "5.000000")
        self.assertTrue(meta["post_run"]["stop_recorded"] and "2x" in meta["post_run"]["stop_recorded"][0])
        with self.assertRaisesRegex(b.BudgetExhausted, "exceeds 2x"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u2", estimate_usd=1)
        before = self.entries(ledger)
        launcher2 = L.PilotLauncher(self.cfg, runs_root=self.root, ledger=b.BudgetLedger(ledger.path, 30, PRICES), eval_fn=eval_fn)
        with self.assertRaises(b.BudgetExhausted):
            launcher2.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u3", estimate_usd=1)
        self.assertEqual(len(launcher2.ledger.snapshot()["stops"]), 1)
        self.assertEqual(self.entries(launcher2.ledger), before)
        self.assertEqual([e["type"] for e in before], ["reservation", "settlement", "stop"])

    def test_unpriced_usage_is_never_zero_and_holds_further_starts_until_a_recorded_review(self):
        def eval_fn(task, **kw):
            return usage_log("unrecognised/model", ModelUsage(input_tokens=1000, output_tokens=0))
        launcher, ledger = self.make(30, eval_fn)
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=5)
        s = meta["settlement"]
        self.assertEqual(s["cost_usd"], "5.000000"); self.assertTrue(s["manual_review_required"]); self.assertTrue(s["estimated"])
        self.assertTrue(any("estimated_unknown_cost" in f for f in s["flags"])); self.assertEqual(s["raw_usage"]["unrecognised/model"]["input_tokens"], 1000)
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u2", estimate_usd=1)
        ledger.clear_review("u1", by="reviewer", basis="provider account statement checked")
        launcher.eval_fn = lambda task, **kw: usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=0))
        self.assertEqual(launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u2", estimate_usd=1)["settlement"]["cost_usd"], "0.002000")
        with self.assertRaises(b.LedgerCorrupt):
            ledger.clear_review("u2", by="reviewer", basis="nothing pending")  # clearance for a unit not awaiting review is an impossible transition

    def test_ledger_refuses_unknown_event_types_and_malformed_events(self):
        _, ledger = self.make(30, None)
        ledger.reserve("unit", "sample", 20, {"model": "m"})
        p = Path(ledger.path)
        good = json.loads(p.read_text())
        damaged = copy.deepcopy(good); damaged["entries"][0]["type"] = "damaged-reservation"
        p.write_text(json.dumps(damaged))
        with self.assertRaises(b.LedgerCorrupt):
            b.BudgetLedger(ledger.path, 30, PRICES)
        with self.assertRaises(b.LedgerCorrupt):
            ledger.snapshot()
        for mutate in (lambda e: e.pop("estimated_usd"), lambda e: e.__setitem__("kind", "other"), lambda e: e.__setitem__("estimated_usd", -1), lambda e: e.pop("at")):
            bad = copy.deepcopy(good); mutate(bad["entries"][0]); p.write_text(json.dumps(bad))
            with self.assertRaises(b.LedgerCorrupt):
                b.BudgetLedger(ledger.path, 30, PRICES)
        orphan = copy.deepcopy(good)
        orphan["entries"].append({"type": "settlement", "unit_id": "ghost", "kind": "sample", "cost_usd": "1.000000", "breakdown": {c: "0.000000" for c in b.CATEGORIES}, "retry_estimate_usd": "0.000000",
                                  "estimated": False, "flags": [], "manual_review_required": False, "raw_usage": {}, "at": "2026-10-30T00:00:00+00:00"})
        p.write_text(json.dumps(orphan))
        with self.assertRaises(b.LedgerCorrupt):  # settlement without a reservation is an impossible transition
            b.BudgetLedger(ledger.path, 30, PRICES)
        p.write_text(json.dumps(good))
        self.assertEqual(b.BudgetLedger(ledger.path, 30, PRICES).snapshot()["reserved_usd"], "20.000000")

    def test_repeat_reservation_with_a_different_estimate_or_binding_conflicts(self):
        _, ledger = self.make(30, None)
        first = ledger.reserve("unit", "sample", 1, {"model": "a", "task": "t"})
        with self.assertRaises(b.LedgerConflict):
            ledger.reserve("unit", "sample", 10, {"model": "a", "task": "t"})
        with self.assertRaises(b.LedgerConflict):
            ledger.reserve("unit", "sample", 1, {"model": "b", "task": "t"})
        with self.assertRaises(b.LedgerConflict):
            ledger.reserve("unit", "judge", 1, {"model": "a", "task": "t"})
        self.assertEqual(ledger.reserve("unit", "sample", 1, {"model": "a", "task": "t"}), first)
        self.assertEqual(ledger.snapshot()["reserved_usd"], "1.000000")


    def test_aggregated_and_per_call_usage_conflict_settles_conservatively_and_holds(self):
        """Codex final review (incomplete_call_usage): aggregated input 1,000,000 vs one per-call event of
        1,000 tokens settled at 0.004 USD. Now: 4.00 USD (not below the aggregate), both raw values and the
        difference kept, estimated + manual review, next paid start refused, hold survives a restart."""
        def eval_fn(task, **kw):
            return usage_log(kw["model"], ModelUsage(input_tokens=1_000_000, output_tokens=0), calls=[ModelUsage(input_tokens=1000, output_tokens=0)])
        launcher, ledger = self.make(100, eval_fn)
        meta = launcher.run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u", estimate_usd=1)  # the review's 1 USD estimate
        s = meta["settlement"]
        self.assertEqual(s["cost_usd"], "4.000000"); self.assertTrue(s["estimated"]); self.assertTrue(s["manual_review_required"])
        self.assertTrue(any("usage_sources_conflict" in f for f in s["flags"]))
        rec = s["usage_reconciliation"]["anthropic/claude-opus-5-5"]
        self.assertEqual((rec["aggregated"]["input"], rec["per_call"]["input"], rec["difference"]["input"], rec["conflict"]), (1_000_000, 1000, 999_000, True))
        self.assertEqual((rec["cost_per_call"], rec["cost_conservative_aggregate"]), ("0.004000", "4.000000"))
        self.assertEqual(s["raw_usage"]["anthropic/claude-opus-5-5"]["input_tokens"], 1_000_000); self.assertEqual(s["raw_calls"]["anthropic/claude-opus-5-5"][0]["input_tokens"], 1000)
        self.assertEqual(s["usage_scope"]["same_sample"], True)
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)
        ledger2 = b.BudgetLedger(ledger.path, 100, PRICES)  # restart
        self.assertTrue(any("manual review" in r for r in ledger2.stop_reasons()))
        self.assertEqual(json.loads(Path(ledger.path).read_text())["entries"][1]["cost_usd"], "4.000000")  # original settlement untouched
        ledger2.clear_review("u", by="reviewer", basis="provider statement checked")
        # Codex round 3 (exact-old-stop): the review hold is lifted, but the 4.00 USD settlement on a 1 USD estimate
        # is an independent 2x stop condition (plus the recorded stop event) that survives the clearance
        after = ledger2.stop_reasons()
        self.assertFalse(any("manual review" in r for r in after)); self.assertTrue(any("exceeds 2x" in r for r in after))
        with self.assertRaisesRegex(b.BudgetExhausted, "2x"):
            L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger2, eval_fn=eval_fn).run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u3", estimate_usd=1)

    def test_usage_conflict_hold_alone_is_lifted_by_a_recorded_review(self):
        """Estimate 3 isolates the review hold from the 2x rule: after clear_review a consistent unit settles exactly."""
        def eval_fn(task, **kw):
            return usage_log(kw["model"], ModelUsage(input_tokens=1_000_000, output_tokens=0), calls=[ModelUsage(input_tokens=1000, output_tokens=0)])
        launcher, ledger = self.make(100, eval_fn)
        launcher.run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u", estimate_usd=3)
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)
        ledger2 = b.BudgetLedger(ledger.path, 100, PRICES)
        ledger2.clear_review("u", by="reviewer", basis="provider statement checked")
        launcher2 = L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger2, eval_fn=lambda task, **kw: usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=0), calls=[ModelUsage(input_tokens=1000, output_tokens=0)]))
        s2 = launcher2.run_sample(task=SimpleNamespace(name="s"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)["settlement"]
        self.assertEqual((s2["cost_usd"], s2["estimated"], s2["manual_review_required"]), ("0.004000", False, False))  # consistent sources: exact per-call pricing

    def test_more_than_one_sample_is_never_settled_from_the_first(self):
        """Codex round 3 (new_two_samples): a log with two samples was settled from samples[0] (0.004 instead of
        4.004 USD). Now: no settlement, reservation kept open, every sample's usage recorded, manual review,
        further paid starts refused, state kept across a restart."""
        l1 = usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1000, output_tokens=0), calls=[ModelUsage(input_tokens=1000, output_tokens=0)])[0]
        l2 = usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1_000_000, output_tokens=0), calls=[ModelUsage(input_tokens=1_000_000, output_tokens=0)])[0]
        l1.samples[0].uuid, l2.samples[0].uuid = "sample-one", "sample-two"; l1.samples += l2.samples
        launcher, ledger = self.make(100, lambda *a, **kw: [l1])
        meta = launcher.run_sample(task=SimpleNamespace(name="two-sample-task"), model="anthropic/claude-opus-5-5", unit_id="u", estimate_usd=3)
        self.assertIsNone(meta["settlement"]); self.assertTrue(meta["manual_review_required"]); self.assertEqual(meta["sample_count"], 2)
        self.assertEqual(set(meta["all_sample_usage"]), {"sample-one", "sample-two"}); self.assertEqual(meta["all_sample_usage"]["sample-two"]["anthropic/claude-opus-5-5"]["input_tokens"], 1_000_000)
        snap = ledger.snapshot()
        self.assertEqual((snap["reserved_usd"], snap["open_reservations"], snap["settled_usd"]), ("3.000000", ["u"], "0.000000"))
        self.assertTrue(any("1 EvalLog(s) with 2 sample(s) in total, expected exactly 1 and 1" in r for r in snap["stops"][0]))  # wording: extraction review R6 (log count added)
        with self.assertRaisesRegex(b.BudgetExhausted, "expected exactly 1"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)
        ledger2 = b.BudgetLedger(ledger.path, 100, PRICES)
        self.assertEqual(ledger2.snapshot()["open_reservations"], ["u"]); self.assertTrue(ledger2.stop_reasons())
        self.assertTrue(any("_sample_cardinality_" in f for f in os.listdir(launcher.record_dir)))

    def test_two_eval_logs_are_never_settled_from_the_first(self):
        """Codex extraction review R6 (two_eval_logs): eval returned two EvalLogs with one executed sample each and the unit
        was settled from logs[0] (0.004 USD while the second log held 1,000,000 input tokens). Now: no settlement, both
        logs and both samples' usage recorded, reservation kept open, engineering stop recorded, manual review, the next
        paid start refused, and the refusal survives a restart (the stop is a ledger event)."""
        l1 = usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1000, output_tokens=0))[0]
        l2 = usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1_000_000, output_tokens=0))[0]
        l1.samples[0].uuid, l2.samples[0].uuid = "first", "second"; l1.location, l2.location = "/synthetic/first.eval", "/synthetic/second.eval"
        launcher, ledger = self.make(100, lambda *a, **kw: [l1, l2])
        meta = launcher.run_sample(task=SimpleNamespace(name="one-task"), model="anthropic/claude-opus-5-5", unit_id="u", estimate_usd=3)
        self.assertIsNone(meta["settlement"]); self.assertTrue(meta["manual_review_required"]); self.assertEqual((meta["log_count"], meta["sample_count"]), (2, 2))
        self.assertEqual([p["log_file"] for p in meta["returned_logs"]], ["/synthetic/first.eval", "/synthetic/second.eval"]); self.assertEqual([p["samples"] for p in meta["returned_logs"]], [["first"], ["second"]])
        self.assertEqual({k: v["anthropic/claude-opus-5-5"]["input_tokens"] for k, v in meta["all_sample_usage"].items()}, {"first": 1000, "second": 1_000_000})
        snap = ledger.snapshot()
        self.assertEqual((snap["reserved_usd"], snap["open_reservations"], snap["settled_usd"]), ("3.000000", ["u"], "0.000000"))
        self.assertTrue(any("2 EvalLog(s) with 2 sample(s) in total, expected exactly 1 and 1" in r for r in snap["stops"][0]))
        with self.assertRaisesRegex(b.BudgetExhausted, "expected exactly 1 and 1"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)
        ledger2 = b.BudgetLedger(ledger.path, 100, PRICES)
        restarted = L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger2, eval_fn=lambda *a, **kw: [l1])
        with self.assertRaises(b.BudgetExhausted):
            restarted.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u3", estimate_usd=1)
        self.assertEqual(ledger2.snapshot()["open_reservations"], ["u"]); self.assertTrue(any("_sample_cardinality_" in f for f in os.listdir(launcher.record_dir)))

    def test_a_list_of_tasks_is_refused_before_any_call_or_reservation(self):
        """Codex extraction review R6, pre-call side: run_sample takes exactly one Task object. A list of two tasks, and a
        list of one, are refused with LauncherError before the stop check, the reservation and the eval call."""
        calls = []
        def eval_fn(*a, **kw):
            calls.append(a); return usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1000, output_tokens=0))
        launcher, ledger = self.make(100, eval_fn)
        for tasks in ([SimpleNamespace(name="a"), SimpleNamespace(name="b")], [SimpleNamespace(name="a")], (SimpleNamespace(name="a"),), None, "task.py"):
            with self.assertRaisesRegex(L.LauncherError, "single-task contract"):
                launcher.run_sample(task=tasks, model="anthropic/claude-opus-5-5", unit_id="u", estimate_usd=3)
        self.assertEqual(calls, []); snap = ledger.snapshot()
        self.assertEqual((snap["reserved_usd"], snap["open_reservations"], snap["settled_usd"]), ("0.000000", [], "0.000000")); self.assertFalse(ledger.stop_reasons())
        self.assertEqual(sum("_refused_" in f for f in os.listdir(launcher.record_dir)), 5)

    def test_stop_paths_leave_collected_outcomes_and_deliverables_untouched(self):
        """Codex round 3 (outcome_unchanged scope): the launcher's stop paths must not touch run_outcome.json or
        the collected deliverables. A real collector outcome is built, then error, 2x-cost and two-sample paths run."""
        import asyncio
        from harness import collect as C
        from harness.tests.test_collect_unit import RUN, FakeSandbox
        host = os.path.join(self.root, "runs", "outcome-under-test")
        binding = {**RUN, "uuid": "outcomeunchanged0000", "sample_id": "task", "task_id": "gdpval-pilot", "eval_id": "e"}
        C.bind_run(host, binding, None, "solver")
        raw = b"collected deliverable bytes"
        listing = {"ok": True, "root": C.FINAL_DIR, "root_state": "dir", "entries": [{"path": "/output/final/a.txt", "size": len(raw), "nlink": 1, "sha256": __import__("hashlib").sha256(raw).hexdigest()}], "skipped": [], "errors": []}
        rec = asyncio.run(C.collect_final_outputs(host, "scorer", binding, sb=FakeSandbox(listing, {"/output/final/a.txt": raw})))
        C.write_run_outcome(host, binding, rec, {"status": "completed", "errors": [], "limits": [], "limit_types": [], "solver_finished": True, "collector_scorer_executed": True})
        files = sorted(str(p) for p in Path(host).rglob("*") if p.is_file())
        before = {f: __import__("hashlib").sha256(Path(f).read_bytes()).hexdigest() for f in files}
        self.assertTrue(any(f.endswith("run_outcome.json") for f in files) and any(f.endswith("a.txt") for f in files))
        launcher, ledger = self.make(100, lambda *a, **kw: returned_error_log())
        for i in range(3):
            try:
                launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id=f"e{i}", estimate_usd=1)
            except b.BudgetExhausted:
                pass
        launcher2, _ = self.make(100, lambda *a, **kw: usage_log(kw["model"], ModelUsage(input_tokens=2_500_000, output_tokens=0)), name="ledger2.json")
        launcher2.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="c1", estimate_usd=1)
        l1 = usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1000, output_tokens=0))[0]; l1.samples += usage_log("anthropic/claude-opus-5-5", ModelUsage(input_tokens=1, output_tokens=0))[0].samples
        launcher3, _ = self.make(100, lambda *a, **kw: [l1], name="ledger3.json")
        launcher3.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="s1", estimate_usd=1)
        after = {f: __import__("hashlib").sha256(Path(f).read_bytes()).hexdigest() for f in files}
        self.assertEqual(after, before)
        self.assertEqual(sorted(str(p) for p in Path(host).rglob("*") if p.is_file()), files)

    def test_per_call_usage_outside_the_sample_scope_is_not_used_for_pricing(self):
        _, ledger = self.make(100, None)
        ledger.reserve("u", "sample", 1, {"model": "m"})
        s = ledger.settle("u", {"anthropic/claude-opus-5-5": {"input_tokens": 1_000_000, "output_tokens": 0}}, calls_by_model={"anthropic/claude-opus-5-5": [{"input_tokens": 1000, "output_tokens": 0}]}, scope={"same_sample": False})
        self.assertEqual(s["cost_usd"], "4.000000"); self.assertTrue(any("scope is not confirmed" in f for f in s["flags"])); self.assertEqual(s["usage_reconciliation"], {})

    def test_inspect_recorded_total_cost_is_a_floor(self):
        _, ledger = self.make(100, None)
        ledger.reserve("u", "sample", 1, {"model": "m"})
        calls = [{"input_tokens": 1000, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0, "total_cost": 0.0064}]  # e.g. Inspect priced 1h cache writes it knows about
        s = ledger.settle("u", {"anthropic/claude-opus-5-5": {"input_tokens": 1000, "output_tokens": 0}}, calls_by_model={"anthropic/claude-opus-5-5": calls}, scope={"same_sample": True})
        self.assertEqual(s["cost_usd"], "0.006400"); self.assertEqual(s["inspect_total_cost_usd"], "0.006400"); self.assertTrue(any("Inspect recorded total_cost" in f for f in s["flags"]))


# ------------------------------------------------------------------------------------------ I4
class ConcurrencyTests(_Base):
    def test_delayed_first_creation_is_not_overwritten_by_a_second_process(self):
        """Codex final review (concurrent_create): two processes initialise the same new ledger; the second
        must wait for the first's creation and reservation instead of re-creating an empty ledger."""
        import time
        ctx = multiprocessing.get_context("spawn")
        path = os.path.join(self.root, "race.json")
        ready, release, q = ctx.Event(), ctx.Event(), ctx.Queue()
        p1 = ctx.Process(target=_delayed_first, args=(path, ready, release, q)); p1.start()
        self.assertTrue(ready.wait(20))
        t0 = time.monotonic()
        p2 = ctx.Process(target=_second, args=(path, q, t0)); p2.start()
        time.sleep(0.7)
        second_waited = p2.is_alive()
        release.set(); p1.join(20); p2.join(20)
        self.assertEqual((p1.exitcode, p2.exitcode), (0, 0))
        msgs = {}
        while not q.empty():
            m = q.get(); msgs[m[0]] = m
        self.assertTrue(second_waited, "the second process did not block on the creation lock")
        self.assertEqual(msgs["first"][1], "reserved")
        self.assertIn(msgs["second"][3], ([], ["held"]))  # the second may read before or after the first's reservation, but never a re-created ledger
        snap = b.BudgetLedger(path, 30, PRICES).snapshot()
        self.assertEqual((snap["entries"], snap["open_reservations"], snap["reserved_usd"]), (1, ["held"], "20.000000"))

    def test_concurrent_initialisation_and_reservation_across_processes(self):
        ctx = multiprocessing.get_context("spawn")
        for ceiling, est, n, expect in ((30, 20, 6, 1), (30, 4, 6, 6), (30, 12, 6, 2)):
            with self.subTest(ceiling=ceiling, estimate=est):
                path = os.path.join(self.root, f"concurrent_{ceiling}_{est}.json")
                with ctx.Pool(n) as pool:
                    results = pool.map(_worker, [(path, ceiling, f"u{i}", est) for i in range(n)])
                self.assertEqual(results.count("reserved"), expect, results)
                self.assertTrue(all(r in ("reserved", "exhausted") for r in results), results)
                snap = b.BudgetLedger(path, ceiling, PRICES).snapshot()
                self.assertEqual((snap["entries"], len(snap["open_reservations"])), (expect, expect))
                self.assertLessEqual(Decimal(snap["reserved_usd"]), Decimal(ceiling))
                self.assertEqual(sorted(os.listdir(self.root)), sorted(f for f in os.listdir(self.root) if not f.endswith(".tmp")))  # no leftover temp files

    def test_concurrent_reservations_on_one_ledger_object_from_threads(self):
        _, ledger = self.make(30, None)
        bar = threading.Barrier(4)

        def reserve(i):
            bar.wait()
            try:
                ledger.reserve(f"t{i}", "sample", 20, {"model": "m"})
                return "reserved"
            except b.BudgetExhausted:
                return "exhausted"
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(reserve, range(4)))
        self.assertEqual(results.count("reserved"), 1, results)
        self.assertEqual(ledger.snapshot()["reserved_usd"], "20.000000")


# ------------------------------------------------------------------------------------------ I6
class RedactionTests(_Base):
    def test_redact_removes_synthetic_credential_like_tokens_in_both_implementations(self):
        spec = importlib.util.spec_from_file_location("list_provider_models", os.path.join(L.ROOT, "scripts", "list_provider_models.py"))
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        for fn in (L.redact, mod.redact):
            for m in MARKERS:
                out = fn(f"Incorrect API key provided: {m}; retry later")
                self.assertNotIn(m.split()[-1], out, (fn.__module__, m)); self.assertIn("<redacted>", out)
            self.assertEqual(fn("/Users/someuser/project/.env not loaded"), "/Users/<user>/project/.env not loaded")
            self.assertEqual(fn("ConnectionError: name resolution failed"), "ConnectionError: name resolution failed")
            self.assertLessEqual(len(fn("x" * 1000)), 300)

    def test_exception_branch_records_carry_no_marker(self):
        marker = MARKERS[0]
        launcher, ledger = self.make(30, lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("synthetic authentication rejection " + marker)))
        with self.assertRaises(RuntimeError):
            launcher.run_sample(task=SimpleNamespace(name="synthetic"), model="anthropic/claude-opus-5-5", unit_id="exception", estimate_usd=1)
        texts = [p.read_text() for p in Path(self.root).rglob("*.json")]
        self.assertTrue(texts)
        self.assertEqual(sum(marker in t for t in texts), 0)
        self.assertTrue(any("RuntimeError" in t and "<redacted>" in t for t in texts))
        self.assertEqual(launcher.engineering_failures, {"RuntimeError": 1})

    def test_returned_error_branch_records_carry_no_marker(self):
        marker = MARKERS[1]
        launcher, ledger = self.make(30, lambda *a, **kw: returned_error_log("AuthenticationError: invalid key " + marker))
        launcher.run_sample(task=SimpleNamespace(name="synthetic"), model="anthropic/claude-opus-5-5", unit_id="returned", estimate_usd=1)
        texts = [p.read_text() for p in Path(self.root).rglob("*.json")]
        self.assertEqual(sum(marker in t for t in texts), 0)
        self.assertEqual(launcher.engineering_failures, {"AuthenticationError": 1})


# ------------------------------------------------------------------------------------------ I7
class PriceTierTests(_Base):
    def test_config_prices_carry_the_documented_tiers(self):
        prices = L.prices_from_config(self.cfg)
        pb = prices["openai/gpt-6.1-sol"]
        # B: the harness requests no extended retention, so the 30m default rate is the matching price for both the ledger and Inspect
        self.assertEqual((pb["input"], pb["output"], pb["cache_read"], pb["cache_write"], pb["cache_write_inspect"], pb["cache_write_extended"]), (2, 10, 0.1, 2.5, 2.5, 5.0))
        lc = pb["long_context"]
        self.assertEqual((lc["threshold_input_tokens"], lc["input"], lc["output"], lc["cache_read"], lc["cache_write"]), (272000, 4, 15, 0.2, 5.0))
        pa = prices["anthropic/claude-opus-5-5"]
        # A: the ledger holds the 1h rate (auto TTL escalation is invisible in usage); Inspect's ModelCost holds the 5m rate and applies the 1h multiplier itself
        self.assertEqual((pa["input"], pa["output"], pa["cache_read"], pa["cache_write"], pa["cache_write_inspect"]), (4, 20, 0.2, 8, 5)); self.assertNotIn("long_context", pa)
        pj = prices["google/gemini-3.1-pro-preview"]
        self.assertEqual((pj["cache_write"], pj["cache_write_inspect"], pj["long_context"]["threshold_input_tokens"], pj["long_context"]["input"], pj["long_context"]["output"], pj["long_context"]["cache_read"]), (2.0, 2.0, 200000, 4.0, 18.0, 0.4))
        mcc = L.model_cost_config(self.cfg)
        self.assertEqual((mcc["openai/gpt-6.1-sol"].input_cache_write, mcc["anthropic/claude-opus-5-5"].input_cache_write, mcc["google/gemini-3.1-pro-preview"].input_cache_write), (2.5, 5.0, 2.0))

    def test_inspect_cost_model_applies_the_1h_multiplier_itself(self):
        """Codex final review I7: check Inspect 0.3.286 compute_model_cost against our ModelCost rates. A
        pre-baked 1h rate would be multiplied again; the default-TTL rate reproduces the documented 1h price."""
        from inspect_ai.model._model import CACHE_WRITE_1H_MULTIPLIER, compute_model_cost
        mcc = L.model_cost_config(self.cfg)
        usage = ModelUsage(input_tokens=0, output_tokens=0, input_tokens_cache_write=1_000_000, input_tokens_cache_read=0)
        a = mcc["anthropic/claude-opus-5-5"]
        self.assertAlmostEqual(compute_model_cost(a, usage, None), 5.0)                      # 5m writes: 5 USD/MTok (1.25x input)
        self.assertAlmostEqual(compute_model_cost(a, usage, "1h"), 8.0)                      # 1h writes: Inspect multiplies by 2.0/1.25
        self.assertAlmostEqual(CACHE_WRITE_1H_MULTIPLIER, 1.6)
        from inspect_ai.model import ModelCost
        prebaked = ModelCost(input=4.0, output=20.0, input_cache_write=8.0, input_cache_read=0.2)
        self.assertAlmostEqual(compute_model_cost(prebaked, usage, "1h"), 12.8)             # the double application the previous config would have caused
        bb = mcc["openai/gpt-6.1-sol"]
        self.assertAlmostEqual(compute_model_cost(bb, usage, None), 2.5); self.assertAlmostEqual(compute_model_cost(bb, usage, "1h"), 4.0)  # Inspect's multiplier is TTL-driven; OpenAI never reports a TTL
        # Inspect has no long-context tier: a 300k-token B prompt is priced at the standard rate by the safety net, at the long tier by the ledger
        big = ModelUsage(input_tokens=300_000, output_tokens=0)
        self.assertAlmostEqual(compute_model_cost(bb, big, None), 0.6)
        self.assertEqual(str(b.usage_cost({"input_tokens": 300_000}, L.prices_from_config(self.cfg)["openai/gpt-6.1-sol"])["total"]), "1.200000")

    def test_per_call_tiering_aggregated_flag_and_settlement(self):
        price = L.prices_from_config(self.cfg)["openai/gpt-6.1-sol"]
        small = {"input_tokens": 100_000, "output_tokens": 10_000, "cache_read_tokens": 0, "cache_write_tokens": 0}   # 0.20 + 0.10
        big = {"input_tokens": 300_000, "output_tokens": 10_000, "cache_read_tokens": 0, "cache_write_tokens": 0}     # 1.20 + 0.15 at the long tier
        self.assertEqual((b.usage_cost(small, price)["tier"], str(b.usage_cost(small, price)["total"])), ("standard", "0.300000"))
        self.assertEqual((b.usage_cost(big, price)["tier"], str(b.usage_cost(big, price)["total"])), ("long_context", "1.350000"))
        edge = {"input_tokens": 272_000, "output_tokens": 0}
        self.assertEqual(b.usage_cost(edge, price)["tier"], "standard")  # threshold is exclusive
        self.assertEqual(b.usage_cost({"input_tokens": 200_000, "cache_read_tokens": 72_001, "output_tokens": 0}, price)["tier"], "long_context")  # cache reads count toward the prompt
        pc = b.price_calls([small, big], price)
        self.assertEqual((str(pc["total"]), pc["tiers"], pc["calls"]), ("1.650000", {"standard": 1, "long_context": 1}, 2))
        agg = b.usage_cost({"input_tokens": 400_000, "output_tokens": 20_000}, price, aggregated=True)
        self.assertEqual((agg["tier"], str(agg["total"])), ("long_context", "1.900000")); self.assertTrue(any("aggregated" in f for f in agg["flags"]))
        cw = b.usage_cost({"input_tokens": 0, "output_tokens": 0, "cache_write_tokens": 100_000}, price)  # a 100k-token prompt: standard tier, 30m rate
        self.assertEqual((cw["tier"], str(cw["cache_write"])), ("standard", "0.250000")); self.assertTrue(any("retention" in f for f in cw["flags"]))
        cw_long = b.usage_cost({"input_tokens": 0, "output_tokens": 0, "cache_write_tokens": 1_000_000}, price)  # a 1M-token prompt is long context
        self.assertEqual((cw_long["tier"], str(cw_long["cache_write"])), ("long_context", "5.000000"))
        ledger = b.BudgetLedger(os.path.join(self.root, "tiers.json"), 30, L.prices_from_config(self.cfg))
        ledger.reserve("s", "sample", 3, {"model": "openai/gpt-6.1-sol"})
        total = {"input_tokens": 400_000, "output_tokens": 20_000, "cache_read_tokens": 0, "cache_write_tokens": 0}
        s = ledger.settle("s", {"openai/gpt-6.1-sol": total}, calls_by_model={"openai/gpt-6.1-sol": [small, big]}, scope={"same_sample": True})
        self.assertEqual(s["cost_usd"], "1.650000"); self.assertEqual(s["per_model"]["openai/gpt-6.1-sol"]["tiers"], {"standard": 1, "long_context": 1}); self.assertFalse(s["estimated"])
        self.assertFalse(s["usage_reconciliation"]["openai/gpt-6.1-sol"]["conflict"])
        judge = L.prices_from_config(self.cfg)["google/gemini-3.1-pro-preview"]
        self.assertEqual(str(b.usage_cost({"input_tokens": 250_000, "output_tokens": 1_000}, judge)["total"]), "1.018000")

    def test_per_call_usage_is_read_from_model_events(self):
        u1 = ModelUsage(input_tokens=100, output_tokens=10, input_tokens_cache_read=5, input_tokens_cache_write=2)
        u2 = ModelUsage(input_tokens=300_000, output_tokens=1)
        log = usage_log("openai/gpt-6.1-sol", ModelUsage(input_tokens=300_100, output_tokens=11, input_tokens_cache_read=5, input_tokens_cache_write=2), calls=[u1, u2])
        calls = b.calls_from_eval_sample(log[0].samples[0])
        self.assertEqual(calls, {"openai/gpt-6.1-sol": [{"input_tokens": 100, "output_tokens": 10, "cache_read_tokens": 5, "cache_write_tokens": 2}, {"input_tokens": 300_000, "output_tokens": 1, "cache_read_tokens": 0, "cache_write_tokens": 0}]})
        launcher, ledger = self.make(30, lambda task, **kw: log)
        launcher.ledger.prices = L.prices_from_config(self.cfg)
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=2)
        self.assertEqual(meta["settlement"]["per_model"]["openai/gpt-6.1-sol"]["tiers"], {"standard": 1, "long_context": 1})


# ------------------------------------------------------------------------------------------ Docker image pinned by ID
class SandboxPreflightTests(_Base):
    """Codex final review (docker probes): the daemon answered tag lookups with 'No such image' while the ID
    resolved. The pre-flight pins by full image ID and never queries the tag."""
    GOOD = "sha256:" + "ab" * 32

    def compose(self, image):
        p = os.path.join(self.root, "compose.yaml")
        Path(p).write_text(f"services:\n  default:\n    image: {image}\n    x-local: true\n    pull_policy: never\n")
        return p

    def cfg_with(self, image_id, platform=None, alias=None):
        c = copy.deepcopy(self.cfg); c["sandbox"]["image_id"] = image_id; c["sandbox"]["image"] = alias or image_id
        c["sandbox"]["platform"] = platform if platform is not None else {"os": "linux", "architecture": "arm64"}
        return c

    def test_preflight_parses_yaml_and_checks_platform_and_alias(self):
        """Codex round 3 (preflight_quoted_image / missing_platform / image_alias_mismatch)."""
        seen = []
        ok = SimpleNamespace(returncode=0, stdout=f"{self.GOOD}|arm64|linux|[]\n", stderr="")
        quoted = os.path.join(self.root, "quoted.yaml")
        Path(quoted).write_text(f'services:\n  default:\n    image: "{self.GOOD}"\n    x-local: true\n    pull_policy: never\n')
        rec = L.preflight_sandbox(self.cfg_with(self.GOOD), quoted, runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        self.assertEqual(rec["daemon_id"], self.GOOD)  # a quoted YAML scalar is the same image reference
        with self.assertRaisesRegex(L.LauncherError, "sandbox.platform must carry non-empty"):
            L.preflight_sandbox(self.cfg_with(self.GOOD, platform={}), self.compose(self.GOOD), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "sandbox.platform must carry non-empty"):
            L.preflight_sandbox(self.cfg_with(self.GOOD, platform={"os": "linux", "architecture": ""}), self.compose(self.GOOD), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "sandbox.image .* differs from sandbox.image_id"):
            L.preflight_sandbox(self.cfg_with(self.GOOD, alias="sha256:" + "a" * 64), self.compose(self.GOOD), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "not valid YAML|no string 'image'"):
            bad = os.path.join(self.root, "bad.yaml"); Path(bad).write_text("services: [not: a: mapping\n")
            L.preflight_sandbox(self.cfg_with(self.GOOD), bad, runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        self.assertEqual(len(seen), 1)  # only the accepted case reached the daemon

    def runner(self, answers, seen):
        def run(cmd, **kw):
            seen.append(cmd)
            return next(answers)
        return run

    def test_preflight_pins_by_id_and_never_queries_the_tag(self):
        seen = []
        ok = SimpleNamespace(returncode=0, stdout=f"{self.GOOD}|arm64|linux|[gdpval-sandbox:stage2]\n", stderr="")
        rec = L.preflight_sandbox(self.cfg_with(self.GOOD), self.compose(self.GOOD), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        self.assertEqual((rec["daemon_id"], rec["architecture"], rec["os"]), (self.GOOD, "arm64", "linux"))
        self.assertEqual(seen, [["docker", "image", "inspect", self.GOOD, "--format", "{{.Id}}|{{.Architecture}}|{{.Os}}|{{.RepoTags}}"]])
        self.assertTrue(all("gdpval-sandbox:stage2" not in " ".join(c) for c in seen))

    def test_preflight_fails_closed_on_every_mismatch(self):
        seen = []
        ok = SimpleNamespace(returncode=0, stdout=f"{self.GOOD}|arm64|linux|[]\n", stderr="")
        missing = SimpleNamespace(returncode=1, stdout="", stderr="Error response from daemon: No such image: " + self.GOOD)
        with self.assertRaisesRegex(L.LauncherError, "differs from config.json sandbox.image_id"):
            L.preflight_sandbox(self.cfg_with(self.GOOD), self.compose("gdpval-sandbox:stage2"), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "full local image ID"):
            L.preflight_sandbox(self.cfg_with("gdpval-sandbox:stage2"), self.compose("gdpval-sandbox:stage2"), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "not present in the local Docker image store after 3 attempts"):
            L.preflight_sandbox(self.cfg_with(self.GOOD), self.compose(self.GOOD), runner=self.runner(iter([missing, missing, missing]), seen), sleeper=lambda s: None)
        with self.assertRaisesRegex(L.LauncherError, "architecture 'arm64' differs"):
            L.preflight_sandbox(self.cfg_with(self.GOOD, {"os": "linux", "architecture": "amd64"}), self.compose(self.GOOD), runner=self.runner(iter([ok]), seen), sleeper=lambda s: None)
        other = SimpleNamespace(returncode=0, stdout="sha256:" + "cd" * 32 + "|arm64|linux|[]\n", stderr="")
        with self.assertRaisesRegex(L.LauncherError, "daemon returned image id"):
            L.preflight_sandbox(self.cfg_with(self.GOOD), self.compose(self.GOOD), runner=self.runner(iter([other]), seen), sleeper=lambda s: None)
        self.assertEqual(seen[0], seen[-1])  # same ID query every time; transient misses are retried a bounded number of times
        rec = L.preflight_sandbox(self.cfg_with(self.GOOD), self.compose(self.GOOD), runner=self.runner(iter([missing, ok]), []), sleeper=lambda s: None)
        self.assertEqual(len(rec["attempts"]), 2)

    def test_repository_compose_config_and_converter_agree_on_the_image_id(self):
        from harness.image import compose_image, sandbox_image_ref, IMAGE_ID_RE
        from grading import extract as X
        self.assertTrue(IMAGE_ID_RE.match(sandbox_image_ref())); self.assertEqual(compose_image(), sandbox_image_ref()); self.assertEqual(X.IMAGE, sandbox_image_ref())
        self.assertEqual(self.cfg["sandbox"]["image"], self.cfg["sandbox"]["image_id"])
        import hashlib
        self.assertEqual(self.cfg["sandbox"]["compose_sha256"], hashlib.sha256(Path(L.ROOT, "harness", "compose.yaml").read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
