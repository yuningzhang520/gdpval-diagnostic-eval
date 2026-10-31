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

from harness.budget import BudgetExhausted, BudgetLedger
from harness.launcher import KEY_ENV_BY_PROVIDER, LauncherError, PilotLauncher, config_sha256, git_provenance, load_env_file, missing_keys, prices_from_config, refuse_disabled_model_api
from grading.costs import grading_cost, run_cost_record
from grading.grade import grade_run, grading_passes, select_pass
from grading.judge import ProviderJudge

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


def settlement_for(ledger_path: str, unit_id: str) -> dict | None:
    with open(ledger_path, encoding="utf-8") as f:
        entries = json.load(f).get("entries", [])
    return next((e for e in entries if e.get("type") == "settlement" and e.get("unit_id") == unit_id), None)


def judge_gate(args, run_uuid: str, env: dict, out_dir: str) -> dict:
    """Everything that must hold before a real judge pass may start. --judge-model alone authorizes nothing:
    the paid scope must be restated (--confirm-judge '<run_uuid>|<judge_model>|<estimate_usd>'), operator
    audit metadata given (recorded verbatim, never verified by this CLI), a ledger named, the environment not
    in mock mode for a real provider, the provider's credential name present, and no judged pass already
    recorded for this run in out_dir unless --rejudge is given (a repeat is a new paid pass)."""
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
    judged = [p for p in grading_passes(out_dir, run_uuid) if p.get("judge_mode") == "real" and p.get("judge_verdicts")]
    if judged and not args.rejudge:
        raise GradingCliError(f"a judged grading pass already exists for run {run_uuid} ({judged[-1].get('grading_pass')}); pass --rejudge to run and pay for another one")
    return {"by": args.authorized_by, "ref": args.authorization_ref, "confirm": args.confirm_judge, "judge_model": args.judge_model, "estimate_usd": str(args.judge_estimate_usd),
            "env_names_loaded": names, "missing_key_names": missing, "rejudge": bool(args.rejudge), "previous_judged_passes": [p.get("grading_pass") for p in judged],
            "note": "operator-supplied audit metadata recorded verbatim; this CLI does not verify an approval"}


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
    args = p.parse_args(argv)
    env = os.environ if environ is None else environ
    if args.unit_id and not args.ledger:
        raise GradingCliError("--unit-id needs --ledger")
    materials = load_materials(args.task_id, args.config)
    host_dir, log, sample, binding = resolve_run(args.host_dir, args.eval_log, args.task_id)
    os.makedirs(args.out_dir, exist_ok=True)
    judge, judge_run, judge_auth, judge_calls_path = None, None, None, None
    common = dict(task_id=args.task_id, rubric=materials["rubric"], task_prompt=materials["task_prompt"], reference=materials["reference"], out_dir=args.out_dir, recalc=not args.no_recalc)
    if not args.judge:
        rec = grade_run(host_dir, log, sample.uuid, judge=None, **common)
    else:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
        judge_auth = judge_gate(args, sample.uuid, env, args.out_dir)
        judge = judge_factory(args.judge_model, cfg) if judge_factory else ProviderJudge(args.judge_model, **{k: v for k, v in (cfg.get("judge") or {}).items() if k in ("temperature", "max_tokens", "max_retries", "timeout")})
        if getattr(judge, "is_stub", False):
            raise GradingCliError("a stub judge is never a judged pass")
        ledger = BudgetLedger(args.ledger, cfg["pilot"]["budget_ceiling_usd"], prices_from_config(cfg))
        launcher = PilotLauncher(cfg, runs_root=args.out_dir, ledger=ledger, eval_fn=None)
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        judge_unit = f"{sample.uuid}:judge:{stamp}"
        launcher.record("judge_authorization", {**judge_auth, "unit_id": judge_unit, "run": binding, "task_id": args.task_id, "criteria": "judge-only items of the task module",
                                                "code": git_provenance(), "config_sha256": materials["config_sha256"], "started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        state = {}

        def batch_fn():
            state["rec"] = grade_run(host_dir, log, sample.uuid, judge=judge, **common)
            return judge.batch_result()
        try:
            judge_run = launcher.run_judge_batch(unit_id=judge_unit, estimate_usd=args.judge_estimate_usd, batch_fn=batch_fn)
        except BudgetExhausted as ex:  # a recorded stop or manual-review hold on the ledger: no reservation, no judge call
            raise GradingCliError(f"judge pass refused by the budget ledger before any call: {ex}") from ex
        finally:
            if state or getattr(judge, "calls", None):  # the batch started: keep every call (raw responses live only here and in the sealed review file)
                judge_calls_path = os.path.join(args.out_dir, f"judge_calls_{sample.uuid}_{stamp}.json")
                with open(judge_calls_path, "x", encoding="utf-8") as f:
                    json.dump({"run": binding, "unit_id": judge_unit, "judge_id": getattr(judge, "judge_id", None), "model": args.judge_model, "generate_params": getattr(judge, "generate_params", None),
                               "calls": getattr(judge, "calls", []), "batch": getattr(judge, "batch_result", lambda: None)()}, f, indent=1, default=str)
        rec = state["rec"]
    settlement = settlement_for(args.ledger, args.unit_id) if args.unit_id else None
    judge_settlement = (judge_run or {}).get("settlement")
    grading = None
    if judge is not None:
        grading = {"source": "judge ledger settlement", "unit_id": (judge_run or {}).get("unit_id"), "usage_incomplete": (judge_run or {}).get("usage_incomplete"),
                   **({k: judge_settlement.get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags", "note")} if judge_settlement else {}),
                   "priced_from_calls": grading_cost(getattr(judge, "usage_by_model", {}) or {}, prices_from_config(cfg)) if getattr(judge, "usage_by_model", None) else None, "calls_log": judge_calls_path}
    cost = run_cost_record(sample.uuid, {"source": "launcher ledger settlement" if settlement else "not linked (no --ledger/--unit-id)", "unit_id": args.unit_id,
                                         **({k: settlement.get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags", "breakdown", "raw_usage")} if settlement else {})}, grading)
    pending = [i for i in rec.get("score", {}).get("ungraded", []) if i["verdict"] == "pending_judge"] if rec.get("graded") else []
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prov_path = os.path.join(args.out_dir, f"grading_run_{sample.uuid}_{rec.get('grading_pass') or stamp}.json")  # one file per grading pass (pass ids are unique; two passes may share a second)
    provenance = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "run": binding, "host_dir": host_dir,
                  "eval_log": {"path": os.path.realpath(args.eval_log), "sha256": _sha256(args.eval_log), "status": log.status},
                  "code": git_provenance(), "config": {"path": os.path.realpath(args.config), "sha256": materials["config_sha256"]}, "materials": {"paths": materials["paths"], "sha256": materials["hashes"]},
                  "grader_version": rec.get("grader_version"), "grading_pass": rec.get("grading_pass"), "pass_kind": rec.get("pass_kind"), "supersedes_pass": rec.get("supersedes_pass"),
                  "selected_pass_for_report": (select_pass(grading_passes(args.out_dir, sample.uuid)) or {}).get("grading_pass"),
                  "judge_mode": rec.get("judge_mode"), "judge": ({"authorization": judge_auth, "unit_id": (judge_run or {}).get("unit_id"), "call_summary": rec.get("judge_call_summary"), "calls_log": judge_calls_path} if judge is not None else None),
                  "judge_items_pending": [i["item"] for i in pending],
                  "gate": rec.get("gate"), "graded": rec.get("graded"), "outputs": {"results": os.path.join(args.out_dir, "results.jsonl"), "grades": os.path.join(args.out_dir, "grades.jsonl") if rec.get("graded") else None,
                                                                                    "review_materials": rec.get("review_materials")}, "cost": cost}
    with open(prov_path, "x", encoding="utf-8") as f:
        json.dump(provenance, f, indent=1, default=str)
    score = rec.get("score") or {}
    print(json.dumps({"graded": rec.get("graded"), "gate": rec.get("gate"), "gate_reason": rec.get("gate_reason"), "outcome_class": rec.get("outcome_class_effective"),
                      "grading_pass": rec.get("grading_pass"), "pass_kind": rec.get("pass_kind"), "judge_call_summary": rec.get("judge_call_summary"),
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
