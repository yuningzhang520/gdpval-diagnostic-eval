"""Offline deterministic grading of ONE saved run (Pilot A wiring U2). Host-side only: the rubric,
the independent reference and the task prompt are read from the host paths (`private/`, `data/`)
that are never mounted into a model sandbox. The run is identified by its host directory
(runs_root/<TaskState uuid>) and its completed Inspect log: run.json, the log's sample and the
requested task id must agree before anything is graded. The judge is not called here (judge=None):
the judge-only criteria stay ``pending_judge`` and are excluded from the graded denominator E;
with --judge (U3) the judge-only criteria are judged by the real judge through the same grade_run,
as a second grading pass (results/grades are appended with a pass identity; the deterministic-only
pass is never overwritten), gated by judge_gate and reserved/settled through the launcher ledger.
Writes grades.jsonl / results.jsonl (through grade_run), the human-review materials (judge verdicts
sealed in their own file), the judge call log, and a provenance record linking the run, the code,
the config, the eval log, the selected pass and the ledger settlements.
Usage: python -m grading.run_grading --host-dir <runs_root/uuid> --eval-log <path.eval> --task-id <uuid> --out-dir <dir>
       [--config config.json] [--ledger <ledger.json> --unit-id <unit>] [--no-recalc]"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from decimal import Decimal

from inspect_ai.log import read_eval_log

from harness.budget import BudgetExhausted, BudgetLedger, LedgerConflict
from harness.launcher import KEY_ENV_BY_PROVIDER, LauncherError, PilotLauncher, config_sha256, git_provenance, load_env_file, missing_keys, prices_from_config, refuse_disabled_model_api
from grading.costs import grading_cost, run_cost_record
from grading.grade import ENGINE_VERSION, GRADER_VERSION, TASK_MODULES, grade_run, grader_version_of, grading_passes, judge_completeness, select_pass, selected_grades
from grading.judge import ProviderJudge, scan_judge_log, usage_from_judge_log

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class GradingCliError(RuntimeError):
    pass


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_materials(task_id: str, config_path: str) -> dict:
    """Rubric, independent reference and task prompt for the task, from host paths only; the prompt
    file must hash to the value recorded in the config."""
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)
    entry = next((t for t in cfg["tasks"] if t["task_id"] == task_id), None)
    if entry is None:
        raise GradingCliError(f"task {task_id} is not in config.tasks")
    g = cfg.get("grading") or {}
    if task_id not in TASK_MODULES:
        raise GradingCliError(f"no grader registered for task {task_id}; refusing to grade")
    declared_engine, declared_task = g.get("engine_version"), (g.get("task_grader_versions") or {}).get(task_id)
    if declared_engine != ENGINE_VERSION or declared_task != TASK_MODULES[task_id]["version"]:  # version consistency: the config states both versions explicitly and they must be the code's
        raise GradingCliError(f"config.grading versions (engine {declared_engine!r}, task {declared_task!r}) differ from the grader code "
                              f"(engine {ENGINE_VERSION!r}, task {TASK_MODULES[task_id]['version']!r}; combined grader_version {grader_version_of(task_id)!r}); refusing to grade")
    rubric_path = os.path.join(ROOT, "private", "rubric", f"{task_id}.json")
    reference_path = os.path.join(ROOT, "private", "checks", "recalc", f"{task_id}.json")
    prompt_path = os.path.join(ROOT, entry["prompt_file"])
    for p in (rubric_path, reference_path, prompt_path):
        if not os.path.isfile(p):
            raise GradingCliError(f"required host material missing: {os.path.relpath(p, ROOT)}")
    prompt_sha = _sha256(prompt_path)
    if prompt_sha != entry["prompt_sha256"]:
        raise GradingCliError(f"task prompt file {entry['prompt_file']} does not match config.tasks prompt_sha256; refusing to grade")
    with open(rubric_path, encoding="utf-8") as f:
        rubric = json.load(f)
    with open(reference_path, encoding="utf-8") as f:
        reference = json.load(f)
    with open(prompt_path, encoding="utf-8") as f:
        prompt = f.read()
    return {"rubric": rubric, "reference": reference, "task_prompt": prompt, "paths": {"rubric": os.path.relpath(rubric_path, ROOT), "reference": os.path.relpath(reference_path, ROOT), "prompt": entry["prompt_file"]},
            "hashes": {"rubric": _sha256(rubric_path), "reference": _sha256(reference_path), "prompt": prompt_sha}, "config_sha256": config_sha256(config_path)}


def resolve_run(host_dir: str, eval_log_path: str, task_id: str):
    """The saved run and the completed log must name the same execution: run.json's binding, the
    directory name (TaskState uuid), the log's sample uuid, the sample id (= task id) and the eval id."""
    host_dir = os.path.realpath(host_dir)
    run_json = os.path.join(host_dir, "run.json")
    if not os.path.isfile(run_json):
        raise GradingCliError(f"{host_dir} has no run.json: not a saved run directory")
    with open(run_json, encoding="utf-8") as f:
        binding = json.load(f)["run"]
    uuid = os.path.basename(host_dir)
    if binding.get("uuid") != uuid:
        raise GradingCliError(f"run.json uuid {binding.get('uuid')!r} differs from the directory name {uuid!r}")
    if binding.get("sample_id") != task_id:
        raise GradingCliError(f"run.json sample_id {binding.get('sample_id')!r} is not the requested task {task_id!r}")
    log = read_eval_log(eval_log_path)
    sample = next((s for s in (log.samples or []) if s.uuid == uuid), None)
    if sample is None:
        raise GradingCliError(f"eval log {eval_log_path} has no sample with uuid {uuid!r}")
    mismatches = [k for k, a, b in (("sample_id", sample.id, task_id), ("eval_id", log.eval.eval_id, binding.get("eval_id")), ("model", log.eval.model, binding.get("model")),
                                      ("task_id", log.eval.task_id, binding.get("task_id")), ("epoch", sample.epoch, binding.get("epoch"))) if a != b]
    if mismatches:
        raise GradingCliError(f"eval log and run.json disagree on {mismatches}; refusing to grade")
    return host_dir, log, sample, binding


def load_ledger_binding(host_dir: str) -> dict:
    """The run's persisted ledger binding (written by the launcher after the sample ran). Required for any paid
    judge pass: without it nothing is guessed and no new binding is created silently."""
    path = os.path.join(host_dir, "ledger_binding.json")
    if not os.path.isfile(path):
        raise GradingCliError(f"{host_dir} has no ledger_binding.json: this run's ledger identity is not recorded; manual handling required (no second cost history is created)")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def judge_log_path(ledger_path: str, run_uuid: str, judge_unit: str) -> str:
    """Write-ahead judge call logs live next to the ledger (not in the grading out_dir), so a changed out_dir cannot hide them."""
    safe = judge_unit.replace("/", "_").replace(":", "_")
    return os.path.join(os.path.dirname(os.path.realpath(ledger_path)), "judge_logs", run_uuid, f"{safe}.jsonl")


USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens")


def durable_usage(log_path: str, judge) -> dict:
    """The usage a failed judge batch is settled on (correction B): the write-ahead log's finished attempts, each once,
    cross-checked against the adapter's in-memory usage. Engine .10 (Codex Review 2 R2-B1): when the two disagree the
    element-wise larger figure per model is settled and the disagreement is named in the source - never silently the
    smaller known value. That settlement path is always estimated and held (BudgetLedger.settle, incomplete)."""
    durable = usage_from_judge_log(log_path)
    memory = getattr(judge, "usage_by_model", None) or {}
    agrees = memory == durable["usage"]
    durable["memory_cross_check"] = {"usage": memory, "agrees": agrees}
    if not agrees:
        merged = {m: {k: max(int((durable["usage"].get(m) or {}).get(k, 0) or 0), int((memory.get(m) or {}).get(k, 0) or 0)) for k in USAGE_KEYS}
                  for m in sorted(set(durable["usage"]) | set(memory))}
        durable["durable_usage"] = durable["usage"]
        durable["usage"] = merged
        durable["source"] += "; durable and in-memory usage disagree: settled at the element-wise larger figure (estimated, held for reconciliation)"
    return durable


def run_judge_history(ledger: BudgetLedger, binding: dict) -> dict:
    """Paid judge history of one run from the canonical ledger and its write-ahead logs: judge units, open / held /
    unresolvable units, UNKNOWN calls (started without terminal event)."""
    units = ledger.units_for_run(binding["run_uuid"], binding.get("generation_unit_id"))
    log_dir = os.path.join(os.path.dirname(ledger.path), "judge_logs", binding["run_uuid"])
    logs = {}
    if os.path.isdir(log_dir):
        for name in sorted(os.listdir(log_dir)):
            if name.endswith(".jsonl"):
                logs[name] = scan_judge_log(os.path.join(log_dir, name))
    unknown = {name: sc["unknown"] for name, sc in logs.items() if sc["unknown"]}
    return {"units": units, "logs": {k: {"events": v["events"], "unknown": v["unknown"], "states": {u: c["state"] for u, c in v["calls"].items()}} for k, v in logs.items()}, "unknown_calls": unknown}


