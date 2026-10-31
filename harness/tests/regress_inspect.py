"""Regressions for the B1–B4 and I4 fixes through the real Inspect Task + docker sandbox chain with
mockllm issuing scripted tool calls (no paid model; INSPECT_DISABLE_MODEL_API=1 is forced by
harness.smoke at import, inherited credential-like variables are scrubbed, dummy credentials are
placed in the process). Only harmless synthetic files are used.

Usage (through the isolated launcher):
  harness/tests/run_isolated.sh <project_root> harness.tests.regress_inspect [scenario ...]
Scenarios: adversarial listing_failed render_corrupt resume two_runs conflict probe_creds (default: all).
Exit status is non-zero if any assertion fails. Logs: logs/stage2_fix/."""
import datetime as dt
import hashlib
import json
import os
import sys
import zipfile

from harness.smoke import DUMMY_CREDS, M, PROBE_FS, SCRUBBED, done, fixture_files, tc  # noqa: E402  (sets guards at import)

from inspect_ai import eval as inspect_eval  # noqa: E402
from inspect_ai.dataset import Sample  # noqa: E402
from inspect_ai.log import read_eval_log  # noqa: E402
from inspect_ai.model import get_model  # noqa: E402

from harness.collect import LIMITS  # noqa: E402
from harness.task import make_task  # noqa: E402

