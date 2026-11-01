"""Batch runner for one run class: every task of the class's task set, one model, one sample each, sequentially,
through the launcher's own gates (harness.launcher.main per unit: staging verification, prompt hash, image
pre-flight, atomic ledger claim, settlement, ledger binding, artifact manifest, run inventory).

One explicit authorization covers the batch: ``--confirm-batch '<label>|<model>|<units>|<estimate_usd>'`` restates
the paid scope once; the runner derives each unit's ``--confirm`` from it and records the batch authorization
verbatim. Duplicate-run protection: a task that already has a completed ``sample`` record for this model in the
class's run inventory is skipped (``--allow-repeat`` is the only way to run it again, and it never retries by
itself). The batch stops at the first unit that is refused, raises, records a stop or needs manual review, and
whenever the ledger shows a stop, a hold or an open reservation before a unit starts. Nothing here calls a provider
except through the launcher's --real-run path.

Usage (dry run first, then the paid batch with the authorization fields):
  python -m harness.batch --run-label dev --model google/gemini-3.8-flash \\
      --runs-root ~/turing-eval-runs/dev/runs --ledger ~/turing-eval-runs/dev/ledger.json --dry-run
  python -m harness.batch --run-label dev --model google/gemini-3.8-flash ... --real-run \\
      --confirm-batch 'dev|google/gemini-3.8-flash|10|1.00' --authorized-by '<name>' --authorization-ref '<docs/status.md entry>'"""
import argparse
import datetime as dt
import json
import os
import sys
from decimal import Decimal, InvalidOperation

from . import launcher as L
from .budget import BudgetLedger
from .samples import TASK_SETS, load_json, task_set_for_manifest


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def prior_attempts(runs_root: str) -> dict:
    """(task_id, model) -> inventory records of earlier real attempts in this class: completed samples (kind 'sample'
    without an engineering failure) and attempts that ended in an execution error (sample error, eval exception,
    cardinality fault). Both block an automatic rerun: a completed sample is the task's one sample; an errored attempt
    may have reached the provider, so running it again is a whole-sample rerun that needs explicit authorization."""
    path = os.path.join(runs_root, "run_inventory.jsonl")
    out: dict = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                if rec.get("kind") != "dry_run" and not rec.get("dry_run"):
                    out.setdefault((rec.get("task_id"), rec.get("model")), []).append(rec)
    return out


def completed_units(runs_root: str) -> dict:
    return {k: [r for r in v if r.get("kind") == "sample" and not r.get("engineering_failure")] for k, v in prior_attempts(runs_root).items()}


def ledger_blocks(ledger: BudgetLedger) -> list[str]:
    snap = ledger.snapshot()
    reasons = []
    if snap.get("stops"):
        reasons.append(f"stop recorded: {snap['stops']}")
    if snap.get("review_pending_units"):
        reasons.append(f"units held for manual review: {snap['review_pending_units']}")
    if snap.get("unresolvable_units"):
        reasons.append(f"unresolvable units: {snap['unresolvable_units']}")
    if snap.get("open_reservations"):
        reasons.append(f"open reservations: {snap['open_reservations']}")
    return reasons


def parse_confirm_batch(text: str | None, *, run_label: str, model: str, units: int, estimate_usd: Decimal) -> None:
    parts = (text or "").split("|")
    if len(parts) != 4:
        raise L.LauncherError("--real-run requires --confirm-batch '<run_label>|<model>|<units>|<estimate_usd>' restating the paid scope of the whole batch")
    try:
        ok = parts[0].strip() == run_label and parts[1].strip() == model and int(parts[2].strip()) == units and Decimal(parts[3].strip()) == estimate_usd
    except (ValueError, InvalidOperation):
        ok = False
    if not ok:
        raise L.LauncherError(f"--confirm-batch does not restate the batch (label {run_label!r}, model {model!r}, {units} unit(s), estimate {estimate_usd} USD each); refusing to start")


