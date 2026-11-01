"""Judge Dev configuration (approved 2026-11-01): the effective Google request settings through Inspect's adapter, the
per-call cost guard, assessment failures never becoming rubric fails, and the recorded call fields. Offline: synthetic
key, socket connects blocked, injected generate functions; no provider call."""
import json
import os
import socket
import unittest
from types import SimpleNamespace
from unittest import mock

from grading import judge as J

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.json")


def cfg_judge():
    return json.load(open(CONFIG, encoding="utf-8"))["judge"]


def unit(i=38):
    return {"unit_id": f"task:item{i:02d}", "run_uuid": "r", "task_id": "task", "item": i, "weight": 1, "criterion": "C", "task_requirement": "T", "source_material": "S",
            "deliverable_excerpt": "E", "evidence_builder": "grading.judge.build_units_x@x-1"}


def output(text, stop="stop", usage=(1000, 500)):
    return SimpleNamespace(completion=text, usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1], input_tokens_cache_read=0, input_tokens_cache_write=0,
                                                                 total_tokens=sum(usage), reasoning_tokens=300), error=None, model="gemini-3.1-pro-preview", stop_reason=stop)


class Offline(unittest.TestCase):
    def setUp(self):
        self._c = socket.socket.connect
        socket.socket.connect = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network"))

    def tearDown(self):
        socket.socket.connect = self._c


class EffectiveSettingsTests(Offline):
    def test_config_block_and_the_request_inspect_builds(self):
        c = cfg_judge()
        self.assertEqual((c["model"], c["temperature"], c["max_tokens"], c["max_retries"], c["reasoning_effort"]), ("google/gemini-3.1-pro-preview", 1.0, 16384, 10, "high"))  # max_retries 3 -> 10 (V1.2, approved 2026-11-01)
        self.assertEqual(c["prompt_sha256"], J.ProviderJudge("google/x").prompt_sha256)
        from inspect_ai.model import GenerateConfig
        from inspect_ai.model._providers.google import GoogleGenAIAPI
        pj = J.ProviderJudge(c["model"], **{k: c[k] for k in ("temperature", "max_tokens", "max_retries", "reasoning_effort")})
        gc = GenerateConfig(**{k: v for k, v in pj.generate_params.items() if v is not None})
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-not-real-KEY0"}, clear=False):
            api = GoogleGenAIAPI(model_name="gemini-3.1-pro-preview", base_url=None, api_key=None, config=GenerateConfig())
            tc = api.chat_thinking_config(gc)
        self.assertEqual((str(tc.thinking_level), tc.include_thoughts, tc.thinking_budget), ("ThinkingLevel.HIGH", True, None))
        self.assertEqual((gc.temperature, gc.max_tokens, gc.max_retries), (1.0, 16384, 10))  # Inspect's own retry count (V1.2)
        self.assertEqual(pj._model_args, {})  # nothing forwarded to google.genai


