"""Judge Dev Pass 1 (approved by the human 2026-11-01): the shared judge on every judge-scored item of the eligible,
revealed Dev outputs, through the official grading entry (`grading.run_grading --judge`), so each run also gets a full
deterministic pass (with the LibreOffice recalculation). Judge costs go to the separate Judge Dev ledger
(~/turing-eval-runs/judge_dev/ledger.json, ceiling 30 USD); a per-call guard keeps Pass 1 within 20 USD and the
aggregate within 30 USD, counting every call at its worst case (input estimate plus the full output cap) before it is
sent. A guard also checks before every call that GOOGLE_API_KEY is the Dev project key (suffix) and that no override
variable is set; the Validation key is never used.

Self-consistency: 20 judge units drawn at random (recorded seed) from the eligible units' judge items, frozen in the pass
plan before any call; each runs once more with the identical stored unit (same request hash) after the primary units.

Output: cost and coverage only (no verdict). Verdicts stay in the sealed grading outputs until the human labels of the
runs concerned are saved. Usage:
  python -m grading.judge_dev plan    # write the pass plan (eligible runs, pending tasks, frozen repeat subset)
  python -m grading.judge_dev add-eligible  # append an addendum for Dev runs that became eligible after the plan
  python -m grading.judge_dev run     # execute the plan (paid; the plan must be committed first)
  python -m grading.judge_dev status  # cost and coverage so far
  python -m grading.judge_dev pass2   # execute the committed Pass 2 plan (paid; targeted calibration re-judge)

Pass 2 (calibration after the saved human Dev labels, within the Judge Dev aggregate ceiling and passes_max): the runs
listed in grading/judge_dev/pass2_plan.json are re-judged once through the official entry (--rejudge, a new unit and
reservation in the Judge Dev ledger) into dev/grading_v1/<run>/, so the V0 records and the Pass 1 verdicts stay as they
are; the plan states the reason and its own ceiling, checked before every call with the Pass 1 and aggregate guards."""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.expanduser("~/turing-eval-runs")
JDIR = os.path.join(BASE, "judge_dev")
LEDGER = os.path.join(JDIR, "ledger.json")
REGISTRY = os.path.join(JDIR, "registry.jsonl")
PLAN = os.path.join(ROOT, "grading", "judge_dev", "pass1_plan.json")
ADDENDA = os.path.join(ROOT, "grading", "judge_dev", "pass1_addenda")
PASS2_PLAN = os.path.join(ROOT, "grading", "judge_dev", "pass2_plan.json")  # runs that became eligible after the plan; never the repeat subset
PASS_ID = "judge-dev-pass-1"
DEV_KEY_SUFFIX = "KW5A"  # GOOGLE_API_KEY, the Dev project (docs/status.md, 2026-11-01)
SEED = 20261101
REPEATS = 20
AUTH_REF = "docs/status.md decision 2026-11-01: Judge Dev Pass 1 (model, settings, 20 / 30 USD ceilings, self-consistency)"


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def cfg():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def _find_judge_pricing(node):
    if isinstance(node, dict):
        if node.get("inspect_model_name") == cfg()["judge"]["model"] and "pricing_usd_per_mtok" in node:
            return node["pricing_usd_per_mtok"]
        for v in node.values():
            r = _find_judge_pricing(v)
            if r:
                return r
    return None


def prices():
    p = _find_judge_pricing(cfg())
    if p is None:
        raise SystemExit("no pricing block for the judge model in config.json")
    return {"std": {"input": Decimal(str(p["input"])), "output": Decimal(str(p["output"])), "cache_read": Decimal(str(p["cache_read"]))},
            "long": {"input": Decimal(str(p["long_context_above_200k_prompt_tokens"]["input"])), "output": Decimal(str(p["long_context_above_200k_prompt_tokens"]["output"])),
                     "cache_read": Decimal(str(p["long_context_above_200k_prompt_tokens"]["cache_read"]))}}


def worst_case_usd(request_chars: int, max_tokens: int, tier_name: str | None = None) -> Decimal:
    """Conservative cost of one call: input tokens estimated at chars / 3, the whole output cap (thinking included)."""
    tin = Decimal(request_chars) / 3
    tier = prices()[tier_name or ("long" if tin > 200_000 else "std")]
    return (tin * tier["input"] + Decimal(max_tokens) * tier["output"]) / Decimal(1_000_000)


