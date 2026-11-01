# Codex Review 2 — review package (prepared 2026-11-01)

This package lists commits, files, changes and test records. It makes no claim that any of them is correct: every
statement below is to be checked against the code.

## 1. Pin and setup (read-only)

- Code under review: commit `5121e1a9d1897392f9a4a4f7526564b6975e0f7b`, tag `v1.2-judge-infrastructure` (local).
  The earlier tags `v1-calibration-freeze` (`0c8efcb25c6a3b27100561af07ce04a688aa5a98`) and `v1.1-judge-item-recovery`
  (`57e2a25ed4f8166f92e85d21f43148ffb500c7a6`) are part of the history under review, not the pin.
- Diff baseline: commit `a9a1f88293264d653e4f0ded024eeeedcf1f4636`, the pin of the Codex Review 1 B2 closure
  (`docs/codex_review_1_b2_closure_2.md`).
- This file was committed after the pin. Before anything else, run:
  `git -C /Users/yuning/turing-th diff --name-only 5121e1a HEAD -- grading harness config.json`
  If it prints anything, stop and report it: the code under review is no longer the code in the working tree.
- Working tree: `/Users/yuning/turing-th`. Gold deliverables and rubrics live in the untracked `private/` and the tests
  need them, so the review runs in that working tree and does not use an export. Do not modify, add, stage or commit
  anything there. Write any output only under a scratch directory of your own, for example `/tmp/codex-r2/`.
- Do not read `plan/`, `.env` or any credential. Do not run `grading.judge_dev run|pass2`,
  `grading.judge_validation run|recover`, `harness.launcher`, `harness.scheduler` or any command that calls a model
  provider. Network access is not needed.
- Validation blind review is in progress. Do not open, print or quote anything under
  `~/turing-eval-runs/validation/grading/`, `~/turing-eval-runs/labeling/validation-v4/` or `~/turing-eval-runs/qa/`.
  Cost and coverage registries without verdicts may be read: `~/turing-eval-runs/judge_validation/registry.jsonl` and
  `ledger.json`. Gold deliverables, rubrics and recalculation references under `private/` may be read.
- Codex CLI, read-only, from the working tree. For example:
  `codex --cd /Users/yuning/turing-th --sandbox read-only --ask-for-approval never`
  (confirm the flags with `codex --help`). In a read-only sandbox, tests that create temporary files may be refused.
  Then verify the code and the recorded logs listed in section 2E, and list the tests you could not run.
- Harness tests must run through `harness/tests/run_isolated.sh /Users/yuning/turing-th <module>`, because the
  collector refuses symlinked temporary paths such as macOS `/var`. Grading tests run with
  `.venv/bin/python -m unittest <module>` from the working tree root.

## 2. What changed between `a9a1f88` and `5121e1a`

60 commits. `git diff --stat a9a1f88 5121e1a -- grading harness config.json` reports 103 files. Subsections A-F cover
the range up to `0c8efcb` (V1); G covers V1.1 (`0c8efcb..57e2a25`); H covers V1.2 (`57e2a25..5121e1a`).

### A. Shared grading engine (`grading/grade.py`, `grading/extract.py`, `grading/run_grading.py`)

| Engine version | Change | Commit | Code |
|---|---|---|---|
| `engine-2026-11-01.1` | at the baseline | `a9a1f88` | |
| `.2` | a deterministic item may route itself to the judge (`route_to_judge`) and is scored once, as a J row | `7f3594c` | `grade.py` |
| `.3` | critical status is also computed under the preregistered definition when a task revised it (`critical_preregistered`, sensitivity reporting) | `a8eb078` | `grade.py` |
| `.4` | recalculated values are joined to sheets whose names LibreOffice truncated at 31 characters | `e80f775` | `extract.map_recalc_sheet_names`, `extract.recalculate_xlsx` |
| `.5` | the xlsx package record lists embedded media parts (`xl/media/`) | `29fdaaa` | `extract.py` |
| `.6` | each docx table records the body paragraph it follows (`table_after_paragraph`; `None` when the counts disagree) | `e2208d3` | `extract.extract_docx` |

