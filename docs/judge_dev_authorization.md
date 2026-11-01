# Judge Dev calibration: authorization package

Written for: the human approver. Prepared 2026-11-01. Status: PROPOSAL. No judge call has been made, and none is made
until every item in section 6 is approved.

## 1. Purpose

Review-queue policy v2 (preregistration 1.19, amendment v2) calibrates the shared judge prompt on Dev human labels
before the first Validation reveal. The judge prompt and model settings are then frozen globally, and the per-task
evidence builders separately. Validation outputs stay sealed throughout; no Validation or Formal output is judged
under this package.

## 2. Proposed judge and settings (all pending approval)

| Setting | Proposal | Note |
|---|---|---|
| Model | `google/gemini-3.1-pro-preview` (the `config.json` judge candidate) | A preview model may change or be withdrawn. The served model string is recorded per call, and a fallback judge is named at the freeze. |
| Thinking | thinking level `high`, pinned explicitly | The model is thinking-only. `grading.judge.ProviderJudge` does not pass a reasoning setting yet; a small offline-tested change is needed (section 5). |
| max_tokens | 16,384 | For this model the limit includes thinking tokens. The adapter default of 1,024 risks truncated, unparsable output. |
| Temperature | pinned explicitly (proposal: 0.0, the adapter default); provider guidance to be checked before the first call | The configuration audit flagged unpinned sampling as a limitation; the judge pins it. |
| Prompt | `grading.judge.JUDGE_SYSTEM_PROMPT` as committed (its sha256 recorded with each call) plus `render_unit` | Prompt revisions are allowed on Dev only (section 4). |
| Retries | Inspect `max_retries` 3; no SDK retries; no whole-call replays | Recovered transient errors are logged. |
| Credential | `GOOGLE_API_KEY` (Dev project), concurrency 1 | About 4.6 k input tokens per unit on average, serial, so it is negligible against the 2 M input-tokens-per-minute quota that Dev generation shares. |
| Ledger | Dev class ledger, one reservation per run's judge unit (`run_grading --judge --judge-estimate-usd`) | Dev ledger: 19.67 USD settled, 80.33 USD remaining of 100 (before the remaining Dev generation, about 10 USD forecast). |

## 3. Scope of one calibration pass (Dev only)

All judge units of the five full-calibration tasks' Dev outputs, plus the one preselected smoke-check judge item of
each other task (`queue_v2.json`, dev plan). Unit sizes are measured offline from the Dev outputs, or from the expert
files where no Dev output exists yet. Input tokens are estimated as characters / 4.

| Task | Plan | Units | Input tokens (est.) | Forecast USD (low / high) | Size basis |
|---|---|---|---|---|---|
| `f841ddcf…` | full | 7 | 43,442 | 0.21 / 1.46 | dev output |
| `47ef842d…` | full | 1 | 1,654 | 0.02 / 0.20 | dev output |
| `1137e2bb…` | full | 7 | 52,099 | 0.23 / 1.48 | dev output |
| `2ea2e5b5…` | full | 4 | 6,894 | 0.09 / 0.80 | expert files (dev output in generation) |
| `a45bc83b…` | full | 61 | 259,853 | 1.62 / 12.51 | expert files (dev output pending) |
| `7b08cd4d…` | smoke | 1 | 6,169 | 0.03 / 0.21 | dev output |
| `7d7fc9a7…` | smoke | 1 | 5,154 | 0.03 / 0.21 | expert files |
| `c3525d4d…` | smoke | 1 | 5,235 | 0.03 / 0.21 | dev output |
| `c357f0e2…` | smoke | 1 | 6,213 | 0.03 / 0.21 | expert files |
| `b5d2e6f1…` | smoke | 0 | 0 | 0 / 0 | the task has no judge item |
| **One pass** | | **84** | **386,713** | **2.29 / 17.29** | |

Pricing: input 2.00, output and thinking 12.00 USD per million tokens. Every unit is far below the 200 k-token
long-context tier. The forecast range assumes 1,500 output and thinking tokens per unit (low) or the 16,384-token cap
(high). This is a FORECAST, not a measured cost.

## 4. Procedure and stop conditions

1. Offline first: the ProviderJudge change for the thinking level and temperature, a mock-provider test of output-schema
   compliance, and the judge block in `config.json` (model id, settings, prompt sha256). These are verified without any
   call.
2. Pass J1 runs on the Dev outputs whose human labels are saved. Judge verdicts are written to the sealed files and are
   compared only after the labels' checkpoint (`grading.review compare --queue queue_v2.json --phase dev`).
3. Calibration: at most two prompt revisions (passes J2, J3) on the same Dev units. Each revision is recorded with its
   prompt sha256, the Dev disagreements that motivated it, and both passes kept. A revision changes the shared prompt
   only, never a criterion, reference or grading rule. The units used to debug the judge are Dev units and are never
   reused to validate it.
4. Freeze: the judge prompt and settings are frozen globally (tagged) before any Validation output is revealed; the
   per-task evidence builders are frozen separately.
5. Stop conditions:
   - a call with missing or uncertain usage halts later units (existing adapter policy);
   - a unit settles above 2x its reservation (existing ledger stop);
   - more than 20 % unparsable outputs in a pass;
   - the judge calibration ceiling is reached;
   - any provider billing or quota error other than a recovered transient one.
   Each stop is reported, not retried.

## 5. Code changes needed before any call (offline, tested)

- `ProviderJudge`: pass `reasoning_effort` (Gemini 3: thinking level) and record it per call.
- `config.json`: a `judge` block (model id, temperature, max_tokens, thinking level, max_retries, timeout, prompt sha256).
- A dry run of the judge path with a mock provider on one Dev run (no network).

## 6. Decisions requested

1. Approve the judge model `google/gemini-3.1-pro-preview` for Dev calibration, or name another.
2. Approve the settings: thinking level high, max_tokens 16,384, temperature (pinned value), Inspect max_retries 3.
3. Approve the scope: up to three passes over the 84 units above (J1 plus at most two revisions).
4. Approve a judge calibration ceiling. Proposal: 30 USD in total on the Dev ledger. It covers three passes of up to
   10 USD each; at the high forecast (17.29 USD per pass), the second revision pass would stop at the ceiling.
5. Approve running the judge on the Dev project key at concurrency 1 while Dev generation continues, or require
   waiting until Dev generation ends.
