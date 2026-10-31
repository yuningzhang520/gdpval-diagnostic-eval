"""Pilot A wiring U2 + U3 regression: the offline grading CLI, then a judged pass with a mock judge, on a REAL saved run produced by
harness.tests.regress_pilot_cli (real Inspect .eval, real run directory with run_outcome.json, mockllm
deliverable note.txt). No model, judge, provider or docker call: the run has no workbook, so no
recalculation happens. Checks the identity binding, the judge-pending handling, the outputs and the
provenance/cost link, plus refusals on a wrong task id and a wrong run directory.
Usage: harness/tests/run_isolated.sh <root> grading.tests.regress_grading_cli --pilot-cli-root <dir with pilot_cli_manifest.json> --output-root <new dir>"""
import argparse
import json
import os
import shutil

from grading import run_grading as RG
from grading import checks_1137e2bb as CK

CHECKS = []


def check(name, ok, detail=None):
    CHECKS.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)[:400] if detail is not None else None})
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {str(detail)[:300]}" if detail is not None and not ok else ""))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--pilot-cli-root", required=True); ap.add_argument("--output-root", required=True); args = ap.parse_args()
    out = os.path.realpath(args.output_root); os.makedirs(out, exist_ok=False)
    manifest = json.load(open(os.path.join(args.pilot_cli_root, "pilot_cli_manifest.json")))
    run_dir, eval_log, task = manifest["run_dir"], manifest["eval_log"], manifest["task_id"]
    grading_out = os.path.join(out, "graded")
    with open(os.path.join(out, "env.test"), "w", encoding="utf-8") as f:
        f.write("GOOGLE_API_KEY=dummy-test-key-not-real-0005\n")  # never the project .env; mockllm needs no key
    rc = RG.main(["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", task, "--out-dir", grading_out, "--ledger", manifest["ledger"], "--unit-id", manifest["unit_id"]])
    check("grading CLI returned 0 on the real saved run", rc == 0, rc)
    results = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
    grades = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))] if os.path.exists(os.path.join(grading_out, "grades.jsonl")) else []
    r = results[-1]
    check("one results record, graded through the outcome gate (the collected note.txt makes the collection complete)", len(results) == 1 and r["gate"] == "passed" and r["graded"] is True and r["collection_status"] == "complete" and r["outcome_class_effective"] == "collected", {k: r.get(k) for k in ("gate", "graded", "collection_status", "outcome_class_effective")})
    check("run identity in results equals the saved run (uuid, sample id = task id)", r["run"]["uuid"] == os.path.basename(run_dir) and r["run"]["sample_id"] == task, r["run"])
    d_items, j_items = [g for g in grades if g["source"] == "D"], [g for g in grades if g["source"] == "J"]
    check("grades.jsonl holds every deterministic item and the 7 judge-only items", sorted(g["item"] for g in d_items) == CK.D_ITEMS and sorted(g["item"] for g in j_items) == CK.J_ITEMS, (len(d_items), len(j_items)))
    check("judge-only items are pending_judge, never pass/fail, with judge_mode none", all(g["verdict"] == "pending_judge" for g in j_items) and r["judge_mode"] == "none" and r["judge_verdicts"] == 0, {g["item"]: g["verdict"] for g in j_items})
    E_expected = sum(g["weight"] for g in d_items if g["verdict"] in ("pass", "fail"))
    check("E (graded denominator) excludes the pending judge items; W includes every item", r["score"]["E"] == E_expected and r["score"]["W"] == sum(g["weight"] for g in grades), (r["score"]["E"], E_expected, r["score"]["W"]))
    check("the mock deliverable (note.txt only) fails the workbook and docx presence items with model_caused_missing", {g["item"]: g["verdict"] for g in d_items if g["item"] in (1, 2)} == {1: "fail", 2: "fail"} and all(g["attribution"] == "model_caused_missing" for g in d_items if g["item"] in (1, 2)), {g["item"]: (g["verdict"], g.get("attribution")) for g in d_items if g["item"] in (1, 2)})
    check("C3 is not_confirmed (judge items pending), not pass", r["score"]["critical"]["C3"]["status"] in ("not_confirmed", "fail"), r["score"]["critical"]["C3"]["status"])
    prov_files = sorted(f for f in os.listdir(grading_out) if f.startswith("grading_run_"))
    prov = json.load(open(os.path.join(grading_out, prov_files[0]))) if prov_files else {}
    check("provenance record: run binding, eval log sha, code commit, config sha, material hashes, pending judge items, cost link", bool(prov) and prov["run"]["uuid"] == os.path.basename(run_dir) and prov["eval_log"]["sha256"] and prov["code"]["commit"] and prov["config"]["sha256"]
          and set(prov["materials"]["sha256"]) == {"rubric", "reference", "prompt"} and prov["judge_items_pending"] == CK.J_ITEMS and prov["cost"]["generation"]["source"] == "launcher ledger settlement" and prov["cost"]["generation"]["cost_usd"],
          {k: prov.get(k) for k in ("judge_items_pending", "grader_version")} | {"cost": (prov.get("cost") or {}).get("generation", {}).get("cost_usd")})
    rm = r.get("review_materials") or {}
    check("human-review materials written (items markdown, independent template, judge file sealed separately)", all(os.path.exists(rm.get(k, "")) for k in ("items", "independent_template", "judge_verdicts")), rm)
    check("private materials were read from the host repository paths only", all(v.startswith(("private/", "data/")) for v in prov["materials"]["paths"].values()), prov["materials"]["paths"])
    # refusals: wrong task id; a copied run directory under another name; a log that does not hold the sample
    def refused(argv):
        try:
            RG.main(argv); return None
        except RG.GradingCliError as ex:
            return str(ex)
    check("wrong --task-id is refused before grading", (refused(["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", "b5d2e6f1-62a2-433a-bcdd-95b260cdd860", "--out-dir", os.path.join(out, "r1")]) or "").startswith("run.json sample_id"))
    renamed = os.path.join(out, "renamed_run", "NOTTHEUUID"); shutil.copytree(run_dir, renamed)
    check("a run directory whose name differs from run.json is refused", "differs from the directory name" in (refused(["--host-dir", renamed, "--eval-log", eval_log, "--task-id", task, "--out-dir", os.path.join(out, "r2")]) or ""))
    other_log = next((os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(os.environ["HARNESS_PROJECT_ROOT"], "logs", "stage2_fix", "inspect")) for f in fs if f.endswith(".eval")), None)
    check("a log without the run's sample is refused", other_log is not None and "has no sample with uuid" in (refused(["--host-dir", run_dir, "--eval-log", other_log, "--task-id", task, "--out-dir", os.path.join(out, "r3")]) or ""), other_log)
    check("refusals wrote no grading outputs", not any(os.path.exists(os.path.join(out, d, "results.jsonl")) for d in ("r1", "r2", "r3")))
    # ---------------------------------------------------------------- U3: judged pass through the same CLI with a mock judge (real Inspect get_model/generate on mockllm)
    from inspect_ai.model import ModelOutput, ModelUsage
    from grading.judge import ProviderJudge
    JUDGE = "mockllm/model"
    good = json.dumps({"verdict": "pass", "evidence": [{"file": "note.txt", "location": "line 1", "quote": "pilot cli mock deliverable"}], "rationale": "synthetic"})
    def with_usage(text, usage=True):
        o = ModelOutput.from_content(JUDGE, text)
        o.usage = ModelUsage(input_tokens=1200, output_tokens=80) if usage else None
        return o
    # Through the real get_model("mockllm/model") path Inspect attaches mockllm's own token usage to every response (preset
    # usage on the custom outputs is not kept), so the missing-usage and provider-error branches are covered by the unit tests
    # with an injected generate (JudgeAdapterTests); here every call carries usage and the ledger has no price for mockllm.
    outputs = [with_usage(good), with_usage(good), with_usage("Not a JSON answer."), with_usage(good), with_usage(good, usage=False), with_usage(good), with_usage(good)]
    factory = lambda model, cfg: ProviderJudge(model, custom_outputs=list(outputs))  # the real get_model("mockllm/model", custom_outputs=...) path
    d_rows_before = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))]
    # the generation unit of this mock run was settled unpriced (mockllm) -> manual-review hold on the ledger; work on a copy
    from harness.budget import BudgetLedger
    from harness.launcher import load_config, prices_from_config
    cfg = load_config(os.path.join(os.environ["HARNESS_PROJECT_ROOT"], "config.json"))
    ledger_copy = os.path.join(out, "ledger.json"); shutil.copyfile(manifest["ledger"], ledger_copy)
    judge_argv = ["--host-dir", run_dir, "--eval-log", eval_log, "--task-id", task, "--out-dir", grading_out, "--ledger", ledger_copy, "--unit-id", manifest["unit_id"],
                  "--judge", "--judge-model", JUDGE, "--judge-estimate-usd", "0.20", "--authorized-by", "mock-regression", "--authorization-ref", "grading/tests/regress_grading_cli.py", "--env-file", os.path.join(out, "env.test")]
    ledger_entries = lambda: [e["type"] for e in json.load(open(ledger_copy))["entries"]]
    n_entries = len(ledger_entries())
    def refused_judge(extra, factory=factory, environ=None):
        try:
            RG.main(judge_argv + extra, judge_factory=factory, environ=environ); return None
        except RG.GradingCliError as ex:
            return str(ex)
    check("--judge without --confirm-judge is refused (judge model alone authorizes nothing)", "confirm-judge" in (refused_judge([]) or ""))
    check("--judge with a wrong scope restatement is refused", "confirm-judge" in (refused_judge(["--confirm-judge", f"{os.path.basename(run_dir)}|{JUDGE}|0.10"]) or ""))
    check("a real provider judge is refused while the process is in mock mode (INSPECT_DISABLE_MODEL_API set)", "INSPECT_DISABLE_MODEL_API" in (refused_judge(["--confirm-judge", f"{os.path.basename(run_dir)}|google/gemini-test|0.20", "--judge-model", "google/gemini-test"], factory=None) or ""))
    check("refusals made no ledger entry and called no judge", len(ledger_entries()) == n_entries and not any(f.startswith("judge_calls_") for f in os.listdir(grading_out)))
    confirm = ["--confirm-judge", f"{os.path.basename(run_dir)}|{JUDGE}|0.20"]
    held = refused_judge(confirm)
    check("with the generation unit on manual-review hold, the judge pass is refused by the ledger before any call", "refused by the budget ledger" in (held or "") and "manual" in (held or "").lower(), held)
    check("the held refusal made no reservation and no judge call", len(ledger_entries()) == n_entries and not any(f.startswith("judge_calls_") for f in os.listdir(grading_out)))
    BudgetLedger(ledger_copy, cfg["pilot"]["budget_ceiling_usd"], prices_from_config(cfg)).clear_review(manifest["unit_id"], by="mock-regression", basis="synthetic: unpriced mock model settlement reviewed")
    n_entries = len(ledger_entries())
    rc_j = RG.main(judge_argv + confirm, judge_factory=factory)
    check("judged pass returned 0 through the real CLI path", rc_j == 0, rc_j)
    results2 = [json.loads(l) for l in open(os.path.join(grading_out, "results.jsonl"))]
    rj = results2[-1]
    check("two passes for one run: deterministic_only then deterministic_plus_judge, linked by supersedes_pass, same run uuid",
          len(results2) == 2 and [x["pass_kind"] for x in results2] == ["deterministic_only", "deterministic_plus_judge"] and rj["supersedes_pass"] == results2[0]["grading_pass"] and rj["run"]["uuid"] == results2[0]["run"]["uuid"],
          [(x.get("pass_kind"), x.get("grading_pass")) for x in results2])
    rows2 = [json.loads(l) for l in open(os.path.join(grading_out, "grades.jsonl"))]
    d_pass1 = {x["item"]: x["verdict"] for x in d_rows_before if x["source"] == "D"}
    d_pass2 = {x["item"]: x["verdict"] for x in rows2 if x["grading_pass"] == rj["grading_pass"] and x["source"] == "D"}
    check("deterministic verdicts identical across passes; pass-1 rows untouched", d_pass1 == d_pass2 and rows2[:len(d_rows_before)] == d_rows_before)
    j = {x["item"]: x for x in rows2 if x["grading_pass"] == rj["grading_pass"] and x["source"] == "J"}
    check("all 7 judge-only criteria reached the mock adapter through the CLI", sorted(j) == CK.J_ITEMS and all(x["call_status"] == "ok" for x in j.values()), {k: v["call_status"] for k, v in j.items()})
    classes = sorted((x["verdict"], x["error_class"], x["usage_status"]) for x in j.values())
    check("verdicts: 6 pass, 1 cannot_assess (judge_parse_error); nothing scored pass/fail from a non-protocol answer; usage present on every call",
          classes.count(("pass", None, "ok")) == 6 and classes.count(("cannot_assess", "judge_parse_error", "ok")) == 1, classes)
    check("results record: judge_mode real, 7 verdicts, call summary", rj["judge_mode"] == "real" and rj["judge_verdicts"] == 7 and rj["judge_call_summary"] == {"ok": 7, "provider_error": 0, "judge_parse_error": 1, "usage_uncertain": 0}, rj.get("judge_call_summary"))
    calls_files = sorted(f for f in os.listdir(grading_out) if f.startswith("judge_calls_"))
    calls = json.load(open(os.path.join(grading_out, calls_files[0]))) if calls_files else {}
    check("judge call log: 7 calls with unit id, request hash, raw response, usage and status; mockllm usage accumulated", len(calls_files) == 1 and len(calls.get("calls", [])) == 7 and all(c["request_sha256"] and c["unit_id"] and c["status"] and c["raw_response"] and c["usage"] for c in calls["calls"]) and calls["batch"]["usage_incomplete"] is False and calls["batch"]["usage"]["mockllm/model"]["input_tokens"] > 0, calls.get("batch"))
    entries = json.load(open(ledger_copy))["entries"]
    judge_settle = [e for e in entries if e["type"] == "settlement" and ":judge:" in e["unit_id"]]
    check("ledger: one judge reservation and one settlement; mockllm has no price -> settled at max(priced part, reservation), estimated, manual review hold (never zero)",
          [e["type"] for e in entries[n_entries:]] == ["reservation", "settlement"] and len(judge_settle) == 1 and judge_settle[0]["estimated"] is True and judge_settle[0]["manual_review_required"] is True and judge_settle[0]["cost_usd"] == "0.200000" and any("estimated_unknown_cost" in f for f in judge_settle[0]["flags"]) and judge_settle[0]["raw_usage"]["mockllm/model"]["input_tokens"] > 0,
          {k: judge_settle[0].get(k) for k in ("cost_usd", "estimated", "manual_review_required", "flags")} if judge_settle else entries[n_entries:])
    rm2 = rj["review_materials"]
    check("review: judge verdicts sealed in a new versioned file; pass-1 judge file and the independent template untouched", rm2["judge_verdicts"] != r["review_materials"]["judge_verdicts"] and os.path.exists(r["review_materials"]["judge_verdicts"]) and rm2["independent_template"] == r["review_materials"]["independent_template"], (rm2["judge_verdicts"], r["review_materials"]["judge_verdicts"]))
    prov2 = sorted(f for f in os.listdir(grading_out) if f.startswith("grading_run_"))
    pj = json.load(open(os.path.join(grading_out, prov2[-1])))
    check("provenance: selected pass for the report is the judged pass; judge authorization, unit and cost recorded", pj["selected_pass_for_report"] == rj["grading_pass"] and pj["judge"]["authorization"]["by"] == "mock-regression" and pj["cost"]["grading"]["source"] == "judge ledger settlement" and pj["cost"]["grading"]["usage_incomplete"] is False and pj["cost"]["grading"]["manual_review_required"] is True, {k: pj.get(k) for k in ("selected_pass_for_report", "pass_kind")})
    n2 = len(ledger_entries())
    check("a second --judge without --rejudge is refused and makes no ledger entry (no silent double billing)", "already exists" in (refused_judge(confirm) or "") and len(ledger_entries()) == n2)
    check("the first pass (deterministic only) is still selectable by pass id", any(x["grading_pass"] == results2[0]["grading_pass"] for x in results2) and results2[0]["judge_mode"] == "none")
    with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
        json.dump({"checks": CHECKS, "input_manifest": manifest, "results_record": r, "judged_record": rj, "provenance_file": prov_files}, f, indent=1, default=str)
    failed = [c for c in CHECKS if c["result"] != "PASS"]
    print(f"\n==== GRADING CLI {len(CHECKS) - len(failed)} PASS, {len(failed)} FAIL; results {os.path.join(out, 'results.json')}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