JUDGE_LEDGER_BINDING = "judge_ledger_binding.json"


def judge_ledger_bindings(host_dir: str) -> list[dict]:
    """Separate judge ledgers declared for a run (approved 2026-11-01: a Judge Dev cost ledger apart from the run's
    generation ledger, whose claim rule refuses while a generation unit holds an open reservation). Append-only list."""
    path = os.path.join(host_dir, JUDGE_LEDGER_BINDING)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def declare_judge_ledger(host_dir: str, run_uuid: str, ledger: BudgetLedger, reason: str) -> dict:
    entries = judge_ledger_bindings(host_dir)
    ident = ledger.identity()
    if not any(e["ledger_path"] == ledger.path and e["ledger_id"] == ident.get("ledger_id") for e in entries):
        entries.append({"run_uuid": run_uuid, "ledger_path": ledger.path, "ledger_id": ident.get("ledger_id"), "label": ident.get("label"), "declared_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                        "reason": reason})
        tmp = os.path.join(host_dir, JUDGE_LEDGER_BINDING + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=1)
        os.replace(tmp, os.path.join(host_dir, JUDGE_LEDGER_BINDING))
    return entries


def combined_judge_history(ledger: BudgetLedger, binding: dict, host_dir: str, prices: dict) -> dict:
    """The run's judge history from its bound ledger plus every declared judge ledger (fail closed: a declared ledger
    that is missing or whose id differs raises)."""
    hist = run_judge_history(ledger, binding)
    for e in judge_ledger_bindings(host_dir):
        if not os.path.isfile(e["ledger_path"]):
            raise GradingCliError(f"declared judge ledger {e['ledger_path']} is missing; the run's judge history cannot be verified")
        jl = BudgetLedger.open_existing(e["ledger_path"], prices)
        if jl.identity().get("ledger_id") != e["ledger_id"]:
            raise GradingCliError(f"declared judge ledger {e['ledger_path']} has another ledger id than declared; refusing")
        h = run_judge_history(jl, binding)
        hist["units"]["units"].update(h["units"]["units"])
        for k in ("judge_units", "open", "review_pending", "unresolvable"):
            hist["units"][k] = sorted(set(hist["units"][k]) | set(h["units"][k]))
        hist["logs"].update({f"{e['label'] or 'judge'}/{n}": v for n, v in h["logs"].items()})
        hist["unknown_calls"].update(h["unknown_calls"])
        hist.setdefault("judge_ledgers", []).append({k: e[k] for k in ("ledger_path", "ledger_id", "label")})
    return hist


def report_selection(cfg: dict, host_dir: str, out_dir: str, run_uuid: str, ledger: BudgetLedger | None = None) -> dict:
    """The attempt-aware selection a report must use. FAIL-CLOSED: the run's ledger binding (host_dir/ledger_binding.json)
    is resolved here, the bound ledger is opened and its judge attempts and write-ahead logs are read; a missing binding,
    a missing bound ledger, or a caller-supplied ledger that is not the bound one all return ``blocked`` with the reason -
    the history is never skipped because an argument was omitted. Returns select_pass's dict with the pass id, the
    attempts and the binding used."""
    passes = grading_passes(out_dir, run_uuid)
    binding_path = os.path.join(host_dir, "ledger_binding.json")
    if not os.path.isfile(binding_path):
        return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": None,
                "basis": f"no ledger_binding.json for run {run_uuid}: the judge attempt history cannot be verified; selection fails closed", "warnings": ["reconcile the run's ledger binding manually"]}
    with open(binding_path, encoding="utf-8") as f:
        binding = json.load(f)
    if binding.get("run_uuid") != run_uuid:
        return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": binding,
                "basis": f"ledger_binding.json names run {binding.get('run_uuid')!r}, not {run_uuid!r}; selection fails closed", "warnings": []}
    if ledger is not None and ledger.path != binding.get("ledger_path"):
        return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": binding,
                "basis": f"the supplied ledger {ledger.path} is not the run's bound ledger {binding.get('ledger_path')}; selection fails closed", "warnings": []}
    if ledger is None:
        if not os.path.isfile(binding.get("ledger_path") or ""):
            return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": binding,
                    "basis": f"the run's bound ledger {binding.get('ledger_path')} is not readable; selection fails closed", "warnings": []}
        ledger = BudgetLedger.open_existing(binding["ledger_path"], prices_from_config(cfg))
    if ledger.snapshot().get("ledger_id") != binding.get("ledger_id"):
        return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": binding,
                "basis": "the bound ledger's id differs from ledger_binding.json; selection fails closed", "warnings": []}
    try:
        attempts = judge_attempts(combined_judge_history(ledger, binding, host_dir, prices_from_config(cfg)), passes)
    except GradingCliError as ex:
        return {"pass": None, "blocked": True, "authoritative": False, "history": select_pass(passes)["history"], "attempts": None, "binding": binding, "basis": str(ex), "warnings": []}
    sel = select_pass(passes, attempts=attempts)
    return {**sel, "pass": sel["pass"].get("grading_pass") if sel.get("pass") else None, "attempts": attempts, "binding": {k: binding.get(k) for k in ("run_uuid", "ledger_path", "ledger_id")}}


