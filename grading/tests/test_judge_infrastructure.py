"""Engine .8 judge infrastructure (approved 2026-11-01): provider error detail, continuation after a recoverable failure,
the three-item stop, the immediate stop on unrecoverable errors, pacing, the inferred buffer, the one schema retry and
schema recovery through a recovery chain. No provider call: the generate hook raises or answers."""
import json
import os
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace

from google.genai.errors import ClientError
from tenacity import RetryError

from grading import grade as G, judge as J, judge_recovery as JR
from harness import budget as B

VALID = json.dumps({"verdict": "pass", "evidence": [{"file": "f", "location": "l", "quote": "q"}], "rationale": "r"})
NO_EVIDENCE = json.dumps({"verdict": "fail", "evidence": [], "rationale": "r"})
QUOTA_429 = {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_requests_per_model", "quotaId": "PerMinute", "quotaValue": "25"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "39s"}]}}


def retry_error(code, body):
    fut = SimpleNamespace(exception=lambda: ClientError(code, body))
    return RetryError(fut)


def unit(i):
    return {"unit_id": f"t:item{i}", "item": i, "weight": 1, "criterion": "c", "task_requirement": "r", "source_material": "s", "deliverable_excerpt": f"e{i}", "excerpt_kind": "k"}


def answer(text, usage=(100, 10)):
    return SimpleNamespace(completion=text, usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1], input_tokens_cache_read=0, input_tokens_cache_write=0),
                           error=None, model="m", stop_reason="stop")


class ErrorDetailTests(unittest.TestCase):
    def test_http_status_quota_and_retry_guidance_from_the_wrapped_client_error(self):
        d = J.provider_error_detail(retry_error(429, QUOTA_429))
        self.assertEqual((d["class"], d["inner_class"], d["http_status"], d["provider_status"], d["retry_delay"], d["recoverability"]),
                         ("RetryError", "ClientError", 429, "RESOURCE_EXHAUSTED", "39s", "recoverable"))
        self.assertEqual(d["quota"][0]["quotaId"], "PerMinute")
        bad_key = J.provider_error_detail(retry_error(400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}))
        self.assertEqual(bad_key["recoverability"], "unrecoverable")
        self.assertEqual(J.provider_error_detail(retry_error(403, {"error": {"code": 403, "message": "denied", "status": "PERMISSION_DENIED"}}))["recoverability"], "unrecoverable")
        self.assertEqual(J.provider_error_detail(TimeoutError("read timed out"))["recoverability"], "recoverable")


class FailureClassTests(unittest.TestCase):
    """V1.3 (approved 2026-11-01): classes by HTTP status and provider status / reason."""

    def cls(self, code, status=None, reason=None, message="x"):
        err = {"code": code, "message": message, **({"status": status} if status else {})}
        if reason:
            err["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}]
        return J.provider_error_detail(ClientError(code, {"error": err}))

    def test_permanent_transient_and_provider_specific_classes(self):
        self.assertEqual(self.cls(400, "INVALID_ARGUMENT", message="Request contains an invalid argument.")["failure_class"], "permanent_request")
        self.assertEqual(self.cls(413, None, message="Request payload size exceeds the limit")["failure_class"], "permanent_request")
        self.assertEqual(self.cls(429, "RESOURCE_EXHAUSTED")["failure_class"], "retryable")
        self.assertEqual(self.cls(408)["failure_class"], "retryable")
        self.assertEqual(J.provider_error_detail(retry_error(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}))["failure_class"], "retryable")
        self.assertEqual(self.cls(403, "PERMISSION_DENIED", reason="RATE_LIMIT_EXCEEDED")["failure_class"], "retryable")  # a rate limit reported as 403
        self.assertEqual(self.cls(403, "PERMISSION_DENIED", message="The caller does not have permission (quota project)")["failure_class"], "fatal")
        self.assertEqual(self.cls(401, "UNAUTHENTICATED")["failure_class"], "fatal")
        self.assertEqual(self.cls(400, "INVALID_ARGUMENT", message="API key not valid. Please pass a valid API key.")["failure_class"], "fatal")
        self.assertEqual(self.cls(404, "NOT_FOUND", message="models/x is not found")["failure_class"], "fatal")
        self.assertEqual(J.provider_error_detail(retry_error(429, QUOTA_429))["attempts"], None)  # a fake future: the count is unknown
        self.assertEqual(self.cls(400, "INVALID_ARGUMENT")["attempts"], 1)  # raised without retry


