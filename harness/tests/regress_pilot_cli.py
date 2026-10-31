"""Pilot A wiring U1 mock regression: the real CLI path ``harness.launcher.main --real-run`` with the real
Inspect ``eval`` and the docker sandbox, driven by mockllm with scripted tool calls (no paid provider;
INSPECT_DISABLE_MODEL_API=1 stays set in the process, imported through harness.smoke, so every provider
except mockllm raises; the environment dict handed to main() omits that variable only so the real-run
guard can be exercised). The temporary env file holds a synthetic key; the project .env is never read.
mockllm is given the Opus price data for the Inspect cost-limit check only (test-time monkeypatch); the
ledger itself has no price for mockllm, so the settlement must be the conservative unpriced path.
Produces a real run directory and a real .eval that the U2 grading-CLI regression consumes.
Usage: harness/tests/run_isolated.sh <project_root> harness.tests.regress_pilot_cli --output-root <new dir>"""
import argparse
import json
import os

from harness.smoke import M, done, tc  # noqa: E402  (guards set at import)

from inspect_ai import eval as inspect_eval  # noqa: E402

from harness import launcher as H  # noqa: E402

ROOT = os.environ.get("HARNESS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--output-root", required=True); args = ap.parse_args()
    out = os.path.realpath(args.output_root); os.makedirs(out, exist_ok=False)
    runs = os.path.join(out, "runs"); os.makedirs(runs)
    env_file = os.path.join(out, "env.test")
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("ANTHROPIC_API_KEY=dummy-test-key-not-real-0004\n")
    env = {k: v for k, v in os.environ.items() if k != "INSPECT_DISABLE_MODEL_API"}  # the guard variable stays set in the real process
    original_cost_config = H.model_cost_config
    H.model_cost_config = lambda c: {**original_cost_config(c), M: original_cost_config(c)["anthropic/claude-opus-5-5"]}  # test-only pricing for the cost limit
    calls = []

    def mock_eval(task, **kw):
        calls.append({"task": task.name, "kwargs": sorted(kw)})
        kw["model_args"] = {**kw.get("model_args", {}), "custom_outputs": [tc("bash", command="mkdir -p /output/final && printf 'pilot cli mock deliverable' > /output/final/note.txt && ls -la /output/final"), done("Produced /output/final/note.txt")]}
        kw.update(display="plain", log_level="warning")
        return inspect_eval(task, **kw)

    argv = ["--runs-root", runs, "--ledger", os.path.join(out, "ledger.json"), "--task-id", TASK, "--model", M, "--estimate-usd", "1", "--env-file", env_file,
            "--real-run", "--confirm", f"{TASK}|{M}|1", "--authorized-by", "mock-regression", "--authorization-ref", "harness/tests/regress_pilot_cli.py"]
    rc = H.main(argv, eval_fn=mock_eval, environ=env)
    check("main --real-run returned 0 through the real Inspect eval with mockllm", rc == 0 and len(calls) == 1, (rc, calls))
    evals = sorted(f for f in os.listdir(os.path.join(runs, "inspect_logs")) if f.endswith(".eval")) if os.path.isdir(os.path.join(runs, "inspect_logs")) else []
    check("exactly one .eval written under runs_root/inspect_logs", len(evals) == 1, evals)
    run_dirs = [d for d in os.listdir(runs) if d not in ("inspect_logs", "launcher_records") and os.path.isdir(os.path.join(runs, d))]
    check("exactly one run directory (TaskState uuid)", len(run_dirs) == 1, run_dirs)
    run_dir = os.path.join(runs, run_dirs[0]) if run_dirs else None
    outcome = json.load(open(os.path.join(run_dir, "run_outcome.json"))) if run_dir and os.path.exists(os.path.join(run_dir, "run_outcome.json")) else None
    check("run_outcome.json written by cleanup and note.txt collected", bool(outcome) and os.path.exists(os.path.join(run_dir, "final", "note.txt")), (run_dir, list(outcome or {})[:8]))
    check("collected deliverable has the scripted content", run_dir is not None and open(os.path.join(run_dir, "final", "note.txt")).read() == "pilot cli mock deliverable")
    records = {f: json.load(open(os.path.join(runs, "launcher_records", f))) for f in os.listdir(os.path.join(runs, "launcher_records"))}
    prov = next((v for k, v in records.items() if "_real_run_provenance_" in k), None)
    check("real_run_provenance record: commit, config sha, prompt form, image id, authorization, sample id", bool(prov) and prov["code"]["commit"] and prov["config_sha256"] and prov["prompt"]["matched_form"] == "stripped_text"
          and prov["image_id"] and prov["authorization"]["by"] == "mock-regression" and prov["sample_ids"] == [TASK], {k: (prov or {}).get(k) for k in ("config_sha256", "image_id", "sample_ids")})
    sample = next((v for k, v in records.items() if "_sample_" in k and "_sample_error_" not in k and "_sample_cardinality_" not in k), None)
    st = (sample or {}).get("settlement") or {}
    check("settlement is the conservative unpriced path (estimated, manual review) because the ledger prices no mock model",
          st.get("estimated") is True and st.get("manual_review_required") is True and any("estimated_unknown_cost" in f for f in st.get("flags", [])), {k: st.get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags")})
    check("inspect status success and single-sample contract satisfied", (sample or {}).get("inspect_status") == "success" and "sample_count" not in (sample or {}), (sample or {}).get("inspect_status"))
    leaked = [str(p) for p in __import__("pathlib").Path(out).rglob("*") if p.is_file() and p.name != "env.test" and "dummy-test-key-not-real-0004" in p.read_text(errors="replace")]
    check("no synthetic key value in any produced file (the test's own env file is the only holder)", leaked == [], leaked)
    ledger = json.load(open(os.path.join(out, "ledger.json")))
    check("ledger: one reservation and one settlement for the unit", [e["type"] for e in ledger["entries"]] == ["reservation", "settlement"], [e["type"] for e in ledger["entries"]])
    manifest = {"run_dir": run_dir, "eval_log": os.path.join(runs, "inspect_logs", evals[0]) if evals else None, "ledger": os.path.join(out, "ledger.json"), "unit_id": (sample or {}).get("unit_id"), "task_id": TASK, "model": M}
    with open(os.path.join(out, "pilot_cli_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": CHECKS, "manifest": manifest, "eval_calls": calls}, f, indent=1, default=str)
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== PILOT CLI {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {os.path.join(out, 'results.json')}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
