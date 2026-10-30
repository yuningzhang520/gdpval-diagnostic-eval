"""Execution-budget attribution regressions through the real Inspect Task + docker sandbox chain
with mockllm (no paid model; guards set by harness.smoke at import). Each scenario triggers a real
Inspect limit or error, then checks the final run_outcome.json published by Task.cleanup.

Scenarios (a–d are required; the rest are additional evidence):
  a. time_limit fires after valid deliverables exist     → limited, complete, grading_eligible
  b. time_limit fires before any file is written          → limited, no_files_confirmed, grading_eligible
  c. time_limit fires and the listing cannot be trusted   → harness_error, not grading_eligible
  d. generation error with complete collection            → error, not grading_eligible, error kept
  e. recovered single tool timeout                        → completed, grading_eligible
  f/g/h. message_limit / token_limit / working_limit probes: PASS only if Inspect actually recorded
         that limit type; otherwise reported UNVERIFIED (never claimed passed).

Usage: harness/tests/run_isolated.sh <project_root> harness.tests.regress_limits --output-root <new dir>
The output root must not exist (no earlier log is overwritten). Exit status 1 on any FAIL."""
import argparse
import json
import os
from pathlib import Path

assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1", "use run_isolated.sh"
from harness import smoke as sm, task as ht, collect as c  # noqa: E402  (guards before Inspect loads)

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402

CHECKS: list[dict] = []
EVIDENCE: list[dict] = []
WRITE_TWO = "mkdir -p /output/final; printf A > /output/final/a.txt; printf B > /output/final/b.txt"


def check(scenario: str, name: str, passed: bool, detail=None):
    CHECKS.append({"scenario": scenario, "check": name, "result": "PASS" if passed else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f"  -- {str(detail)[:200]}" if detail is not None and not passed else ""))


def unverified(scenario: str, name: str, detail):
    CHECKS.append({"scenario": scenario, "check": name, "result": "UNVERIFIED", "detail": str(detail)[:400]})
    print(f"  [UNVERIFIED] {name}  -- {str(detail)[:200]}")


def binding_from_log(log, sample):
    return {"uuid": sample.uuid, "model": log.eval.model, "task_id": log.eval.task_id,
            "eval_id": log.eval.eval_id, "sample_id": sample.id, "epoch": sample.epoch}


def responder(first_command: str, *, error_after_tool: bool = False, loop_forever: bool = False):
    def response(messages, tools, choice, config):
        if any(m.role == "tool" for m in messages):
            if error_after_tool:
                raise RuntimeError("synthetic provider failure after tool result")
            if loop_forever:
                return sm.tc("bash", command="echo again")
            return sm.done()
        return sm.tc("bash", command=first_command)
    return response


def run_case(root: Path, name: str, response, *, time_limit=None, tool_timeout=600, **eval_kw):
    task, runs = ht.make_task([Sample(id="synthetic-s1", input="Execute the synthetic probe.")], str(root / "runs" / name),
                              name=f"limits_{name}", time_limit=time_limit, tool_timeout=tool_timeout)
    log = inspect_eval(task, model=get_model("mockllm/model", custom_outputs=response), log_dir=str(root / "inspect"),
                       sandbox_prebuilt=True, sandbox_cleanup=True, display="plain", log_level="warning",
                       max_samples=1, max_tasks=1, task_retry_attempts=0, **eval_kw)[0]
    sample = log.samples[0]
    binding = binding_from_log(log, sample)
    host = Path(runs) / sample.uuid
    outcome = c.load_run_outcome(str(host), binding, for_grading=False)
    limit_events = [e for e in sample.events if e.event == "sample_limit"]
    error_events = [e for e in sample.events if e.event == "error"]
    tool_events = [e for e in sample.events if e.event == "tool"]
    print(f"\n######## {name}: inspect_status={log.status} sample.limit={sample.limit.type if sample.limit else None} "
          f"sample.error={'yes' if sample.error else 'no'} tool_events={len(tool_events)} limit_events={[e.type for e in limit_events]} "
          f"→ execution={outcome['execution']['status']} collection={outcome['collection_status']} "
          f"grading_eligible={outcome['grading_eligible']} class={outcome['outcome_class']}")
    EVIDENCE.append({"case": name, "log": log.location, "inspect_status": log.status, "binding": binding,
                     "sample_limit": {"type": sample.limit.type, "limit": sample.limit.limit} if sample.limit else None,
                     "sample_error": sample.error.message[:300] if sample.error else None,
                     "limit_events": [{"uuid": e.uuid, "type": e.type, "limit": e.limit, "message": e.message} for e in limit_events],
                     "error_events": [{"uuid": e.uuid, "message": e.error.message[:300]} for e in error_events],
                     "tool_errors": [{"function": e.function, "error": e.error.message[:200]} for e in tool_events if e.error],
                     "outcome_file": str(host / "run_outcome.json"), "execution": outcome["execution"],
                     "collection_status": outcome["collection_status"], "harness_error": outcome["harness_error"],
                     "grading_eligible": outcome["grading_eligible"], "outcome_class": outcome["outcome_class"],
                     "grading_basis": outcome["grading_basis"]})
    check(name, "final outcome identity equals the eval log identity", outcome["run"] == binding)
    check(name, "no capability metrics and only unscored provisional score events",
          (not log.results or all(not s.metrics for s in log.results.scores)) and
          all(v.reason == "provisional_collection_only" for v in (sample.scores or {}).values()))
    return log, sample, outcome, host, limit_events, error_events, tool_events


