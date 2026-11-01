"""Batched, verdict-free human-labeling materials (preregistration 1.16: labels in groups of at least three tasks, saved
as a checkpoint before any automated verdict is revealed).

For each listed development run: refuse unless its task is listed in grading/readiness.json (Grader v0 tagged and the
task's readiness gate passed; the tag must exist), the run is designated canonical in its class, and the class is
``dev`` (validation outputs stay sealed). The deterministic grading pass goes through the official entry
(``grading.run_grading``, ledger-bound, no judge) unless the run already has a pass. The batch folder then holds, per
run, a copy of the verdict-free packet, a copy of the independent-judgments CSV template and read-only copies of the
collected deliverables, plus a README and a manifest with SHA-256 of every copied file. The sealed verdict file of a
pass is never copied, opened or printed; the manifest records only its path so the comparison can find it after the
labels are checkpointed (``grading.review save-labels`` then ``compare``).

Usage: python -m grading.label_batch --batch <name> --run dev:<task_id>:<run_uuid> [--run ...] (three or more tasks)
       [--no-recalc] [--out ~/turing-eval-runs/labeling]"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
README = """# Labeling batch {batch}

Written for: the human labeller. Created {created}.

For each run folder below, read `items.md` (criteria, weights, where to look, independent source material, deliverable
excerpts; no automated verdict) and the copied deliverables in `deliverables/`, then fill `labels.csv` with one of
`pass`, `fail`, `cannot_tell` per item and an optional note. Visual items are judged from the rendered files.

When a run's CSV is complete, save it as a checkpoint before looking at any automated verdict:

```
.venv/bin/python -m grading.review save-labels --out-dir <grading_out_dir> --run-uuid <run_uuid> --csv <this folder>/<run>/labels.csv --labeller '<name>'
```

The grading output directory of each run is listed in `manifest.json`. The comparison (`grading.review compare`) refuses
to run before a checkpoint exists.