class ContinuationTests(unittest.TestCase):
    def judge(self, plan, **kw):
        it = iter(plan)

        def gen(messages):
            x = next(it)
            if isinstance(x, BaseException):
                raise x
            return answer(x)
        return J.ProviderJudge("google/m", max_retries=10, generate=gen, provider_error_stop_items=3, **kw)

    def test_a_recoverable_failure_does_not_stop_the_batch_and_is_settled_as_an_inferred_buffer(self):
        j = self.judge([VALID, retry_error(429, QUOTA_429), VALID])
        v = J.judge_units([unit(1), unit(2), unit(3)], j)
        self.assertEqual([x["error_class"] for x in v], [None, "provider_error", None])
        self.assertIsNone(j.halted)
        br = j.batch_result()
        self.assertFalse(br["usage_incomplete"])
        self.assertEqual((br["recovered"]["recovered"], br["recovered"]["buffer_calls"]), (1, 11))  # 1 failed request x (1 + max_retries 10)
        self.assertEqual(G.judge_row_verdict(v[1]), "provider_error")

    def test_three_distinct_failed_items_stop_new_requests(self):
        j = self.judge([retry_error(429, QUOTA_429)] * 3 + [VALID])
        v = J.judge_units([unit(i) for i in (1, 2, 3, 4)], j)
        self.assertEqual([x["error_class"] for x in v], ["provider_error"] * 3 + ["not_attempted"])
        self.assertIn("3 distinct items", j.halted)

    def test_an_unrecoverable_error_stops_at_once_and_holds(self):
        j = self.judge([retry_error(401, {"error": {"code": 401, "message": "unauthenticated", "status": "UNAUTHENTICATED"}}), VALID])
        v = J.judge_units([unit(1), unit(2)], j)
        self.assertEqual([x["error_class"] for x in v], ["provider_error", "not_attempted"])
        self.assertTrue(j.batch_result()["usage_incomplete"])

    def test_without_a_stop_threshold_the_earlier_halting_policy_is_kept(self):
        j = J.ProviderJudge("google/m", generate=lambda m: (_ for _ in ()).throw(retry_error(429, QUOTA_429)))
        v = J.judge_units([unit(1), unit(2)], j)
        self.assertEqual([x["error_class"] for x in v], ["provider_error", "not_attempted"])  # out of scope: Judge Dev style adapters keep halting

    def test_a_permanent_request_failure_is_provider_error_at_once_and_the_batch_goes_on(self):
        j = self.judge([ClientError(413, {"error": {"code": 413, "message": "Request payload size exceeds the limit"}}), VALID])
        v = J.judge_units([unit(1), unit(2)], j)
        self.assertEqual([x["error_class"] for x in v], ["provider_error", None])
        self.assertEqual((j.calls[0]["error"]["failure_class"], j.calls[0]["error"]["attempts"], j.calls[0]["runner_version"]), ("permanent_request", 1, J.JUDGE_RUNNER_VERSION))
        self.assertIsNone(j.halted)
        self.assertEqual(j.batch_result()["recovered"]["buffer_calls"], 1)  # one request was sent, not 1 + max_retries

    def test_the_item_wall_clock_cap_cancels_a_hanging_request_and_the_batch_goes_on(self):
        import asyncio
        answers = iter(["hang", VALID])

        async def gen(messages):
            x = next(answers)
            if x == "hang":
                await asyncio.sleep(5)
            return answer(VALID)
        j = J.ProviderJudge("google/m", max_retries=10, generate=gen, provider_error_stop_items=3, item_wall_clock_cap_s=0.3)
        v = J.judge_units([unit(1), unit(2)], j)
        self.assertEqual([x["error_class"] for x in v], ["provider_error", None])
        e = j.calls[0]["error"]
        self.assertEqual((e["timed_out"], e["failure_class"], e["wall_clock_cap_s"]), (True, "retryable", 0.3))
        self.assertLess(j.calls[0]["seconds"], 2)
        self.assertEqual(G.judge_row_verdict(v[0]), "provider_error")  # never a rubric fail

    def test_the_cap_covers_the_schema_retry_of_the_same_item(self):
        import time
        def slow_invalid(messages):
            time.sleep(0.25)
            return answer(NO_EVIDENCE)
        j = J.ProviderJudge("google/m", generate=slow_invalid, provider_error_stop_items=3, item_wall_clock_cap_s=0.2)
        v = J.judge_units([unit(1)], j)[0]
        self.assertEqual((len(j.calls), j.calls[1]["status"], j.calls[1]["error"]["class"]), (2, "provider_error", "WallClockCap"))  # the retry is not sent: the item's cap is spent
        self.assertEqual(v["error_class"], "provider_error")

    def test_pacing_pauses_between_requests(self):
        import time
        j = self.judge([VALID, VALID], pacing_pause_s=0.2)
        t0 = time.monotonic(); J.judge_units([unit(1), unit(2)], j)
        self.assertGreaterEqual(time.monotonic() - t0, 0.2)