def gate_accepts(host: Path, binding: dict) -> bool:
    try:
        c.load_run_outcome(str(host), binding, for_grading=True)
        return True
    except c.OutcomeValidationError:
        return False


def limited_checks(name, sample, outcome, limit_events, kind):
    """Common assertions for a real Inspect budget limit of type ``kind``."""
    check(name, f"Inspect recorded sample.limit of type {kind}", sample.limit is not None and sample.limit.type == kind, sample.limit)
    check(name, "SampleLimitEvent present in the transcript", any(e.type == kind for e in limit_events), [e.type for e in limit_events])
    check(name, "execution.status == limited", outcome["execution"]["status"] == "limited", outcome["execution"]["status"])
    check(name, "outcome keeps the limit type and the Inspect event uuid",
          outcome["execution"]["limit_types"] == [kind] and
          {l["event_uuid"] for l in outcome["execution"]["limits"]} <= {e.uuid for e in limit_events}, outcome["execution"]["limits"])
    check(name, "no execution error recorded", outcome["execution"]["errors"] == [], outcome["execution"]["errors"])


def scenario_a(root):
    name = "a_time_limit_with_deliverables"
    log, sample, out, host, limits, errors, tools = run_case(root, name, responder(WRITE_TWO + "; sleep 20"), time_limit=3)
    limited_checks(name, sample, out, limits, "time")
    check(name, "collection_status == complete with both deliverables", out["collection_status"] == "complete" and out["collection"]["file_count"] == 2, out["collection_status"])
    check(name, "grading_eligible == true, harness_error == false, class collected",
          out["grading_eligible"] is True and out["harness_error"] is False and out["outcome_class"] == "collected", (out["grading_eligible"], out["outcome_class"]))
    check(name, "grading gate accepts the outcome", gate_accepts(host, out["run"]))
    check(name, "deliverables preserved on the host", all((host / "final" / f).read_bytes() == b for f, b in (("a.txt", b"A"), ("b.txt", b"B"))))
    check(name, "grading_basis names the budget", "budget exhausted (time)" in out["grading_basis"], out["grading_basis"])


def scenario_b(root):
    name = "b_time_limit_zero_files"
    log, sample, out, host, limits, errors, tools = run_case(root, name, responder("sleep 20"), time_limit=3)
    limited_checks(name, sample, out, limits, "time")
    check(name, "collection_status == no_files_confirmed", out["collection_status"] == "no_files_confirmed", out["collection_status"])
    # The sandbox image creates /output/final, so an untouched directory reports root_state "dir".
    check(name, "enumeration was reliable (empty or missing root, no listing errors, nothing skipped or rejected)",
          out["collection"]["listing_ok"] is True and out["collection"]["root_state"] in ("dir", "missing") and
          out["collection"]["listing_errors"] == [] and out["collection"]["skipped"] == [] and out["collection"]["rejected"] == []
          and out["collection"]["files"] == [], (out["collection"]["root_state"], out["collection"]["listing_errors"]))
    check(name, "grading_eligible == true, class no_deliverable_files_confirmed",
          out["grading_eligible"] is True and out["outcome_class"] == "no_deliverable_files_confirmed" and out["harness_error"] is False)
    check(name, "grading gate accepts the outcome (missing deliverables are graded as not delivered)", gate_accepts(host, out["run"]))


def scenario_c(root):
    name = "c_time_limit_with_listing_failed"
    cmd = "mkdir -p /output/final; printf A > /output/final/a.txt; chmod 000 /output/final; sleep 20"
    log, sample, out, host, limits, errors, tools = run_case(root, name, responder(cmd), time_limit=3)
    limited_checks(name, sample, out, limits, "time")
    check(name, "collection_status == listing_failed", out["collection_status"] == "listing_failed", out["collection_status"])
    check(name, "harness_error == true, grading_eligible == false, class harness_collection_error",
          out["harness_error"] is True and out["grading_eligible"] is False and out["outcome_class"] == "harness_collection_error")
    check(name, "not attributed to model non-delivery", out["collection_status"] != "no_files_confirmed" and out["collection"]["file_count"] == 0)
    check(name, "grading gate refuses the outcome", not gate_accepts(host, out["run"]))


