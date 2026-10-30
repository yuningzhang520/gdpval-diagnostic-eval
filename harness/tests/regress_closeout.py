"""Narrow B1-B3 final-outcome regressions. Run via run_isolated.sh, mockllm and prebuilt Docker only.

Use --output-root for a NEW log directory. A caller may override task.COMPOSE with an external
pinned existing-image configuration before main(); no image is built by this module.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
from unittest.mock import patch

assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1", "use run_isolated.sh"
from harness import smoke as sm, task as ht, collect as c  # guards before Inspect initialization
from inspect_ai import eval as inspect_eval
from inspect_ai.dataset import Sample
from inspect_ai.model import get_model

CHECKS = []


def check(name, passed, detail=None):
    CHECKS.append({"check": name, "pass": bool(passed), "detail": detail})
    print(f"{'PASS' if passed else 'FAIL'} {name}")
    if not passed:
        raise AssertionError(name)


def snapshot(path):
    p = Path(path); st = p.stat()
    return {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "inode": st.st_ino, "mtime_ns": st.st_mtime_ns}


def binding_from_log(log, sample):
    return {"uuid": sample.uuid, "model": log.eval.model, "task_id": log.eval.task_id,
            "eval_id": log.eval.eval_id, "sample_id": sample.id, "epoch": sample.epoch}


COMMON = "mkdir -p /output/final; printf A > /output/final/a.txt; printf B > /output/final/b.txt"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=False)
    evidence = []

    def evaluate(name, *, task=None, score=True, error=False, epochs=1, command=COMMON, simulate=None, observe=None):
        task, runs = (task, str(root / "runs" / name)) if task else ht.make_task(
            [Sample(id="synthetic-s1", input="Execute the synthetic probe.")], str(root / "runs" / name),
            name="closeout_" + name, run_id="label-only", time_limit=45, _simulate_read_failure=simulate)
        if observe:
            original = task.cleanup
            async def cleanup(state):
                await observe(state, runs)
                await original(state)
            task.cleanup = cleanup
        def response(messages, tools, choice, config):
            if any(m.role == "tool" for m in messages):
                if error:
                    raise RuntimeError("synthetic closeout generation failure")
                return sm.done()
            return sm.tc("bash", command=command)
        log = inspect_eval(task, model=get_model("mockllm/model", custom_outputs=response), score=score, epochs=epochs,
                           log_dir=str(root / "inspect"), sandbox_prebuilt=True, sandbox_cleanup=True, display="plain",
                           log_level="warning", max_samples=1, max_tasks=1, task_retry_attempts=0)[0]
        outcomes = []
        for sample in log.samples:
            binding = binding_from_log(log, sample)
            host = Path(runs) / sample.uuid
            outcome = c.load_run_outcome(str(host), binding, for_grading=False)
            outcomes.append(outcome)
            check(name + ": full binding matches actual eval log", outcome["run"] == binding)
            manifest = json.loads((host / "run.json").read_text())
            check(name + ": bound on first trusted solver state", manifest["first_bound_phase"] == "solver" and manifest["run"] == binding)
            check(name + ": actual Inspect ToolEvent", any(e.event == "tool" for e in sample.events))
            check(name + ": no capability metrics", not log.results or all(not s.metrics for s in log.results.scores))
            for score_value in (sample.scores or {}).values():
                check(name + ": provisional unscored event", math.isnan(score_value.value) and score_value.reason == "provisional_collection_only"
                      and score_value.metadata["provisional"] is True)
            evidence.append({"case": name, "binding": binding, "inspect_status": log.status, "log": log.location,
                             "score_events": sum(e.event == "score" for e in sample.events),
                             "collection_status": outcome["collection_status"], "execution_status": outcome["execution"]["status"],
                             "harness_error": outcome["harness_error"], "outcome": str(host / "run_outcome.json")})
        return log, outcomes

    log, outcomes = evaluate("listing_failed", command="mkdir -p /output/final; chmod 000 /output/final")
    out = outcomes[0]
    check("listing_failed: final harness error", out["collection_status"] == "listing_failed" and out["harness_error"])
    check("listing_failed: scorer and cleanup both attempted", len(out["collection"]["passes"]) == 2)
    try:
        c.load_run_outcome(str(Path(evidence[-1]["outcome"]).parent), out["run"])
        accepted = True
    except c.OutcomeValidationError:
        accepted = False
    check("listing_failed: grading gate refuses model non-delivery", not accepted)

    before = {}
    async def before_resume(state, runs):
        host = Path(runs) / state.uuid
        before["a"] = snapshot(host / "final/a.txt")
        before["binding"] = c.run_binding(state)
        before["collection"] = json.loads((host / "collection.json").read_text())
        check("resume: scorer outcome not yet authoritative", not (host / "run_outcome.json").exists())
    log, outcomes = evaluate("resume", simulate={"/output/final/b.txt"}, observe=before_resume)
    out = outcomes[0]; host = Path(evidence[-1]["outcome"]).parent
    check("resume: final complete without collection error", out["collection_status"] == "complete" and not out["harness_error"])
    check("resume: passes partial then complete", [p["status"] for p in out["collection"]["passes"]] == ["partial", "complete"])
    check("resume: first per-file failure retained", "read_failed" in json.dumps(out["collection"]["passes"][0]["files"]))
    check("resume: first artifact bytes/inode/mtime preserved", before["a"] == snapshot(host / "final/a.txt"))
    check("resume: scorer/cleanup binding identical", before["binding"] == out["run"])
    check("resume: historical score remains partial", next(iter(log.samples[0].scores.values())).answer == "partial")
    check("resume: final gate accepts recovered delivery", c.load_run_outcome(str(host), out["run"])["grading_eligible"])

    for name, score, error in [("score_false", False, False), ("generation_error", True, True)]:
        log, outcomes = evaluate(name, score=score, error=error)
        sample, out = log.samples[0], outcomes[0]
        check(name + ": scorer never executed", not sample.scores and not out["execution"]["collector_scorer_executed"] and
              not any(e.event == "score" for e in sample.events))
        check(name + ": cleanup collected files", out["collection_status"] == "complete" and out["collection"]["file_count"] == 2 and
              out["collection"]["passes"][0]["note"] == "collected in cleanup (scorer did not run)")
        check(name + ": execution attribution preserved", out["execution"]["status"] == ("error" if error else "completed") and
              out["grading_eligible"] is not error)
        if error:
            check(name + ": actual error linked to Inspect event", sample.error is not None and log.status == "error" and
                  out["execution"]["errors"][0]["event_uuid"] in [e.uuid for e in sample.events if e.event == "error"])

    timeout_task, _ = ht.make_task([Sample(id="synthetic-s1", input="Execute timeout probe.")],
                                  str(root / "runs/sample_timeout"), name="sample_timeout", time_limit=2)
    log, outcomes = evaluate("sample_timeout", task=timeout_task, command=COMMON + "; sleep 10")
    check("sample_timeout: limit is not normal completion", log.samples[0].limit is not None and
          log.samples[0].limit.type == "time" and outcomes[0]["execution"]["status"] == "limited" and
          outcomes[0]["execution"]["limit_types"] == ["time"])
    check("sample_timeout: budget exhaustion with complete collection is grading-eligible (policy of 2026-10-30)",
          outcomes[0]["grading_eligible"] is True and outcomes[0]["outcome_class"] == "collected" and
          not outcomes[0]["harness_error"])
    check("sample_timeout: pre-limit artifacts preserved", outcomes[0]["collection_status"] == "complete" and
          outcomes[0]["collection"]["file_count"] == 2)

    real_sandbox = c.sandbox
    class MalformedEnumeration:
        def __init__(self): self.sb = real_sandbox()
        async def exec(self, *a, **kw):
            result = await self.sb.exec(*a, **kw)
            value = json.loads(result.stdout.strip().splitlines()[-1]); value["entries"] = [42]
            result.stdout = json.dumps(value)
            return result
        async def read_file(self, *a, **kw): raise AssertionError("malformed listing must not read any file")
    with patch.object(c, "sandbox", MalformedEnumeration):
        log, outcomes = evaluate("malformed")
    check("entries=[42]: final listing_failed", outcomes[0]["collection_status"] == "listing_failed" and outcomes[0]["harness_error"])
    check("entries=[42]: recorded schema reason", "listing_output_invalid" in json.dumps(outcomes[0]["collection"]["passes"]))

    async def identity_conflicts(state, runs):
        host = Path(runs) / state.uuid
        binding = c.run_binding(state)
        before = {p.name: p.read_bytes() for p in host.iterdir() if p.is_file()}
        for key, value in [("model", "mockllm/other"), ("task_id", "synthetic-other-task"), ("epoch", 99)]:
            try:
                c.bind_run(str(host), {**binding, key: value}, None, "cleanup")
                refused = False
            except c.OutcomeValidationError:
                refused = True
            check("same UUID changed " + key + ": refused with original records intact", refused and
                  before == {p.name: p.read_bytes() for p in host.iterdir() if p.is_file()})
    evaluate("identity_conflicts", observe=identity_conflicts)

    shared, _ = ht.make_task([Sample(id="synthetic-s1", input="Execute probe.")], str(root / "runs/repeated"), name="repeated")
    first, out1 = evaluate("repeated", task=shared)
    first_path = Path(evidence[-1]["outcome"]).parent / "final/a.txt"
    first_bytes = snapshot(first_path)
    second, out2 = evaluate("repeated", task=shared)
    check("independent actual evals of SAME Task: different UUID directories", out1[0]["run"]["uuid"] != out2[0]["run"]["uuid"])
    check("independent eval: earlier artifact unchanged", first_bytes == snapshot(first_path))

    grid, _ = ht.make_task([Sample(id="synthetic-s1", input="Execute probe."), Sample(id="synthetic-s2", input="Execute probe.")],
                           str(root / "runs/grid"), name="grid")
    log, outcomes = evaluate("grid", task=grid, epochs=2)
    check("different samples and epochs: four UUID directories", len({o["run"]["uuid"] for o in outcomes}) == 4 and
          {(o["run"]["sample_id"], o["run"]["epoch"]) for o in outcomes} == {(s, e) for s in ("synthetic-s1", "synthetic-s2") for e in (1, 2)})
    (root / "results.json").write_text(json.dumps({"checks": CHECKS, "evidence": evidence}, indent=2))
    print(f"CLOSEOUT {len(CHECKS)}/{len(CHECKS)} PASS")


if __name__ == "__main__":
    main()
