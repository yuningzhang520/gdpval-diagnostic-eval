"""Codex Review 2 Blocking findings R2-B1, B2, B4, B5 (pinned 5121e1a; corrections engine .10, approved 2026-11-02).
Each test reproduces the reviewed failure (it fails on engine .9) and checks the out-of-scope neighbours. No provider
call: the generate hook answers or raises. R2-B3 (ledger) is in harness/tests/test_budget_unit.py."""
import csv
import json
import os
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from grading import judge as J, judge_dev as JD, judge_formal as JF, judge_validation as JV, review as R
from grading.grade import select_pass

VALID = json.dumps({"verdict": "pass", "evidence": [{"file": "f", "location": "A1", "quote": "q"}], "rationale": "r"})


def unit(i=1):
    return {"unit_id": f"t:item{i:02d}", "item": i, "weight": 1, "criterion": "c", "task_requirement": "r", "source_material": "s", "deliverable_excerpt": "e"}


def answer(raw, n_in, usage=True):
    u = SimpleNamespace(input_tokens=n_in, output_tokens=0, input_tokens_cache_read=0, input_tokens_cache_write=0) if usage else None
    return SimpleNamespace(completion=raw, usage=u, error=None, model="m", stop_reason="stop")


def scripted(*outs):
    seq = list(outs)

    def gen(_):
        x = seq.pop(0)
        if isinstance(x, BaseException):
            raise x
        return x
    return gen


class Crash(BaseException):  # process death stand-in: not swallowed by the adapter
    pass


class WalAttemptTests(unittest.TestCase):
    """R2-B1: every provider request is its own write-ahead attempt."""

    def setUp(self):
        self.log = os.path.join(tempfile.mkdtemp(prefix="wal_"), "u.jsonl")

    def judge(self, gen):
        return J.ProviderJudge("m/x", generate=gen, log_path=self.log, run_uuid="R", judge_unit="R:judge:1")

    def test_both_paid_schema_attempts_are_recovered_from_the_log(self):
        j = self.judge(scripted(answer("not JSON", 5_000_000), answer(VALID, 2_000_000)))
        J.judge_units([unit()], j)
        d = J.usage_from_judge_log(self.log)
        self.assertEqual(d["usage"]["m/x"]["input_tokens"], 7_000_000)  # engine .9: 2,000,000 (the first attempt was merged away)
        self.assertEqual(d["usage"], j.usage_by_model)
        self.assertEqual((d["calls"], d["units"], d["unknown_calls"]), (2, 1, 0))
        ids = [json.loads(l)["attempt_id"] for l in open(self.log)]
        self.assertEqual(len(set(ids)), 2)  # started / finished of each attempt share one id

    def test_an_interrupted_retry_stays_unknown_and_the_first_attempt_keeps_its_cost(self):
        j = self.judge(scripted(answer("not JSON", 5_000_000), Crash()))
        with self.assertRaises(Crash):
            J.judge_units([unit()], j)
        scan = J.scan_judge_log(self.log)
        self.assertEqual((scan["unknown"], scan["calls"]["t:item01"]["state"], len(scan["unknown_attempts"])), (["t:item01"], "UNKNOWN", 1))  # engine .9: ok, no unknown
        d = J.usage_from_judge_log(self.log)
        self.assertEqual((d["usage"]["m/x"]["input_tokens"], d["unknown_calls"]), (5_000_000, 1))

    def test_mixed_usage_availability_counts_the_attempt_without_usage(self):
        j = J.ProviderJudge("m/x", generate=scripted(answer("not JSON", 1000), answer(VALID, 0, usage=False)), log_path=self.log, run_uuid="R", judge_unit="R:judge:1",
                            stop_on_uncertain_usage=False)
        J.judge_units([unit()], j)
        d = J.usage_from_judge_log(self.log)
        self.assertEqual((d["usage"]["m/x"]["input_tokens"], d["finished_without_usage"], d["unknown_calls"]), (1000, 1, 0))

    def test_logs_without_attempt_ids_pair_in_log_order(self):
        ev = [{"phase": "started", "unit_id": "u1"}, {"phase": "finished", "unit_id": "u1", "status": "ok", "usage": {"input_tokens": 5}, "model": "m"},
              {"phase": "started", "unit_id": "u1"}, {"phase": "finished", "unit_id": "u1", "status": "ok", "usage": {"input_tokens": 2}, "model": "m"},
              {"phase": "started", "unit_id": "u2"}, {"phase": "finished", "unit_id": "u2", "status": "ok", "usage": {"input_tokens": 1}, "model": "m"}, {"phase": "started", "unit_id": "u2"}]
        with open(self.log, "w") as f:
            f.write("".join(json.dumps(e) + "\n" for e in ev))
        d = J.usage_from_judge_log(self.log)
        self.assertEqual((d["usage"]["m"]["input_tokens"], d["unknown_calls"], d["unknown_units"]), (8, 1, ["u2"]))
        self.assertEqual(J.scan_judge_log(self.log)["calls"]["u1"]["state"], "ok")  # out of scope: a unit whose attempts all finished

    def test_durable_and_memory_disagreement_settles_the_larger_figure(self):
        from grading.run_grading import durable_usage
        j = self.judge(scripted(answer(VALID, 10)))
        J.judge_units([unit()], j)
        j.usage_by_model["m/x"]["input_tokens"] += 90  # an in-memory call whose terminal event never reached the disk
        d = durable_usage(self.log, j)
        self.assertFalse(d["memory_cross_check"]["agrees"])
        self.assertEqual(d["usage"]["m/x"]["input_tokens"], 100)  # engine .9: the durable 10 was settled silently
        self.assertIn("disagree", d["source"])


