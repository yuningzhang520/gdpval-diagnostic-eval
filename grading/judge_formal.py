"""Formal judge pass (approved in advance by the human 2026-11-01; config ``judge.formal``): one pass of the frozen judge over
the 20 formal outputs, each judged as soon as its run is finalized while generation continues. PREPARED, NOT RUN: the
paid command refuses until every gate holds.

Gates (FAIL-CLOSED, checked before any call):
- the tag ``freeze-v1-grading`` exists, the grading and harness code and config.json are identical to it, nothing is
  uncommitted, and its freeze record (grading/freeze/freeze-v1-grading_manifest.json) verifies (engine .12: the
  two-stage freeze of 2026-11-02; ``freeze-v1-generation`` freezes generation only and unlocks nothing here);
- config.json is marked FROZEN for grading (``_status``; a FROZEN-GENERATION status does not count);
- ``judge.formal`` holds the approved ceiling (30 USD), concurrency 1, one pass;
- ``run`` restates the human's Formal launch authorization (``--authorized-by``, ``--authorization-ref`` naming its
  docs/status.md entry, recorded verbatim; that authorization also authorizes this pass) and the scope
  (``--confirm 'judge-formal|<judge model>|<ceiling>'``).

Project (approved 2026-11-02): one Google project per workload, never split within one. The Formal judge pass runs on the
second project (``judge.formal.credential_env``, GOOGLE_API_KEY_VALIDATION, put into GOOGLE_API_KEY in this process only and
re-checked after Inspect's .env initialisation); the Dev project's key is refused. An exhausted daily quota checkpoints
and pauses the pass; it resumes after the provider's reset as the same logical pass (``resume``), never re-judging a
completed item; the judge model, prompt, rubric, settings and inputs are unchanged.

A run is judged only when it is designated canonical in the formal inventory, its run_outcome.json is final and its eval
log exists: never a partially written output (run_grading's outcome gate re-validates finality and integrity). Costs go
to the separate formal judge ledger; every call is guarded at its worst case against the ceiling with the judge key
check. Within the one pass: Inspect's retries and one bounded per-item recovery of provider_error / not_run items; no
repeat pass and no re-judging of a completed schema-valid item.

Hidden results: grades, judge verdicts and scores are written only under ~/turing-eval-runs/formal/grading_sealed/
(mode 700), with the grading logs, and never printed. ``status`` and the registry carry counts and costs only, until the human's 20 formal blind
labels are checkpointed. A budget stop, a persistent provider error or a missing output keeps the partial state and is
reported without verdicts; nothing is rerun silently and a missing verdict is never a fail.

Usage:
  python -m grading.judge_formal check    # gates and the finalized-run listing, no call
  python -m grading.judge_formal run --authorized-by WHO --authorization-ref REF --confirm 'judge-formal|MODEL|CEILING'
                                          # the pass (paid; only after the gates)
  python -m grading.judge_formal resume --authorized-by WHO --authorization-ref REF --confirm 'judge-formal|MODEL|CEILING'
                                          # continue the started pass after a quota pause or an interrupted process
  python -m grading.judge_formal status   # counts and costs only"""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from decimal import ROUND_CEILING, Decimal

from grading.judge_dev import DEV_KEY_SUFFIX, call_cost_usd, next_liability_bound_usd, on_ac_power, quota_resume_at, worst_case_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
RUNS = os.path.join(BASE, "formal", "runs")
# 2026-11-02 (the human, deadline): formal generation ran in three independent roots, each with its own generation
# ledger - the first two units on the single-ledger scheduler, then one harness.batch worker per candidate.
RUNS_ROOTS = ((RUNS, os.path.join(BASE, "formal", "ledger.json")),
              (os.path.join(BASE, "formal", "opus", "runs"), os.path.join(BASE, "formal", "opus", "ledger.json")),
              (os.path.join(BASE, "formal", "gpt", "runs"), os.path.join(BASE, "formal", "gpt", "ledger.json")))
SEALED = os.path.join(BASE, "formal", "grading_sealed")
JDIR = os.path.join(BASE, "judge_formal")
LEDGER = os.path.join(JDIR, "ledger.json")
REGISTRY = os.path.join(JDIR, "registry.jsonl")
FREEZE_TAG = "freeze-v1-grading"  # engine .12: two-stage freeze (approved 2026-11-02); freeze-v1-generation unlocks nothing here
MANIFEST = os.path.join(ROOT, "grading", "freeze", "freeze-v1-grading_manifest.json")
FROZEN_PATHS = ("grading", "harness", "config.json")
PASS_ID = "judge-formal-pass-1"
POLL_S = 60
STOPS = ("budget_stop", "ledger_stop", "halted", "recovery_error", "idle_stop")
PAUSES = ("quota_pause",)


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def cfg():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def registry(event: dict) -> None:
    os.makedirs(JDIR, exist_ok=True)
    with open(REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), "pass": PASS_ID, **event}, default=str) + "\n")


