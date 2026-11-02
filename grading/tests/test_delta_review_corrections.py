"""Codex delta review of v1.6-recovery-hash-check (b33cc37): Blocking D1-D3 (corrections engine .12, approved
2026-11-02; N1 is in harness/tests/test_gemini_class_controls_unit.py). Each failing case reproduces the reviewed
counterexample (it fails on engine .11) and the neighbours that must keep working. No provider call: the generate hook
answers or raises; every registry, plan, ledger and grading directory is a temporary one."""
import datetime as dt
import json
import os
import random
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from grading import judge as J, judge_dev as JD, judge_formal as JF, judge_recovery as JR, judge_validation as JV, run_grading as RG
from harness.budget import BudgetLedger
from harness.launcher import PilotLauncher, load_config, prices_from_config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CFG = load_config(os.path.join(ROOT, "config.json"))
MODEL = CFG["judge"]["model"]
PRICES = prices_from_config(CFG)
TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"
VALID = json.dumps({"verdict": "pass", "evidence": [{"file": "f", "location": "A1", "quote": "q"}], "rationale": "r"})


def unit(i, excerpt="e"):
    return {"unit_id": f"t:item{i:02d}", "item": i, "weight": 1, "criterion": "c", "task_requirement": "r", "source_material": "s", "deliverable_excerpt": excerpt}


def usage(n_in=0, n_out=0, cr=0, cw=0):
    return {"input_tokens": n_in, "output_tokens": n_out, "cache_read_tokens": cr, "cache_write_tokens": cw}


def dev_key():
    return mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-" + JD.DEV_KEY_SUFFIX}, clear=True)


def retry_error_429(attempts=11):
    from google.genai.errors import ClientError
    from tenacity import RetryError
    return RetryError(SimpleNamespace(exception=lambda: ClientError(429, {"error": {"code": 429, "message": "synthetic per-minute quota", "status": "RESOURCE_EXHAUSTED"}}),
                                      attempt_number=attempts))


def settle(calls: list[dict], failures: list[dict], max_retries: int = 10) -> Decimal:
    """What the real ledger settles for a judge batch with these metered calls and recoverable failures (the shape of
    ProviderJudge.batch_result and PilotLauncher.run_judge_batch)."""
    d = tempfile.mkdtemp(prefix="d1_settle_")
    lg = BudgetLedger(os.path.join(d, "l.json"), 1_000_000, PRICES)
    lg.reserve("u", "judge", Decimal("0.01"), {})
    agg = {k: sum(c[k] for c in calls) for k in usage()}
    rec = {"recovered": len(failures), "buffer_calls": J.inferred_buffer_calls(failures, max_retries)} if failures else None
    return Decimal(lg.settle("u", {MODEL: agg}, calls_by_model={MODEL: calls}, scope={"same_sample": True}, recovered=rec)["cost_usd"])