def passes(*recs):
    return [{"graded": True, "judge_mode": "real", "judge_completeness": "complete", **r} for r in recs]


class AuthoritativeSelectionTests(unittest.TestCase):
    """R2-B2: the latest judged pass is chosen by pass and attempt identity, never by its count of successful calls."""

    def attempts(self, *units):
        return [{"unit_id": u, "state": "settled", "at": f"2026-11-02T0{i}:00:00+00:00", "has_pass": hp} for i, (u, hp) in enumerate(units)]

    def test_a_zero_success_recovery_is_the_current_pass(self):
        ps = passes({"grading_pass": "partial-base", "judge_unit": "R:judge:1", "judge_completeness": "partial", "judge_verdicts": 1},
                    {"grading_pass": "complete-pass", "judge_unit": "R:judge:2", "judge_verdicts": 1},
                    {"grading_pass": "latest-recovery", "judge_unit": "R:judge:3", "pass_kind": "judge_item_recovery", "judge_completeness": "partial", "judge_verdicts": 0})
        sel = select_pass(ps, attempts=self.attempts(("R:judge:1", True), ("R:judge:2", True), ("R:judge:3", True)))
        self.assertEqual((sel["pass"]["grading_pass"], sel["blocked"]), ("latest-recovery", False))  # engine .9: complete-pass
        self.assertEqual((sel["latest_attempt"]["unit_id"], sel["latest_complete_pass"]), ("R:judge:3", "complete-pass"))
        self.assertTrue(any("partial" in w for w in sel["warnings"]))

    def test_an_incomplete_recovery_with_some_successes_is_current(self):
        ps = passes({"grading_pass": "p1", "judge_unit": "R:judge:1", "judge_completeness": "partial"},
                    {"grading_pass": "rec", "judge_unit": "R:judge:2", "pass_kind": "judge_item_recovery", "judge_completeness": "partial", "judge_verdicts": 2})
        self.assertEqual(select_pass(ps, attempts=self.attempts(("R:judge:1", True), ("R:judge:2", True)))["pass"]["grading_pass"], "rec")

    def test_multiple_passes_order_conflict_and_missing_history_block(self):
        det = {"graded": True, "grading_pass": "d0", "judge_mode": "none", "pass_kind": "deterministic_only"}
        ps = [det] + passes({"grading_pass": "p1", "judge_unit": "R:judge:1"}, {"grading_pass": "p2", "judge_unit": "R:judge:2"})
        ok = select_pass(ps, attempts=self.attempts(("R:judge:1", True), ("R:judge:2", True)))
        self.assertEqual(ok["pass"]["grading_pass"], "p2")
        swapped = select_pass(ps, attempts=self.attempts(("R:judge:2", True), ("R:judge:1", True)))
        self.assertTrue(swapped["blocked"]); self.assertIn("order", swapped["basis"])  # attempt order and record order disagree: fail closed
        missing = select_pass(ps, attempts=self.attempts(("R:judge:2", True)))
        self.assertTrue(missing["blocked"]); self.assertIn("R:judge:1", missing["basis"])  # a judged pass whose unit is absent from the ledger history
        self.assertEqual(select_pass([det], attempts=[])["pass"]["grading_pass"], "d0")  # out of scope: no judge, the latest deterministic pass

    def test_historical_view_without_attempts_is_never_authoritative(self):
        ps = passes({"grading_pass": "p1", "judge_unit": "R:judge:1"}, {"grading_pass": "rec", "judge_unit": "R:judge:2", "pass_kind": "judge_item_recovery", "judge_verdicts": 0})
        sel = select_pass(ps)
        self.assertEqual((sel["pass"]["grading_pass"], sel["authoritative"]), ("rec", False))