class SchemaRetryTests(unittest.TestCase):
    def test_one_retry_accepts_the_first_schema_valid_response_and_keeps_both(self):
        answers = iter([NO_EVIDENCE, VALID])
        v = J.judge_units([unit(18)], lambda u: next(answers))[0]
        self.assertEqual((v["verdict"], v["error_class"], len(v["schema_attempts"])), ("pass", None, 2))
        self.assertIn("non-empty", v["schema_attempts"][0]["parse_error"])

    def test_two_invalid_responses_are_invalid_judge_output(self):
        v = J.judge_units([unit(18)], lambda u: NO_EVIDENCE)[0]
        self.assertEqual((v["error_class"], G.judge_row_verdict(v)), ("invalid_judge_output", "invalid_judge_output"))
        none = J.judge_units([unit(18)], lambda u: NO_EVIDENCE, schema_retry=False)[0]
        self.assertEqual(none["error_class"], "judge_parse_error")  # a recovery that is itself the retry passes no inline retry

    def test_a_schema_valid_response_is_never_retried(self):
        calls = []
        J.judge_units([unit(1)], lambda u: calls.append(1) or json.dumps({"verdict": "fail", "evidence": [{"file": "f", "location": "l", "quote": "q"}], "rationale": "r"}))
        self.assertEqual(len(calls), 1)


class LedgerBufferTests(unittest.TestCase):
    def test_buffer_calls_scale_the_inferred_buffer_and_nothing_metered_holds(self):
        with tempfile.TemporaryDirectory() as d:
            prices = {"m/x": {"input": 1, "output": 0}}
            lg = B.BudgetLedger(os.path.join(d, "l.json"), 100, prices)
            lg.reserve("j", "judge", 10, {})
            st = lg.settle("j", {"m/x": {"input_tokens": 2_000_000, "output_tokens": 0}}, calls_by_model={"m/x": [{"input_tokens": 1_000_000, "output_tokens": 0}] * 2},
                           scope={"same_sample": True}, recovered={"recovered": 1, "buffer_calls": 11})
            self.assertEqual((st["cost_usd"], st["manual_review_required"], st["inferred"]["buffer_calls"]), ("13.000000", False, 11))  # 2 + 11 x 1.0
            lg.reserve("k", "judge", 5, {})
            held = lg.settle("k", {"m/x": {"input_tokens": 0, "output_tokens": 0}}, recovered={"recovered": 1, "buffer_calls": 11})
            self.assertTrue(held["manual_review_required"])