Runs:
{runs}
"""


class BatchError(RuntimeError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def readiness(path: str = os.path.join(ROOT, "grading", "readiness.json")) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def tag_exists(tag: str, run=subprocess.run) -> bool:
    r = run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def _inventory_line(runs_root: str, run_uuid: str) -> dict | None:
    p = os.path.join(runs_root, "run_inventory.jsonl")
    if not os.path.isfile(p):
        return None
    recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if r.get("run_uuid") == run_uuid and r.get("kind") == "sample"]
    return recs[-1] if recs else None


def _canonical(runs_root: str, run_uuid: str) -> bool:
    p = os.path.join(runs_root, "canonical_designations.jsonl")
    if not os.path.isfile(p):
        return False
    latest = None
    for l in open(p, encoding="utf-8"):
        if l.strip():
            d = json.loads(l)
            if d.get("run_uuid") == run_uuid:
                latest = d.get("designation")
    return latest == "canonical"


def check_runs(runs: list[tuple[str, str, str]], *, base: str = BASE, ready: dict | None = None, tag_check=tag_exists) -> list[dict]:
    """Validate every (label, task, uuid); returns the resolved run records or raises BatchError (nothing written)."""
    ready = ready if ready is not None else readiness()
    if len({t for _, t, _ in runs}) < 3:
        raise BatchError("a labeling batch covers at least three tasks (preregistration 1.16)")
    out = []
    for label, task, uuid in runs:
        if label != "dev":
            raise BatchError(f"run {uuid}: class {label!r} - only development outputs are labelled here; validation outputs stay sealed until the validation checkpoint")
        if task not in ready["ready"]:
            why = ready.get("not_ready", {}).get(task, "not listed in grading/readiness.json")
            raise BatchError(f"task {task}: not ready for opening ({why})")
        if not tag_check(ready["ready"][task]["tag"]):
            raise BatchError(f"task {task}: tag {ready['ready'][task]['tag']} does not exist")
        runs_root = os.path.join(base, label, "runs")
        inv = _inventory_line(runs_root, uuid)
        if inv is None or inv.get("task_id") != task:
            raise BatchError(f"run {uuid}: no sample record of task {task} in the {label} inventory")
        if not _canonical(runs_root, uuid):
            raise BatchError(f"run {uuid}: not designated canonical in the {label} class")
        out.append({"label": label, "task_id": task, "run_uuid": uuid, "runs_root": runs_root, "host_dir": os.path.join(runs_root, uuid), "inventory": inv,
                    "grading_out": os.path.join(base, label, "grading", uuid)})
    return out


def _latest_pass(out_dir: str, run_uuid: str) -> dict | None:
    p = os.path.join(out_dir, "results.jsonl")
    if not os.path.isfile(p):
        return None
    recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    recs = [r for r in recs if (r.get("run") or {}).get("uuid") == run_uuid and r.get("graded")]
    return recs[-1] if recs else None


def official_pass(r: dict, *, no_recalc: bool, run=subprocess.run) -> dict:
    """The run's deterministic pass through grading.run_grading (no judge); an existing pass is reused."""
    existing = _latest_pass(r["grading_out"], r["run_uuid"])
    if existing:
        return existing
    os.makedirs(r["grading_out"], exist_ok=True)
    inv = r["inventory"]
    argv = [os.path.join(ROOT, ".venv", "bin", "python"), "-m", "grading.run_grading", "--host-dir", r["host_dir"], "--eval-log", inv["log_file"], "--task-id", r["task_id"],
            "--out-dir", r["grading_out"], "--ledger", os.path.join(os.path.dirname(r["runs_root"]), "ledger.json"), "--unit-id", inv["unit_id"]] + (["--no-recalc"] if no_recalc else [])
    res = run(argv, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        raise BatchError(f"run {r['run_uuid']}: official grading exited {res.returncode} (stderr tail withheld from the batch; see the grading output directory)")
    p = _latest_pass(r["grading_out"], r["run_uuid"])
    if p is None:
        raise BatchError(f"run {r['run_uuid']}: no graded pass after the official entry")
    return p


def assemble(batch: str, runs: list[dict], passes: list[dict], out_root: str) -> dict:
    folder = os.path.join(out_root, batch)
    if os.path.exists(folder):
        raise BatchError(f"batch folder {folder} exists; batches are never overwritten")
    os.makedirs(folder)
    manifest = {"batch": batch, "created_at": _now(), "runs": [], "note": "sealed verdict files are referenced by path only; open them only after the labels are checkpointed"}
    lines = []
    for r, p in zip(runs, passes):
        rm = p.get("review_materials") or {}
        sub = os.path.join(folder, f"{r['task_id'][:8]}_{r['run_uuid'][:8]}")
        os.makedirs(os.path.join(sub, "deliverables"))
        items = os.path.join(sub, "items.md"); shutil.copyfile(rm["items"], items)
        labels = os.path.join(sub, "labels.csv"); shutil.copyfile(rm["independent_template"], labels)
        files = []
        final = os.path.join(r["host_dir"], "final")
        for dp, _, fs in os.walk(final):
            for f in sorted(fs):
                src = os.path.join(dp, f)
                if os.path.islink(src) or not os.path.isfile(src):
                    continue
                rel = os.path.relpath(src, final)
                dst = os.path.join(sub, "deliverables", rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP)
                files.append({"path": rel, "sha256": _sha(dst), "matches_original": _sha(dst) == _sha(src)})
        manifest["runs"].append({"task_id": r["task_id"], "run_uuid": r["run_uuid"], "run_label": r["label"], "folder": os.path.basename(sub), "grading_out": r["grading_out"],
                                 "grading_pass": p.get("grading_pass"), "grader_version": p.get("grader_version"), "code_commit": (p.get("code") or {}).get("commit"),
                                 "items_sha256": _sha(items), "labels_template_sha256": _sha(labels), "deliverables": files, "sealed_verdicts_path": rm.get("judge_verdicts")})
        lines.append(f"- `{os.path.basename(sub)}`: task {r['task_id']}, run {r['run_uuid']} ({len(files)} deliverable file(s))")
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(folder, "README.md"), "x", encoding="utf-8") as f:
        f.write(README.format(batch=batch, created=manifest["created_at"], runs="\n".join(lines)))
    return {"folder": folder, "runs": len(runs), "manifest": os.path.join(folder, "manifest.json")}


