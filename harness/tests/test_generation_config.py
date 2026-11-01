"""Pilot A/B generation configuration (approved 2026-11-01): the explicit reasoning settings reach the provider
adapters as the launcher passes them. Offline: provider objects are constructed with dummy keys, socket connects are
blocked, and the OpenAI client call is replaced by a recorder that captures the request body and never sends it.
What stays REAL PROVIDER UNVERIFIED: the effort level each provider actually applies and the usage it reports."""
import asyncio
import json
import os
import socket
import unittest

from harness import launcher as L

CONFIG = os.path.join(L.ROOT, "config.json")
PROBE_TEXT = "Please say 'hello, world'"  # inspect_ai 0.3.286 openai.py reasoning_summaries(): the account probe request


class _Offline(unittest.TestCase):
    def setUp(self):
        self._connect = socket.socket.connect

        def deny(*a, **k):
            raise AssertionError("network use attempted in an offline test")

        socket.socket.connect = deny

    def tearDown(self):
        socket.socket.connect = self._connect


class EvalKwargsReasoningTests(_Offline):
    def test_eval_kwargs_carry_the_approved_reasoning_settings_as_valid_generate_config_fields(self):
        cfg = L.load_config(CONFIG)
        kw = L.eval_kwargs(cfg, log_dir="/x", model="anthropic/claude-opus-5-5")
        self.assertEqual((kw["reasoning_effort"], kw["reasoning_summary"], kw["max_tokens"]), ("high", "none", 32000))
        self.assertEqual((kw["time_limit"], kw["working_limit"], kw["message_limit"], kw["token_limit"], kw["cost_limit"]), (7200, 7200, 200, 20_000_000, 20.0))
        self.assertEqual((kw["max_retries"], kw["timeout"], kw["attempt_timeout"], kw["model_args"]), (3, 2700, 900, {"max_retries": 0}))
        from inspect_ai.model import GenerateConfig
        fields = ("max_tokens", "reasoning_effort", "reasoning_summary", "max_retries", "timeout", "attempt_timeout")
        gc = GenerateConfig(**{k: kw[k] for k in fields})  # exactly what eval(**kwargs) builds: pydantic validation must accept it
        self.assertEqual((gc.reasoning_effort, gc.reasoning_summary, gc.max_tokens), ("high", "none", 32000))
        # identical for both candidates: the kwargs differ only in the model name
        kw_b = L.eval_kwargs(cfg, log_dir="/x", model="openai/gpt-6.1-sol")
        self.assertEqual({k: v for k, v in kw.items() if k != "model_cost_config"}, {k: v for k, v in kw_b.items() if k != "model_cost_config"})

    def test_missing_or_unknown_reasoning_literals_refuse_before_any_call(self):
        cfg = L.load_config(CONFIG)
        for field, bad in (("reasoning_effort", "maximum"), ("reasoning_effort", None), ("reasoning_summary", "auto-detect"), ("reasoning_summary", 1)):
            c = json.loads(json.dumps(cfg))
            c["generation"][field] = bad
            with self.subTest(field=field, bad=bad), self.assertRaisesRegex(L.LauncherError, field):
                L.eval_kwargs(c, log_dir="/x", model="openai/gpt-6.1-sol")