class GuardAndFailureTests(Offline):
    def test_cost_guard_stops_before_the_request_and_never_fails_an_item(self):
        sent = []
        def gen(messages):
            sent.append(1); return output('{"verdict": "pass", "evidence": [{"file": "f.xlsx", "location": "A1", "quote": "x"}], "rationale": "ok"}')
        state = {"n": 0}
        def guard(chars):
            state["n"] += 1
            return "pass 1 ceiling would be exceeded" if state["n"] > 1 else None
        pj = J.ProviderJudge("google/gemini-3.1-pro-preview", generate=gen, cost_guard=guard)
        vs = J.judge_units([unit(1), unit(2), unit(3)], pj)
        self.assertEqual(len(sent), 1)
        self.assertEqual([v["verdict"] for v in vs], ["pass", "cannot_assess", "cannot_assess"])
        self.assertEqual([v["error_class"] for v in vs[1:]], ["not_attempted", "not_attempted"])
        self.assertIn("budget stop", pj.halted)

    def test_truncated_and_malformed_responses_are_assessment_failures(self):
        for text, stop in (("", "max_tokens"), ('{"verdict": "pass"', "max_tokens"), ("The item passes.", "stop")):
            pj = J.ProviderJudge("google/gemini-3.1-pro-preview", generate=lambda m, t=text, s=stop: output(t, s))
            v = J.judge_units([unit()], pj)[0]
            with self.subTest(text=text):
                self.assertEqual((v["verdict"], v["error_class"]), ("cannot_assess", "invalid_judge_output"))  # engine .8: one schema retry, both invalid
                self.assertEqual((len(pj.calls), len(v["schema_attempts"])), (2, 2))
                self.assertEqual(pj.calls[0]["stop_reason"], stop)

    def test_call_record_fields(self):
        pj = J.ProviderJudge("google/gemini-3.1-pro-preview", temperature=1.0, max_tokens=16384, max_retries=3, reasoning_effort="high",
                             generate=lambda m: output('{"verdict": "fail", "evidence": [{"file": "f.xlsx", "location": "A1", "quote": "x"}], "rationale": "r"}'))
        J.judge_units([unit()], pj)
        c = pj.calls[0]
        self.assertEqual((c["served_model"], c["stop_reason"], c["prompt_sha256"], c["generate_params"]["reasoning_effort"], c["evidence_builder"]),
                         ("gemini-3.1-pro-preview", "stop", pj.prompt_sha256, "high", "grading.judge.build_units_x@x-1"))
        self.assertTrue(c["request_sha256"] and c["usage"])


class SeparateJudgeLedgerGateTests(unittest.TestCase):
    """A separate judge ledger: unrelated open reservations of the generation ledger do not block; open units of the
    judge ledger and the run's own open units do."""

    def test_gate(self):
        import tempfile
        from harness.budget import BudgetLedger
        from grading import run_grading as RG
        prices = {"google/x": {"input": 1, "output": 1, "cache_read": 1, "cache_write": 1}}
        with tempfile.TemporaryDirectory() as d:
            gen = BudgetLedger(os.path.join(d, "dev", "ledger.json"), 100, prices, label="dev")
            jl = BudgetLedger(os.path.join(d, "judge_dev", "ledger.json"), 30, prices, label="judge_dev")
            host = os.path.join(d, "run"); os.makedirs(host)
            binding = {"run_uuid": "RUN", "generation_unit_id": "gen-RUN", "ledger_path": gen.path, "ledger_id": gen.identity()["ledger_id"]}
            gen.reserve("other-unit", "sample", 5, {"model": "m", "task": "t"})  # another run's generation unit in flight
            RG.declare_judge_ledger(host, "RUN", jl, "test")
            out = os.path.join(d, "out"); os.makedirs(out)
            RG.judge_history_gate(gen, binding, out, "RUN", False, host_dir=host, prices=prices, reservation_ledger=jl)  # no block
            with self.assertRaisesRegex(RG.GradingCliError, "open reservation"):
                RG.judge_history_gate(gen, binding, out, "RUN", False, host_dir=host, prices=prices)  # without the separate ledger: blocked as before
            jl.reserve("RUN:judge:x", "judge", 1, {"kind": "judge"})
            with self.assertRaisesRegex(RG.GradingCliError, "open reservation"):
                RG.judge_history_gate(gen, binding, out, "RUN", False, host_dir=host, prices=prices, reservation_ledger=jl)  # the run's open judge unit blocks


class GuardTierTests(unittest.TestCase):
    """The guard prices calls at the long-context rates, an upper bound of the ledger's settlement of the unit."""

    def test_guard_uses_long_context_rates(self):
        from unittest import mock
        from decimal import Decimal
        from grading import judge_dev as JD
        usage = {"input_tokens": 20_000, "output_tokens": 1_000}
        self.assertGreater(JD.call_cost_usd(usage, "long"), JD.call_cost_usd(usage))
        std_total = JD.call_cost_usd(usage) * 10
        long_total = JD.call_cost_usd(usage, "long") * 10
        nxt = JD.worst_case_usd(3_000, 16_384, "long")
        cap = std_total + nxt + Decimal("0.01")  # enough at standard rates, not at long-context rates
        self.assertLess(cap, long_total + nxt)
        j = SimpleNamespace(calls=[{"usage": usage}] * 10)
        cfg = JD.cfg(); cfg["judge"]["ceilings_usd"] = {"pass_1": str(cap), "judge_dev_aggregate": "30"}
        env = {"GOOGLE_API_KEY": "x" + JD.DEV_KEY_SUFFIX}
        with mock.patch.object(JD, "cfg", return_value=cfg), mock.patch.dict(os.environ, env, clear=False):
            for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
                os.environ.pop(k, None)
            guard = JD.make_guard({"judge": j}, 16_384, {"pass_1": Decimal(0), "aggregate": Decimal(0)})
            self.assertRegex(guard(3_000) or "", "Pass 1 ceiling")


