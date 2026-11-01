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
            self.assertEqual((kw["max_tokens"], kw["attempt_timeout"], kw["token_limit"]), (32000, 900, 20_000_000))  # approved 2026-11-01
            self.assertEqual((kw["reasoning_effort"], kw["reasoning_summary"]), (g["reasoning_effort"], g["reasoning_summary"]))
            self.assertEqual((kw["reasoning_effort"], kw["reasoning_summary"]), ("high", "none"))  # explicit, identical for both candidates
            self.assertEqual((kw["time_limit"], kw["working_limit"], kw["message_limit"]), (g["time_limit_s"], g["working_limit_s"], g["message_limit"]))
            self.assertEqual((kw["max_retries"], kw["timeout"], kw["model_args"]), (r1["max_retries"], r1["timeout_s"], {"max_retries": self.cfg["retries"]["layer_2_provider_sdk"]["max_retries"]}))
            self.assertEqual((kw["retry_on_error"], kw["fail_on_error"], kw["task_retry_attempts"], kw["epochs"]), (0, False, 0, 1))
            self.assertEqual(kw["cost_limit"], float(g["cost_limit_usd"])); self.assertIn(m, kw["model_cost_config"])
            self.assertTrue(kw["sandbox_prebuilt"]); self.assertTrue(kw["log_images"])
            self.assertEqual((kw["max_samples"], kw["max_tasks"], kw["max_sandboxes"], kw["max_connections"]), (c["max_samples"], c["max_tasks"], c["max_sandboxes"], c["max_connections"]))
            # the execution gets its own directory under the launcher's log root (the binding usage recovery relies on)
            self.assertEqual(os.path.dirname(kw["log_dir"]), launcher.log_dir); self.assertTrue(os.path.basename(kw["log_dir"])); self.assertTrue(os.path.isdir(kw["log_dir"]))

    def test_missing_execution_settings_refuse_before_any_ledger_change(self):
        for path in (("generation", "max_tokens_per_request"), ("retries", "layer_1_inspect_model_request", "attempt_timeout_s"), ("generation", "token_limit"),
                     ("generation", "reasoning_effort"), ("generation", "reasoning_summary")):
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
        """B1 (returned error logs): fail_on_error=False returns an error log; each is an engineering failure settled at the
        reservation (no usage). B2-1 approved policy (2026-10-31): a settlement without usage also HOLDS further paid
        starts, so the second start is refused by the hold before the failure-count rule can apply; after a recorded
        reconciliation of the first unit the second start runs, and the third is refused by both the hold and the
        second-occurrence rule. Old expectation: two starts settled, third refused by the failure count only."""
        launcher, ledger = self.make(100, lambda task, **kw: returned_error_log())
        s1 = launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u1", estimate_usd=1)["settlement"]
        self.assertEqual((s1["cost_usd"], s1["estimated"], s1["manual_review_required"]), ("1.000000", True, True))  # no usage -> reservation, estimated, hold
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)
        ledger.resolve_manually("u1", resolution="settled_amount", by="tester", basis="synthetic account check", amount_usd="0.30")
        s2 = launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u2", estimate_usd=1)["settlement"]
        self.assertEqual((s2["cost_usd"], s2["manual_review_required"]), ("1.000000", True))
        self.assertEqual(launcher.engineering_failures, {"ProviderError": 2})
        with self.assertRaisesRegex(b.BudgetExhausted, "occurred 2 times"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u3", estimate_usd=1)
        snap = ledger.snapshot()
        self.assertEqual((snap["settled_usd"], snap["review_pending_units"], snap["resolved_units"]), ("1.300000", ["u2"], ["u1"]))  # u1 adjusted to the verified 0.30

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
class JudgeBatchSettlementTests(_Base):
    """U3: run_judge_batch with a ProviderJudge-style dict result. Incomplete usage is never priced as if complete:
    the settlement is the larger of the priced known part and the reservation, flagged estimated."""

    def test_incomplete_usage_settles_conservatively_and_holds_until_reconciled(self):
        """Approved policy (2026-10-31): incomplete usage -> larger of priced known part and reservation, estimated AND a
        persistent manual hold; the next paid unit is refused until a verified-amount reconciliation; unresolvable keeps
        the hold; complete usage never triggers it; legacy tuple results keep the old behaviour."""
        launcher, ledger = self.make(100, None)
        small = {"usage": {"anthropic/claude-opus-5-5": {"input_tokens": 1000, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}}, "retries": {}, "usage_incomplete": True, "note": "1 call uncertain"}
        r1 = launcher.run_judge_batch(unit_id="j1", estimate_usd=Decimal("0.50"), batch_fn=lambda: small)
        self.assertEqual((r1["settlement"]["cost_usd"], r1["settlement"]["estimated"], r1["settlement"]["manual_review_required"], r1["usage_incomplete"]), ("0.500000", True, True, True))
        self.assertEqual(r1["settlement"]["raw_usage"]["anthropic/claude-opus-5-5"]["input_tokens"], 1000)  # the known usage stays in the settlement
        self.assertTrue(any(f.startswith("hold:") for f in r1["settlement"]["flags"]) and any(f.startswith("incomplete usage: priced known part") for f in r1["settlement"]["flags"]), r1["settlement"]["flags"])
        complete = {**small, "usage_incomplete": False}
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_judge_batch(unit_id="j3", estimate_usd=Decimal("0.50"), batch_fn=lambda: complete)  # hold persists across starts
        ledger2 = b.BudgetLedger(ledger.path, 100, PRICES)  # restart: the hold is ledger state
        self.assertEqual(ledger2.snapshot()["review_pending_units"], ["j1"])
        ledger2.resolve_manually("j1", resolution="unresolvable", by="tester", basis="synthetic: account statement not available")
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_judge_batch(unit_id="j3", estimate_usd=Decimal("0.50"), batch_fn=lambda: complete)  # unresolvable lifts nothing
        ledger2.resolve_manually("j1", resolution="settled_amount", by="tester", basis="synthetic: statement shows 0.41", amount_usd="0.41")
        r3 = launcher.run_judge_batch(unit_id="j3", estimate_usd=Decimal("0.50"), batch_fn=lambda: complete)
        self.assertEqual((r3["settlement"]["cost_usd"], r3["settlement"]["estimated"], r3["settlement"]["manual_review_required"]), ("0.004000", False, False))
        r4 = launcher.run_judge_batch(unit_id="j4", estimate_usd=Decimal("0.50"), batch_fn=lambda: ({}, {}))  # legacy tuple, no usage -> reservation (no hold in the legacy path)
        self.assertEqual((r4["settlement"]["cost_usd"], r4["settlement"]["estimated"]), ("0.500000", True))
        big = {**small, "usage": {"anthropic/claude-opus-5-5": {"input_tokens": 1_000_000, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}}}
        r2 = launcher.run_judge_batch(unit_id="j2", estimate_usd=Decimal("0.50"), batch_fn=lambda: big)
        self.assertEqual((r2["settlement"]["cost_usd"], r2["settlement"]["estimated"], r2["settlement"]["manual_review_required"]), ("4.000000", True, True))  # priced known part wins, still held
        self.assertTrue(r2["post_run"]["stop_recorded"])
        snap = ledger.snapshot()
        self.assertEqual((snap["settled_usd"], snap["resolved_units"], snap["review_pending_units"]), ("4.914000", ["j1"], ["j2"]))  # 0.41 + 0.004 + 0.50 + 4.00
        self.assertEqual([e["type"] for e in self.entries(ledger)], ["reservation", "settlement", "manual_resolution", "manual_resolution", "reservation", "settlement", "reservation", "settlement", "reservation", "settlement", "stop"])

    def test_open_reservation_of_another_unit_blocks_new_paid_starts(self):
        """B2-1: a reservation never settled, voided or resolved (an earlier process died) refuses every new paid unit
        before any call; a void or a verified-amount resolution releases it; the unit's own idempotent reservation is fine."""
        launcher, ledger = self.make(100, lambda task, **kw: usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=0)))
        ledger.reserve("stale-unit", "sample", 2, {"model": "m", "task": "t"})  # left open by a crashed process
        with self.assertRaisesRegex(b.BudgetExhausted, "open reservation"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u1", estimate_usd=1)
        with self.assertRaisesRegex(b.BudgetExhausted, "open reservation"):
            launcher.run_judge_batch(unit_id="j1", estimate_usd=Decimal("0.2"), batch_fn=lambda: ({}, {}))
        self.assertEqual([e["type"] for e in self.entries(ledger)], ["reservation"])  # nothing else happened
        ledger.resolve_manually("stale-unit", resolution="settled_amount", by="tester", basis="synthetic: provider statement 0.00", amount_usd="0")
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model="anthropic/claude-opus-5-5", unit_id="u1", estimate_usd=1)
        self.assertEqual(meta["settlement"]["cost_usd"], "0.004000")
        self.assertTrue(meta["ledger_binding"]["written"]); self.assertEqual(meta["ledger_binding"]["ledger_id"], ledger.snapshot()["ledger_id"])
        self.assertTrue(os.path.exists(os.path.join(self.root, "u1", "ledger_binding.json")))  # runs_root/<sample uuid>/ledger_binding.json