def authoritative_selection(cfg: dict, host_dir: str, out_dir: str, run_uuid: str) -> dict:
    """The statistics entry: attempt-aware selection plus the selected pass's grade rows (none while blocked)."""
    sel = report_selection(cfg, host_dir, out_dir, run_uuid)
    rows = selected_grades(out_dir, run_uuid, attempts=sel["attempts"])["grades"] if sel.get("attempts") is not None and not sel.get("blocked") else []
    return {**sel, "grades": rows}


def settlement_for(ledger: BudgetLedger, unit_id: str) -> dict | None:
    """The unit's EFFECTIVE settlement from the ledger's derived state (manual resolutions applied; a resolved open
    reservation counts as settled at the verified amount), with the raw events and the resolution kept for provenance.
    Never the first raw settlement event."""
    eff = ledger.effective_settlement(unit_id)
    if eff["effective"] is None:
        return None
    return {**eff["effective"], "resolution": eff["resolution"], "raw_events": [e["type"] for e in eff["events"]], "source": "ledger derived state (effective_settlement)"}


def judge_attempts(history: dict, passes: list[dict]) -> list[dict]:
    """Every persisted judge attempt of a run, joined to the grading passes it produced: state settled / held / open /
    unknown (write-ahead started event without a terminal event) and whether a results record exists for it."""
    with_pass = {p.get("judge_unit") for p in passes if p.get("judge_unit")}
    unknown_units = {name[:-len(".jsonl")] for name, calls in history.get("unknown_calls", {}).items()}
    out = []
    for uid, u in history["units"]["units"].items():
        if ":judge:" not in uid:
            continue
        safe = uid.replace("/", "_").replace(":", "_")
        state = "unknown" if (safe in unknown_units and u.get("resolution") != "settled_amount") else "open" if u["open"] else "held" if u["review_pending"] else "settled" if u["settled"] else "voided" if u["voided"] else "unknown"
        at = next((e.get("at") for e in u["events"] if e.get("type") == "reservation"), None) or ""
        out.append({"unit_id": uid, "state": state, "at": at, "has_pass": uid in with_pass, "resolution": u.get("resolution")})
    return sorted(out, key=lambda a: (a["at"], a["unit_id"]))


def judge_gate(args, run_uuid: str, env: dict, out_dir: str, host_dir: str) -> dict:
    """Everything that must hold before a real judge pass may start. --judge-model alone authorizes nothing: the paid
    scope must be restated (--confirm-judge '<run_uuid>|<judge_model>|<estimate_usd>'), operator audit metadata given
    (recorded verbatim, never verified by this CLI), the environment not in mock mode for a real provider, the provider's
    credential name present, the ledger given must be the one this run is bound to (ledger_binding.json: real path and
    ledger id), and the run's paid judge history in that ledger must be clean: no open reservation, no held or
    unresolvable unit, no UNKNOWN call; an earlier judged unit refuses unless --rejudge (a new unit, a new reservation,
    recorded as rejudge_of). The out_dir results are a secondary signal only."""
    if not args.judge_model or args.judge_estimate_usd is None:
        raise GradingCliError("--judge requires --judge-model and --judge-estimate-usd")
    if not args.ledger:
        raise GradingCliError("--judge requires --ledger (the judge calls are reserved and settled there)")
    parts = (args.confirm_judge or "").split("|")
    ok = len(parts) == 3 and parts[0].strip() == run_uuid and parts[1].strip() == args.judge_model
    try:
        ok = ok and Decimal(parts[2].strip()) == Decimal(str(args.judge_estimate_usd))
    except Exception:
        ok = False
    if not ok:
        raise GradingCliError("--judge requires --confirm-judge '<run_uuid>|<judge_model>|<estimate_usd>' restating the paid judge scope exactly")
    if not (args.authorized_by and args.authorization_ref):
        raise GradingCliError("--judge requires --authorized-by and --authorization-ref (audit metadata for the record)")
    provider = args.judge_model.split("/", 1)[0]
    if provider != "mockllm":
        try:
            refuse_disabled_model_api(env)
        except LauncherError as ex:
            raise GradingCliError(str(ex)) from ex
        if provider not in KEY_ENV_BY_PROVIDER:
            raise GradingCliError(f"unknown judge provider {provider!r}; refusing")
        names = load_env_file(args.env_file, env)
        missing = missing_keys([provider], env)
        if missing:
            raise GradingCliError(f"missing credential variable(s) for the judge provider: {missing} (names only)")
    else:
        names, missing = [], []
    binding = load_ledger_binding(host_dir)
    if binding.get("run_uuid") != run_uuid:
        raise GradingCliError(f"ledger_binding.json names run {binding.get('run_uuid')!r}, not {run_uuid!r}")
    given_path = os.path.realpath(args.ledger)
    if given_path != binding.get("ledger_path"):
        raise GradingCliError(f"--ledger {given_path} is not the ledger this run is bound to ({binding.get('ledger_path')}); refusing (no second cost history for one run)")
    with open(given_path, encoding="utf-8") as f:
        ledger_id = json.load(f).get("ledger_id")
    if not ledger_id or ledger_id != binding.get("ledger_id"):
        raise GradingCliError(f"ledger id {ledger_id!r} differs from the run's bound ledger id {binding.get('ledger_id')!r}; refusing")
    return {"by": args.authorized_by, "ref": args.authorization_ref, "confirm": args.confirm_judge, "judge_model": args.judge_model, "estimate_usd": str(args.judge_estimate_usd),
            "env_names_loaded": names, "missing_key_names": missing, "rejudge": bool(args.rejudge), "binding": binding,
            "note": "operator-supplied audit metadata recorded verbatim; this CLI does not verify an approval"}


