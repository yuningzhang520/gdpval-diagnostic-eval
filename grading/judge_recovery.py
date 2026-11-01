"""Per-item judge infrastructure recovery (approved by the human 2026-11-01; engine-2026-11-01.7).

A judged pass whose batch was interrupted by the infrastructure (a provider failure, or calls never attempted after the
judge halted) can be completed item by item, never by re-judging the batch:
- eligible: only judge items whose call in the base pass ended ``provider_error`` (retried once) or ``not_attempted``
  (its first evaluation); an item with a completed call (any verdict, including the judge's own cannot_assess or a
  parse error) is never re-judged, so a recovery can never select a preferred verdict;
- bounded: one recovery attempt per (run, item), ever, across all recovery passes of the run;
- identical evidence: the base pass's stored judge units are sent unchanged (same frozen prompt, settings and
  evidence); the request hash is checked against the base call before any call;
- separate record: a new grading pass of kind ``judge_item_recovery`` copies every row of the base pass unchanged
  except the recovered items, records the base pass, and a recovery record (judge_recovery_<run>_<pass>.json) keeps
  each attempt with its request hash, status, usage and outcome; the base pass and its rows stay as they are;
- an item whose recovery fails again stays ``provider_error`` / ``not_run``, never fail and never an evidence-based
  cannot_assess.
Candidate-model attempts are untouched: this concerns the judge's calls only.

The paid path goes through grading.run_grading (--judge --judge-recover ITEMS --base-pass PASS): the judge gate, the
ledger binding, the history gate, the write-ahead log and the ledger settlement are those of every judged pass."""
import datetime as dt
import glob
import hashlib
import json
import os

from . import judge as J
from .grade import ENGINE_VERSION, TASK_MODULES, _append, code_provenance, grading_passes, judge_row_verdict, score_rows

RECOVERABLE = {"provider_error": "retry once (provider failure)", "not_attempted": "first evaluation (never attempted)"}
MAX_ATTEMPTS_PER_ITEM = 1


class RecoveryError(Exception):
    pass


def _rows(out_dir: str, run_uuid: str, grading_pass: str) -> list[dict]:
    with open(os.path.join(out_dir, "grades.jsonl"), encoding="utf-8") as f:
        return [r for r in (json.loads(l) for l in f if l.strip()) if r.get("run_uuid") == run_uuid and r.get("grading_pass") == grading_pass]