def call_cost_usd(usage: dict, tier_name: str = "std") -> Decimal:
    """Provider cost of one call (every judge call is far below the 200 k-token tier: standard rates). The guard passes
    "long": the ledger settles a judge unit on its summed usage, whose tier can be the long-context one."""
    tier = prices()[tier_name]
    return (Decimal(usage.get("input_tokens", 0)) * tier["input"] + Decimal(usage.get("cache_read_tokens", 0)) * tier["cache_read"]
            + Decimal(usage.get("output_tokens", 0)) * tier["output"]) / Decimal(1_000_000)


def _max_retries_of(judge) -> int:
    mr = (getattr(judge, "generate_params", None) or {}).get("max_retries")
    return int(mr if mr is not None else cfg()["judge"]["max_retries"])


def batch_liability_usd(judge) -> Decimal:
    """What the ledger can settle for this judge batch so far (engine .10, Codex Review 2 R2-B4), in the settlement's
    terms (harness.budget.BudgetLedger.settle): every metered call, plus the inferred buffer of the batch's recoverable
    provider failures - the batch's average metered call times grading.judge.inferred_buffer_calls - priced at the
    long-context rates that bound the settlement. Without a metered call nothing can be inferred: the ledger then holds
    the unit at its reservation, which fit the ceiling when it was made."""
    from grading.judge import inferred_buffer_calls
    calls = [cl["usage"] for cl in (getattr(judge, "calls", None) or []) if cl.get("usage")]
    metered = sum((call_cost_usd(u, "long") for u in calls), Decimal(0))
    failures = list(getattr(judge, "recoverable_failures", None) or [])
    if not calls or not failures:
        return metered
    return metered + metered / len(calls) * inferred_buffer_calls(failures, _max_retries_of(judge))


def next_request_bound_usd(judge, request_chars: int, max_tokens: int) -> Decimal:
    """The next request's own increment as engine .10 bounded it: its estimated worst case if it completes, or, if it
    fails with a recoverable error, the buffer the ledger infers for it at the current average. It omits the repricing
    of the batch's earlier failures by a new metered call (Codex delta review D1); the guards use
    next_liability_bound_usd since engine .12."""
    nxt = worst_case_usd(request_chars, max_tokens, "long")
    calls = [cl["usage"] for cl in (getattr(judge, "calls", None) or []) if cl.get("usage")]
    if not calls:
        return nxt
    avg = sum((call_cost_usd(u, "long") for u in calls), Decimal(0)) / len(calls)
    return max(nxt, avg * (1 + _max_retries_of(judge)))


GUARD_CONTROL_TOKENS = 1024  # allowance for the chat template's control tokens around the system and user messages
LEDGER_CALL_ROUNDING = Decimal("0.000002")  # the ledger rounds each of a call's four category amounts half-up to 0.000001 USD
LEDGER_BUFFER_ROUNDING = Decimal("0.000001")  # and the inferred buffer once


def request_bound_usd(request_bytes: int, max_tokens: int) -> Decimal:
    """Engine .12 (Codex delta review D1): an upper bound of one judge call's cost, for the per-request guards. Prompt
    tokens are at most the request's UTF-8 bytes plus GUARD_CONTROL_TOKENS (Gemini's subword vocabulary falls back to
    single bytes, so no token spans less than one byte); output tokens, thinking included, at most max_tokens, which the
    provider enforces; every prompt token at the long-context input rate, which no rate the ledger applies to a prompt
    token exceeds (standard or long tier; uncached, cache read, or cache write at the input stand-in), and the output at
    the long-context output rate. worst_case_usd (chars / 3) stays the reservation estimate; it is not a bound."""
    tier = prices()["long"]
    return ((Decimal(request_bytes) + GUARD_CONTROL_TOKENS) * tier["input"] + Decimal(max_tokens) * tier["output"]) / Decimal(1_000_000)


def _bound_call_usd(usage: dict) -> Decimal:
    """A metered call at long-context rates (cache writes at the input rate) plus the ledger's rounding: never below
    what the ledger prices for it, whichever tier its prompt falls in."""
    tier = prices()["long"]
    return (Decimal(usage.get("input_tokens", 0)) * tier["input"] + Decimal(usage.get("cache_write_tokens", 0)) * tier["input"]
            + Decimal(usage.get("cache_read_tokens", 0)) * tier["cache_read"] + Decimal(usage.get("output_tokens", 0)) * tier["output"]) / Decimal(1_000_000) + LEDGER_CALL_ROUNDING