class GuardLiabilityTests(unittest.TestCase):
    """R2-B4: every per-call guard counts the inferred liability the ledger will settle for the batch."""

    def holder(self, n_calls=1, failures=1, max_retries=10):
        usage = {"input_tokens": 1_000_000, "output_tokens": 0}
        return {"judge": SimpleNamespace(calls=[{"usage": usage}] * n_calls, recoverable_failures=[{"item": i} for i in range(failures)], generate_params={"max_retries": max_retries})}

    def env(self):
        return mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-" + JD.DEV_KEY_SUFFIX}, clear=True)

    def test_the_reviewed_24_usd_liability_against_a_15_usd_ceiling_refuses(self):
        h = self.holder()
        one = JD.call_cost_usd({"input_tokens": 1_000_000}, "long")
        self.assertEqual(JD.batch_liability_usd(h["judge"]), one * 12)  # 1 metered call + 11 average calls inferred
        with self.env():
            self.assertIsNotNone(JV.make_guard(h, 0, Decimal(0), Decimal(15))(3))  # engine .9: None (allowed)
            self.assertIsNotNone(JF.make_guard(h, 0, Decimal(0), Decimal(15))(3))

    def test_boundaries_and_a_ceiling_already_exceeded(self):
        h = self.holder(failures=0)
        one = JD.call_cost_usd({"input_tokens": 1_000_000}, "long")
        nxt = JD.next_request_bound_usd(h["judge"], 3, 0)
        self.assertEqual(nxt, one * 11)  # if the next request fails, the ledger infers (1 + max_retries) average calls
        with self.env():
            self.assertIsNone(JV.make_guard(h, 0, Decimal(0), one + nxt)(3))  # exactly at the ceiling: allowed
            self.assertIsNotNone(JV.make_guard(h, 0, Decimal(0), one + nxt - Decimal("0.000001"))(3))
            self.assertIsNotNone(JV.make_guard({"judge": None}, 0, Decimal(16), Decimal(15))(3))  # the ledger is already over: nothing more is authorized
        empty = SimpleNamespace(calls=[], recoverable_failures=[{"item": 1}], generate_params={"max_retries": 10})
        self.assertEqual(JD.batch_liability_usd(empty), 0)  # no metered call to average: the ledger holds the unit at its reservation instead

    def test_judge_dev_guard_counts_the_same_liability(self):
        h = self.holder()
        c = JD.cfg(); c["judge"]["ceilings_usd"] = {"pass_1": 15, "judge_dev_aggregate": 30}
        with self.env(), mock.patch.object(JD, "cfg", return_value=c):
            self.assertIsNotNone(JD.make_guard(h, 0, {"pass_1": Decimal(0), "aggregate": Decimal(0)})(3))

    def test_the_settlement_and_the_guard_use_one_buffer_rule(self):
        fails = [{"item": 1, "attempts": 4}, {"item": 2}]
        self.assertEqual(J.inferred_buffer_calls(fails, 10), 4 + 11)


