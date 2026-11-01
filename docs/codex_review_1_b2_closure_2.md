# Codex Review 1 — B2 closure, second round (2026-11-01)

Focused closure check of the two B2 defects the Codex check of `c04a788` left open. The first-round package is
`docs/codex_review_1_b2_closure.md` (pinned to `c04a788`). Not in scope: another architecture review, other findings,
other tasks, the harness.

- Fix commit: `a9a1f88293264d653e4f0ded024eeeedcf1f4636` (task version `7d7fc9a7-2026-11-01.4`).
- Changed files against `c04a788`: `grading/checks_7d7fc9a7.py`, `grading/gold_variants_7d7fc9a7.py` (R36, R37),
  `config.json` (task version label), `docs/status.md`. Shared engine and the 1137 grader unchanged:
  `git diff c04a788 a9a1f88 -- grading/engine grading/checks_1137e2bb.py` is empty.
- Code-bound records written from the fix commit with a clean tree:
  `grading/validation/7d7fc9a7-21a7-4b83-906f-416dea5ad04f/code_a9a1f88/` (`corruption_catalog.json`, 52 variants;
  `gold_transitions.json`; `red_c04a788_round2.txt`, the reproduction on the `c04a788` module).

## Defects and fixes

| Defect at `c04a788` | Fix in `a9a1f88` |
|---|---|
| `across_candidates` checked "any candidate unassessable" before "every candidate violates", so unrelated unassessable evidence in one candidate erased a violation confirmed in every candidate | each candidate is decided like an item: a violation fails it even beside an unassessable input; otherwise an unassessable input leaves it unassessable. The item fails when every candidate fails, and the unassessable evidence is kept beside the violation. Otherwise any failing or unassessable candidate leaves it `cannot_assess` |
| with no totals row, the presence check (items 27–29, 47) read only the first ending-balance row | without a totals row, every ending-balance row is a candidate |

## Reproducing regressions (declared before observation)

| Variant | Construction | At `c04a788` (blob `80b9d64c…`) | Declared and observed at `a9a1f88` |
|---|---|---|---|
| R36 | both 1250 totals rows misstate January amortization (+100, +200); the first also has an uncached February amortization formula | 22 `cannot_assess` | 22 fail (confirmed in every candidate, the unassessable cell kept as evidence); 11 `cannot_assess` (one candidate's sum is unknown); 23–29 ambiguous as before |
| R37 | no totals row; two ending-balance rows, the first without February | 29 fail | 29 `cannot_assess`; 22, 27, 28 fail on the missing totals row; 11 `cannot_assess`; 23–26 ambiguous |

The first-round variants R29–R35 and every earlier variant still match their declarations. Expert workbook and
values-only twin are unchanged (expert: 10 and 30 fail).

## Tests at the fix commit

| Suite | Result |
|---|---|
| `grading.tests.test_gold_7d7fc9a7` (anchor, twin, 52 variants, production `grade_run`) | 55 pass, 3 Docker-gated skipped |
| `grading.tests.test_grading_chain` / `harness.tests.test_docs_consistency` / `grading.tests.test_label_batch` | 29 / 3 / 3 pass |
| `GoldRecalcDockerTests` (7d7fc9a7) | deferred while paid sandbox units run; the recalculation path is untouched |

## What to verify

1. R36: a violation present in every candidate survives unrelated unassessable evidence (22 fails).
2. R37: without a totals row, a conflicting pair of ending rows gives 29 `cannot_assess`, not a first-row FAIL.
3. Single-candidate paths unchanged: expert and twin baselines unchanged; R29–R35 unchanged.

```
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7
git diff c04a788 a9a1f88 -- grading/checks_7d7fc9a7.py grading/gold_variants_7d7fc9a7.py
git diff --stat c04a788 a9a1f88 -- grading/engine grading/checks_1137e2bb.py   # expected empty
```
