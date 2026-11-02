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

from grading.judge_dev import DEV_KEY_SUFFIX, batch_liability_usd, call_cost_usd, next_liability_bound_usd, on_ac_power, quota_resume_at, worst_case_usd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
VDIR = os.path.join(BASE, "judge_validation")
LEDGER = os.path.join(VDIR, "ledger.json")
REGISTRY = os.path.join(VDIR, "registry.jsonl")
PLAN = os.path.join(ROOT, "grading", "judge_validation", "plan.json")
MANIFEST = os.path.join(ROOT, "grading", "freeze", "v1_manifest.json")
FREEZE_TAG = "v1-calibration-freeze"
# Immutable code-version tags, oldest first, each with its freeze record. The gate holds the code to the latest tag that
# exists; v1-calibration-freeze is never moved. V1.1 (2026-11-01, approved): per-item judge recovery, inferred ledger
# resolutions, provider_error / not_run judge verdicts, picture-chart visual-review flags; judge prompt, model, settings
# and evidence builders byte-identical to V1 (checked by grading.freeze_manifest judge-surface).
VERSION_TAGS = ((FREEZE_TAG, MANIFEST), ("v1.1-judge-item-recovery", os.path.join(ROOT, "grading", "freeze", "v1.1_manifest.json")),
                ("v1.2-judge-infrastructure", os.path.join(ROOT, "grading", "freeze", "v1.2_manifest.json")),  # V1.2: engine .8 judge infrastructure (approved 2026-11-01)
                ("v1.3-corrections", os.path.join(ROOT, "grading", "freeze", "v1.3_manifest.json")),  # V1.3: engine .9 grader corrections and judge-runner reliability (approved 2026-11-01)
                ("v1.4-review2-corrections", os.path.join(ROOT, "grading", "freeze", "v1.4_manifest.json")),  # V1.4: engine .10 Codex Review 2 Blocking corrections (approved 2026-11-02)
                ("v1.5-item27-quota-pause", os.path.join(ROOT, "grading", "freeze", "v1.5_manifest.json")),  # V1.3.1 (2ea2e5b5 .6, item 27) and the daily-quota pause, one project per workload (approved 2026-11-02)
                ("v1.6-recovery-hash-check", os.path.join(ROOT, "grading", "freeze", "v1.6_manifest.json")),  # engine .11: Review 2 N3, recovery refused without the base request hash (approved 2026-11-02)
                ("v1.7-delta-review-corrections", os.path.join(ROOT, "grading", "freeze", "v1.7_manifest.json")),  # engine .12: Codex delta review D1-D3, N1; formal judge requires freeze-v1-grading (approved 2026-11-02)
                ("v1.8-formal-roots", os.path.join(ROOT, "grading", "freeze", "v1.8_manifest.json")))  # engine .12: the formal judge reads the three formal runs roots, each with its own generation ledger (2026-11-02)
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
    """The freeze gate: code identical to the latest existing version tag, no uncommitted change, that tag's freeze
    record consistent with the code."""
    from grading.freeze_manifest import verify
    found = []
    for name, manifest in VERSION_TAGS:
        c = subprocess.run(["git", "rev-parse", "--verify", "--quiet", f"{name}^{{commit}}"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        if c:
            found.append((name, c, manifest))
    if not found:
        return {"ok": False, "reason": f"tag {FREEZE_TAG} does not exist"}
    name, tag, manifest = found[-1]
    diff = subprocess.run(["git", "diff", "--name-only", tag, "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", *FROZEN_PATHS], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if diff or dirty:
        return {"ok": False, "reason": f"frozen paths differ from {name}: {(diff or dirty).splitlines()[:6]}"}
    problems = verify(json.load(open(manifest, encoding="utf-8")))
    if problems:
        return {"ok": False, "reason": f"freeze manifest does not match the code: {problems[:4]}"}
    return {"ok": True, "tag": name, "tag_commit": tag, "manifest": os.path.relpath(manifest, ROOT)}


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
    def guard(request_chars: int, request_bytes: int | None = None):
        key = os.environ.get("GOOGLE_API_KEY") or ""
        if not key.endswith(DEV_KEY_SUFFIX):
            return "GOOGLE_API_KEY is not the Dev project key"
        if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI")):
            return "a Google credential override variable is set"
        j = holder.get("judge")
        so_far = batch_liability_usd(j)  # engine .10 (R2-B4): metered calls plus the inferred buffer the ledger settles for this batch
        after = next_liability_bound_usd(j, request_chars, max_tokens, request_bytes)  # engine .12 (D1): the settlement after the next request, repricing included
        if base_total + after > ceiling:
            return f"Judge Validation ceiling {ceiling} USD would be exceeded (ledger {base_total:.4f} + this run {so_far:.4f}; at most {base_total + after:.4f} after the next request)"
        return None
    return guard


def grade_run(spec: dict, r: dict, log, extra_argv: list | None = None) -> dict:
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
                              pacing_pause_s=c.get("pacing_pause_s", 0.0), provider_error_stop_items=c.get("provider_error_stop_items"), item_wall_clock_cap_s=c.get("item_wall_clock_cap_s"),
                              cost_guard=make_guard(holder, c["max_tokens"], base, ceiling))
            holder["judge"] = j
            return j
        argv += ["--judge", "--judge-model", c["model"], "--judge-estimate-usd", str(est), "--confirm-judge", f"{r['run_uuid']}|{c['model']}|{est}",
                 "--authorized-by", "Yuning Zhang (approved in chat 2026-11-01)", "--authorization-ref", AUTH_REF, "--env-file", os.path.join(ROOT, ".env"), "--judge-ledger", LEDGER]
        argv += list(extra_argv or [])
    with contextlib.redirect_stdout(log):
        rc = RG.main(argv, judge_factory=factory) if factory else RG.main(argv)
    j = holder.get("judge")
    calls = getattr(j, "calls", []) or []
    rec = RG.grading_passes(r["grading_out"], r["run_uuid"])[-1] if RG.grading_passes(r["grading_out"], r["run_uuid"]) else {}
    return {"rc": rc, "judge_unit": rec.get("judge_unit"), "grading_pass": rec.get("grading_pass"), "graded": rec.get("graded"), "gate": rec.get("gate"), "grader_version": rec.get("grader_version"),
            "calls": len(calls), "calls_ok": sum(1 for x in calls if x.get("status") == "ok"), "not_attempted": sum(1 for x in calls if x.get("status") == "not_attempted"),
            "provider_error": sum(1 for x in calls if x.get("status") == "provider_error"), "halted": getattr(j, "halted", None), "daily_quota": getattr(j, "daily_quota", None),
            "cost_from_calls_usd": str(sum((call_cost_usd(x["usage"]) for x in calls if x.get("usage")), Decimal(0)).quantize(Decimal("0.000001")))}


PAUSED = 2  # run / recover: the pass was checkpointed on an exhausted daily quota (approved 2026-11-02)
STOPPED = 1  # run / recover / resume: any other stop (a non-quota halt, a recovery error, a ledger stop); engine .12 (Codex delta review D2)


def quota_pause(run_uuid: str, daily_quota: dict) -> int:
    """Checkpoint: the registry records the pause and when the pass may resume; nothing else changes (the batch's
    later items are not_attempted and stay eligible for their first evaluation; the failed item keeps its one retry)."""
    registry({"kind": "quota_pause", "run_uuid": run_uuid, "daily_quota": daily_quota, "resume_at": quota_resume_at(daily_quota).isoformat(timespec="seconds")})
    return PAUSED


def terminal_stop() -> dict | None:
    """The pass's persisted terminal stop (engine .12, D2): the latest resume_stop event. An unattended resume refuses
    before any request while one exists; continuing a stopped pass is the human's decision."""
    return next((e for e in reversed(registry_events()) if e.get("kind") == "resume_stop"), None)


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
    registry({"kind": "pass_start", "plan_sha256": hashlib.sha256(open(PLAN, "rb").read()).hexdigest(), "freeze_tag_commit": ck["freeze"]["tag_commit"], "code_tag": ck["freeze"].get("tag"),
              "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    runs = {r["run_uuid"]: r for r in validation_runs()}
    done = {e["run_uuid"] for e in registry_events() if e.get("kind") in ("run_done", "run_error")}
    rc_out = 0
    for spec in plan["order"]:
        u = spec["run_uuid"]
        if u in done:
            continue
        r = runs.get(u)
        if r is None or r["task_id"] != spec["task_id"] or len(r["judge_items"]) != spec["judge_items"]:
            registry({"kind": "skipped", "run_uuid": u, "reason": "the run no longer matches the plan"}); continue
        if spent()["snapshot"].get("stops"):
            registry({"kind": "budget_stop", "stops": spent()["snapshot"]["stops"]}); rc_out = STOPPED; break
        registry({"kind": "run_start", "run_uuid": u, "task_id": r["task_id"], "judge_items": len(r["judge_items"]), "reservation_usd": spec["reservation_usd"]})
        try:
            out = grade_run(spec, r, log)
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": u, "error": f"{type(ex).__name__}: {str(ex)[:300]}"}); continue
        registry({"kind": "run_done", "run_uuid": u, "task_id": r["task_id"], "unit_id": out["judge_unit"], **{k: v for k, v in out.items() if k != "judge_unit"}})
        if out.get("daily_quota"):
            return quota_pause(u, out["daily_quota"])
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": u, "reason": out["halted"]}); rc_out = STOPPED; break  # engine .12 (D2): the stop reaches the caller
        if r["judge_items"] and (out.get("provider_error") or out.get("not_attempted")):  # engine .8: one bounded per-item recovery pass afterwards
            items = auto_recovery_items(r)
            rc = recover(u, items) if items else 0
            if rc == PAUSED:
                return PAUSED
            if rc != 0:
                rc_out = rc; break
    registry({"kind": "pass_end", "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    return rc_out


def auto_recovery_items(r: dict) -> list[int]:
    """Items of the run's current judged pass that are eligible for the one bounded recovery (provider_error retried
    once, not_attempted run once); schema-invalid responses were already retried once inside the pass. Engine .12
    (D3): the current pass is the authoritative selection over the run's judge history; none while it is blocked."""
    from grading import judge_recovery as JR
    return JR.authoritative_recovery(cfg(), r.get("host_dir"), r["grading_out"], r["run_uuid"], r["judge_items"])["items"]


def recover(run_uuid: str, items: list[int]) -> int:
    """Per-item judge infrastructure recovery of one interrupted Validation run (approved 2026-11-01; see
    grading.judge_recovery): the listed items of the run's latest judged pass, under the same gates, guard and ceiling."""
    from grading import judge_recovery as JR
    from grading import run_grading as RG
    ck = check()
    if not ck["plan_committed"]:
        raise SystemExit("the Judge Validation plan must be committed before any paid call")
    if not ck["freeze"]["ok"]:
        raise SystemExit(f"freeze gate: {ck['freeze']['reason']}")
    snap = spent()["snapshot"]
    if snap.get("review_pending_units") or snap.get("open_reservations") or snap.get("stops"):
        raise SystemExit(f"ledger not clear: hold {snap.get('review_pending_units')}, open {snap.get('open_reservations')}, stops {snap.get('stops')}")
    r = {x["run_uuid"]: x for x in validation_runs()}.get(run_uuid)
    if r is None:
        raise SystemExit(f"{run_uuid} is not a canonical Validation run")
    current = JR.authoritative_recovery(cfg(), r.get("host_dir"), r["grading_out"], run_uuid, r["judge_items"])  # engine .12 (D3): never the last record alone
    if current["blocked"]:
        raise SystemExit(f"recovery refused: the run's current pass cannot be established from its judge history ({current['blocked']})")
    if not current["base"]:
        raise SystemExit("no judged pass to recover")
    base = current["base"]
    plan = JR.recovery_plan(r["grading_out"], run_uuid, base, items)
    refused = {i: d["reason"] for i, d in plan["decision"].items() if not d["eligible"]}
    if refused:
        raise SystemExit(f"not recoverable: {refused}")
    c = cfg()["judge"]
    est = sum((worst_case_usd(len(JR.J.JUDGE_SYSTEM_PROMPT) + len(JR.J.render_unit(plan["units"][i])), c["max_tokens"], "long") for i in items), Decimal(0)).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    planned = next((Decimal(x["reservation_usd"]) for x in json.load(open(PLAN, encoding="utf-8"))["order"] if x["run_uuid"] == run_uuid), None)
    if planned is not None and planned > 0:
        est = min(est, planned)  # never more than the run's planned reservation; the per-call guard bounds the spend against the ceiling
    log = open(os.path.join(VDIR, f"{PASS_ID}_recovery_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "recovery_start", "run_uuid": run_uuid, "task_id": r["task_id"], "base_pass": base, "items": items, "reservation_usd": str(est),
              "decision": plan["decision"], "code_tag": ck["freeze"].get("tag"), "code_tag_commit": ck["freeze"]["tag_commit"]})
    try:
        out = grade_run({"reservation_usd": str(est)}, r, log, extra_argv=["--judge-recover", ",".join(str(i) for i in items), "--base-pass", base])
    except Exception as ex:  # recorded, never retried automatically
        registry({"kind": "recovery_error", "run_uuid": run_uuid, "error": f"{type(ex).__name__}: {str(ex)[:300]}"})
        return 1
    rec = [p for p in RG.grading_passes(r["grading_out"], run_uuid)][-1]
    registry({"kind": "recovery_done", "run_uuid": run_uuid, "task_id": r["task_id"], "unit_id": out.get("judge_unit"), "recovery_pass": out.get("grading_pass"),
              "pass_kind": rec.get("pass_kind"), "judge_completeness": rec.get("judge_completeness"), "calls": out.get("calls"), "calls_ok": out.get("calls_ok"),
              "provider_error": out.get("provider_error"), "not_attempted": out.get("not_attempted"), "cost_from_calls_usd": out.get("cost_from_calls_usd"), "halted": out.get("halted"),
              "code_tag": ck["freeze"].get("tag")})
    if out.get("daily_quota"):
        return quota_pause(run_uuid, out["daily_quota"])
    if out.get("halted"):  # engine .12 (D2): a non-quota halt ends the pass's automatic continuation
        registry({"kind": "halted", "run_uuid": run_uuid, "reason": out["halted"], "source": "recovery"})
        return STOPPED
    return 0


def pending_pause() -> dict | None:
    """The latest quota pause that no later resume event closed."""
    last = None
    for e in registry_events():
        if e.get("kind") == "quota_pause":
            last = e
        elif e.get("kind") == "quota_resume":
            last = None
    return last


def resume(poll_s: int = 300, max_pauses: int = 10, sleep=None) -> int:
    """Unattended continuation of the one logical Judge Validation pass (approved 2026-11-02; Dev project key,
    existing 15 USD ceiling, the same frozen judge): after a pending quota pause has passed its resume time and only on AC
    power, first the eligible per-item recoveries of judged runs (provider_error retried once, never-sent items evaluated;
    completed items and exhausted ones, such as an item already recovered once, are never sent), then the runs not yet
    judged. An exhausted daily quota checkpoints and pauses again; any other stop ends the resume and is recorded as a
    resume_stop, which every later resume refuses before any request (engine .12, Codex delta review D2)."""
    import time as _time
    sleep = sleep or _time.sleep
    stop = terminal_stop()
    if stop:
        registry({"kind": "resume_refused", "stop_at": stop.get("at"), "reason": f"the pass stopped ({str(stop.get('reason'))[:200]}); continuing it is the human's decision"})
        return STOPPED
    pauses = 0
    registry({"kind": "resume_start"})
    while True:
        p = pending_pause()
        if p:
            wait = (dt.datetime.fromisoformat(p["resume_at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
            if wait > 0:
                sleep(wait); continue
            registry({"kind": "quota_resume", "paused_at": p["at"], "resume_at": p["resume_at"]})
        if not on_ac_power():
            if not any(e.get("kind") == "power_wait" for e in registry_events()[-3:]):
                registry({"kind": "power_wait", "reason": "on battery: an unattended paid batch starts only on AC power"})
            sleep(poll_s); continue
        try:
            rc = 0
            runs = {r["run_uuid"]: r for r in validation_runs()}
            for spec in json.load(open(PLAN, encoding="utf-8"))["order"]:
                r = runs.get(spec["run_uuid"])
                items = auto_recovery_items(r) if r and r["judge_items"] else []
                if items:
                    rc = recover(r["run_uuid"], items)
                    if rc:
                        break
            if rc == 0:
                rc = run()
        except SystemExit as ex:  # a gate or ledger refusal: recorded, never bypassed
            registry({"kind": "resume_stop", "reason": str(ex)[:300]}); return STOPPED
        if rc == PAUSED:
            pauses += 1
            if pauses > max_pauses:
                registry({"kind": "resume_stop", "reason": f"{pauses} quota pauses"}); return STOPPED
            continue
        if rc != 0:  # engine .12 (D2): a halted recovery or run, a recovery error or a ledger stop ends the pass's continuation
            last = next((e for e in reversed(registry_events()) if e.get("kind") in ("halted", "recovery_error", "budget_stop")), {})
            registry({"kind": "resume_stop", "reason": f"rc {rc}: {last.get('kind')} {str(last.get('reason') or last.get('error') or last.get('stops') or '')[:240]}"})
            return rc
        registry({"kind": "resume_end", "rc": rc})
        return rc


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
    ap.add_argument("command", choices=("plan", "check", "run", "status", "recover", "resume"))
    ap.add_argument("--env-file", default=os.path.join(ROOT, ".env"), help="resume: credential file loaded into this process (names only; existing variables win)")
    ap.add_argument("--run-uuid", default=None, help="recover: the interrupted Validation run")
    ap.add_argument("--items", default=None, help="recover: comma-separated judge items")
    a = ap.parse_args(argv)
    if a.command == "plan":
        p = write_plan()
        print(json.dumps({k: p[k] for k in ("judge_units", "ceiling_usd")} | {"order": [(x["task_id"][:8], x["judge_items"], x["reservation_usd"]) for x in p["order"]]}, indent=1))
    elif a.command == "check":
        print(json.dumps(check(), indent=1))
    elif a.command == "run":
        return run()
    elif a.command == "resume":
        from harness.launcher import load_env_file
        load_env_file(a.env_file)
        return resume()
    elif a.command == "recover":
        if not (a.run_uuid and a.items):
            raise SystemExit("recover needs --run-uuid and --items")
        return recover(a.run_uuid, sorted({int(x) for x in a.items.split(",") if x.strip()}))
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