Other shared changes:
- `grading/run_grading.py`, commits `f9d8858` and `0aa4047`:
  - a separate judge cost ledger (`--judge-ledger`, `judge_ledger_binding.json`, `declare_judge_ledger`,
    `combined_judge_history`);
  - `judge_history_gate(..., reservation_ledger=...)` checks the judge ledger's open reservations.
- `config.json` `grading.engine_version` and `grading.task_grader_versions` must equal the code (`grade.ENGINE_VERSION`,
  each `checks_<task>.VERSION`). `run_grading` refuses otherwise, and `harness/tests/test_docs_consistency.py` checks it.

### B. Judge: routing, evidence builders, shared prompt and model freeze

- `grading/judge.py`:
  - `JUDGE_SYSTEM_PROMPT`, SHA-256 `1de955e607e16bd8d236469603bde099b3d309a885be170c21d7e759c57487b5`;
  - `ProviderJudge`, with a per-call `cost_guard`, a write-ahead call log and `batch_result()`;
  - `build_units_<task>` for the ten tasks.
- Builder version: `grade.py` sets each unit's `evidence_builder` to `grading.judge.build_units_<task>@<task VERSION>`.
- Builders changed after Dev calibration:
  - `build_units_2ea2e5b5`: it now lists each slide's title placeholder (or "none"), its text shapes top to bottom
    with their vertical position, native charts and pictures (commit `e2208d3`);
  - `_excerpt_named_docx`, used by `a45bc83b…`: tables now appear after the paragraph they follow when
    `table_after_paragraph` is present (commit `e2208d3`).
- Judge cost accounting (`0c8efcb`):
  - `ProviderJudge.batch_result()` returns `calls_by_model`;
  - `harness/launcher.PilotLauncher.run_judge_batch` passes it to `BudgetLedger.settle` with
    `scope={"same_sample": True}`, so each call is tiered by its own prompt size.
- Judge Dev (calibration on development outputs only), `grading/judge_dev.py`:
  - Pass 1: plan `grading/judge_dev/pass1_plan.json`, addenda `grading/judge_dev/pass1_addenda/`, 20 frozen
    self-consistency repeats;
  - Pass 2: plan `grading/judge_dev/pass2_plan.json` (`run_pass2`, `pass_spent`, the `extra_cap` guard);
  - guards: `make_guard` (Dev key suffix, long-context worst case per call, Pass 1 and aggregate ceilings).
- Freeze:
  - `grading/freeze_manifest.py` (`build`, `verify`) and `grading/freeze/v1_manifest.json`;
  - the `config.json` `judge` block (`status` FROZEN, `validation`);
  - tag `v1-calibration-freeze`.
- Judge Validation, `grading/judge_validation.py`:
  - the plan is `grading/judge_validation/plan.json`;
  - `frozen_state` runs `git diff` against the tag for `grading`, `harness` and `config.json`, checks for uncommitted
    changes, and runs `freeze_manifest.verify`;
  - other functions: `make_guard`, `grade_run`, `run`.

### C. Task graders, V0 to V1, and original against revised critical definitions

