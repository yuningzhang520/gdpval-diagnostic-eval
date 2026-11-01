# Codex Review 1 — Shared grading core after the second task (2026-11-01)

Scope of this review: the shared spreadsheet grading core extracted after the second task, before it is scaled to
the remaining eight tasks. Not in scope: the harness, budget ledger and batch runner (reviewed earlier), the approved
rubric adjudications, and the judge protocol. Please do not reopen the evaluation architecture.

## What to review

1. **The engine package `grading/engine/`** (extracted on the rule of two: only what both graders use):
   - `cells.py`: one cell-reading interface (`read_value` / `read_cell`: ok / empty / formula_unrecalculated /
     error_value), `numeric_cell`, `norm_text`, `qty`, `q2`, `describe_cell`, the INVALID / UNRELIABLE kinds.
   - `decision.py`: `Result`, `Decision` (confirmed violation → FAIL; otherwise unreliable required input →
     cannot_assess; otherwise PASS; both kept in the evidence), `ATTRIBUTION`.
   - `headers.py`: `map_columns(header, schema, flag_schema)` with exact synonyms, long-synonym containment, keyword
     rules and per-field `keyword_exclude`; a field is `confirmed_missing` only when no unrecognised header remains.
   - `workbook.py`: `workbook_gate` (no workbook / unreadable workbook attribution / single-file rule).
   - `money.py`: `parse_money`, `cents` (HALF_UP on the Decimal), `cents_equal`, `close` (0.005 identity tolerance).
   - `sheets.py`: `month_of`, sheet lookup, row labels, header-block text search.
   The 1137e2bb grader now imports these (its own pipeline is unchanged); the 1137 gold catalog (51 variants) and
   layout suite (57) are the regression net for the move — all green before and after.
2. **The second task specification `grading/checks_7d7fc9a7.py`** (prepaid amortization): sheet location by name
   with content fallbacks, the month-grouped header (two-row or one-row), line parsing, bottom rows (totals /
   ending / variance / GL / adjustment), invoice matching against the independently parsed invoice lists,
   reconciliation per the approved rule (prereg 2.7), summary linkage (values by cents, formulas referencing the
   detail sheets), number formats. Judge units: `grading/judge.py::build_units_7d7fc9a7`.
3. **Gold-first evidence**: `grading/validation/7d7fc9a7-…/` (first pass preserved; catalog with declared maps;
   observed transitions) and `grading/gold_variants_7d7fc9a7.py` (20 rubric-relevant, 15 neutral). The 1137
   equivalents under `grading/validation/1137e2bb-…/`.
4. **Versioning and grading registration**: `grading/grade.py` (`ENGINE_VERSION`, per-task `VERSION`, full commit
   in every pass, visual items as `pending_human` rows), `config.json` `grading`.

## Invariants the reviewer should try to break

- No comparison is ever skipped into a PASS; a confirmed violation FAILs even when another input is unreliable.
- Grader-side faults (unreadable cell, unrecalculated formula, unmapped column) become `cannot_assess` with a
  grader-side attribution, never a model FAIL and never a PASS.
- A presentation-only row (footer, subtotal, note) is never a business row; an ambiguous row never matches a named
  line and never confirms an absence.
- Every GL / rubric comparison is HALF_UP to cents on the Decimal of the delivered value; identities on the
  deliverable's own values use the 0.005 tolerance only.
- The expert deliverable is never the value reference; the independent recalculation is.
- A task module changes nothing in the engine's behaviour for another task (1137 suites prove it for this round).

## Known limitations (state them, do not fix them here)

- Long-format schedules (one row per vendor and month) are not parsed: they become `cannot_assess` (grader-side),
  a coverage loss, not a FAIL.
- Vendor matching is normalised containment; two different vendors whose names contain each other would be
  conflated (none in this task's data).
- The 7d7fc9a7 docker-path cases (expert file through LibreOffice; summary linkage variants that need formulas) and
  the 1137 docker recalculation regression after the engine move are deferred until the sandbox is free from paid
  generation; the fast path uses the expert file's cached values.
- Item 53 (currency formats) and item 6 (reporting period in the header block) use operational definitions recorded
  in prereg 2.7; rubric 55 is a judge item (K1); the C2 composition question (rubric 30) is escalated.

## How to run

```
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_1137e2bb     # 53 + 2 gated
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7     # 37 + 3 gated
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_layout_regressions
harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_grading_chain
GOLD_RECALC_DOCKER=1 harness/tests/run_isolated.sh /abs/repo unittest grading.tests.test_gold_7d7fc9a7.GoldRecalcDockerTests   # when docker is free
```

Independent probes are welcome: new corruptions or layouts of the expert workbooks with a declared expected map.
Report findings as Blocking (a false PASS, a false FAIL, a cross-task behaviour change) or Non-blocking.
