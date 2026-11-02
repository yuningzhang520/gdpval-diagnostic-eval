"""Formal judge pass (approved in advance by the human 2026-11-01; config ``judge.formal``): one pass of the frozen judge over
the 20 formal outputs, each judged as soon as its run is finalized while generation continues. PREPARED, NOT RUN: the
paid command refuses until every gate holds.

Gates (FAIL-CLOSED, checked before any call):
- the tag ``freeze-v1`` exists, the grading and harness code and config.json are identical to it, nothing is uncommitted,
  and its freeze record (grading/freeze/freeze-v1_manifest.json) verifies;
- config.json is marked FROZEN (``_status``);
- ``judge.formal`` holds the approved ceiling (30 USD), concurrency 1, one pass;
- ``run`` restates the human's Formal launch authorization (``--authorized-by``, ``--authorization-ref`` naming its
  docs/status.md entry, recorded verbatim; that authorization also authorizes this pass) and the scope
  (``--confirm 'judge-formal|<judge model>|<ceiling>'``).

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

from grading.judge_dev import DEV_KEY_SUFFIX, batch_liability_usd, call_cost_usd, next_request_bound_usd, worst_case_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
RUNS = os.path.join(BASE, "formal", "runs")
SEALED = os.path.join(BASE, "formal", "grading_sealed")
JDIR = os.path.join(BASE, "judge_formal")
LEDGER = os.path.join(JDIR, "ledger.json")
REGISTRY = os.path.join(JDIR, "registry.jsonl")
FREEZE_TAG = "freeze-v1"
MANIFEST = os.path.join(ROOT, "grading", "freeze", "freeze-v1_manifest.json")
FROZEN_PATHS = ("grading", "harness", "config.json")
PASS_ID = "judge-formal-pass-1"
POLL_S = 60
STOPS = ("budget_stop", "ledger_stop", "halted", "recovery_error", "idle_stop")


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
    out["config_frozen"] = {"ok": str(cfg().get("_status", "")).startswith("FROZEN"), "status": str(cfg().get("_status", ""))[:60]}
    f = (cfg().get("judge") or {}).get("formal") or {}
    out["judge_formal_config"] = {"ok": Decimal(str(f.get("ceiling_usd", 0))) == Decimal(30) and f.get("concurrency") == 1 and f.get("passes") == 1 and f.get("repeats") == 0,
                                  "ceiling_usd": f.get("ceiling_usd"), "concurrency": f.get("concurrency"), "passes": f.get("passes")}
    out["ok"] = all(v.get("ok") for v in out.values() if isinstance(v, dict))
    return out


def finalized_runs() -> list[dict]:
    """Canonical formal runs whose outcome is final and whose eval log exists (metadata only; no output is opened)."""
    from grading.grade import TASK_MODULES
    des_p, inv_p = os.path.join(RUNS, "canonical_designations.jsonl"), os.path.join(RUNS, "run_inventory.jsonl")
    if not (os.path.isfile(des_p) and os.path.isfile(inv_p)):
        return []
    des = [json.loads(l) for l in open(des_p, encoding="utf-8") if l.strip()]
    inv = {r["run_uuid"]: r for r in (json.loads(l) for l in open(inv_p, encoding="utf-8") if l.strip()) if r.get("run_uuid")}
    out = []
    for d in des:
        u, t = d.get("run_uuid"), d.get("task_id")
        if d.get("designation") != "canonical" or u not in inv or t not in TASK_MODULES:
            continue
        host = os.path.join(RUNS, u)
        oc = os.path.join(host, "run_outcome.json")
        try:
            final = json.load(open(oc, encoding="utf-8")).get("final") is True
        except (OSError, ValueError):
            final = False
        log = inv[u].get("log_file")
        if final and log and os.path.isfile(log):
            mod = __import__(f"grading.checks_{t[:8]}", fromlist=["J_ITEMS"])
            out.append({"task_id": t, "run_uuid": u, "model": d.get("model"), "host_dir": host, "eval_log": log, "unit_id": inv[u].get("unit_id"),
                        "judge_items": list(mod.J_ITEMS), "grading_out": os.path.join(SEALED, u)})
    return out


def ensure_ledger():
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    if not os.path.isfile(LEDGER):
        os.makedirs(JDIR, exist_ok=True)
        BudgetLedger(LEDGER, Decimal(str(cfg()["judge"]["formal"]["ceiling_usd"])), prices_from_config(cfg()), label="judge_formal")
    return BudgetLedger.open_existing(LEDGER, prices_from_config(cfg()))


def make_guard(holder: dict, max_tokens: int, base_total: Decimal, ceiling: Decimal):
    def guard(request_chars: int):
        key = os.environ.get("GOOGLE_API_KEY") or ""
        if not key.endswith(DEV_KEY_SUFFIX):
            return "GOOGLE_API_KEY is not the judge project key"
        if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI")):
            return "a Google credential override variable is set"
        j = holder.get("judge")
        so_far = batch_liability_usd(j)  # engine .10 (R2-B4): metered calls plus the inferred buffer the ledger settles for this batch
        nxt = next_request_bound_usd(j, request_chars, max_tokens)
        if base_total + so_far + nxt > ceiling:
            return f"formal judge ceiling {ceiling} USD would be exceeded"
        return None
    return guard


def _grade(r: dict, est: Decimal, log, auth: dict, extra: list | None = None) -> dict:
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
                          cost_guard=make_guard(holder, c["max_tokens"], base, Decimal(str(c["formal"]["ceiling_usd"]))))
        holder["judge"] = j
        return j
    argv = ["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"], "--ledger", os.path.join(BASE, "formal", "ledger.json"),
            "--unit-id", r["unit_id"], "--judge", "--judge-model", c["model"], "--judge-estimate-usd", str(est), "--confirm-judge", f"{r['run_uuid']}|{c['model']}|{est}",
            "--authorized-by", auth["by"], "--authorization-ref", auth["ref"], "--env-file", os.path.join(ROOT, ".env"), "--judge-ledger", LEDGER] + list(extra or [])
    with contextlib.redirect_stdout(log):
        rc = RG.main(argv, judge_factory=factory)
    j = holder.get("judge")
    calls = getattr(j, "calls", []) or []
    return {"rc": rc, "calls": len(calls), "calls_ok": sum(1 for x in calls if x.get("status") == "ok"), "provider_error": sum(1 for x in calls if x.get("status") == "provider_error"),
            "not_attempted": sum(1 for x in calls if x.get("status") == "not_attempted"), "halted": getattr(j, "halted", None),
            "cost_from_calls_usd": str(sum((call_cost_usd(x["usage"]) for x in calls if x.get("usage")), Decimal(0)).quantize(Decimal("0.000001")))}


def _grade_deterministic(r: dict, log) -> dict:
    """A run whose task has no judge-only criterion: graded without a call, its output sealed like every other."""
    from grading import run_grading as RG
    os.makedirs(r["grading_out"], mode=0o700, exist_ok=True)
    with contextlib.redirect_stdout(log):
        rc = RG.main(["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"],
                      "--ledger", os.path.join(BASE, "formal", "ledger.json"), "--unit-id", r["unit_id"]])
    return {"rc": rc, "calls": 0}


def one_call_usd() -> Decimal:
    """The worst case of one judge call (the long tier, a 40,000-character request): the least headroom a start needs."""
    return worst_case_usd(40_000, cfg()["judge"]["max_tokens"], "long")


def reservation_usd(n_items: int, remaining: Decimal) -> Decimal:
    """A run's judge reservation: the worst case of each of its items, at most the remaining budget (a hold released to
    the actual cost at settlement; the per-call guard, not the reservation, bounds the spend)."""
    return min((one_call_usd() * max(1, n_items)).quantize(Decimal("0.01"), rounding=ROUND_CEILING), remaining)


def run(authorized_by: str | None, authorization_ref: str | None, confirm: str | None, poll_s: int = POLL_S, max_idle_polls: int = 600) -> int:
    g = gates()
    if not g["ok"]:
        raise SystemExit(f"gates not met: { {k: v for k, v in g.items() if isinstance(v, dict) and not v.get('ok')} }")
    c = cfg()["judge"]
    scope = f"judge-formal|{c['model']}|{c['formal']['ceiling_usd']}"
    if not (authorized_by and authorization_ref) or confirm != scope:
        raise SystemExit(f"run requires --authorized-by, --authorization-ref (the Formal launch authorization) and --confirm '{scope}'")
    auth = {"by": authorized_by, "ref": authorization_ref}
    if any(e.get("kind") == "pass_start" for e in registry_events()):
        raise SystemExit("the one formal judge pass has already started; continuing or repeating it is the human's decision (partial state is kept)")
    units = int(cfg()["batches"]["formal"]["units_total"])
    from grading import judge_recovery as JR
    from grading import run_grading as RG
    os.environ.pop("GOOGLE_API_KEY_VALIDATION", None)
    os.makedirs(SEALED, mode=0o700, exist_ok=True)
    os.chmod(SEALED, 0o700)
    log = open(os.path.join(SEALED, f"{PASS_ID}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "pass_start", "freeze_commit": g["freeze_tag"]["commit"], "authorization": {**auth, "confirm": confirm}})
    idle = 0
    while True:
        done = {e["run_uuid"] for e in registry_events() if e.get("kind") in ("run_done", "run_error")}
        if len(done) >= units:
            break
        todo = [r for r in finalized_runs() if r["run_uuid"] not in done]
        if not todo:
            idle += 1
            if idle > max_idle_polls:
                registry({"kind": "idle_stop", "judged": len(done)}); break
            time.sleep(poll_s); continue
        idle = 0
        snap = ensure_ledger().snapshot()
        if snap.get("stops") or snap.get("review_pending_units") or snap.get("open_reservations"):
            registry({"kind": "ledger_stop", "stops": len(snap.get("stops") or []), "held": len(snap.get("review_pending_units") or []), "open": len(snap.get("open_reservations") or [])}); break
        r = todo[0]
        if r["judge_items"] and Decimal(snap["remaining_usd"]) < one_call_usd():
            registry({"kind": "budget_stop", "remaining_usd": snap["remaining_usd"], "pending_runs": len(todo)}); break
        est = reservation_usd(len(r["judge_items"]), Decimal(snap["remaining_usd"]))
        registry({"kind": "run_start", "run_uuid": r["run_uuid"], "task_id": r["task_id"], "judge_items": len(r["judge_items"]), "reservation_usd": str(est)})
        try:
            out = _grade(r, est, log, auth) if r["judge_items"] else _grade_deterministic(r, log)
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": r["run_uuid"], "error": type(ex).__name__}); continue
        registry({"kind": "run_done", "run_uuid": r["run_uuid"], "task_id": r["task_id"], **out})
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": r["run_uuid"]}); break
        if r["judge_items"] and (out.get("provider_error") or out.get("not_attempted")):  # one bounded per-item recovery within the pass
            judged = [p for p in RG.grading_passes(r["grading_out"], r["run_uuid"]) if p.get("judge_mode") == "real"]
            plan = JR.recovery_plan(r["grading_out"], r["run_uuid"], judged[-1]["grading_pass"], list(r["judge_items"])) if judged else {"decision": {}}
            items = sorted(i for i, d in plan["decision"].items() if d["eligible"] and d["base_call_status"] in ("provider_error", "not_attempted"))
            snap = ensure_ledger().snapshot()
            if items and Decimal(snap["remaining_usd"]) < one_call_usd():
                registry({"kind": "budget_stop", "remaining_usd": snap["remaining_usd"], "unrecovered_items": len(items)}); break
            if items:
                est2 = reservation_usd(len(items), Decimal(snap["remaining_usd"]))
                registry({"kind": "recovery_start", "run_uuid": r["run_uuid"], "items": len(items), "reservation_usd": str(est2)})
                try:
                    rec = _grade(r, est2, log, auth, ["--judge-recover", ",".join(map(str, items)), "--base-pass", judged[-1]["grading_pass"]])
                except Exception as ex:  # recorded, never retried automatically
                    registry({"kind": "recovery_error", "run_uuid": r["run_uuid"], "error": type(ex).__name__}); break
                registry({"kind": "recovery_done", "run_uuid": r["run_uuid"], **rec})
                if rec.get("halted"):
                    registry({"kind": "halted", "run_uuid": r["run_uuid"]}); break
    registry({"kind": "pass_end", "judged": len({e["run_uuid"] for e in registry_events() if e.get("kind") == "run_done"})})
    return 0


def status() -> dict:
    ev = registry_events()
    snap = ensure_ledger().snapshot() if os.path.isfile(LEDGER) else None
    return {"judged_runs": sum(1 for e in ev if e.get("kind") == "run_done"), "errors": sum(1 for e in ev if e.get("kind") in ("run_error", "recovery_error")),
            "stops": [e["kind"] for e in ev if e.get("kind") in STOPS],
            "calls": sum(int(e.get("calls") or 0) for e in ev if e.get("kind") in ("run_done", "recovery_done")),
            "provider_errors": sum(int(e.get("provider_error") or 0) for e in ev if e.get("kind") in ("run_done", "recovery_done")),
            "ledger": {k: snap.get(k) for k in ("settled_usd", "reserved_usd", "remaining_usd", "stops")} if snap else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="formal judge pass (one pass, frozen judge, hidden results)")
    ap.add_argument("command", choices=("check", "run", "status"))
    ap.add_argument("--authorized-by", default=None); ap.add_argument("--authorization-ref", default=None); ap.add_argument("--confirm", default=None)
    a = ap.parse_args(argv)
    if a.command == "check":
        print(json.dumps({"gates": gates(), "finalized_runs": len(finalized_runs())}, indent=1, default=str))
    elif a.command == "run":
        return run(a.authorized_by, a.authorization_ref, a.confirm)
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