def scenario_d(root):
    name = "d_generation_error_with_complete_collection"
    log, sample, out, host, limits, errors, tools = run_case(root, name, responder(WRITE_TWO, error_after_tool=True))
    check(name, "Inspect recorded a sample error and eval status error", sample.error is not None and log.status == "error", (log.status, sample.error and sample.error.message[:80]))
    check(name, "execution.status == error with the original error message and event uuid",
          out["execution"]["status"] == "error" and any("synthetic provider failure" in e["message"] for e in out["execution"]["errors"]) and
          {e["event_uuid"] for e in out["execution"]["errors"]} <= {e.uuid for e in errors}, out["execution"]["errors"])
    check(name, "collection_status == complete (cleanup collected both files)", out["collection_status"] == "complete" and out["collection"]["file_count"] == 2)
    check(name, "grading_eligible == false, harness_error == false, class execution_error",
          out["grading_eligible"] is False and out["harness_error"] is False and out["outcome_class"] == "execution_error", (out["grading_eligible"], out["outcome_class"]))
    check(name, "no limit recorded", out["execution"]["limits"] == [] and sample.limit is None)
    check(name, "grading gate refuses the outcome", not gate_accepts(host, out["run"]))


def scenario_e(root):
    name = "e_recovered_tool_timeout"
    log, sample, out, host, limits, errors, tools = run_case(root, name, responder(WRITE_TWO + "; sleep 20"), tool_timeout=3)
    check(name, "one ToolEvent carries a timeout error and the sample continued",
          any(e.error and "timed out" in e.error.message for e in tools) and sample.error is None and sample.limit is None,
          [(e.function, e.error and e.error.message[:60]) for e in tools])
    check(name, "execution.status == completed, no error, no limit", out["execution"]["status"] == "completed" and out["execution"]["errors"] == [] and out["execution"]["limits"] == [])
    check(name, "collection complete and grading_eligible", out["collection_status"] == "complete" and out["grading_eligible"] is True and out["outcome_class"] == "collected")


def probe_limit(root, name, kind, response, **eval_kw):
    """Budget types other than time: PASS only if Inspect really recorded that limit type."""
    try:
        log, sample, out, host, limits, errors, tools = run_case(root, name, response, **eval_kw)
    except Exception as ex:  # a crash is a FAIL, never UNVERIFIED
        check(name, "scenario ran without exception", False, f"{type(ex).__name__}: {ex}")
        return
    if sample.limit is None or sample.limit.type != kind or not any(e.type == kind for e in limits):
        unverified(name, f"{kind}_limit did not fire in the mock environment", f"sample.limit={sample.limit}, events={[e.type for e in limits]}")
        return
    limited_checks(name, sample, out, limits, kind)
    check(name, "collection status is complete or no_files_confirmed and grading_eligible",
          out["collection_status"] in ("complete", "no_files_confirmed") and out["grading_eligible"] is True and out["harness_error"] is False,
          (out["collection_status"], out["grading_eligible"]))
    check(name, "grading gate accepts the outcome", gate_accepts(host, out["run"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    parser.add_argument("scenarios", nargs="*", default=[])
    args = parser.parse_args()
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=False)
    scenarios = {
        "a": lambda: scenario_a(root), "b": lambda: scenario_b(root), "c": lambda: scenario_c(root), "d": lambda: scenario_d(root),
        "e": lambda: scenario_e(root),
        "f": lambda: probe_limit(root, "f_message_limit", "message", responder(WRITE_TWO, loop_forever=True), message_limit=6),
        "g": lambda: probe_limit(root, "g_token_limit", "token", responder(WRITE_TWO, loop_forever=True), token_limit=400),
        "h": lambda: probe_limit(root, "h_working_limit", "working", responder(WRITE_TWO + "; sleep 20"), working_limit=3),
    }
    for key in (args.scenarios or list(scenarios)):
        try:
            scenarios[key]()
        except Exception as ex:
            check(key, "scenario ran without exception", False, f"{type(ex).__name__}: {ex}")
    counts = {k: sum(1 for ch in CHECKS if ch["result"] == k) for k in ("PASS", "FAIL", "UNVERIFIED")}
    (root / "results.json").write_text(json.dumps({"checks": CHECKS, "evidence": EVIDENCE, "counts": counts,
                                                   "inspect_disable_model_api": os.environ.get("INSPECT_DISABLE_MODEL_API"),
                                                   "budget_limit_types": list(c.BUDGET_LIMIT_TYPES)}, indent=2, default=str))
    print(f"\n==== LIMITS {counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['UNVERIFIED']} UNVERIFIED; results {root / 'results.json'}")
    for ch in CHECKS:
        if ch["result"] != "PASS":
            print(f"{ch['result']} {ch['scenario']}: {ch['check']} -- {ch['detail']}")
    raise SystemExit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
