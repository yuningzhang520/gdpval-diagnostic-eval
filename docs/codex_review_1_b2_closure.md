# Codex Review 1 — B2 remainder closure package (2026-11-01)

Focused closure check of the two B2 items left BLOCKED by the Codex closure check of `2c37d6a`. Not in scope: another
architecture review, other findings, other tasks, the harness.

- Fix commit: `c04a788411379611057ce290941218677a48e667` (task version `7d7fc9a7-2026-11-01.3`).
- Changed files: `grading/checks_7d7fc9a7.py` (task specification), `grading/gold_variants_7d7fc9a7.py` (variants
  R29–R35), `config.json` (task version label), `docs/status.md`. The shared engine (`grading/engine/`) and the 1137
  grader are unchanged: `git diff 2c37d6a c04a788 -- grading/engine grading/checks_1137e2bb.py` is empty.
- Code-bound records written from the fix commit with a clean tree:
  `grading/validation/7d7fc9a7-21a7-4b83-906f-416dea5ad04f/code_c04a788/` (`corruption_catalog.json`, 50 variants;
  `gold_transitions.json`; `red_prefix_b2.txt`, the pre-fix reproduction).

## Cause

Duplicate bottom rows were recorded as ambiguous, but each check still read the first row and could confirm a
violation from it. Item 11 summed a month's first amortization column without consulting the header's ambiguity
record. A definitive FAIL therefore depended on an unresolved choice of row or column.

## Fix

`across_candidates(d, candidates, evaluate, label)` (task module) evaluates a check once per candidate reading on a
scratch decision:

| Candidates | Decision |
|---|---|
| one | evaluated on the item directly: the code path is unchanged |
| any candidate unassessable | the item is unassessable |
| every candidate violates | confirmed violation, annotated "in every one of N candidate rows" |
| candidates disagree | `cannot_assess`, with each candidate's first violation as evidence |
| every candidate clean | no violation (the existing duplicate-row ambiguity mark still applies) |

Applied to items 22 and 40 (each totals row, paired with each ending row for the end-balance fallback), the bottom
summary presence items 27–29 and 47, the variance items 30 and 48 (each GL row with each variance row), and item 11 (per
account, over its totals rows). Item 11 also treats an amortization column that appears twice for a month as
ambiguous; if no summary cell carries the YTD figure, its independent `absent` violation still fails.

Found while reproducing: the presence check passed `kind=` to `Decision.violation`, whose first parameter is `kind`, so
any deliverable with a missing bottom summary figure raised `TypeError`. That line existed in the pre-fix code and in
the first fixed draft. The keyword is renamed to `figure_kind`.

## Reproducing regressions (declared before observation)

| Variant | Construction | Pre-fix (blob `c5d8dbbc…`) | Declared and observed after the fix |
|---|---|---|---|
| R29 | second 1250 "Month Totals" row read first, January amortization +100 | 11 fail, 22 fail | 11, 22 `cannot_assess`; 23–29 keep their duplicate-row ambiguity |
| R30 (guard) | both 1250 totals rows wrong (+100, +200) | 11 fail, 22 fail | 11 fail, 22 fail (confirmed in every row) |
| R31 | second January amortization column; the first column's total is +100 | 11 fail | 11 `cannot_assess`; 20, 21, 22, 28 ambiguous as before |
| R32 | as R29 on 1251 | 11 fail, 40 fail | 11, 40 `cannot_assess`; 41–44, 47 ambiguous |
| R33 | second 1251 variance row read first, January variance 5.00 | 48 fail | 48 `cannot_assess` |
| R34 | duplicate 1250 totals row read first without January additions | TypeError | 27 `cannot_assess`; 11 pass (both rows agree) |
| R35 | the single 1250 totals row without January additions | TypeError | 27 fail |

The expert workbook and its values-only twin grade as before (expert: 10 and 30 fail).

## Tests at the fix commit

| Suite | Result |
|---|---|
| `grading.tests.test_gold_7d7fc9a7` (anchor, twin, 50 variants, production `grade_run`) | 53 pass, 3 Docker-gated skipped |
| `grading.tests.test_grading_chain` / `test_review_packets` / `harness.tests.test_docs_consistency` | 29 / 2 / 3 pass |
| `grading.tests.test_gold_1137e2bb` | 53 pass, 2 skipped |
| `GoldRecalcDockerTests` (7d7fc9a7) | deferred while paid sandbox units run; the recalculation path is untouched and the expert workbook takes the single-candidate path |

## What to verify

1. The two blockers: R29, R31 and R32 grade 11, 22 and 40 `cannot_assess`, and the guard R30 still fails.
2. No row-dependent FAIL remains for duplicate bottom rows in items 11, 22, 27–30, 40, 47 and 48.
3. Single-row workbooks take the unchanged path: expert and twin baselines are unchanged.

```
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7
git diff 2c37d6a c04a788 -- grading/checks_7d7fc9a7.py grading/gold_variants_7d7fc9a7.py
git diff --stat 2c37d6a c04a788 -- grading/engine grading/checks_1137e2bb.py   # expected empty
```
