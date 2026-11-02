"""The V1 calibration freeze record (2026-11-01): the shared judge (model, settings, prompt hash) and, per task, the V1
grader and evidence-builder version, with the SHA-256 of every grading and harness source file. Written once at the
freeze commit (tag v1-calibration-freeze); `verify` checks that the running code still matches it. The commit itself is
recorded by each grading pass (code provenance), never inside this file.

Usage: python -m grading.freeze_manifest write [--manifest PATH --freeze NAME --scope TEXT] | verify [--manifest PATH] | judge-surface TAG [--request-only]
(judge-surface: the judge prompt, request construction, evidence builders and their constants at TAG against the
working tree; any difference is listed)."""
import ast
import glob
import hashlib
import subprocess
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "grading", "freeze", "v1_manifest.json")


def _sources() -> list[str]:
    files = sorted(glob.glob(os.path.join(ROOT, "grading", "**", "*.py"), recursive=True) + glob.glob(os.path.join(ROOT, "harness", "**", "*.py"), recursive=True))
    return [os.path.relpath(f, ROOT) for f in files if f"{os.sep}tests{os.sep}" not in f]


JUDGE_SURFACE_FUNCTIONS = ("render_unit", "unit_id", "parse_judge_response", "judge_units", "_verdict_of")
# How a request is sent and its answer read (changed on purpose in V1.2, engine .8: error detail, pacing, continuation,
# schema retry; and in V1.3, engine .9: retryable / permanent classification, the per-item wall-clock cap, the runner
# version); everything else in the surface defines WHAT the judge receives and must not change after the freeze.
CALL_HANDLING = ("ProviderJudge.__call__", "ProviderJudge._call", "judge_units", "parse_judge_response", "_verdict_of", "UNRECOVERABLE_HTTP", "UNRECOVERABLE_STATUS",
                 "JUDGE_RUNNER_VERSION", "RETRYABLE_HTTP", "RATE_LIMIT_MARKERS", "FATAL_HTTP")


def judge_surface(source: str) -> dict:
    """SHA-256 of every part of grading/judge.py that shapes what the judge receives or how its answer is read: the
    system prompt and every module constant, render_unit / unit_id / parse_judge_response / judge_units, every
    build_units_* and _excerpt* builder, and ProviderJudge's request construction (__call__, _call)."""
    tree = ast.parse(source)
    out = {}
    h = lambda node: hashlib.sha256(ast.get_source_segment(source, node).encode("utf-8")).hexdigest()
    for node in tree.body:
        if isinstance(node, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in node.targets):
            out[",".join(t.id for t in node.targets)] = h(node)
        elif isinstance(node, ast.FunctionDef) and (node.name in JUDGE_SURFACE_FUNCTIONS or node.name.startswith(("build_units_", "_excerpt"))):
            out[node.name] = h(node)
        elif isinstance(node, ast.ClassDef) and node.name == "ProviderJudge":
            for m in node.body:
                if isinstance(m, ast.FunctionDef) and m.name in ("__call__", "_call"):
                    out[f"ProviderJudge.{m.name}"] = h(m)
    return out


def judge_surface_diff(tag: str, request_only: bool = False) -> list[str]:
    old = subprocess.run(["git", "show", f"{tag}:grading/judge.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    a, b = judge_surface(old), judge_surface(open(os.path.join(ROOT, "grading", "judge.py"), encoding="utf-8").read())
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return [k for k in diff if k not in CALL_HANDLING] if request_only else diff


def build() -> dict:
    from grading.grade import ENGINE_VERSION, TASK_MODULES
    from grading.judge import JUDGE_SYSTEM_PROMPT
    cfg = json.load(open(os.path.join(ROOT, "config.json"), encoding="utf-8"))
    j = cfg["judge"]
    tasks = {}
    for t in sorted(TASK_MODULES):
        mod = __import__(f"grading.checks_{t[:8]}", fromlist=["VERSION", "J_ITEMS"])
        tasks[t] = {"task_grader_version": mod.VERSION, "evidence_builder": f"grading.judge.build_units_{t[:8]}@{mod.VERSION}", "judge_items": len(mod.J_ITEMS)}
    return {"freeze": "v1-calibration-freeze", "scope": "shared judge prompt and model configuration; every task's V1 grader and evidence builder; frozen before any Validation output is revealed",
            "engine_version": ENGINE_VERSION, "judge": {"model": j["model"], "settings": {k: j[k] for k in ("temperature", "max_tokens", "max_retries", "reasoning_effort")},
                                                        "prompt_sha256": hashlib.sha256(JUDGE_SYSTEM_PROMPT.encode("utf-8")).hexdigest()},
            "tasks": tasks, "judge_surface_sha256": judge_surface(open(os.path.join(ROOT, "grading", "judge.py"), encoding="utf-8").read()), "files_sha256": {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in _sources()},
            "config_sha256": hashlib.sha256(open(os.path.join(ROOT, "config.json"), "rb").read()).hexdigest()}


def verify(manifest: dict) -> list[str]:
    """Differences between the manifest and the running code (empty when they match)."""
    now = build()
    problems = []
    for k in ("engine_version", "judge", "tasks", "config_sha256") + (("judge_surface_sha256",) if "judge_surface_sha256" in manifest else ()):
        if now[k] != manifest.get(k):
            problems.append(f"{k} differs")
    for p in sorted(set(now["files_sha256"]) | set(manifest.get("files_sha256", {}))):
        if now["files_sha256"].get(p) != manifest.get("files_sha256", {}).get(p):
            problems.append(f"{p} differs")
    return problems


def main(argv=None) -> int:
    args = list(argv if argv is not None else sys.argv[1:]) or ["verify"]
    cmd = args[0]
    path = args[args.index("--manifest") + 1] if "--manifest" in args else MANIFEST
    path = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if cmd == "judge-surface":
        req = "--request-only" in args
        diff = judge_surface_diff(args[1], request_only=req)
        print(json.dumps({"tag": args[1], "scope": "request surface (what the judge receives)" if req else "full surface", "identical": not diff, "differs": diff,
                          **({} if req else {"call_handling_differs": [k for k in diff if k in CALL_HANDLING]})}, indent=1))
        return 0 if not diff else 1
    if cmd == "write":
        if os.path.exists(path):
            raise SystemExit(f"{path} exists; the freeze record is never overwritten")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        rec = build()
        if "--freeze" in args:
            rec["freeze"] = args[args.index("--freeze") + 1]
        if "--scope" in args:
            rec["scope"] = args[args.index("--scope") + 1]
        with open(path, "x", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        print(path)
        return 0
    problems = verify(json.load(open(path, encoding="utf-8")))
    print(json.dumps({"matches": not problems, "problems": problems[:20]}, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
