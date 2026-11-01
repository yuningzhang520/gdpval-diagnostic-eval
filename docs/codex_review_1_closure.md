# Codex Review 1 — blocker closure package (2026-11-01)

Focused closure check for the Codex Review 1 findings on the shared grading core
(`logs/shared-core-review-wm_mg0v2/review.md`, reviewed target `bd5713bdfccdb6418190fbcac332de25ca3b713a`).
Scope: B1–B4, N11, provenance, and any directly related correctness blocker. Not in scope: another architecture
review, other tasks, the harness. The fixes are in the task specification `grading/checks_7d7fc9a7.py` (task version
`7d7fc9a7-2026-11-01.2`), `grading/grade.py::code_provenance`, the two gold catalogs and suites; the shared engine
(`grading/engine/`) and the 1137 grader are unchanged. Closure commit: `9b1df11851f65349a8e5e0bc63a418f311202dac`.
Code-bound verification records (written from that commit with a clean tree): `grading/validation/<task>/code_9b1df11/`
(`corruption_catalog.json`, `gold_transitions.json`, `gold_transitions_recalc.json`), each with `_provenance`
(full commit, `dirty: false`, changed and untracked path counts, task grader and engine versions). Test log
directories: `logs/codex-r1-fixes-20261101T110924Z/` (non-Docker suites, pre-fix reproduction) and
`logs/codex-r1-docker-20261101T112649Z/` (Docker-gated suites and record dumps).

## Closure table

| Finding | Original failure (pre-fix code, reproduced) | Fix | Reproducing test | Result after the fix | Remaining uncertainty |
|---|---|---|---|---|---|
| B1 item contract | `grade_run` on a 7d7fc9a7 run raised `KeyError: 'weight'` | every D item row carries weight, criterion, dependencies, fail_on_own | `test_gold_7d7fc9a7.ProductionGradeRunTests` (real collector + outcome writer, judge disabled) | 56 rows (41 D with weights, 14 J `pending_judge`, 1 V `pending_human`), D map = gold baseline, W/E/P from the rows, combined grader version and full commit in the pass, verdict-free packet | real recalculation path for this test is not exercised (recalc off) |
| B2 uncached summary figure | Summary!B9 formula without cache → item 8 FAIL (absent) | figure cells keep formula / state; unreadable → `cannot_assess` | R23 | 8 `cannot_assess` (grader_caused_recalculation) | — |
| B2 uncached addition | ADOBE Jan add as uncached formula → 13 PASS, 14 FAIL | per-month add states; invoice uncertain when its line has an unreadable figure | R24 | 13, 14, 21 `cannot_assess`; 22 holds | — |
| B2 uncached amortization | one Jan amortization uncached → 22 FAIL | column sums carry unknown cells | R25 | 21, 22 `cannot_assess` | — |
| B2 uncached insurance amortization | 36 FAIL, 40 FAIL, 49 PASS | unreadable cells registered in 36/39/40/49/50 | R26 | 36, 39, 40, 49 `cannot_assess` | — |
| B2 duplicate month column | first-wins: 21, 22, 23, 29 PASS | ambiguous (month, kind) kept with candidates | R27 | 21, 22, 23, 29 `cannot_assess`; 30 keeps its independent FAIL | — |
| B2 vendor-less row | row dropped as a note → 13 FAIL, 14 PASS, 22 FAIL | unidentified rows bound the confirmed missing count | R28 | 13, 14, 22 `cannot_assess` (13 attribution unknown) | the rule mirrors 1137 2.4; no new adjudication |
| B3 account identity | B9/B14 amounts swapped, labels unchanged → 8 and 9 PASS | label + heading identify account and measure before the value | R22 | 8 and 9 FAIL; gold B9/B14/B8/B13 located by label; total absent | label vocabulary is a fixed rule set; unrecognised labels give `cannot_assess` |
| B4 item 53 allowance | one General invoice amount → 53 PASS | allowance removed; every nonzero monetary cell tested | R21 | 53 FAIL; gold 535 monetary cells compliant | zero / blank cells not tested (no amount shown) |
| P1 N11 | declared neutral although judge item 17 changes | kind `d_neutral`, `judge_expected` {17} | suite asserts (D-)neutral variants declare no D change | recorded in catalog | judge effects of other variants not asserted (scope note in both catalogs) |
| P1 provenance | `code_provenance` ignored untracked files; validation records lacked a commit | `--untracked-files=all`, changed / untracked path counts; suite dumps carry `_provenance`; new records bound to the closure commit | `test_grading_chain.CodeProvenanceTests` | untracked file → dirty | earlier records keep their original text (no retrospective SHA invented) |

Pre-fix reproduction: `logs/codex-r1-fixes-*/red_prefix_7d7fc9a7.log` (the nine new cases against the committed
pre-fix module, blob `057a4180c047ad37ba8dffcd331eaa4c9857410a`, identical to `bd5713b`): 8 failures, 1 error.

## Test results at the closure commit

| Suite | Result |
|---|---|
| `test_gold_7d7fc9a7` (incl. R21-R28, production `grade_run`) | 46 + 3 Docker-gated skipped, all pass |
| nine new cases against the pre-fix module | 8 failures, 1 error (expected red) |
| `test_gold_1137e2bb` / `test_layout_regressions` / `test_grading_chain` / `test_review_packets` | 53 + 2 skipped / 57 / 29 / 2, all pass |
| `GoldRecalcDockerTests` (1137 / 7d7fc9a7, LibreOffice in the pinned image) | 2/2 / 3/3 |
| `regress_recalc_docker` / `regress_grading_cli` / `regress_pilot_cli` | 16 / 61 / 13 PASS, 0 FAIL |
| harness unit suites (launcher, batch, budget, staging, generation config, docs consistency) | all pass |

Durations and exit codes: `docs/status.md`, section "Codex Review 1 fixes".

## What to verify

1. The four blockers on the fixed module: run the commands below; compare with the closure table.
2. That no expert verdict changed: gold baselines of both tasks (7d7fc9a7: 10 and 30 fail; 1137: 21 fails).
3. That no shared-engine or 1137 behaviour changed: `git diff <reviewed target>..<closure commit> -- grading/engine grading/checks_1137e2bb.py`
   is empty; the 1137 suites are green.
4. Provenance binding of the new records (commit, dirty flag, untracked count) in `grading/validation/*/code_9b1df11/`.

```
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_1137e2bb grading.tests.test_layout_regressions grading.tests.test_grading_chain
GOLD_RECALC_DOCKER=1 harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7.GoldRecalcDockerTests grading.tests.test_gold_1137e2bb.GoldRecalcDockerTests
harness/tests/run_isolated.sh /abs/repo grading.tests.regress_grading_cli --output-root /abs/fresh/dir
git diff bd5713b..9b1df11 -- grading/engine grading/checks_1137e2bb.py   # expected empty
```