| Task | V0 tag (commit, version) | V1 version at the pin | Task-module commits since `a9a1f88` | Rules (preregistration) |
|---|---|---|---|---|
| `1137e2bb…` | `grader-v0-1137e2bb` (3847219, .2) | .3 | 8e6ad63 | 2.4 "Dev calibration .3" |
| `2ea2e5b5…` | `grader-v0-2ea2e5b5` (a8eb078, .2) | .3 | a8eb078 e2208d3 | 2.8 "Dev calibration .3", R-2.8-1 |
| `47ef842d…` | `grader-v0-47ef842d` (25e9e38, .1) | .2 | 25e9e38 29fdaaa | 2.3 "Dev calibration .2" |
| `7b08cd4d…` | `grader-v0-7b08cd4d` (393a7bc, .1) | .3 | 393a7bc 1bf9170 4f71d3d | 2.6 "Dev calibration .3" |
| `7d7fc9a7…` | `grader-v0-7d7fc9a7` (1b92af8, .5) | .7 | 1b92af8 e80f775 e2208d3 | 2.7 "Dev calibration .6", R-2.7-11, R-2.7-21 |
| `a45bc83b…` | `grader-v0-a45bc83b` (ff86cb3, .1) | .3 | e2208d3 | 2.10 "Dev calibration .3" |
| `b5d2e6f1…` | `grader-v0-b5d2e6f1` (7f3594c, .2) | .2 | 48fd3fc 7f3594c | 2.1 |
| `c3525d4d…` | `grader-v0-c3525d4d` (7f3594c, .2) | .5 | 5435534 7f3594c 1bf9170 b87972b e2208d3 | 2.5 "Dev calibration .4", R-2.5-27 |
| `c357f0e2…` | `grader-v0-c357f0e2` (7f3594c, .2) | .3 | 24d2eea 7f3594c 146ce2a | 2.9 "Dev calibration .3" |
| `f841ddcf…` | `grader-v0-f841ddcf` (b3c0ab2, .1) | .2 | b3c0ab2 e2208d3 | 2.2 "Dev calibration .2" |

- Six of the ten graders (`b5d2e6f1…`, `f841ddcf…`, `47ef842d…`, `c3525d4d…`, `7b08cd4d…`, `c357f0e2…`) did not exist
  at `a9a1f88`; their gold-first V0 is in range.
- Each module defines `CRITICAL`. A module whose task revised a critical composition also defines
  `CRITICAL_PREREGISTERED`, and `grade.py` scores both (`critical`, `critical_preregistered`). At the pin, only
  `checks_2ea2e5b5.py` does: C2 without item 10 (R-2.8-1, preregistration 1.18 and 2.8).
- Rubric decisions the human made on 2026-11-01 and the code that implements them:
  - R-2.7-11, `checks_7d7fc9a7.rounding_order_only` and `_round_cents`: a one-cent item-11 difference is accepted only
    on path A or path B;
  - R-2.7-21, `checks_7d7fc9a7.additions_absent` and `ADDS_ROW`: the per-line additions identity (21, 39) and
    balance increases (50); bottom-summary additions rows (27, 47);
  - R-2.5-27, `checks_c3525d4d.candidates` and `over_candidates`: items 26-30 and 49.

### D. Provenance, first-pass preservation, label checkpoints

- Each grading pass writes:
  - `grading_run_<run>_<pass>.json` (host dir, eval log, code commit, config and materials hashes, pass kind,
    supersedes, judge unit, cost);
  - `results.jsonl` and `grades.jsonl`, appended per pass.
  - Selection: `run_grading.report_selection` and `authoritative_selection`.
- Recalculation references: `private/checks/recalc/<task>.json`, built by `scripts/recalc/*.py`
  (`scripts/recalc/run_all.py`).
- V0 and V1 on development outputs:
  - V0 passes are in `~/turing-eval-runs/dev/grading/<run>/`.
  - V1 re-grades are in `~/turing-eval-runs/dev/grading_v1/<run>/`: six tasks at engine .5, recorded in
    `docs/status.md`; `c357f0e2…` and `2ea2e5b5…` later, with the latter's Judge Dev Pass 2 at engine .6.
- Label checkpoints, `grading/review.py`:
  - `save_label_checkpoint` writes a copy, its SHA-256, the timestamp and counts, and appends to
    `labels/checkpoints.jsonl`;
  - `compare_labels` refuses without a checkpoint and when the copy's SHA-256 differs.
  - The v4 Dev checkpoints, with their hashes, are listed in `docs/status.md` (2026-11-01 entry).
  - The `compare` CLI reads the host dir from the run's `grading_run_*.json` (`e2208d3`).
- Review queue:
  - `grading/review_queue.py` (v4: `build_plans_v4`, `freeze_v4`, `verify_v4`, `_rng4`);
  - `grading/review_queue/queue_v4.json`;
  - verdict-free packets via `grading/label_batch.assemble_v2`.

