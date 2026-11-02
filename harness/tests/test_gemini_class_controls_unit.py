"""Gemini dev / validation class controls approved 2026-11-01: per-class Google credentials (dev GOOGLE_API_KEY,
validation GOOGLE_API_KEY_VALIDATION, separate Paid Tier 1 projects), Inspect GenerateConfig.max_retries 10 for those
two classes only, and the recovered-429/5xx settlement (reported usage + one average metered call, inferred, no hold).
Offline: synthetic keys only, socket connects blocked, no provider, Docker or .env of the repository is read.
Run: python -m unittest harness.tests.test_gemini_class_controls_unit -v"""
import asyncio
import json
import os
import socket
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from inspect_ai.model import ModelUsage

from harness import budget as b
from harness import launcher as L
from harness import unit_gate as G

CONFIG = os.path.join(L.ROOT, "config.json")
GEM = "google/gemini-3.8-flash"
DEV_KEY = "synthetic-dev-project-key-not-real-DEV1"
VAL_KEY = "synthetic-validation-project-key-not-real-VAL2"
DOTENV_KEY = "synthetic-dotenv-key-not-real-ENV3"
PRICES = {GEM: {"input": 0.75, "output": 3.75, "cache_read": 0.075, "cache_write": 0.75}}


def cfg():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


class _Offline(unittest.TestCase):
    def setUp(self):
        self._connect = socket.socket.connect

        def deny(*a, **k):
            raise AssertionError("network use attempted in an offline test")

        socket.socket.connect = deny
        self.tmp = tempfile.TemporaryDirectory(prefix="gemini_controls_")
        self.root = os.path.realpath(self.tmp.name)

    def tearDown(self):
        socket.socket.connect = self._connect
        self.tmp.cleanup()


