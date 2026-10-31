"""Sandbox image regression through the real Inspect + Docker chain with mockllm (Codex review rounds
logs/pilot-a-review-6uxm37u9 I5 and logs/pilot-final-review-ogcsjzyp Docker: tag lookups misfired
while the image ID resolved). The compose file pins the image by its full local ID with
`x-local: true` and `pull_policy: never`. (a) The pre-flight checks compose/config agreement and
the daemon's answer by ID (never by tag); the state of the tag lookup is recorded as evidence
only; the sandbox starts and a scripted turn writes a file. (b) A compose file naming a
non-existent image ID: Inspect's prebuilt verification raises a PrerequisiteError before any
compose `up`, no eval log is written, the local image list is unchanged (no pull), nothing is
rerun and no container is left behind.
Usage: harness/tests/run_isolated.sh <root> harness.tests.regress_compose_local --output-root <new dir>"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1", "use run_isolated.sh"
from harness import smoke as sm, task as ht  # noqa: E402  (guards before Inspect initialization)
from harness.launcher import LauncherError, load_config, preflight_sandbox  # noqa: E402
from harness.image import CONFIG, IMAGE_ID_RE  # noqa: E402
from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402

CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def docker(*args, timeout=60):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def images():
    return sorted(l for l in docker("image", "ls", "--format", "{{.Repository}}:{{.Tag}} {{.ID}}").stdout.splitlines() if l)


def containers():
    return sorted(l for l in docker("ps", "-a", "--format", "{{.Names}}").stdout.splitlines() if l)


def run(name, compose_path, root, outputs, time_limit=120):
    ht.COMPOSE = compose_path  # make_task reads the module attribute at call time
    task, runs = ht.make_task([Sample(id="synthetic-s1", input="Execute the compose probe.")], str(root / "runs" / name), name=f"compose_{name}", time_limit=time_limit)
    t0 = time.monotonic()
    try:
        log = inspect_eval(task, model=get_model(sm.M, custom_outputs=outputs), log_dir=str(root / "inspect"), sandbox_prebuilt=True, sandbox_cleanup=True,
                           display="plain", log_level="warning", max_samples=1, max_tasks=1, task_retry_attempts=0, fail_on_error=False)[0]
        status = log.status
        err = (log.error.message if getattr(log, "error", None) else None) or ((log.samples[0].error.message if log.samples and log.samples[0].error else None))
        location = log.location
    except Exception as ex:  # a raise during sandbox start is also a failure, recorded as such
        log, status, err, location = None, "raised", f"{type(ex).__name__}: {ex}", None
    return {"log": log, "status": status, "error": err, "elapsed_s": round(time.monotonic() - t0, 1), "location": location}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--output-root", required=True); args = p.parse_args()
    root = Path(args.output_root); root.mkdir(parents=True, exist_ok=False)
    compose_text = Path(ht.COMPOSE).read_text()
    image = re.search(r"^\s*image:\s*(\S+)", compose_text, re.M).group(1)
    cfg = load_config(CONFIG)
    check("compose declares x-local: true and pull_policy: never", "x-local: true" in compose_text and "pull_policy: never" in compose_text)
    check("compose pins the image by a full local image ID equal to config.json sandbox.image_id", bool(IMAGE_ID_RE.match(image)) and image == cfg["sandbox"]["image_id"], (image, cfg["sandbox"]["image_id"]))
    try:
        pre = preflight_sandbox(cfg, ht.COMPOSE, attempts=5, delay_s=2.0)
        image_id = pre["daemon_id"]
    except LauncherError as ex:
        pre, image_id = {"attempts": [], "error": str(ex)}, None
    check("pre-flight by image ID succeeds (daemon knows the ID, platform matches config)", image_id == image, pre)
    tag = cfg["sandbox"].get("image_tag_informational", "").split(" ")[0]
    tag_lookup = docker("image", "inspect", tag, "--format", "{{.Id}}") if tag else None
    tag_state = {"tag": tag, "rc": tag_lookup.returncode if tag_lookup else None, "resolves_to_pinned_id": bool(tag_lookup and tag_lookup.returncode == 0 and tag_lookup.stdout.strip() == image),
                 "stderr": (tag_lookup.stderr or "")[-160:] if tag_lookup else None}
    print(f"  [INFO] tag lookup state (evidence only, not a check): {tag_state}")
    images_before, containers_before = images(), containers()
    evidence = {"image": image, "image_id": image_id, "preflight": pre, "tag_lookup_state": tag_state, "compose_sha256_prefix": __import__("hashlib").sha256(compose_text.encode()).hexdigest()[:16]}

    # (a) image present: the sandbox starts and the scripted turn completes
    outputs = [sm.tc("bash", command="mkdir -p /output/final && echo compose-local-ok > /output/final/ok.txt && cat /output/final/ok.txt"), sm.done()]
    a = run("present", ht.COMPOSE, root, outputs)
    log = a["log"]
    sample = log.samples[0] if log is not None and log.samples else None
    tool_events = [e for e in (sample.events if sample else []) if e.event == "tool"]
    check("present: eval status success", a["status"] == "success", (a["status"], a["error"]))
    check("present: sample has no error and one successful bash tool call", sample is not None and sample.error is None and len(tool_events) == 1 and tool_events[0].error is None,
          [(getattr(e, "function", None), getattr(e.error, "message", None) if e.error else None) for e in tool_events])
    check("present: the tool result carries the written text", any("compose-local-ok" in str(getattr(e, "result", "")) for e in tool_events))
    evidence["present"] = {"status": a["status"], "elapsed_s": a["elapsed_s"], "log": a["location"], "sample_uuid": getattr(sample, "uuid", None)}

    # (b) non-existent image ID: fast failure, no pull, no rerun, no leftover container
    missing_tag = "sha256:" + hashlib.sha256(b"regress-missing-" + os.urandom(6)).hexdigest()
    tmp = tempfile.mkdtemp(prefix="compose_missing_")  # outside the repository (TMPDIR of the isolated launcher)
    missing_compose = Path(tmp, "compose.yaml")
    missing_compose.write_text(compose_text.replace(image, missing_tag))
    check("missing: probe compose still declares x-local and pull_policy never", "x-local: true" in missing_compose.read_text() and "pull_policy: never" in missing_compose.read_text())
    b = run("missing", str(missing_compose), root, [sm.done()], time_limit=60)
    err = b["error"] or ""
    check("missing: eval did not succeed", b["status"] != "success", b["status"])
    check("missing: failed fast (under 120 s)", b["elapsed_s"] < 120, b["elapsed_s"])
    check("missing: local image list unchanged (no pull happened)", images() == images_before, set(images()) ^ set(images_before))
    check("missing: no registry-contact signature in the failure text", not re.search(r"pull access denied|manifest unknown|unauthorized|requested access to the resource is denied", err, re.I), err[:300])
    check("missing: failure text names the missing image ID", missing_tag in err, err[:300])
    check("missing: Inspect's prebuilt verification raised before any compose up (PrerequisiteError, no sample ran)", b["status"] == "raised" and "PrerequisiteError" in err and "not present in the Docker image store" in err, (b["status"], err[:200]))
    eval_files = sorted(f for f in os.listdir(root / "inspect") if "compose-missing" in f or "compose_missing" in f)
    check("missing: no eval log written and nothing rerun", len(eval_files) == 0, eval_files)
    time.sleep(2)
    check("missing: no container left behind", containers() == containers_before, set(containers()) ^ set(containers_before))
    evidence["missing"] = {"tag": missing_tag, "status": b["status"], "elapsed_s": b["elapsed_s"], "error_text": err[:600], "log": b["location"], "eval_files": eval_files}
    ht.COMPOSE = os.path.join(os.path.dirname(ht.__file__), "compose.yaml")
    evidence["present"]["image_in_eval_log"] = image

    (root / "results.json").write_text(json.dumps({"checks": CHECKS, "evidence": evidence, "images_before": images_before}, indent=1, default=str))
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== COMPOSE LOCAL {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {root / 'results.json'}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