QUEUE_README = """# Labeling batch {batch} (fixed review queue)

Written for: the human labeller. Created {created}. Queue: `{queue}` (policy {policy}, seed {seed}, frozen {frozen}).

Each run folder holds only the items of the frozen, verdict-independent review queue: every critical rubric item,
every visual item, and five random deterministic and five random judge items. Membership was computed from the rubric
inventory, the item types, the critical mappings and the seed alone. `items.md` gives each item's rubric text, its queue
category, the independent reference computed from the task's inputs and, for judge items, the deliverable excerpt the
judge will see. It carries no automated verdict and no grader location or explanation. `deliverables/` holds the
model's files and `inputs/` the task's input files (read-only copies).

Label every row of `labels.csv` with `pass`, `fail` or `cannot_tell` and name the evidence location. A queued item that
the grader cannot assess stays in the sample (its coverage is reported); nothing is replaced. When a run's CSV is
complete, save it before any automated verdict is shown:

```
.venv/bin/python -m grading.review save-labels --out-dir <grading_out_dir> --run-uuid <run_uuid> --csv <this folder>/<run>/labels.csv --labeller '<name>'
```

The comparison (`grading.review compare --queue {queue}`) then reveals the grader and judge verdicts for the queued
items only. Other unassessable items are triaged separately after the labels are saved and are never added to the
agreement sample.

Runs:
{runs}
"""


def _queue_items_md(src_md: str, items: dict, judge_items: set) -> str:
    """The pass's verdict-free packet reduced to the queued items: the preamble and the independent reference kept,
    'Where to look' lines (grader-derived locations) removed, judge excerpts kept for preregistered judge items only."""
    text = open(src_md, encoding="utf-8").read()
    head, *sections = text.split("\n## Item ")
    out = [head.rstrip() + "\n\nQueue categories: critical (C...), visual, random_deterministic, random_judge.\n"]
    for sec in sections:
        num = int(sec.split(" ", 1)[0])
        if num not in items:
            continue
        lines = [l for l in sec.split("\n") if not l.startswith("**Where to look:**")]
        if num not in judge_items:
            keep, skip = [], False
            for l in lines:
                if l.startswith("**Source material / independent reference:**") or l.startswith("**Deliverable excerpt:**"):
                    skip = True
                elif l.startswith("## ") or (skip and l.startswith("**") and not l.startswith("**Source") and not l.startswith("**Deliverable")):
                    skip = False
                if not skip:
                    keep.append(l)
            lines = keep
        lines.insert(1, f"\n**Queue category:** {', '.join(items[num])}")
        out.append("## Item " + "\n".join(lines).rstrip() + "\n")
    return "\n".join(out)