def next_liability_bound_usd(judge, request_chars: int, max_tokens: int, request_bytes: int | None = None) -> Decimal:
    """Engine .12 (Codex delta review D1): the most the ledger can settle for this judge batch once the next request
    has ended, whatever its outcome - what every per-request guard compares with its ceiling. The ledger settles a
    judge batch (harness.budget.BudgetLedger.settle) at S * (1 + K / n): S the n metered calls, K the inferred buffer
    calls of the batch's recoverable failures (grading.judge.inferred_buffer_calls) at the batch's AVERAGE metered call,
    so every later metered call reprices all earlier failures. With X the next request's bound (request_bound_usd;
    without request_bytes, 4 bytes per character, the UTF-8 maximum):
      - it completes: (S + X) * (1 + K / (n + 1));
      - it fails without usage: K grows by at most 1 + max_retries attempts (Inspect stops after max_retries retries) at
        the unchanged average, S * (1 + (K + 1 + max_retries) / n); with n = 0 nothing can be inferred and the ledger
        holds the unit at its reservation, which fit the ledger's ceiling when it was made.
    Both are increasing in S and X and every term is rounded up to the ledger's precision, so the bound is never below
    the settlement. With no failure (K = 0) it is S plus the larger of X and (1 + max_retries) average calls."""
    from grading.judge import inferred_buffer_calls
    calls = [cl["usage"] for cl in (getattr(judge, "calls", None) or []) if cl.get("usage")]
    s, n = sum((_bound_call_usd(u) for u in calls), Decimal(0)), len(calls)
    failures = list(getattr(judge, "recoverable_failures", None) or [])
    k = inferred_buffer_calls(failures, _max_retries_of(judge)) if failures else 0
    x = request_bound_usd(request_bytes if request_bytes is not None else 4 * request_chars, max_tokens) + LEDGER_CALL_ROUNDING
    completes = (s + x) * (1 + Decimal(k) / (n + 1))
    fails = s * (1 + Decimal(k + 1 + _max_retries_of(judge)) / n) if n else Decimal(0)
    return max(completes, fails) + LEDGER_BUFFER_ROUNDING


QUOTA_RESET_TZ = "America/Los_Angeles"  # Gemini API daily quotas reset at midnight Pacific time
QUOTA_RESUME_MARGIN_S = 300