class ExecutionClaimAndRecoveryTests(_Base):
    """Codex B2 review counter-examples (logs/b2-review-76gawzsc): check_reserve_race, same_unit_reexecution,
    generation_partial_usage, generation_exception, post_response_failure."""
    M = "anthropic/claude-opus-5-5"

    def test_two_concurrent_executors_on_one_ledger_admit_exactly_one_paid_call(self):
        import threading
        ledger = b.BudgetLedger(os.path.join(self.root, "ledger.json"), 100, PRICES)
        entered, gate = [], threading.Barrier(2)
        def eval_fn(task, **kw):
            entered.append(kw["model"]); return usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=0))
        outcomes = {}
        def worker(uid):
            launcher = L.PilotLauncher(self.cfg, runs_root=os.path.join(self.root, uid), ledger=b.BudgetLedger(ledger.path, 100, PRICES), eval_fn=eval_fn)
            gate.wait()
            try:
                launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id=uid, estimate_usd=1); outcomes[uid] = "ran"
            except (b.BudgetExhausted, b.LedgerConflict) as ex:
                outcomes[uid] = "refused"
        ts = [threading.Thread(target=worker, args=(u,)) for u in ("race-a", "race-b")]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual((sorted(outcomes.values()), len(entered)), (["ran", "refused"], 1), outcomes)
        snap = ledger.snapshot(); self.assertEqual((len(snap["settled_units"]), snap["open_reservations"]), (1, []))

    def test_a_unit_with_an_open_reservation_is_never_re_executed(self):
        entered = []
        launcher, ledger = self.make(100, lambda task, **kw: entered.append(1) or usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=0)))
        ledger.reserve("u1", "sample", 1, {"model": self.M, "task": "t"})  # an earlier executor claimed u1 and died
        with self.assertRaises((b.BudgetExhausted, b.LedgerConflict)):
            launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u1", estimate_usd=1)
        self.assertEqual(entered, []); self.assertEqual([e["type"] for e in self.entries(ledger)], ["reservation"])

    def test_partial_usage_across_model_events_is_estimated_and_held(self):
        log = usage_log(self.M, ModelUsage(input_tokens=1000, output_tokens=100), calls=[ModelUsage(input_tokens=1000, output_tokens=100)])
        log[0].samples[0].events.append(SimpleNamespace(event="model", model=self.M, retries=None, output=SimpleNamespace(usage=None)))  # a second call whose usage was not reported
        launcher, ledger = self.make(100, lambda task, **kw: log)
        s = launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u", estimate_usd=1)["settlement"]
        self.assertEqual((s["cost_usd"], s["estimated"], s["manual_review_required"]), ("1.000000", True, True))  # priced 0.006 < reservation; not 0.006 exact
        self.assertTrue(any("unknown" in f or "incomplete" in f for f in s["flags"]), s["flags"])
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u2", estimate_usd=1)
        # the same two calls with both usages reported settle exactly and hold nothing
        full = usage_log(self.M, ModelUsage(input_tokens=2000, output_tokens=200), calls=[ModelUsage(input_tokens=1000, output_tokens=100)] * 2)
        launcher2, ledger2 = self.make(100, lambda task, **kw: full, name="ledger2.json")
        s2 = launcher2.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u", estimate_usd=1)["settlement"]
        self.assertEqual((s2["cost_usd"], s2["estimated"], s2["manual_review_required"]), ("0.012000", False, False))

    def test_eval_exception_settles_conservatively_holds_and_records_the_recovery_limit(self):
        def boom(task, **kw):
            raise RuntimeError("synthetic transport failure")
        launcher, ledger = self.make(100, boom)
        with self.assertRaises(RuntimeError):
            launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u", estimate_usd=1)
        s = ledger.effective_settlement("u")["effective"]
        self.assertEqual((s["cost_usd"], s["estimated"], s["manual_review_required"]), ("1.000000", True, True))
        rec = next(v for k, v in self.records(launcher).items() if "_sample_error_" in k)
        self.assertIn("usage_recovery", rec); self.assertIn("recovered", json.loads(rec)["usage_recovery"]) if isinstance(rec, str) else None
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model=self.M, unit_id="u2", estimate_usd=1)

    def test_judge_failure_after_known_usage_keeps_the_known_cost_and_stops(self):
        launcher, ledger = self.make(100, None)
        known = {self.M: {"input_tokens": 1_000_000, "output_tokens": 150_000, "cache_read_tokens": 0, "cache_write_tokens": 0}}  # 4 + 3 = 7 USD known
        def batch_fn():
            raise OSError("synthetic review-material write failure")
        with self.assertRaises(OSError):
            launcher.run_judge_batch(unit_id="j", estimate_usd=Decimal("1"), batch_fn=batch_fn, recover_usage=lambda: {"usage": known, "unknown_calls": 0, "source": "write-ahead log"})
        s = ledger.effective_settlement("j")["effective"]
        self.assertEqual((s["cost_usd"], s["estimated"], s["manual_review_required"]), ("7.000000", True, True))  # never the 1 USD reservation
        self.assertTrue(any("exceeds 2x" in r for r in ledger.stop_reasons()))
        self.assertEqual([e["type"] for e in self.entries(ledger)], ["reservation", "engineering_failure", "settlement", "stop"])  # one settlement, no duplicate