# ----------------------------------------------------------------------------------------------- credentials
class CredentialSelectionTests(_Offline):
    def batch(self, label):
        return L.batch_controls(cfg(), label)

    def test_config_maps_each_gemini_class_to_its_own_variable_and_candidates_to_none(self):
        self.assertEqual(self.batch("dev")["credential_env"], {"google": "GOOGLE_API_KEY"})
        self.assertEqual(self.batch("validation")["credential_env"], {"google": "GOOGLE_API_KEY_VALIDATION"})
        self.assertEqual(self.batch("compat")["credential_env"], {})

    def test_selection_sets_only_this_process_environment_and_returns_names_and_suffix(self):
        env = {"GOOGLE_API_KEY": DEV_KEY, "GOOGLE_API_KEY_VALIDATION": VAL_KEY, "VSCODE_PID": "1", "VSCODE_CWD": "/x", "TERM_PROGRAM": "vscode"}
        scheduler_env = dict(env)
        child = dict(scheduler_env)  # the scheduler hands each unit a copy ({**os.environ}); the copy is what changes
        c = L.select_credential("google", self.batch("validation"), child)
        self.assertEqual((child["GOOGLE_API_KEY"], c["variable"], c["provider_variable"], c["suffix"]), (VAL_KEY, "GOOGLE_API_KEY_VALIDATION", "GOOGLE_API_KEY", "VAL2"))
        self.assertEqual(sorted(c["dotenv_override_markers_removed"]), ["TERM_PROGRAM", "VSCODE_CWD", "VSCODE_PID"])
        self.assertFalse(any(k in child for k in ("VSCODE_PID", "VSCODE_CWD", "TERM_PROGRAM")))
        self.assertEqual(scheduler_env["GOOGLE_API_KEY"], DEV_KEY)  # the parent's environment is untouched
        self.assertNotIn(VAL_KEY, json.dumps(c)); self.assertNotIn(DEV_KEY, json.dumps(c))
        dev_child = dict(scheduler_env)
        d = L.select_credential("google", self.batch("dev"), dev_child)
        self.assertEqual((dev_child["GOOGLE_API_KEY"], d["variable"], d["suffix"]), (DEV_KEY, "GOOGLE_API_KEY", "DEV1"))

    def test_fail_closed_on_missing_variable_or_an_override_the_sdk_would_prefer(self):
        with self.assertRaisesRegex(L.LauncherError, "missing credential variable GOOGLE_API_KEY_VALIDATION"):
            L.select_credential("google", self.batch("validation"), {"GOOGLE_API_KEY": DEV_KEY})
        for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI"):
            with self.subTest(k=k), self.assertRaisesRegex(L.LauncherError, k):
                L.select_credential("google", self.batch("dev"), {"GOOGLE_API_KEY": DEV_KEY, k: "1"})
        # a dry run never needs the credential: it is reported, not required
        c = L.select_credential("google", self.batch("validation"), {}, required=False)
        self.assertIsNone(c["suffix"])

    def _client_key_after_inspect_dotenv(self, label, *, scrub=True):
        """The production order inside one unit process: the launcher selects the credential, Inspect's eval() runs its
        .env initialisation (cwd holds a .env with a third synthetic key), then the Google provider builds its client."""
        work = os.path.join(self.root, f"cwd_{label}_{scrub}")
        os.makedirs(work)
        Path(work, ".env").write_text(f"GOOGLE_API_KEY={DOTENV_KEY}\n")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.root, "GOOGLE_API_KEY": DEV_KEY, "GOOGLE_API_KEY_VALIDATION": VAL_KEY, "VSCODE_PID": "4242", "VSCODE_CWD": work}
        cwd = os.getcwd()
        with mock.patch.dict(os.environ, env, clear=True):
            os.chdir(work)
            try:
                if scrub:
                    c = L.select_credential("google", self.batch(label), os.environ)
                    check = L.verify_credential_after_dotenv(c)
                else:  # what would happen without the marker removal: the selection is replaced by .env
                    os.environ["GOOGLE_API_KEY"] = os.environ[self.batch(label)["credential_env"]["google"]]
                    check = None
                from inspect_ai._util.dotenv import init_dotenv
                from inspect_ai.model import GenerateConfig
                from inspect_ai.model._providers.google import GoogleGenAIAPI
                init_dotenv()  # eval() -> init_runtime_context() -> init_dotenv(), again
                api = GoogleGenAIAPI(model_name="gemini-3.8-flash", base_url=None, api_key=None, config=GenerateConfig())
                client = api.model_client(api._http_options(GenerateConfig(timeout=60)))
                return client._api_client.api_key, check
            finally:
                os.chdir(cwd)

    def test_the_selected_key_reaches_the_google_genai_client_through_inspects_dotenv_initialisation(self):
        key, check = self._client_key_after_inspect_dotenv("validation")
        self.assertEqual(key, VAL_KEY); self.assertEqual((check["checked"], check["inspect_dotenv_applied"], check["suffix"]), (True, True, "VAL2"))
        key, check = self._client_key_after_inspect_dotenv("dev")
        self.assertEqual(key, DEV_KEY); self.assertEqual(check["suffix"], "DEV1")

    def test_negative_control_without_marker_removal_inspect_would_replace_the_selection(self):
        key, _ = self._client_key_after_inspect_dotenv("validation", scrub=False)
        self.assertEqual(key, DOTENV_KEY)  # the hazard the marker removal closes

    def test_verify_refuses_when_the_provider_variable_does_not_hold_the_selection(self):
        with self.assertRaisesRegex(L.LauncherError, "credential check failed"):
            L.verify_credential_after_dotenv({"provider_variable": "GOOGLE_API_KEY", "variable": "GOOGLE_API_KEY_VALIDATION", "suffix": "VAL2"}, {"GOOGLE_API_KEY": DEV_KEY})
        with self.assertRaisesRegex(L.LauncherError, "credential check failed"):
            L.verify_credential_after_dotenv({"provider_variable": "GOOGLE_API_KEY", "variable": "GOOGLE_API_KEY_VALIDATION", "suffix": "VAL2"}, {"GOOGLE_API_KEY": VAL_KEY, "VSCODE_PID": "1"})


