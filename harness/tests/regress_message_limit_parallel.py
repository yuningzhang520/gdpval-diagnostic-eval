"""Effective message limit per run class and two class processes in parallel (approved change 2026-11-01): the real
CLI path ``harness.launcher.main --real-run`` with the real Inspect eval and the docker sandbox, driven by mockllm
with 110 scripted bash tool calls, in two concurrent processes:
  dev     (config.batches.dev.message_limit null)   -> more than 200 messages, no limit event, execution completed;
  compat  (no override: generation.message_limit 200) -> limited by 'message' at exactly 200 messages.
Both processes run at the same time with their own runs root, ledger, inventory and log directory; their sandbox
containers must overlap in time. No paid provider: INSPECT_DISABLE_MODEL_API stays set in each process (every provider
except mockllm raises); the env file holds synthetic keys only.
Usage: harness/tests/run_isolated.sh <project_root> harness.tests.regress_message_limit_parallel --output-root <new dir>"""
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.environ.get("HARNESS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEV_TASK = "1137e2bb-bdf9-4876-b572-f29b7de5e595"
COMPAT_TASK = "87da214f-fd92-4c58-9854-f4d0d10adce0"
N_CALLS = 110


def role_main(role: str, out: str) -> int:
    from harness.smoke import M, done, tc  # noqa: F401  (guards set at import)
    from inspect_ai import eval as inspect_eval
    from harness import launcher as H
    label, task = ("dev", DEV_TASK) if role == "dev" else ("compat", COMPAT_TASK)
    runs = os.path.join(out, label, "runs"); os.makedirs(runs, exist_ok=True)
    cfg = json.load(open(os.path.join(out, "config.json")))
    env_file = os.path.join(out, "env.test")
    env = {k: v for k, v in os.environ.items() if k != "INSPECT_DISABLE_MODEL_API"}
    original = H.model_cost_config
    H.model_cost_config = lambda c: {**original(c), M: original(c)["anthropic/claude-opus-5-5"]}  # test-only pricing for the cost-limit check
    seen = {}

    def mock_eval(t, **kw):
        seen["message_limit"] = kw.get("message_limit", "<absent>")
        outputs = [tc("bash", command=f"echo call {i}") for i in range(N_CALLS)]
        outputs += [tc("bash", command="mkdir -p /output/final && printf 'mock deliverable' > /output/final/note.txt"), done("finished")]
        kw["model_args"] = {**kw.get("model_args", {}), "custom_outputs": outputs}
        kw.update(display="plain", log_level="warning")
        with open(os.path.join(out, f"{role}.timeline"), "a") as f:
            f.write(json.dumps({"ev": "eval_start", "t": time.time()}) + "\n")
        r = inspect_eval(t, **kw)
        with open(os.path.join(out, f"{role}.timeline"), "a") as f:
            f.write(json.dumps({"ev": "eval_end", "t": time.time()}) + "\n")
        return r

    argv = ["--config", os.path.join(out, "config.json"), "--run-label", label, "--runs-root", runs, "--ledger", os.path.join(out, label, "ledger.json"), "--task-id", task, "--model", M,
            "--estimate-usd", "1", "--env-file", env_file, "--real-run", "--confirm", f"{task}|{M}|1", "--authorized-by", "mock-regression", "--authorization-ref", __file__]
    rc = H.main(argv, eval_fn=mock_eval, environ=env)
    with open(os.path.join(out, f"{role}.result.json"), "w") as f:
        json.dump({"rc": rc, "message_limit_passed": seen.get("message_limit"), "cfg_dev_override": cfg["batches"]["dev"].get("message_limit", "<absent>")}, f)
    return rc


def check_all(out: str) -> list[dict]:
    from inspect_ai.log import read_eval_log
    checks = []

    def check(name, ok, detail=None):
        checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": None if detail is None else str(detail)[:400]})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok or detail is None else f" -- {str(detail)[:300]}"))
    res = {r: json.load(open(os.path.join(out, f"{r}.result.json"))) for r in ("dev", "compat") if os.path.exists(os.path.join(out, f"{r}.result.json"))}
    check("both role processes wrote a result", set(res) == {"dev", "compat"}, sorted(res))
    for role, label in (("dev", "dev"), ("compat", "compat")):
        r = res.get(role, {})
        runs = os.path.join(out, label, "runs")
        check(f"{role}: launcher returned 0", r.get("rc") == 0, r)
        evals = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(runs, "inspect_logs")) for f in fs if f.endswith(".eval")]
        check(f"{role}: exactly one .eval in its own runs root", len(evals) == 1, evals)
        if len(evals) != 1:
            continue
        log = read_eval_log(evals[0]); sample = log.samples[0]
        n = len(sample.messages); lim = sample.limit
        if role == "dev":
            check("dev: eval() received message_limit None", r.get("message_limit_passed") is None, r.get("message_limit_passed"))
            check("dev: the eval log records no message limit (config.message_limit is None)", log.eval.config.message_limit is None, log.eval.config.message_limit)
            check(f"dev: more than 200 messages ({n}) and no limit event", n > 200 and lim is None, (n, lim))
            check("dev: the other limits are unchanged (time 7200, token 20M, cost 10)", (log.eval.config.time_limit, log.eval.config.token_limit, log.eval.config.cost_limit) == (7200, 20_000_000, 10.0),
                  (log.eval.config.time_limit, log.eval.config.token_limit, log.eval.config.cost_limit))
        else:
            check("compat: eval() received message_limit 200", r.get("message_limit_passed") == 200, r.get("message_limit_passed"))
            check(f"compat: limited by 'message' at 200 messages ({n})", lim is not None and lim.type == "message" and n == 200, (n, lim))
        run_dirs = [d for d in os.listdir(runs) if os.path.isfile(os.path.join(runs, d, "run_outcome.json"))]
        check(f"{role}: one run directory with an outcome", len(run_dirs) == 1, run_dirs)
        if run_dirs:
            oc = json.load(open(os.path.join(runs, run_dirs[0], "run_outcome.json")))
            want = ("completed", []) if role == "dev" else ("limited", ["message"])
            check(f"{role}: run outcome {want}", ((oc["execution"]["status"]), sorted(oc["execution"].get("limit_types") or [])) == want, oc["execution"].get("status"))
            check(f"{role}: collection complete", oc["collection"]["status"] in ("complete", "no_files_confirmed"), oc["collection"]["status"])
        inv = [json.loads(l) for l in open(os.path.join(runs, "run_inventory.jsonl"))] if os.path.exists(os.path.join(runs, "run_inventory.jsonl")) else []
        check(f"{role}: its own inventory holds exactly its own sample line", [(i["kind"], i["run_label"]) for i in inv] == [("sample", label)], [(i.get("kind"), i.get("run_label")) for i in inv])
    tl = {r: [json.loads(l) for l in open(os.path.join(out, f"{r}.timeline"))] for r in ("dev", "compat") if os.path.exists(os.path.join(out, f"{r}.timeline"))}
    if len(tl) == 2:
        (a0, a1), (b0, b1) = [(next(e["t"] for e in tl[r] if e["ev"] == "eval_start"), next(e["t"] for e in tl[r] if e["ev"] == "eval_end")) for r in ("dev", "compat")]
        overlap = min(a1, b1) - max(a0, b0)
        check(f"the two evals overlapped in time ({overlap:.1f} s)", overlap > 5, overlap)
    return checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", required=True)
    ap.add_argument("--role", choices=("dev", "compat"))
    args = ap.parse_args()
    out = os.path.realpath(args.output_root)
    if args.role:
        return role_main(args.role, out)
    os.makedirs(out, exist_ok=False)
    cfg = json.load(open(os.path.join(ROOT, "config.json")))
    from harness.smoke import M
    cfg["batches"]["dev"]["models"].append(M); cfg["batches"]["compat"]["models"].append(M)
    json.dump(cfg, open(os.path.join(out, "config.json"), "w"), indent=2)
    with open(os.path.join(out, "env.test"), "w") as f:
        f.write("ANTHROPIC_API_KEY=dummy-test-key-not-real-0007\nGOOGLE_API_KEY=dummy-test-key-not-real-0008\n")
    procs = {r: subprocess.Popen([sys.executable, "-m", "harness.tests.regress_message_limit_parallel", "--output-root", out, "--role", r],
                                 stdout=open(os.path.join(out, f"{r}.log"), "w"), stderr=subprocess.STDOUT) for r in ("dev", "compat")}
    rcs = {r: p.wait(timeout=1200) for r, p in procs.items()}
    print("role exit codes:", rcs)
    checks = check_all(out)
    fails = sum(1 for c in checks if c["result"] == "FAIL")
    json.dump({"checks": checks}, open(os.path.join(out, "results.json"), "w"), indent=1)
    print(f"==== MESSAGE LIMIT PARALLEL {len(checks) - fails} PASS, {fails} FAIL; results {os.path.join(out, 'results.json')}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