def quota_resume_at(daily_quota: dict, now: dt.datetime | None = None) -> dt.datetime:
    """When a pass paused on an exhausted daily quota may send again (approved 2026-11-02): the later of the provider's
    retry guidance (RetryInfo, from the failed request) and the next midnight Pacific time, plus a 5-minute margin, so a
    resumed pass does not spend an item on a quota that has not reset yet."""
    from zoneinfo import ZoneInfo
    now = now or dt.datetime.now(dt.timezone.utc)
    at = dt.datetime.fromisoformat(daily_quota["at"]) if daily_quota.get("at") else now
    hint = at
    m = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(daily_quota.get("retry_delay") or ""))
    if m:
        hint = at + dt.timedelta(seconds=float(m.group(1)))
    local = at.astimezone(ZoneInfo(QUOTA_RESET_TZ))
    midnight = (local + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(dt.timezone.utc)
    return max(hint, midnight) + dt.timedelta(seconds=QUOTA_RESUME_MARGIN_S)


def on_ac_power() -> bool:
    """True when macOS reports AC power (pmset); an unattended paid batch starts only then (approved 2026-11-02)."""
    try:
        out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "AC Power" in out.splitlines()[0] if out else False


def registry(event: dict, pass_id: str = PASS_ID) -> None:
    os.makedirs(JDIR, exist_ok=True)
    with open(REGISTRY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": _now(), "pass": pass_id, **event}, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def registry_events() -> list[dict]:
    if not os.path.isfile(REGISTRY):
        return []
    return [json.loads(l) for l in open(REGISTRY, encoding="utf-8") if l.strip()]


def eligible_runs() -> tuple[list[dict], list[str]]:
    """Canonical dev runs of tasks listed ready in grading/readiness.json (Grader v0 tagged; reveal gate passed)."""
    from grading.grade import TASK_MODULES
    ready = json.load(open(os.path.join(ROOT, "grading", "readiness.json"), encoding="utf-8"))["ready"]
    runs_root = os.path.join(BASE, "dev", "runs")
    des = {}
    for l in open(os.path.join(runs_root, "canonical_designations.jsonl"), encoding="utf-8"):
        d = json.loads(l); des[d["run_uuid"]] = d
    inv = {}
    for l in open(os.path.join(runs_root, "run_inventory.jsonl"), encoding="utf-8"):
        r = json.loads(l)
        if r.get("run_uuid"):
            inv[r["run_uuid"]] = r
    out, pending = [], []
    for t in sorted(TASK_MODULES):
        canon = [u for u, d in des.items() if d["task_id"] == t and d["designation"] == "canonical"]
        if t not in ready or not canon:
            pending.append(t); continue
        u = canon[-1]; r = inv[u]
        mod = __import__(f"grading.checks_{t[:8]}", fromlist=["J_ITEMS"])
        out.append({"task_id": t, "run_uuid": u, "host_dir": os.path.join(runs_root, u), "eval_log": r["log_file"], "unit_id": r["unit_id"], "judge_items": list(mod.J_ITEMS),
                    "grading_out": os.path.join(BASE, "dev", "grading", u)})
    return out, pending


def ensure_ledger() -> dict:
    """The separate Judge Dev cost ledger (approved 2026-11-01), created once with the aggregate ceiling."""
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    if not os.path.isfile(LEDGER):
        os.makedirs(JDIR, exist_ok=True)
        BudgetLedger(LEDGER, Decimal(str(cfg()["judge"]["ceilings_usd"]["judge_dev_aggregate"])), prices_from_config(cfg()), label="judge_dev")
    return BudgetLedger.open_existing(LEDGER, prices_from_config(cfg())).identity()


def write_plan() -> dict:
    if os.path.exists(PLAN):
        raise SystemExit(f"{PLAN} exists; a pass plan is never overwritten")
    ensure_ledger()
    runs, pending = eligible_runs()
    frame = sorted((r["run_uuid"], i) for r in runs for i in r["judge_items"])
    subset = sorted(random.Random(SEED).sample(frame, min(REPEATS, len(frame))))
    c = cfg()["judge"]
    plan = {"pass": PASS_ID, "created_at": _now(), "model": c["model"], "settings": {k: c[k] for k in ("temperature", "max_tokens", "max_retries", "reasoning_effort")},
            "prompt_sha256": c["prompt_sha256"], "ceilings_usd": c["ceilings_usd"], "authorization_ref": AUTH_REF,
            "eligible_runs": [{k: r[k] for k in ("task_id", "run_uuid")} | {"judge_items": len(r["judge_items"])} for r in runs], "pending_tasks": pending,
            "eligible_judge_units": len(frame),
            "inventory_note": "84 was the earlier plan-scope estimate (the five full-calibration tasks plus one smoke item each); full coverage is every judge item of every dev output, 168 units over ten tasks",
            "self_consistency": {"seed": SEED, "n": len(subset), "frame": "(run_uuid, judge item) pairs of the eligible runs, sorted; random.Random(seed).sample", "units": subset,
                                 "frozen_before_any_call": True}}
    os.makedirs(os.path.dirname(PLAN), exist_ok=True)
    with open(PLAN, "x", encoding="utf-8") as f:
        json.dump(plan, f, indent=1)
    return plan


def addenda() -> list[dict]:
    return [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(ADDENDA, "addendum_*.json")))]


def planned_runs(plan: dict) -> set[str]:
    return {r["run_uuid"] for r in plan["eligible_runs"]} | {r["run_uuid"] for a in addenda() for r in a["eligible_runs"]}


def add_eligible() -> dict | None:
    """Primary units of Dev runs that became eligible after the plan (their outputs completed later). Written once per
    run, before any call on it; the self-consistency subset stays the one frozen in the plan."""
    plan = json.load(open(PLAN, encoding="utf-8"))
    known = planned_runs(plan)
    runs, pending = eligible_runs()
    new = [r for r in runs if r["run_uuid"] not in known]
    if not new:
        return None
    os.makedirs(ADDENDA, exist_ok=True)
    n = len(addenda()) + 1
    add = {"pass": PASS_ID, "addendum": n, "created_at": _now(), "plan_sha256": hashlib.sha256(open(PLAN, "rb").read()).hexdigest(),
           "eligible_runs": [{k: r[k] for k in ("task_id", "run_uuid")} | {"judge_items": len(r["judge_items"])} for r in new], "pending_tasks": pending,
           "added_judge_units": sum(len(r["judge_items"]) for r in new),
           "self_consistency": "unchanged: the subset frozen in pass1_plan.json; added runs get primary units only"}
    with open(os.path.join(ADDENDA, f"addendum_{n:02d}.json"), "x", encoding="utf-8") as f:
        json.dump(add, f, indent=1)
    return add