# ----------------------------------------------------------------------------------------------- retries
class GeminiRetryLimitTests(_Offline):
    def test_dev_and_validation_carry_max_retries_10_and_candidates_inherit_3(self):
        c = cfg()
        for label, expected in (("dev", 10), ("validation", 10), ("compat", 3)):
            bc = L.batch_controls(c, label)
            model = GEM if label != "compat" else "anthropic/claude-opus-5-5"
            kw = L.eval_kwargs(c, log_dir="/x", model=model, cost_limit_override=bc["cost_limit_usd"], message_limit_override=bc["message_limit"], max_retries_override=bc["inspect_max_retries"])
            with self.subTest(label=label):
                self.assertEqual(kw["max_retries"], expected)
                if model == GEM:
                    self.assertEqual(kw["model_args"], {})  # nothing is forwarded to google.genai
        self.assertEqual(c["retries"]["layer_1_inspect_model_request"]["max_retries"], 3)  # the candidate default is unchanged
        self.assertNotIn("inspect_max_retries", c["batches"]["compat"]); self.assertNotIn("inspect_max_retries", c["batches"]["formal"])

    def test_the_value_is_a_generate_config_field_and_inspects_own_stop_allows_10_retries(self):
        from inspect_ai.model import GenerateConfig
        from inspect_ai.model._retry import model_retry_config
        from tenacity import AsyncRetrying, wait_none
        self.assertEqual(GenerateConfig(max_retries=10).max_retries, 10)
        rc = model_retry_config("gemini-3.8-flash", 10, None, lambda ex: True, lambda ex: None, lambda *a, **k: None, wait=wait_none(), live_overrides=False, report_retry_wait=False)
        attempts = []

        async def go():
            async for attempt in AsyncRetrying(**rc, reraise=True):
                with attempt:
                    attempts.append(1)
                    raise RuntimeError("synthetic 429")

        with self.assertRaises(RuntimeError):
            asyncio.run(go())
        self.assertEqual(len(attempts), 11)  # 10 retries = 11 attempts, Inspect's documented semantics

    def test_bad_values_refuse(self):
        for bad in (-1, "10", True, 2.5):
            c = cfg(); c["batches"]["dev"]["inspect_max_retries"] = bad
            with self.subTest(bad=bad), self.assertRaisesRegex(L.LauncherError, "inspect_max_retries"):
                L.batch_controls(c, "dev")


# ----------------------------------------------------------------------------------------------- settlement
def ev(usage=None, *, traceback=None, error=None, msg_id=None):
    out = SimpleNamespace(usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(id=msg_id))] if msg_id else [])
    return SimpleNamespace(event="model", model=GEM, retries=None, output=out, traceback=traceback, error=error)


U = ModelUsage(input_tokens=100_000, output_tokens=2_000)
TB429 = "Traceback (most recent call last):\n  ...\ngoogle.genai.errors.ClientError: 429 RESOURCE_EXHAUSTED. {'error': {'code': 429}}"
TB503 = "Traceback ...\ngoogle.genai.errors.ServerError: 503 UNAVAILABLE. {'error': {'code': 503}}"
TB400 = "Traceback ...\ngoogle.genai.errors.ClientError: 400 INVALID_ARGUMENT. Request payload limit 500 MB; retry in 429 ms"
TB_CHAINED = "Traceback ...\ngoogle.genai.errors.ServerError: 503 UNAVAILABLE.\n\nDuring handling ...\ngoogle.genai.errors.ClientError: 400 INVALID_ARGUMENT."


def sample(events, *, uuid="runA"):
    total = ModelUsage(input_tokens=sum(e.output.usage.input_tokens for e in events if e.output.usage), output_tokens=sum(e.output.usage.output_tokens for e in events if e.output.usage))
    msgs = [SimpleNamespace(role="assistant", id=e.output.choices[0].message.id) for e in events if e.output.usage and e.output.choices]
    return SimpleNamespace(model_usage={GEM: total}, events=events, messages=msgs, uuid=uuid, error=None)


class RecoveredAttemptClassificationTests(unittest.TestCase):
    def test_429_and_5xx_followed_by_a_metered_call_are_recovered(self):
        s = sample([ev(U, msg_id="a1"), ev(traceback=TB429), ev(traceback=TB503), ev(U, msg_id="a2")])
        r = b.recovered_attempts(s)
        self.assertEqual((r["unknown"], r["recovered"]), (2, 2)); self.assertEqual([a["status"] for a in r["attempts"]], [429, 503])

    def test_other_status_trailing_failure_unknown_cause_or_transcript_presence_are_not(self):
        cases = {"400": [ev(U, msg_id="a1"), ev(traceback=TB400), ev(U, msg_id="a2")],
                 "last exception 400": [ev(U, msg_id="a1"), ev(traceback=TB_CHAINED), ev(U, msg_id="a2")],
                 "last call": [ev(U, msg_id="a1"), ev(traceback=TB429)],
                 "no traceback": [ev(U, msg_id="a1"), ev(), ev(U, msg_id="a2")],
                 "in transcript": [ev(U, msg_id="a1"), ev(traceback=TB429, msg_id="a1"), ev(U, msg_id="a2")]}
        for name, evs in cases.items():
            with self.subTest(name):
                r = b.recovered_attempts(sample(evs))
                self.assertEqual((r["unknown"], r["recovered"]), (1, 0))


