"""Grading entry point. Consumes run_outcome.json through harness.collect.load_run_outcome with
the identity taken from the completed Inspect log, joins the terminal log, routes the run by the
attribution policy (harness-caused → run error; unknown → adjudication; model-caused → graded with
the rejected files treated as not delivered; complete / no_files_confirmed → graded; limited → graded
like any other eligible run), and writes grades.jsonl (one line per criterion) and results.jsonl
(one line per run). Nothing here calls a model; the judge is injected (stub in tests, real judge only
under pilot authorization)."""
import datetime as dt
import json
import os
import subprocess

from typing import get_args

from harness import collect as C
from harness.redact import redact, redact_path

try:
    from inspect_ai.log import EvalStatus  # Literal["started", "success", "cancelled", "error"]
except ImportError:  # pragma: no cover
    from inspect_ai.log._log import EvalStatus
VALID_EVAL_STATUS = frozenset(get_args(EvalStatus))
from . import checks_1137e2bb as CK
from . import checks_7d7fc9a7 as CK2
from . import checks_2ea2e5b5 as CK3
from . import checks_a45bc83b as CK4
from . import judge as J
from .extract import extract_all
from .review import write_review_materials

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Versioning (2026-11-01): the shared engine (extraction, recalculation, outcome gate, scoring, pass selection, judge and
# review infrastructure) carries ENGINE_VERSION; every task specification carries its own VERSION; a grading pass records
# the combined grader version "<engine>+<task>" and the full git commit of the code that graded. config.grading must state
# the engine version and the per-task versions (checked by run_grading before any grading).
ENGINE_VERSION = "engine-2026-11-01.1"
TASK_MODULES = {CK.TASK: {"checks": CK.run_checks, "units": J.build_units_1137e2bb, "critical": CK.CRITICAL, "judge_items": CK.J_ITEMS, "visual_items": [], "version": CK.VERSION},
                CK2.TASK: {"checks": CK2.run_checks, "units": J.build_units_7d7fc9a7, "critical": CK2.CRITICAL, "judge_items": CK2.J_ITEMS, "visual_items": CK2.V_ITEMS, "version": CK2.VERSION},
                CK3.TASK: {"checks": CK3.run_checks, "units": J.build_units_2ea2e5b5, "critical": CK3.CRITICAL, "judge_items": CK3.J_ITEMS, "visual_items": CK3.V_ITEMS, "version": CK3.VERSION},
                CK4.TASK: {"checks": CK4.run_checks, "units": J.build_units_a45bc83b, "critical": CK4.CRITICAL, "judge_items": CK4.J_ITEMS, "visual_items": CK4.V_ITEMS, "version": CK4.VERSION}}


def grader_version_of(task_id: str) -> str:
    return f"{ENGINE_VERSION}+{TASK_MODULES[task_id]['version']}"


GRADER_VERSION = grader_version_of(CK.TASK)  # the pilot task's combined version (kept as the name earlier code imports)


def code_provenance() -> dict:
    """Full git commit of the grading code and whether the tree was dirty when the pass ran (recorded in every pass)."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, capture_output=True, text=True, timeout=20)
        if head.returncode != 0:
            return {"commit": None, "dirty": None, "error": "git rev-parse failed"}
        changed = [l for l in dirty.stdout.splitlines() if l.strip()] if dirty.returncode == 0 else None
        return {"commit": head.stdout.strip(), "dirty": bool(changed) if changed is not None else None,  # untracked (non-ignored) files count: they may be executable source
                "changed_paths": len(changed) if changed is not None else None, "untracked_paths": sum(1 for l in changed if l.startswith("??")) if changed is not None else None}
    except Exception as ex:  # pragma: no cover
        return {"commit": None, "dirty": None, "error": type(ex).__name__}


def binding_from_log(log, sample) -> dict:
    return {"uuid": sample.uuid, "model": log.eval.model, "task_id": log.eval.task_id, "eval_id": log.eval.eval_id, "sample_id": sample.id, "epoch": sample.epoch}


def join_log(loaded: dict, log, sample) -> dict:
    """Cross-check the final outcome against the completed Inspect log. Blocks grading when the
    sample's recorded errors/limits disagree with the outcome, when the eval log is not terminal or
    was cancelled, and when the log carries an eval-level error (``EvalLog.error``) or an error
    status without a sample error. A terminal eval error cannot be excluded for the current sample
    by any caller-supplied record: there is no override parameter, and the pilot grades such runs
    as blocked (run error) with the original error kept, redacted, in the result. A future human
    exclusion mechanism, if ever needed, is a separately approved design (bound to run and event,
    with an immutable audit basis), not part of this grader."""
    e = loaded["execution"]
    mismatches = []
    sample_error = getattr(sample, "error", None) is not None
    if sample_error != bool(e["errors"]):
        mismatches.append(f"log sample.error={'present' if sample_error else 'absent'} but outcome records {len(e['errors'])} error event(s)")
    limit = getattr(sample, "limit", None)
    log_limit_type = getattr(limit, "type", None) if limit is not None else None
    if (log_limit_type is not None) != bool(e["limits"]) or (log_limit_type is not None and log_limit_type not in e.get("limit_types", [])):
        mismatches.append(f"log sample.limit={log_limit_type!r} but outcome limit_types={e.get('limit_types')}")
    raw_status = getattr(log, "status", None)
    status_valid = isinstance(raw_status, str) and raw_status in VALID_EVAL_STATUS
    status = raw_status if status_valid else "invalid_status"  # never echo a value outside Inspect's EvalStatus enum
    if not status_valid:
        mismatches.append(f"eval log status is not a valid Inspect EvalStatus value ({redact(repr(raw_status), 80)})")
    elif status not in ("success", "error", "cancelled"):
        mismatches.append(f"eval log status {status!r} is not terminal")
    if status == "cancelled":
        mismatches.append("eval was cancelled")
    eval_error = getattr(log, "error", None)
    eval_error_msg = getattr(eval_error, "message", None) if eval_error is not None else None
    terminal_error = eval_error is not None or (status == "error" and not sample_error)
    if terminal_error:
        mismatches.append("terminal eval-level error in the log (EvalLog.error present or eval status error without a sample error); "
                          "its effect on this sample cannot be excluded: grading is blocked, no override exists")
    return {"log_status": status, "log_status_valid": status_valid, "sample_error": sample_error, "sample_limit": log_limit_type, "eval_error": eval_error is not None,
            "eval_error_type": type(eval_error).__name__ if eval_error is not None and not hasattr(eval_error, "message") else (getattr(eval_error, "error_type", None) or ("EvalError" if eval_error is not None else None)),
            "eval_error_message": redact(eval_error_msg) if eval_error_msg else None, "terminal_error_blocks_grading": terminal_error,
            "mismatches": [redact(m) for m in mismatches]}


def grading_passes(out_dir: str, run_uuid: str | None = None) -> list[dict]:
    """Every grading pass recorded in out_dir/results.jsonl (grade_run appends one results record per
    pass and never overwrites), oldest first, optionally for one run uuid. A pass is identified by
    ``grading_pass``; ``pass_kind`` is deterministic_only / deterministic_plus_judge / stub_test;
    ``supersedes_pass`` names the previous pass of the same run in the same out_dir. Any report or
    statistic groups by run uuid and takes exactly one pass per run (see select_pass); two passes of
    one run are never two samples."""
    path = os.path.join(out_dir, "results.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                if run_uuid is None or (rec.get("run") or {}).get("uuid") == run_uuid:
                    out.append(rec)
    return out


def judge_completeness(verdicts: list[dict]) -> str:
    """complete: every judge-only unit has a protocol-conformant terminal verdict (a protocol-conformant cannot_assess counts);
    partial: any provider_error, judge_parse_error or not_attempted; none: no judge in this pass. 'unknown' is assigned by
    the grading CLI to a judge unit whose write-ahead log holds a started event without a terminal event (no results record)."""
    if not verdicts:
        return "none"
    return "partial" if any(v.get("error_class") for v in verdicts) else "complete"


def select_pass(passes: list[dict], prefer: str = "latest_with_judge", attempts: list[dict] | None = None) -> dict:
    """The one pass of a run that a report uses, with the basis, warnings and the full history. ``attempts`` are the
    run's persisted judge attempts from the ledger and the write-ahead logs ({"unit_id", "state": settled|held|open|unknown,
    "at", "has_pass"}): when the LATEST attempt has no results record (it is UNKNOWN, still open or otherwise unfinished)
    the selection is ``blocked`` - no pass is returned as current, the older passes stay in ``history`` for review, and
    the warning names the attempt. Otherwise ``latest_with_judge`` selects the latest judged pass even when partial
    (an older complete pass never hides a newer failure); without a judged pass the latest deterministic-only pass."""
    graded = [p for p in passes if p.get("graded")]
    history = [{k: p.get(k) for k in ("grading_pass", "pass_kind", "judge_mode", "judge_completeness", "judge_unit", "graded_at")} for p in graded]
    authoritative = attempts is not None  # without the persisted attempt history this is historical inspection, never the authoritative result
    latest_attempt = max(attempts, key=lambda a: (a.get("at") or "", a.get("unit_id") or "")) if attempts else None  # reservations carry second stamps; the unit id carries microseconds
    warnings = [] if authoritative else ["attempt history not loaded: historical view only, not an authoritative selection (use grading.run_grading.report_selection)"]
    if latest_attempt and not latest_attempt.get("has_pass"):
        if latest_attempt.get("state") in ("unknown", "open", "held"):
            return {"pass": None, "blocked": True, "authoritative": True, "history": history,
                    "basis": f"latest judge attempt {latest_attempt['unit_id']} is {latest_attempt.get('state')} and produced no grading pass; no current pass is selected until it is reconciled",
                    "warnings": [f"unfinished judge attempt {latest_attempt['unit_id']} ({latest_attempt.get('state')}); {len(graded)} earlier pass(es) are kept for review only"]}
        warnings.append(f"latest judge attempt {latest_attempt['unit_id']} was reconciled ({latest_attempt.get('state')}) without producing a grading pass; the selection falls back to the latest recorded pass")
    if not graded:
        return {"pass": None, "blocked": False, "authoritative": authoritative, "history": history, "basis": "no graded pass", "warnings": warnings + ["no graded pass recorded"]}
    judged = [p for p in graded if p.get("judge_mode") == "real" and p.get("judge_verdicts")]
    if prefer == "latest_with_judge" and judged:
        chosen = judged[-1]
        basis = f"latest judged pass {chosen.get('grading_pass')} (judge_completeness {chosen.get('judge_completeness')}) of {len(judged)} judged / {len(graded)} graded passes"
        if chosen.get("judge_completeness") != "complete":
            warnings.append(f"selected judged pass is {chosen.get('judge_completeness')}: {chosen.get('judge_call_summary')}; earlier passes are not used to hide this")
        if len(judged) > 1:
            warnings.append(f"{len(judged)} judged passes exist for this run; only the latest is selected, the others stay recorded")
    else:
        chosen = graded[-1]
        basis = f"latest graded pass {chosen.get('grading_pass')} ({chosen.get('pass_kind')}); no judged pass" if not judged else f"latest graded pass {chosen.get('grading_pass')}"
        if chosen.get("judge_mode") != "real":
            warnings.append("judge-only items are pending in the selected pass")
    return {"pass": chosen, "blocked": False, "authoritative": authoritative, "history": history, "basis": basis, "warnings": warnings}


def selected_grades(out_dir: str, run_uuid: str, prefer: str = "latest_with_judge", attempts: list[dict] | None = None) -> dict:
    """Grade rows of the selected pass only: the statistics input for one model run (never rows of several passes).
    FAIL-CLOSED: ``attempts`` (the run's persisted judge attempts, an empty list when the history was loaded and holds
    none) is required; without it the entry returns blocked and no rows, so a caller that skipped the history can never
    receive an old complete pass as the current result. Blocked selections return no rows."""
    passes = grading_passes(out_dir, run_uuid)
    if attempts is None:
        sel = select_pass(passes, prefer, attempts=None)
        return {**sel, "pass": None, "blocked": True, "authoritative": False, "grades": [],
                "basis": "attempt history not supplied; the statistics entry fails closed (use grading.run_grading.authoritative_selection, which resolves the run's bound ledger)"}
    sel = select_pass(passes, prefer, attempts=attempts)
    rows = []
    if sel["pass"] and not sel.get("blocked"):
        with open(os.path.join(out_dir, "grades.jsonl"), encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        rows = [r for r in rows if r.get("run_uuid") == run_uuid and r.get("grading_pass") == sel["pass"]["grading_pass"]]
    return {**sel, "grades": rows}


def _score(grades: list[dict], critical_spec: dict) -> dict:
    W = sum(g["weight"] for g in grades)
    graded = [g for g in grades if g["verdict"] in ("pass", "fail")]
    E = sum(g["weight"] for g in graded)
    P = sum(g["weight"] for g in graded if g["verdict"] == "pass")
    by_item = {g["item"]: g["verdict"] for g in grades}
    critical = {}
    for cid, spec in critical_spec.items():
        items = spec["items"] + spec.get("judge_items", []) + spec.get("visual_items", [])  # visual rows stay pending_human until reviewed
        vs = [by_item.get(i, "pending") for i in items]
        critical[cid] = {"name": spec["name"], "status": "fail" if "fail" in vs else "pass" if vs and all(v == "pass" for v in vs) else "not_confirmed", "items": items,
                         "verdicts": {i: by_item.get(i, "pending") for i in items}}
    return {"W": W, "E": E, "P": P, "P_over_E": (P / E) if E else None, "E_over_W": (E / W) if W else None,
            "ungraded": [{"item": g["item"], "verdict": g["verdict"], "reason": g.get("note") or g.get("rationale") or g.get("parse_error")} for g in grades if g["verdict"] not in ("pass", "fail")],
            "critical": critical, "critical_overall": "fail" if any(c["status"] == "fail" for c in critical.values()) else "pass" if all(c["status"] == "pass" for c in critical.values()) else "not_confirmed"}


def grade_run(host_dir: str, log, sample_uuid: str, *, task_id: str, rubric: list[dict], task_prompt: str, reference: dict, out_dir: str,
              judge=None, recalc: bool = True, runner=subprocess.run, grader_version: str | None = None,
              allow_stub: bool = False) -> dict:
    """Grade one run. ``log`` is a completed Inspect EvalLog (or an object with the same fields).
    A stub judge is refused unless ``allow_stub`` (test mode) is set explicitly. There is no
    parameter that can lift a terminal-log block. Error text written to the results is redacted.
    Returns the results record that was appended to out_dir/results.jsonl."""
    if judge is not None and getattr(judge, "is_stub", False) and not allow_stub:
        raise ValueError("stub judge refused in formal grading mode; pass allow_stub=True only in an explicit test run")
    if task_id not in TASK_MODULES:
        raise ValueError(f"no grader registered for task {task_id}")
    grader_version = grader_version or grader_version_of(task_id)
    os.makedirs(out_dir, exist_ok=True)
    sample = next((s for s in log.samples if s.uuid == sample_uuid), None)
    if sample is None:
        raise ValueError(f"sample {sample_uuid} not in the log")
    binding = binding_from_log(log, sample)
    judge_mode = "stub-test-mode" if getattr(judge, "is_stub", False) else "real" if judge is not None else "none"
    previous = grading_passes(out_dir, binding["uuid"])
    graded_at = dt.datetime.now(dt.timezone.utc)
    rec = {"run": binding, "task_id": task_id, "graded_at": graded_at.isoformat(timespec="seconds"), "grader_version": grader_version,
           "engine_version": ENGINE_VERSION, "task_grader_version": TASK_MODULES[task_id]["version"], "code": code_provenance(),
           "grading_pass": f"pass-{graded_at.strftime('%Y%m%dT%H%M%S%fZ')}-{os.urandom(2).hex()}",
           "pass_kind": {"none": "deterministic_only", "real": "deterministic_plus_judge", "stub-test-mode": "stub_test"}[judge_mode],
           "supersedes_pass": previous[-1].get("grading_pass") if previous else None, "pass_index": len(previous) + 1,
           "log_file": redact_path(getattr(log, "location", None)), "graded": False, "judge_mode": judge_mode, "judge_unit": getattr(judge, "judge_unit", None) if judge is not None else None}
    try:
        loaded = C.load_run_outcome(host_dir, binding, for_grading=False)
    except C.OutcomeValidationError as ex:
        rec.update({"gate": "refused", "gate_reason": redact(ex), "gate_reason_type": type(ex).__name__, "outcome_class": None})
        return _append(out_dir, rec)
    join = join_log(loaded, log, sample)
    eff = loaded["effective"]
    rec.update({"gate": "passed", "collection_status": loaded["collection_status"], "execution_status": loaded["execution"]["status"],
                "limit_types": loaded["execution"].get("limit_types", []), "limited": loaded["execution"]["status"] == "limited",
                "outcome_class_stored": loaded["outcome_class"], "outcome_class_effective": eff["outcome_class"], "grading_eligible": eff["grading_eligible"],
                "attribution_class": eff["attribution"]["class"], "attribution_items": eff["attribution"]["items"], "adjudication_applied": eff["adjudication_applied"],
                "harness_error": loaded["harness_error"], "log_join": join})
    if join["mismatches"]:
        # Blocked before the outcome policy: an adjudication of unknown collection items never reaches this point for such a run.
        rec.update({"gate": "log_join_mismatch", "graded": False, "gate_reason": "; ".join(join["mismatches"])})
        return _append(out_dir, rec)
    if not eff["grading_eligible"]:
        rec.update({"graded": False, "reason": eff["grading_basis"]})
        return _append(out_dir, rec)
    mod = TASK_MODULES[task_id]
    rejected_files = [i["path"] for i in eff["attribution"]["items"] if i["class"] == "model_caused"]
    work = os.path.join(out_dir, f"work_{binding['uuid']}")
    extraction = extract_all(os.path.join(host_dir, "final"), work, recalc=recalc, runner=runner)
    # transfer integrity per deliverable: collector-side hash == collected hash == hash of the copy on disk
    collected = {os.path.relpath(f["host_path"], os.path.join(host_dir, "final")): f for f in loaded["collection"]["files"] if f.get("status") in ("collected", "already_collected") and f.get("host_path")}
    integrity = {}
    for item in extraction["inventory"]:
        f = collected.get(item["path"])
        integrity[item["path"]] = (f is not None and f.get("sha256_in_sandbox") == f.get("sha256_collected") == item["sha256"]) if f else None
    provenance = {k: {kk: v.get(kk) for kk in ("sha256", "copy_sha256", "copy_verified", "copy_verified_before_parse", "error_class", "exception_type", "error")} for k, v in list(extraction["xlsx"].items()) + list(extraction["docx"].items()) + list(extraction["pptx"].items()) + list(extraction.get("pdf", {}).items())}
    checks = mod["checks"](extraction, reference, rubric, integrity=integrity)
    units = mod["units"](task_prompt, rubric, extraction, reference, checks, binding["uuid"])
    verdicts = J.judge_units(units, judge) if judge is not None else []
    grades = []
    for i, r in checks["items"].items():
        grades.append({"run_uuid": binding["uuid"], "task_id": task_id, "item": i, "weight": r["weight"], "criterion": r["criterion"], "source": "D", "verdict": r["verdict"],
                       "evidence": r["evidence"], "deliverable_value": r["deliverable_value"], "reference_value": r["reference_value"], "note": r["note"],
                       "attribution": r.get("attribution"), "grader_version": grader_version, "grading_pass": rec["grading_pass"]})
    vb = {v["item"]: v for v in verdicts}
    for i in mod["judge_items"]:
        v = vb.get(i)
        grades.append({"run_uuid": binding["uuid"], "task_id": task_id, "item": i, "weight": rubric[i - 1]["score"], "criterion": rubric[i - 1]["criterion"], "source": "J",
                       "verdict": v["verdict"] if v else "pending_judge", "evidence": v["evidence"] if v else [], "rationale": v["rationale"] if v else "", "judge_id": v["judge_id"] if v else None,
                       "parse_error": v["parse_error"] if v else None, "error_class": v.get("error_class") if v else None, "call_status": v.get("call_status") if v else None,
                       "usage_status": v.get("usage_status") if v else None, "grader_version": grader_version, "grading_pass": rec["grading_pass"]})
    for i in mod.get("visual_items", []):  # visual criteria: never judged from text; stay in W as ungraded until the human review records a verdict
        grades.append({"run_uuid": binding["uuid"], "task_id": task_id, "item": i, "weight": rubric[i - 1]["score"], "criterion": rubric[i - 1]["criterion"], "source": "V",
                       "verdict": "pending_human", "evidence": [], "note": "visual criterion: human review from the rendered deliverable", "grader_version": grader_version, "grading_pass": rec["grading_pass"]})
    grades.sort(key=lambda g: g["item"])
    with open(os.path.join(out_dir, "grades.jsonl"), "a", encoding="utf-8") as f:
        for g in grades:
            f.write(json.dumps(g, default=str) + "\n")
    score = _score(grades, mod["critical"])
    review = write_review_materials(os.path.join(out_dir, "review"), binding["uuid"], rubric, checks, units, verdicts, extraction, reference=reference, task_id=task_id, grading_pass=rec["grading_pass"])
    rec.update({"graded": True, "deliverables": [i["path"] for i in extraction["inventory"]], "rejected_files_not_delivered": rejected_files,
                "transfer_integrity": integrity, "originals_unchanged": extraction.get("originals_unchanged"), "working_copies": provenance, "extraction_status": checks.get("extraction_status"),
                "recalc": {k: v.get("recalc", {}).get("status") for k, v in extraction["xlsx"].items()},
                "recalc_comparison": {k: {kk: vv for kk, vv in v.get("recalc_comparison", {}).items() if kk != "details"} for k, v in extraction["xlsx"].items()},
                "score": score, "judge_units": len(units), "judge_verdicts": len(verdicts),
                "judge_call_summary": {"ok": sum(1 for v in verdicts if v.get("call_status") == "ok"), "provider_error": sum(1 for v in verdicts if v.get("error_class") == "provider_error"),
                                       "judge_parse_error": sum(1 for v in verdicts if v.get("error_class") == "judge_parse_error"), "not_attempted": sum(1 for v in verdicts if v.get("error_class") == "not_attempted"),
                                       "usage_uncertain": sum(1 for v in verdicts if v.get("usage_uncertain"))} if verdicts else None,
                "judge_completeness": judge_completeness(verdicts) if judge is not None else "none",
                "review_materials": review})
    return _append(out_dir, rec)


def _append(out_dir: str, rec: dict) -> dict:
    with open(os.path.join(out_dir, "results.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec
