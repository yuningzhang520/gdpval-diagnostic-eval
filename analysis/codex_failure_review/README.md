# Codex failure review (AI-generated draft second opinion)

**What this is.** An AI-generated draft second opinion by OpenAI Codex, produced as a static, read-only
review of the failure-analysis bundle (`~/turing-eval-runs/analysis/failures-v1/`: the frozen item
verdicts, the deliverables, the task inputs, the public rubrics and the frozen grader code at
`freeze-v1-grading`). No grader was executed, no model or judge was called, and no label, verdict or
deliverable was modified. The classes and root-cause IDs in `analysis.md` and `diagnosis.csv` are
**draft classifications, not human adjudication**; the frozen item-level scores of the preregistered
evaluation are unchanged by them.

**Human-verified subset.** The human-verified items are recorded in the adjudication files
(`~/turing-eval-runs/formal/human_review/adjudication_*.jsonl`, summarised in
`formal/human_layers_summary.json` and in `report/REPORT.md` section 7.3); the human-verification
worksheet built from this review is `~/turing-eval-runs/analysis/critical_adjudication.md` / `.csv`.
A Codex class is never a verdict: a `grader_false_fail` row stays a FAIL in the frozen scores until the
human adjudicates it, and a `model_error` row is a lead to verify, not a confirmed model failure.

**Coverage.** The review covers 239 of the 265 non-pass items (`failures.csv` rows) of the two formal
candidates. The other 26 are 24 pending non-critical visual items (human review, not an automated
verdict) and 2 `invalid_judge_output` items (judge infrastructure, never a FAIL).

**Files.**
- `analysis.md`: the draft root-cause taxonomy (model-error clusters M1-M6, grader defects D01-D24,
  grouped `cannot_assess` diagnoses R01-R09) and the adjudication boundaries it declines to decide.
- `diagnosis.csv`: one row per reviewed item (`candidate|task_id|item_id`), with criterion id, critical
  flag, layer, draft class, evidence and the reviewer's confidence in its own classification.

Paths in both files are relative to the bundle root (`failures-v1/`). The bundle itself is not part of
this repository (it contains the deliverables and the private rubric copies); the two review files are
kept here verbatim apart from that path rewrite.
