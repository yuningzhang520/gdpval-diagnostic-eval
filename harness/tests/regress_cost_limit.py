"""Inspect 0.3.286 per-sample cost limit, triggered for real with mockllm (no paid model).

Mechanism checked here: cost data is attached to the mock model with set_model_info(...,
ModelInfo(cost=ModelCost(...))) (mock models are not in Inspect's model database, so
set_model_cost()/model_cost_config would raise); eval(cost_limit=X) opens a cost limit; after each
generate call Inspect prices the usage, records it (record_model_cost) and calls
check_cost_limit(), which raises LimitExceededError type "cost" and records a SampleLimitEvent of
type "cost" with the configured limit and a message carrying the running value. Two cases:
(a) the limit fires after the first tool call has written files → limited + complete;
(b) the limit fires before any tool runs → limited + no_files_confirmed. Both must be
grading-eligible under the budget policy ("cost" in BUDGET_LIMIT_TYPES) with the limit type
and amounts recorded in run_outcome.json.
Usage: harness/tests/run_isolated.sh <root> harness.tests.regress_cost_limit --output-root <new dir>"""
import argparse
import json
import os
from pathlib import Path

assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1", "use run_isolated.sh"
from harness.smoke import M, done, fixture_files, tc  # noqa: E402

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import ModelCost, ModelInfo, get_model, get_model_info, set_model_info  # noqa: E402

from harness import collect as c  # noqa: E402
from harness.task import make_task  # noqa: E402

WRITE = "mkdir -p /output/final; printf A > /output/final/a.txt; printf B > /output/final/b.txt; ls /output/final"
MOCK_PRICE = ModelCost(input=1000.0, output=1000.0, input_cache_write=1000.0, input_cache_read=1000.0)  # synthetic: 1,000 USD per MTok


def binding_from_log(log, sample):
    return {"uuid": sample.uuid, "model": log.eval.model, "task_id": log.eval.task_id, "eval_id": log.eval.eval_id, "sample_id": sample.id, "epoch": sample.epoch}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--output-root", required=True); args = p.parse_args()
    root = Path(args.output_root); root.mkdir(parents=True, exist_ok=False)
    checks = []
    def check(name, ok, detail=None):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:300] if detail is not None else None})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:200]}" if detail is not None and not ok else ""))

    check("mock model has no cost data before registration (fail-closed precondition)", (get_model_info(M) is None) or (get_model_info(M).cost is None))
    set_model_info(M, ModelInfo(organization="mock", model="model", cost=MOCK_PRICE))
    info = get_model_info(M)
    check("cost data registered for the mock model", info is not None and info.cost is not None and info.cost.input == 1000.0)

    def responder(messages, tools, choice, config):
        if any(m.role == "tool" for m in messages):
            return tc("bash", command="echo again")  # keep calling until the cost limit stops the sample
        return tc("bash", command=WRITE)

    evidence = []
    for name, limit in (("a_cost_limit_after_files", 2.0), ("b_cost_limit_before_tool", 0.5)):
        task, runs = make_task([Sample(id="synthetic-s1", input="Execute the cost-limit probe.", files=fixture_files())], str(root / "runs" / name), name=f"cost_{name}")
        log = inspect_eval(task, model=get_model(M, custom_outputs=responder), log_dir=str(root / "inspect"), sandbox_prebuilt=True, sandbox_cleanup=True,
                           display="plain", log_level="warning", max_samples=1, max_tasks=1, task_retry_attempts=0, cost_limit=limit)[0]
        sample = log.samples[0]
        host = Path(runs) / sample.uuid
        out = c.load_run_outcome(str(host), binding_from_log(log, sample), for_grading=False)
        limit_events = [e for e in sample.events if e.event == "sample_limit"]
        tool_events = [e for e in sample.events if e.event == "tool"]
        print(f"\n######## {name}: cost_limit={limit} sample.limit={sample.limit.type if sample.limit else None} "
              f"tool_events={len(tool_events)} usage={ {k: (v.input_tokens, v.output_tokens, getattr(v, 'total_cost', None)) for k, v in (sample.model_usage or {}).items()} } "
              f"→ execution={out['execution']['status']} collection={out['collection_status']} eligible={out['grading_eligible']} class={out['outcome_class']}")
        check(f"{name}: Inspect recorded sample.limit.type == cost with the configured limit", sample.limit is not None and sample.limit.type == "cost" and sample.limit.limit == limit, sample.limit)
        check(f"{name}: SampleLimitEvent of type cost with a dollar message", any(e.type == "cost" and "$" in e.message for e in limit_events), [(e.type, e.message) for e in limit_events])
        check(f"{name}: outcome execution limited with limit_types == ['cost'] and the amount in the message",
              out["execution"]["status"] == "limited" and out["execution"]["limit_types"] == ["cost"] and any("limit: $" in l["message"] for l in out["execution"]["limits"]), out["execution"]["limits"])
        check(f"{name}: sample usage carries total_cost", any(getattr(v, "total_cost", None) for v in (sample.model_usage or {}).values()))
        expected_collection = "complete" if name.startswith("a_") else "no_files_confirmed"
        check(f"{name}: collection_status == {expected_collection}", out["collection_status"] == expected_collection, out["collection_status"])
        check(f"{name}: grading_eligible true (budget type), harness_error false", out["grading_eligible"] is True and out["harness_error"] is False, (out["grading_eligible"], out["outcome_class"]))
        evidence.append({"case": name, "cost_limit": limit, "log": log.location, "sample_limit": sample.limit.model_dump() if sample.limit else None,
                         "limit_events": [{"type": e.type, "limit": e.limit, "message": e.message} for e in limit_events],
                         "model_usage": {k: v.model_dump() for k, v in (sample.model_usage or {}).items()}, "outcome": str(host / "run_outcome.json"),
                         "execution": out["execution"], "collection_status": out["collection_status"], "grading_eligible": out["grading_eligible"], "outcome_class": out["outcome_class"]})
    (root / "results.json").write_text(json.dumps({"checks": checks, "evidence": evidence, "mock_price_per_mtok_usd": MOCK_PRICE.model_dump()}, indent=1, default=str))
    failed = [x for x in checks if x["result"] != "PASS"]
    print(f"\n==== COST LIMIT {len(checks) - len(failed)} PASS, {len(failed)} FAIL; results {root / 'results.json'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