### E. Regression evidence and test records

Gold-first evidence per task:
- the catalog builder `grading/gold_variants_<task>.py`;
- code-bound records under `grading/validation/<task>/code_<commit>/` (catalogs and observed transitions) and
  `gold_first_pass.json`.

| Date (2026-11-01, UTC) | Command | Result | Wall time | Log |
|---|---|---|---|---|
| before `e2208d3` | `.venv/bin/python -m unittest discover -s grading/tests -p "test_*.py" -t .` | 421 tests, 5 skipped, OK | 117.34 s | `logs/v1-labelled-20261101/grading_tests.log` |
| before `e2208d3` | `run_isolated.sh` for each `harness/tests/test_*.py` | 14 modules, 199 tests, OK (first recorded as 214; corrected from the log) | 51 s | `logs/v1-labelled-20261101/harness_isolated.log` |
| before `0c8efcb` | grading discover (as above) | 426 tests, 5 skipped, OK | 121.97 s | `logs/v1-freeze-20261101/grading_tests.log` |
| before `0c8efcb` | `run_isolated.sh` for each harness module | 14 modules, 200 tests, OK (first recorded as 215; corrected from the log) | 51 s | `logs/v1-freeze-20261101/harness_isolated.log` |
| before `57e2a25` | grading discover | 433 tests, 5 skipped, OK | 120.36 s | `logs/v1.1-20261101/grading_tests.log` |
| before `57e2a25` | `run_isolated.sh` for each harness module | 14 modules, 201 tests, OK | 51 s | `logs/v1.1-20261101/harness_isolated.log` |
| before `57e2a25` | Docker: `GoldRecalcDockerTests` (`7d7fc9a7…`, `1137e2bb…`) | 3/3, 2/2 | 8.23 s, 10.67 s | `logs/docker-gated-v1.1-221241Z/` |
| before `57e2a25` | Docker: `regress_recalc_docker` | 16 PASS, 0 FAIL | 3.93 s | `logs/docker-gated-v1.1-221241Z/` |
| before `57e2a25` | Docker: `regress_grading_cli` | first run 60 PASS, 1 FAIL (the not-attempted expectation); after updating it to `not_run`, 61 PASS, 0 FAIL | 7.25 s, 7.91 s | `logs/docker-gated-v1.1-221241Z/` |
| before `5121e1a` | grading discover | first run 444 tests, 7 failures (config engine version, expected V1.2 changes); after the updates 444 tests, 5 skipped, OK | 125.84 s, 119.86 s | `logs/v1.2-20261101/grading_tests.log`, `grading_tests_2.log` |
| before `5121e1a` | `run_isolated.sh` for each harness module | 14 modules, 201 tests, OK | 53 s | `logs/v1.2-20261101/harness_isolated_2.log` |
| before `5121e1a` | Docker: `GoldRecalcDockerTests`, `regress_recalc_docker` | 3/3, 2/2, 16 PASS | 7.46 s, 10.26 s, 3.89 s | `logs/docker-gated-v1.2-231621Z/` |
| before `5121e1a` | Docker: `regress_grading_cli` | first run 60 PASS, 1 FAIL (call-summary keys); then 61 PASS | 7.06 s, 6.66 s | `logs/docker-gated-v1.2-231621Z/` |

- The five skipped tests are `GoldRecalcDockerTests` in `test_gold_1137e2bb` and `test_gold_7d7fc9a7`, which need
  `GOLD_RECALC_DOCKER=1` and the pinned LibreOffice image.
- Docker-gated suites: `grading/tests/regress_recalc_docker.py` and `grading/tests/regress_grading_cli.py`. Their
  latest results are in section 4.
- `logs/` is not tracked; the paths above are local to `/Users/yuning/turing-th`.

### G. V1.1 (`57e2a25`; preregistration 1.20; `docs/status.md` "V1.1")