class LabelIdentityTests(unittest.TestCase):
    """R2-B5: labels are compared only with grade rows of the same run and one named pass."""

    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="labels_")

    def checkpoint(self, run, rows_run=None):
        p = os.path.join(self.d, f"{run}.csv")
        with open(p, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["run_uuid", "item", "weight", "criterion", "label", "evidence", "time", "reviewer"])
            w.writerow([rows_run or run, 1, 1, "c", "pass", "e", "2026-11-02", "h"])
        return R.save_label_checkpoint(self.d, run, p, "h")

    def grades(self, run="B", gp="B-pass"):
        return [{"run_uuid": run, "grading_pass": gp, "item": 1, "source": "D", "weight": 1, "verdict": "pass"}]

    def test_a_checkpoint_of_another_run_is_rejected(self):
        cp = self.checkpoint("A")
        os.makedirs(os.path.join(self.d, "labels", "B"))
        with self.assertRaisesRegex(RuntimeError, "run"):
            R.compare_labels(self.d, "B", self.grades(), checkpoint_path=cp["checkpoint"])  # engine .9: agreement 1/1 for B

    def test_foreign_label_rows_mixed_or_foreign_grade_rows_and_missing_identity_are_rejected(self):
        cp = self.checkpoint("B")
        with open(cp["copy"], "a", newline="") as f:  # a label row of run A inside B's copy: the recorded SHA no longer matches either
            csv.writer(f).writerow(["A", 2, 1, "c", "fail", "e", "t", "h"])
        with self.assertRaises(RuntimeError):
            R.compare_labels(self.d, "B", self.grades(), checkpoint_path=cp["checkpoint"])
        cp = self.checkpoint("B")
        for bad in (self.grades("A", "A-pass"), self.grades() + [{**self.grades()[0], "item": 2, "grading_pass": "other"}],
                    [{k: v for k, v in self.grades()[0].items() if k != "grading_pass"}], [{k: v for k, v in self.grades()[0].items() if k != "run_uuid"}]):
            with self.assertRaises(RuntimeError):
                R.compare_labels(self.d, "B", bad, checkpoint_path=cp["checkpoint"])
        with self.assertRaisesRegex(RuntimeError, "pass"):
            R.compare_labels(self.d, "B", self.grades(), checkpoint_path=cp["checkpoint"], grading_pass="another-pass")

    def test_a_legacy_checkpoint_without_run_identity_is_rejected(self):
        cp = self.checkpoint("B")
        rec = json.load(open(cp["checkpoint"])); rec.pop("run_uuid")
        legacy = os.path.join(self.d, "labels", "B", "checkpoint_legacy.json"); json.dump(rec, open(legacy, "w"))
        with self.assertRaisesRegex(RuntimeError, "identity"):
            R.compare_labels(self.d, "B", self.grades(), checkpoint_path=legacy)

    def test_a_valid_match_is_compared(self):
        cp = self.checkpoint("B")
        out = R.compare_labels(self.d, "B", self.grades(), checkpoint_path=cp["checkpoint"], grading_pass="B-pass")
        self.assertEqual((out["summary"]["D"]["agreement"], out["grading_pass"], out["identity"]["checkpoint_run"]), ("1/1", "B-pass", "B"))

    def test_the_cli_refuses_an_unknown_grading_pass(self):
        cp = self.checkpoint("B")
        with open(os.path.join(self.d, "grades.jsonl"), "w") as f:
            f.write(json.dumps(self.grades()[0]) + "\n")
        with open(os.path.join(self.d, "results.jsonl"), "w") as f:
            f.write(json.dumps({"run": {"uuid": "B"}, "grading_pass": "B-pass", "graded": True}) + "\n")
        with self.assertRaises(SystemExit):
            R.main(["compare", "--out-dir", self.d, "--run-uuid", "B", "--checkpoint", cp["checkpoint"], "--grading-pass", "mistyped"])  # engine .9: fell back to the authoritative pass


