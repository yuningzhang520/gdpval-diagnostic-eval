"""Pilot A wiring U2 + U3 + B2-1 regression: the offline grading CLI on a REAL saved run produced by
harness.tests.regress_pilot_cli (real Inspect .eval, run directory with run_outcome.json and ledger_binding.json,
mockllm deliverable note.txt). No model, judge, provider or docker call: the run has no workbook, so no recalculation
happens; the judge is a fake generate or mockllm through the real inspect_ai model layer.
Scenarios: deterministic-only pass; judge gate refusals (scope, mock mode, wrong ledger, missing binding, open
reservation, hold); a crash after the third call -> UNKNOWN -> refused until reconciled; a missing-usage call ->
halt, not_attempted, estimated + hold -> refused until reconciled; an explicit --rejudge with a complete mockllm
pass; pass selection and single-pass statistics; immutability of earlier passes and settlements.
Usage: harness/tests/run_isolated.sh <root> grading.tests.regress_grading_cli --output-root <new dir> [--pilot-cli-root <existing fresh run>] [--stale-run <pilot-cli root whose run has no ledger_binding.json>]"""
import argparse
import json
import os
import shutil

from grading import checks_1137e2bb as CK
from grading import run_grading as RG
from grading.grade import GRADER_VERSION, grading_passes, select_pass, selected_grades
from grading.judge import ProviderJudge
from harness.budget import BudgetLedger
from harness.launcher import load_config, prices_from_config

CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pilot-cli-root", default=None, help="an existing fresh run from regress_pilot_cli; default: produce one now (docker, mockllm)"); ap.add_argument("--output-root", required=True); ap.add_argument("--stale-run", default=None); args = ap.parse_args()
    out = os.path.realpath(args.output_root); os.makedirs(out, exist_ok=False)
    if args.pilot_cli_root:
        manifest = json.load(open(os.path.join(args.pilot_cli_root, "pilot_cli_manifest.json")))
    else:  # the ledger is stateful: every regression run needs its own freshly produced, ledger-bound run
        from harness.tests.regress_pilot_cli import run_pilot_cli, CHECKS as PILOT_CHECKS
        manifest = run_pilot_cli(os.path.join(out, "pilot-cli"))
        check("fresh run produced through the real-run CLI path (Inspect + mockllm + docker) with every pilot-cli check passing", all(c["result"] == "PASS" for c in PILOT_CHECKS), [c["check"] for c in PILOT_CHECKS if c["result"] != "PASS"])
    run_dir, eval_log, task, ledger_path = manifest["run_dir"], manifest["eval_log"], manifest["task_id"], manifest["ledger"]
    uuid = os.path.basename(run_dir)
    cfg = load_config(os.path.join(os.environ["HARNESS_PROJECT_ROOT"], "config.json"))
    ledger = lambda: BudgetLedger.open_existing(ledger_path, prices_from_config(cfg))
    entries = lambda: [e["type"] for e in json.load(open(ledger_path))["entries"]]
    with open(os.path.join(out, "env.test"), "w", encoding="utf-8") as f:
        f.write("GOOGLE_API_KEY=dummy-test-key-not-real-0005\n")  # never the project .env; mockllm needs no key
    grading_out = os.path.join(out, "graded")
    base_argv = ["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", task, "--out-dir", grading_out, "--ledger", ledger_path, "--unit-id", manifest["unit_id"]]

    # ---------------------------------------------------------------- 1. deterministic-only pass (U2)
    rc = RG.main(base_argv)
    check("grading CLI returned 0 on the real saved run", rc == 0, rc)
    results = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
    grades = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))]
    r = results[-1]
    check("one results record, graded through the outcome gate (the collected note.txt makes the collection complete)", len(results) == 1 and r["gate"] == "passed" and r["graded"] is True and r["collection_status"] == "complete" and r["outcome_class_effective"] == "collected", {k: r.get(k) for k in ("gate", "graded", "collection_status", "outcome_class_effective")})
    check("run identity in results equals the saved run (uuid, sample id = task id); grader version is the code's", r["run"]["uuid"] == uuid and r["run"]["sample_id"] == task and r["grader_version"] == GRADER_VERSION and r["engine_version"] and r["task_grader_version"] and len(r["code"]["commit"] or "") == 40, (r["run"], r["grader_version"], r.get("code")))
    d_items, j_items = [g for g in grades if g["source"] == "D"], [g for g in grades if g["source"] == "J"]
    check("grades.jsonl holds every deterministic item and the 7 judge-only items", sorted(g["item"] for g in d_items) == CK.D_ITEMS and sorted(g["item"] for g in j_items) == CK.J_ITEMS, (len(d_items), len(j_items)))
    check("judge-only items are pending_judge, never pass/fail, with judge_mode none and completeness none", all(g["verdict"] == "pending_judge" for g in j_items) and r["judge_mode"] == "none" and r["judge_verdicts"] == 0 and r["judge_completeness"] == "none", {g["item"]: g["verdict"] for g in j_items})
    E_expected = sum(g["weight"] for g in d_items if g["verdict"] in ("pass", "fail"))
    check("E (graded denominator) excludes the pending judge items; W includes every item", r["score"]["E"] == E_expected and r["score"]["W"] == sum(g["weight"] for g in grades), (r["score"]["E"], E_expected, r["score"]["W"]))
    check("the mock deliverable (note.txt only) fails the workbook and docx presence items with model_caused_missing", {g["item"]: g["verdict"] for g in d_items if g["item"] in (1, 2)} == {1: "fail", 2: "fail"} and all(g["attribution"] == "model_caused_missing" for g in d_items if g["item"] in (1, 2)))
    check("C3 is not_confirmed (judge items pending), not pass", r["score"]["critical"]["C3"]["status"] in ("not_confirmed", "fail"), r["score"]["critical"]["C3"]["status"])
    prov1 = json.load(open(os.path.join(grading_out, sorted(f for f in os.listdir(grading_out) if f.startswith("grading_run_"))[0])))
    check("provenance record: run binding, eval log sha, code commit, config sha, material hashes, pending judge items, cost link", prov1["run"]["uuid"] == uuid and prov1["eval_log"]["sha256"] and prov1["code"]["commit"] and prov1["config"]["sha256"]
          and set(prov1["materials"]["sha256"]) == {"rubric", "reference", "prompt"} and prov1["judge_items_pending"] == CK.J_ITEMS and prov1["cost"]["generation"]["source"] == "launcher ledger settlement", {k: prov1.get(k) for k in ("judge_items_pending", "grader_version")})
    rm = r.get("review_materials") or {}
    check("human-review materials written (items markdown, independent template, judge file sealed separately)", all(os.path.exists(rm.get(k, "")) for k in ("items", "independent_template", "judge_verdicts")), rm)
    check("private materials were read from the host repository paths only", all(v.startswith(("private/", "data/")) for v in prov1["materials"]["paths"].values()), prov1["materials"]["paths"])

    def refused(argv, **kw):
        try:
            RG.main(argv, **kw); return None
        except RG.GradingCliError as ex:
            return str(ex)
        except SystemExit as ex:  # argparse error in the probe itself: report, never abort the regression silently
            return f"ARGPARSE_EXIT {ex.code}"
    msg = refused(["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", "b5d2e6f1-62a2-433a-bcdd-95b260cdd860", "--out-dir", os.path.join(out, "r1")]) or ""
    check("wrong --task-id is refused before grading (no grader registered for it yet, or the run's sample id is not that task)", msg.startswith(("no grader registered", "run.json sample_id")), msg)
    renamed = os.path.join(out, "renamed_run", "NOTTHEUUID"); shutil.copytree(run_dir, renamed)
    check("a run directory whose name differs from run.json is refused", "differs from the directory name" in (refused(["--host-dir", renamed, "--eval-log", eval_log, "--task-id", task, "--out-dir", os.path.join(out, "r2")]) or ""))
    other_log = next((os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(os.environ["HARNESS_PROJECT_ROOT"], "logs", "stage2_fix", "inspect")) for f in fs if f.endswith(".eval")), None)
    check("a log without the run's sample is refused", other_log is not None and "has no sample with uuid" in (refused(["--host-dir", run_dir, "--eval-log", other_log, "--task-id", task, "--out-dir", os.path.join(out, "r3")]) or ""), other_log)
    check("refusals wrote no grading outputs", not any(os.path.exists(os.path.join(out, d, "results.jsonl")) for d in ("r1", "r2", "r3")))

    # ---------------------------------------------------------------- 1b. execution-bound recovery on the REAL Inspect log of this run (Codex foreign_recovery)
    from harness.launcher import PilotLauncher
    launcher_probe = PilotLauncher(cfg, runs_root=os.path.join(out, "probe_runs"), ledger=ledger(), eval_fn=None)
    rec_own = launcher_probe.recover_usage_from_logs(manifest["unit_log_dir"], unit_id=manifest["unit_id"], task_name="formal_1137e2bb", model=manifest["model"])
    check("recovery from this execution's own log directory reads the real .eval once (mockllm usage, 1 event, 0 duplicates, attributable)", rec_own["recovered"] and rec_own["counted_events"] == 1 and rec_own["duplicate_events_skipped"] == 0 and rec_own["attribution_uncertain"] is False and rec_own["usage"][manifest["model"]]["input_tokens"] > 0, {k: rec_own.get(k) for k in ("recovered", "counted_events", "summary")})
    shutil.copyfile(manifest["eval_log"], os.path.join(manifest["unit_log_dir"], "duplicate-copy.eval"))
    rec_dup = launcher_probe.recover_usage_from_logs(manifest["unit_log_dir"], unit_id=manifest["unit_id"], task_name="formal_1137e2bb", model=manifest["model"])
    check("a duplicate representation of the same log counts once", rec_dup["counted_events"] == 1 and rec_dup["duplicate_events_skipped"] == 1 and rec_dup["usage"] == rec_own["usage"], {k: rec_dup.get(k) for k in ("counted_events", "duplicate_events_skipped")})
    os.remove(os.path.join(manifest["unit_log_dir"], "duplicate-copy.eval"))
    rec_other = launcher_probe.recover_usage_from_logs(manifest["unit_log_dir"], unit_id="SOME-OTHER-UNIT", task_name="another_task", model=manifest["model"])
    check("the same log is NOT attributed to a unit with a different task identity (uncertain, nothing counted)", rec_other["recovered"] is False and rec_other["attribution_uncertain"] is True and rec_other["counted_events"] == 0, rec_other["summary"])
    rec_none = launcher_probe.recover_usage_from_logs(os.path.join(out, "empty_unit_dir"), unit_id="x", task_name="formal_1137e2bb", model=manifest["model"])
    check("an empty execution directory recovers nothing and says so", rec_none["recovered"] is False and "nothing recovered" in rec_none["summary"])

    # ---------------------------------------------------------------- 2. judge gate (U3 + B2-1)
    from inspect_ai.model import ModelOutput, ModelUsage
    JUDGE = "mockllm/model"
    good = json.dumps({"verdict": "pass", "evidence": [{"file": "note.txt", "location": "line 1", "quote": "pilot cli mock deliverable"}], "rationale": "synthetic"})
    def with_usage(text, usage=True):
        o = ModelOutput.from_content(JUDGE, text); o.usage = ModelUsage(input_tokens=1200, output_tokens=80) if usage else None; return o
    judge_argv = base_argv + ["--judge", "--judge-model", JUDGE, "--judge-estimate-usd", "0.20", "--authorized-by", "mock-regression", "--authorization-ref", "grading/tests/regress_grading_cli.py", "--env-file", os.path.join(out, "env.test")]
    confirm = ["--confirm-judge", f"{uuid}|{JUDGE}|0.20"]
    mock_factory = lambda outputs: (lambda model, cfg: ProviderJudge(model, custom_outputs=list(outputs)))  # real get_model("mockllm/model") path
    complete_outputs = [with_usage(good) for _ in range(7)]
    n0 = len(entries())
    check("--judge without --confirm-judge is refused (judge model alone authorizes nothing)", "confirm-judge" in (refused(judge_argv, judge_factory=mock_factory(complete_outputs)) or ""))
    check("--judge with a wrong scope restatement is refused", "confirm-judge" in (refused(judge_argv + ["--confirm-judge", f"{uuid}|{JUDGE}|0.10"], judge_factory=mock_factory(complete_outputs)) or ""))
    real_argv = base_argv + ["--judge", "--judge-model", "google/gemini-test", "--judge-estimate-usd", "0.20", "--authorized-by", "x", "--authorization-ref", "y", "--env-file", os.path.join(out, "env.test"), "--confirm-judge", f"{uuid}|google/gemini-test|0.20"]
    check("a real provider judge is refused while the process is in mock mode (INSPECT_DISABLE_MODEL_API set)", "INSPECT_DISABLE_MODEL_API" in (refused(real_argv) or ""), refused(real_argv))
    other_ledger = os.path.join(out, "other_ledger.json"); shutil.copyfile(ledger_path, other_ledger)
    check("a ledger other than the run's bound ledger is refused (same content, different path)", "not the ledger this run is bound to" in (refused([a if a != ledger_path else other_ledger for a in judge_argv] + confirm, judge_factory=mock_factory(complete_outputs)) or ""))
    if args.stale_run:
        stale_log = json.load(open(os.path.join(os.path.dirname(os.path.dirname(args.stale_run)), "..", "pilot_cli_manifest.json")))["eval_log"] if False else None
    held = refused(judge_argv + confirm, judge_factory=mock_factory(complete_outputs))
    check("with the generation unit on manual-review hold (unpriced mock model), the judge pass is refused before any call", "manual-review hold" in (held or "") or "manual review" in (held or "").lower(), held)
    check("the refusals made no ledger entry and sent no judge call", len(entries()) == n0 and not os.path.isdir(os.path.join(os.path.dirname(ledger_path), "judge_logs")))
    lg = ledger()
    lg.resolve_manually(manifest["unit_id"], resolution="settled_amount", by="mock-regression", basis="synthetic: provider statement shows 0.0012", amount_usd="0.0012")
    eff = lg.effective_settlement(manifest["unit_id"])
    check("effective settlement of the generation unit reflects the manual amount (previous 1.00 -> 0.0012) with the original event kept", eff["effective"]["cost_usd"] == "0.001200" and eff["effective"]["previous_cost_usd"] == "1.000000" and [e["type"] for e in eff["events"]] == ["reservation", "settlement", "manual_resolution"], eff["effective"])
    lg.reserve("stale-other-unit", "sample", 1, {"model": "m", "task": "t"})  # a reservation left open by another process
    opened = refused(judge_argv + confirm, judge_factory=mock_factory(complete_outputs))
    check("an open reservation in the ledger refuses the judge pass (not a warning)", "open reservation" in (opened or ""), opened)
    lg.void("stale-other-unit", "synthetic: never started")
    n1 = len(entries())

    # ---------------------------------------------------------------- 3. crash after the third call -> UNKNOWN
    class Crash(BaseException):
        pass
    def crashing_factory(model, cfg):
        scripted = [with_usage(good), with_usage(good), Crash()]
        def generate(messages):
            nxt = scripted.pop(0)
            if isinstance(nxt, BaseException):
                raise nxt
            return nxt
        return ProviderJudge(model, generate=generate)
    try:
        RG.main(judge_argv + confirm, judge_factory=crashing_factory); crashed = False
    except Crash:
        crashed = True
    log_dir = os.path.join(os.path.dirname(ledger_path), "judge_logs", uuid)
    logs = sorted(os.listdir(log_dir)) if os.path.isdir(log_dir) else []
    ev = [json.loads(l) for l in open(os.path.join(log_dir, logs[0]))] if logs else []
    check("process-death stand-in after the third request: two complete call records and a third 'started' only, next to the ledger", crashed and len(logs) == 1 and [e["phase"] for e in ev] == ["started", "finished", "started", "finished", "started"], [e.get("phase") for e in ev])
    snap = lg.snapshot()
    unit_unknown = [u for u in snap["open_reservations"] if u.startswith(f"{uuid}:judge:")]
    check("the crashed judge unit's reservation stays open; no settlement, no results record for it", len(unit_unknown) == 1 and len(entries()) == n1 + 1 and len([json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]) == 1, (unit_unknown, entries()[n1:]))
    sel_blocked = RG.report_selection(cfg, run_dir, grading_out, uuid, ledger=lg)
    check("attempt-aware selection is BLOCKED while the latest judge attempt is UNKNOWN/open (no silent fallback to the deterministic-only pass)", sel_blocked["blocked"] is True and sel_blocked["pass"] is None and unit_unknown[0] in sel_blocked["basis"] and len(sel_blocked["history"]) == 1 and sel_blocked["attempts"][-1]["state"] in ("unknown", "open"), {k: sel_blocked.get(k) for k in ("blocked", "pass", "basis")})
    check("selected_grades returns no rows while blocked", selected_grades(grading_out, uuid, attempts=sel_blocked["attempts"])["grades"] == [])
    # Codex closure review (attempt_selection.actual_cli_without_ledger): the official CLI without --ledger must still be blocked
    cli_no_ledger_out = os.path.join(out, "graded_no_ledger"); shutil.copytree(grading_out, cli_no_ledger_out)
    rc_nl = RG.main(["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", task, "--out-dir", cli_no_ledger_out])
    prov_nl = json.load(open(os.path.join(cli_no_ledger_out, sorted(f for f in os.listdir(cli_no_ledger_out) if f.startswith("grading_run_"))[-1])))
    sel_nl = prov_nl["selected_pass_for_report"]
    check("official CLI without --ledger resolves the bound ledger itself and reports BLOCKED (not the old complete pass)", rc_nl == 0 and sel_nl["blocked"] is True and sel_nl["pass"] is None and sel_nl["authoritative"] is True and unit_unknown[0] in sel_nl["basis"], {k: sel_nl.get(k) for k in ("blocked", "pass", "authoritative", "basis")})
    auth = RG.authoritative_selection(cfg, run_dir, grading_out, uuid)
    check("authoritative statistics entry returns 0 rows while blocked", auth["blocked"] is True and auth["grades"] == [])
    blind = selected_grades(grading_out, uuid)
    check("the low-level statistics helper without attempt history fails closed (0 rows, not authoritative)", blind["blocked"] is True and blind["grades"] == [] and blind["authoritative"] is False)
    # binding missing / inconsistent -> fail closed
    no_binding = os.path.join(out, "no_binding_run", uuid); shutil.copytree(run_dir, no_binding); os.remove(os.path.join(no_binding, "ledger_binding.json"))
    sel_nb = RG.report_selection(cfg, no_binding, grading_out, uuid)
    check("a run without ledger_binding.json fails closed", sel_nb["blocked"] is True and "no ledger_binding.json" in sel_nb["basis"])
    bad_binding = os.path.join(out, "bad_binding_run", uuid); shutil.copytree(run_dir, bad_binding)
    bb = json.load(open(os.path.join(bad_binding, "ledger_binding.json"))); bb["ledger_path"] = os.path.join(out, "other_ledger.json"); json.dump(bb, open(os.path.join(bad_binding, "ledger_binding.json"), "w"))
    sel_bb = RG.report_selection(cfg, bad_binding, grading_out, uuid, ledger=lg)
    check("a supplied ledger that is not the run's bound ledger fails closed", sel_bb["blocked"] is True and "not the run's bound ledger" in sel_bb["basis"])
    # restart: a fresh CLI invocation must see the UNKNOWN and the open reservation
    again = refused(judge_argv + confirm, judge_factory=mock_factory(complete_outputs))
    check("after restart, --judge is refused: UNKNOWN call and open reservation of this run", "UNKNOWN" in (again or "") and "open reservation" in (again or ""), again)
    again2 = refused(judge_argv + confirm + ["--rejudge"], judge_factory=mock_factory(complete_outputs))
    check("--rejudge cannot bypass the UNKNOWN / open reservation", "not bypassable" in (again2 or ""), again2)
    lg.resolve_manually(unit_unknown[0], resolution="unresolvable", by="mock-regression", basis="synthetic: provider statement not yet available")
    again3 = refused(judge_argv + confirm + ["--rejudge"], judge_factory=mock_factory(complete_outputs))
    check("unresolvable keeps the refusal (open reservation remains)", "open reservation" in (again3 or ""), again3)
    lg.resolve_manually(unit_unknown[0], resolution="settled_amount", by="mock-regression", basis="synthetic: statement shows 0.0031 for three requests", amount_usd="0.0031")
    snap = lg.snapshot()
    check("verified-amount resolution closes the UNKNOWN unit at the stated amount; the UNKNOWN log is kept", not any(u.startswith(f"{uuid}:judge:") for u in snap["open_reservations"]) and unit_unknown[0] in snap["resolved_units"] and os.path.exists(os.path.join(log_dir, logs[0])), snap["resolved_units"])
    n2 = len(entries())

    # ---------------------------------------------------------------- 4. missing usage at call 3 -> halt, not_attempted, estimated + hold
    def missing_usage_factory(model, cfg):
        scripted = [with_usage(good), with_usage(good), with_usage(good, usage=False), with_usage(good), with_usage(good), with_usage(good), with_usage(good)]
        return ProviderJudge(model, generate=lambda messages: scripted.pop(0))
    if True:  # the reconciled UNKNOWN unit no longer blocks; a gate refusal here raises and fails the regression loudly
        results2 = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
        pre = len(results2)
        rc_m = RG.main(judge_argv + confirm + ["--rejudge"], judge_factory=missing_usage_factory)
        results2 = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
        rj = results2[-1]
        check("missing-usage pass returned 0 and recorded a judged pass", rc_m == 0 and len(results2) == pre + 1 and rj["judge_mode"] == "real", (rc_m, len(results2)))
        rows = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))]
        j = {x["item"]: x for x in rows if x["grading_pass"] == rj["grading_pass"] and x["source"] == "J"}
        classes = [(j[i]["call_status"], j[i]["error_class"], j[i]["usage_status"], j[i]["verdict"]) for i in CK.J_ITEMS]
        check("calls 1-2 ok, call 3 verdict kept with missing usage, calls 4-7 not_attempted (no fabricated verdict)",
              classes[:2] == [("ok", None, "ok", "pass")] * 2 and classes[2] == ("ok", None, "missing", "pass") and classes[3:] == [("not_attempted", "not_attempted", "not_attempted", "cannot_assess")] * 4, classes)
        check("judge_completeness partial; call summary separates the classes", rj["judge_completeness"] == "partial" and rj["judge_call_summary"] == {"ok": 3, "provider_error": 0, "judge_parse_error": 0, "not_attempted": 4, "usage_uncertain": 1}, (rj["judge_completeness"], rj["judge_call_summary"]))
        js = [e for e in json.load(open(ledger_path))["entries"] if e["type"] == "settlement" and e["unit_id"].startswith(f"{uuid}:judge:")]
        check("ledger: estimated + manual_review hold at the reservation (mock model unpriced), known usage kept in raw_usage, floor flagged", len(js) == 1 and js[0]["estimated"] is True and js[0]["manual_review_required"] is True and js[0]["cost_usd"] == "0.200000" and js[0]["raw_usage"]["mockllm/model"]["input_tokens"] == 2400 and "incomplete" in js[0]["note"] and any(f.startswith("hold:") for f in js[0]["flags"]) and any(f.startswith(("incomplete usage", "estimated_unknown_cost")) for f in js[0]["flags"]), {k: js[0].get(k) for k in ("cost_usd", "estimated", "manual_review_required")} if js else None)
        prov_m = json.load(open(os.path.join(grading_out, f"grading_run_{uuid}_{rj['grading_pass']}.json")))
        check("grading cost record reads the EFFECTIVE generation settlement (0.0012 after reconciliation, not the raw 1.00)", prov_m["cost"]["generation"]["cost_usd"] == "0.001200" and prov_m["cost"]["generation"]["resolution"]["amount_usd"] == "0.001200" and prov_m["cost"]["generation"]["source"] == "launcher ledger settlement", prov_m["cost"]["generation"])
        check("provenance: accounting_status manual_review_required, halted reason, rejudge_of the crashed unit, write-ahead log path", prov_m["cost"]["grading"]["accounting_status"] == "manual_review_required" and "no usage" in (prov_m["cost"]["grading"]["halted"] or "") and prov_m["cost"]["grading"]["rejudge_of"] == unit_unknown and prov_m["cost"]["grading"]["write_ahead_log"].startswith(log_dir), {k: prov_m["cost"]["grading"].get(k) for k in ("accounting_status", "halted", "rejudge_of")})
        held2 = refused(judge_argv + confirm + ["--rejudge"], judge_factory=mock_factory(complete_outputs))
        check("the hold refuses the next judge pass after a restart", "hold" in (held2 or "") or "manual review" in (held2 or "").lower(), held2)
        lg.resolve_manually(js[0]["unit_id"], resolution="settled_amount", by="mock-regression", basis="synthetic: statement shows 0.0045 for three requests", amount_usd="0.0045")
        # ------------------------------------------------------------ 4b. post-response failure: 7 responses done, then the review write fails (correction B)
        fail_out = os.path.join(out, "graded_fail"); os.makedirs(fail_out); open(os.path.join(fail_out, "review"), "w").close()  # review must be a directory -> grade_run raises after the judge calls
        fail_argv = [a if a != grading_out else fail_out for a in judge_argv] + confirm + ["--rejudge"]
        n3 = len(entries())
        try:
            RG.main(fail_argv, judge_factory=mock_factory(complete_outputs)); failed_after = False
        except Exception as ex:
            failed_after = type(ex).__name__ in ("FileExistsError", "NotADirectoryError", "OSError")
        js2 = [e for e in json.load(open(ledger_path))["entries"] if e["type"] == "settlement" and e["unit_id"].startswith(f"{uuid}:judge:")]
        wal = sorted(os.listdir(log_dir))
        last_wal = [json.loads(l) for l in open(os.path.join(log_dir, wal[-1]))]
        check("post-response failure: the 7 completed calls are on the write-ahead log and the recovered usage is in the single conservative settlement (estimated, held), not a bare reservation", failed_after and len(js2) == 2 and js2[-1]["estimated"] is True and js2[-1]["manual_review_required"] is True and "write-ahead log" in js2[-1]["note"] and '"input_tokens"' in js2[-1]["note"] and js2[-1]["note"].count("input_tokens") >= 1 and [e["phase"] for e in last_wal].count("finished") == 7 and entries()[n3:] == ["reservation", "engineering_failure", "settlement"], (failed_after, entries()[n3:], js2[-1].get("note", "")[:200] if len(js2) == 2 else None))
        sel_after_fail = RG.report_selection(cfg, run_dir, grading_out, uuid, ledger=lg)
        check("selection is blocked by the held attempt that produced no pass", sel_after_fail["blocked"] is True and sel_after_fail["attempts"][-1]["state"] == "held", sel_after_fail.get("attempts", [])[-1:])
        lg.resolve_manually(js2[-1]["unit_id"], resolution="settled_amount", by="mock-regression", basis="synthetic: statement shows 0.0100 for seven requests", amount_usd="0.0100")
        sel_rec = RG.report_selection(cfg, run_dir, grading_out, uuid, ledger=lg)
        check("after reconciliation the selection falls back to the latest recorded pass with an explicit warning", sel_rec["blocked"] is False and sel_rec["pass"] == rj["grading_pass"] and any("reconciled" in w for w in sel_rec["warnings"]), {k: sel_rec.get(k) for k in ("blocked", "pass", "warnings")})
        # ------------------------------------------------------------ 5. explicit rejudge: complete pass through the real mockllm model layer
        rc_c = RG.main(judge_argv + confirm + ["--rejudge"], judge_factory=mock_factory(complete_outputs))
        results3 = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
        rc3 = results3[-1]
        check("complete rejudge pass: 7 ok calls through get_model('mockllm/model'), completeness complete", rc_c == 0 and rc3["judge_completeness"] == "complete" and rc3["judge_call_summary"]["ok"] == 7 and rc3["judge_verdicts"] == 7, rc3.get("judge_call_summary"))
        sel = select_pass(grading_passes(grading_out, uuid))
        check("select_pass picks the latest (complete) judged pass with its basis; the partial pass stays recorded", sel["pass"]["grading_pass"] == rc3["grading_pass"] and "complete" in sel["basis"] and any("2 judged passes" in w for w in sel["warnings"]), sel)
        sel_partial = select_pass(grading_passes(grading_out, uuid)[:-1])
        check("with the partial pass latest, it is selected WITH a warning (an older complete pass never hides it)", sel_partial["pass"]["grading_pass"] == rj["grading_pass"] and any("partial" in w for w in sel_partial["warnings"]), sel_partial["warnings"])
        sg = RG.authoritative_selection(cfg, run_dir, grading_out, uuid)  # the statistics entry resolves the bound ledger itself
        check("statistics input is one pass (authoritative entry, attempt history verified): one row per rubric item for this run", sg["blocked"] is False and sg["authoritative"] is True and len(sg["grades"]) == len(CK.D_ITEMS) + len(CK.J_ITEMS) and {x["grading_pass"] for x in sg["grades"]} == {rc3["grading_pass"]}, {k: sg.get(k) for k in ("blocked", "authoritative", "basis")})
        rows3 = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))]
        d_by_pass = {}
        for x in rows3:
            if x["source"] == "D":
                d_by_pass.setdefault(x["grading_pass"], {})[x["item"]] = (x["verdict"], x.get("attribution"))
        check("deterministic verdicts and attributions identical across the three passes; earlier rows untouched", len(d_by_pass) == 3 and len({json.dumps(v, sort_keys=True) for v in d_by_pass.values()}) == 1 and rows3[:len(grades)] == grades)
        settles = [e for e in json.load(open(ledger_path))["entries"] if e["type"] == "settlement" and e["unit_id"].startswith(f"{uuid}:judge:")]
        res_ev = [e for e in json.load(open(ledger_path))["entries"] if e["type"] == "manual_resolution"]
        check("ledger history intact: distinct judge units, original estimated settlement unchanged, resolutions appended, last pass settled unpriced->hold again", len({e["unit_id"] for e in settles}) == 3 and settles[0]["cost_usd"] == "0.200000" and len(res_ev) == 5 and settles[-1]["manual_review_required"] is True, [(e["unit_id"][-15:], e["cost_usd"]) for e in settles])
        sel_final = RG.report_selection(cfg, run_dir, grading_out, uuid, ledger=lg)
        check("final attempt-aware selection: the complete pass is current, every attempt listed, none unfinished", sel_final["blocked"] is False and sel_final["pass"] == rc3["grading_pass"] and all(a["has_pass"] or a["state"] == "settled" for a in sel_final["attempts"]), [(a["unit_id"][-12:], a["state"], a["has_pass"]) for a in sel_final["attempts"]])
        rm3 = rc3["review_materials"]
        check("review: each judged pass has its own sealed judge file; the independent template is the same file, untouched", rm3["judge_verdicts"] != rj["review_materials"]["judge_verdicts"] and rm3["independent_template"] == r["review_materials"]["independent_template"] and os.path.exists(r["review_materials"]["judge_verdicts"]))
        check("the UNKNOWN record is still present in the run's judge logs after everything", os.path.exists(os.path.join(log_dir, logs[0])) and [json.loads(l) for l in open(os.path.join(log_dir, logs[0]))][-1]["phase"] == "started")
    # ---------------------------------------------------------------- 6. a run without a ledger binding is never judged
    if args.stale_run:
        stale_manifest = json.load(open(os.path.join(args.stale_run, "pilot_cli_manifest.json")))
        stale = refused(["--host-dir", stale_manifest["run_dir"], "--eval-log", stale_manifest["eval_log"], "--task-id", task, "--out-dir", os.path.join(out, "stale"), "--ledger", stale_manifest["ledger"], "--judge", "--judge-model", JUDGE,
                         "--judge-estimate-usd", "0.20", "--authorized-by", "x", "--authorization-ref", "y", "--env-file", os.path.join(out, "env.test"), "--confirm-judge", f"{os.path.basename(stale_manifest['run_dir'])}|{JUDGE}|0.20"], judge_factory=mock_factory(complete_outputs))
        check("a run recorded before ledger bindings existed is refused for judging (no binding is guessed or created)", "no ledger_binding.json" in (stale or ""), stale)
    leaked = [str(p) for p in __import__("pathlib").Path(out).rglob("*") if p.is_file() and p.name != "env.test" and "dummy-test-key-not-real" in p.read_text(errors="replace")]
    check("no synthetic key value in any produced file", leaked == [], leaked)
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": CHECKS, "input_manifest": manifest}, f, indent=1, default=str)
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== GRADING CLI {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {os.path.join(out, 'results.json')}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