class SchemaRecoveryTests(unittest.TestCase):
    """A schema-invalid item of a pass whose latest version is itself a recovery pass is recovered once through the
    chain (units and the request hash of the original judged pass)."""
    RUN, ROOT, P2 = "RUNCHAIN", "pass-root-0001", "pass-recovery-0002"
    TASK = "a45bc83b-22f9-4def-8d89-9c5661b2b86f"

    def test_schema_recovery_through_a_recovery_chain(self):
        with tempfile.TemporaryDirectory() as out:
            units = {i: {**unit(i), "unit_id": J.unit_id(self.TASK, i), "run_uuid": self.RUN, "task_id": self.TASK} for i in (18, 20)}
            sha = lambda u: JR.expected_request_sha256(u)
            row = lambda i, p, ec, cs: {"run_uuid": self.RUN, "task_id": self.TASK, "item": i, "weight": 1, "criterion": "c", "source": "J", "verdict": "cannot_assess" if ec else "pass",
                                        "evidence": [], "error_class": ec, "call_status": cs, "grader_version": "v1", "grading_pass": p}
            with open(os.path.join(out, "grades.jsonl"), "w") as f:
                for p in (self.ROOT, self.P2):
                    f.write(json.dumps(row(18, p, "judge_parse_error", "ok")) + "\n" + json.dumps(row(20, p, None, "ok")) + "\n")
            recs = [{"run": {"uuid": self.RUN}, "grading_pass": self.ROOT, "graded": True, "judge_mode": "real", "judge_unit": "u-root", "pass_kind": "deterministic_plus_judge", "score": {}},
                    {"run": {"uuid": self.RUN}, "grading_pass": self.P2, "graded": True, "judge_mode": "real", "judge_unit": "u-rec", "pass_kind": "judge_item_recovery", "base_pass": self.ROOT, "score": {}}]
            open(os.path.join(out, "results.jsonl"), "w").write("".join(json.dumps(r) + "\n" for r in recs))
            json.dump({"unit_id": "u-root", "calls": [{"item": i, "status": "ok", "request_sha256": sha(units[i])} for i in (18, 20)]}, open(os.path.join(out, f"judge_calls_{self.RUN}_a.json"), "w"))
            json.dump({"units": list(units.values())}, open(os.path.join(out, f"judge_units_{self.RUN}_{self.ROOT}.json"), "w"))
            d = JR.recovery_plan(out, self.RUN, self.P2, [18, 20])["decision"]
            self.assertEqual((d[18]["eligible"], d[18]["base_call_status"], d[20]["eligible"]), (True, "judge_parse_error", False))  # a schema-valid verdict is never re-judged
            class Fake:
                calls, judge_unit, judge_id, halted = [], "u-rec2", "fake", None

                def __call__(self, u):
                    rec = {"item": u["item"], "status": "ok", "raw_response": NO_EVIDENCE, "request_sha256": sha(u), "usage": None, "usage_status": "ok"}
                    self.calls.append(rec); return rec
            j = Fake()
            rec = JR.recovery_pass(out, self.RUN, self.TASK, self.P2, [18], j)
            new = {r["item"]: r for r in map(json.loads, open(os.path.join(out, "grades.jsonl"))) if r["grading_pass"] == rec["grading_pass"]}
            self.assertEqual((new[18]["verdict"], new[20]["verdict"], len(j.calls)), ("invalid_judge_output", "pass", 1))  # one schema retry only
            att = json.load(open(rec["recovery"]["record"]))["attempts"][0]
            self.assertEqual((att["response_schema_valid"], att["same_request_as_base"]), (False, True))


if __name__ == "__main__":
    unittest.main()
