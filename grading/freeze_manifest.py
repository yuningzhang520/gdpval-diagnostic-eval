"""The V1 calibration freeze record (2026-11-01): the shared judge (model, settings, prompt hash) and, per task, the V1
grader and evidence-builder version, with the SHA-256 of every grading and harness source file. Written once at the
freeze commit (tag v1-calibration-freeze); `verify` checks that the running code still matches it. The commit itself is
recorded by each grading pass (code provenance), never inside this file.

Usage: python -m grading.freeze_manifest write | verify"""
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "grading", "freeze", "v1_manifest.json")


def _sources() -> list[str]:
    files = sorted(glob.glob(os.path.join(ROOT, "grading", "**", "*.py"), recursive=True) + glob.glob(os.path.join(ROOT, "harness", "**", "*.py"), recursive=True))
    return [os.path.relpath(f, ROOT) for f in files if f"{os.sep}tests{os.sep}" not in f]


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
            "tasks": tasks, "files_sha256": {p: hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest() for p in _sources()},
            "config_sha256": hashlib.sha256(open(os.path.join(ROOT, "config.json"), "rb").read()).hexdigest()}


def verify(manifest: dict) -> list[str]:
    """Differences between the manifest and the running code (empty when they match)."""
    now = build()
    problems = []
    for k in ("engine_version", "judge", "tasks", "config_sha256"):
        if now[k] != manifest.get(k):
            problems.append(f"{k} differs")
    for p in sorted(set(now["files_sha256"]) | set(manifest.get("files_sha256", {}))):
        if now["files_sha256"].get(p) != manifest.get("files_sha256", {}).get(p):
            problems.append(f"{p} differs")
    return problems


def main(argv=None) -> int:
    cmd = (argv or sys.argv[1:] or ["verify"])[0]
    if cmd == "write":
        if os.path.exists(MANIFEST):
            raise SystemExit(f"{MANIFEST} exists; the freeze record is never overwritten")
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "x", encoding="utf-8") as f:
            json.dump(build(), f, indent=1)
        print(MANIFEST)
        return 0
    problems = verify(json.load(open(MANIFEST, encoding="utf-8")))
    print(json.dumps({"matches": not problems, "problems": problems[:20]}, indent=1))
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