def main(argv=None, *, eval_fn=None, environ: dict | None = None, docker_runner=None) -> int:
    p = argparse.ArgumentParser(description="run every task of one run class through the launcher, one unit at a time")
    p.add_argument("--config", default=os.path.join(L.ROOT, "config.json"))
    p.add_argument("--run-label", required=True, choices=L.BATCH_LABELS)
    p.add_argument("--model", required=True)
    p.add_argument("--runs-root", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--tasks", default="all", help="'all' (every task of the class's task set, manifest order) or a comma-separated list of full task ids")
    p.add_argument("--estimate-usd", type=Decimal, default=None, help="per-unit pre-run estimate; default: config.batches.<label>.reservation_usd_by_model[model]")
    p.add_argument("--env-file", default=os.path.join(L.ROOT, ".env"))
    p.add_argument("--allow-repeat", action="store_true", help="run a task again although a completed sample exists for it in this class (never automatic)")
    p.add_argument("--stop-after", type=int, default=None, help="run at most this many units in this invocation")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--real-run", action="store_true")
    p.add_argument("--confirm-batch", default=None)
    p.add_argument("--authorized-by", default=None)
    p.add_argument("--authorization-ref", default=None)
    args = p.parse_args(argv)

    cfg = L.load_config(args.config)
    batch = L.batch_controls(cfg, args.run_label)
    if args.model not in batch["models"]:
        raise L.LauncherError(f"model {args.model!r} is not allowed in run class {args.run_label!r} ({batch['models']})")
    task_set = task_set_for_manifest(batch["task_manifest"])
    all_tasks = [t["task_id"] for t in load_json(TASK_SETS[task_set]["selected"])["tasks"]]
    tasks = all_tasks if args.tasks == "all" else [t.strip() for t in args.tasks.split(",") if t.strip()]
    unknown = [t for t in tasks if t not in all_tasks]
    if unknown:
        raise L.LauncherError(f"task(s) {unknown} are not in the {task_set!r} task set of run class {args.run_label!r}")
    estimate = args.estimate_usd
    if estimate is None:
        raw = batch["reservation_usd_by_model"].get(args.model)
        if raw is None:
            raise L.LauncherError(f"no reservation forecast for {args.model!r} in config.batches.{args.run_label}.reservation_usd_by_model; pass --estimate-usd")
        estimate = Decimal(str(raw))
    L.check_run_class_paths(args.run_label, args.runs_root, args.ledger)
    runs_root = L.resolve_runs_root(args.runs_root)
    if args.real_run:
        parse_confirm_batch(args.confirm_batch, run_label=args.run_label, model=args.model, units=len(tasks), estimate_usd=estimate)
        if not (args.authorized_by and args.authorization_ref):
            raise L.LauncherError("--real-run requires --authorized-by and --authorization-ref (the batch authorization, recorded verbatim)")
    attempts = prior_attempts(runs_root)
    plan = []
    for tid in tasks:
        prior = attempts.get((tid, args.model), [])
        completed = [r for r in prior if r.get("kind") == "sample" and not r.get("engineering_failure")]
        errored = [r for r in prior if r not in completed]
        if prior and not args.allow_repeat:
            reason = (f"completed sample exists ({[r.get('run_uuid') for r in completed]}); pass --allow-repeat to run it again" if completed else
                      f"an earlier attempt ended in an execution error ({[(r.get('engineering_failure') or r.get('kind')) for r in errored]}; run uuids {[r.get('run_uuid') for r in errored]}); "
                      "a rerun is a whole-sample rerun that needs explicit authorization: pass --allow-repeat with --tasks <id>")
            plan.append({"task_id": tid, "action": "skip", "reason": reason})
        else:
            plan.append({"task_id": tid, "action": "run", "repeat_of": [r.get("run_uuid") for r in prior] if prior else None,
                         "earlier_execution_errors": [r.get("engineering_failure") for r in errored] if errored else None})
    record_dir = os.path.join(runs_root, "batch_records")
    os.makedirs(record_dir, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {"run_label": args.run_label, "model": args.model, "task_set": task_set, "mode": "real-run" if args.real_run else "dry-run", "estimate_usd_per_unit": str(estimate),
               "batch": {k: (str(v) if isinstance(v, Decimal) else v) for k, v in batch.items()}, "config_sha256": L.config_sha256(args.config), "code": L.git_provenance(), "code_loaded": L.code_loaded(),
               "authorization": {"by": args.authorized_by, "ref": args.authorization_ref, "confirm_batch": args.confirm_batch} if args.real_run else None,
               "plan": plan, "units": [], "started_at": _now()}
    path = os.path.join(record_dir, f"batch_{args.run_label}_{stamp}.json")

    def save(status, reason=None):
        summary.update({"status": status, "stop_reason": reason, "finished_at": _now()})
        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=1, default=str)
        print(json.dumps({"batch_record": path, "status": status, "stop_reason": reason, "units_run": len(summary["units"]), "skipped": sum(1 for x in plan if x["action"] == "skip")}, indent=1))

    save("planned")
    ran = 0
    for item in plan:
        if item["action"] != "run":
            continue
        if args.stop_after is not None and ran >= args.stop_after:
            save("paused", f"--stop-after {args.stop_after} reached")
            return 0
        if os.path.exists(args.ledger):
            blocks = ledger_blocks(BudgetLedger.open_existing(args.ledger, L.prices_from_config(cfg)))
            if blocks:
                save("stopped", "ledger blocks the next start: " + "; ".join(blocks))
                return 3
        tid = item["task_id"]
        unit_argv = ["--config", args.config, "--run-label", args.run_label, "--runs-root", runs_root, "--ledger", args.ledger, "--task-id", tid, "--model", args.model,
                     "--estimate-usd", str(estimate), "--env-file", args.env_file]
        if args.real_run:
            unit_argv += ["--real-run", "--confirm", f"{tid}|{args.model}|{estimate}", "--authorized-by", args.authorized_by, "--authorization-ref", args.authorization_ref]
        else:
            unit_argv += ["--dry-run"]
        entry = {"task_id": tid, "started_at": _now()}
        try:
            kw = {"eval_fn": eval_fn, "environ": environ}
            if docker_runner is not None:
                kw["docker_runner"] = docker_runner
            rc = L.main(unit_argv, **kw)
            entry.update({"return_code": rc, "finished_at": _now()})
        except Exception as ex:  # the launcher already settled conservatively and recorded the failure; the batch never retries
            entry.update({"error": f"{type(ex).__name__}: {L.redact(ex)}", "finished_at": _now()})
            summary["units"].append(entry)
            save("stopped", f"unit {tid} failed: {type(ex).__name__}; no automatic rerun")
            return 2
        summary["units"].append(entry)
        ran += 1
        if rc != 0:
            save("stopped", f"unit {tid} returned {rc}")
            return rc
        if os.path.exists(args.ledger):
            blocks = ledger_blocks(BudgetLedger.open_existing(args.ledger, L.prices_from_config(cfg)))
            if blocks:
                save("stopped", "ledger blocks after the unit: " + "; ".join(blocks))
                return 3
        save("running")
    save("completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
