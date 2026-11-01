"""Mock verification of the budget ledger and the launcher's budget protection (no model, no
Docker, no network). Covers the six required checks: (1) no start without budget cover, (2)
settlement from simulated usage with retries counted, (3) ceiling reached stops further samples
without per-request interception, (4) restart recovers the persisted ledger and keeps the stop
condition, (5) failure, interruption and duplicate settlement neither release twice nor
double-charge, (6) reservation atomicity under concurrency is NOT claimed here (formal-run gate).
Run: python -m unittest harness.tests.test_budget_unit -v"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace

from inspect_ai.model import ModelUsage

from harness import budget as b
from harness import launcher as L

PRICES = {"anthropic/claude-opus-5-5": {"input": 4, "output": 20, "cache_read": 0.20, "cache_write": 5},
          "openai/gpt-6.1-sol": {"input": 2, "output": 10, "cache_read": 0.10, "cache_write": 2}}


def fake_log(model, usage: ModelUsage, retries: int = 0, status="success"):
    ev = SimpleNamespace(event="model", model=model, retries=retries or None, output=SimpleNamespace(usage=usage))
    sample = SimpleNamespace(model_usage={model: usage}, events=[ev], uuid="u1")
    return [SimpleNamespace(status=status, samples=[sample], location="/dev/null/log.eval")]


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="budget_unit_")
        self.path = os.path.join(os.path.realpath(self.tmp.name), "ledger.json")

    def tearDown(self):
        self.tmp.cleanup()

    def ledger(self, ceiling=25):
        return b.BudgetLedger(self.path, ceiling, PRICES)

    # (1) no start without cover ----------------------------------------------------------
    def test_reserve_refused_when_remaining_cannot_cover(self):
        lg = self.ledger(ceiling=5)
        lg.reserve("s1", "sample", 3)
        self.assertFalse(lg.can_start(3))
        with self.assertRaises(b.BudgetExhausted):
            lg.reserve("s2", "sample", 3)
        self.assertEqual(lg.snapshot()["open_reservations"], ["s1"])
        self.assertTrue(lg.can_start(2))

    def test_judge_batch_reservation_also_gated(self):
        lg = self.ledger(ceiling=4)
        lg.reserve("s1", "sample", 3.5)
        with self.assertRaises(b.BudgetExhausted):
            lg.reserve("j1", "judge", 1)

    # (2) settlement from simulated usage, retries included ---------------------------------
    def test_settlement_by_category_and_retry_estimate(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 5)
        usage = {"anthropic/claude-opus-5-5": {"input_tokens": 1_000_000, "output_tokens": 100_000, "cache_read_tokens": 2_000_000, "cache_write_tokens": 500_000}}
        s = lg.settle("s1", usage, retries_by_model={"anthropic/claude-opus-5-5": 2})
        # input 4.00 + output 2.00 + cache_read 0.40 + cache_write 2.50 = 8.90; retries 2 x input 4.00 = 8.00 (estimate)
        self.assertEqual(s["breakdown"], {"input": "4.000000", "output": "2.000000", "cache_read": "0.400000", "cache_write": "2.500000"})
        self.assertEqual(s["retry_estimate_usd"], "8.000000")
        self.assertEqual(s["cost_usd"], "16.900000")
        self.assertTrue(s["estimated"])
        snap = lg.snapshot()
        self.assertEqual(snap["settled_usd"], "16.900000")
        self.assertEqual(snap["reserved_usd"], "0.000000")
        self.assertEqual(snap["remaining_usd"], "8.100000")
        self.assertEqual(snap["by_category_usd"]["retry_estimate"], "8.000000")

    def test_unknown_price_settles_conservatively_and_flags(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        s = lg.settle("s1", {"openai/unknown-model": {"input_tokens": 10}}, fallback_to_reservation=True)
        self.assertEqual(s["cost_usd"], "3.000000")
        self.assertTrue(s["estimated"])
        self.assertTrue(any("estimated_unknown_cost" in f for f in s["flags"]))
        self.assertTrue(s["manual_review_required"])
        self.assertEqual(s["raw_usage"], {"openai/unknown-model": {"input_tokens": 10}})

    def test_no_usage_without_fallback_is_refused(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        with self.assertRaises(b.LedgerConflict):
            lg.settle("s1", {})

    # (3) ceiling reached stops further samples ----------------------------------------------
    def test_ceiling_reached_blocks_next_sample(self):
        lg = self.ledger(ceiling=10)
        lg.reserve("s1", "sample", 4)
        lg.settle("s1", {"openai/gpt-6.1-sol": {"input_tokens": 5_000_000, "output_tokens": 100_000}})  # 10 + 1 = 11 > ceiling
        self.assertEqual(lg.snapshot()["remaining_usd"], "-1.000000")
        self.assertTrue(any("ceiling reached" in r for r in lg.stop_reasons()))
        with self.assertRaises(b.BudgetExhausted):
            lg.reserve("s2", "sample", 0.01)

    def test_stop_reasons_two_x_estimate_and_repeated_failure_class(self):
        lg = self.ledger()
        r = lg.stop_reasons(per_task_costs={"1137e2bb": 7}, per_task_estimate_usd=3, engineering_failures={"TimeoutError": 2, "ValueError": 1})
        self.assertTrue(any("exceeds 2x" in x for x in r))
        self.assertTrue(any("TimeoutError" in x for x in r))
        self.assertFalse(any("ValueError" in x for x in r))

    # (4) restart recovery -----------------------------------------------------------------
    def test_restart_recovers_totals_and_open_reservations(self):
        lg = self.ledger(ceiling=10)
        lg.reserve("s1", "sample", 4)
        lg.settle("s1", {"openai/gpt-6.1-sol": {"input_tokens": 1_000_000}})  # 2.00
        lg.reserve("s2", "sample", 5)  # interrupted before settlement
        del lg
        lg2 = b.BudgetLedger(self.path, 10, PRICES)
        snap = lg2.snapshot()
        self.assertEqual((snap["settled_usd"], snap["reserved_usd"], snap["remaining_usd"]), ("2.000000", "5.000000", "3.000000"))
        self.assertEqual(snap["open_reservations"], ["s2"])
        with self.assertRaises(b.BudgetExhausted):
            lg2.reserve("s3", "sample", 3.5)
        # the open reservation is not released by the restart; settling it later works exactly once
        lg2.settle("s2", {}, fallback_to_reservation=True)
        self.assertEqual(lg2.snapshot()["remaining_usd"], "3.000000")

    def test_ceiling_mismatch_on_restart_is_refused(self):
        self.ledger(ceiling=10)
        with self.assertRaises(b.LedgerConflict):
            b.BudgetLedger(self.path, 25, PRICES)

    # (5) failure, interruption, duplicate settlement ------------------------------------------
    def test_duplicate_settlement_does_not_double_charge(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        first = lg.settle("s1", {"openai/gpt-6.1-sol": {"input_tokens": 1_000_000}})
        second = lg.settle("s1", {"openai/gpt-6.1-sol": {"input_tokens": 9_000_000}})
        self.assertEqual(first["cost_usd"], second["cost_usd"])
        self.assertEqual(lg.snapshot()["settled_usd"], "2.000000")
        with self.assertRaises(b.LedgerConflict):
            lg.reserve("s1", "sample", 1)  # settled units cannot be re-reserved

    def test_duplicate_reservation_is_idempotent_not_additive(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        lg.reserve("s1", "sample", 3)
        self.assertEqual(lg.snapshot()["reserved_usd"], "3.000000")
        with self.assertRaises(b.LedgerConflict):
            lg.reserve("s1", "judge", 3)

    def test_void_only_for_unstarted_units(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        lg.void("s1", "never started")
        self.assertEqual(lg.snapshot()["remaining_usd"], "25.000000")
        with self.assertRaises(b.LedgerConflict):
            lg.void("s1", "again")
        with self.assertRaises(b.LedgerConflict):
            lg.reserve("s1", "sample", 1)
        lg.reserve("s2", "sample", 3)
        lg.settle("s2", {}, fallback_to_reservation=True)
        with self.assertRaises(b.LedgerConflict):
            lg.void("s2", "settled units cannot be voided")

    def test_entries_are_append_only_and_totals_derived(self):
        lg = self.ledger()
        lg.reserve("s1", "sample", 3)
        lg.settle("s1", {"openai/gpt-6.1-sol": {"input_tokens": 500_000}})
        state = json.loads(Path(self.path).read_text())
        self.assertEqual([e["type"] for e in state["entries"]], ["reservation", "settlement"])
        self.assertNotIn("settled_total", state)


class LauncherBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="launcher_unit_")
        self.root = os.path.realpath(self.tmp.name)
        with open(os.path.join(L.ROOT, "config.json"), encoding="utf-8") as f:
            self.cfg = json.load(f)

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, ceiling, eval_fn):
        ledger = b.BudgetLedger(os.path.join(self.root, "ledger.json"), ceiling, PRICES)
        return L.PilotLauncher(self.cfg, runs_root=self.root, ledger=ledger, eval_fn=eval_fn), ledger

    def test_sample_flow_reserve_run_settle_with_retries(self):
        model = "anthropic/claude-opus-5-5"
        calls = []
        def fake_eval(task, **kw):
            calls.append(kw)
            return fake_log(model, ModelUsage(input_tokens=200_000, output_tokens=20_000, input_tokens_cache_read=1_000_000, input_tokens_cache_write=50_000), retries=1)
        launcher, ledger = self.make(25, fake_eval)
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model=model, unit_id="u1", estimate_usd=5)
        kw = calls[0]
        self.assertEqual((kw["max_retries"], kw["model_args"], kw["retry_on_error"], kw["fail_on_error"], kw["task_retry_attempts"]), (3, {"max_retries": 0}, 0, False, 0))
        self.assertEqual((kw["time_limit"], kw["working_limit"], kw["message_limit"], kw["epochs"]), (7200, 7200, 200, 1))  # approved 2026-11-01 limits
        self.assertEqual((kw["max_samples"], kw["max_tasks"], kw["max_sandboxes"], kw["max_connections"]), (1, 1, 1, 1))
        # input 0.80 + output 0.40 + cache_read 0.20 + cache_write 0.25 = 1.65; retry estimate 1 x 0.80
        self.assertEqual(meta["settlement"]["cost_usd"], "2.450000")
        self.assertEqual(meta["settlement"]["retry_estimate_usd"], "0.800000")
        self.assertEqual(ledger.snapshot()["open_reservations"], [])
        self.assertTrue(os.path.exists(launcher.record_dir))

    def test_insufficient_budget_never_calls_eval(self):
        called = []
        launcher, ledger = self.make(3, lambda *a, **k: called.append(1))
        with self.assertRaises(b.BudgetExhausted):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=5)
        self.assertEqual(called, [])
        self.assertEqual(ledger.snapshot()["open_reservations"], [])
        self.assertTrue(any("_refused_" in f for f in os.listdir(launcher.record_dir)))

    def test_ceiling_reached_stops_next_sample_not_per_request(self):
        model = "openai/gpt-6.1-sol"
        calls = []
        def fake_eval(task, **kw):
            calls.append(1)
            return fake_log(model, ModelUsage(input_tokens=6_000_000, output_tokens=0))  # 12 USD actual, above the 10 USD ceiling
        launcher, ledger = self.make(10, fake_eval)
        launcher.run_sample(task=SimpleNamespace(name="t"), model=model, unit_id="u1", estimate_usd=4)
        self.assertEqual(ledger.snapshot()["remaining_usd"], "-2.000000")  # the running sample exceeded the ceiling; not a hard cap
        with self.assertRaises(b.BudgetExhausted):
            launcher.run_sample(task=SimpleNamespace(name="t"), model=model, unit_id="u2", estimate_usd=1)
        self.assertEqual(len(calls), 1)

    def test_eval_failure_settles_conservatively_and_counts_failure_class(self):
        def failing_eval(task, **kw):
            raise TimeoutError("synthetic transport failure")
        launcher, ledger = self.make(25, failing_eval)
        with self.assertRaises(TimeoutError):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=4)
        snap = ledger.snapshot()
        self.assertEqual((snap["settled_usd"], snap["reserved_usd"], snap["estimated_portion_usd"]), ("4.000000", "0.000000", "4.000000"))
        self.assertEqual(launcher.engineering_failures, {"TimeoutError": 1})  # persisted in the ledger, not in memory
        self.assertEqual(snap["review_pending_units"], ["u1"])  # B2 remediation: an exception leaves the cost unknown -> persistent hold
        with self.assertRaisesRegex(b.BudgetExhausted, "manual review"):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u2", estimate_usd=4)
        ledger.resolve_manually("u1", resolution="settled_amount", by="tester", basis="synthetic: provider statement shows no charge", amount_usd="0")
        with self.assertRaises(TimeoutError):
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u2", estimate_usd=4)
        with self.assertRaises(b.BudgetExhausted):  # second failure of the same class is a stop condition (and u2 is held)
            launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u3", estimate_usd=4)
        self.assertEqual(launcher.engineering_failures, {"TimeoutError": 2})

    def test_interrupted_unit_stays_reserved_after_restart(self):
        launcher, ledger = self.make(25, lambda *a, **k: None)
        ledger.reserve("u-interrupted", "sample", 6)
        launcher2, ledger2 = L.PilotLauncher(self.cfg, runs_root=self.root, ledger=b.BudgetLedger(os.path.join(self.root, "ledger.json"), 25, PRICES), eval_fn=None), None
        self.assertEqual(launcher2.open_reservations_after_restart(), ["u-interrupted"])
        self.assertEqual(launcher2.ledger.snapshot()["remaining_usd"], "19.000000")

    def test_judge_batch_reserve_and_settle(self):
        launcher, ledger = self.make(25, None)
        out = launcher.run_judge_batch(unit_id="j1", estimate_usd=2, batch_fn=lambda: ({"openai/gpt-6.1-sol": {"input_tokens": 500_000, "output_tokens": 50_000}}, {}))
        self.assertEqual(out["settlement"]["cost_usd"], "1.500000")
        self.assertEqual(out["settlement"]["kind"], "judge")
        self.assertEqual(ledger.snapshot()["by_category_usd"]["judge"], "1.500000")

    def test_dry_run_reserves_then_voids_without_eval(self):
        launcher, ledger = self.make(25, lambda *a, **k: (_ for _ in ()).throw(AssertionError("eval must not be called")))
        meta = launcher.run_sample(task=SimpleNamespace(name="t"), model="openai/gpt-6.1-sol", unit_id="u1", estimate_usd=3, dry_run=True)
        self.assertTrue(meta["dry_run"])
        self.assertEqual(ledger.snapshot()["remaining_usd"], "25.000000")
        self.assertEqual(ledger.snapshot()["voided_units"], ["u1"])


class LauncherPreflightTests(unittest.TestCase):
    def test_env_file_names_only_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, ".env")
            Path(p).write_text("# comment\nANTHROPIC_API_KEY='dummy-not-real-1'\nexport OPENAI_API_KEY=dummy-not-real-2\nBAD LINE\n")
            env = {"OPENAI_API_KEY": "keep-existing"}
            names = L.load_env_file(p, env)
            self.assertEqual(names, ["ANTHROPIC_API_KEY", "OPENAI_API_KEY"])
            self.assertEqual(env["ANTHROPIC_API_KEY"], "dummy-not-real-1")
            self.assertEqual(env["OPENAI_API_KEY"], "keep-existing")
            self.assertEqual(L.missing_keys(["anthropic", "openai", "google"], env), ["GOOGLE_API_KEY"])
            self.assertEqual(L.load_env_file(os.path.join(d, "absent.env"), {}), [])

    def test_refuse_disabled_model_api(self):
        with self.assertRaises(L.LauncherError):
            L.refuse_disabled_model_api({"INSPECT_DISABLE_MODEL_API": "1"})
        L.refuse_disabled_model_api({})

    def test_runs_root_must_be_real_path(self):
        with tempfile.TemporaryDirectory() as d:
            real = os.path.realpath(d)
            link = os.path.join(real, "link")
            os.symlink(real, link)
            self.assertEqual(L.resolve_runs_root(os.path.join(real, "runs")), os.path.join(real, "runs"))
            with self.assertRaises(L.LauncherError):
                L.resolve_runs_root(os.path.join(link, "runs"))
            with self.assertRaises(L.LauncherError):
                L.resolve_runs_root("relative/path")
            with self.assertRaises(L.LauncherError):
                L.resolve_runs_root(os.path.join(real, "a", "..", "b"))
            if os.path.islink("/tmp"):
                with self.assertRaises(L.LauncherError):
                    L.resolve_runs_root("/tmp/gdpval-runs", create=False)

    def test_preflight_image_bounded_retry(self):
        answers = iter([SimpleNamespace(returncode=1, stdout="", stderr="Error: No such image: x"),
                        SimpleNamespace(returncode=0, stdout="sha256:abc\n", stderr="")])
        sleeps = []
        rec = L.preflight_image("gdpval-sandbox:stage2", attempts=3, delay_s=0.5, runner=lambda *a, **k: next(answers), sleeper=sleeps.append)
        self.assertEqual(rec["image_id"], "sha256:abc")
        self.assertEqual(len(rec["attempts"]), 2)
        self.assertEqual(sleeps, [0.5])
        always_missing = lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="No such image")
        with self.assertRaises(L.LauncherError):
            L.preflight_image("gdpval-sandbox:stage2", attempts=3, delay_s=0, runner=always_missing, sleeper=lambda s: None)
        with self.assertRaises(L.LauncherError):
            L.preflight_image("x", attempts=50, runner=always_missing, sleeper=lambda s: None)  # unbounded retries refused

    def test_eval_kwargs_four_retry_layers_from_config(self):
        with open(os.path.join(L.ROOT, "config.json"), encoding="utf-8") as f:
            cfg = json.load(f)
        with self.assertRaisesRegex(L.LauncherError, "model name is required"):
            L.eval_kwargs(cfg, log_dir="/nonexistent/logs")  # cost_limit is set in the DRAFT config: the model is mandatory
        kw = L.eval_kwargs(cfg, log_dir="/nonexistent/logs", model="anthropic/claude-opus-5-5")
        self.assertEqual(kw["max_retries"], 3)
        self.assertEqual(kw["model_args"], {"max_retries": 0})
        self.assertEqual((kw["retry_on_error"], kw["fail_on_error"], kw["task_retry_attempts"]), (0, False, 0))
        self.assertEqual((kw["token_limit"], kw["max_tokens"], kw["attempt_timeout"], kw["timeout"]), (20_000_000, 32000, 900, 2700))  # approved 2026-11-01
        self.assertEqual((kw["cost_limit"], "anthropic/claude-opus-5-5" in kw["model_cost_config"]), (20.0, True))
        self.assertEqual((kw["reasoning_effort"], kw["reasoning_summary"]), ("high", "none"))
        bad = json.loads(json.dumps(cfg)); bad["generation"]["reasoning_effort"] = "maximum"
        with self.assertRaisesRegex(L.LauncherError, "reasoning_effort"):
            L.eval_kwargs(bad, log_dir="/x", model="anthropic/claude-opus-5-5")  # an unknown literal is refused before any call
        self.assertEqual(L.eval_kwargs(cfg, log_dir="/x", token_limit=400_000, model="anthropic/claude-opus-5-5")["token_limit"], 400_000)
        prices = L.prices_from_config(cfg)
        self.assertEqual(prices["anthropic/claude-opus-5-5"]["output"], 20)
        self.assertEqual(prices["openai/gpt-6.1-sol"]["cache_read"], 0.10)


class ManualResolutionTests(unittest.TestCase):
    """B2-1: ledger identity, settle(hold=True), manual_resolution events and their derived effects."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ledger_resolution_")
        self.path = os.path.join(self.tmp.name, "ledger.json")
        self.prices = {"m/x": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 8}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_ledger_id_is_persistent_and_backfilled(self):
        lg = b.BudgetLedger(self.path, 10, self.prices)
        ident = lg.identity()
        self.assertEqual(ident["ledger_path"], os.path.realpath(self.path)); self.assertEqual(len(ident["ledger_id"]), 32)
        self.assertEqual(b.BudgetLedger(self.path, 10, self.prices).identity(), ident)
        state = json.load(open(self.path)); state.pop("ledger_id"); json.dump(state, open(self.path, "w"))  # a ledger written before the identity existed
        new_id = b.BudgetLedger(self.path, 10, self.prices).identity()["ledger_id"]
        self.assertEqual(len(new_id), 32); self.assertEqual(b.BudgetLedger(self.path, 10, self.prices).identity()["ledger_id"], new_id)

    def test_settled_amount_closes_an_open_reservation_and_adjusts_an_estimated_settlement(self):
        lg = b.BudgetLedger(self.path, 10, self.prices)
        lg.reserve("unknown-outcome", "judge", 0.5, {})
        lg.reserve("held", "sample", 1, {"model": "m/x", "task": "t"})
        held = lg.settle("held", {}, fallback_to_reservation=True, hold=True)
        self.assertEqual((held["cost_usd"], held["estimated"], held["manual_review_required"]), ("1.000000", True, True))
        snap = lg.snapshot()
        self.assertEqual((snap["open_reservations"], snap["review_pending_units"], snap["settled_usd"], snap["reserved_usd"]), (["unknown-outcome"], ["held"], "1.000000", "0.500000"))
        self.assertTrue(lg.stop_reasons())
        lg.resolve_manually("unknown-outcome", resolution="settled_amount", by="reviewer", basis="statement line 12", amount_usd="0.12")
        snap = lg.snapshot()
        self.assertEqual((snap["open_reservations"], snap["settled_usd"], snap["reserved_usd"], snap["resolved_units"]), ([], "1.120000", "0.000000", ["unknown-outcome"]))
        self.assertTrue(lg.stop_reasons())  # the held unit still blocks
        lg.resolve_manually("held", resolution="settled_amount", by="reviewer", basis="statement line 13", amount_usd="0.70")
        snap = lg.snapshot()
        self.assertEqual((snap["review_pending_units"], snap["settled_usd"], snap["estimated_portion_usd"]), ([], "0.820000", "0.000000"))  # 0.12 + 0.70; the estimate is replaced, not added
        self.assertEqual(lg.stop_reasons(), [])
        entries = json.load(open(self.path))["entries"]
        self.assertEqual([e["type"] for e in entries], ["reservation", "reservation", "settlement", "manual_resolution", "manual_resolution"])
        self.assertEqual(entries[2]["cost_usd"], "1.000000")  # the original estimated settlement event is untouched
        with self.assertRaises(b.LedgerConflict):
            lg.resolve_manually("held", resolution="settled_amount", by="reviewer", basis="twice", amount_usd="0.70")

    def test_unresolvable_changes_nothing_and_malformed_resolutions_are_refused(self):
        lg = b.BudgetLedger(self.path, 10, self.prices)
        lg.reserve("u", "sample", 1, {"model": "m/x", "task": "t"})
        lg.settle("u", {}, fallback_to_reservation=True, hold=True)
        lg.resolve_manually("u", resolution="unresolvable", by="reviewer", basis="no statement available")
        snap = lg.snapshot()
        self.assertEqual((snap["review_pending_units"], snap["unresolvable_units"], snap["settled_usd"]), (["u"], ["u"], "1.000000"))
        self.assertTrue(any("manual review" in r for r in lg.stop_reasons()))
        with self.assertRaises(b.LedgerConflict):
            lg.resolve_manually("u", resolution="settled_amount", by="reviewer", basis="no amount")
        with self.assertRaises(b.LedgerConflict):
            lg.resolve_manually("nonexistent", resolution="unresolvable", by="reviewer", basis="x")
        state = json.load(open(self.path)); state["entries"].append({"type": "manual_resolution", "unit_id": "u", "resolution": "settled_amount", "by": "x", "basis": "y", "at": "t"})
        json.dump(state, open(self.path, "w"))
        with self.assertRaises(b.LedgerCorrupt):
            b.BudgetLedger(self.path, 10, self.prices).snapshot()  # amount missing -> the whole ledger is refused (schema violation)

    def test_units_for_run_groups_judge_units_and_the_bound_generation_unit(self):
        lg = b.BudgetLedger(self.path, 10, self.prices)
        lg.reserve("task:model:ts", "sample", 1, {"model": "m/x", "task": "t"}); lg.settle("task:model:ts", {"m/x": {"input_tokens": 1000, "output_tokens": 0}})
        lg.reserve("RUN1:judge:a", "judge", 0.2, {}); lg.reserve("RUN1:judge:b", "judge", 0.2, {}); lg.reserve("RUN2:judge:a", "judge", 0.2, {})
        lg.settle("RUN1:judge:a", {}, fallback_to_reservation=True, hold=True)  # a hold blocks NEW reservations, so the others were reserved first
        r = lg.units_for_run("RUN1", "task:model:ts")
        self.assertEqual((r["judge_units"], r["open"], r["review_pending"], sorted(r["units"])), (["RUN1:judge:a", "RUN1:judge:b"], ["RUN1:judge:b"], ["RUN1:judge:a"], ["RUN1:judge:a", "RUN1:judge:b", "task:model:ts"]))


