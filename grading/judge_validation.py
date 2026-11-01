"""Judge Validation (authorized by the human 2026-11-01): one full pass of the frozen shared judge over the ten sealed
Validation outputs, through the official grading entry (`grading.run_grading --judge`), so each Validation output is
revealed once, graded once per frozen version, deterministic and judge items together.

Gates, all checked before the first call (FAIL-CLOSED):
- the plan (grading/judge_validation/plan.json) is committed;
- the grading and harness code and config.json are byte-identical to the freeze tag (FREEZE_TAG) and uncommitted
  changes in them are absent, so the shared judge prompt, model configuration and every task's V1 grader and evidence
  builder are the frozen ones (grading/freeze/v1_manifest.json records them);
- the frozen manifest still matches the code (versions, prompt hash).

Costs go to the separate Judge Validation ledger (~/turing-eval-runs/judge_validation/ledger.json, ceiling 15 USD); a
per-call guard counts every call at its worst case (long-context rates, full output cap) against the ceiling before it
is sent, checks that GOOGLE_API_KEY is the Dev project key (the human's choice for this pass) and that no override
variable is set. Concurrency 1; no repeat pass; a failed run is recorded and never retried automatically. A task
without judge items is graded deterministically (no paid call).

Output: cost and coverage only. Verdicts stay in the grading outputs, hidden from the human until the Validation labels
are saved. Usage:
  python -m grading.judge_validation check   # gates only, no call
  python -m grading.judge_validation run     # the pass (paid)
  python -m grading.judge_validation status  # cost and coverage so far"""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
from decimal import ROUND_CEILING, Decimal

from grading.judge_dev import DEV_KEY_SUFFIX, call_cost_usd, worst_case_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
VDIR = os.path.join(BASE, "judge_validation")
LEDGER = os.path.join(VDIR, "ledger.json")
REGISTRY = os.path.join(VDIR, "registry.jsonl")
PLAN = os.path.join(ROOT, "grading", "judge_validation", "plan.json")
MANIFEST = os.path.join(ROOT, "grading", "freeze", "v1_manifest.json")
FREEZE_TAG = "v1-calibration-freeze"
PASS_ID = "judge-validation-pass-1"
FROZEN_PATHS = ("grading", "harness", "config.json")
AUTH_REF = "docs/status.md decision 2026-11-01: Judge Validation authorized (one pass, frozen judge, separate ledger, 15 USD, concurrency 1, Dev project key)"


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def cfg():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def registry(event: dict) -> None:
    os.makedirs(VDIR, exist_ok=True)
    with open(REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), "pass": PASS_ID, **event}, default=str) + "\n")


def registry_events() -> list[dict]:
    if not os.path.exists(REGISTRY):
        return []
    return [json.loads(l) for l in open(REGISTRY, encoding="utf-8") if l.strip()]