class Pass2GuardTests(unittest.TestCase):
    """Pass 2: the plan's own ceiling is checked before every call, beside the Pass 1 and aggregate ceilings."""

    def test_pass_ceiling_refuses_before_the_call(self):
        from unittest import mock
        from decimal import Decimal
        from grading import judge_dev as JD
        cfg = JD.cfg(); cfg["judge"]["ceilings_usd"] = {"pass_1": "20", "judge_dev_aggregate": "30"}
        nxt = JD.worst_case_usd(7_000, 16_384, "long")
        with mock.patch.object(JD, "cfg", return_value=cfg), mock.patch.dict(os.environ, {"GOOGLE_API_KEY": "x" + JD.DEV_KEY_SUFFIX}, clear=False):
            for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
                os.environ.pop(k, None)
            base = {"pass_1": Decimal(0), "aggregate": Decimal(0)}
            tight = JD.make_guard({"judge": SimpleNamespace(calls=[])}, 16_384, base, ("judge-dev-pass-2", Decimal("0.90"), Decimal("1.0")))
            self.assertRegex(tight(7_000) or "", "judge-dev-pass-2 ceiling")  # 0.90 spent + the worst case of the next call > 1.0
            roomy = JD.make_guard({"judge": SimpleNamespace(calls=[])}, 16_384, base, ("judge-dev-pass-2", Decimal(0), nxt + Decimal("0.01")))
            self.assertIsNone(roomy(7_000))

    def test_pass2_refuses_an_uncommitted_plan(self):
        from unittest import mock
        from grading import judge_dev as JD
        dirty = SimpleNamespace(stdout=" M grading/judge_dev/pass2_plan.json\n")
        with mock.patch.object(JD.subprocess, "run", return_value=dirty):
            with self.assertRaises(SystemExit):
                JD.run_pass2()


class AddendumTests(unittest.TestCase):
    """Runs that become eligible after the plan get one append-only addendum; the frozen repeat subset is untouched."""

    def test_add_eligible(self):
        import tempfile
        from unittest import mock
        from grading import judge_dev as JD
        with tempfile.TemporaryDirectory() as d:
            plan = os.path.join(d, "pass1_plan.json")
            with open(plan, "w") as f:
                json.dump({"eligible_runs": [{"task_id": "t1", "run_uuid": "A", "judge_items": 2}], "self_consistency": {"units": [["A", 1]]}}, f)
            runs = [{"task_id": "t1", "run_uuid": "A", "judge_items": [1, 2]}, {"task_id": "t2", "run_uuid": "B", "judge_items": [3, 4, 5]}]
            with mock.patch.object(JD, "PLAN", plan), mock.patch.object(JD, "ADDENDA", os.path.join(d, "addenda")), \
                    mock.patch.object(JD, "eligible_runs", return_value=(runs, ["t3"])):
                add = JD.add_eligible()
                self.assertEqual([r["run_uuid"] for r in add["eligible_runs"]], ["B"])
                self.assertEqual(add["added_judge_units"], 3)
                self.assertEqual(JD.planned_runs(json.load(open(plan))), {"A", "B"})
                self.assertIsNone(JD.add_eligible())  # nothing new: no second file
                self.assertEqual(len(os.listdir(os.path.join(d, "addenda"))), 1)


if __name__ == "__main__":
    unittest.main()