class InteractionTests(unittest.TestCase):
    """The corrected paths together, through the real adapter, write-ahead log, ledger, guard, history join, selection
    and label comparison: a schema retry, a recoverable 429 and an ok call in one batch; a zero-success recovery; the
    labels compared with the authoritative pass; an interrupted retry blocking the selection."""

    def setUp(self):
        from harness.budget import BudgetLedger
        from harness.launcher import load_config, prices_from_config
        from grading import run_grading as RG
        self.RG, self.BL = RG, BudgetLedger
        self.cfg = load_config(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json"))
        self.model = self.cfg["judge"]["model"]
        self.prices = prices_from_config(self.cfg)
        self.d = os.path.realpath(tempfile.mkdtemp(prefix="r2_interaction_"))
        self.ledger = BudgetLedger(os.path.join(self.d, "ledger.json"), 15, self.prices, label="judge_validation")
        self.binding = {"run_uuid": "R", "ledger_path": self.ledger.path, "ledger_id": self.ledger.identity()["ledger_id"], "generation_unit_id": None}

    def batch(self, unit_id, outs, units, base=Decimal(0), ceiling=Decimal(15)):
        from google.genai.errors import ClientError  # noqa: F401  (the provider error class the adapter classifies)
        holder = {}
        log = self.RG.judge_log_path(self.ledger.path, "R", unit_id)
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-" + JD.DEV_KEY_SUFFIX}, clear=True):
            j = J.ProviderJudge(self.model, generate=scripted(*outs), log_path=log, run_uuid="R", judge_unit=unit_id, max_retries=10, provider_error_stop_items=3,
                                cost_guard=JV.make_guard(holder, 16384, base, ceiling))
            holder["judge"] = j
            self.ledger.reserve(unit_id, "judge", Decimal("1.00"), {"kind": "judge"})
            verdicts = J.judge_units(units, j)
        br = j.batch_result()
        st = self.ledger.settle(unit_id, br["usage"], calls_by_model=br["calls_by_model"], recovered=br["recovered"], incomplete=br["usage_incomplete"],
                                fallback_to_reservation=not br["usage"], scope={"same_sample": True} if br["calls_by_model"] else None)
        return j, verdicts, st, log

    def quota_error(self):
        from google.genai.errors import ClientError
        from tenacity import RetryError
        return RetryError(SimpleNamespace(exception=lambda: ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}), attempt_number=11))

    def test_retry_failure_settlement_guard_recovery_selection_and_labels(self):
        j, v, st, log = self.batch("R:judge:1", [answer("not JSON", 1000), answer(VALID, 1000), self.quota_error(), answer(VALID, 1000)], [unit(1), unit(2), unit(3)])
        self.assertEqual([x["call_status"] for x in v], ["ok", "provider_error", "ok"])
        self.assertEqual(J.usage_from_judge_log(log)["usage"], j.usage_by_model)  # B1: both attempts of item 1 on disk and in memory
        self.assertEqual(j.usage_by_model[self.model]["input_tokens"], 3000)
        self.assertEqual((st["estimated"], st["manual_review_required"], st["inferred"]["buffer_calls"]), (True, False, 11))  # B3: estimated, no hold
        self.assertGreaterEqual(JD.batch_liability_usd(j), Decimal(st["cost_usd"]))  # B4: the guard's liability bounds the settlement
        tight = JV.make_guard({"judge": j}, 0, Decimal(0), JD.batch_liability_usd(j) - Decimal("0.000001"))
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-" + JD.DEV_KEY_SUFFIX}, clear=True):
            self.assertIsNotNone(tight(10))
        # a recovery of item 2 whose only call fails again: nothing metered, so the unit is held at its reservation
        j2, v2, st2, _ = self.batch("R:judge:2", [self.quota_error()], [unit(2)])
        self.assertTrue(st2["manual_review_required"])
        out = os.path.join(self.d, "grades"); os.makedirs(out)
        recs = [{"run": {"uuid": "R"}, "grading_pass": "base", "graded": True, "judge_mode": "real", "judge_unit": "R:judge:1", "pass_kind": "deterministic_plus_judge", "judge_completeness": "partial", "judge_verdicts": 3},
                {"run": {"uuid": "R"}, "grading_pass": "rec", "graded": True, "judge_mode": "real", "judge_unit": "R:judge:2", "pass_kind": "judge_item_recovery", "judge_completeness": "partial",
                 "judge_verdicts": 3, "judge_calls_ok": 0, "base_pass": "base"}]
        with open(os.path.join(out, "results.jsonl"), "w") as f:
            f.write("".join(json.dumps(r) + "\n" for r in recs))
        with open(os.path.join(out, "grades.jsonl"), "w") as f:
            for gp, verdict in (("base", "provider_error"), ("rec", "provider_error")):
                f.write(json.dumps({"run_uuid": "R", "grading_pass": gp, "item": 2, "source": "J", "weight": 1, "verdict": verdict}) + "\n")
        attempts = self.RG.judge_attempts(self.RG.run_judge_history(self.ledger, self.binding), [dict(r) for r in recs])
        sel = select_pass(recs, attempts=attempts)
        self.assertEqual((sel["pass"]["grading_pass"], sel["blocked"]), ("rec", False))  # B2: the zero-success recovery is current
        # B5: labels of this run compared with the authoritative pass; the same checkpoint refused for another run's rows
        csvp = os.path.join(self.d, "l.csv")
        with open(csvp, "w", newline="") as f:
            w = csv.writer(f); w.writerow(["run_uuid", "item", "weight", "criterion", "label", "evidence", "time", "reviewer"]); w.writerow(["R", 2, 1, "c", "pass", "e", "t", "h"])
        cp = R.save_label_checkpoint(out, "R", csvp, "h")
        rows = [g for g in (json.loads(l) for l in open(os.path.join(out, "grades.jsonl"))) if g["grading_pass"] == sel["pass"]["grading_pass"]]
        cmp_ = R.compare_labels(out, "R", rows, checkpoint_path=cp["checkpoint"], grading_pass="rec")
        self.assertEqual((cmp_["grading_pass"], cmp_["summary"]["J"]["grader_cannot"]), ("rec", 1))
        with self.assertRaises(RuntimeError):
            R.compare_labels(out, "R", [{**rows[0], "run_uuid": "S"}], checkpoint_path=cp["checkpoint"])

    def test_an_interrupted_retry_keeps_the_known_cost_and_blocks_the_selection(self):
        log = self.RG.judge_log_path(self.ledger.path, "R", "R:judge:1")
        j = J.ProviderJudge(self.model, generate=scripted(answer("not JSON", 1000), Crash()), log_path=log, run_uuid="R", judge_unit="R:judge:1")
        self.ledger.reserve("R:judge:1", "judge", Decimal("1.00"), {"kind": "judge"})
        with self.assertRaises(Crash):
            J.judge_units([unit(1)], j)
        d = self.RG.durable_usage(log, j)
        self.assertEqual((d["usage"][self.model]["input_tokens"], d["unknown_calls"]), (1000, 1))  # B1: the first attempt's cost is kept, the second is UNKNOWN
        self.ledger.settle("R:judge:1", d["usage"], estimated=True, fallback_to_reservation=not d["usage"], incomplete=True)
        attempts = self.RG.judge_attempts(self.RG.run_judge_history(self.ledger, self.binding), [])
        self.assertEqual(attempts[0]["state"], "unknown")
        self.assertTrue(select_pass([], attempts=attempts)["blocked"])  # B1 x B2: an unterminated retry is never hidden


if __name__ == "__main__":
    unittest.main()