def spent() -> dict:
    """Pass 1 and aggregate Judge Dev spend from the Judge Dev ledger (settled cost of every judge unit recorded there)."""
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    L = BudgetLedger.open_existing(LEDGER, prices_from_config(cfg()))
    snap = L.snapshot()
    pass_units = {e["unit_id"] for e in registry_events() if e.get("unit_id")}
    p1 = Decimal(0)
    for uid in pass_units:
        eff = L.effective_settlement(uid)
        if eff["effective"]:
            p1 += Decimal(eff["effective"]["cost_usd"])
        elif eff["open"]:
            p1 += Decimal(next((e["estimated_usd"] for e in eff["events"] if e["type"] == "reservation"), "0"))
    return {"pass_1": p1, "aggregate": Decimal(snap["settled_usd"]) + Decimal(snap["reserved_usd"]), "snapshot": snap}


def pass_spent(pass_id: str) -> Decimal:
    """Settled (or reserved, while open) cost of the judge units registered under one pass."""
    from harness.budget import BudgetLedger
    from harness.launcher import prices_from_config
    L = BudgetLedger.open_existing(LEDGER, prices_from_config(cfg()))
    total = Decimal(0)
    for uid in {e["unit_id"] for e in registry_events() if e.get("unit_id") and e.get("pass") == pass_id}:
        eff = L.effective_settlement(uid)
        if eff["effective"]:
            total += Decimal(eff["effective"]["cost_usd"])
        elif eff["open"]:
            total += Decimal(next((e["estimated_usd"] for e in eff["events"] if e["type"] == "reservation"), "0"))
    return total


def make_guard(judge_holder: dict, max_tokens: int, base: dict, extra_cap: tuple | None = None):
    c = cfg()["judge"]
    cap1, capall = Decimal(str(c["ceilings_usd"]["pass_1"])), Decimal(str(c["ceilings_usd"]["judge_dev_aggregate"]))

    def guard(request_chars: int, request_bytes: int | None = None):
        key = os.environ.get("GOOGLE_API_KEY") or ""
        if not key.endswith(DEV_KEY_SUFFIX):
            return "GOOGLE_API_KEY is not the Dev project key"
        if any(os.environ.get(k) for k in ("GEMINI_API_KEY", "VERTEX_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI")):
            return "a Google credential override variable is set"
        j = judge_holder.get("judge")
        # Long-context rates bound what the ledger can settle for this unit (it prices the unit's summed usage, which may
        # cross the 200 k tier), so the ledger total stays within both ceilings, not only the provider bill.
        # Engine .10 (R2-B4): the batch's liability includes the inferred buffer of its recoverable failures; engine .12
        # (D1): the bound is the whole settlement after the next request, the repricing of earlier failures included.
        so_far = batch_liability_usd(j)
        after = next_liability_bound_usd(j, request_chars, max_tokens, request_bytes)
        if base["pass_1"] + after > cap1:
            return f"Pass 1 ceiling {cap1} USD would be exceeded (spent {base['pass_1'] + so_far:.4f}; at most {base['pass_1'] + after:.4f} after the next request)"
        if base["aggregate"] + after > capall:
            return f"Judge Dev aggregate ceiling {capall} USD would be exceeded"
        if extra_cap is not None and extra_cap[1] + after > extra_cap[2]:
            return f"{extra_cap[0]} ceiling {extra_cap[2]} USD would be exceeded (spent {extra_cap[1] + so_far:.4f}; at most {extra_cap[1] + after:.4f} after the next request)"
        return None
    return guard