- `harness/budget.py`:
  - `resolve_manually(..., inferred=...)`, `validate_event` and `_derive`: an inferred (not provider-confirmed)
    `settled_amount` lifts the unit's hold and keeps it estimated and flagged.
  - `harness/launcher.run_judge_batch` settles judge batches per call (from `0c8efcb`).
- Engine `engine-2026-11-01.7`, `grading/grade.py`:
  - `judge_row_verdict`: a provider failure gives verdict `provider_error`; an unattempted call gives `not_run`;
  - `visual_review_items` and `_score` (`judge_infrastructure`, `visual_review_required`, per critical criterion);
  - `score_rows`.
- `grading/judge_recovery.py`:
  - `recovery_plan` (eligibility, the once-per-item bound, request-hash check);
  - `recovery_pass` (new `judge_item_recovery` pass, rows copied from the base pass, separate
    `judge_recovery_<run>_<pass>.json`);
  - `grading/run_grading.py --judge-recover ITEMS --base-pass PASS`, which refuses ineligible items before any
    reservation.
- `grading/judge_validation.py`:
  - `VERSION_TAGS` and `frozen_state` (latest existing version tag and its manifest);
  - `recover`, which requires a clear ledger.
- `grading/checks_2ea2e5b5.py` .4 and `grading/checks_47ef842d.py` .3: `visual_review="picture_chart"` on picture-chart
  unassessable entries.
- `grading/review.py`:
  - `save_evidence_correction` (append-only, post-reveal, judgments unchanged);
  - `save_label_checkpoint(extra=...)`;
  - a `_n` suffix on same-second checkpoint names.
- `grading/freeze_manifest.py`: `judge_surface`, `judge_surface_diff`, and `write --manifest --freeze --scope`.
  Record: `grading/freeze/v1.1_manifest.json`.
- Tests: `grading/tests/test_judge_recovery.py`, `test_judge_validation.py`,
  `harness/tests/test_budget_unit.py::test_inferred_settled_amount_lifts_the_hold_but_stays_an_estimate`, and the
  visual-review assertions in `test_gold_2ea2e5b5` and `test_gold_47ef842d`.
- `regress_grading_cli` now expects `not_run` for not-attempted rows.

### H. V1.2 judge infrastructure (`5121e1a`; engine-2026-11-01.8; preregistration 1.20 "V1.2"; `docs/status.md` "V1.2")

- `grading/judge.py`:
  - `provider_error_detail` reports HTTP status, provider status, quota, retry guidance, a redacted and truncated
    message, and recoverability;
  - `ProviderJudge(pacing_pause_s, provider_error_stop_items)`: continuation after a recoverable failure, a stop at
    3 distinct failed items, an immediate halt on an unrecoverable error, the recoverable-failure list, and
    `batch_result()["recovered"]`;
  - `judge_units(..., schema_retry)` and `_verdict_of`: one schema retry, `schema_attempts`, `invalid_judge_output`.
- `harness/budget.py` `settle`: `recovered.buffer_calls`, and a hold when nothing was metered.
  `harness/launcher.run_judge_batch` passes `recovered`.
- `grading/grade.py`: `invalid_judge_output` verdict, provider error and schema-attempt fields on J rows, call-summary
  counts.
- `grading/judge_recovery.py`: `_chain`, `_item_status`, the `judge_parse_error` rule, `response_schema_valid`.
- `grading/judge_validation.py`: `auto_recovery_items`, automatic recovery in `run`, the planned-reservation cap in
  `recover`, `VERSION_TAGS`.
- `grading/freeze_manifest.py`: `CALL_HANDLING` and `judge-surface TAG --request-only`. Record:
  `grading/freeze/v1.2_manifest.json`.
- `config.json` judge: `max_retries` 10, `pacing_pause_s` 2.0, `provider_error_stop_items` 3, and the approval note.
- Tests:
  - new: `grading/tests/test_judge_infrastructure.py`;
  - updated expectations, listed in `docs/status.md` "V1.2": `test_grading_chain`, `test_judge_dev`,
    `test_judge_recovery`, `test_judge_validation`, `regress_grading_cli`.