def write_inspect_log(path, *, eval_id, run_id, task, model, sample_uuid, input_tokens, status="success"):
    """A real Inspect EvalLog file (read back by read_eval_log), standing in for what Inspect writes under log_dir."""
    from inspect_ai.log import EvalConfig, EvalDataset, EvalLog, EvalSample, EvalSpec, write_eval_log
    spec = EvalSpec(task=task, task_id=f"T-{eval_id}", run_id=run_id, created="2026-10-31T00:00:00+00:00", dataset=EvalDataset(), model=model, config=EvalConfig(), eval_id=eval_id)
    sample = EvalSample(id="1137e2bb-bdf9-4876-b572-f29b7de5e595", epoch=1, input="x", target="", uuid=sample_uuid, model_usage={model: ModelUsage(input_tokens=input_tokens, output_tokens=0)})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_eval_log(EvalLog(eval=spec, samples=[sample], status=status), path)


class ExecutionBoundRecoveryTests(_Base):
    """Codex closure review (logs/b2-closure-review-tf6xtnn5, foreign_recovery): usage recovered after an eval exception
    must belong to THIS execution and count each billable event once. The binding is the per-unit log directory the
    launcher hands to eval(); logs anywhere else, or logs whose eval identity does not match, never contribute."""
    M = "anthropic/claude-opus-5-5"  # priced in the config (the cost-limit check refuses an unpriced model before eval) and in PRICES: 4 USD per 1M input tokens
    PRICED = PRICES

    def make_priced(self, eval_fn):
        ledger = b.BudgetLedger(os.path.join(self.root, "ledger.json"), 100, self.PRICED)
        return L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger, eval_fn=eval_fn), ledger

    def test_only_this_executions_log_counts_and_only_once(self):
        seen = {}
        def eval_fn(task, **kw):
            seen["log_dir"] = kw["log_dir"]
            # Inspect wrote this execution's log (twice: a duplicate representation) ...
            write_inspect_log(os.path.join(kw["log_dir"], "own.eval"), eval_id="EID-own", run_id="RID-own", task=task.name, model=kw["model"], sample_uuid="SU-own", input_tokens=1_000_000)
            write_inspect_log(os.path.join(kw["log_dir"], "own-copy.json"), eval_id="EID-own", run_id="RID-own", task=task.name, model=kw["model"], sample_uuid="SU-own", input_tokens=1_000_000)
            raise RuntimeError("synthetic failure after the log was written")
        launcher, ledger = self.make_priced(eval_fn)
        # ... while another run's $28 of usage sits next to it in two representations (same task, model, fresh mtime)
        for name in ("foreign-a.eval", "foreign-b.json"):
            write_inspect_log(os.path.join(launcher.log_dir, name), eval_id="EID-other", run_id="RID-other", task="pilot_1137e2bb", model=self.M, sample_uuid="SU-other", input_tokens=7_000_000)
        with self.assertRaises(RuntimeError):
            launcher.run_sample(task=SimpleNamespace(name="pilot_1137e2bb"), model=self.M, unit_id="CURRENT-UNIT", estimate_usd=1)
        s = ledger.effective_settlement("CURRENT-UNIT")["effective"]
        self.assertEqual((s["cost_usd"], s["estimated"], s["manual_review_required"]), ("4.000000", True, True))  # 1M tokens x 4 USD once; never 8 (duplicate) nor 32/60 (foreign)
        self.assertEqual(s["raw_usage"][self.M]["input_tokens"], 1_000_000)
        self.assertNotEqual(seen["log_dir"], launcher.log_dir)  # the execution got its own directory under the launcher's log root
        rec = json.loads(next(v for k, v in self.records(launcher).items() if "_sample_error_" in k))
        r = rec["usage_recovery"]
        self.assertEqual((r["recovered"], r["counted_events"], r["duplicate_events_skipped"], r["attribution_uncertain"]), (True, 1, 1, False))
        self.assertTrue(all(l["log"] in ("own.eval", "own-copy.json") for l in r["logs"]))  # foreign files were never considered

    def test_unattributable_log_in_the_unit_directory_is_uncertain_not_counted(self):
        def eval_fn(task, **kw):
            write_inspect_log(os.path.join(kw["log_dir"], "mine.eval"), eval_id="EID-1", run_id="RID-1", task=task.name, model=kw["model"], sample_uuid="SU-1", input_tokens=500_000)
            write_inspect_log(os.path.join(kw["log_dir"], "stray.eval"), eval_id="EID-2", run_id="RID-2", task="some_other_task", model=kw["model"], sample_uuid="SU-2", input_tokens=7_000_000)
            raise RuntimeError("synthetic failure")
        launcher, ledger = self.make_priced(eval_fn)
        with self.assertRaises(RuntimeError):
            launcher.run_sample(task=SimpleNamespace(name="pilot_1137e2bb"), model=self.M, unit_id="u", estimate_usd=1)
        s = ledger.effective_settlement("u")["effective"]
        self.assertEqual((s["cost_usd"], s["estimated"], s["manual_review_required"]), ("2.000000", True, True))  # the attributable 0.5M tokens (2 USD) are kept; the stray log is not
        r = json.loads(next(v for k, v in self.records(launcher).items() if "_sample_error_" in k))["usage_recovery"]
        self.assertTrue(r["attribution_uncertain"]); self.assertEqual([l["log"] for l in r["logs"] if l.get("excluded")], ["stray.eval"])
        self.assertTrue(ledger.snapshot()["review_pending_units"] == ["u"])