def judge_run(r: dict, log, force_rejudge: bool = False, extra_cap: tuple | None = None) -> dict:
    """One eligible run: official grading with the judge (recalculation on), judge costs in the Judge Dev ledger."""
    from grading import run_grading as RG
    from grading.judge import ProviderJudge
    c = cfg()["judge"]
    est_units = len(r["judge_items"]) + 2
    est = (worst_case_usd(40_000 * 3, c["max_tokens"]) * est_units).quantize(Decimal("0.01"))
    base = spent()
    holder = {}

    def factory(model, cfgd):
        j = ProviderJudge(model, temperature=c["temperature"], max_tokens=c["max_tokens"], max_retries=c["max_retries"], reasoning_effort=c["reasoning_effort"],
                          cost_guard=make_guard(holder, c["max_tokens"], base, extra_cap))
        holder["judge"] = j
        return j
    os.makedirs(r["grading_out"], exist_ok=True)
    argv = ["--host-dir", r["host_dir"], "--eval-log", r["eval_log"], "--task-id", r["task_id"], "--out-dir", r["grading_out"], "--ledger", os.path.join(BASE, "dev", "ledger.json"),
            "--unit-id", r["unit_id"], "--judge", "--judge-model", c["model"], "--judge-estimate-usd", str(est), "--confirm-judge", f"{r['run_uuid']}|{c['model']}|{est}",
            "--authorized-by", "Yuning Zhang (approved in chat 2026-11-01)", "--authorization-ref", AUTH_REF, "--env-file", os.path.join(ROOT, ".env"), "--judge-ledger", LEDGER]
    prior = [p.get("grading_pass") for p in RG.grading_passes(r["grading_out"], r["run_uuid"]) if p.get("judge_mode") == "real"]
    if prior or force_rejudge:
        argv.append("--rejudge")
    import contextlib
    with contextlib.redirect_stdout(log):
        rc = RG.main(argv, judge_factory=factory)
    j = holder.get("judge")
    calls = getattr(j, "calls", []) or []
    rec = RG.grading_passes(r["grading_out"], r["run_uuid"])[-1]
    return {"rc": rc, "judge_unit": rec.get("judge_unit"), "grading_pass": rec.get("grading_pass"), "graded": rec.get("graded"), "gate": rec.get("gate"),
            "calls": len(calls), "calls_ok": sum(1 for x in calls if x.get("status") == "ok"), "not_attempted": sum(1 for x in calls if x.get("status") == "not_attempted"),
            "provider_error": sum(1 for x in calls if x.get("status") == "provider_error"), "halted": getattr(j, "halted", None),
            "cost_from_calls_usd": str(sum((call_cost_usd(x["usage"]) for x in calls if x.get("usage")), Decimal(0)).quantize(Decimal("0.000001"))),
            "deterministic_items": sum(1 for l in open(os.path.join(r["grading_out"], "grades.jsonl"), encoding="utf-8") if l.strip() and json.loads(l).get("grading_pass") == rec.get("grading_pass")
                                       and json.loads(l).get("source") == "D") if rec.get("graded") else None}