class RecoveredSettlementTests(_Offline):
    def ledger(self):
        return b.BudgetLedger(os.path.join(self.root, "dev", "ledger.json"), 100, PRICES, label="dev")

    def test_ledger_inferred_buffer_is_one_average_metered_call_with_no_hold(self):
        lg = self.ledger(); lg.reserve("u", "sample", "5.00", {"model": GEM, "task": "t"})
        calls = {GEM: [b.model_usage_to_dict(U), b.model_usage_to_dict(U)]}
        usage = {GEM: b.model_usage_to_dict(ModelUsage(input_tokens=200_000, output_tokens=4_000))}
        st = lg.settle("u", usage, calls_by_model=calls, scope={"same_sample": True}, recovered={"unknown": 1, "recovered": 1, "attempts": [{"index": 1, "status": 429, "recovered": True}]})
        per_call = Decimal("0.100000") * Decimal("0.75") + Decimal("0.002") * Decimal("3.75")  # 0.0825 USD per call
        self.assertEqual(Decimal(st["cost_usd"]), per_call * 3)  # 2 metered calls + 1 average-call buffer
        # engine .10 (Codex Review 2 R2-B3): the inferred amount is an estimate (basis: the buffer alone); still no hold
        self.assertEqual((st["estimated"], st["estimate_basis"], st["manual_review_required"], st["inferred"]["buffer_usd"], st["inferred"]["reconciliation_required"]),
                         (True, ["inferred_buffer"], False, "0.082500", "provider dashboard"))
        self.assertEqual(lg.snapshot()["review_pending_units"], [])
        self.assertTrue(any(f.startswith("inferred:") for f in st["flags"]))

    def test_hold_and_incomplete_win_over_a_recovered_claim(self):
        lg = self.ledger(); lg.reserve("u", "sample", "5.00", {"model": GEM, "task": "t"})
        st = lg.settle("u", {GEM: b.model_usage_to_dict(U)}, calls_by_model={GEM: [b.model_usage_to_dict(U)]}, scope={"same_sample": True}, incomplete=True,
                       recovered={"unknown": 1, "recovered": 1})
        self.assertEqual((st["cost_usd"], st["estimated"], st["manual_review_required"], st["inferred"]), ("5.000000", True, True, None))