### F. Recorded limitations and open items (facts from `docs/status.md` and `preregistration.md`)

- Dev judge agreement on the six v4 Dev labels: 4/6 on the first pass (Judge Dev Pass 1). With builder
  `2ea2e5b5…` .3, Pass 2 agrees on both labelled items (2/2); that figure is post hoc. Six labels are a calibration
  check, not an accuracy estimate.
- Picture charts give `cannot_assess` (visual review) in `2ea2e5b5…` and `47ef842d…`. `1137e2bb…` items 25 and 26
  stay `cannot_assess` on its Dev output.
- `2ea2e5b5…` item 27 requires the literal label "Margin Impact" in a header or group row.
- `c3525d4d…` item 30 evaluates the first located change line (`delta_program`) against every total pair; the other
  `delta_program` facts are not candidates.
- `checks_7d7fc9a7.match_invoices` treats vendor lines without any readable amount as not matching an invoice (seen
  on a synthetic layout without amounts, not on a delivered output).
- `a45bc83b…`: eight AI-QA judge-interpretation leads were recorded and not acted on; Dev judge items were not
  re-run with builder .3.
- Judge Dev ledger settlements before `0c8efcb` priced summed prompts at the long-context tier and stay as recorded.
- Done after `0c8efcb`: V1 re-grades of every Dev run under the frozen versions; the Docker-gated suites at `0c8efcb`
  and before `57e2a25`.
- Judge protocol: a judge answer with a pass or fail verdict but an empty evidence list is a `judge_parse_error`
  (`cannot_assess`). It is a completed call, so it is never recovered. Four such items are recorded on one Validation
  run.
- Provider failures: twice a judge call failed with `RetryError` wrapping a google `ClientError` (V1/V1.1, before the
  status code was recorded). V1.2 records the detail and continues past recoverable failures.
- With `max_retries` 10, Inspect's backoff (`wait_exponential_jitter(initial=3, max=1800)`, no total timeout) can hold a
  single failing request for about 50 minutes before it is recorded.
- Not done at the pin: the remaining Judge Validation runs and recoveries; the formal freeze (`freeze-v1`); Formal
  candidate runs.

## 3. Focused acceptance checks

1. **Pin.** Section 1's `git diff` is empty, and
   `.venv/bin/python -m grading.freeze_manifest verify --manifest grading/freeze/v1.2_manifest.json` prints
   `"matches": true`. Confirm that `v1.2_manifest.json` covers every non-test `.py` file under `grading/` and `harness/`.
   `.venv/bin/python -m grading.freeze_manifest judge-surface v1-calibration-freeze --request-only` must report
   `"identical": true`.
   - Check that the request surface covers everything that shapes WHAT the judge receives.
   - Check that the entries classed as `CALL_HANDLING` only change how a request is sent and its answer read.
2. **Decision semantics.** For `Decision` (`grading/engine/decision.py`), `across_candidates` (`checks_7d7fc9a7`)
   and `over_candidates` (`checks_c3525d4d`), confirm against the code:
   - a confirmed violation fails;
   - an unreadable input of a non-failing reading leaves `cannot_assess`;
   - nothing is skipped into a pass;
   - candidates that disagree never resolve by position.
3. **The two rounding paths.** In `checks_7d7fc9a7.rounding_order_only`, confirm that both paths require the one-cent
   gap, the summary rounding and the totals' relation to the line cells, and that no other difference is excused.
4. **Additions.** In `checks_7d7fc9a7.additions_absent` and its callers, confirm that a month with an unclassified or
   ambiguous column never yields a confirmed absence, and that item 50 fails only on an increase.
5. **`2ea2e5b5…` headings and pictures.** Check `slide_heading`, `locate_sections`, `parse_table` (group rows, the
   percent choice) and `is_grand_total`. Check every chart-dependent item's branch when a picture is present without
   a native chart, and when a native non-pie chart is present.
6. **Evidence builders carry no verdict.** `build_units_*` must receive no grader verdict. Confirm the deliverable
   excerpt is built from the extraction only and that the task requirement and source material are present per unit.