def registry_events() -> list[dict]:
    return [json.loads(l) for l in open(REGISTRY, encoding="utf-8") if l.strip()] if os.path.exists(REGISTRY) else []


def gates() -> dict:
    """Every gate with its state; ``ok`` only when all hold."""
    from grading.freeze_manifest import verify
    out = {}
    tag = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{FREEZE_TAG}^{{commit}}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    out["freeze_tag"] = {"ok": bool(tag), "commit": tag or None}
    if tag:
        diff = subprocess.run(["git", "diff", "--name-only", tag, "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        out["frozen_code"] = {"ok": not diff and not dirty, "differs": (diff or dirty).splitlines()[:6]}
        problems = verify(json.load(open(MANIFEST, encoding="utf-8"))) if os.path.isfile(MANIFEST) else ["freeze record missing"]
        out["freeze_record"] = {"ok": not problems, "problems": problems[:4]}
    status = str(cfg().get("_status", ""))
    out["config_frozen"] = {"ok": status.startswith("FROZEN") and not status.startswith("FROZEN-GENERATION"), "status": status[:60]}  # a generation-only freeze is no grading freeze
    f = (cfg().get("judge") or {}).get("formal") or {}
    out["judge_formal_config"] = {"ok": Decimal(str(f.get("ceiling_usd", 0))) == Decimal(30) and f.get("concurrency") == 1 and f.get("passes") == 1 and f.get("repeats") == 0,
                                  "ceiling_usd": f.get("ceiling_usd"), "concurrency": f.get("concurrency"), "passes": f.get("passes")}
    out["ok"] = all(v.get("ok") for v in out.values() if isinstance(v, dict))
    return out


def finalized_runs(roots=None) -> list[dict]:
    """Canonical formal runs whose outcome is final and whose eval log exists (metadata only; no output is opened), from
    every formal runs root (RUNS_ROOTS), each run with its own root's generation ledger. Fail closed when one task and
    model has canonical runs in two roots (k=1: never two samples)."""
    out = []
    for runs_root, gen_ledger in (roots or RUNS_ROOTS):
        out += _finalized_in(runs_root, gen_ledger)
    seen = {}
    for r in out:
        key = (r["task_id"], r["model"])
        if key in seen:
            raise SystemExit(f"two canonical formal runs for {key}: {seen[key]} and {r['run_uuid']}; refusing (k=1)")
        seen[key] = r["run_uuid"]
    return out


def _finalized_in(runs_root: str, gen_ledger: str) -> list[dict]:
    from grading.grade import TASK_MODULES
    des_p, inv_p = os.path.join(runs_root, "canonical_designations.jsonl"), os.path.join(runs_root, "run_inventory.jsonl")
    if not (os.path.isfile(des_p) and os.path.isfile(inv_p)):
        return []
    des = [json.loads(l) for l in open(des_p, encoding="utf-8") if l.strip()]
    inv = {r["run_uuid"]: r for r in (json.loads(l) for l in open(inv_p, encoding="utf-8") if l.strip()) if r.get("run_uuid")}
    out = []
    for d in des:
        u, t = d.get("run_uuid"), d.get("task_id")
        if d.get("designation") != "canonical" or u not in inv or t not in TASK_MODULES:
            continue
        host = os.path.join(runs_root, u)
        oc = os.path.join(host, "run_outcome.json")
        try:
            final = json.load(open(oc, encoding="utf-8")).get("final") is True
        except (OSError, ValueError):
            final = False
        log = inv[u].get("log_file")
        if final and log and os.path.isfile(log):
            mod = __import__(f"grading.checks_{t[:8]}", fromlist=["J_ITEMS"])
            out.append({"task_id": t, "run_uuid": u, "model": d.get("model"), "host_dir": host, "eval_log": log, "unit_id": inv[u].get("unit_id"),
                        "judge_items": list(mod.J_ITEMS), "grading_out": os.path.join(SEALED, u), "gen_ledger": gen_ledger})
    return out


def ensure_ledger():
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    if not os.path.isfile(LEDGER):
        os.makedirs(JDIR, exist_ok=True)
        BudgetLedger(LEDGER, Decimal(str(cfg()["judge"]["formal"]["ceiling_usd"])), prices_from_config(cfg()), label="judge_formal")
    return BudgetLedger.open_existing(LEDGER, prices_from_config(cfg()))


def select_project_credential() -> dict:
    """The Formal judge project's key in this process (names and the 4-character suffix only; nothing printed): the
    configured variable (judge.formal.credential_env) into GOOGLE_API_KEY, Inspect's .env initialisation re-checked, the
    Dev project's key refused."""
    from harness.launcher import load_env_file, select_credential, verify_credential_after_dotenv
    load_env_file(os.path.join(ROOT, ".env"))
    var = cfg()["judge"]["formal"]["credential_env"]
    cred = select_credential("google", {"credential_env": {"google": var}}, os.environ)
    if cred.get("suffix") == DEV_KEY_SUFFIX:
        raise SystemExit(f"{var} holds the Dev project's key; the Formal judge pass runs on its own project")
    verify_credential_after_dotenv(cred)
    return {k: cred.get(k) for k in ("variable", "provider_variable", "suffix", "dotenv_override_markers_removed")}


def make_guard(holder: dict, max_tokens: int, base_total: Decimal, ceiling: Decimal, project_suffix: str | None = None):
    def guard(request_chars: int, request_bytes: int | None = None):
        key = os.environ.get("GOOGLE_API_KEY") or ""
        if not project_suffix or not key.endswith(project_suffix) or key.endswith(DEV_KEY_SUFFIX):
            return "GOOGLE_API_KEY is not the Formal judge project key"
        if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI")):
            return "a Google credential override variable is set"
        j = holder.get("judge")
        # engine .10 (R2-B4) / .12 (D1): the whole settlement of this batch after the next request, its inferred buffer and repricing included
        if base_total + next_liability_bound_usd(j, request_chars, max_tokens, request_bytes) > ceiling:
            return f"formal judge ceiling {ceiling} USD would be exceeded"
        return None
    return guard


def _grade(r: dict, est: Decimal, log, auth: dict, extra: list | None = None, project_suffix: str | None = None) -> dict:
    from grading import run_grading as RG
    from grading.judge import ProviderJudge
    c = cfg()["judge"]
    os.makedirs(r["grading_out"], mode=0o700, exist_ok=True)
    os.chmod(SEALED, 0o700)
    snap = ensure_ledger().snapshot()
    base = Decimal(snap["settled_usd"]) + Decimal(snap["reserved_usd"])
    holder: dict = {}

    def factory(model, cfgd):
        j = ProviderJudge(model, temperature=c["temperature"], max_tokens=c["max_tokens"], max_retries=c["max_retries"], reasoning_effort=c["reasoning_effort"],
                          pacing_pause_s=c.get("pacing_pause_s", 0.0), provider_error_stop_items=c.get("provider_error_stop_items"), item_wall_clock_cap_s=c.get("item_wall_clock_cap_s"),
                          cost_guard=make_guard(holder, c["max_tokens"], base, Decimal(str(c["formal"]["ceiling_usd"])), project_suffix))
        holder["judge"] = j
        return j
    argv = ["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"], "--ledger", r["gen_ledger"],
            "--unit-id", r["unit_id"], "--judge", "--judge-model", c["model"], "--judge-estimate-usd", str(est), "--confirm-judge", f"{r['run_uuid']}|{c['model']}|{est}",
            "--authorized-by", auth["by"], "--authorization-ref", auth["ref"], "--env-file", os.path.join(ROOT, ".env"), "--judge-ledger", LEDGER] + list(extra or [])
    with contextlib.redirect_stdout(log):
        rc = RG.main(argv, judge_factory=factory)
    j = holder.get("judge")
    calls = getattr(j, "calls", []) or []
    return {"rc": rc, "calls": len(calls), "calls_ok": sum(1 for x in calls if x.get("status") == "ok"), "provider_error": sum(1 for x in calls if x.get("status") == "provider_error"),
            "not_attempted": sum(1 for x in calls if x.get("status") == "not_attempted"), "halted": getattr(j, "halted", None), "daily_quota": getattr(j, "daily_quota", None),
            "cost_from_calls_usd": str(sum((call_cost_usd(x["usage"]) for x in calls if x.get("usage")), Decimal(0)).quantize(Decimal("0.000001")))}


def _grade_deterministic(r: dict, log) -> dict:
    """A run whose task has no judge-only criterion: graded without a call, its output sealed like every other."""
    from grading import run_grading as RG
    os.makedirs(r["grading_out"], mode=0o700, exist_ok=True)
    with contextlib.redirect_stdout(log):
        rc = RG.main(["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"],
                      "--ledger", r["gen_ledger"], "--unit-id", r["unit_id"]])
    return {"rc": rc, "calls": 0}