def judge_history_gate(ledger: BudgetLedger, binding: dict, out_dir: str, run_uuid: str, rejudge: bool, host_dir: str | None = None, prices: dict | None = None,
                       reservation_ledger: BudgetLedger | None = None, base_pass: str | None = None) -> dict:
    """Refuse on any unresolved paid state of this run, from the canonical ledger (not the out_dir): open reservations,
    held (manual review) or unresolvable units, UNKNOWN write-ahead calls; an earlier judged unit needs --rejudge.
    Engine .12 (Codex delta review D3): the recorded passes must establish the run's current pass from the same
    history (grade.select_pass with the attempts, as report_selection), and a recovery's base_pass must be that
    current pass, a judged one."""
    hist = combined_judge_history(ledger, binding, host_dir, prices) if host_dir else run_judge_history(ledger, binding)
    blocking = []
    if hist["units"]["open"]:
        blocking.append(f"open reservation(s) of this run: {hist['units']['open']}")
    if hist["units"]["review_pending"]:
        blocking.append(f"unit(s) of this run on manual-review hold: {hist['units']['review_pending']}")
    if hist["units"]["unresolvable"]:
        blocking.append(f"unit(s) of this run recorded as unresolvable (risk not cleared): {hist['units']['unresolvable']}")
    # An UNKNOWN call (started, no terminal event) blocks until its judge unit was reconciled with a verified amount; an
    # unresolvable or missing reconciliation keeps it blocking. The log record itself is never removed.
    resolved_ok = {uid for uid, u in hist["units"]["units"].items() if u.get("resolution") == "settled_amount"}
    unknown_blocking = {name: calls for name, calls in hist["unknown_calls"].items() if not any(name == f"{uid.replace('/', '_').replace(':', '_')}.jsonl" for uid in resolved_ok)}
    if unknown_blocking:
        blocking.append(f"UNKNOWN judge call(s) (started, no terminal event) not yet reconciled with a verified amount: {unknown_blocking}")
    snap = (reservation_ledger or ledger).snapshot()  # the ledger the judge unit is claimed in (the run's own open units of every ledger block above)
    if snap["open_reservations"]:
        blocking.append(f"open reservation(s) in the ledger: {snap['open_reservations']}")
    if blocking:
        raise GradingCliError("judge pass refused (not bypassable by --rejudge): " + "; ".join(blocking) + "; reconcile with harness.ledger_admin first")
    passes = grading_passes(out_dir, run_uuid)
    sel = select_pass(passes, attempts=judge_attempts(hist, passes))
    if sel["blocked"]:
        raise GradingCliError(f"judge pass refused (not bypassable by --rejudge): the run's judge history does not establish its current pass ({sel['basis']}); reconcile first")
    if base_pass is not None and ((sel.get("pass") or {}).get("grading_pass") != base_pass or (sel.get("pass") or {}).get("judge_mode") != "real"):
        raise GradingCliError(f"judge recovery refused: base pass {base_pass} is not the run's current judged pass ({(sel.get('pass') or {}).get('grading_pass')}) in its judge history")
    prior = hist["units"]["judge_units"]
    prior_out = [p.get("grading_pass") for p in grading_passes(out_dir, run_uuid) if p.get("judge_mode") == "real"]  # engine .10: by pass identity, not a call count
    if (prior or prior_out) and not rejudge:
        raise GradingCliError(f"a paid judge pass already exists for run {run_uuid} (ledger units {prior}; out_dir passes {prior_out}); pass --rejudge to run and pay for another one")
    return {"history": hist, "prior_judge_units": prior, "prior_judged_passes_in_out_dir": prior_out}