class RecoveredSettlementLauncherTests(_Offline):
    """The run_sample transitions: recovered attempts on a usable unit -> inferred, no hold, gate continue; the same
    events without the class policy, on an unusable outcome or with an unrecovered usage-less call -> estimated + hold."""

    def launcher(self, *, policy=True, outcome=None, events=None, label="dev"):
        os.makedirs(os.path.join(self.root, label), exist_ok=True)
        runs = tempfile.mkdtemp(prefix="runs_", dir=os.path.join(self.root, label))
        lg = b.BudgetLedger(os.path.join(runs, "ledger.json"), 100, PRICES, label=label)
        s = sample(events or [ev(U, msg_id="a1"), ev(traceback=TB429), ev(U, msg_id="a2")])

        def fake_eval(task, **kw):
            if outcome is not None:
                os.makedirs(os.path.join(runs, s.uuid), exist_ok=True)
                Path(runs, s.uuid, "run_outcome.json").write_text(json.dumps(outcome))
            return [SimpleNamespace(status="success", error=None, samples=[s], location="/synthetic/log.eval")]

        c = cfg()
        return L.PilotLauncher(c, runs_root=runs, ledger=lg, eval_fn=fake_eval, run_label=label, recovered_retry_settlement=policy,
                               max_retries_override=L.batch_controls(c, label)["inspect_max_retries"]), lg, runs

    OK = {"final": True, "execution": {"status": "limited", "limit_types": ["token"]}, "grading_eligible": True, "harness_error": False, "requires_adjudication": False,
          "collection": {"status": "complete", "file_count": 4}}

    def run_one(self, **kw):
        la, lg, runs = self.launcher(**kw)
        meta = la.run_sample(task=SimpleNamespace(name="dev_47ef842d"), model=GEM, unit_id="unit-1", estimate_usd="5.00", task_id="t")
        inv = [json.loads(l) for l in Path(runs, "run_inventory.jsonl").read_text(encoding="utf-8").splitlines()]
        return meta, lg, inv[-1], runs

    def test_recovered_429_on_a_usable_unit_is_inferred_without_a_hold(self):
        meta, lg, inv, runs = self.run_one(outcome=self.OK)
        st = meta["settlement"]
        self.assertEqual((st["estimated"], st["manual_review_required"], bool(st["inferred"])), (True, False, True))  # engine .10 (R2-B3): estimated, no hold
        self.assertEqual(Decimal(st["cost_usd"]), Decimal("0.082500") * 3)
        self.assertEqual(meta["eval_kwargs"]["max_retries"], 10)
        self.assertEqual((inv["inferred"], inv["estimated"], inv["estimate_basis"], inv["manual_review_required"], inv["inspect_max_retries"]), (True, True, ["inferred_buffer"], False, 10))
        self.assertEqual(inv["recovered_attempts"], {"unknown": 1, "recovered": 1, "applied": True})
        self.assertEqual(lg.snapshot()["review_pending_units"], [])
        self.assertTrue(meta["recovered_attempts"]["applied"]); self.assertEqual(meta["recovered_attempts"]["attempts"][0]["status"], 429)
        gate = G.evaluate_unit(runs, inv, gemini=True)
        self.assertTrue(gate["inferred"]); self.assertNotIn("settlement estimated, held for manual review, or a stop was recorded", gate["reasons"])  # the approved no-hold policy
        stop = "settlement estimated, held for manual review, or a stop was recorded"
        self.assertIn(stop, G.evaluate_unit(runs, {**inv, "estimate_basis": ["inferred_buffer", "inspect_cost_floor"]}, gemini=True)["reasons"])  # any other estimate basis still stops
        self.assertIn(stop, G.evaluate_unit(runs, {k: v for k, v in inv.items() if k != "estimate_basis"}, gemini=True)["reasons"])  # a record without a basis: estimated meant another cause

    def test_the_no_hold_exception_needs_exactly_the_inferred_buffer_basis(self):
        """Codex delta review N1 (engine .12): an empty, missing, unknown or mixed basis, or a basis without the inferred
        settlement, is no inferred-buffer-only estimate; the other fail-closed reasons stop whatever the basis."""
        meta, lg, inv, runs = self.run_one(outcome=self.OK)
        stop = "settlement estimated, held for manual review, or a stop was recorded"
        reasons = lambda rec: G.evaluate_unit(runs, rec, gemini=True)["reasons"]
        self.assertNotIn(stop, reasons(inv))  # exactly ["inferred_buffer"] with its inferred settlement: the approved no-hold policy
        for basis in ([], None, ["unknown_reason"], ["inferred_buffer", "usage_conflict"], "inferred_buffer"):
            self.assertIn(stop, reasons({**inv, "estimate_basis": basis}), basis)  # engine .11: [] was accepted
        self.assertIn(stop, reasons({**inv, "inferred": False}))
        for k, v in (("manual_review_required", True), ("stop_recorded", "synthetic stop")):
            self.assertIn(stop, reasons({**inv, k: v}), k)
        self.assertNotIn(stop, reasons({**inv, "estimated": False, "estimate_basis": []}))  # no estimate at all: nothing to except

    def test_without_the_class_policy_the_same_unit_is_held(self):
        meta, lg, inv, _ = self.run_one(policy=False, outcome=self.OK)
        self.assertEqual((meta["settlement"]["estimated"], meta["settlement"]["manual_review_required"], meta["settlement"]["cost_usd"]), (True, True, "5.000000"))
        self.assertEqual(lg.snapshot()["review_pending_units"], ["unit-1"]); self.assertNotIn("recovered_attempts", meta)

    def test_unusable_outcomes_and_unrecovered_missing_usage_keep_the_hold(self):
        bad = {"message limit": {**self.OK, "execution": {"status": "limited", "limit_types": ["message"]}},
               "collection partial": {**self.OK, "collection": {"status": "partial", "file_count": 2}},
               "no files": {**self.OK, "collection": {"status": "complete", "file_count": 0}},
               "error": {**self.OK, "execution": {"status": "error", "limit_types": []}},
               "not final": {**self.OK, "final": False}}
        for name, oc in bad.items():
            with self.subTest(name):
                meta, lg, inv, _ = self.run_one(outcome=oc)
                self.assertEqual((meta["settlement"]["manual_review_required"], meta["recovered_attempts"]["applied"]), (True, False))
        with self.subTest("no run outcome"):
            meta, *_ = self.run_one(outcome=None)
            self.assertTrue(meta["settlement"]["manual_review_required"])
        with self.subTest("one recovered, one unknown"):
            meta, *_ = self.run_one(outcome=self.OK, events=[ev(U, msg_id="a1"), ev(traceback=TB429), ev(), ev(U, msg_id="a2")])
            self.assertEqual((meta["settlement"]["manual_review_required"], meta["recovered_attempts"]["recovered"], meta["recovered_attempts"]["unknown"]), (True, 1, 2))