def one_call_usd() -> Decimal:
    """The worst case of one judge call (the long tier, a 40,000-character request): the least headroom a start needs."""
    return worst_case_usd(40_000, cfg()["judge"]["max_tokens"], "long")


def reservation_usd(n_items: int, remaining: Decimal) -> Decimal:
    """A run's judge reservation: the worst case of each of its items, at most the remaining budget (a hold released to
    the actual cost at settlement; the per-call guard, not the reservation, bounds the spend)."""
    return min((one_call_usd() * max(1, n_items)).quantize(Decimal("0.01"), rounding=ROUND_CEILING), remaining)


def recovery_items(r: dict) -> tuple[str | None, list[int]]:
    """The run's latest judged pass and its items eligible for the bounded per-item recovery: provider_error retried
    once, a never-sent item evaluated (judge_recovery's bound; completed and exhausted items are never sent). Engine .12
    (D3): the current pass is the authoritative selection over the run's judge history; none while it is blocked."""
    from grading import judge_recovery as JR
    current = JR.authoritative_recovery(cfg(), r.get("host_dir"), r["grading_out"], r["run_uuid"], r["judge_items"])
    return current["base"], current["items"]


def pending_pause() -> dict | None:
    last = None
    for e in registry_events():
        if e.get("kind") == "quota_pause":
            last = e
        elif e.get("kind") == "quota_resume":
            last = None
    return last