def _base_calls(out_dir: str, run_uuid: str, judge_unit: str) -> dict:
    for path in sorted(glob.glob(os.path.join(out_dir, f"judge_calls_{run_uuid}_*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        if d.get("unit_id") == judge_unit:
            return {c["item"]: c for c in d.get("calls", [])}
    raise RecoveryError(f"no judge call record of unit {judge_unit} in {out_dir}")


def prior_attempts(out_dir: str, run_uuid: str) -> dict:
    """{item: [recovery record path, ...]} of every earlier recovery attempt of this run that was sent to the provider
    (an attempt the judge did not send, after halting, does not count against the bound)."""
    out: dict = {}
    for path in sorted(glob.glob(os.path.join(out_dir, f"judge_recovery_{run_uuid}_*.json"))):
        for a in json.load(open(path, encoding="utf-8")).get("attempts", []):
            if a.get("status") != "not_attempted":
                out.setdefault(a["item"], []).append(path)
    return out


def expected_request_sha256(unit: dict) -> str:
    return hashlib.sha256((J.JUDGE_SYSTEM_PROMPT + "\n" + J.render_unit(unit)).encode("utf-8")).hexdigest()


def recovery_plan(out_dir: str, run_uuid: str, base_pass: str, items: list[int]) -> dict:
    """The base pass, its stored units and calls, and for each requested item whether it may be recovered (and why
    not). Raises when the base pass is not a judged pass of this run."""
    passes = {p.get("grading_pass"): p for p in grading_passes(out_dir, run_uuid)}
    base = passes.get(base_pass)
    if base is None or base.get("judge_mode") != "real" or not base.get("judge_unit"):
        raise RecoveryError(f"{base_pass} is not a judged pass of run {run_uuid} in {out_dir}")
    calls = _base_calls(out_dir, run_uuid, base["judge_unit"])
    units_path = os.path.join(out_dir, f"judge_units_{run_uuid}_{base_pass}.json")
    if not os.path.isfile(units_path):
        raise RecoveryError(f"stored judge units of {base_pass} missing: {units_path}")
    units = {u["item"]: u for u in json.load(open(units_path, encoding="utf-8"))["units"]}
    earlier = prior_attempts(out_dir, run_uuid)
    rows = {r["item"]: r for r in _rows(out_dir, run_uuid, base_pass)}
    decision = {}
    for i in items:
        call, row = calls.get(i), rows.get(i)
        status = (call or {}).get("status")
        if row is None or row.get("source") != "J" or i not in units:
            decision[i] = {"eligible": False, "reason": "not a judge item of the base pass"}
        elif status not in RECOVERABLE:
            decision[i] = {"eligible": False, "reason": f"base call status {status!r}: only {sorted(RECOVERABLE)} are recoverable (a completed call is never re-judged)"}
        elif len(earlier.get(i, [])) >= MAX_ATTEMPTS_PER_ITEM:
            decision[i] = {"eligible": False, "reason": f"already recovered once ({earlier[i]})"}
        elif call.get("request_sha256") and call["request_sha256"] != expected_request_sha256(units[i]):
            decision[i] = {"eligible": False, "reason": "the stored unit no longer renders the base request (evidence or prompt differs)"}
        else:
            decision[i] = {"eligible": True, "rule": RECOVERABLE[status], "base_call_status": status, "base_request_sha256": call.get("request_sha256")}
    return {"base": base, "units": units, "calls": calls, "decision": decision, "units_path": units_path}


def recovery_pass(out_dir: str, run_uuid: str, task_id: str, base_pass: str, items: list[int], judge) -> dict:
    """Judge the eligible items once on their stored units and record a judge_item_recovery pass (see the module)."""
    plan = recovery_plan(out_dir, run_uuid, base_pass, items)
    refused = {i: d["reason"] for i, d in plan["decision"].items() if not d["eligible"]}
    if refused or not items:
        raise RecoveryError(f"items not recoverable: {refused or 'none requested'}")
    base = plan["base"]
    mod = TASK_MODULES[task_id]
    # never-attempted items first: a retried provider failure that fails again halts the judge and must not take an
    # item's first evaluation with it
    order = sorted(items, key=lambda i: (plan["decision"][i]["base_call_status"] != "not_attempted", i))
    verdicts = {v["item"]: v for v in J.judge_units([plan["units"][i] for i in order], judge)}
    calls = {c["item"]: c for c in getattr(judge, "calls", [])}
    now = dt.datetime.now(dt.timezone.utc)
    gp = f"pass-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{os.urandom(2).hex()}"
    attempts, rows = {}, []
    for r in sorted(_rows(out_dir, run_uuid, base_pass), key=lambda x: x["item"]):
        row = {**r, "grading_pass": gp}
        if r["source"] == "J" and r.get("error_class") and r["item"] not in items:
            row["verdict"] = judge_row_verdict(r)  # engine .7 labels for an unrecovered infrastructure failure
        if r["item"] in items:
            v, c, d = verdicts.get(r["item"]), calls.get(r["item"], {}), plan["decision"][r["item"]]
            row.update({"verdict": judge_row_verdict(v), "evidence": (v or {}).get("evidence", []), "rationale": (v or {}).get("rationale", ""), "judge_id": (v or {}).get("judge_id"),
                        "parse_error": (v or {}).get("parse_error"), "error_class": (v or {}).get("error_class"), "call_status": (v or {}).get("call_status"),
                        "usage_status": (v or {}).get("usage_status"),
                        "recovery": {"base_pass": base_pass, "base_call_status": d["base_call_status"], "rule": d["rule"], "attempt": 1, "recovery_pass": gp,
                                     "engine_version": ENGINE_VERSION, "judge_unit": getattr(judge, "judge_unit", None)}})
            same = c.get("request_sha256") == d["base_request_sha256"] if d["base_request_sha256"] else None
            attempts[r["item"]] = ({"item": r["item"], "base_call_status": d["base_call_status"], "rule": d["rule"], "attempt": 1, "status": c.get("status"),
                             "request_sha256": c.get("request_sha256"), "same_request_as_base": same, "usage": c.get("usage"), "usage_status": c.get("usage_status"),
                             "error": c.get("error"), "outcome": row["verdict"]})
        rows.append(row)
    attempts = [attempts[i] for i in order if i in attempts]  # in the order the calls were sent
    with open(os.path.join(out_dir, "grades.jsonl"), "a", encoding="utf-8") as f:
        for g in rows:
            f.write(json.dumps(g, default=str) + "\n")
    extra = {}
    for c in ((base.get("score") or {}).get("critical") or {}).values():
        extra.update({k: {"verdict": v} for k, v in (c.get("extra_checks") or {}).items()})
    score = score_rows(rows, mod, extra or None)
    jrows = [g for g in rows if g["source"] == "J"]
    sealed = os.path.join(out_dir, "review", f"review_{run_uuid}_judge_verdicts_recovery_{gp}.json")
    os.makedirs(os.path.dirname(sealed), exist_ok=True)
    with open(sealed, "x", encoding="utf-8") as f:
        json.dump({"run_uuid": run_uuid, "grading_pass": gp, "note": "SEALED: recovered judge verdicts; open only after the independent judgments are saved",
                   "verdicts": [{k: verdicts[i].get(k) for k in ("item", "verdict", "evidence", "rationale", "error_class", "call_status")} for i in items if i in verdicts]}, f, indent=1, default=str)
    record = {"run_uuid": run_uuid, "task_id": task_id, "recovery_pass": gp, "base_pass": base_pass, "base_judge_unit": base.get("judge_unit"), "judge_unit": getattr(judge, "judge_unit", None),
              "engine_version": ENGINE_VERSION, "code": code_provenance(), "units_file": plan["units_path"], "attempts": attempts, "recorded_at": now.isoformat(timespec="seconds"),
              "policy": {"recoverable": RECOVERABLE, "max_attempts_per_item": MAX_ATTEMPTS_PER_ITEM}}
    with open(os.path.join(out_dir, f"judge_recovery_{run_uuid}_{gp}.json"), "x", encoding="utf-8") as f:
        json.dump(record, f, indent=1, default=str)
    previous = grading_passes(out_dir, run_uuid)
    keep = ("run", "task_id", "log_file", "gate", "collection_status", "execution_status", "limit_types", "limited", "outcome_class_stored", "outcome_class_effective", "grading_eligible",
            "attribution_class", "attribution_items", "adjudication_applied", "harness_error", "log_join", "deliverables", "rejected_files_not_delivered", "transfer_integrity",
            "originals_unchanged", "working_copies", "extraction_status", "recalc", "recalc_comparison", "judge_units", "judge_agreement_only", "task_grader_version")
    rec = {**{k: base.get(k) for k in keep}, "graded_at": now.isoformat(timespec="seconds"), "grader_version": base.get("grader_version"), "engine_version": ENGINE_VERSION,
           "base_engine_version": base.get("engine_version"), "code": code_provenance(), "grading_pass": gp, "pass_kind": "judge_item_recovery", "base_pass": base_pass,
           "supersedes_pass": previous[-1].get("grading_pass") if previous else None, "pass_index": len(previous) + 1, "graded": True, "judge_mode": "real",
           "judge_unit": getattr(judge, "judge_unit", None), "judge_units_combined": [base.get("judge_unit"), getattr(judge, "judge_unit", None)], "score": score,
           "judge_verdicts": sum(1 for g in jrows if g.get("call_status") == "ok"),
           "judge_call_summary": {"ok": sum(1 for g in jrows if g.get("call_status") == "ok"), "provider_error": sum(1 for g in jrows if g.get("error_class") == "provider_error"),
                                  "judge_parse_error": sum(1 for g in jrows if g.get("error_class") == "judge_parse_error"),
                                  "not_attempted": sum(1 for g in jrows if g.get("error_class") == "not_attempted"), "recovered_items": sorted(items)},
           "judge_completeness": "partial" if any(g.get("error_class") for g in jrows) else "complete",
           "recovery": {"items": sorted(items), "record": os.path.join(out_dir, f"judge_recovery_{run_uuid}_{gp}.json"), "outcomes": {a["item"]: a["outcome"] for a in attempts}},
           "review_materials": {**(base.get("review_materials") or {}), "judge_verdicts_recovery": sealed}}
    return _append(out_dir, rec)