class D1GuardBoundTests(unittest.TestCase):
    """D1: a successful request reprices every earlier inferred failure; the guards bound the whole settlement."""

    def test_codex_035_ceiling_case_through_adapter_guard_launcher_and_ledger(self):
        holder, sent = {}, []
        response = SimpleNamespace(completion=VALID, usage=SimpleNamespace(input_tokens=1000, output_tokens=16000, input_tokens_cache_read=0, input_tokens_cache_write=0),
                                   error=None, model="m", stop_reason="stop")
        seq = iter([retry_error_429(11), response])

        def gen(_):
            sent.append(1); v = next(seq)
            if isinstance(v, BaseException):
                raise v
            return v
        d = tempfile.mkdtemp(prefix="d1_chain_")
        lg = BudgetLedger(os.path.join(d, "l.json"), Decimal("0.35"), PRICES)
        la = PilotLauncher(CFG, runs_root=os.path.join(d, "runs"), ledger=lg, eval_fn=lambda **kw: None)
        j = J.ProviderJudge(MODEL, generate=gen, max_retries=10, max_tokens=16384, provider_error_stop_items=3, cost_guard=JV.make_guard(holder, 16384, Decimal(0), Decimal("0.35")))
        holder["judge"] = j

        def batch():
            J.judge_units([unit(1), unit(2)], j)
            return j.batch_result()
        with dev_key():
            rec = la.run_judge_batch(unit_id="R:judge:1", estimate_usd=Decimal("0.35"), batch_fn=batch)
        st = rec["settlement"]
        self.assertEqual(len(sent), 1)  # engine .11: 2 (the second request was sent and the settlement became 2.328000)
        self.assertEqual([c["status"] for c in j.calls], ["provider_error", "not_attempted"])
        self.assertIn("Judge Validation ceiling 0.35 USD", j.halted)
        self.assertLessEqual(Decimal(st["cost_usd"]), Decimal("0.35"))
        # the engine .11 bound allowed that second request: nothing metered, so it counted the request's own estimate only
        chars = len(J.JUDGE_SYSTEM_PROMPT) + len(J.render_unit(unit(2)))
        self.assertLessEqual(JD.batch_liability_usd(SimpleNamespace(calls=[], recoverable_failures=j.recoverable_failures)) + JD.next_request_bound_usd(SimpleNamespace(calls=[]), chars, 16384),
                             Decimal("0.35"))
        # and that request, completing at its usage, settles 12 average calls (1 metered + 11 inferred): the reviewed 2.328
        self.assertEqual(settle([usage(1000, 16000)], j.recoverable_failures), Decimal("2.328000"))

    def test_codex_existing_metered_call_case(self):
        old, new = usage(1000), usage(1_000_000)
        h = {"judge": SimpleNamespace(calls=[{"usage": old}], recoverable_failures=[{"item": 2}], generate_params={"max_retries": 10})}
        ceiling = Decimal("4.352912")  # the reviewed ceiling: liability 0.048 + the engine .11 next-request bound 4.294912 + 0.01
        self.assertEqual(JD.batch_liability_usd(h["judge"]) + JD.next_request_bound_usd(h["judge"], 3_000_000, 16384) + Decimal("0.01"), ceiling)
        with dev_key():
            reason = JV.make_guard(h, 16384, Decimal(0), ceiling)(3_000_000, request_bytes=3_000_000)
        self.assertIsNotNone(reason)  # engine .11: None, and the settlement below became 26.013000
        after = settle([old, new], [{"item": 2}])
        self.assertEqual(after, Decimal("26.013000"))
        self.assertGreaterEqual(JD.next_liability_bound_usd(h["judge"], 3_000_000, 16384, request_bytes=3_000_000), after)

    def test_the_bound_is_never_below_the_ledger_settlement(self):
        """Random batches through the real ledger: before every request the bound is computed; after it (completing
        within the bound's limits, or failing with up to 1 + max_retries attempts) the settlement never exceeds it,
        whichever tier each call's prompt falls in."""
        rng = random.Random(20261102)
        checked = 0
        for _ in range(120):
            calls, failures = [], []
            for step in range(rng.randint(1, 7)):
                req_bytes = rng.choice([400, 6_000, 45_000, 250_000])
                j = SimpleNamespace(calls=[{"usage": u} for u in calls], recoverable_failures=list(failures), generate_params={"max_retries": 10})
                bound = JD.next_liability_bound_usd(j, req_bytes, 16384, request_bytes=req_bytes)
                if rng.random() < 0.4:
                    failures.append({"item": step, "attempts": rng.choice([None, 1, 4, 11])})
                else:
                    prompt = rng.randint(0, req_bytes + JD.GUARD_CONTROL_TOKENS)
                    cr, cw = rng.randint(0, prompt // 3), rng.randint(0, prompt // 5)
                    calls.append(usage(prompt - cr - cw, rng.randint(0, 16384), cr, cw))
                if calls:  # with nothing metered the ledger holds the unit at its reservation
                    self.assertLessEqual(settle(calls, failures), bound, (calls, failures))
                    checked += 1
        self.assertGreater(checked, 200)

    def test_without_failures_the_bound_keeps_the_engine_10_shape(self):
        calls = [usage(20_000, 2_000)] * 3
        j = SimpleNamespace(calls=[{"usage": u} for u in calls], recoverable_failures=[], generate_params={"max_retries": 10})
        s = sum(JD._bound_call_usd(u) for u in calls)
        x = JD.request_bound_usd(9_000, 16384) + JD.LEDGER_CALL_ROUNDING
        self.assertEqual(JD.next_liability_bound_usd(j, 9_000, 16384, request_bytes=9_000), s + max(x, s / 3 * 11) + JD.LEDGER_BUFFER_ROUNDING)

    def test_the_adapter_hands_the_guard_the_request_bytes(self):
        seen = []

        def guard(chars, request_bytes=None):
            seen.append((chars, request_bytes)); return None
        u = unit(1, excerpt="€" * 100)  # a 3-byte character
        pj = J.ProviderJudge(MODEL, generate=lambda _: SimpleNamespace(completion=VALID, usage=None, error=None), cost_guard=guard, stop_on_uncertain_usage=False)
        J.judge_units([u], pj)
        user = J.render_unit(u)
        self.assertEqual(seen[0], (len(J.JUDGE_SYSTEM_PROMPT) + len(user), len(J.JUDGE_SYSTEM_PROMPT.encode("utf-8")) + len(user.encode("utf-8"))))
        self.assertEqual(seen[0][1] - seen[0][0], 200)

    def test_every_runner_uses_the_shared_bound(self):
        h = {"judge": SimpleNamespace(calls=[], recoverable_failures=[{"item": 1}], generate_params={"max_retries": 10})}
        x = JD.next_liability_bound_usd(h["judge"], 5_000, 16384, request_bytes=5_000)
        c = JD.cfg(); c["judge"]["ceilings_usd"] = {"pass_1": str(x), "judge_dev_aggregate": "30"}
        with dev_key(), mock.patch.object(JD, "cfg", return_value=c):
            self.assertIsNone(JD.make_guard(h, 16384, {"pass_1": Decimal(0), "aggregate": Decimal(0)})(5_000, request_bytes=5_000))
            self.assertIsNone(JV.make_guard(h, 16384, Decimal(0), x)(5_000, request_bytes=5_000))
        c["judge"]["ceilings_usd"]["pass_1"] = str(x - Decimal("0.000001"))
        with dev_key(), mock.patch.object(JD, "cfg", return_value=c):
            self.assertIsNotNone(JD.make_guard(h, 16384, {"pass_1": Decimal(0), "aggregate": Decimal(0)})(5_000, request_bytes=5_000))
            self.assertIsNotNone(JV.make_guard(h, 16384, Decimal(0), x - Decimal("0.000001"))(5_000, request_bytes=5_000))
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-FRML"}, clear=True):
            self.assertIsNone(JF.make_guard(h, 16384, Decimal(0), x, project_suffix="FRML")(5_000, request_bytes=5_000))
            self.assertIsNotNone(JF.make_guard(h, 16384, Decimal(0), x - Decimal("0.000001"), project_suffix="FRML")(5_000, request_bytes=5_000))


def history_fixture(ledger_units=("R:judge:1",), passes=(("base", "R:judge:1"),)):
    """A run R with judge items 1-3 (ok / provider_error / not_attempted in the pass 'base') and its canonical history:
    host_dir/ledger_binding.json bound to a ledger holding ledger_units, settled."""
    d = os.path.realpath(tempfile.mkdtemp(prefix="d3_hist_"))
    out, host = os.path.join(d, "grades"), os.path.join(d, "host")
    os.makedirs(out); os.makedirs(host)
    lg = BudgetLedger(os.path.join(d, "ledger.json"), 30, PRICES)
    for uid in ledger_units:
        lg.reserve(uid, "judge", Decimal("0.10"), {"kind": "judge"})
        lg.settle(uid, {MODEL: usage(1000)})
    binding = {"run_uuid": "R", "ledger_path": lg.path, "ledger_id": lg.identity()["ledger_id"], "generation_unit_id": None}
    json.dump(binding, open(os.path.join(host, "ledger_binding.json"), "w"))
    units = [unit(i) for i in (1, 2, 3)]
    statuses = {1: "ok", 2: "provider_error", 3: "not_attempted"}
    with open(os.path.join(out, "results.jsonl"), "w") as f:
        for pid, uid in passes:
            f.write(json.dumps({"run": {"uuid": "R"}, "task_id": TASK, "grading_pass": pid, "graded": True, "judge_mode": "real", "judge_unit": uid,
                                "pass_kind": "deterministic_plus_judge", "judge_completeness": "partial", "score": {}}) + "\n")
    with open(os.path.join(out, "grades.jsonl"), "w") as f:
        for pid, _ in passes:
            for i in (1, 2, 3):
                f.write(json.dumps({"run_uuid": "R", "task_id": TASK, "grading_pass": pid, "item": i, "source": "J", "weight": 1, "criterion": "c",
                                    "verdict": {"ok": "pass", "provider_error": "provider_error", "not_attempted": "not_run"}[statuses[i]],
                                    "error_class": None if i == 1 else statuses[i], "call_status": statuses[i]}) + "\n")
    for pid, uid in passes:
        json.dump({"units": units}, open(os.path.join(out, f"judge_units_R_{pid}.json"), "w"))
        json.dump({"unit_id": uid, "calls": [{"item": u["item"], "status": statuses[u["item"]], "request_sha256": JR.expected_request_sha256(u)} for u in units]},
                  open(os.path.join(out, f"judge_calls_R_{pid}.json"), "w"))
    return {"run_uuid": "R", "task_id": TASK, "host_dir": host, "grading_out": out, "judge_items": [1, 2, 3], "ledger": lg, "binding": binding}


def gate(r, base_pass=None):
    return RG.judge_history_gate(r["ledger"], r["binding"], r["grading_out"], "R", True, host_dir=r["host_dir"], prices=PRICES, reservation_ledger=r["ledger"], base_pass=base_pass)


class D3AuthoritativeRecoveryTests(unittest.TestCase):
    """D3: automatic recovery and the pre-request history gate take the current pass from the authoritative selection."""

    def test_a_valid_history_recovers_its_current_pass(self):
        r = history_fixture()
        with mock.patch.object(JV, "cfg", return_value=CFG), mock.patch.object(JF, "cfg", return_value=CFG):
            self.assertEqual(JV.auto_recovery_items(r), [2, 3])
            self.assertEqual(JF.recovery_items(r), ("base", [2, 3]))
        self.assertEqual(gate(r, "base")["prior_judge_units"], ["R:judge:1"])  # the production arguments of run_grading.main

    def test_an_orphan_judged_pass_is_refused_before_any_request(self):
        r = history_fixture(ledger_units=())  # the pass names R:judge:1; the canonical ledger has no such unit
        self.assertTrue(RG.authoritative_selection(CFG, r["host_dir"], r["grading_out"], "R")["blocked"])
        with mock.patch.object(JV, "cfg", return_value=CFG), mock.patch.object(JF, "cfg", return_value=CFG):
            self.assertEqual(JV.auto_recovery_items(r), [])  # engine .11: [2, 3]
            self.assertEqual(JF.recovery_items(r), (None, []))  # engine .11: ("base", [2, 3])
        with self.assertRaisesRegex(RG.GradingCliError, "does not establish its current pass"):  # engine .11: allowed
            gate(r)
        with self.assertRaisesRegex(RG.GradingCliError, "does not establish its current pass"):
            gate(r, "base")
        d = tempfile.mkdtemp(prefix="d3_jv_")
        with mock.patch.multiple(JV, VDIR=d, REGISTRY=os.path.join(d, "registry.jsonl")), mock.patch.object(JV, "cfg", return_value=CFG), \
             mock.patch.object(JV, "check", return_value={"plan_committed": True, "freeze": {"ok": True, "tag": "t", "tag_commit": "c"}}), \
             mock.patch.object(JV, "spent", return_value={"snapshot": {}}), mock.patch.object(JV, "validation_runs", return_value=[r]), mock.patch.object(JV, "grade_run") as graded:
            with self.assertRaisesRegex(SystemExit, "cannot be established"):
                JV.recover("R", [2, 3])
        graded.assert_not_called()

    def test_attempt_and_record_orders_that_disagree_are_refused(self):
        r = history_fixture(ledger_units=("R:judge:1", "R:judge:2"), passes=(("late", "R:judge:2"), ("early", "R:judge:1")))
        with mock.patch.object(JV, "cfg", return_value=CFG), mock.patch.object(JF, "cfg", return_value=CFG):
            self.assertEqual(JV.auto_recovery_items(r), [])  # engine .11: the items of 'early', the last record
            self.assertEqual(JF.recovery_items(r), (None, []))
        with self.assertRaisesRegex(RG.GradingCliError, "disagree"):
            gate(r, "early")

    def test_a_recovery_base_other_than_the_current_pass_is_refused(self):
        r = history_fixture(ledger_units=("R:judge:1", "R:judge:2"), passes=(("base", "R:judge:1"), ("rec", "R:judge:2")))
        with self.assertRaisesRegex(RG.GradingCliError, "is not the run's current judged pass"):
            gate(r, "base")
        gate(r, "rec")
        gate(r)  # a rejudge needs a consistent history, no base


class D2TerminalStopTests(unittest.TestCase):
    """D2: a non-quota halt stops the Judge Validation continuation; a recorded stop is never resumed automatically;
    the daily-quota pause keeps its continuation."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="d2_")
        self.reg = os.path.join(self.d, "registry.jsonl")
        self.plan = os.path.join(self.d, "plan.json")
        json.dump({"order": [{"run_uuid": "R", "task_id": TASK, "judge_items": 3, "reservation_usd": "1"}]}, open(self.plan, "w"))
        self.r = history_fixture()
        for p in (mock.patch.multiple(JV, VDIR=self.d, REGISTRY=self.reg, PLAN=self.plan), mock.patch.object(JV, "cfg", return_value=CFG),
                  mock.patch.object(JV, "check", return_value={"plan_committed": True, "freeze": {"ok": True, "tag": "t", "tag_commit": "c"}}),
                  mock.patch.object(JV, "spent", return_value={"snapshot": {}}), mock.patch.object(JV, "validation_runs", return_value=[self.r]),
                  mock.patch.object(JV, "on_ac_power", return_value=True)):
            p.start(); self.addCleanup(p.stop)

    def kinds(self):
        return [e["kind"] for e in JV.registry_events()]

    def out(self, **kw):
        return {"rc": 0, "judge_unit": "R:judge:2", "grading_pass": "rec", "calls": 2, "calls_ok": 0, "provider_error": 2, "not_attempted": 0, "cost_from_calls_usd": "0", **kw}

    def test_a_non_quota_halt_in_recovery_is_propagated_and_recorded(self):
        with mock.patch.object(JV, "grade_run", return_value=self.out(halted="3 distinct items failed with recoverable provider errors in this pass")):
            self.assertEqual(JV.recover("R", [2, 3]), JV.STOPPED)  # engine .11: 0
        self.assertEqual(self.kinds(), ["recovery_start", "recovery_done", "halted"])

    def test_resume_stops_after_a_halted_recovery_and_a_later_resume_refuses(self):
        with mock.patch.object(JV, "grade_run", return_value=self.out(halted="call for t:item02 failed with RetryError (unrecoverable: HTTP 500 INTERNAL); its cost is unknown")), \
             mock.patch.object(JV, "run") as run:
            self.assertEqual(JV.resume(sleep=lambda _: None), JV.STOPPED)  # engine .11: run() followed and the resume ended 0
        run.assert_not_called()
        self.assertEqual(self.kinds(), ["resume_start", "recovery_start", "recovery_done", "halted", "resume_stop"])
        with mock.patch.object(JV, "recover") as rec, mock.patch.object(JV, "run") as run:
            self.assertEqual(JV.resume(sleep=lambda _: None), JV.STOPPED)
        rec.assert_not_called(); run.assert_not_called()  # engine .11: both were called
        self.assertEqual(self.kinds()[-1], "resume_refused")

    def test_codex_recorded_stop_case(self):
        with open(self.reg, "w") as f:
            f.write(json.dumps({"kind": "resume_stop", "reason": "non-quota stop", "at": "2026-11-02T00:00:00+00:00"}) + "\n")
        with mock.patch.object(JV, "auto_recovery_items") as auto, mock.patch.object(JV, "recover") as rec, mock.patch.object(JV, "run") as run:
            self.assertEqual(JV.resume(sleep=lambda _: None), JV.STOPPED)
        auto.assert_not_called(); rec.assert_not_called(); run.assert_not_called()
        self.assertEqual(self.kinds(), ["resume_stop", "resume_refused"])

    def test_a_halted_run_returns_the_stop_and_no_later_run_is_graded(self):
        r2 = {**self.r, "run_uuid": "S"}
        json.dump({"order": [{"run_uuid": "R", "task_id": TASK, "judge_items": 3, "reservation_usd": "1"}, {"run_uuid": "S", "task_id": TASK, "judge_items": 3, "reservation_usd": "1"}]},
                  open(self.plan, "w"))
        with mock.patch.object(JV, "validation_runs", return_value=[self.r, r2]), mock.patch.object(JV, "ensure_ledger"), \
             mock.patch.object(JV, "grade_run", return_value=self.out(halted="call for t:item01 returned no usage; its cost cannot be accounted")) as graded:
            self.assertEqual(JV.run(), JV.STOPPED)  # engine .11: 0
        self.assertEqual(graded.call_count, 1)
        self.assertEqual(self.kinds(), ["pass_start", "run_start", "run_done", "halted", "pass_end"])

    def test_the_daily_quota_pause_still_continues_the_pass(self):
        # the real registry's shape: halted events of 2026-11-01, resolved by approved recoveries, carry no resume_stop
        past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)).isoformat(timespec="seconds")
        with open(self.reg, "w") as f:
            for e in ({"kind": "halted", "run_uuid": "R", "reason": "call for t:item69 failed with RetryError; its cost is unknown"}, {"kind": "pass_end"},
                      {"kind": "quota_pause", "run_uuid": "R", "resume_at": past, "at": past}):
                f.write(json.dumps({"at": past, **e}) + "\n")
        quota = {"quota_id": "GenerateRequestsPerDayPerProjectPerModel", "quota_value": "250", "retry_delay": "1s"}
        results = iter([self.out(daily_quota=quota, halted="daily quota exhausted (GenerateRequestsPerDayPerProjectPerModel, value 250); paused until the provider's reset"),
                        self.out(calls_ok=2, provider_error=0)])
        sleeps = []

        def sleep(s):  # the second pause's resume time is in the future: move it into the past once waited for
            sleeps.append(s)
            ev = JV.registry_events()
            ev[-1]["resume_at"] = past
            open(self.reg, "w").write("".join(json.dumps(e) + "\n" for e in ev))
        with mock.patch.object(JV, "grade_run", side_effect=lambda *a, **k: next(results)), mock.patch.object(JV, "run", return_value=0) as run:
            self.assertEqual(JV.resume(sleep=sleep), 0)
        self.assertEqual(run.call_count, 1); self.assertEqual(len(sleeps), 1)
        self.assertEqual(self.kinds()[3:], ["resume_start", "quota_resume", "recovery_start", "recovery_done", "quota_pause", "quota_resume", "recovery_start", "recovery_done",
                                            "resume_end"])


if __name__ == "__main__":
    unittest.main()