7. **Judge cost safety.**
   - In `judge_dev.make_guard` and `judge_validation.make_guard`, confirm that the worst case is checked before every
     call against every applicable ceiling.
   - In `run_judge_batch` and `BudgetLedger.settle`, confirm that per-call pricing applies only to usage of the same
     batch, and that a conflict between the two sources settles at the larger figure with a hold.
8. **Freeze gate.** In `judge_validation.frozen_state` and `run`, confirm that no paid call is possible without the
   committed plan and an unchanged frozen tree.
9. **First-pass preservation.** Confirm that no code path rewrites or deletes an existing `grades.jsonl`,
   `results.jsonl` or `grading_run_*.json` row; that V1 re-grades and Pass 2 write to `dev/grading_v1/`; and that
   `compare_labels` verifies the checkpoint copy's SHA-256.
10. **Version registration.** Confirm that every task module's `VERSION` equals `config.json`
    `grading.task_grader_versions`, and that `ENGINE_VERSION` equals `grading.engine_version`.
11. **Per-item recovery** (`judge_recovery`, `run_grading --judge-recover`). Confirm against the code:
    - only `provider_error` and `not_attempted` base calls are eligible;
    - a completed call (any verdict or parse error) is never re-judged;
    - each item gets at most one sent recovery attempt;
    - the stored unit is sent unchanged, with the hash checked before any call;
    - every non-recovered row is copied unchanged, and the base pass and its rows are never rewritten;
    - a failed recovery stays `provider_error` / `not_run`;
    - nothing touches candidate-model attempts.
12. **Inferred ledger resolution.** Confirm that an inferred amount cannot be recorded without a calculation basis,
    stays estimated, lifts only that unit's hold, and leaves the reservation and settlement events untouched.
13. **Engine .7 labels and image-only evidence.** Check every consumer of verdict values (`_score`, `select_pass`,
    `review.compare_labels`, critical status) with the new `provider_error` / `not_run` values. Confirm that every
    `visual_review` tag comes from a picture-chart branch only, and that it reaches
    `score.critical.<C>.visual_review_required`.
14. **V1.2 provider failures.** Confirm against the code:
    - `provider_error_detail` never records credentials, headers or request contents;
    - a recoverable failure continues the batch;
    - three distinct failed items stop new requests;
    - authentication, permission, billing and invalid-request or configuration errors halt at once and leave the ledger
      held;
    - the inferred buffer applies only to recoverable failures with metered calls in the same batch, and an unmetered
      batch is held;
    - Inspect's `max_retries` is the only retry layer, and the pause adds no retry.
15. **V1.2 schema retry.** Confirm against the code:
    - only a completed call with a schema-invalid response is retried, exactly once, with the identical request;
    - the first schema-valid response is accepted whatever its verdict;
    - both attempts are kept;
    - two invalid responses give `invalid_judge_output`;
    - a schema-valid response is never retried;
    - a schema recovery pass performs no further inline retry for the recovered item.

Run the gold, layout and decision suites. Independent probes are welcome: a new layout or corruption of an expert
deliverable, with the expected item map declared before it is run. Report each finding as Blocking (a false pass, a
false fail, a cross-task behaviour change, a cost-safety or isolation defect, or a broken provenance or label-integrity
guarantee) or Non-blocking, with the file and line, the input, the observed and the expected outcome.

## 4. Records after the V1 pin (`0c8efcb`) and the V1.1 pin (`57e2a25`)

Docker-gated suites at `0c8efcb` (clean frozen tree; logs `logs/docker-gated-20261101T213418Z/`):