class AnthropicMappingTests(_Offline):
    """inspect_ai 0.3.286 anthropic.py completion_config: frontier Claude + reasoning_effort -> adaptive thinking with
    output_config.effort, and the output-128k beta when max_tokens exceeds 8192."""

    def api(self):
        from inspect_ai.model import GenerateConfig
        from inspect_ai.model._providers.anthropic import AnthropicAPI
        return AnthropicAPI("claude-opus-5-5", api_key="dummy-not-a-real-key-offline", config=GenerateConfig(), max_retries=0)

    def test_high_effort_becomes_adaptive_thinking_with_output_config_high(self):
        from inspect_ai.model import GenerateConfig
        api = self.api()
        cfg = L.load_config(CONFIG)
        kw = L.eval_kwargs(cfg, log_dir="/x", model="anthropic/claude-opus-5-5")
        gc = GenerateConfig(max_tokens=kw["max_tokens"], reasoning_effort=kw["reasoning_effort"], reasoning_summary=kw["reasoning_summary"])
        params, extra_body, headers, betas = api.completion_config(gc)
        self.assertEqual((params["model"], params["max_tokens"]), ("claude-opus-5-5", 32000))
        self.assertEqual(params["thinking"], {"type": "adaptive", "display": "summarized"})
        self.assertEqual(dict(params["output_config"]), {"effort": "high"})
        self.assertIn("output-128k-2025-02-19", betas)
        self.assertTrue(api.is_using_thinking(gc))
        self.assertFalse(api.is_using_extended_thinking(gc))  # no budget_tokens path on Claude 5
        self.assertFalse(api._supports_disabling_thinking())  # Opus 5.5 always thinks; "none" could not switch it off
        self.assertEqual(api.client.max_retries, 0)  # layer-2 SDK retries off, as model_args requests
        # the pre-approval state (no effort configured): neither thinking nor output_config nor the output-128k beta is sent
        p0, _, _, b0 = api.completion_config(GenerateConfig(max_tokens=32000))
        self.assertNotIn("thinking", p0)
        self.assertNotIn("output_config", p0)
        self.assertNotIn("output-128k-2025-02-19", b0)
        # Inspect's own sizing for high effort would be 48,000 output tokens; the explicit 32,000 is a deliberate shared cap
        self.assertEqual(api.max_tokens_for_config(GenerateConfig(reasoning_effort="high")), 48000)

    def test_reasoning_tokens_budget_is_refused_up_front_on_claude_5(self):
        from inspect_ai.model import GenerateConfig
        from inspect_ai._util.error import PrerequisiteError
        with self.assertRaises(PrerequisiteError):
            self.api().completion_config(GenerateConfig(max_tokens=32000, reasoning_tokens=8000))


class OpenAIRequestTests(_Offline):
    """inspect_ai 0.3.286 openai.py / openai_responses.py: gpt-6.1-sol takes the Responses API; the request body is
    captured by replacing client.responses.create with a recorder that never sends."""

    class Trap(Exception):
        pass

    def api(self):
        from inspect_ai.model import GenerateConfig
        from inspect_ai.model._providers.openai import OpenAIAPI
        return OpenAIAPI("gpt-6.1-sol", api_key="dummy-not-a-real-key-offline", config=GenerateConfig(), max_retries=0)

    def capture(self, config):
        from inspect_ai.model import ChatMessageUser
        api = self.api()
        calls = []

        async def fake_create(**kwargs):
            calls.append(kwargs)
            raise OpenAIRequestTests.Trap("captured; nothing was sent")

        api.client.responses.create = fake_create
        self.assertEqual(api.client.max_retries, 0)

        async def run():
            try:
                return await api.generate([ChatMessageUser(content="Say hi.")], [], "auto", config)
            except OpenAIRequestTests.Trap:
                return "trapped"

        result = asyncio.run(run())
        return calls, result

    def test_high_effort_and_summary_none_produce_one_request_with_reasoning_effort_high(self):
        from inspect_ai.model import GenerateConfig
        cfg = L.load_config(CONFIG)
        kw = L.eval_kwargs(cfg, log_dir="/x", model="openai/gpt-6.1-sol")
        calls, _ = self.capture(GenerateConfig(max_tokens=kw["max_tokens"], reasoning_effort=kw["reasoning_effort"], reasoning_summary=kw["reasoning_summary"]))
        self.assertEqual(len(calls), 1)  # no account probe: reasoning_summary is set
        req = calls[0]
        self.assertEqual(req["model"], "gpt-6.1-sol")
        self.assertEqual(req["reasoning"], {"effort": "high"})  # no summary requested
        self.assertEqual(req["max_output_tokens"], 32000)
        self.assertIs(req["store"], False)
        self.assertIn("reasoning.encrypted_content", req["include"])  # stateless reasoning replay across the agent loop
        self.assertNotIn(PROBE_TEXT, json.dumps(req["input"], default=str))

    def test_unset_summary_would_send_an_unaccounted_probe_request_first(self):
        """The finding behind reasoning_summary=none: with the field unset the adapter sends a real low-effort request
        ("hello, world") to detect reasoning-summary support before the sample's first call. It is not a sample event
        and would not enter the ledger."""
        from inspect_ai.model import GenerateConfig
        calls, _ = self.capture(GenerateConfig(max_tokens=32000, reasoning_effort="high"))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["input"], PROBE_TEXT)
        self.assertEqual(calls[0]["reasoning"], {"effort": "low", "summary": "auto"})
        self.assertEqual(calls[1]["reasoning"], {"effort": "high"})  # after the (failed) probe the real request goes out without summaries


if __name__ == "__main__":
    unittest.main()