def validation_runs() -> list[dict]:
    """The canonical Validation run of every task (metadata only: run inventory and designations; no output opened)."""
    from grading.grade import TASK_MODULES
    runs_root = os.path.join(BASE, "validation", "runs")
    des, inv = {}, {}
    for l in open(os.path.join(runs_root, "canonical_designations.jsonl"), encoding="utf-8"):
        d = json.loads(l); des[d["run_uuid"]] = d
    for l in open(os.path.join(runs_root, "run_inventory.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r.get("run_uuid"):
            inv[r["run_uuid"]] = r
    out = []
    for t in sorted(TASK_MODULES):
        canon = [u for u, d in des.items() if d["task_id"] == t and d["designation"] == "canonical"]
        if len(canon) != 1:
            raise SystemExit(f"task {t}: {len(canon)} canonical Validation runs (exactly one required)")
        u = canon[0]; r = inv[u]
        mod = __import__(f"grading.checks_{t[:8]}", fromlist=["J_ITEMS"])
        out.append({"task_id": t, "run_uuid": u, "host_dir": os.path.join(runs_root, u), "eval_log": r["log_file"], "unit_id": r["unit_id"], "judge_items": list(mod.J_ITEMS),
                    "grading_out": os.path.join(BASE, "validation", "grading", u)})
    return out


def frozen_state() -> dict:
    """The freeze gate: code identical to the tag, no uncommitted change, manifest consistent with the code."""
    from grading.freeze_manifest import verify
    tag = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{FREEZE_TAG}^{{commit}}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if not tag:
        return {"ok": False, "reason": f"tag {FREEZE_TAG} does not exist"}
    diff = subprocess.run(["git", "diff", "--name-only", tag, "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if diff or dirty:
        return {"ok": False, "reason": f"frozen paths differ from {FREEZE_TAG}: {(diff or dirty).splitlines()[:6]}"}
    problems = verify(json.load(open(MANIFEST, encoding="utf-8")))
    if problems:
        return {"ok": False, "reason": f"freeze manifest does not match the code: {problems[:4]}"}
    return {"ok": True, "tag_commit": tag}


def ensure_ledger() -> dict:
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    if not os.path.isfile(LEDGER):
        os.makedirs(VDIR, exist_ok=True)
        BudgetLedger(LEDGER, Decimal(str(cfg()["judge"]["validation"]["ceiling_usd"])), prices_from_config(cfg()), label="judge_validation")
    return BudgetLedger.open_existing(LEDGER, prices_from_config(cfg())).identity()


def spent() -> dict:
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    snap = BudgetLedger.open_existing(LEDGER, prices_from_config(cfg())).snapshot()
    return {"settled": Decimal(snap["settled_usd"]), "reserved": Decimal(snap["reserved_usd"]), "total": Decimal(snap["settled_usd"]) + Decimal(snap["reserved_usd"]), "snapshot": snap}


def make_guard(holder: dict, max_tokens: int, base_total: Decimal, ceiling: Decimal):
    def guard(request_chars: int):
        key = os.environ.get("GOOGLE_API_KEY") or ""
        if not key.endswith(DEV_KEY_SUFFIX):
            return "GOOGLE_API_KEY is not the Dev project key"
        if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI")):
            return "a Google credential override variable is set"
        j = holder.get("judge")
        so_far = sum((call_cost_usd(cl["usage"], "long") for cl in (getattr(j, "calls", None) or []) if cl.get("usage")), Decimal(0))
        nxt = worst_case_usd(request_chars, max_tokens, "long")
        if base_total + so_far + nxt > ceiling:
            return f"Judge Validation ceiling {ceiling} USD would be exceeded (ledger {base_total:.4f} + this run {so_far:.4f} + worst case {nxt:.4f})"
        return None
    return guard


def grade_run(spec: dict, r: dict, log) -> dict:
    from grading import run_grading as RG
    from grading.judge import ProviderJudge
    c = cfg()["judge"]
    os.makedirs(r["grading_out"], exist_ok=True)
    argv = ["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"], "--ledger", os.path.join(BASE, "validation", "ledger.json"),
            "--unit-id", r["unit_id"]]
    holder: dict = {}
    factory = None
    if r["judge_items"]:
        est = Decimal(spec["reservation_usd"])
        base = spent()["total"]  # before this run's reservation
        ceiling = Decimal(str(c["validation"]["ceiling_usd"]))

        def factory(model, cfgd):
            j = ProviderJudge(model, temperature=c["temperature"], max_tokens=c["max_tokens"], max_retries=c["max_retries"], reasoning_effort=c["reasoning_effort"],
                              cost_guard=make_guard(holder, c["max_tokens"], base, ceiling))
            holder["judge"] = j
            return j
        argv += ["--judge", "--judge-model", c["model"], "--judge-estimate-usd", str(est), "--confirm-judge", f"{r['run_uuid']}|{c['model']}|{est}",
                 "--authorized-by", "Yuning Zhang (approved in chat 2026-11-01)", "--authorization-ref", AUTH_REF, "--env-file", os.path.join(ROOT, ".env"), "--judge-ledger", LEDGER]
    with contextlib.redirect_stdout(log):
        rc = RG.main(argv, judge_factory=factory) if factory else RG.main(argv)
    j = holder.get("judge")
    calls = getattr(j, "calls", []) or []
    rec = RG.grading_passes(r["grading_out"], r["run_uuid"])[-1] if RG.grading_passes(r["grading_out"], r["run_uuid"]) else {}
    return {"rc": rc, "judge_unit": rec.get("judge_unit"), "grading_pass": rec.get("grading_pass"), "graded": rec.get("graded"), "gate": rec.get("gate"), "grader_version": rec.get("grader_version"),
            "calls": len(calls), "calls_ok": sum(1 for x in calls if x.get("status") == "ok"), "not_attempted": sum(1 for x in calls if x.get("status") == "not_attempted"),
            "provider_error": sum(1 for x in calls if x.get("status") == "provider_error"), "halted": getattr(j, "halted", None),
            "cost_from_calls_usd": str(sum((call_cost_usd(x["usage"]) for x in calls if x.get("usage")), Decimal(0)).quantize(Decimal("0.000001")))}


def check() -> dict:
    plan_dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", PLAN], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    fz = frozen_state()
    return {"plan_committed": os.path.isfile(PLAN) and not plan_dirty, "freeze": fz}


def run() -> int:
    ck = check()
    if not ck["plan_committed"]:
        raise SystemExit("the Judge Validation plan must be committed before any paid call")
    if not ck["freeze"]["ok"]:
        raise SystemExit(f"freeze gate: {ck['freeze']['reason']}")
    plan = json.load(open(PLAN, encoding="utf-8"))
    ensure_ledger()
    os.environ.pop("GOOGLE_API_KEY_VALIDATION", None)
    log = open(os.path.join(VDIR, f"{PASS_ID}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "pass_start", "plan_sha256": hashlib.sha256(open(PLAN, "rb").read()).hexdigest(), "freeze_tag_commit": ck["freeze"]["tag_commit"],
              "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    runs = {r["run_uuid"]: r for r in validation_runs()}
    done = {e["run_uuid"] for e in registry_events() if e.get("kind") in ("run_done", "run_error")}
    for spec in plan["order"]:
        u = spec["run_uuid"]
        if u in done:
            continue
        r = runs.get(u)
        if r is None or r["task_id"] != spec["task_id"] or len(r["judge_items"]) != spec["judge_items"]:
            registry({"kind": "skipped", "run_uuid": u, "reason": "the run no longer matches the plan"}); continue
        if spent()["snapshot"].get("stops"):
            registry({"kind": "budget_stop", "stops": spent()["snapshot"]["stops"]}); break
        registry({"kind": "run_start", "run_uuid": u, "task_id": r["task_id"], "judge_items": len(r["judge_items"]), "reservation_usd": spec["reservation_usd"]})
        try:
            out = grade_run(spec, r, log)
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": u, "error": f"{type(ex).__name__}: {str(ex)[:300]}"}); continue
        registry({"kind": "run_done", "run_uuid": u, "task_id": r["task_id"], "unit_id": out["judge_unit"], **{k: v for k, v in out.items() if k != "judge_unit"}})
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": u, "reason": out["halted"]}); break
    registry({"kind": "pass_end", "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    return 0


def status() -> dict:
    ev = registry_events()
    s = spent() if os.path.isfile(LEDGER) else None
    done = [e for e in ev if e.get("kind") == "run_done"]
    return {"ledger": {k: s["snapshot"].get(k) for k in ("settled_usd", "reserved_usd", "remaining_usd", "review_pending_units", "stops")} if s else None,
            "runs_done": [{k: e.get(k) for k in ("task_id", "calls", "calls_ok", "not_attempted", "provider_error", "cost_from_calls_usd", "graded", "gate", "halted")} for e in done],
            "errors": [{k: e.get(k) for k in ("run_uuid", "error")} for e in ev if e.get("kind") == "run_error"]}


def write_plan() -> dict:
    """The run order and per-run reservations, from metadata and the Dev Pass 1 provider cost of the same task (3x, at
    least 0.30 USD; the per-call guard, not the reservation, bounds the spend). Largest first, so the largest units meet
    the most ledger headroom."""
    if os.path.exists(PLAN):
        raise SystemExit(f"{PLAN} exists; a plan is never overwritten")
    dev = {}
    for e in (json.loads(l) for l in open(os.path.join(BASE, "judge_dev", "registry.jsonl"), encoding="utf-8") if l.strip()):
        if e.get("kind") == "run_done" and e.get("pass") == "judge-dev-pass-1":
            dev[e["task_id"]] = Decimal(e["cost_from_calls_usd"])
    order = []
    for r in validation_runs():
        res = max(Decimal("0.30"), 3 * dev.get(r["task_id"], Decimal("0.30"))).quantize(Decimal("0.01"), rounding=ROUND_CEILING) if r["judge_items"] else Decimal(0)
        order.append({"task_id": r["task_id"], "run_uuid": r["run_uuid"], "judge_items": len(r["judge_items"]), "reservation_usd": str(res),
                      "dev_pass1_provider_usd": str(dev.get(r["task_id"])) if r["task_id"] in dev else None})
    order.sort(key=lambda x: (-Decimal(x["reservation_usd"]), x["task_id"]))
    c = cfg()["judge"]
    plan = {"pass": PASS_ID, "created_at": _now(), "model": c["model"], "settings": {k: c[k] for k in ("temperature", "max_tokens", "max_retries", "reasoning_effort")},
            "prompt_sha256": c["prompt_sha256"], "ceiling_usd": c["validation"]["ceiling_usd"], "concurrency": 1, "repeats": 0, "freeze_tag": FREEZE_TAG,
            "authorization_ref": AUTH_REF, "order": order, "judge_units": sum(x["judge_items"] for x in order)}
    os.makedirs(os.path.dirname(PLAN), exist_ok=True)
    with open(PLAN, "x", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Judge Validation (one pass, frozen judge)")
    ap.add_argument("command", choices=("plan", "check", "run", "status"))
    a = ap.parse_args(argv)
    if a.command == "plan":
        p = write_plan()
        print(json.dumps({k: p[k] for k in ("judge_units", "ceiling_usd")} | {"order": [(x["task_id"][:8], x["judge_items"], x["reservation_usd"]) for x in p["order"]]}, indent=1))
    elif a.command == "check":
        print(json.dumps(check(), indent=1))
    elif a.command == "run":
        return run()
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
