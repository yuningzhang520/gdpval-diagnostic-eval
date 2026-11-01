> SUPERSEDED 2026-11-01: the candidate pilot on `1137e2bb…` described here was not run. The revised evaluation architecture replaces it with run classes (`dev`, `validation`, `compat`, `formal`; `config.json` `batches`, `PLAN.md` sections 3, 4 and 7). Kept unchanged below as the record of the superseded request.

# Pilot A — paid-run request (DRAFT, not executed)

Status: DRAFT request for approval, corrected 2026-10-31 after the Stage 3b review. Nothing in
this document has been run. No model, judge or paid API call has been made. Values marked
FORECAST are planning estimates, not measurements; no version or cost figure below is confirmed
by an actual run, and the placeholders stay until the human fills them at authorization.

Status update 2026-11-01: the generation configuration below was revised to the approved high-reasoning
condition (`reasoning_effort` high on both candidates, `max_tokens` 32,000, time and working limits 7,200 s,
`token_limit` 20,000,000, `cost_limit` 20 USD, reservations A 8 USD / B 5 USD, pilot ceiling 45 USD; see
"Execution limits in force" and `config.json`). Superseded statements kept below for the record: the real
launcher path is implemented and mock-verified since commit `bcb8887` (`--real-run`, section "Enabling the
real launcher"); missing or incomplete usage now settles conservatively AND holds further paid starts until a
recorded manual reconciliation (B2, approved 2026-10-31), which closes the "Open before the pilot" row.

## Scope

| Item | Value |
|---|---|
| Model A | `anthropic/claude-opus-5-5` (candidate per `config.json` `models.strategy_capability_first_preferred`; final approval of A pending) |
| Task | `1137e2bb-bdf9-4876-b572-f29b7de5e595` (PO entry audit), one Task, one sample, k = 1, `attempts = 1`, `epochs = 1` |
| Entry point | `harness.launcher` real mode (not yet enabled, see below) → `inspect_ai.eval` → sandbox from image `sha256:18cde712cde1867c94b8f23ae1f4066b0aa3146fdbd8deac70d1b4aa043ea9ee` (linux/arm64), `network_mode: none` |
| After the run | `grading.grade.grade_run` on the collected `final/` outputs; Gemini judge called once per judge-only criterion (7 calls per run, `judge_units`; no batch is wired); human review before any judge verdict is shown |

## Generation calls, tokens and cost (FORECAST)

Assumptions: an agent loop that reads the input workbook, writes the .xlsx and .docx with
Python or LibreOffice, re-opens its deliverables once, and finishes well inside the 200-message
limit; every call re-sends the growing context (Inspect `token_limit` type `all`); Anthropic
prompt caching reduces repeated input to cache reads. No measurement of this model on this task
exists yet; the ranges below are judgement, not data.

| Quantity | Low | High | Basis |
|---|---|---|---|
| model calls | 25 | 90 | one call per tool step; 200-message cap = ~100 steps |
| uncached input tokens | 0.2 M | 1.0 M | first sends of each context segment |
| cache-read tokens | 0.5 M | 4.0 M | re-sent context per call |
| cache-write tokens | 0.1 M | 0.5 M | |
| output tokens (incl. thinking) | 20 k | 120 k | tool calls plus deliverable code |
| cost at list prices (4 / 20 / 0.20 read / 8 write ledger rate) | ≈ 2.1 USD | ≈ 11.2 USD | low: 0.2 M × 4 + 0.5 M × 0.20 + 0.1 M × 8 + 0.02 M × 20 = 0.8 + 0.1 + 0.8 + 0.4; high: 1.0 M × 4 + 4.0 M × 0.20 + 0.5 M × 8 + 0.12 M × 20 = 4.0 + 0.8 + 4.0 + 2.4; the high case exceeds the 10 USD `cost_limit`, which Inspect checks between calls (cost limit event, graded under the budget policy) |
| cost at `reasoning_effort` high (approved 2026-11-01; same call, input and cache quantities; output incl. thinking 40 k–250 k, a guess of two to three times the default-effort forecast) | ≈ 2.5 USD | ≈ 14 USD | FORECAST; the 20 USD `cost_limit` can still bind in the worst case; Model B at half price ≈ 1.1–6 USD |

Pre-run estimate for the ledger reservation: 8 USD for sample A and 5 USD for sample B (FORECAST,
approved 2026-11-01; the 5 USD figure of the earlier draft is superseded). The reservation, the
2× stop rule, the 20 USD per-sample `cost_limit` and the 45 USD aggregate ceiling are
accounting and stop controls inside this harness: none of them caps the provider's final bill.
A call already in flight when a limit is crossed is billed in full, cache and retry charges
are priced from the provider's usage report after the fact, and the ledger's conservative
figures are estimates until reconciled with the invoice. Uncertainty: thinking-token volume
and the number of self-check iterations dominate; a factor of 3 either way is plausible.

## Judge (FORECAST; protocol not yet verified against the real provider)

| Item | Value |
|---|---|
| Judge | `google/gemini-3.1-pro-preview` (candidate; version fixed at freeze; fallback named then) |
| Items | 11, 23, 24, 27, 28, 29, 30 (judge-only) |
| Call shape as implemented | `grading.grade.grade_run` calls `judge.judge_units`, i.e. one judge call per unit (7 calls per run), each carrying the system prompt, the task text, the criterion, the reference values and the deliverable excerpts (model identity hidden). The per-task batch helpers (`render_batch`, `parse_batch_response`, `judge_batch`) exist and are protocol-tested with the stub only; they are NOT wired into `grade_run` |
| Tokens (FORECAST, per-call basis) | ≈ 3–6 k input and ≈ 0.3–0.5 k output per call → ≈ 25–45 k input, ≈ 2–4 k output per run |
| Cost (FORECAST) | ≈ 0.08–0.14 USD per run at 2 / 12 USD per MTok (≤ 200 k tier); two runs (A, later B) ≈ 0.3 USD, plus any debug calls |
| Not verified / not wired | no real judge call has been made: response format, refusal behaviour and usage fields are unknown; the real `judge` callable for `grade_run` (provider client, usage capture, ledger reservation and settlement for a judge unit) is not implemented; batching, if adopted, needs its own wiring and a protocol check |
| Agreement claim | the 7 judge-only items are in the debug set (`grading/debug_set.json`); they can be used to debug the judge protocol but not to claim an independent judge–human agreement figure (debug items are never reused for validation) |

## Budget

| Control | Value | Source |
|---|---|---|
| Pilot ceiling | 45 USD cumulative (approved 2026-11-01; 30 USD before) (A, B, judge, cache charges, billable retries) | `config.json` `pilot.budget_ceiling_usd`; ledger-enforced, not a provider hard cap |
| Per-sample cost limit | 20 USD (approved 2026-11-01; 10 USD before; Inspect `cost_limit` with `model_cost_config` from the candidate facts; fails closed without price data) | `generation.cost_limit_usd` |
| Reservation | 8 USD for sample A and 5 USD for sample B (FORECAST, approved 2026-11-01); judge units for one run ≈ 0.15 USD reserved separately (per-call basis above; FORECAST) | this request |
| Stop conditions | reservation not covered; actual > 2× estimate; same engineering failure class twice; ceiling reached; usage-source conflict or unpriced usage → settled conservatively and held for manual review | `pilot.stop_conditions`, `harness/budget.py` |
| Engineering errors (as implemented) | a returned eval error (`fail_on_error=false`) is recorded as an engineering failure (two of the same class stop further starts) and settled through the normal `settle` path: with usage present → priced from the usage (exact; `estimated` only when retries, unpriced models or an aggregated-vs-per-call conflict are involved); with no usage → `fallback_to_reservation`: max(priced part, reservation), `estimated`, no hold; unpriced or conflicting usage → `estimated` + `manual_review_required` hold. An exception raised by `eval` itself → settled `estimated` at the reservation. Human handling is required for: every `manual_review_required` settlement, every open reservation after a restart, and any `estimated` settlement before the pilot cost is reported | `launcher.run_sample`, `_after_unit`, `classify_eval_log`, `budget.settle` |
| Missing usage (as implemented) | no usage in the returned sample → `settle(fallback_to_reservation=True)`: cost = max(priced part, reservation), flagged `estimated` ("settled at the reserved amount"); this does NOT set `manual_review_required` and does not by itself stop further starts | `budget.settle` |
| Unpriced or conflicting usage (as implemented) | a model without price data, or aggregated vs per-call usage disagreeing → settled at the larger figure, `estimated`, `manual_review_required`, further paid starts held until a recorded review | `budget.settle`, `reconcile_usage` |
| Open before the pilot | whether a missing-usage settlement should also hold further starts (stricter unknown-usage stop) is a decision to take before the first paid run; not implemented | this request |
| Multi-log / multi-sample return | no settlement, reservation kept, stop recorded (R6) | `launcher.run_sample` |

## Execution limits in force (`config.json`, DRAFT until `freeze-v1`)

Approved 2026-11-01 (high-reasoning configuration): `reasoning_effort` high on both candidates
(explicit, passed as `GenerateConfig.reasoning_effort`; `reasoning_summary` none), `token_limit`
20,000,000 (type `all`), `message_limit` 200, `time_limit_s` 7200, `working_limit_s` 7200,
`max_tokens_per_request` 32,000, `tool_timeout_s` 600, `mem_limit` 3 GB, concurrency 1 / 1 / 1 / 1.
Retries: Inspect request retries 3 (timeout 2700 s, attempt 900 s), SDK retries 0 (`model_args`),
`retry_on_error` 0, `fail_on_error` false, `task_retry_attempts` 0. `eval_kwargs` passes every value
from the config and refuses to start when one is missing or not an Inspect literal. Same nominal
effort is not equal compute: the two providers implement it differently, tokenizers and prices differ,
and results are reported per model with their own usage.

## Enabling the real launcher (superseded: implemented 2026-10-31, commits `bcb8887` and `b22ebd9`)

Superseded. Kept as the historical record of the request; `--real-run` with `--confirm`, `--authorized-by` and `--authorization-ref` is implemented and mock-verified.

A paid pilot cannot be executed with the current code: `harness/launcher.py main()` raises
"real mode is not enabled in this stage" after the pre-flight (only `--dry-run` runs), and no
real judge callable exists for `grade_run`. Enabling requires, in this order and each with
approval: (1) a code change wiring `eval_fn=inspect_ai.eval` and the real `make_task` path in
`main()`, plus the judge client with usage capture and ledger settlement;
(2) `INSPECT_DISABLE_MODEL_API` unset in the launcher process (`refuse_disabled_model_api`),
`.env` (mode 0600) loaded by the launcher only, `ANTHROPIC_API_KEY` present (name checked,
value never printed); (3) `freeze-v1` tagged before any formal run — the pilot itself runs on
the approved draft config with the commit hash recorded in the run metadata. Still locked:
model A/B final approval, judge id and the unverified judge protocol, `token_limit`/`max_tokens`
final values, the missing-usage stop decision, the stale config note above.

## Pre-run checklist

- Code: commit hash recorded (`PLACEHOLDER_COMMIT_HASH`); working tree clean or every diff listed.
- Config: `config.json` sha256 recorded (`PLACEHOLDER_CONFIG_SHA256`); `_status` DRAFT acknowledged; `pilot.task_id` = 1137e2bb.
- Image: pre-flight by full image ID equals `sandbox.image_id` and `harness/compose.yaml` (`image`, `pull_policy: never`, `x-local: true`); platform linux/arm64; no rebuild since the ID was recorded.
- Credential isolation: `.env` outside the sandbox, loaded by the launcher only; no key in environment of the sandbox or in any prompt; `harness.smoke` scrubbing not active in real mode (dummy keys must NOT be injected).
- Model-input isolation: `build_samples(verify_config=...)` allowlist and hashes pass (I1); only `data/inputs/<task>/` files and pre-staged resources enter via `Sample.files`; `private/`, `data/gdpval.parquet`, `preregistration.md`, `plan/`, grader code and other runs not mounted or copied; provider server-side tools off.
- Budget: ledger snapshot shows remaining ≥ reservation; no open reservations from earlier processes; stop reasons empty.
- Prompt: `system_prompt_sha256` equals the recorded value; identical for A and B.

## Post-run artefacts to keep (immutable once collected)

`.eval` log (runs_root `inspect_logs/`), `final/` deliverables with hashes, `run.json`,
`run_outcome.json`, launcher records and ledger JSON, `grades.jsonl`, `results.jsonl`,
`work_<uuid>/` extraction and recalculation evidence, `review/` materials (independent human
template filled before the judge verdict is revealed), judge request/response and usage per call (7 per run),
cost and time accounting (generation, grading, human review).

## Approval record (to fill at authorization)

commit `PLACEHOLDER_COMMIT_HASH` · config sha256 `PLACEHOLDER_CONFIG_SHA256` · image
`sha256:18cde712cde1867c94b8f23ae1f4066b0aa3146fdbd8deac70d1b4aa043ea9ee` · approved by ___ on
___ · ceiling 45 USD · sample A reservation 8 USD (FORECAST) · sample B reservation 5 USD (FORECAST) · judge reservation ___ USD.