def run(authorized_by: str | None, authorization_ref: str | None, confirm: str | None, poll_s: int = POLL_S, max_idle_polls: int = 600, resume: bool = False, sleep=None) -> int:
    sleep = sleep or time.sleep
    g = gates()
    if not g["ok"]:
        raise SystemExit(f"gates not met: { {k: v for k, v in g.items() if isinstance(v, dict) and not v.get('ok')} }")
    c = cfg()["judge"]
    scope = f"judge-formal|{c['model']}|{c['formal']['ceiling_usd']}"
    if not (authorized_by and authorization_ref) or confirm != scope:
        raise SystemExit(f"run requires --authorized-by, --authorization-ref (the Formal launch authorization) and --confirm '{scope}'")
    auth = {"by": authorized_by, "ref": authorization_ref}
    ev = registry_events()
    started = any(e.get("kind") == "pass_start" for e in ev)
    if started and not resume:
        raise SystemExit("the one formal judge pass has already started; continuing or repeating it is the human's decision (partial state is kept)")
    if resume:
        if not started:
            raise SystemExit("no formal judge pass to resume")
        stops = [e["kind"] for e in ev if e.get("kind") in STOPS]
        if stops or any(e.get("kind") == "pass_end" for e in ev):
            raise SystemExit(f"the pass ended or stopped ({stops or 'pass_end'}); continuing it is the human's decision")
    units = int(cfg()["batches"]["formal"]["units_total"])
    os.environ.pop("GOOGLE_API_KEY", None)  # the Formal project's key only (select_project_credential), never an inherited one
    cred = select_project_credential()
    os.makedirs(SEALED, mode=0o700, exist_ok=True)
    os.chmod(SEALED, 0o700)
    log = open(os.path.join(SEALED, f"{PASS_ID}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "pass_resume" if resume else "pass_start", "freeze_commit": g["freeze_tag"]["commit"], "authorization": {**auth, "confirm": confirm}, "credential": cred})
    idle = 0
    while True:
        p = pending_pause()
        if p:
            wait = (dt.datetime.fromisoformat(p["resume_at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
            if wait > 0:
                sleep(wait); continue
            registry({"kind": "quota_resume", "paused_at": p["at"], "resume_at": p["resume_at"]})
        if not on_ac_power():
            if not any(e.get("kind") == "power_wait" for e in registry_events()[-3:]):
                registry({"kind": "power_wait"})
            sleep(poll_s); continue
        done = {e["run_uuid"] for e in registry_events() if e.get("kind") in ("run_done", "run_error")}
        errored = {e["run_uuid"] for e in registry_events() if e.get("kind") in ("run_error", "recovery_error")}
        snap = ensure_ledger().snapshot()
        if snap.get("stops") or snap.get("review_pending_units") or snap.get("open_reservations"):
            registry({"kind": "ledger_stop", "stops": len(snap.get("stops") or []), "held": len(snap.get("review_pending_units") or []), "open": len(snap.get("open_reservations") or [])}); break
        # 1. the bounded per-item recoveries of runs already judged in this pass (after a quota pause: their unsent items)
        pending = []
        for r in finalized_runs():
            if r["run_uuid"] in done and r["run_uuid"] not in errored and r["judge_items"]:
                base, items = recovery_items(r)
                if items:
                    pending.append((r, base, items))
        if pending:
            r, base, items = pending[0]
            if Decimal(snap["remaining_usd"]) < one_call_usd():
                registry({"kind": "budget_stop", "remaining_usd": snap["remaining_usd"], "unrecovered_items": len(items)}); break
            est = reservation_usd(len(items), Decimal(snap["remaining_usd"]))
            registry({"kind": "recovery_start", "run_uuid": r["run_uuid"], "items": len(items), "reservation_usd": str(est)})
            try:
                rec = _grade(r, est, log, auth, ["--judge-recover", ",".join(map(str, items)), "--base-pass", base], project_suffix=cred["suffix"])
            except Exception as ex:  # recorded, never retried automatically
                registry({"kind": "recovery_error", "run_uuid": r["run_uuid"], "error": type(ex).__name__}); break
            registry({"kind": "recovery_done", "run_uuid": r["run_uuid"], **{k: v for k, v in rec.items() if k != "daily_quota"}})
            if rec.get("daily_quota"):
                registry({"kind": "quota_pause", "run_uuid": r["run_uuid"], "daily_quota": rec["daily_quota"], "resume_at": quota_resume_at(rec["daily_quota"]).isoformat(timespec="seconds")}); continue
            if rec.get("halted"):
                registry({"kind": "halted", "run_uuid": r["run_uuid"]}); break
            continue
        # 2. the next finalized run
        if len(done) >= units:
            break
        todo = [r for r in finalized_runs() if r["run_uuid"] not in done]
        if not todo:
            idle += 1
            if idle > max_idle_polls:
                registry({"kind": "idle_stop", "judged": len(done)}); break
            sleep(poll_s); continue
        idle = 0
        r = todo[0]
        if r["judge_items"] and Decimal(snap["remaining_usd"]) < one_call_usd():
            registry({"kind": "budget_stop", "remaining_usd": snap["remaining_usd"], "pending_runs": len(todo)}); break
        est = reservation_usd(len(r["judge_items"]), Decimal(snap["remaining_usd"]))
        registry({"kind": "run_start", "run_uuid": r["run_uuid"], "task_id": r["task_id"], "judge_items": len(r["judge_items"]), "reservation_usd": str(est)})
        try:
            out = _grade(r, est, log, auth, project_suffix=cred["suffix"]) if r["judge_items"] else _grade_deterministic(r, log)
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": r["run_uuid"], "error": type(ex).__name__}); continue
        registry({"kind": "run_done", "run_uuid": r["run_uuid"], "task_id": r["task_id"], **{k: v for k, v in out.items() if k != "daily_quota"}})
        if out.get("daily_quota"):
            registry({"kind": "quota_pause", "run_uuid": r["run_uuid"], "daily_quota": out["daily_quota"], "resume_at": quota_resume_at(out["daily_quota"]).isoformat(timespec="seconds")}); continue
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": r["run_uuid"]}); break
    registry({"kind": "pass_end", "judged": len({e["run_uuid"] for e in registry_events() if e.get("kind") == "run_done"})})
    return 0


def status() -> dict:
    ev = registry_events()
    snap = ensure_ledger().snapshot() if os.path.isfile(LEDGER) else None
    return {"judged_runs": sum(1 for e in ev if e.get("kind") == "run_done"), "errors": sum(1 for e in ev if e.get("kind") in ("run_error", "recovery_error")),
            "stops": [e["kind"] for e in ev if e.get("kind") in STOPS], "quota_pauses": sum(1 for e in ev if e.get("kind") in PAUSES), "paused": bool(pending_pause()),
            "calls": sum(int(e.get("calls") or 0) for e in ev if e.get("kind") in ("run_done", "recovery_done")),
            "provider_errors": sum(int(e.get("provider_error") or 0) for e in ev if e.get("kind") in ("run_done", "recovery_done")),
            "ledger": {k: snap.get(k) for k in ("settled_usd", "reserved_usd", "remaining_usd", "stops")} if snap else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="formal judge pass (one pass, frozen judge, hidden results)")
    ap.add_argument("command", choices=("check", "run", "resume", "status"))
    ap.add_argument("--authorized-by", default=None); ap.add_argument("--authorization-ref", default=None); ap.add_argument("--confirm", default=None)
    a = ap.parse_args(argv)
    if a.command == "check":
        print(json.dumps({"gates": gates(), "finalized_runs": len(finalized_runs())}, indent=1, default=str))
    elif a.command in ("run", "resume"):
        return run(a.authorized_by, a.authorization_ref, a.confirm, resume=a.command == "resume")
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
