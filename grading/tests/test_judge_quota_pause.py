"""Daily-quota checkpoint, pause and resume (approved 2026-11-02): a per-day quota 429 ends Inspect's retries of the
request and halts the batch; the runners record the pause, wait for the provider's reset (and AC power), and continue
the same logical pass with the eligible per-item recoveries, never re-judging a completed or exhausted item. One project
per workload: the Formal judge pass refuses the Dev project's key. No provider call."""
import datetime as dt
import json
import os
import tempfile
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from google.genai.errors import ClientError

from grading import judge as J, judge_dev as JD, judge_formal as JF, judge_validation as JV

VALID = json.dumps({"verdict": "pass", "evidence": [{"file": "f", "location": "A1", "quote": "q"}], "rationale": "r"})
PER_DAY = {"error": {"code": 429, "message": "You exceeded your current quota", "status": "RESOURCE_EXHAUSTED", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_requests_per_model_per_day",
                                                                            "quotaId": "GenerateRequestsPerDayPerProjectPerModel", "quotaValue": "250"}]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "28178s"}]}}
PER_MINUTE = {"error": {"code": 429, "message": "rate", "status": "RESOURCE_EXHAUSTED", "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaMetric": "generativelanguage.googleapis.com/generate_requests_per_model", "quotaId": "PerMinute", "quotaValue": "25"}]}]}}


def unit(i):
    return {"unit_id": f"t:item{i}", "item": i, "weight": 1, "criterion": "c", "task_requirement": "r", "source_material": "s", "deliverable_excerpt": "e"}


def answer(text):
    return SimpleNamespace(completion=text, usage=SimpleNamespace(input_tokens=10, output_tokens=1, input_tokens_cache_read=0, input_tokens_cache_write=0), error=None, model="m", stop_reason="stop")


class DetectionTests(unittest.TestCase):
    def test_a_per_day_429_is_recognised_and_a_per_minute_one_is_not(self):
        d = J.daily_quota_violation(ClientError(429, PER_DAY))
        self.assertEqual((d["quota_id"], d["quota_value"], d["retry_delay"]), ("GenerateRequestsPerDayPerProjectPerModel", "250", "28178s"))
        self.assertIsNone(J.daily_quota_violation(ClientError(429, PER_MINUTE)))
        self.assertIsNone(J.daily_quota_violation(ClientError(503, {"error": {"code": 503, "message": "unavailable", "status": "UNAVAILABLE"}})))

    def test_the_batch_halts_at_the_daily_quota_and_later_items_are_not_sent(self):
        seq = [answer(VALID), ClientError(429, PER_DAY)]
        sent = []

        def gen(_):
            sent.append(1)
            x = seq.pop(0)
            if isinstance(x, BaseException):
                raise x
            return x
        j = J.ProviderJudge("m/x", generate=gen, max_retries=10, provider_error_stop_items=3)
        v = J.judge_units([unit(1), unit(2), unit(3), unit(4)], j)
        self.assertEqual([x["error_class"] for x in v], [None, "provider_error", "not_attempted", "not_attempted"])
        self.assertEqual((len(sent), j.daily_quota["item"], j.daily_quota["quota_value"]), (2, 2, "250"))
        self.assertIn("daily quota exhausted", j.halted)
        self.assertEqual(j.batch_result()["recovered"]["recovered"], 1)  # the failed request is a recoverable failure (one retry after the reset)

    def test_inspect_retries_end_on_the_daily_quota_only(self):
        inspect_says = []
        fake = SimpleNamespace(should_retry=lambda ex: inspect_says.append(ex) or True)

        async def generate(messages):
            return answer(VALID)
        fake.generate = generate
        with mock.patch("inspect_ai.model.get_model", return_value=fake):
            j = J.ProviderJudge("google/x", max_retries=10)
            J.judge_units([unit(1)], j)
        self.assertFalse(j._model.should_retry(ClientError(429, PER_DAY)))  # no backoff on an exhausted daily quota
        self.assertTrue(j._model.should_retry(ClientError(429, PER_MINUTE)))  # every other decision stays Inspect's
        self.assertEqual(len(inspect_says), 1)


class ResumeTimeTests(unittest.TestCase):
    def test_the_later_of_the_retry_hint_and_midnight_pacific_plus_the_margin(self):
        at = "2026-11-01T23:18:47+00:00"  # item 20's failure; the hint (07:08:25Z) is earlier than midnight PST (08:00Z)
        self.assertEqual(JD.quota_resume_at({"at": at, "retry_delay": "28178s"}), dt.datetime(2026, 11, 2, 8, 5, tzinfo=dt.timezone.utc))
        self.assertEqual(JD.quota_resume_at({"at": at, "retry_delay": "40000s"}), dt.datetime(2026, 11, 2, 10, 30, 27, tzinfo=dt.timezone.utc))  # a later hint wins
        self.assertEqual(JD.quota_resume_at({"at": "2026-07-01T12:00:00+00:00"}), dt.datetime(2026, 7, 2, 7, 5, tzinfo=dt.timezone.utc))  # midnight PDT


class ValidationResumeTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="jv_resume_")
        for k, v in (("VDIR", self.d), ("REGISTRY", os.path.join(self.d, "registry.jsonl"))):
            p = mock.patch.object(JV, k, v); p.start(); self.addCleanup(p.stop)
        plan = os.path.join(self.d, "plan.json")
        json.dump({"order": [{"run_uuid": "A"}, {"run_uuid": "B"}]}, open(plan, "w"))
        p = mock.patch.object(JV, "PLAN", plan); p.start(); self.addCleanup(p.stop)
        runs = [{"run_uuid": "A", "judge_items": [1, 2]}, {"run_uuid": "B", "judge_items": [3]}]
        p = mock.patch.object(JV, "validation_runs", return_value=runs); p.start(); self.addCleanup(p.stop)

    def test_power_wait_then_recoveries_then_the_remaining_runs(self):
        power = iter([False, True])
        sleeps = []
        with mock.patch.object(JV, "on_ac_power", side_effect=lambda: next(power)), mock.patch.object(JV, "auto_recovery_items", side_effect=lambda r: [2] if r["run_uuid"] == "A" else []), \
             mock.patch.object(JV, "recover", return_value=0) as rec, mock.patch.object(JV, "run", return_value=0) as run:
            self.assertEqual(JV.resume(poll_s=7, sleep=sleeps.append), 0)
        self.assertEqual((sleeps, rec.call_args.args, run.call_count), ([7], ("A", [2]), 1))
        kinds = [e["kind"] for e in JV.registry_events()]
        self.assertEqual(kinds, ["resume_start", "power_wait", "resume_end"])

    def test_a_quota_pause_waits_for_the_reset_and_continues_the_same_pass(self):
        sleeps, calls = [], []

        def recover(u, items):
            calls.append((u, items))
            if len(calls) == 1:  # the first attempt exhausts the daily quota
                return JV.quota_pause(u, {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "retry_delay": "1s"})
            return 0
        import time

        def fake_sleep(s):  # the resume time is recorded in the registry; the runner sleeps until it has passed
            sleeps.append(s); time.sleep(min(s, 2.5))
        with mock.patch.object(JV, "on_ac_power", return_value=True), mock.patch.object(JV, "auto_recovery_items", side_effect=lambda r: [2] if r["run_uuid"] == "A" else []), \
             mock.patch.object(JV, "quota_resume_at", side_effect=lambda dq: dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2)), mock.patch.object(JV, "recover", side_effect=recover), \
             mock.patch.object(JV, "run", return_value=0):
            self.assertEqual(JV.resume(sleep=fake_sleep), 0)
        self.assertEqual(len(calls), 2); self.assertTrue(sleeps and sleeps[0] > 0)  # recover is sent again only after the recorded resume time
        kinds = [e["kind"] for e in JV.registry_events()]
        self.assertEqual(kinds, ["resume_start", "quota_pause", "quota_resume", "resume_end"])

    def test_a_gate_refusal_stops_and_is_recorded(self):
        with mock.patch.object(JV, "on_ac_power", return_value=True), mock.patch.object(JV, "auto_recovery_items", return_value=[1]), \
             mock.patch.object(JV, "recover", side_effect=SystemExit("ledger not clear")):
            self.assertEqual(JV.resume(sleep=lambda s: None), 1)
        self.assertEqual(JV.registry_events()[-1]["kind"], "resume_stop")


class FormalProjectTests(unittest.TestCase):
    def test_the_formal_pass_refuses_the_dev_project_key(self):
        env = {"GOOGLE_API_KEY": "dev-" + JD.DEV_KEY_SUFFIX, "GOOGLE_API_KEY_VALIDATION": "dev-" + JD.DEV_KEY_SUFFIX}
        c = JF.cfg()  # the real configuration; ROOT points at an empty directory so the real .env is never read
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(JF, "cfg", return_value=c), mock.patch.object(JF, "ROOT", tempfile.mkdtemp()):
            with self.assertRaisesRegex(SystemExit, "Dev project"):
                JF.select_project_credential()

    def test_the_formal_project_key_is_selected_into_the_provider_variable(self):
        env = {"GOOGLE_API_KEY": "dev-" + JD.DEV_KEY_SUFFIX, "GOOGLE_API_KEY_VALIDATION": "second-FRML"}
        c = JF.cfg()
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(JF, "cfg", return_value=c), mock.patch.object(JF, "ROOT", tempfile.mkdtemp()), \
             mock.patch("harness.launcher.verify_credential_after_dotenv", return_value={"checked": True}):
            cred = JF.select_project_credential()
            self.assertEqual((cred["variable"], cred["suffix"], os.environ["GOOGLE_API_KEY"][-4:]), ("GOOGLE_API_KEY_VALIDATION", "FRML", "FRML"))
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "dev-" + JD.DEV_KEY_SUFFIX}, clear=True):
            self.assertIn("not the Formal judge project key", JF.make_guard({"judge": None}, 0, Decimal(0), Decimal(30), project_suffix="FRML")(3))


class FormalPauseTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory(); self.addCleanup(self.d.cleanup)
        for k, v in (("JDIR", self.d.name), ("REGISTRY", os.path.join(self.d.name, "registry.jsonl")), ("SEALED", os.path.join(self.d.name, "sealed"))):
            p = mock.patch.object(JF, k, v); p.start(); self.addCleanup(p.stop)
        for name, value in (("gates", {"ok": True, "freeze_tag": {"ok": True, "commit": "c0ffee"}}), ("select_project_credential", {"variable": "GOOGLE_API_KEY_VALIDATION", "suffix": "FRML"}),
                            ("on_ac_power", True)):
            p = mock.patch.object(JF, name, return_value=value); p.start(); self.addCleanup(p.stop)
        self.scope = f"judge-formal|{JF.cfg()['judge']['model']}|{JF.cfg()['judge']['formal']['ceiling_usd']}"
        self.cfg = JF.cfg(); self.cfg["batches"]["formal"]["units_total"] = 1
        self.run = {"run_uuid": "R0", "task_id": "t", "judge_items": [1, 2, 3], "grading_out": os.path.join(self.d.name, "sealed", "R0")}

    def ledger(self):
        return SimpleNamespace(snapshot=lambda: {"remaining_usd": "30", "settled_usd": "0", "reserved_usd": "0"})

    def test_a_quota_pause_resumes_with_the_unsent_items_and_never_rejudges(self):
        grades, items_state = [], {"pending": [2, 3]}

        def fake_grade(r, est, log, auth, extra=None, project_suffix=None):
            grades.append(extra)
            if extra is None:  # the run's first batch: item 1 ok, item 2 hits the daily quota, item 3 never sent
                return {"rc": 0, "calls": 3, "calls_ok": 1, "provider_error": 1, "not_attempted": 1, "halted": "daily quota exhausted",
                        "daily_quota": {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "retry_delay": "1s", "quota_value": "250"}}
            items_state["pending"] = []
            return {"rc": 0, "calls": 2, "calls_ok": 2, "provider_error": 0, "not_attempted": 0, "halted": None}
        sleeps = []
        with mock.patch.object(JF, "finalized_runs", return_value=[self.run]), mock.patch.object(JF, "_grade", side_effect=fake_grade), mock.patch.object(JF, "ensure_ledger", return_value=self.ledger()), \
             mock.patch.object(JF, "cfg", return_value=self.cfg), mock.patch.object(JF, "recovery_items", side_effect=lambda r: ("base", list(items_state["pending"]))), \
             mock.patch.object(JF, "quota_resume_at", side_effect=lambda dq: dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2)):
            self.assertEqual(JF.run("human", "status entry", self.scope, poll_s=0, sleep=lambda s: sleeps.append(s) or __import__("time").sleep(max(0, min(s, 2.5)))), 0)
        self.assertEqual(grades[0], None)
        self.assertEqual(grades[1], ["--judge-recover", "2,3", "--base-pass", "base"])  # only the failed and the unsent items; item 1 is never re-judged
        kinds = [e["kind"] for e in JF.registry_events()]
        self.assertEqual(kinds, ["pass_start", "run_start", "run_done", "quota_pause", "quota_resume", "recovery_start", "recovery_done", "pass_end"])
        self.assertTrue(sleeps)
        text = open(JF.REGISTRY).read()
        self.assertNotIn("verdict", text)

    def test_resume_continues_a_started_pass_but_not_a_stopped_one(self):
        JF.registry({"kind": "pass_start"})
        with mock.patch.object(JF, "finalized_runs", return_value=[]), mock.patch.object(JF, "ensure_ledger", return_value=self.ledger()), mock.patch.object(JF, "cfg", return_value=self.cfg):
            with self.assertRaisesRegex(SystemExit, "already started"):
                JF.run("human", "status entry", self.scope)
            JF.run("human", "status entry", self.scope, poll_s=0, max_idle_polls=0, resume=True, sleep=lambda s: None)  # an interrupted pass continues
            with self.assertRaisesRegex(SystemExit, "stopped|ended"):
                JF.run("human", "status entry", self.scope, resume=True)  # idle_stop and pass_end were recorded: a human decision


if __name__ == "__main__":
    unittest.main()