class ClaimAndEffectiveSettlementTests(unittest.TestCase):
    """Codex B2 review (logs/b2-review-76gawzsc): atomic claim, same-unit re-execution, money validation,
    effective settlement after manual resolution, incomplete-usage floor + hold inside the ledger."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ledger_claim_")
        self.path = os.path.join(self.tmp.name, "ledger.json")
        self.prices = {"m/x": {"input": 4, "output": 20, "cache_read": 0.2, "cache_write": 8}}

    def tearDown(self):
        self.tmp.cleanup()

    def test_claim_admits_exactly_one_executor_and_never_reexecutes_an_open_unit(self):
        import threading
        lg = b.BudgetLedger(self.path, 100, self.prices)
        outcomes = {}
        gate = threading.Barrier(2)
        def worker(uid):
            gate.wait()
            try:
                lg.reserve(uid, "sample", 1, {"model": "m/x", "task": "t"}, claim=True); outcomes[uid] = "claimed"
            except b.BudgetExhausted as ex:
                outcomes[uid] = "refused: " + str(ex)[:60]
        ts = [threading.Thread(target=worker, args=(u,)) for u in ("race-a", "race-b")]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(v.split(":")[0] for v in outcomes.values()), ["claimed", "refused"], outcomes)  # exactly one executor
        claimed = next(u for u, v in outcomes.items() if v == "claimed")
        with self.assertRaisesRegex(b.LedgerConflict, "open reservation"):
            lg.reserve(claimed, "sample", 1, {"model": "m/x", "task": "t"}, claim=True)  # the same unit cannot be re-executed through an idempotent return
        self.assertEqual(lg.reserve(claimed, "sample", 1, {"model": "m/x", "task": "t"})["unit_id"], claimed)  # the non-claim (bookkeeping) path keeps its idempotent contract
        self.assertEqual(lg.snapshot()["open_reservations"], [claimed])

    def test_money_inputs_are_validated_before_quantization(self):
        lg = b.BudgetLedger(self.path, 100, self.prices)
        lg.reserve("u", "sample", 1, {}); lg.settle("u", {}, fallback_to_reservation=True, hold=True)
        for bad in ("-0.0000001", "-1", "NaN", "Infinity", "-Infinity"):
            with self.assertRaises(b.LedgerConflict, msg=bad):
                lg.resolve_manually("u", resolution="settled_amount", by="r", basis="x", amount_usd=bad)
        for bad in ("-0.0000001", "NaN", "Infinity"):
            with self.assertRaises(b.LedgerConflict, msg=bad):
                lg.reserve(f"r{bad}", "sample", bad, {})
        lg.resolve_manually("u", resolution="settled_amount", by="r", basis="statement", amount_usd="0")  # a legitimate zero is accepted
        self.assertEqual(lg.snapshot()["settled_usd"], "0.000000")
        lg.reserve("v", "sample", "0.5", {}); self.assertEqual(lg.snapshot()["reserved_usd"], "0.500000")

    def test_effective_settlement_reflects_manual_resolution_and_resolved_open_units(self):
        lg = b.BudgetLedger(self.path, 100, self.prices)
        lg.reserve("gen", "sample", 5, {"model": "m/x", "task": "t"}); lg.settle("gen", {}, fallback_to_reservation=True, hold=True)
        self.assertEqual(lg.effective_settlement("gen")["effective"]["cost_usd"], "5.000000")
        lg.resolve_manually("gen", resolution="settled_amount", by="r", basis="statement", amount_usd="2")
        eff = lg.effective_settlement("gen")
        self.assertEqual((eff["effective"]["cost_usd"], eff["effective"]["previous_cost_usd"], eff["effective"]["resolved_from"], eff["resolution"]["amount_usd"], [e["type"] for e in eff["events"]]),
                         ("2.000000", "5.000000", "estimated_settlement", "2.000000", ["reservation", "settlement", "manual_resolution"]))
        lg.reserve("open", "judge", 0.5, {}); lg.resolve_manually("open", resolution="settled_amount", by="r", basis="statement", amount_usd="0.12")
        self.assertEqual((lg.effective_settlement("open")["effective"]["cost_usd"], lg.effective_settlement("open")["effective"]["resolved_from"]), ("0.120000", "open_reservation"))
        self.assertIsNone(lg.effective_settlement("never")["effective"])

    def test_incomplete_settlement_floors_at_the_reservation_and_holds(self):
        lg = b.BudgetLedger(self.path, 100, self.prices)
        lg.reserve("a", "judge", 1, {}); lg.reserve("b", "judge", 1, {})
        small = lg.settle("a", {"m/x": {"input_tokens": 1000, "output_tokens": 0}}, incomplete=True)
        self.assertEqual((small["cost_usd"], small["estimated"], small["manual_review_required"]), ("1.000000", True, True))  # priced 0.004 < reservation 1 -> floor
        big = lg.settle("b", {"m/x": {"input_tokens": 1_000_000, "output_tokens": 100_000}}, incomplete=True)
        self.assertEqual((big["cost_usd"], big["estimated"], big["manual_review_required"]), ("6.000000", True, True))  # known 4 + 2 above the reservation is kept


if __name__ == "__main__":
    unittest.main()