class RealRunCliTests(_Base):
    """Pilot A wiring U1: the CLI's --real-run path through main() with an injected eval_fn, an isolated environment
    dict, a temporary env file with a synthetic key and a fake docker runner. No provider is ever contacted."""
    TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
    MODEL = "anthropic/claude-opus-5-5"

    def setUp(self):
        super().setUp()
        # run classes (2026-11-01): the CLI runs the formal task set with the candidates only under the 'formal' class; the
        # repository config keeps the formal ceiling as a PLACEHOLDER until freeze, so these tests use a config copy with a
        # numeric formal ceiling and labelled paths (<root>/formal/runs, <root>/formal/ledger.json)
        self.runs = os.path.join(self.root, "formal", "runs"); os.makedirs(self.runs)
        self.ledger_path = os.path.join(self.root, "formal", "ledger.json")
        self.env_file = os.path.join(self.root, "env.test")
        Path(self.env_file).write_text("ANTHROPIC_API_KEY=dummy-test-key-not-real-0003\n")
        self.image_id = self.cfg["sandbox"]["image_id"]
        self.docker = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=f"{self.image_id}|arm64|linux|[]\n", stderr="")
        self.cfg_path = self.config_with(formal_ceiling=30)

    def config_with(self, *, formal_ceiling=30, extra_models=(), name="config.json"):
        c = cfg(); c["batches"]["formal"]["budget_ceiling_usd"] = formal_ceiling
        c["batches"]["formal"]["models"] = list(c["batches"]["formal"]["models"]) + list(extra_models)
        path = os.path.join(self.root, name); json.dump(c, open(path, "w"), indent=2); return path

    def argv(self, *extra, model=None, estimate="5", config=None, run_label="formal"):
        return ["--config", config or self.cfg_path, "--run-label", run_label, "--runs-root", self.runs, "--ledger", self.ledger_path, "--task-id", self.TASK,
                "--model", model or self.MODEL, "--estimate-usd", estimate, "--env-file", self.env_file, *extra]

    def real(self, *extra, config=None, model=None, estimate="5"):
        return self.argv("--real-run", "--confirm", f"{self.TASK}|{model or self.MODEL}|{estimate}", "--authorized-by", "test-operator", "--authorization-ref", "unit-test", *extra, config=config, model=model, estimate=estimate)

    def test_mode_must_be_explicit_and_real_run_needs_scope_and_metadata(self):
        with self.assertRaises(SystemExit):  # neither --dry-run nor --real-run
            L.main(self.argv(), eval_fn=lambda *a, **k: self.fail("eval called"), environ={}, docker_runner=self.docker)
        for extra, msg in ((["--real-run"], "--confirm"), (["--real-run", "--confirm", f"{self.TASK}|{self.MODEL}|4"], "does not restate"),
                           (["--real-run", "--confirm", f"{self.TASK}|{self.MODEL}|5"], "--authorized-by")):
            with self.assertRaisesRegex(L.LauncherError, msg):
                L.main(self.argv(*extra), eval_fn=lambda *a, **k: self.fail("eval called"), environ={}, docker_runner=self.docker)
        with self.assertRaisesRegex(L.LauncherError, "INSPECT_DISABLE_MODEL_API"):
            L.main(self.real(), eval_fn=lambda *a, **k: self.fail("eval called"), environ={"INSPECT_DISABLE_MODEL_API": "1"}, docker_runner=self.docker)
        with self.assertRaisesRegex(L.LauncherError, "missing credential"):
            L.main(self.real("--env-file", os.path.join(self.root, "absent.env")), eval_fn=lambda *a, **k: self.fail("eval called"), environ={}, docker_runner=self.docker)
        self.assertEqual(os.listdir(self.runs), [])  # nothing created before the refusals

    def test_prompt_hash_mismatch_refuses_before_any_call(self):
        cfg = json.loads(Path(self.cfg_path).read_text()); cfg["generation"]["system_prompt_sha256"] = "0" * 64  # the formal-class copy, with the prompt hash broken
        bad = os.path.join(self.root, "config_bad_prompt.json"); Path(bad).write_text(json.dumps(cfg))
        calls = []
        with self.assertRaisesRegex(L.LauncherError, "system prompt file"):
            L.main(self.real(config=bad), eval_fn=lambda *a, **k: calls.append(1), environ={}, docker_runner=self.docker)
        self.assertEqual(calls, []); self.assertFalse(os.path.exists(self.ledger_path) and json.loads(Path(self.ledger_path).read_text())["entries"])
        self.assertEqual(L.verify_system_prompt(self.cfg)["matched_form"], "stripped_text")

    def test_real_run_path_calls_the_injected_eval_once_with_the_built_task_and_records_provenance(self):
        seen = []
        def fake_eval(task, **kw):
            seen.append((task, kw)); return usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=200))
        env = {}
        rc = L.main(self.real(), eval_fn=fake_eval, environ=env, docker_runner=self.docker)
        self.assertEqual(rc, 0); self.assertEqual(len(seen), 1)
        task, kw = seen[0]
        self.assertEqual((task.name, kw["model"], kw["max_tokens"], kw["token_limit"], kw["time_limit"], kw["retry_on_error"], kw["fail_on_error"], kw["task_retry_attempts"]),
                         ("formal_1137e2bb", self.MODEL, self.cfg["generation"]["max_tokens_per_request"], self.cfg["generation"]["token_limit"], self.cfg["generation"]["time_limit_s"], 0, False, 0))
        self.assertEqual(os.path.dirname(kw["log_dir"]), os.path.join(self.runs, "inspect_logs")); self.assertTrue(os.path.isdir(kw["log_dir"]))  # per-execution log directory
        self.assertEqual(task.name, "formal_1137e2bb")
        self.assertEqual(env.get("ANTHROPIC_API_KEY"), "dummy-test-key-not-real-0003")
        records = {f: json.loads(Path(self.runs, "launcher_records", f).read_text()) for f in os.listdir(os.path.join(self.runs, "launcher_records"))}
        prov = next(v for k, v in records.items() if "_real_run_provenance_" in k)
        self.assertEqual((prov["task_id"], prov["model"], prov["sample_ids"], prov["prompt"]["matched_form"], prov["image_id"], prov["authorization"]["by"], prov["authorization"]["ref"]),
                         (self.TASK, self.MODEL, [self.TASK], "stripped_text", self.image_id, "test-operator", "unit-test"))
        self.assertTrue(prov["config_sha256"] and prov["code"]["commit"] and prov["staging_verified"]); self.assertIn("not verify", prov["authorization"]["note"])
        sample = next(v for k, v in records.items() if "_sample_" in k and "_sample_error_" not in k and "_sample_cardinality_" not in k)
        self.assertEqual((sample["settlement"]["cost_usd"], sample["settlement"]["estimated"]), ("0.008000", False))  # 1000 x 4 + 200 x 20 per MTok
        ledger = json.loads(Path(self.ledger_path).read_text())
        self.assertEqual([e["type"] for e in ledger["entries"]], ["reservation", "settlement"])
        for f in Path(self.runs).rglob("*"):
            if f.is_file():
                self.assertNotIn("dummy-test-key-not-real-0003", f.read_text(errors="replace"), f)
        self.assertNotIn("dummy-test-key-not-real-0003", Path(self.ledger_path).read_text())

    def test_dry_run_shares_the_unit_construction_and_never_calls_eval(self):
        rc = L.main(self.argv("--dry-run"), eval_fn=lambda *a, **k: self.fail("eval called"), environ={"INSPECT_DISABLE_MODEL_API": "1"}, docker_runner=self.docker)
        self.assertEqual(rc, 0)
        ledger = json.loads(Path(self.ledger_path).read_text())
        self.assertEqual([e["type"] for e in ledger["entries"]], ["reservation", "void"])
        self.assertTrue(any("_dry_run_" in f for f in os.listdir(os.path.join(self.runs, "launcher_records"))))


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