| Command (`harness/tests/run_isolated.sh /Users/yuning/turing-th ...`) | Exit | Result | Wall time |
|---|---|---|---|
| `GOLD_RECALC_DOCKER=1 ... unittest grading.tests.test_gold_7d7fc9a7.GoldRecalcDockerTests` | 0 | 3/3 | 5.43 s |
| `GOLD_RECALC_DOCKER=1 ... unittest grading.tests.test_gold_1137e2bb.GoldRecalcDockerTests` | 0 | 2/2 | 10.30 s |
| `... grading.tests.regress_recalc_docker --output-root <new dir>` | 0 | 16 PASS, 0 FAIL | 3.98 s |
| `... grading.tests.regress_grading_cli --output-root <new dir>` | 0 | 61 PASS, 0 FAIL | 7.51 s |

Validation and Judge Validation records (2026-11-01, code `0c8efcb`; details in `docs/status.md`):
- Judge Validation registry: `~/turing-eval-runs/judge_validation/registry.jsonl`; ledger:
  `~/turing-eval-runs/judge_validation/ledger.json`.
- The first run (`a45bc83b…`) halted after a provider `ClientError` on item 69 (usage uncertain). Items 70 and 71 were
  not attempted. The unit settled at its 7.06 USD reservation and is on manual-review hold.
- The other nine Validation runs were graded deterministically through the official entry (log
  `~/turing-eval-runs/validation/grading/deterministic_reveal.jsonl`).
- Dev frozen-version re-grades: `~/turing-eval-runs/dev/grading_v1/frozen_v1_regrade.jsonl`.
- After the V1.1 tag (registry `~/turing-eval-runs/judge_validation/registry.jsonl`):
  - the `a45bc83b…` unit was resolved at an inferred 0.856327 USD with the human's authorization;
  - item 71 (first evaluation) and item 69 (one retry) were recovered: 2 calls, both ok, same request hashes as the
    base, 0.049708 USD;
  - four items of that run (18, 19, 20, 64) keep `judge_parse_error` from their completed base calls and are not
    re-judged;
  - the resumed pass halted on the first call of `c357f0e2…` (item 12: `RetryError` wrapping a google
    `ClientError`); 53 calls were not attempted; the unit settled at its 6.11 USD reservation and is on hold.
- After the V1.2 tag:
  - the `c357f0e2…` unit was resolved at an inferred 0.056719 USD (4 x 0.850788 / 60 successfully metered calls of the
    pass);
  - recovery runs continue under V1.2; their records are `judge_recovery_<run>_<pass>.json` in each run's grading
    folder and the registry.
  - These later records are not part of the pinned code.
- Formal preflight at `eb781fd`: launcher `--dry-run` for all 20 Formal units, all rc 0, no provider call. Records are
  in `docs/status.md` ("Formal preflight").
- Verdicts of the Validation runs must not be disclosed to the human before the Validation labels are checkpointed.
  Do not print or quote Validation verdicts or judge responses in the review report.

## 5. Prompt for a fresh Codex session

```
You are reviewing a grading codebase read-only. Start with /Users/yuning/turing-th/docs/codex_review_2.md and treat
every statement in it as a claim to verify against the code, not as a fact: open the cited files and functions,
check them line by line, and run the listed tests yourself. Do not accept a description, a test count or a result
because the package states it.

Rules: do not modify, add, stage or commit any file in /Users/yuning/turing-th; write your notes and probe files only
under /tmp/codex-r2/. Do not read plan/, .env or any credential. Do not run any command that calls a model provider
(grading.judge_dev run or pass2, grading.judge_validation run or recover, grading.run_grading --judge, harness.launcher,
harness.scheduler). Harness tests run
through harness/tests/run_isolated.sh /Users/yuning/turing-th <module>; grading tests with
.venv/bin/python -m unittest <module> from the repository root.

First check the pin (section 1): if git diff --name-only 5121e1a HEAD -- grading harness config.json prints anything,
stop and report. Do not open anything under ~/turing-eval-runs/validation/grading/, ~/turing-eval-runs/labeling/validation-v4/
or ~/turing-eval-runs/qa/, and never quote Validation verdicts or judge responses. Then work through sections 2 and 3. For every claim you checked, record confirmed or not confirmed,
with file:line evidence. Report findings as Blocking or Non-blocking with the input, the observed and the expected
outcome, and say plainly what you did not check.
```