class ValidationRealRunCliTests(_Offline):
    """main(--real-run) for the validation class with an injected environment, a synthetic env file holding both
    project keys, a fake docker runner and an injected eval: the eval sees the validation key in GOOGLE_API_KEY and
    max_retries 10; the records carry the variable name and suffix only."""
    TASK = "47ef842d-8eac-4b90-bda8-dd934c228c96"

    def test_validation_unit_gets_its_own_key_and_the_records_hold_names_and_suffixes_only(self):
        c = cfg()
        runs = os.path.join(self.root, "validation", "runs"); os.makedirs(runs)
        env_file = os.path.join(self.root, "env.test")
        Path(env_file).write_text(f"GOOGLE_API_KEY={DEV_KEY}\nGOOGLE_API_KEY_VALIDATION={VAL_KEY}\n")
        docker = lambda cmd, **kw: SimpleNamespace(returncode=0, stdout=f"{c['sandbox']['image_id']}|arm64|linux|[]\n", stderr="")
        seen = []

        def fake_eval(task, **kw):
            seen.append({"key": env.get("GOOGLE_API_KEY"), "max_retries": kw["max_retries"], "model_args": kw["model_args"]})
            u = ModelUsage(input_tokens=1000, output_tokens=200)
            s_ = SimpleNamespace(model_usage={GEM: u}, events=[SimpleNamespace(event="model", model=GEM, retries=None, output=SimpleNamespace(usage=u))], messages=[], uuid="v1", error=None)
            return [SimpleNamespace(status="success", error=None, samples=[s_], location="/synthetic/log.eval")]

        env = {"VSCODE_PID": "7"}
        argv = ["--config", CONFIG, "--run-label", "validation", "--runs-root", runs, "--ledger", os.path.join(self.root, "validation", "ledger.json"), "--task-id", self.TASK,
                "--model", GEM, "--estimate-usd", "5.00", "--env-file", env_file, "--real-run", "--confirm", f"{self.TASK}|{GEM}|5.00", "--authorized-by", "test", "--authorization-ref", "unit-test"]
        self.assertEqual(L.main(argv, eval_fn=fake_eval, environ=env, docker_runner=docker), 0)
        self.assertEqual(seen, [{"key": VAL_KEY, "max_retries": 10, "model_args": {}}])
        recs = {f: json.loads(Path(runs, "launcher_records", f).read_text()) for f in os.listdir(os.path.join(runs, "launcher_records"))}
        prov = next(v for k, v in recs.items() if "_real_run_provenance_" in k)
        self.assertEqual({k: prov["credential"][k] for k in ("variable", "provider_variable", "suffix")}, {"variable": "GOOGLE_API_KEY_VALIDATION", "provider_variable": "GOOGLE_API_KEY", "suffix": "VAL2"})
        self.assertEqual(prov["credential_check"]["suffix"], "VAL2"); self.assertFalse(prov["credential_check"]["inspect_dotenv_applied"])
        inv = json.loads(Path(runs, "run_inventory.jsonl").read_text().splitlines()[-1])
        self.assertEqual((inv["credential"], inv["inspect_max_retries"]), ({"variable": "GOOGLE_API_KEY_VALIDATION", "suffix": "VAL2"}, 10))
        for f in Path(self.root).rglob("*"):
            if f.is_file() and f.name != "env.test":
                text = f.read_text(errors="replace")
                self.assertNotIn(VAL_KEY, text, f); self.assertNotIn(DEV_KEY, text, f)


if __name__ == "__main__":
    unittest.main()