ROOT = os.environ.get("HARNESS_PROJECT_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(ROOT, "logs", "stage2_fix", "inspect")
RUNS = os.path.join(ROOT, "logs", "stage2_fix", "runs")
RESULTS: list[dict] = []


def check(scenario: str, name: str, ok: bool, detail=""):
    RESULTS.append({"scenario": scenario, "check": name, "pass": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {str(detail)[:200]}" if detail and not ok else ""))


def sha_file(p: str) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def run_eval(name: str, outputs, samples=None, run_id=None, **task_kw):
    samples = samples or [Sample(id=f"regress-{name}", input="Run the scripted regression.", files=fixture_files())]
    task, run_dir = make_task(samples, os.path.join(RUNS, name), run_id=run_id, name=f"regress_{name}", **task_kw)
    logs = inspect_eval(task, model=get_model(M, custom_outputs=outputs), log_dir=LOG_DIR, display="plain",
                        log_level="warning", sandbox_cleanup=True, log_images=True, sandbox_prebuilt=True, task_retry_attempts=0)
    log = logs[0]
    sample = log.samples[0] if log.samples else None
    run_dir = os.path.join(run_dir, sample.uuid) if sample else run_dir
    events = [e for e in sample.events if e.event == "tool"] if sample else []
    print(f"\n######## {name}: status={log.status} model={log.eval.model} tool_events={len(events)} run_dir={run_dir}")
    for e in events:
        err = e.error.message if e.error else None
        print(f"  tool {e.function} error={err!r}")
    return log, sample, events, run_dir


def result_text(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        return "\n".join(c.text if getattr(c, "type", None) == "text" else f"<{getattr(c, 'type', '?')}>" for c in result)
    return str(result)


def has_image(result) -> bool:
    return isinstance(result, list) and any(getattr(c, "type", None) == "image" for c in result)


def load_record(run_dir: str, sample_id: str) -> dict:
    with open(os.path.join(run_dir, "collection.json"), encoding="utf-8") as f:
        return json.load(f)


def host_files_under(run_dir: str) -> list[str]:
    return sorted(os.path.join(dp, f) for dp, _, fn in os.walk(run_dir) for f in fn)


# ------------------------------------------------------------------------------------------------
ADVERSARIAL_CMD = r'''
set -e
mkdir -p "/output/final/sub dir/deep"
printf 'alpha\n' > /output/final/a.txt
printf 'beta\n' > "/output/final/sub dir/deep/b.txt"
printf 'noext\n' > /output/final/README
printf 'outside\n' > /tmp/outside.txt && ln /tmp/outside.txt /output/final/hard.txt
ln -s /etc/hostname /output/final/link_to_etc
ln -s /nonexistent/target /output/final/broken_link
ln -s /workspace/inputs /output/final/dirlink
mkfifo /output/final/pipe
dd if=/dev/zero of=/output/final/m_big.bin bs=1M count=65 2>/dev/null
printf 'omega\n' > /output/final/z.txt
ls -la /output/final "/output/final/sub dir/deep"
'''


def scenario_adversarial():
    s = "adversarial"
    log, sample, events, run_dir = run_eval(s, [tc("bash", command=ADVERSARIAL_CMD), done()])
    check(s, "eval completed", log.status == "success" and events and events[0].error is None, log.status)
    rec = load_record(run_dir, f"regress-{s}")
    by = {f["sandbox_path"]: f for f in rec["files"]}
    expect_collected = {"/output/final/a.txt": b"alpha\n", "/output/final/sub dir/deep/b.txt": b"beta\n",
                        "/output/final/README": b"noext\n", "/output/final/hard.txt": b"outside\n", "/output/final/z.txt": b"omega\n"}
    for p, content in expect_collected.items():
        f = by.get(p)
        ok = f is not None and f["status"] == "collected" and os.path.isfile(f["host_path"]) and open(f["host_path"], "rb").read() == content
        check(s, f"collected intact: {p}", ok, f and (f["status"], f.get("reason")))
    check(s, "hardlink recorded as regular file with nlink 2", by.get("/output/final/hard.txt", {}).get("nlink") == 2, by.get("/output/final/hard.txt", {}).get("nlink"))
    big = by.get("/output/final/m_big.bin", {})
    check(s, "oversized file recorded, not collected", big.get("status") == "error" and big.get("reason") == "oversized" and "host_path" not in big
          and big.get("size") == 65 * 1024 ** 2 and LIMITS["max_file_bytes"] < big.get("size", 0), big)
    skipped = {e["path"]: e["reason"] for e in rec["skipped"]}
    check(s, "symlink to /etc skipped", skipped.get("/output/final/link_to_etc") == "symlink", skipped)
    check(s, "broken symlink skipped", skipped.get("/output/final/broken_link") == "symlink_broken", skipped)
    check(s, "symlinked directory skipped, not descended", skipped.get("/output/final/dirlink") == "symlink_directory"
          and not any(p.startswith("/output/final/dirlink/") for p in by), skipped)
    check(s, "fifo skipped", skipped.get("/output/final/pipe") == "fifo", skipped)
    att = rec.get("attribution", {})
    check(s, "status partial; attribution: 4 model-caused special entries, oversized file unknown, no harness fault",
          rec["status"] == "partial" and rec["all_intact"] is False and rec["harness_error"] is False and att.get("class") == "unknown"
          and att.get("counts") == {"model_caused": 4, "harness_caused": 0, "unknown": 1}, (rec["status"], rec.get("harness_error"), att.get("counts")))
    check(s, "small files on both sides of oversized file collected", by["/output/final/a.txt"]["status"] == "collected" and by["/output/final/z.txt"]["status"] == "collected")
    root_real = os.path.realpath(os.path.join(run_dir, "final"))
    collected_paths = [f["host_path"] for f in rec["files"] if f["status"] == "collected"]
    check(s, "every collected host path is inside the sample's final root", all(os.path.realpath(p).startswith(root_real + os.sep) for p in collected_paths))
    extra = [p for p in host_files_under(run_dir) if not p.startswith(root_real + os.sep) and os.path.basename(p) not in ("collection.json", "run.json", "run_outcome.json")]
    check(s, "no other host files written by the run", extra == [], extra)
    check(s, "limits recorded", rec.get("limits") == LIMITS)
    check(s, "scorer answer is the status string", sample.scores and list(sample.scores.values())[0].answer == "partial", sample.scores)


def scenario_listing_failed():
    s = "listing_failed"
    cmd = "mkdir -p /output/final && echo x > /output/final/a.txt && chmod 000 /output/final && ls -ld /output/final"
    log, sample, events, run_dir = run_eval(s, [tc("bash", command=cmd), done()])
    check(s, "eval completed", log.status == "success", log.status)
    rec = load_record(run_dir, f"regress-{s}")
    check(s, "status listing_failed", rec["status"] == "listing_failed", rec["status"])
    check(s, "all_intact false, harness_error true", rec["all_intact"] is False and rec["harness_error"] is True)
    check(s, "outcome is harness_collection_error, not model non-delivery", rec["outcome_class"] == "harness_collection_error" and rec["status"] != "no_files_confirmed", rec["outcome_class"])
    check(s, "root_state unreadable recorded", rec.get("root_state") == "unreadable", rec.get("root_state"))
    check(s, "no file recorded as collected", rec["file_count"] == 0 and rec["files"] == [])
    check(s, "cleanup attempted a second pass (marker did not block it)", len(rec["passes"]) == 2 and all(p["status"] == "listing_failed" for p in rec["passes"]), [p["note"] for p in rec["passes"]])
    check(s, "scorer answer is listing_failed", sample.scores and list(sample.scores.values())[0].answer == "listing_failed", sample.scores)


def scenario_render_corrupt():
    s = "render_corrupt"
    outputs = [
        tc("bash", command="mkdir -p /tmp/t && cp /workspace/inputs/sample_doc.docx /tmp/t/doc.docx && ls -la /tmp/t"),
        tc("render_document", path="/tmp/t/doc.docx", page=1),
        tc("bash", command="head -c 1500 /workspace/inputs/sample_doc.docx > /tmp/t/doc.docx && ls -la /tmp/t/doc.docx"),
        tc("render_document", path="/tmp/t/doc.docx", page=1),
        tc("bash", command="printf 'not a pdf' > /tmp/t/bad.pdf; : > /tmp/t/empty.docx; ls -la /tmp/t"),
        tc("render_document", path="/tmp/t/bad.pdf", page=1),
        tc("render_document", path="/tmp/t/empty.docx", page=1),
        tc("render_document", path="/workspace/inputs/sample.pdf", page=9),
        tc("bash", command="ls -d /tmp/render_* 2>/dev/null | wc -l"),
        done(),
    ]
    log, sample, events, run_dir = run_eval(s, outputs)
    check(s, "eval completed with 9 tool events", log.status == "success" and len(events) == 9, (log.status, len(events)))
    e = events[1]
    check(s, "valid DOCX renders to an image", e.error is None and has_image(e.result), e.error and e.error.message)
    e = events[3]
    check(s, "truncated DOCX at the same path returns ToolError, no image", e.error is not None and "conversion produced no PDF" in e.error.message and not has_image(e.result), e.error and e.error.message)
    e = events[5]
    check(s, "non-PDF bytes with .pdf extension return ToolError", e.error is not None and "could not be opened" in e.error.message, e.error and e.error.message)
    e = events[6]
    check(s, "empty file returns ToolError", e.error is not None and "file is empty" in e.error.message, e.error and e.error.message)
    e = events[7]
    check(s, "page out of range returns ToolError", e.error is not None and "out of range" in e.error.message, e.error and e.error.message)
    e = events[8]
    check(s, "no render temp directories left behind", e.error is None and result_text(e.result).strip() == "0", result_text(e.result))


def scenario_resume():
    s = "resume"
    cmd = "mkdir -p /output/final && printf 'A\\n' > /output/final/a.txt && printf 'B\\n' > /output/final/b.txt && ls -la /output/final"
    log, sample, events, run_dir = run_eval(s, [tc("bash", command=cmd), done()], _simulate_read_failure={"/output/final/b.txt"})
    check(s, "eval completed", log.status == "success", log.status)
    rec = load_record(run_dir, f"regress-{s}")
    notes = [p["note"] for p in rec["passes"]]
    check(s, "two passes: scorer then cleanup resume", notes == ["collected in scorer", "collected in cleanup (resume of earlier pass)"], notes)
    check(s, "scorer pass was partial", rec["passes"][0]["status"] == "partial", rec["passes"][0]["status"])
    check(s, "scorer score recorded partial", sample.scores and list(sample.scores.values())[0].answer == "partial")
    by = {f["sandbox_path"]: f for f in rec["files"]}
    a, b = by.get("/output/final/a.txt", {}), by.get("/output/final/b.txt", {})
    check(s, "a.txt collected once in pass 1 and seen identical in pass 2 (not rewritten)", a.get("status") == "collected" and "seen_again_at" in a
          and a["at"] <= rec["passes"][1]["started_at"], a)
    check(s, "b.txt failed in pass 1 and collected in pass 2", b.get("status") == "collected" and b["at"] >= rec["passes"][1]["started_at"]
          and rec["passes"][0]["files_this_pass"] == 2, b)
    check(s, "final status complete", rec["status"] == "complete" and rec["file_count"] == 2, rec["status"])
    check(s, "contents intact", open(a["host_path"], "rb").read() == b"A\n" and open(b["host_path"], "rb").read() == b"B\n")


def scenario_two_runs():
    s = "two_runs"
    cmd = 'mkdir -p /output/final && printf "run %s %s\\n" "$(date +%s%N)" "$RANDOM" > /output/final/out.txt && cat /output/final/out.txt'
    _, _, _, run_dir1 = run_eval(s, [tc("bash", command=cmd), done()])
    rec1 = load_record(run_dir1, f"regress-{s}")
    path1 = rec1["files"][0]["host_path"]
    sha1_before = sha_file(path1)
    _, _, _, run_dir2 = run_eval(s, [tc("bash", command=cmd), done()])
    rec2 = load_record(run_dir2, f"regress-{s}")
    check(s, "two independent runs use two directories", run_dir1 != run_dir2 and rec1["run"]["uuid"] != rec2["run"]["uuid"], (run_dir1, run_dir2))
    check(s, "run binding carries model, task id, epoch", rec1["run"]["model"] == M and rec1["run"]["sample_id"] == f"regress-{s}" and bool(rec1["run"]["task_id"]) and rec1["run"]["epoch"] == 1, rec1["run"])
    check(s, "both runs complete", rec1["status"] == "complete" and rec2["status"] == "complete")
    check(s, "first run's file unchanged after second run", sha_file(path1) == sha1_before == rec1["files"][0]["sha256_collected"])
    check(s, "second run wrote its own copy with different content", rec2["files"][0]["host_path"] != path1 and rec2["files"][0]["sha256_collected"] != sha1_before)
    check(s, "collected files are read-only", oct(os.stat(path1).st_mode & 0o777) == "0o444", oct(os.stat(path1).st_mode & 0o777))


def scenario_conflict():
    s = "conflict"
    from unittest.mock import patch
    from harness import collect as collector
    actual_collect = collector.collect_final_outputs
    victims = []
    async def preseed(host_dir, *args, **kw):
        if not victims:
            os.makedirs(os.path.join(host_dir, "final"), exist_ok=True)
            victim = os.path.join(host_dir, "final", "out.txt")
            with open(victim, "xb") as f:
                f.write(b"earlier content of the same run\n")
            victims.append(victim)
        return await actual_collect(host_dir, *args, **kw)
    cmd = "mkdir -p /output/final && printf 'new content\\n' > /output/final/out.txt && printf 'fresh\\n' > /output/final/other.txt"
    with patch.object(collector, "collect_final_outputs", preseed):
        log, sample, events, run_dir = run_eval(s, [tc("bash", command=cmd), done()])
    victim = victims[0]
    check(s, "collection directory is actual execution UUID", os.path.basename(run_dir) == sample.uuid)
    rec = load_record(run_dir, f"regress-{s}")
    by = {f["sandbox_path"]: f for f in rec["files"]}
    check(s, "same-name different-content reported as conflict", by.get("/output/final/out.txt", {}).get("reason") == "conflict_existing_differs", by.get("/output/final/out.txt"))
    check(s, "existing file not overwritten", open(victim, "rb").read() == b"earlier content of the same run\n")
    check(s, "other file still collected", by.get("/output/final/other.txt", {}).get("status") == "collected")
    check(s, "status partial, harness_error", rec["status"] == "partial" and rec["harness_error"] is True, rec["status"])
    notes = [p.get("note") for p in rec["passes"]]
    check(s, "scorer pass and cleanup resume both recorded", notes == ["collected in scorer", "collected in cleanup (resume of earlier pass)"], notes)


def scenario_probe_creds():
    s = "probe_creds"
    log, sample, events, run_dir = run_eval(s, [tc("bash", command=PROBE_FS), done()])
    check(s, "eval completed", log.status == "success" and events and events[0].error is None, log.status)
    text = result_text(events[0].result)
    check(s, "probe reports the three test variables as absent", all(f"{v}: absent" in text for v in DUMMY_CREDS), text[:300])
    check(s, "dummy sentinel count is 0", "dummy sentinel occurrences in environment values: 0" in text)
    check(s, "key-prefix match count is 0", "environment values matching known key prefixes: 0" in text)
    values = list(DUMMY_CREDS.values())
    dumped = log.model_dump_json()
    check(s, "no dummy credential value in the parsed eval log", not any(v in dumped for v in values))
    check(s, "no dummy credential value in tool event arguments or results",
          not any(v in json.dumps(e.arguments, default=str) or v in result_text(e.result) for e in events for v in values))
    with zipfile.ZipFile(log.location) as z:
        raw_hit = any(any(v.encode() in z.read(n) for v in values) for n in z.namelist())
    check(s, "no dummy credential value in the raw .eval archive", not raw_hit)
    check(s, "process scrubbed inherited credential-like variables (count only)", isinstance(SCRUBBED, int), SCRUBBED)
    check(s, "probe does not print environment values (no 'GPG_KEY=' or '=' env dump lines)", "GPG_KEY" not in text and "\nPATH=" not in text)


SCENARIOS = {"adversarial": scenario_adversarial, "listing_failed": scenario_listing_failed, "render_corrupt": scenario_render_corrupt,
             "resume": scenario_resume, "two_runs": scenario_two_runs, "conflict": scenario_conflict, "probe_creds": scenario_probe_creds}


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(SCENARIOS)
    assert os.environ.get("INSPECT_DISABLE_MODEL_API") == "1"
    for n in names:
        try:
            SCENARIOS[n]()
        except Exception as ex:  # a crash is a failed scenario, recorded, not hidden
            check(n, "scenario ran without exception", False, f"{type(ex).__name__}: {ex}")
    failed = [r for r in RESULTS if not r["pass"]]
    os.makedirs(os.path.join(ROOT, "logs", "stage2_fix"), exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = os.path.join(ROOT, "logs", "stage2_fix", f"regress_summary_{stamp}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"at_utc": stamp, "scenarios": names, "checks": RESULTS, "passed": len(RESULTS) - len(failed), "failed": len(failed),
                   "inspect_disable_model_api": os.environ.get("INSPECT_DISABLE_MODEL_API"), "scrubbed_inherited_credential_vars": SCRUBBED}, f, indent=2)
    print(f"\n==== {len(RESULTS) - len(failed)} passed, {len(failed)} failed; summary {out}")
    for r in failed:
        print(f"FAILED {r['scenario']}: {r['check']} -- {r['detail']}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