class SdkRetryArgsTests(_Base):
    """Dev batch 2026-11-01: the Google SDK client rejects max_retries; the layer-2 policy is provider-aware."""
    def test_google_models_get_no_sdk_retry_argument_and_the_others_keep_it(self):
        self.assertEqual(L.eval_kwargs(self.cfg, log_dir="/x", model="google/gemini-3.8-flash")["model_args"], {})
        self.assertEqual(L.eval_kwargs(self.cfg, log_dir="/x", model="anthropic/claude-opus-5-5")["model_args"], {"max_retries": self.cfg["retries"]["layer_2_provider_sdk"]["max_retries"]})
        self.assertEqual(L.eval_kwargs(self.cfg, log_dir="/x", model="openai/gpt-6.1-sol")["model_args"], {"max_retries": 0})
        self.assertEqual(L.sdk_model_args("mockllm/model", {"max_retries": 0}), {"max_retries": 0})


class RunClassTests(_Base):
    """Run classes (2026-11-01): per-batch controls from config.batches, labelled roots and ledgers that are never mixed,
    the model and task set of a class, the per-class cost limit, the append-only run inventory and the artifact manifest."""
    TASK, MODEL = RealRunCliTests.TASK, RealRunCliTests.MODEL
    DEV_MODEL = "google/gemini-3.8-flash"
    COMPAT_TASK = "87da214f-fd92-4c58-9854-f4d0d10adce0"
    config_with, argv, real = RealRunCliTests.config_with, RealRunCliTests.argv, RealRunCliTests.real

    def setUp(self):
        super().setUp()
        self.runs = os.path.join(self.root, "formal", "runs"); os.makedirs(self.runs)
        self.ledger_path = os.path.join(self.root, "formal", "ledger.json")
        self.env_file = os.path.join(self.root, "env.test")
        Path(self.env_file).write_text("ANTHROPIC_API_KEY=dummy-test-key-not-real-0003\n")
        self.image_id = self.cfg["sandbox"]["image_id"]
        self.docker = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=f"{self.image_id}|arm64|linux|[]\n", stderr="")
        self.cfg_path = self.config_with(formal_ceiling=30)

    def test_batch_controls_fail_closed_on_unknown_label_or_placeholder_ceiling(self):
        c = cfg()
        with self.assertRaisesRegex(L.LauncherError, "run label"):
            L.batch_controls(c, "pilot")
        with self.assertRaisesRegex(L.LauncherError, "not a number"):
            L.batch_controls(c, "formal")  # PLACEHOLDER until freeze-v1
        dev = L.batch_controls(c, "dev")
        self.assertEqual((dev["budget_ceiling_usd"], dev["models"], dev["task_manifest"], dev["cost_limit_usd"]), (Decimal("100"), [self.DEV_MODEL], "data/selected_tasks.json", 10.0))
        compat = L.batch_controls(c, "compat")
        self.assertEqual((compat["task_manifest"], sorted(compat["models"]), compat["cost_limit_usd"]), ("data/compat_tasks.json", ["anthropic/claude-opus-5-5", "openai/gpt-6.1-sol"], None))

    def test_run_class_paths_must_carry_the_label_and_never_another_class(self):
        L.check_run_class_paths("dev", os.path.join(self.root, "dev", "runs"), os.path.join(self.root, "dev", "ledger.json"))
        with self.assertRaisesRegex(L.LauncherError, "does not lie under"):
            L.check_run_class_paths("dev", os.path.join(self.root, "runs"), os.path.join(self.root, "dev", "ledger.json"))
        with self.assertRaisesRegex(L.LauncherError, "refusing to mix"):
            L.check_run_class_paths("dev", os.path.join(self.root, "dev", "runs"), os.path.join(self.root, "validation", "ledger.json"))
        with self.assertRaisesRegex(L.LauncherError, "run classes"):
            L.main(self.argv("--dry-run", run_label="dev", config=CONFIG, model=self.DEV_MODEL), docker_runner=self.docker)  # formal paths with the dev label

    def test_dev_dry_run_uses_the_dev_controls_and_writes_the_inventory(self):
        runs = os.path.join(self.root, "dev", "runs"); ledger = os.path.join(self.root, "dev", "ledger.json")
        argv = ["--config", CONFIG, "--run-label", "dev", "--runs-root", runs, "--ledger", ledger, "--task-id", self.TASK, "--model", self.DEV_MODEL, "--estimate-usd", "1.00", "--env-file", self.env_file, "--dry-run"]
        self.assertEqual(L.main(argv, docker_runner=self.docker), 0)
        state = json.loads(Path(ledger).read_text())
        self.assertEqual((state["label"], state["ceiling_usd"]), ("dev", "100.000000"))
        rec = next(json.loads(Path(runs, "launcher_records", f).read_text()) for f in os.listdir(os.path.join(runs, "launcher_records")) if "_dry_run_" in f)
        self.assertEqual((rec["run_label"], rec["task_id"], rec["eval_kwargs"]["cost_limit"], rec["eval_kwargs"]["reasoning_effort"]), ("dev", self.TASK, 10.0, "high"))
        self.assertIn("input=0.75", str(rec["eval_kwargs"]["model_cost_config"][self.DEV_MODEL]))  # ModelCost serialised into the record
        inv = [json.loads(l) for l in Path(runs, "run_inventory.jsonl").read_text().splitlines()]
        self.assertEqual([(i["kind"], i["run_label"], i["task_id"], i["model"], i["dry_run"]) for i in inv], [("dry_run", "dev", self.TASK, self.DEV_MODEL, True)])
        self.assertTrue(inv[0]["config_sha256"] and inv[0]["code_commit"])
        with self.assertRaisesRegex(b.LedgerConflict, "label"):  # the dev ledger cannot be reused by another class
            b.BudgetLedger(ledger, 100, PRICES, label="validation")

    def test_model_and_task_set_are_bound_to_the_class(self):
        with self.assertRaisesRegex(L.LauncherError, "not allowed in run class 'dev'"):
            L.main(["--config", CONFIG, "--run-label", "dev", "--runs-root", os.path.join(self.root, "dev", "runs"), "--ledger", os.path.join(self.root, "dev", "ledger.json"), "--task-id", self.TASK,
                    "--model", self.MODEL, "--estimate-usd", "1", "--env-file", self.env_file, "--dry-run"], docker_runner=self.docker)
        with self.assertRaisesRegex(L.LauncherError, "not in the 'compat' task set"):
            L.main(["--config", CONFIG, "--run-label", "compat", "--runs-root", os.path.join(self.root, "compat", "runs"), "--ledger", os.path.join(self.root, "compat", "ledger.json"), "--task-id", self.TASK,
                    "--model", self.MODEL, "--estimate-usd", "8", "--env-file", self.env_file, "--dry-run"], docker_runner=self.docker)
        runs = os.path.join(self.root, "compat", "runs")
        rc = L.main(["--config", CONFIG, "--run-label", "compat", "--runs-root", runs, "--ledger", os.path.join(self.root, "compat", "ledger.json"), "--task-id", self.COMPAT_TASK,
                     "--model", self.MODEL, "--estimate-usd", "8", "--env-file", self.env_file, "--dry-run"], docker_runner=self.docker)
        self.assertEqual(rc, 0)
        rec = next(json.loads(Path(runs, "launcher_records", f).read_text()) for f in os.listdir(os.path.join(runs, "launcher_records")) if "_dry_run_" in f)
        self.assertEqual((rec["task_id"], rec["run_label"], rec["eval_kwargs"]["cost_limit"]), (self.COMPAT_TASK, "compat", 20.0))  # compat keeps the generation cost limit
        self.assertEqual(json.loads(Path(self.root, "compat", "ledger.json").read_text())["ceiling_usd"], "45.000000")

    def test_real_run_records_inventory_binding_and_artifact_manifest(self):
        def fake_eval(task, **kw):
            return usage_log(kw["model"], ModelUsage(input_tokens=1000, output_tokens=200))
        rc = L.main(self.real(), eval_fn=fake_eval, environ={}, docker_runner=self.docker)
        self.assertEqual(rc, 0)
        inv = [json.loads(l) for l in Path(self.runs, "run_inventory.jsonl").read_text().splitlines()]
        self.assertEqual(len(inv), 1); i = inv[0]
        self.assertEqual((i["kind"], i["run_label"], i["task_id"], i["model"], i["dry_run"], i["inspect_status"]), ("sample", "formal", self.TASK, self.MODEL, False, "success"))
        self.assertTrue(i["run_uuid"] and i["settlement_cost_usd"] and i["artifact_manifest"]["path"] and i["artifact_manifest"]["sha256"])
        self.assertEqual(len(i["code_loaded_commit"] or ""), 40); self.assertEqual(len(i["harness_source_sha256"] or ""), 64)  # the code the process runs, captured at import
        self.assertEqual(i["harness_source_sha256"], L.code_loaded()["harness_source"]["sha256"])
        man = json.loads(Path(i["artifact_manifest"]["path"]).read_text())
        self.assertEqual((man["run_uuid"], man["run_label"], man["files"], man["file_count"]), (i["run_uuid"], "formal", [], 0))  # the synthetic log collected nothing: an empty, hashed manifest
        run_json = json.loads(Path(self.runs, i["run_uuid"], "ledger_binding.json").read_text())
        self.assertEqual(run_json["run_uuid"], i["run_uuid"])
        launcher = L.PilotLauncher(self.cfg, runs_root=self.runs, ledger=b.BudgetLedger.open_existing(self.ledger_path, PRICES), eval_fn=None, run_label="formal")
        again = launcher.write_artifact_manifest(i["run_uuid"])
        self.assertEqual((again["written"], again["consistent_with_existing"]), (False, True))  # written once, verified afterwards


class CodeLoadedTests(_Base):
    """A long batch process keeps running the modules it imported: the fingerprint is captured once and never refreshed."""
    def test_code_loaded_is_captured_once_and_fingerprints_the_harness_sources(self):
        first = L.code_loaded()
        self.assertIs(L.code_loaded(), first)
        fp = L.harness_source_fingerprint()
        self.assertEqual(first["harness_source"], fp)  # the tree has not changed during this test
        self.assertGreater(fp["files"], 5)