def resources_ok() -> tuple[bool, dict]:
    lvl = int(subprocess.run(["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], capture_output=True, text=True).stdout.strip() or 0)
    free = subprocess.run(["memory_pressure", "-Q"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
    pct = int(free.split(":")[-1].strip().rstrip("%"))
    return (lvl <= 2 and pct >= 20), {"pressure_level": lvl, "free_pct": pct}


def run_repeats(plan: dict, log) -> dict:
    """The frozen self-consistency subset: each stored unit of the primary pass once more (identical request)."""
    from harness.budget import BudgetLedger
    from harness.launcher import PilotLauncher, prices_from_config
    from grading.judge import ProviderJudge, judge_units
    c = cfg()["judge"]
    wanted = {(u, i) for u, i in plan["self_consistency"]["units"]}
    done = {(e["run_uuid"], e["item"]) for e in registry_events() if e.get("kind") == "repeat_result"}
    results = []
    by_run = {}
    for u, i in sorted(wanted - done):
        by_run.setdefault(u, []).append(i)
    for u, items in by_run.items():
        files = sorted(glob.glob(os.path.join(BASE, "dev", "grading", u, f"judge_units_{u}_*.json")))
        if not files:
            registry({"kind": "repeat_skipped", "run_uuid": u, "reason": "no stored primary units"}); continue
        stored = json.load(open(files[-1], encoding="utf-8"))
        units = [x for x in stored["units"] if x["item"] in items]
        base = spent()
        holder = {}
        j = ProviderJudge(c["model"], temperature=c["temperature"], max_tokens=c["max_tokens"], max_retries=c["max_retries"], reasoning_effort=c["reasoning_effort"],
                          cost_guard=make_guard(holder, c["max_tokens"], base))
        holder["judge"] = j
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        unit_id = f"{u}:judge-repeat:{stamp}"
        j.log_path = os.path.join(JDIR, "repeat_logs", u, f"{unit_id.replace(':', '_')}.jsonl")
        j.run_uuid, j.judge_unit = u, unit_id
        ledger = BudgetLedger.open_existing(LEDGER, prices_from_config(cfg()))
        launcher = PilotLauncher(cfg(), runs_root=JDIR, ledger=ledger, eval_fn=None)
        est = (worst_case_usd(40_000 * 3, c["max_tokens"]) * len(units)).quantize(Decimal("0.01"))
        registry({"kind": "repeat_batch_start", "run_uuid": u, "unit_id": unit_id, "items": items, "estimate_usd": str(est), "primary_units_file": files[-1]})
        state = {}

        def batch_fn():
            state["verdicts"] = judge_units(units, j)
            return j.batch_result()
        launcher.run_judge_batch(unit_id=unit_id, estimate_usd=est, batch_fn=batch_fn)
        primary = {}
        for cf in sorted(glob.glob(os.path.join(BASE, "dev", "grading", u, f"judge_calls_{u}_*.json"))):
            for cl in json.load(open(cf, encoding="utf-8"))["calls"]:
                primary[cl["item"]] = cl
        sealed = os.path.join(JDIR, "repeats", f"{unit_id.replace(':', '_')}.json")
        os.makedirs(os.path.dirname(sealed), exist_ok=True)
        with open(sealed, "x", encoding="utf-8") as f:
            json.dump({"run_uuid": u, "unit_id": unit_id, "calls": j.calls, "verdicts": state.get("verdicts")}, f, indent=1, default=str)
        for cl in j.calls:
            same = primary.get(cl["item"], {}).get("request_sha256") == cl["request_sha256"]
            registry({"kind": "repeat_result", "run_uuid": u, "item": cl["item"], "unit_id": unit_id, "status": cl["status"], "same_request_as_primary": same,
                      "cost_usd": str(call_cost_usd(cl["usage"])) if cl.get("usage") else None, "sealed_file": sealed})
            results.append((u, cl["item"], cl["status"], same))
    return {"repeats_run": len(results), "identical_requests": sum(1 for r in results if r[3])}


def run() -> int:
    plan = json.load(open(PLAN, encoding="utf-8"))
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", PLAN, ADDENDA], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        raise SystemExit("the pass plan and its addenda must be committed before any paid call")
    os.environ.pop("GOOGLE_API_KEY_VALIDATION", None)
    log = open(os.path.join(JDIR, f"pass1_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "pass_start", "plan_sha256": hashlib.sha256(open(PLAN, "rb").read()).hexdigest(), "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    runs, _ = eligible_runs()
    planned = planned_runs(plan)
    done = {e["run_uuid"] for e in registry_events() if e.get("kind") == "run_done"}
    for r in runs:
        if r["run_uuid"] not in planned or r["run_uuid"] in done:
            continue
        ok, res = resources_ok()
        if not ok:
            registry({"kind": "deferred", "run_uuid": r["run_uuid"], "resources": res}); continue
        s = spent()
        if s["pass_1"] >= Decimal(str(cfg()["judge"]["ceilings_usd"]["pass_1"])):
            registry({"kind": "budget_stop", "spent": str(s["pass_1"])}); break
        registry({"kind": "run_start", "run_uuid": r["run_uuid"], "task_id": r["task_id"], "judge_items": len(r["judge_items"]), "resources": res})
        try:
            out = judge_run(r, log)
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": r["run_uuid"], "error": f"{type(ex).__name__}: {str(ex)[:300]}"}); continue
        registry({"kind": "run_done", "run_uuid": r["run_uuid"], "task_id": r["task_id"], "unit_id": out["judge_unit"], **{k: v for k, v in out.items() if k != "judge_unit"}})
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": r["run_uuid"], "reason": out["halted"]}); break
    rep = run_repeats(plan, log)
    registry({"kind": "pass_end", "repeats": rep, "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}})
    return 0


def run_pass2() -> int:
    """Execute the committed Pass 2 plan once per listed run (never automatically repeated)."""
    plan = json.load(open(PASS2_PLAN, encoding="utf-8"))
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=all", "--", PASS2_PLAN], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        raise SystemExit("the Pass 2 plan must be committed before any paid call")
    if len({e.get("pass") for e in registry_events()} - {PASS_ID}) > int(cfg()["judge"]["ceilings_usd"]["passes_max"]) - 1:
        raise SystemExit("passes_max reached")
    os.environ.pop("GOOGLE_API_KEY_VALIDATION", None)
    pid, cap = plan["pass"], Decimal(str(plan["ceiling_usd"]))
    log = open(os.path.join(JDIR, f"{pid}_{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log"), "a", encoding="utf-8")
    registry({"kind": "pass_start", "plan_sha256": hashlib.sha256(open(PASS2_PLAN, "rb").read()).hexdigest(), "reason": plan["reason"]}, pid)
    runs = {r["run_uuid"]: r for r in eligible_runs()[0]}
    done = {e["run_uuid"] for e in registry_events() if e.get("kind") == "run_done" and e.get("pass") == pid}
    for spec in plan["runs"]:
        u = spec["run_uuid"]
        if u in done or u not in runs:
            registry({"kind": "skipped", "run_uuid": u, "reason": "done" if u in done else "not eligible"}, pid); continue
        r = {**runs[u], "grading_out": os.path.join(BASE, "dev", "grading_v1", u)}
        if sorted(r["judge_items"]) != sorted(spec["items"]):
            registry({"kind": "skipped", "run_uuid": u, "reason": f"judge items {r['judge_items']} differ from the plan {spec['items']}"}, pid); continue
        registry({"kind": "run_start", "run_uuid": u, "task_id": r["task_id"], "judge_items": len(r["judge_items"])}, pid)
        try:
            out = judge_run(r, log, force_rejudge=True, extra_cap=(pid, pass_spent(pid), cap))
        except Exception as ex:  # recorded, never retried automatically
            registry({"kind": "run_error", "run_uuid": u, "error": f"{type(ex).__name__}: {str(ex)[:300]}"}, pid); continue
        registry({"kind": "run_done", "run_uuid": u, "task_id": r["task_id"], "unit_id": out["judge_unit"], **{k: v for k, v in out.items() if k != "judge_unit"}}, pid)
        if out.get("halted"):
            registry({"kind": "halted", "run_uuid": u, "reason": out["halted"]}, pid); break
    registry({"kind": "pass_end", "spent_pass_usd": str(pass_spent(pid)), "spent": {k: str(v) for k, v in spent().items() if k != "snapshot"}}, pid)
    return 0


def status() -> dict:
    ev = registry_events()
    s = spent()
    done = [e for e in ev if e.get("kind") == "run_done"]
    reps = [e for e in ev if e.get("kind") == "repeat_result"]
    return {"spent_pass_1_usd": str(s["pass_1"]), "judge_dev_ledger": {k: s["snapshot"].get(k) for k in ("settled_usd", "reserved_usd", "remaining_usd", "review_pending_units", "stops")},
            "runs_done": [{k: e.get(k) for k in ("task_id", "calls", "calls_ok", "not_attempted", "provider_error", "cost_from_calls_usd", "graded", "deterministic_items", "halted")} for e in done],
            "repeats_done": len(reps), "repeats_identical_request": sum(1 for e in reps if e.get("same_request_as_primary")),
            "events": {k: sum(1 for e in ev if e.get("kind") == k) for k in sorted({e.get("kind") for e in ev})}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Judge Dev Pass 1 and the targeted Pass 2")
    ap.add_argument("command", choices=("plan", "add-eligible", "run", "status", "pass2"))
    a = ap.parse_args(argv)
    if a.command == "plan":
        p = write_plan()
        print(json.dumps({k: p[k] for k in ("eligible_runs", "pending_tasks", "eligible_judge_units")} | {"self_consistency_n": p["self_consistency"]["n"]}, indent=1))
    elif a.command == "add-eligible":
        add = add_eligible()
        print(json.dumps({k: add[k] for k in ("addendum", "eligible_runs", "pending_tasks", "added_judge_units")} if add else {"added": 0}, indent=1))
    elif a.command == "run":
        return run()
    elif a.command == "pass2":
        return run_pass2()
    else:
        print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
