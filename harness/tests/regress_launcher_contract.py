"""R6 regression (Codex extraction review, logs/extraction-review-0r3d__40/real-scope.json) through the REAL Inspect
eval with mockllm: the launcher is handed one Task, but the eval function it is wired to misbehaves and runs two
Tasks (the review's two-task scenario), so eval returns two EvalLogs with one executed sample each (1,000 and
1,000,000 input tokens). Before: the unit was settled from logs[0] at 0.004 USD and nothing stopped. Expected now:
both logs detected, both samples' usage recorded, no settlement, reservation kept open, engineering stop recorded,
manual review required, the next paid start refused, the refusal kept after a restart. Also: a list of tasks handed
to run_sample is refused before any call. No paid model: INSPECT_DISABLE_MODEL_API=1 is forced by harness.smoke at
import (every provider except mockllm raises) and the model is mockllm/model with scripted outputs; mockllm is
given the opus price data of config.json for the cost-limit check only (the real launcher refuses unpriced models).
Usage: harness/tests/run_isolated.sh <project_root> harness.tests.regress_launcher_contract --output-root <new dir>"""
import argparse
import copy
import json
import os

from harness.smoke import M  # noqa: E402  (sets the guards at import: INSPECT_DISABLE_MODEL_API, scrubbed credentials, dummy keys)

from inspect_ai import Task, eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ModelOutput, ModelUsage  # noqa: E402
from inspect_ai.solver import generate  # noqa: E402

from harness import budget as D  # noqa: E402
from harness import launcher as H  # noqa: E402

ROOT = os.environ.get("HARNESS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def responder(messages, tools, choice, config):
    text = str(messages[-1].content)
    n = 1000 if "first" in text else 1_000_000
    out = ModelOutput.from_content(M, "Synthetic response")
    out.usage = ModelUsage(input_tokens=n, output_tokens=0)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--output-root", required=True); args = ap.parse_args()
    out = os.path.realpath(args.output_root); os.makedirs(out, exist_ok=False)
    os.environ["XDG_CACHE_HOME"] = os.path.join(out, "cache"); os.environ["XDG_DATA_HOME"] = os.path.join(out, "data")
    cfg = H.load_config(os.path.join(ROOT, "config.json"))
    prices = H.prices_from_config(cfg); prices[M] = copy.deepcopy(prices["anthropic/claude-opus-5-5"])
    original_cost_config = H.model_cost_config
    H.model_cost_config = lambda c: {**original_cost_config(c), M: original_cost_config(c)["anthropic/claude-opus-5-5"]}  # test-only: price the mock model
    returned = []

    def misbehaving_eval(task, **kw):
        """Ignores the single Task it was given and runs two (the review's scenario); otherwise the launcher's kwargs."""
        kw["model_args"] = {**kw.get("model_args", {}), "custom_outputs": responder}
        kw.update(display="plain", log_level="warning", log_dir=os.path.join(out, "inspect"))
        tasks = [Task(name="contract_first", dataset=[Sample(id="one", input="synthetic first")], solver=generate()),
                 Task(name="contract_second", dataset=[Sample(id="two", input="synthetic second")], solver=generate())]
        result = inspect_eval(tasks, **kw)
        returned.extend(result)
        return result

    ledger = D.BudgetLedger(os.path.join(out, "ledger.json"), 100, prices)
    launcher = H.PilotLauncher(cfg, runs_root=os.path.join(out, "runs"), ledger=ledger, eval_fn=misbehaving_eval)
    single = Task(name="contract_single", dataset=[Sample(id="one", input="synthetic first")], solver=generate())
    meta = launcher.run_sample(task=single, model=M, unit_id="two-task-execution", estimate_usd=3)
    evidence = {"returned_logs": [{"task": l.eval.task, "status": l.status, "location": l.location, "samples": [{"uuid": s.uuid, "usage": {m: u.model_dump() for m, u in s.model_usage.items()}} for s in l.samples]} for l in returned],
                "meta": {k: meta.get(k) for k in ("settlement", "log_count", "sample_count", "all_sample_usage", "manual_review_required", "stop_recorded", "returned_logs", "inspect_status")}}
    check("real Inspect eval returned two EvalLogs, both success, one sample each", len(returned) == 2 and all(l.status == "success" and len(l.samples) == 1 for l in returned), [(l.status, len(l.samples)) for l in returned])
    check("launcher detected two logs and two samples", (meta.get("log_count"), meta.get("sample_count")) == (2, 2), (meta.get("log_count"), meta.get("sample_count")))
    usage = meta.get("all_sample_usage") or {}
    tokens = sorted(v.get(M, {}).get("input_tokens") for v in usage.values())
    check("both samples' usage recorded (1,000 and 1,000,000 input tokens)", tokens == [1000, 1_000_000], tokens)
    check("no settlement from the first log", meta.get("settlement") is None, meta.get("settlement"))
    snap = ledger.snapshot()
    check("reservation kept open at the estimate", (snap["reserved_usd"], snap["open_reservations"], snap["settled_usd"]) == ("3.000000", ["two-task-execution"], "0.000000"), {k: snap[k] for k in ("reserved_usd", "open_reservations", "settled_usd")})
    check("manual review required and an engineering stop recorded", meta.get("manual_review_required") is True and bool(ledger.stop_reasons()) and any("2 EvalLog(s) with 2 sample(s)" in r for r in ledger.stop_reasons()), ledger.stop_reasons())
    try:
        launcher.run_sample(task=single, model=M, unit_id="next", estimate_usd=1); blocked = False
    except D.BudgetExhausted:
        blocked = True
    check("next paid sample refused", blocked)
    restarted = H.PilotLauncher(cfg, runs_root=os.path.join(out, "runs-restart"), ledger=D.BudgetLedger(ledger.path, 100, prices), eval_fn=misbehaving_eval)
    try:
        restarted.run_sample(task=single, model=M, unit_id="after-restart", estimate_usd=1); blocked2 = False
    except D.BudgetExhausted:
        blocked2 = True
    check("refusal kept after a restart; reservation still open", blocked2 and restarted.ledger.snapshot()["open_reservations"] == ["two-task-execution"])
    check("sample_cardinality record written", any("_sample_cardinality_" in f for f in os.listdir(launcher.record_dir)))
    calls_before = len(returned)
    try:
        launcher2 = H.PilotLauncher(cfg, runs_root=os.path.join(out, "runs-list"), ledger=D.BudgetLedger(os.path.join(out, "ledger-list.json"), 100, prices), eval_fn=misbehaving_eval)
        launcher2.run_sample(task=[single, single], model=M, unit_id="list", estimate_usd=1); refused = False
    except H.LauncherError as ex:
        refused = "single-task contract" in str(ex)
    check("a list of tasks is refused before any call (no eval, no reservation)", refused and len(returned) == calls_before and launcher2.ledger.snapshot()["open_reservations"] == [])
    eval_files = sorted(f for f in os.listdir(os.path.join(out, "inspect")) if f.endswith(".eval")) if os.path.isdir(os.path.join(out, "inspect")) else []
    check("two .eval logs persisted under the output root", len(eval_files) == 2, eval_files)
    evidence["eval_files"] = eval_files
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": CHECKS, "evidence": evidence}, f, indent=1, default=str)
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== LAUNCHER CONTRACT {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {os.path.join(out, 'results.json')}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