def main(argv=None, *, judge_factory=None, environ: dict | None = None) -> int:
    """``judge_factory(model_name, cfg)`` and ``environ`` are injection points for tests; defaults are
    ProviderJudge over inspect_ai and os.environ. Without --judge nothing here contacts a provider."""
    p = argparse.ArgumentParser(description="Offline deterministic grading of one saved run; the judge runs only with --judge and its gate")
    p.add_argument("--host-dir", required=True, help="runs_root/<TaskState uuid> of the saved run")
    p.add_argument("--eval-log", required=True, help="the completed Inspect .eval log of that run")
    p.add_argument("--task-id", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--config", default=os.path.join(ROOT, "config.json"))
    p.add_argument("--ledger", default=None, help="budget ledger JSON; with --unit-id links the launcher's settlement to this grading")
    p.add_argument("--unit-id", default=None)
    p.add_argument("--no-recalc", action="store_true", help="skip the LibreOffice recalculation (docker); formulas without cached values stay unassessable")
    p.add_argument("--judge", action="store_true", help="also run the judge-only criteria through the real judge (paid); requires the judge gate arguments")
    p.add_argument("--judge-model", default=None, help="Inspect model name of the judge, e.g. google/<id>; audit input, not an authorization")
    p.add_argument("--judge-estimate-usd", type=Decimal, default=None, help="reservation for this run's judge calls")
    p.add_argument("--confirm-judge", default=None, help="restate the paid judge scope as '<run_uuid>|<judge_model>|<estimate_usd>'")
    p.add_argument("--authorized-by", default=None); p.add_argument("--authorization-ref", default=None)
    p.add_argument("--rejudge", action="store_true", help="allow a second judged pass for a run that already has one (paid again)")
    p.add_argument("--env-file", default=os.path.join(ROOT, ".env"), help="credential file read (names only logged) for a real judge provider")
    p.add_argument("--judge-recover", default=None, help="engine .7: comma-separated judge items of --base-pass to recover (provider_error retried once, not_attempted run once); never a completed call (grading.judge_recovery)")
    p.add_argument("--base-pass", default=None, help="the judged pass whose interrupted items --judge-recover completes")
    p.add_argument("--judge-ledger", default=None, help="a separate judge cost ledger (e.g. the Judge Dev ledger): judge reservations, settlements and write-ahead logs go there; declared in the run's judge_ledger_binding.json")
    args = p.parse_args(argv)
    env = os.environ if environ is None else environ
    if args.unit_id and not args.ledger:
        raise GradingCliError("--unit-id needs --ledger")
    materials = load_materials(args.task_id, args.config)
    host_dir, log, sample, binding = resolve_run(args.host_dir, args.eval_log, args.task_id)
    os.makedirs(args.out_dir, exist_ok=True)
    judge, judge_run, judge_auth, judge_calls_path, history = None, None, None, None, None
    with open(args.config, encoding="utf-8") as f:
        cfg = json.load(f)
    ledger = None
    if args.ledger:
        if not os.path.isfile(args.ledger):
            raise GradingCliError(f"--ledger {args.ledger} does not exist; grading never creates a ledger")
        ledger = BudgetLedger.open_existing(args.ledger, prices_from_config(cfg))
    common = dict(task_id=args.task_id, rubric=materials["rubric"], task_prompt=materials["task_prompt"], reference=materials["reference"], out_dir=args.out_dir, recalc=not args.no_recalc)
    recover_items = None
    if args.judge_recover:
        from . import judge_recovery as JR
        if not (args.judge and args.base_pass):
            raise GradingCliError("--judge-recover needs --judge and --base-pass")
        recover_items = sorted({int(x) for x in args.judge_recover.split(",") if x.strip()})
        plan = JR.recovery_plan(args.out_dir, sample.uuid, args.base_pass, recover_items)  # refused before any reservation or call
        refused = {i: d["reason"] for i, d in plan["decision"].items() if not d["eligible"]}
        if refused or not recover_items:
            raise GradingCliError(f"judge recovery refused: {refused or 'no item'}")
    if not args.judge:
        rec = grade_run(host_dir, log, sample.uuid, judge=None, **common)
    else:
        judge_auth = judge_gate(args, sample.uuid, env, args.out_dir, host_dir)
        judge_ledger = ledger
        if args.judge_ledger:
            if not os.path.isfile(args.judge_ledger):
                raise GradingCliError(f"--judge-ledger {args.judge_ledger} does not exist; grading never creates a ledger")
            judge_ledger = BudgetLedger.open_existing(args.judge_ledger, prices_from_config(cfg))
            declare_judge_ledger(host_dir, sample.uuid, judge_ledger, "separate judge cost ledger (approved 2026-11-01)")
        history = judge_history_gate(ledger, judge_auth["binding"], args.out_dir, sample.uuid, bool(args.rejudge or recover_items), host_dir=host_dir, prices=prices_from_config(cfg),
                                     reservation_ledger=judge_ledger, base_pass=args.base_pass if recover_items else None)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + os.urandom(2).hex()  # unique even for two passes within one second
        judge_unit = f"{sample.uuid}:judge:{stamp}"
        log_path = judge_log_path(judge_ledger.path, sample.uuid, judge_unit)
        judge_params = {k: v for k, v in (cfg.get("judge") or {}).items() if k in ("temperature", "max_tokens", "max_retries", "timeout", "reasoning_effort", "pacing_pause_s", "provider_error_stop_items", "item_wall_clock_cap_s")}
        judge = judge_factory(args.judge_model, cfg) if judge_factory else ProviderJudge(args.judge_model, **judge_params)
        if getattr(judge, "is_stub", False):
            raise GradingCliError("a stub judge is never a judged pass")
        for attr, value in (("log_path", log_path), ("run_uuid", sample.uuid), ("judge_unit", judge_unit)):
            setattr(judge, attr, value)  # the write-ahead log is bound to this run and unit whatever factory built the judge
        launcher = PilotLauncher(cfg, runs_root=args.out_dir, ledger=judge_ledger, eval_fn=None)
        launcher.record("judge_authorization", {**{k: v for k, v in judge_auth.items() if k != "binding"}, "ledger": judge_ledger.identity(), "generation_ledger": ledger.identity(), "unit_id": judge_unit, "run": binding, "task_id": args.task_id,
                                                "criteria": "judge-only items of the task module", "rejudge_of": history["prior_judge_units"] if args.rejudge else [],
                                                "superseded_judged_passes": history["prior_judged_passes_in_out_dir"] if args.rejudge else [], "judge_call_log": log_path,
                                                "recovery": {"base_pass": args.base_pass, "items": recover_items} if recover_items else None,
                                                "code": git_provenance(), "config_sha256": materials["config_sha256"], "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        state = {}

        def batch_fn():
            if recover_items:
                state["rec"] = JR.recovery_pass(args.out_dir, sample.uuid, args.task_id, args.base_pass, recover_items, judge)
            else:
                state["rec"] = grade_run(host_dir, log, sample.uuid, judge=judge, **common)
            return judge.batch_result()
        def recover_usage():  # correction B: durable evidence first; the adapter's memory cross-checks it
            return durable_usage(log_path, judge)
        try:
            judge_run = launcher.run_judge_batch(unit_id=judge_unit, estimate_usd=args.judge_estimate_usd, batch_fn=batch_fn, recover_usage=recover_usage)
        except (BudgetExhausted, LedgerConflict) as ex:  # a recorded stop, hold, open reservation or an already-claimed unit: no reservation, no judge call
            raise GradingCliError(f"judge pass refused by the budget ledger before any call: {ex}") from ex
        finally:
            if state or getattr(judge, "calls", None):  # the batch started: keep every call (raw responses live only here and in the sealed review file)
                judge_calls_path = os.path.join(args.out_dir, f"judge_calls_{sample.uuid}_{stamp}.json")
                with open(judge_calls_path, "x", encoding="utf-8") as f:
                    json.dump({"run": binding, "unit_id": judge_unit, "judge_id": getattr(judge, "judge_id", None), "model": args.judge_model, "generate_params": getattr(judge, "generate_params", None),
                               "calls": getattr(judge, "calls", []), "batch": getattr(judge, "batch_result", lambda: None)()}, f, indent=1, default=str)
        rec = state["rec"]
    settlement = settlement_for(ledger, args.unit_id) if (ledger and args.unit_id) else None
    judge_settlement = settlement_for(judge_ledger, (judge_run or {}).get("unit_id")) if (judge is not None and judge_run) else None  # effective, from the judge ledger (the run's ledger unless --judge-ledger)
    grading = None
    if judge is not None:
        accounting = ("manual_review_required" if judge_settlement and judge_settlement.get("manual_review_required") else "estimated" if judge_settlement and judge_settlement.get("estimated")
                      else "reliably_accounted" if judge_settlement else "not_settled")
        grading = {"source": "judge ledger settlement", "unit_id": (judge_run or {}).get("unit_id"), "usage_incomplete": (judge_run or {}).get("usage_incomplete"), "accounting_status": accounting,
                   **({k: judge_settlement.get(k) for k in ("cost_usd", "estimated", "inferred", "manual_review_required", "flags", "note", "resolution", "previous_cost_usd", "resolved_from", "raw_events")} if judge_settlement else {}),
                   "priced_from_calls": grading_cost(getattr(judge, "usage_by_model", {}) or {}, prices_from_config(cfg)) if getattr(judge, "usage_by_model", None) else None, "calls_log": judge_calls_path,
                   "write_ahead_log": getattr(judge, "log_path", None), "halted": getattr(judge, "halted", None), "rejudge_of": history["prior_judge_units"] if args.rejudge else []}
    cost = run_cost_record(sample.uuid, {"source": "launcher ledger settlement" if settlement else "not linked (no --ledger/--unit-id)", "unit_id": args.unit_id,
                                         **({k: settlement.get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags", "breakdown", "raw_usage", "resolution", "previous_cost_usd", "resolved_from", "raw_events")} if settlement else {})}, grading)
    pending = [i for i in rec.get("score", {}).get("ungraded", []) if i["verdict"] == "pending_judge"] if rec.get("graded") else []
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prov_path = os.path.join(args.out_dir, f"grading_run_{sample.uuid}_{rec.get('grading_pass') or stamp}.json")  # one file per grading pass (pass ids are unique; two passes may share a second)
    provenance = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "run": binding, "host_dir": host_dir,
                  "eval_log": {"path": os.path.realpath(args.eval_log), "sha256": _sha256(args.eval_log), "status": log.status},
                  "code": git_provenance(), "config": {"path": os.path.realpath(args.config), "sha256": materials["config_sha256"]}, "materials": {"paths": materials["paths"], "sha256": materials["hashes"]},
                  "grader_version": rec.get("grader_version"), "grading_pass": rec.get("grading_pass"), "pass_kind": rec.get("pass_kind"), "supersedes_pass": rec.get("supersedes_pass"),
                  "judge_completeness": rec.get("judge_completeness"), "judge_unit": rec.get("judge_unit"),
                  "selected_pass_for_report": report_selection(cfg, host_dir, args.out_dir, sample.uuid, ledger=ledger),
                  "judge_mode": rec.get("judge_mode"), "judge": ({"authorization": judge_auth, "unit_id": (judge_run or {}).get("unit_id"), "call_summary": rec.get("judge_call_summary"), "calls_log": judge_calls_path} if judge is not None else None),
                  "judge_items_pending": [i["item"] for i in pending],
                  "gate": rec.get("gate"), "graded": rec.get("graded"), "outputs": {"results": os.path.join(args.out_dir, "results.jsonl"), "grades": os.path.join(args.out_dir, "grades.jsonl") if rec.get("graded") else None,
                                                                                    "review_materials": rec.get("review_materials")}, "cost": cost}
    with open(prov_path, "x", encoding="utf-8") as f:
        json.dump(provenance, f, indent=1, default=str)
    score = rec.get("score") or {}
    print(json.dumps({"graded": rec.get("graded"), "gate": rec.get("gate"), "gate_reason": rec.get("gate_reason"), "outcome_class": rec.get("outcome_class_effective"),
                      "grading_pass": rec.get("grading_pass"), "pass_kind": rec.get("pass_kind"), "judge_call_summary": rec.get("judge_call_summary"), "judge_completeness": rec.get("judge_completeness"),
                      "accounting_status": (grading or {}).get("accounting_status"),
                      "judge_settlement": {k: judge_settlement.get(k) for k in ("cost_usd", "estimated", "manual_review_required")} if judge_settlement else None,
                      "W": score.get("W"), "E": score.get("E"), "P": score.get("P"), "critical": {k: v["status"] for k, v in (score.get("critical") or {}).items()},
                      "judge_items_pending": [i["item"] for i in pending], "provenance": prov_path, "cost_source": cost["generation"]["source"]}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except GradingCliError as ex:
        print(f"refused: {ex}", file=sys.stderr)
        sys.exit(2)