def assemble_queue(batch: str, runs: list[dict], passes: list[dict], out_root: str, queue_path: str) -> dict:
    """A labeling batch restricted to the frozen review queue (approved 2026-11-01). Never overwrites a batch."""
    import csv
    from . import review_queue as RQ
    queue = RQ.load(queue_path)
    folder = os.path.join(out_root, batch)
    if os.path.exists(folder):
        raise BatchError(f"batch folder {folder} exists; batches are never overwritten")
    os.makedirs(folder)
    manifest = {"batch": batch, "created_at": _now(), "queue": os.path.relpath(queue_path, ROOT) if queue_path.startswith(ROOT) else queue_path, "queue_sha256": _sha(queue_path),
                "queue_policy": queue["policy_version"], "seed": queue["seed"], "runs": [],
                "note": "sealed verdict files are referenced by path only; open them only after the labels are checkpointed"}
    lines = []
    for r, p in zip(runs, passes):
        q = queue["queues"].get(r["task_id"])
        if q is None:
            raise BatchError(f"task {r['task_id']} has no frozen queue in {queue_path}")
        items = {x["item"]: x["categories"] for x in q["items"]}
        rm = p.get("review_materials") or {}
        sub = os.path.join(folder, f"{r['task_id'][:8]}_{r['run_uuid'][:8]}")
        os.makedirs(os.path.join(sub, "deliverables")); os.makedirs(os.path.join(sub, "inputs"))
        ck = RQ.task_module(r["task_id"])
        items_md = os.path.join(sub, "items.md")
        with open(items_md, "x", encoding="utf-8") as f:
            f.write(_queue_items_md(rm["items"], items, set(ck.J_ITEMS)))
        labels = os.path.join(sub, "labels.csv")
        with open(rm["independent_template"], encoding="utf-8", newline="") as src, open(labels, "x", encoding="utf-8", newline="") as dst:
            rd, wr = csv.reader(src), csv.writer(dst)
            hdr = next(rd); wr.writerow(hdr + ["queue_category"])
            for row in rd:
                if row and row[1].strip().isdigit() and int(row[1]) in items:
                    wr.writerow(row + ["; ".join(items[int(row[1])])])
        files = []
        for base, tgt in ((os.path.join(r["host_dir"], "final"), "deliverables"), (os.path.join(ROOT, "data", "inputs", r["task_id"]), "inputs")):
            for dp, _, fs in os.walk(base):
                for fn in sorted(fs):
                    src = os.path.join(dp, fn)
                    if os.path.islink(src) or not os.path.isfile(src):
                        continue
                    rel = os.path.relpath(src, base)
                    dst = os.path.join(sub, tgt, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(src, dst)
                    os.chmod(dst, stat.S_IRUSR | stat.S_IRGRP)
                    files.append({"path": f"{tgt}/{rel}", "sha256": _sha(dst), "matches_original": _sha(dst) == _sha(src)})
        manifest["runs"].append({"task_id": r["task_id"], "run_uuid": r["run_uuid"], "run_label": r["label"], "folder": os.path.basename(sub), "grading_out": r["grading_out"],
                                 "grading_pass": p.get("grading_pass"), "grader_version": p.get("grader_version"), "code_commit": (p.get("code") or {}).get("commit"),
                                 "queue_items": sorted(items), "queue_counts": q["counts"], "queue_shortfall": q["shortfall"],
                                 "items_sha256": _sha(items_md), "labels_template_sha256": _sha(labels), "files": files, "sealed_verdicts_path": rm.get("judge_verdicts")})
        lines.append(f"- `{os.path.basename(sub)}`: task {r['task_id']}, run {r['run_uuid']}: {len(items)} queued items " + json.dumps(q["counts"]))
    with open(os.path.join(folder, "manifest.json"), "x", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    with open(os.path.join(folder, "README.md"), "x", encoding="utf-8") as f:
        f.write(QUEUE_README.format(batch=batch, created=manifest["created_at"], queue=manifest["queue"], policy=queue["policy_version"], seed=queue["seed"], frozen=queue["frozen_at"],
                                    runs="\n".join(lines)))
    return {"folder": folder, "runs": len(runs), "manifest": os.path.join(folder, "manifest.json")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="assemble a verdict-free labeling batch of three or more development runs")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--run", action="append", required=True, help="dev:<task_id>:<run_uuid>")
    ap.add_argument("--no-recalc", action="store_true", help="skip the LibreOffice recalculation (docker) in the grading pass")
    ap.add_argument("--out", default=os.path.join(BASE, "labeling"))
    ap.add_argument("--queue", default=None, help="frozen review queue (grading/review_queue/queue_v1.json): restrict the packets to its items")
    args = ap.parse_args(argv)
    runs = [tuple(x.split(":", 2)) for x in args.run]
    resolved = check_runs(runs)
    passes = [official_pass(r, no_recalc=args.no_recalc) for r in resolved]
    res = assemble_queue(args.batch, resolved, passes, args.out, args.queue) if args.queue else assemble(args.batch, resolved, passes, args.out)
    print(json.dumps(res, indent=1))  # paths and counts only; no verdict
    return 0


if __name__ == "__main__":
    sys.exit(main())
