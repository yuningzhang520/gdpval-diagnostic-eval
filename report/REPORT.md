# GDPval diagnostic evaluation: report

How this report maps to the assignment brief (`Field-Engineer-Take-Home-Project.pdf`):

| Brief part | Section |
|---|---|
| 1. Run an evaluation: what ran, how it was graded, what it cost | 2, 3, 5, 8.1 |
| 2. Failure modes, classified by hand | 6, 7.5 |
| 3. Gaps and opportunities: where the models fell short, which gaps data could close | 7.5, including "Data opportunity" |
| 4. Live pitch | not in this document; the per-model targets are in section 7.5, "Data opportunity" |
| Limits: sample size, grader reliability, cost | 4, 8 |

---

## 1. Summary

**Result.** After author review, Claude Opus 5.5 passes 7 of the 10 tasks and GPT-6.1 Sol passes 3; a task passes only
when all its critical criteria pass (adjudicated statuses, section 7.3; task verdicts in `site/data/metrics.json`,
`task_verdicts`). On the 35 critical criteria per model, Opus 5.5 passes 31 and GPT-6.1 Sol 26. The author confirmed
40 model failures (rubric items), which fall into 4 categories (section 7.5): A, required content omitted (Opus 5.5 3,
GPT-6.1 Sol 14); B, label or display not as required (4 and 7); C, document content omitted (3 and 5); D, an added
line that breaks a rule (0 and 4). Tagged by where the failed requirement is stated (section 7.5, "Requirement
source"; tagged after the runs), 12 of the 40 are stated in the prompt, all GPT-6.1 Sol's (4 tasks); 24 follow only
the rubric's wording or detail (Opus 5.5 8, GPT-6.1 Sol 16) and 4 the pre-registered additions rule R-2.7-21 (2 each).
Two of Opus 5.5's three failed tasks fail only on an exact label; without R-2.7-21, the task verdicts are Opus 5.5 7
pass / 2 fail / 1 not confirmed and GPT-6.1 Sol 3 / 6 / 1.
- **None of the 40 confirmed failures is a wrong calculation** (the page's title: "Omissions and form, not
  arithmetic"). They are content left out (25 rubric items), a different label or form (11), and one rounding approach
  that breaks an accounting rule (4). Totals reconcile even where a breakdown is missing.
- **Only GPT-6.1 Sol missed things the prompt asked for.** Each failure is tagged by whether the model was told: in the
  prompt; rubric only (GDPval's grading key expects it, the prompt does not say it); or the additions rule (R-2.7-21,
  set before the runs). 12 of GPT-6.1 Sol's 30 failures are in the prompt, such as store subtotals, and cost it 2 of its
  7 failed tasks (weekly sales, PO entry audit). All 10 of Opus 5.5's are rubric only or R-2.7-21. Twelve failures are
  borderline cases (section 7.5): counted all as rubric only or all as in the prompt, GPT-6.1 Sol's prompt failures range from 3 to 15 rubric items and 1 to 4 tasks; all 12 are GPT-6.1 Sol failures.
- **Rubric grading needs a human pass.** Of the 100 graded fails the author reviewed, chosen where a verdict could
  change (78) or a model failure was suspected (22), 67 (67%) were grader false fails (39% of all 170 reviewed items; the count flow is in section 7.7); in one
  task (`1137e2bb…`, GPT-6.1 Sol) a judge false pass hid the only failure. 8 of the 10 task failures (3 Opus 5.5, 7 GPT-6.1 Sol) turn
  only on rubric-only wording or detail, or R-2.7-21. The 67% describes those selected fails, not an overall grader error
  rate: the blind audit (section 7.6), which samples all rubric items, finds 17 of 20 in agreement.

**Terms.** The submission page (`site/`) uses plainer terms for the objects this report names: critical requirement =
critical criterion; before review / after review = as graded / adjudicated; undecided = not confirmed (a critical
criterion with no failed item and at least one `cannot_assess` item); code grader = deterministic checks; LLM judge =
judge; "cannot assess → pass" = `verified_pass`; "cannot assess → left" = `leave` (an unresolved item-level coverage
gap); confirmed failure = `confirmed_fail`, `verified_fail` or `grader_false_pass`; failure type = cluster (section
7.5); the additions rule = R-2.7-21; failure source (in the prompt, rubric only, additions rule) = the requirement-source
tags `prompt`, `rubric`, `rule` of section 7.5; GPT-6.1-sol = GPT-6.1 Sol (`openai/gpt-6.1-sol`).

**What was evaluated.** Two candidate models, Claude Opus 5.5 (`anthropic/claude-opus-5-5`) and GPT-6.1 Sol
(`openai/gpt-6.1-sol`), each ran once (k = 1, `attempts=1`) on 10 tasks from the public GDPval gold subset
(`openai/gdpval` at revision `11e7900cdcac61bc4daf59e65feb238acda98fbf`, the v2 release with rubrics). The tasks are
the complete Order Clerks block (5 tasks) and 5 supplementary tasks: 2 from Accountants and Auditors and 3 from
Computer and Information Systems Managers. That gives 20 samples and 580 rubric items per candidate
(`data/selected_tasks.json`, `data/manifest.json`).

**The question.** Can a model apply the explicit business rules and requirements of a task to a real work
deliverable, correctly and consistently? Where it cannot, which errors can be identified reliably and mapped to
useful data improvements? (`PLAN.md` section 1.) The ten tasks are a purposive diagnostic sample. They do not stand
for an occupation, for knowledge work in general, or for any GDP-weighted capability.

**How it was graded.** Each deliverable was graded item by item against the public GDPval v2 rubrics, with
documented pre-run adjudications for identified inconsistencies (`preregistration.md` 1.1). There are three
layers:
- 396 deterministic items, with LibreOffice recalculation on copies and comparison with independent
  recomputations from the task inputs;
- 166 judge-only items, judged by `google/gemini-3.1-pro-preview` under a frozen prompt and settings;
- 18 human-authoritative visual items.

On top of the items there are 35 preregistered critical criteria, a blind human item-level sample of 36 labels (20
on Formal outputs), and a human check of every critical FAIL before it is reported as confirmed. The scores are not
comparable to published GDPval win rates: the official metric is expert pairwise preference, and this evaluation
scores rubric criteria one by one (`PLAN.md` section 2).

**Details behind the result** (every number from the records named in sections 7.3, 7.5 and 7.7; every critical FAIL
below is human-confirmed at the item level, adjudication batch 2026-11-02T22:05:01Z).
- Critical criteria, final (35 per candidate, adjudicated): Claude Opus 5.5 31 pass / 4 fail / 0 not confirmed;
  GPT-6.1 Sol 26 pass / 9 fail / 0 not confirmed. The four baselines (section 7.3): pure automated 24 / 7 / 4 and
  15 / 14 / 6; as graded (plus the preregistered visual layer) 25 / 7 / 3 and 16 / 14 / 5; adjudicated as above;
  R-2.7-21 sensitivity 31 / 2 / 2 and 26 / 7 / 2. Of the 21 automated critical FAILs as graded, 12 were grader false
  fails. Of the eight criteria not confirmed as graded, four became fails on human-verified items and four became
  passes, among them Opus `7d7fc9a7…` C1, whose four unresolved items were verified pass by an invoice-by-invoice
  reconciliation (section 7.3). No critical criterion remains not confirmed.
- 40 human-confirmed model failures (rubric items, not independent incidents) fall into 9 clusters (section 7.5).
  The most consequential, M1 "required reporting levels or measures are omitted" (11 items, 3 tasks, 5 critical:
  store subtotals, per-stop withholding and net revenue, the daily-sales measure), is GPT-6.1 Sol only. The per-line
  additions column is absent in both candidates' prepaid schedules (4 critical items, under the binding pre-run rule
  R-2.7-21). Both share M2 literal-naming failures (Opus 3, GPT 7; 4 tasks), the sole cause of Opus 5.5's two
  label-related critical fails, and the unstated controls or test conditions of M3 and M5 (Opus 3, GPT 4; 2 tasks).
  The one judge false pass found (M7) is a narrative that applies a rule correctly but never states it.
- Grader noise exceeded model signal among the automated fails: of the 170 adjudicated worksheet rows, 67 were grader
  false fails and 21 verified passes, against 33 confirmed fails, 6 verified fails and 1 false pass; 42 stay
  unresolved item-level coverage gaps (section 7.7). Item-level scores (section 7.2) are reported as graded; the
  adjudicated critical statuses are the final ones.
- Where the candidates differ: GPT-6.1 Sol fails the critical criteria of `b5d2e6f1…` C3, `7b08cd4d…` C1,
  `1137e2bb…` C3 and `c357f0e2…` C2 and C3 where Opus 5.5 passes; both fail `47ef842d…` C4 on the same literal
  chart-label item, `2ea2e5b5…` C3 on the same literal table labels and `7d7fc9a7…` C2 and C3 on the same absent
  additions column.
- Gaps a dataset could target (section 7.5, "Data opportunity"): GPT-6.1 Sol: prompt-stated requirements first (12
  failed rubric items in 4 tasks: store subtotals, the daily-sales figure, account numbers in tab names, the case-pack
  rule in a summary). Opus 5.5: none of its failures is prompt-stated; the suite guards the breakdowns it delivers and
  scores rubric-only wording apart.

**State of the measurement on 2026-11-02** (`docs/status.md`, sections from "Formal generation complete" onward):

| Step | State |
|---|---|
| Formal generation | Complete: 20/20 samples. No hold, stop, limit event or engineering failure. 17.979211 USD settled (run-level metadata, not a quality result) |
| Deterministic grading | 20/20 sealed deterministic-only passes at `freeze-v1-grading-deterministic` |
| Formal judge pass | Complete: 20/20 runs judged, 11:57:25Z to 12:55:28Z at `freeze-v1-grading`. Second project to its 250/day quota, then the third project for the same pass. 330/332 judge items have a verdict; 2 `invalid_judge_output`, no provider error. 12.079453 USD settled of 30 (1.665296 USD estimated). The provisional label on its verdicts was lifted under `preregistration.md` 1.25 (section 8.2) |
| Formal blind labels (20) | Saved 2026-11-02T12:48:10Z, checkpoint SHA-256 `308771dd1f308ded222992eb2a1b947bb47b9f6eb5e7a16e985c8f356aabdb19`. Agreement with the frozen graders 17/20 (section 7.6) |
| Judge Validation agreement | 3/3 judge-only items, debug-set item excluded; coverage 163/166 |
| Independent recheck of V1.9 (`freeze-v1-grading`) | Done (Codex recheck 2). Closed by the author with its findings recorded as known limitations (section 8.2) |

---

## 2. Experimental setup and the frozen generation configuration

Sources: `config.json` (`generation`, `models.pilot_models`, `sandbox`, `retries`, `batches.formal`),
`harness/freeze/freeze-v1-generation.json`, and `docs/status.md`.

### 2.1 Candidates

| | Claude Opus 5.5 | GPT-6.1 Sol |
|---|---|---|
| Inspect model | `anthropic/claude-opus-5-5` | `openai/gpt-6.1-sol` |
| Reasoning request | `reasoning_effort` high, mapped to adaptive thinking with effort high | `reasoning_effort` high, mapped to Responses `reasoning.effort` high; `reasoning_summary` none |
| Configured list price, USD per MTok (input / output) | 4 / 20 | 2 / 10 (4 / 15 above 272k input tokens) |
| Ledger reservation per sample (a forecast) | 8.00 USD | 5.00 USD |

Both candidates get the same nominal reasoning level, but not equal compute. The mechanisms and the tokenizers
differ, and reasoning tokens are billed at different output rates. Cost and tokens are therefore reported per model
and never on one scale (`config.json` `models.pilot_models.compute_equivalence_note`). Provider server-side tools
(web search, code interpreter, file search) are off.

### 2.2 Shared frozen system prompt

- File `harness/system_prompt_draft.txt`. SHA-256 of the stripped text:
  `6b539cf9171a0f303a5afd3fe64d68536e3db00f9ba767478d8415331cd558e9`. File SHA-256: `67238ba0f24ad2c5…`.
- The prompt is identical for both candidates. It has no task-specific hint and no rubric content. Its only
  self-check is generic.
- Text (`config.json` `generation.system_prompt_text`):

  > You are completing a professional work task. Read the task description and the files under /workspace/inputs
  > (and /workspace/resources when present). Produce every requested deliverable as a file under /output/final/ using
  > the requested file formats and clear file names. The sandbox has no network access; Python with openpyxl,
  > python-docx, python-pptx, pandas, matplotlib, reportlab and pymupdf, and LibreOffice (soffice, with python3-uno
  > bindings) are available. Tools to view images and render document pages are provided. No one is available to
  > answer questions; make reasonable assumptions and state them in the deliverable. Before finishing, open your
  > deliverables again and check that the numbers, labels and formatting are correct and consistent with each other.
  > Finish by stating which files you produced.

- Task prompts: one per task, pinned by SHA-256 in `harness/freeze/freeze-v1-generation.json` (`staged_inputs`).

### 2.3 Limits and retries (identical for both candidates)

| Setting | Value |
|---|---|
| Samples per task, attempts | k = 1 (`epochs` 1), `attempts=1`, no scorer feedback, no resubmission |
| Output cap per request | `max_tokens` 32,000 |
| Token limit per sample | 20,000,000, type `all` (input plus output of every call, cumulative) |
| Time limit / working limit | 7,200 s / 7,200 s |
| Message limit | 200 |
| Tool timeout | 600 s |
| Inspect per-sample cost limit | 20 USD. This is a safety net: a hit is recorded as a `cost` limit and graded under the budget policy |
| Retries | Inspect `max_retries` 3 (transport-class errors only), request timeout 2,700 s, attempt timeout 900 s, provider SDK retries 0, whole-sample reruns off |

An exhausted limit ends the attempt as `execution.status=limited`. The attempt is still graded on what it delivered,
and it stays in every denominator (`preregistration.md` 1.3). A deliverable that was not produced fails the criteria
that depend on it. A launch, infrastructure or collection failure is a run error, never model non-delivery
(`preregistration.md` 1.2).

### 2.4 Tools, sandbox and isolation

- **Tools.** `bash`, `python`, `view_image` and `render_document`. Images are decoded and bounded on the host
  before they reach a provider.
- **Image.** `sha256:18cde712cde1867c94b8f23ae1f4066b0aa3146fdbd8deac70d1b4aa043ea9ee`, linux/arm64, created
  2026-10-30T08:28:15Z. The image is pinned by its full local ID (no repository digest exists for a local build) and
  is never pulled.
- **Container.** `network_mode: none`, 3 GiB memory, 2 CPUs, 512 PIDs, `cap_drop: ALL`, `no-new-privileges`. The
  container runs as root with every capability dropped, a known limitation. It has no volumes, and its only
  environment variable is `HOME`, so credentials stay with the host launcher (`docs/status.md` "Formal preflight").
- **Inputs.** They enter only through the per-task staged-file allowlist, and each file is verified against its
  SHA-256 in `config.json` before the sample starts. Expert deliverables, rubrics, the parquet,
  `preregistration.md`, grader code, other runs' outputs and credentials are never in the sandbox.
- **Collection.** Files are collected from `/output/final/` with fail-closed validation: at most 200 files, 64 MiB
  per file, 512 MiB in total, 600 s (`config.json` `collection`). Raw outputs are immutable once collected.

### 2.5 Staged inputs

There are 43 staged files over the ten tasks (`config.json` `tasks[].staged_files`;
`harness/freeze/freeze-v1-generation.json`):
- 1 file each for `b5d2e6f1`, `f841ddcf`, `47ef842d`, `1137e2bb`, `7b08cd4d`, `2ea2e5b5` and `c357f0e2`;
- 3 for `c3525d4d`;
- 6 for `7d7fc9a7`;
- 27 for `a45bc83b`: 2 task inputs, 11 official Google Cloud HTML pages, 11 extracted text files and 3 official icon
  packs. These are the 2026-10-29 snapshot, identical for both models (`config.json` `pre_staged_resources`).

The Formal preflight verified the 43 files for each candidate, 86 checks in all (`docs/status.md` "Validation
comparison ..., Formal preflight at V1.2").

### 2.6 Two-stage freeze

| Tag | Commit | Freezes | Record |
|---|---|---|---|
| `freeze-v1-generation` | `dda234f` (code baseline `b33cc37`) | Generation conditions: candidate models and pricing, generation, retries, limits, system and task prompts, staged inputs, pre-staged resources, image, collection, `batches.formal`. Config SHA-256 `77f76531…`. Python 3.11.4, inspect_ai 0.3.286, anthropic 2.3.0, openai 3.41.0, google-genai 2.34.0, Docker 29.6.1 | `harness/freeze/freeze-v1-generation.json` |
| `freeze-v1-grading-deterministic` | `ef53050` (grading code `2eb4060`) | Deterministic-only grading: engine `engine-2026-11-02.12`, the ten task grader versions, the SHA-256 of the grading sources and of 99 rubric and reference files | `grading/freeze/freeze-v1-grading-deterministic.json` |
| `freeze-v1-grading` | `cc684ef` | Grading and the Formal judge (V1.9). Deterministic scoring is identical to the previous tag. Judge request surface identical to `v1-calibration-freeze` | `grading/freeze/freeze-v1-grading_manifest.json` |

Neither tag moves, and later corrections get new tags (`config.json` `_status`). The two-stage freeze let Formal
generation start while the delta-review corrections to the grading code were still in progress. A dependency check
showed that no `harness` module imports `grading` (`docs/status.md` "Formal generation: two-stage freeze").

### 2.7 How Formal generation actually ran

From `docs/status.md`, sections "Formal generation launch arrangements", "Formal generation: two independent
workers" and "Formal generation complete":

1. All runs started from a clean worktree detached at `freeze-v1-generation` (`dda234f`), with its inputs and
   `config.json` read-only. Launcher `--dry-run` passed for all 20 units before the first provider call.
2. **Units 1-2: single-ledger scheduler.** `harness.scheduler` ran at concurrency 1 on one Formal ledger
   (`formal/ledger.json`, 150 USD admission threshold), in the fixed task order with both candidates of a task
   adjacent. It ran the two `b5d2e6f1…` units, Opus 5.5 and then GPT-6.1 Sol. `stop_new` was set at 10:04:47Z, and the
   scheduler exited at 10:09Z once its in-flight unit had finished.
3. **Units 3-20: one `harness.batch` worker per candidate**, on the author's decision, to meet the submission deadline. Each worker ran the
   remaining 9 tasks in the frozen order with its own runs root, ledger, inventory, batch records and Inspect logs.
   - Ledgers `formal/opus/` and `formal/gpt/`, each with a 200 USD ceiling.
   - The ceiling came from a config snapshot (`config_formal-two-workers_80433476eaa1.json`, SHA-256 `80433476…`)
     that differs from the frozen config only in `batches.formal.budget_ceiling_usd` (150 changed to 200). Staging
     verification still read the frozen config.
   - Concurrency was 2 overall, with at most one unit per candidate active at any time.
   - No generation code changed.
4. **Outcome.** All 20 samples finished by 11:04:41Z, and both workers exited 0. There was no hold, estimated
   settlement, stop, engineering failure or limit event, and all three ledgers are clean.
5. **Acceptance.** `harness.unit_gate.evaluate_unit` accepted all 20 units: completed, no limit, collection
   complete. One canonical designation per run was recorded (append-only).
6. **Cost.** 17.979211 USD settled in total: Opus 5.5 14.900901 USD, GPT-6.1 Sol 3.078310 USD (section 8.1). These
   are run-level metadata, not quality results.

---

## 3. Task coverage and rubric structure

### 3.1 Selection

The selection rule was fixed before any model run (`preregistration.md` section 2): one occupation's complete
block of tasks, plus five tasks from other occupations. Each supplementary task adds a different domain or
deliverable shape to the same two requirements, namely (1) rule execution traceable to the inputs and (2) consistency
across detail, summary and narrative. No task is swapped or dropped on the basis of results.

Candidates that were examined and not selected, with the factual basis for each (`preregistration.md` section 2):
- Two Computer and Information Systems Managers tasks have no reference files.
- An audit-sampling task has a rubric that contradicts its own prompt on column positions.
- A tax-return task needs tax-law judgment that cannot be derived from its inputs.
- A month-end task names an input file that is missing.
- None of the five Financial and Investment Analysts tasks can be done offline with its provided inputs.

Pre-declared substitutes existed for the GCP design task, and so did a single-model fallback. Neither was used.

### 3.2 Tasks, rubric items and routing

Derivation:
- **R** (rubric items): `data/manifest.json`, rubric entries, `item_count`.
- **J** (judge-only items): `grading/freeze/freeze-v1-grading_manifest.json`, `tasks.<id>.judge_items`.
- **V** (human-authoritative visual items): `grading/review_queue/queue_v4.json`, `plans.<id>.visual_items`.
- **D** (deterministic items) = R - J - V.

The totals agree with the grader coverage record of 2026-11-02: 580 items, D 396, J 166, V 18, each item assigned
once (`docs/status.md` "Final verification on `df4a560`"). The criterion counts and their distinct member items come
from `queue_v4.json` `plans.<id>.criteria` (current definitions).

| # | Task (full UUID) | Occupation | Deliverable family | R | D | J | V | Critical criteria | Distinct critical member items |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `b5d2e6f1-62a2-433a-bcdd-95b260cdd860` weekly sales analysis | Order Clerks | spreadsheet | 32 | 31 | 0 | 1 | 4 | 21 |
| 2 | `f841ddcf-2a28-4f6d-bac3-61b607219d3e` June shipment recap | Order Clerks | spreadsheet | 59 | 51 | 7 | 1 | 5 | 24 |
| 3 | `47ef842d-8eac-4b90-bda8-dd934c228c96` weeks of supply | Order Clerks | spreadsheet | 58 | 54 | 1 | 3 | 4 | 29 |
| 4 | `1137e2bb-bdf9-4876-b572-f29b7de5e595` PO entry audit | Order Clerks | spreadsheet | 62 | 55 | 7 | 0 | 3 | 53 |
| 5 | `c3525d4d-2012-45df-853e-2d2a0e902991` holiday floor-stand budget | Order Clerks | spreadsheet | 52 | 46 | 5 | 1 | 3 | 28 |
| 6 | `7b08cd4d-df60-41ae-9102-8aaa49306ba2` tour profit and loss | Accountants and Auditors | spreadsheet | 59 | 43 | 14 | 2 | 3 | 20 |
| 7 | `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` prepaid amortization | Accountants and Auditors | spreadsheet | 56 | 41 | 14 | 1 | 4 | 25 |
| 8 | `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` work-time study deck | Computer and Information Systems Managers | presentation | 60 | 56 | 4 | 0 | 3 | 59 (60 under the preregistered C2) |
| 9 | `c357f0e2-963d-4eb7-a6fa-3078fe55b3ba` UAT test plan | Computer and Information Systems Managers | spreadsheet | 70 | 15 | 54 | 1 | 3 | 42 |
| 10 | `a45bc83b-22f9-4def-8d89-9c5661b2b86f` GCP migration design | Computer and Information Systems Managers | document | 72 | 4 | 60 | 8 | 3 | 19 |
| | **Total** | 3 occupations | | **580** | **396** | **166** | **18** | **35** | **320** |

Rubric weights (W) as stated in `preregistration.md` section 3, in table order, are 65, 88, 99, 80, 86, 89, 95, 85,
101 and 87. Recomputed on 2026-11-02 as the sum of each rubric file's `score` field (`private/rubric/<task>.json`): the
same ten values, 875 in all, which is also the W of every formal run (section 7.2).

Notes on routing (`preregistration.md` sections 1.19-1.20 and 2.x; `docs/status.md`):
- `b5d2e6f1…` has no judge item and is graded deterministically, apart from one visual item.
- `c357f0e2…` item 69 passes deterministically when the "Cross-functional Testing" label or a legitimate synonym is
  present. Otherwise it is routed to the judge (`route_to_judge`) and scored once, as a judge row.
- `a45bc83b…` item 70 is counted once, from the human visual verdict. Its judge verdict is used only for judge-human
  agreement.
- When a required chart is delivered only as a picture, the items that depend on it are `cannot_assess` and tagged
  `visual_review`, never an automatic fail (`preregistration.md` 1.20).
- The Formal judge runner lists 332 judge items over the 20 runs, 166 per candidate (`docs/status.md` "Formal
  generation complete").
- Under the preregistered C2 definition every one of the 60 `2ea2e5b5…` items is a critical member. Under the
  revised definition 59 are.
- 6 of the 8 `a45bc83b…` visual items are critical members.

### 3.3 Critical criteria (35)

The criteria are pre-registered with the business requirement, the evidence location, the check method and the
reason a failure cannot be compensated (`preregistration.md` section 3, all APPROVED). A criterion fails when any of
its members fails. It is `not_confirmed` while a member is pending or unassessable.

| Task | Criteria |
|---|---|
| `b5d2e6f1…` | C1 Structure; C2 Brand totals (source data is the reference); C3 PivotTable; C4 ST% logic (ratio of sums) |
| `f841ddcf…` | C1 June shipped total; C2 Auditable PO-level evidence; C3 Slipped cohort; C4 Row or account arithmetic; C5 Narrative consistency |
| `47ef842d…` | C1 Scope (five UPCs); C2 Rate and WOS; C3 Out-of-stock; C4 Chart |
| `1137e2bb…` | C1 Line flags; C2 SKU summary; C3 Word summary |
| `c3525d4d…` | C1 Store reconciliation; C2 Budget arithmetic; C3 Email consistency |
| `7b08cd4d…` | C1 Withholding and net revenue; C2 Expenses; C3 Net income |
| `7d7fc9a7…` | C1 Completeness; C2 1250 reconciliation; C3 1251 reconciliation; C4 Summary linkage |
| `2ea2e5b5…` | C1 Deck structure; C2 Activity shares (revised 2026-11-01, R-2.8-1: item 10 removed; both definitions are reported, `preregistration.md` 1.18); C3 Classification |
| `c357f0e2…` | C1 Plan structure; C2 Permission boundaries; C3 Module and negative coverage |
| `a45bc83b…` | C1 Deliverable set; C2 Hard requirements met as an architecture, consistently; C3 Diagram |

`f841ddcf…` carries five criteria, where `PLAN.md` section 4 says each task carries two to four. This is a documented
deviation from the design guideline, not an error in the record: the five criteria (C1 June shipped total, C2
auditable PO-level evidence, C3 slipped cohort, C4 row or account arithmetic, C5 narrative consistency) were drafted in
`preregistration.md` 2.2 because the task's business requirement has five independent, non-compensable parts, were
approved there before `freeze-v1-grading`, and are reported as frozen. `PLAN.md` is not amended retroactively; the range
it states remains the planning guideline for the other nine tasks, all of which carry three or four.

---

## 4. Validation methodology and historical audit

Sources: `PLAN.md` section 4, `preregistration.md` 1.6, 1.16 and 1.19-1.25, `docs/status.md`,
`docs/codex_review_2.md` and `docs/expert_gold_fail_audit.md`.

### 4.1 Gold-first grader development

For each task the grader was first run on the expert deliverables, and the original first-pass result was
preserved. Numeric expectations were reconciled with recomputations from the source files (`scripts/recalc/`), never
copied from the rubric. Each finding was classified as an expert-deliverable defect, a rubric ambiguity, a
source-data issue or a grader defect.

A catalog of seeded corruptions and layout transformations, derived from the expert files, declares the expected
item-level verdict transitions. Neutral transformations must leave the complete verdict map unchanged. For example,
at `code_9b1df11` the catalog holds 51 variants for `1137e2bb…` and 43 for `7d7fc9a7…` (`docs/status.md` "Codex
Review 1 fixes"; records under `grading/validation/<task_id>/`).

Grader v0 of a task was committed and tagged before that task's development output was opened.

The expert-gold FAIL audit (`docs/expert_gold_fail_audit.md`) classified every deterministic non-pass of the expert
deliverables. It found expert errors, rubric items that go beyond the prompt, one dataset artifact and unresolved
cases. It found no grader-reading defect. The author's decisions on the audit are recorded in `preregistration.md`
section 4.

### 4.2 Development and sealed Validation samples (Gemini outputs)

- **Model.** `google/gemini-3.8-flash`, under the candidate generation configuration with three differences for the
  Gemini classes: no message limit, Inspect `max_retries` 10, and a 10 USD per-sample cost limit. Each class has its
  own ledger with a 100 USD ceiling (`config.json` `batches.dev`, `batches.validation`).
- **Dev.** 10 canonical samples, one per task, used for calibration. Earlier attempts stay in the run inventory: a
  200-message diagnostic run of `b5d2e6f1…` outside the canonical ten, and earlier failed attempts. Calibration on
  the Dev outputs changed 122 of the 396 deterministic verdicts between the V0 pass and the frozen V1 re-grade, and
  `cannot_assess` fell from 59 to 27. These are retrospective re-grades, not held-out evidence (`docs/status.md`
  "Validation reveal ..." table).
- **Validation.** 10 independently generated samples, sealed (content, trajectory and logs unopened) until the shared
  judge and every task's V1 grader were frozen (`v1-calibration-freeze` = `0c8efcb`, `grading/freeze/v1_manifest.json`).
  - The author labelled the 10 queue-v4 Validation items from verdict-free packets. The labels were checkpointed at
    2026-11-01T23:26:55Z, before any verdict was revealed.
  - **Held-out deterministic stratum: 4/6 agreement against grader V1.** The two disagreements (`2ea2e5b5…` item 45,
    `c3525d4d…` item 32) were false fails. They were diagnosed as grader implementation defects and corrected as V1.3
    for both candidates, and that held-out result stays as first recorded.
  - Re-grades under V1.3 and V1.3.1 are regression evidence only (`preregistration.md` 1.21, 1.23).
  - Judge-only stratum (4 items: `1137e2bb…` 28, `47ef842d…` 57, `7d7fc9a7…` 18, `c357f0e2…` 24): the Judge
    Validation pass (complete 2026-11-02, 104/104 calls on the third project) returned pass on all four, and all four
    human labels are pass; the statistic is 3/3 with item 28 excluded (section 4.4).
  - `PLAN.md` section 6 states that every judge-only criterion of `1137e2bb…` was used to debug the judge assembly,
    which leaves that task no held-out judge criterion. `1137e2bb…` item 28 is listed in `grading/debug_set.json`, so
    it is excluded from the judge agreement statistic although its verdict and label agree.
- **Compatibility.** One sample of each candidate ran on task `87da214f-fd92-4c58-9854-f4d0d10adce0` (Customer
  Service Representatives), outside the formal ten. Both completed with no limit event. One GPT-6.1 Sol request
  failed with a provider HTTP 502 and was recovered by Inspect's retry. These runs check provider, tool, artifact and
  accounting behaviour only, never capability (`docs/status.md` "GPT compat reconciliation ...").
- **Limitation.** The development model and the judge come from the same provider family. Agreement measured on Dev
  and Validation outputs may be inflated by shared style or shared blind spots, and it does not transfer directly to
  the candidates (`PLAN.md` section 6).

### 4.3 Judge calibration and freeze

- **Judge Dev Pass 1.** 167 primary units over the nine Dev outputs that have judge items, all `ok`. A fixed
  self-consistency subset of 20 units, drawn with seed 20261101 before any verdict, was re-run with identical
  requests. All 20 pairs agree (PASS 16, FAIL 4 in both runs). This measures stability, not correctness.
- **Agreement on the 6 Dev labels:**
  - first pass 4/6. This is the independent figure;
  - both disagreements (`2ea2e5b5…` items 57 and 59) traced to an evidence-builder defect: the deck's headings were
    text boxes, and the excerpt showed title placeholders only;
  - after the builder fix, a targeted Pass 2 agrees 2/2, so 6/6 overall. That figure is post hoc, not independent.
- **Prompt.** The shared judge prompt was never revised. Its SHA-256 is
  `1de955e607e16bd8d236469603bde099b3d309a885be170c21d7e759c57487b5`, unchanged since Pass 1.
- **Freeze.** The shared judge was frozen at `v1-calibration-freeze` (`0c8efcb`), before any Validation output was
  revealed.
- **Later changes.** The judge versions after that tag (V1.1-V1.9) changed only infrastructure: call handling,
  recovery, accounting, quota handling and project selection. The request surface stayed identical. That claim rests
  on two checks:
  - `judge-surface --request-only`, an auxiliary AST digest (Review 2 N2);
  - the full source-file hashes in each freeze record.

### 4.4 Judge Validation (one pass)

- **Authorization.** One pass over the nine Validation runs that have judge items (166 units). It has a separate
  ledger with a 15 USD ceiling, runs at concurrency 1, and allows no repeat pass (`config.json` `judge.validation`).
- **History.**
  - Started 2026-11-01 21:25:39Z.
  - Halted twice on provider HTTP 429 errors. A later 429 identified the Dev Google project's daily quota: 250
    requests per day for `gemini-3.1-pro`, from the provider's own quota detail.
  - Resumed through the approved per-item recovery and daily-quota pause.
  - On 2026-11-02 at 11:57:05Z, handed off within the same pass to a third Google project from `freeze-v1-grading`.
- **Remaining at handoff:**
  - the `c357f0e2…` recovery (52 items);
  - seven runs not yet judged (52 items).
- **Exhausted** (`provider_error`, never a rubric fail): `a45bc83b…` item 20 and one `c357f0e2…` item.
- **Agreement:** 3/3 on the judge-only Validation labels (`c357f0e2…` 24, `7d7fc9a7…` 18, `47ef842d…` 57; all
  pass / pass); `1137e2bb…` item 28 also agrees but is excluded as a judge debug-set item. Coverage 163/166 Validation
  judge items; the three without a verdict are two `provider_error` and one `invalid_judge_output`, never fails
  (`docs/status.md` "Judge Validation complete").

### 4.5 Independent reviews (OpenAI Codex, read-only)

The author reviewed every finding before any change was made. Each correction is recorded in `preregistration.md`
with its old rule, its evidence and its new rule, and each has regression tests that fail on the pre-fix code.

| Review | Target | Verdict | Findings and corrections | State |
|---|---|---|---|---|
| Stage-1 re-check | materials and recalculations, 2026-10-29/30 | findings | Several corrections followed (`docs/status.md` "Independent re-check"): exact rational arithmetic for `7d7fc9a7…` (929,354.31); withdrawal of the blanket ±0.50 USD tolerance; source-based store counts for `47ef842d…`; operational definitions for under-specified tasks | closed |
| Harness and pilot-grader reviews | 2026-10-30 to 2026-11-01 (Stage 2, Pilot-A pre-review, final, close-out, extraction, Stage 3b, B2) | blocking findings | collector containment, run binding, ledger atomicity, usage recovery, extraction pipeline, pass selection | closed (B2: "READY FOR B2 COMMIT") |
| Review 1 | shared spreadsheet grading core (`bd5713b`) | BLOCKED | B1-B4 and P1 fixed (`9b1df11`). The closure checks found two further B2 remainders, also fixed. READY at `a9a1f88` | closed, accepted by the author |
| Review 2 | `5121e1a` | BLOCKED | R2-B1 (WAL merged schema-retry attempts), R2-B2 (a failed latest recovery hidden by an older complete pass), R2-B3 (inferred cost marked reliable), R2-B4 (budget guard excluded inferred liability), R2-B5 (labels accepted across runs). Corrected in V1.4 (`7e30849`). Non-blocking N1-N5: N1 and N3 fixed (N3 at `b33cc37`), N2 and N4 accepted as limitations, N5 closed by Docker evidence | B1-B5 confirmed by the later recheck |
| Delta review | `b33cc37` | BLOCKED | D1 (per-request budget bound), D2 (Judge Validation stops), D3 (recovery base selection), N1 (no-hold exception basis). Corrected at engine .12 (`2eb4060`, `v1.7-delta-review-corrections`) | D1, D3 and N1 confirmed by the recheck |
| Recheck | `v1.8-formal-roots` (`b7ce2db`) | BLOCKED on one D2 path | It confirmed D1, D3, N1, N3 and the six original Review 2 probes. The blocking path: a standalone `recover()` halt was not persisted as a terminal stop. Corrected in V1.9 (`e081f6d`) and frozen with explicit judge projects at `cc684ef` | **open: V1.9 not yet independently rechecked** |

`docs/status.md` states that no claim is made that the grading pipeline passed independent review in full. The V1.9
changes (D2 terminal stops, the formal stop result, task-order judging, explicit judge projects) were rechecked by Codex
(recheck 2, 2026-11-02): three Blocking and one non-blocking findings on stop / pause control under conditions absent
from this run, closed by the author without a code change and recorded as known limitations (section 8.2).

### 4.6 Historical impact audits

- **Review 2 corrections** (`logs/r2-fixes/audit/`). A read-only audit with the V1.3 and V1.4 code covered 772 record
  files, which were identical before and after.
  - Settled amounts, the authoritative pass selection of 34 run directories and 15 label comparisons are unchanged.
    Run and pass identity was verified on all 15 comparisons.
  - Only the estimated portions of three ledgers changed. These are derived values, reported beside the originals:
    dev 0 → 5.452624 USD, validation 0 → 4.808123 USD, judge_validation 0.913046 → 1.191394 USD.
  - Replaying the B4 guard over every recorded judge batch, no historical request would have been refused.
  - Re-verified on `df4a560`, with 694 record files unchanged.
- **Delta-review corrections.** A replay of the new D1 bound over every historical judge batch found no request that
  would have been refused. No recorded settlement, selection, verdict or agreement changed.

### 4.7 Open validation items

- Judge Validation agreement: 3/3 judge-only items, debug-set item excluded (section 4.4).
- Independent recheck of V1.9: done, closed by the author with its findings recorded as known limitations (section 8.2).
- 20 Formal blind labels and their agreement statistics: section 7.6 (17/20).
- Human verification of every critical FAIL cited in sections 1, 6 or 7: complete on 2026-11-02 (sections 7.3, 7.6).
- The rubric-to-capability map (`grading/capability_map.json`, `preregistration.md` 1.17) was authored before
  generation (committed once in `9b1df11`, 2026-11-01T11:22:58Z, unchanged through `freeze-v1-generation` and the
  reveal) and approved by the author on 2026-11-02, after the reveal, without changes. It is used in section 7.4.

---

## 5. Evaluation methods

### 5.1 Deterministic checks

`grading/grade.py` with the shared engine (`grading/engine/`) and one thin specification per task
(`grading/checks_<task8>.py`):
- **Outcome gate.** The run's `run_outcome.json` is loaded with its identity taken from the completed Inspect log.
  Missing, corrupt, non-final or mismatched outcomes fail closed.
- **Extraction on copies.**
  - xlsx: formulas and cached values; LibreOffice recalculation in the same pinned image, which separates "wrong
    formula", "missing cached value" and "recalculation failed"; pivot and chart objects from the package XML;
    drawing text boxes.
  - docx: paragraphs, tables and text boxes.
  - pptx: shapes, tables, and both `pieChart` and `pie3DChart`.
  - pdf: the text layer.
- **Gold-first, independent references.** Key figures are compared with recomputations from the task inputs
  (`scripts/recalc/`, outputs under `private/checks/recalc/`), never with figures copied from the rubric or the expert
  file. Detail-to-summary and workbook-to-document consistency are also checked.
- **Numeric policy.** `Decimal`, or exact rationals for divisions. Quantization happens only at the comparison point,
  defined per item. There is no global tolerance or rounding mode, and identities are checked on unrounded values
  (`preregistration.md` 1.7).
- **Verdict semantics.**
  - A confirmed violation of the item's own text gives FAIL, even when another input could not be assessed.
  - An unreliable input without a confirmed violation gives `cannot_assess`.
  - Every required comparison must be completed before a PASS.
  - Each verdict carries locatable evidence (file, sheet, cell, page, slide or paragraph) and an attribution:
    `model_caused*`, `grader_*` or `unknown`.
- **Versions** (`config.json` `grading`):

  | Component | Version |
  |---|---|
  | engine | `engine-2026-11-02.12` |
  | `1137e2bb…` | .3 |
  | `7d7fc9a7…` | .7 |
  | `2ea2e5b5…` | .6 |
  | `a45bc83b…` | .3 |
  | `b5d2e6f1…` | .2 |
  | `f841ddcf…` | .2 |
  | `47ef842d…` | .3 |
  | `c3525d4d…` | .6 |
  | `7b08cd4d…` | .3 |
  | `c357f0e2…` | .3 |

  Every pass records `<engine>+<task>` and the full git commit.
- **Formal.** 20/20 deterministic-only passes from the clean checkout at `freeze-v1-grading-deterministic`. Every
  exit was 0 and spreadsheet recalculation was `ok`. The passes are sealed (`docs/status.md` "Formal generation
  complete").

### 5.2 LLM judge

- **Model and settings** (`grading/freeze/freeze-v1-grading_manifest.json`, `config.json` `judge`):
  - model `google/gemini-3.1-pro-preview`, thinking level high (`reasoning_effort` high), temperature 1.0;
  - `max_tokens` 16,384, thinking included;
  - Inspect `max_retries` 10. It was 3 at the calibration freeze and raised to 10 in V1.2, an infrastructure-only
    change;
  - prompt SHA-256 `1de955e6…`, and one call per judge-only criterion.
- **Evidence inputs** (`preregistration.md` 1.5):
  - each unit carries the task requirement (a prompt excerpt), the criterion, the source material or independent
    computation the criterion needs, and the deliverable excerpt (extracted text with formulas and recalculated
    values);
  - evidence must be locatable;
  - model identity is hidden;
  - visual criteria are not judged from text;
  - candidate artifacts and sources are treated as data.
- **Response protocol.**
  - The judge answers pass, fail or cannot_assess, with evidence.
  - A schema-invalid response gets one retry with the identical request. Two invalid responses give
    `invalid_judge_output`.
  - A completed, schema-valid call is never re-judged.
  - A `provider_error` item is retried once, and a `not_attempted` item gets its first evaluation, within the pass
    (`preregistration.md` 1.20).
- **Write-ahead log and accounting.**
  - Every provider request is its own write-ahead attempt (`attempt_id`). A started attempt without a terminal event
    stays UNKNOWN and blocks.
  - Each judge workload has its own ledger: Judge Dev 30 USD, Judge Validation 15 USD, Formal 30 USD.
  - Unknown usage is settled conservatively and is never counted as zero (`preregistration.md` 1.22).
- **Budget guard** (D1, `preregistration.md` 1.24). Before each request, the whole settlement after that request,
  for both outcomes, must stay within the ceiling. The per-call bound is the request's UTF-8 bytes plus 1,024 control
  tokens of input, plus `max_tokens` of output, priced at long-context rates.
- **Reliability controls.**
  - 2 s pacing between requests.
  - A 600 s wall-clock cap per item.
  - Failures are classified as retryable (408, 429, 5xx), item-permanent (other 4xx) or fatal (authentication,
    billing). New requests stop after 3 distinct failed items.
  - All Formal processes run on AC power under `caffeinate`, because the item cap uses a monotonic clock that stops
    while macOS sleeps.
- **Quota pause and project selection** (`preregistration.md` 1.23, 1.25):
  - A per-day 429 halts the batch and checkpoints `quota_pause`. The pass resumes at the later of the provider's
    retry guidance and the next midnight Pacific, plus 5 minutes, as the same logical pass.
  - Each runner selects its Google project explicitly (`--credential-env`). A pause on one project does not hold the
    pass on another (`project_switch`). A terminal stop refuses on every project.
  - One worker runs at a time per pass.
- **Formal runner** (`grading.judge_formal`):
  - one pass of 332 items, in task order with both candidates adjacent;
  - returns non-zero after a stop, and resume refuses every stop kind;
  - grades and verdicts go only to the sealed Formal grading folder.

### 5.3 Human review

- **Queue.** `grading/review_queue/queue_v4.json`: policy `review-queue-2026-11-01.4`, seed 20261101, frozen
  2026-11-01T19:09:54Z. Membership comes only from the rubric inventory, the deliverable families and the seed; no
  outcome is used. Queues v1-v3 were never labelled and are kept.
- **Labels: 36 in all**, item-level, blind:
  - Dev 6: two judge-only items per deliverable family, used for judge calibration;
  - Validation 10: one item per task, alternating between the deterministic and judge-only strata;
  - Formal 20: one item per task, with the same item id on both candidate outputs, candidate identity hidden and
    presentation order randomized with the seed. Five tasks sample a critical-criterion member item (`47ef842d…`,
    `b5d2e6f1…`, `c3525d4d…`, `c357f0e2…`, `f841ddcf…`) and five sample a judge-only item (`1137e2bb…`, `2ea2e5b5…`,
    `7b08cd4d…`, `7d7fc9a7…`, `a45bc83b…`).
- **Packets.** They give the rubric text, the independent reference, judge excerpts for judge items, the deliverables
  and the task inputs. They give no automated verdict and no grader location. The 20 Formal packets are built, with a
  sealed letter mapping, and a count-only scan of the packet text found no run id, model name or formal path. Labels
  are checkpointed with SHA-256 and a timestamp before any verdict is shown.
- **Outside the agreement sample:**
  - every critical FAIL cited in the comparison, the headline results or the failure taxonomy is verified by a human
    against the deliverable, the source data and the rubric before it is reported as confirmed;
  - about 20-30 failure events are investigated in depth;
  - visual items without a human verdict are reported as `not evaluated`;
  - an image-only critical member needs the author's visual judgment before its criterion status is reported.
- **Reporting.** n = 36 labels is a limited reliability check, not a precise accuracy estimate. Agreement measures
  consistency, not correctness.
- **Human review time:** about 3 hours in total (author estimate, not measured; section 8.1), covering the 20 formal
  blind labels, the 12 visual verdicts, the 170 worksheet decisions and the five representative verifications, and
  excluding the reading of the AI-assisted drafts. No per-phase split was recorded.

### 5.4 How the layers combine

| Item route | Verdict source | Counted in E (graded weight) | Effect on critical status |
|---|---|---|---|
| Deterministic | grader | `pass` / `fail` yes; `cannot_assess` no (stays in W, listed with its reason) | a member `fail` fails the criterion; `cannot_assess` leaves it `not_confirmed` |
| Judge-only | judge | `pass` / `fail` yes; the judge's own `cannot_assess` no | as above |
| Judge infrastructure verdicts (`provider_error`, `not_run`, `judge_parse_error`, `invalid_judge_output`) | none | no. They are excluded from E like any ungraded row | `not_confirmed`, **never a FAIL** |
| Visual | human | `pass` / `fail` yes; no human verdict: `not evaluated` (stays in W) | `not_confirmed` |
| Picture-chart-dependent items | grader (`cannot_assess`, `visual_review`) | no, until a human verdict | the author's visual judgment is needed before the criterion status is reported |

- **Scores per task and model.** W is the total rubric weight, E the weight judged pass or fail, P the weight
  confirmed pass. Reported: P/E, the coverage E/W, and the list of ungraded items with reasons
  (`preregistration.md` 1.2). Critical status (pass / fail / not_confirmed) is reported separately and is not a
  "GDPval score".
- **2ea2e5b5 C2.** Its critical status is computed under both the preregistered and the revised definition from the
  same item verdicts, and any change in conclusion is flagged (`preregistration.md` 1.18).
- **Missing evidence.** Missing judge verdicts and provider errors are never counted as FAILs (`preregistration.md`
  1.20, 1.25). A deliverable that was not produced fails its dependent criteria only when collection establishes that
  it was not produced.
- **One pass per run.** A report uses exactly one pass per run, chosen by `authoritative_selection`: the latest
  judged pass with its basis and warnings, `blocked` while an attempt is UNKNOWN or unreconciled. Two passes of one
  run are never two samples.
- **Disagreements.** A disagreement between the judge and the deterministic checks is adjudicated and recorded. An
  adjudication never overwrites the original verdict.

### 5.5 Post-run adjudication policies (decided by the author on 2026-11-02, after the reveal)

These decisions were taken while adjudicating the 170 worksheet rows (section 7.7). They are applied identically to both
candidates and are recorded here so that the adjudicated statuses can be re-derived; the frozen verdicts and the
preregistered rules are unchanged.
- **`preregistration.md` 2.2 "obvious forms".** The headers "Order cost" and "Shipped cost" (`f841ddcf…`, GPT-6.1 Sol,
  items 11, 13, 21 and their dependants) are accepted as obvious forms of "Order Value at Cost" and "Shipped Value at
  Cost", and the long-form source headers of the Data sheet ("Store Number", "Week / Month / Year to Date …";
  `b5d2e6f1…` item 22, both candidates, worksheet rows 147-148) as obvious forms of the required field names. The
  grader's finite label vocabulary did not cover them; the fails are grader false fails.
- **The labelled fractional-cent rounding line** (GPT-6.1 Sol `7d7fc9a7…`, row 51 of the 1250 schedule and row 35 of
  the 1251 schedule) is treated as a schedule line throughout: where it violates the no-negative-amortization and
  no-unfunded-increase rules (items 31, 32, 49, 50: confirmed fails, cluster M4) and where the totals include it
  (items 22, 40: the totals equal the per-line sums, grader false fails).
- **`c357f0e2…` item 12 is graded by label** under `preregistration.md` 2.9 ("naming and semantics are graded
  separately"): the plural role labels "Viewers / Project Managers / System Admins / Super Admins" fail the exact-match
  item (confirmed fail, cluster M2); permission correctness is judged by meaning on items 49-58.
- **R-2.7-21 (per-line additions never inferred) is binding** (section 7.3); the sensitivity line there states the
  effect of the opposite choice.
- **Judgment calls** (recorded with their evidence in the adjudication batch):
  - `2ea2e5b5…` item 33 (Opus 5.5): slices labelled "Cost Impact" / "Investment Impact", the prompt's own segment
    names, satisfy "labeled Cost and Investment" (grader false fail); item 25 (GPT-6.1 Sol): a pie keyed by the IDs
    01-12 that the adjacent table maps to the twelve activities shows no category outside the twelve (grader false
    fail).
  - `a45bc83b…` item 66 (GPT-6.1 Sol): identity-restricted administrative access is addressed in substance by IAM
    least privilege, MFA for administrators, an internal IAM-authenticated ingress and the absence of an admin VM
    (grader false fail of a judge verdict).
  - `f841ddcf…` item 38 (GPT-6.1 Sol): the June window written in words ("Fiscal month: June 1-30, 2025") with the
    slipped POs "shipped July 1" satisfies the item; no frozen rule requires the numeric date form (grader false
    fail of a judge verdict).

### 5.6 Design choices

The four choices the submission page states, with their reasons:
- **Graders never guess.** "Cannot assess" instead of an inferred pass, so no hidden passes.
- **The expert reference is evidence too.** Expected values come from the source files, which exposed a rubric stricter
  than its reference (tour task).
- **Frozen verdicts, author decisions on top.** Every correction stays traceable, and review time goes only where it can
  change a verdict.
- **Task pass as the headline.** A deliverable counts only if every must-have holds; severity shows how bad each failure
  is. Trade-off: one exact-label miss fails a whole task.

---

## 6. Failure taxonomy and critical-case analysis

Sections 6.1-6.4 give the structure and section 6.5 the results. The structure is built from `PLAN.md` section 5 and
`preregistration.md` 1.10, 1.11, 1.14, 1.17 and 1.19.

### 6.1 Unit and scope

- **Failure event.** A rubric-item FAIL, or a critical-criterion FAIL, on a Formal candidate output. A critical FAIL
  counts as confirmed only after human verification.
- **Triage.** All failures, incomplete runs, `cannot_assess` items and critical disagreements enter triage after the
  blind labels are saved, and passes are sampled for false passes. Triage never adds items to the agreement sample.
- **Depth.** About 20-30 events are investigated in depth. They are selected by business impact, severity,
  uncertainty and capability family, and kept separate from the agreement statistics.

### 6.2 Classification axes

1. **Observable error class.** This is the primary capability of the rubric item, from the map in
   `preregistration.md` 1.17 (approved as-is by the author on 2026-11-02; section 7.4):

   | Class | Meaning |
   |---|---|
   | requirements | deliverable-spec compliance |
   | grounding | figures and items taken from the attached sources |
   | rule_execution | computed figures, flags and classifications by the task's rules |
   | coverage | every required element present, no omissions or extras |
   | consistency | parts of the deliverable agree, including document against workbook |
   | mechanics | formulas and links, pivot and chart objects, error-free and sortable cells |
   | presentation | formatting, readability, style |

2. **Locus, in the order of investigation** (an order, not a proof of root cause):
   1. task material: expert error, rubric beyond the prompt, dataset artifact, or under-specified task, as in the
      audit classes of `docs/expert_gold_fail_audit.md`;
   2. grading rule or grader: `grader_extraction`, `grader_caused_recalculation`, `grader_caused_extraction`;
   3. environment: `environment_unsupported`, which needs evidence that the missing capability was necessary;
   4. model: `model_caused`, `model_caused_missing`, `model_caused_corrupt`.

   Run, collection and judge-infrastructure errors are reported in their own categories and are not model failures.
3. **Cause judgment.** Evidenced, probable or undetermined. Trajectory evidence is recorded at three levels (file
   access observed; content returned to the model's context; content used correctly). It is used for attribution
   only, never for scoring. A missing read is reported as "no confirmed read observed".
4. **Severity and business impact.** Critical or non-critical membership, a one-sentence business impact and rework
   need, and an "original verdict overturned on review" status (`preregistration.md` 1.11).

### 6.3 Known task-side confounds to rule out before attributing a failure to a model

These rules were fixed before any model output was seen, unless the source says otherwise (`preregistration.md`
section 3, `docs/status.md` "Known issues and findings").

| Task | Confound | Rule in force |
|---|---|---|
| `b5d2e6f1…` | The expert "Data" tab differs from the source in 557 cells. The expert ST% averages row ratios | The source is the reference. ST% is the ratio of sums (C4) |
| `f841ddcf…` | The expert narrative labels the June order value (145,219) as shipped. 13,248 is a different metric | Precision rules per item. PO-level evidence is critical (C2). Narrative figures are graded by the metric they name |
| `47ef842d…` | The prompt's "out-of-stock percentage" field does not exist. The rubric store counts 729 / 1,223 copy the expert, while the distinct counts are 728 / 1,222 | Operational definitions (OOS := Current Week Inv = 0). A-31 and A-52 grade against the source |
| `1137e2bb…` | Rubric 21 (a missing case-pack indicator) goes beyond the prompt | A-21: graded as written, excluded from critical |
| `c3525d4d…` | Store ids are integers in one list and 4-character text in the other. The expert ids are re-identified | Normalised comparison (1,226 common, 31 added, 2 removed). A-24/25 overage rounding is this evaluation's rule |
| `7b08cd4d…` | The expense allocation is not defined by the prompt. The rounded rubric figures do not add up | Identities are checked unrounded (A-53). The allocation is classified before reporting |
| `7d7fc9a7…` | The prompt states no rounding rule. Per-line cent rounding drifts −0.01 to −0.05 from the GL | Reconciliation and rounding rule (section 2.7). Total at 4/30 is 929,354.31 (A-10) |
| `2ea2e5b5…` | Rubric item 10 (Total Hours) goes beyond the prompt. Rubric 8 lists a duplicate | C2 revised and reported under both definitions. Item 27 needs the literal "Margin Impact" label |
| `c357f0e2…` | Rubric 2 places the headers in row 1, but the template has them in row 2 | A-2 accepts either row. Item 4 is literal (80-100). Naming and permission meaning are graded separately |
| `a45bc83b…` | The official resources are staged offline (the 2026-10-29 snapshot) | Requirement layers for C2. Visual items are human-authoritative |

### 6.4 What counts as signal for a researcher, and what is noise

- **Signal:**
  - human-verified critical FAILs attributed to the model, with an evidenced or probable cause;
  - repeated error classes across tasks or across both candidates;
  - failures where the task material is clean, that is, none of the confounds in 6.3 applies.
- **Reported separately, not as a model capability finding:**
  - failures on rubric items that go beyond the prompt;
  - literal-label and pure presentation items;
  - `cannot_assess` and `not evaluated` items;
  - judge-infrastructure verdicts and run errors.

Section 7.5 ("Requirement source") applies this split to the 40 confirmed failures: each is tagged by whether the
prompt itself states the failed requirement, only the rubric does (its exact wording or extra detail, or an item beyond
the prompt), or R-2.7-21 decides it. The confirmed failures are all reported; the tag separates them, it re-weights
nothing.

### 6.5 Results of the failure analysis

Events are the 40 human-confirmed model failures (rubric items adjudicated `confirmed_fail`, `verified_fail` or
`grader_false_pass` across the whole adjudication layer; section 7.5), classed by the item's primary capability in the
approved map (section 7.4). Counts are rubric items, not independent incidents (M4's four items are one rounding
strategy; the additions-column items are one requirement on two schedules per candidate). "Critical" counts the items
that sit in a critical criterion.

| Error class | Opus 5.5: events (critical) | GPT-6.1 Sol: events (critical) | Tasks affected |
|---|---|---|---|
| requirements | 5 (3) | 21 (9) | 8 (`1137e2bb…`, `2ea2e5b5…`, `47ef842d…`, `7b08cd4d…`, `7d7fc9a7…`, `a45bc83b…`, `b5d2e6f1…`, `c357f0e2…`) |
| grounding | 0 (0) | 0 (0) | 0 |
| rule_execution | 3 (2) | 6 (3) | 3 (`1137e2bb…`, `7d7fc9a7…`, `b5d2e6f1…`) |
| coverage | 1 (0) | 3 (2) | 1 (`c357f0e2…`) |
| consistency | 0 (0) | 0 (0) | 0 |
| mechanics | 1 (0) | 0 (0) | 1 (`1137e2bb…`) |
| presentation | 0 (0) | 0 (0) | 0 |
| task-material / grader / environment (not model) | 67 grader false fails and 21 verified passes among the 170 adjudicated worksheet rows (both candidates; section 7.7; 70 false fails in the adjudication layer); 42 rows left unresolved as grader read limits; no environment failure | | |

Exemplar critical cases (all human-confirmed on 2026-11-02; adjudication records in `formal/human_review/`):
- GPT-6.1 Sol, `b5d2e6f1…` C3 (items 16, 25, 26, deterministic): the "Sales by Store" sheet has 39 store blocks of
  eight brand rows and one Grand Total, no per-store subtotal rows (checked stores 37-39 and the total). Cause: the
  requested aggregation level was dropped (M1). Business impact: the store view the manager asked for cannot be read
  without re-aggregating. Batch 22:05:01Z.
- GPT-6.1 Sol, `7b08cd4d…` C1 (items 16, 17, deterministic): "Revenue Detail" A8:E14 lists gross and rate per stop but
  no per-stop withholding or net revenue; both are computed by country only (A19:E24) and A26 states that no stop-level
  tax allocation is made. The expert reference is also country-level; the rubric is stricter (M1). Impact: the P&L
  cannot answer a per-show question. Batch 22:05:01Z.
- Opus 5.5, `2ea2e5b5…` C3 (items 27, 38, deterministic): the margin and time tables carry the group rows "Cost Impact /
  Investment Impact" and "High / Medium / Low" under the header "Segment / Activity"; no row or column is labelled
  "Margin Impact" or "Time Sensitivity" (the literal rule of `preregistration.md` 1.23; M2). Impact: low, the slide
  titles carry the phrases. Batch 22:05:01Z.
- GPT-6.1 Sol, `c357f0e2…` C2 (item 50, judge) and C3 (item 15, judge): row 91 (UAT-089) opens an Org A and an Org B
  project but edits only Org B, so no row edits an Idea, Proposal or Project in two organisations with both edits
  allowed, the form the rubric names; the plan tests Super Admin access in other forms (Org B records in rows 14, 40,
  60 and 88; programs and settings in both organisations in rows 68 and 75). Row 3 (UAT-001) names one required field
  where two are required (M5). Impact: the rubric's cross-organisation edit and a two-field creation case are not in
  the plan; both items are rubric detail (section 7.5, "Requirement source"). Batch 22:05:01Z.
- GPT-6.1 Sol, `1137e2bb…` C3 (item 23, judge pass overturned by blind label F06): the Word summary explains the price
  check, gives a 1-unit / 24-pack example and names a CASE-only divisibility control, but never states that CASE
  quantities must be whole multiples of the case pack (M7). Impact: a reader cannot re-apply the check from the
  summary. Recorded 18:56:21Z.

Overturned verdicts and reclassifications among the 170 adjudicated worksheet rows: 67 automated fails overturned as
grader false fails (both candidates; every one a grader extraction or scoring defect, sections 7.7 and 8.2), 21
`cannot_assess` items verified pass (including GPT-6.1 Sol's `b5d2e6f1…` item 12, the PivotTable confirmed in Excel, and
Opus 5.5's `7d7fc9a7…` C1 items 13, 14, 33 and 34, reconciled invoice by invoice), 6 verified fail (including the per-line additions items 21 / 39 of Opus 5.5 and the
table-label items 27 / 38 of GPT-6.1 Sol, re-graded by hand after a consistency review), 1 judge pass overturned (F06),
33 fails confirmed, 42 `cannot_assess` items left as grader read limits. Three further grader false fails were imported
from the defect review (D07, D08, D23; non-critical items), and ten automated passes of Opus 5.5 behind the section 1
claim that it provides the levels GPT-6.1 Sol omits were recorded `confirmed_pass` with the author's evidence
(`b5d2e6f1…` 12, 16, 25, 26; `47ef842d…` 28, 35, 42, 49, 56, 57; its `7b08cd4d…` 16 / 17 were already
`grader_false_fail` on the per-stop columns L7:M13), so the adjudication layer holds 183 items. No
reclassification to task material or environment was made: the two `7b08cd4d…` items that follow the expert reference's
country-level approach stay model failures against the rubric, with the note recorded.

---

## 7. Results

Every figure below comes from the run's authoritative pass (`grading.run_grading.authoritative_selection` at `freeze-v1-grading`, `cc684ef`),
summarised in `~/turing-eval-runs/formal/results_summary.json` with each run's `results.jsonl` / `grades.jsonl` and pass id. Results were
unsealed only after the author's 20 formal labels were checkpointed (2026-11-02T12:48:10Z, SHA-256 `308771dd…`).

**Status of these numbers.**
- Judge-derived verdicts: the formal judge pass ran before its held-out validation was complete, to meet the submission
  deadline, so its verdicts were labelled provisional (`preregistration.md` 1.25). The label was lifted once the Judge
  Validation agreement and the independent recheck of V1.9 were both recorded (section 8.2).
- Every failed critical criterion in the adjudicated results is author-confirmed; the as-graded results preserve the original verdicts.
- Items the graders could not evaluate are reported as not evaluated, never as FAIL.

### 7.1 Run inventory

- 20/20 samples completed with no limit event, hold, stop or engineering failure (`docs/status.md`).
- Every unit was accepted by the unit gate and designated canonical.
- Deliverables present / required and wall time per run (`run_inventory.jsonl` `started_at` / `finished_at`,
  `artifact_manifest.json` `file_count`; required = the deliverable list of `preregistration.md` section 3; every run
  delivered the required count):

| Task | Required | Opus 5.5: files, wall time | GPT-6.1 Sol: files, wall time |
|---|---|---|---|
| `b5d2e6f1…` | 1 | 1, 6.8 min | 1, 5.0 min |
| `f841ddcf…` | 1 | 1, 3.3 min | 1, 2.7 min |
| `47ef842d…` | 1 | 1, 6.6 min | 1, 5.7 min |
| `1137e2bb…` | 2 | 2, 6.8 min | 2, 4.1 min |
| `c3525d4d…` | 2 | 2, 3.2 min | 2, 4.0 min |
| `7b08cd4d…` | 1 | 1, 3.9 min | 1, 4.8 min |
| `7d7fc9a7…` | 1 | 1, 5.9 min | 1, 5.7 min |
| `2ea2e5b5…` | 1 | 1, 2.6 min | 1, 3.6 min |
| `c357f0e2…` | 1 | 1, 7.9 min | 1, 6.0 min |
| `a45bc83b…` | 3 | 3, 17.4 min | 3, 11.1 min |

### 7.2 Scores per task and model

P = points of the evaluated items that pass; E = evaluated weight; W = rubric weight; P/E = score on what could be evaluated; E/W = coverage.
Models with different coverage are not ranked by P/E alone (`PLAN.md` section 2).

| Task | Model | P / E / W | P/E | E/W | Not evaluated (reason: count) | Critical overall | Judge items with a verdict |
|---|---|---|---|---|---|---|---|
| `b5d2e6f1…` | Opus 5.5 | 58 / 60 / 65 | 0.967 | 0.923 | visual (human review): 1 | pass | 0/0 |
| `b5d2e6f1…` | GPT-6.1 Sol | 42 / 58 / 65 | 0.724 | 0.892 | extraction failed: 1, visual (human review): 1 | fail | 0/0 |
| `f841ddcf…` | Opus 5.5 | 82 / 83 / 88 | 0.988 | 0.943 | visual (human review): 1 | pass | 7/7 |
| `f841ddcf…` | GPT-6.1 Sol | 61 / 81 / 88 | 0.753 | 0.920 | extraction failed: 1, visual (human review): 1 | fail | 7/7 |
| `47ef842d…` | Opus 5.5 | 82 / 92 / 99 | 0.891 | 0.929 | visual (human review): 3 | fail | 1/1 |
| `47ef842d…` | GPT-6.1 Sol | 76 / 92 / 99 | 0.826 | 0.929 | visual (human review): 3 | fail | 1/1 |
| `1137e2bb…` | Opus 5.5 | 60 / 79 / 80 | 0.759 | 0.988 | extraction failed: 1 | fail | 7/7 |
| `1137e2bb…` | GPT-6.1 Sol | 75 / 77 / 80 | 0.974 | 0.963 | extraction failed: 1, no number bound to the price-mismatch ph: 1, conflicting case-pack counts [2, 10]; ro: 1 | not_confirmed | 7/7 |
| `c3525d4d…` | Opus 5.5 | 52 / 75 / 86 | 0.693 | 0.872 | extraction failed: 3, visual (human review): 1 | fail | 5/5 |
| `c3525d4d…` | GPT-6.1 Sol | 55 / 75 / 86 | 0.733 | 0.872 | extraction failed: 3, visual (human review): 1 | fail | 5/5 |
| `7b08cd4d…` | Opus 5.5 | 62 / 83 / 89 | 0.747 | 0.933 | visual (human review): 2 | fail | 14/14 |
| `7b08cd4d…` | GPT-6.1 Sol | 62 / 82 / 89 | 0.756 | 0.921 | visual (human review): 2, The excerpt only provides the high-level: 1 | fail | 14/14 |
| `7d7fc9a7…` | Opus 5.5 | 36 / 39 / 95 | 0.923 | 0.411 | extraction failed: 30, visual (human review): 1 | fail | 14/14 |
| `7d7fc9a7…` | GPT-6.1 Sol | 66 / 84 / 95 | 0.786 | 0.884 | extraction failed: 3, visual (human review): 1 | fail | 14/14 |
| `2ea2e5b5…` | Opus 5.5 | 78 / 85 / 85 | 0.918 | 1.000 | none | fail (preregistered: fail) | 4/4 |
| `2ea2e5b5…` | GPT-6.1 Sol | 28 / 30 / 85 | 0.933 | 0.353 | extraction failed: 33 | fail (preregistered: fail) | 4/4 |
| `c357f0e2…` | Opus 5.5 | 92 / 95 / 101 | 0.968 | 0.941 | evidence must be a non-empty list for pa: 1, visual (human review): 1 | fail | 53/54 |
| `c357f0e2…` | GPT-6.1 Sol | 89 / 96 / 101 | 0.927 | 0.950 | visual (human review): 1 | fail | 54/54 |
| `a45bc83b…` | Opus 5.5 | 66 / 73 / 87 | 0.904 | 0.839 | visual (human review): 8, evidence must be a non-empty list for pa: 1 | not_confirmed | 59/60 |
| `a45bc83b…` | GPT-6.1 Sol | 68 / 74 / 87 | 0.919 | 0.851 | visual (human review): 8 | not_confirmed | 60/60 |

Totals over the 10 tasks (sum of P, E and W; not a capability estimate, section 8.2):

| Model | P / E / W | P/E | E/W |
|---|---|---|---|
| Opus 5.5 | 668 / 764 / 875 | 0.874 | 0.873 |
| GPT-6.1 Sol | 622 / 749 / 875 | 0.830 | 0.856 |

Low coverage is a grader extraction limit, not a model result:
- Opus `7d7fc9a7…`: 29 items where the grader could not identify the vendor column of the two schedule sheets.
- GPT `2ea2e5b5…`: 33 items where it could not identify the time, strategic and margin sections in the slides.

Deliverable-integrity observation, not a rubric result: GPT-6.1 Sol's `Weekly Sales Analysis.xlsx` (`b5d2e6f1…`) opens
in Excel for Mac only after Excel's repair prompt ("[Repaired]" in the title bar); Apple Numbers and openpyxl open it
without repair, and both PivotTables survive the repair (the author confirmed the "Sales by Store" PivotTable in Excel,
batch 2026-11-02). No rubric item scores file integrity, and the frozen grading read the file without error.

### 7.3 Critical criteria (35 per candidate)

Status **as graded** is the frozen automated verdicts plus the preregistered human visual layer (the `a45bc83b…` C3 Diagram
items, all pass, `formal/human_review/visual_*.jsonl`). Status **as adjudicated** also applies the author's adjudication records
(`formal/human_review/adjudication_*.jsonl`; classes `confirmed_fail` / `grader_false_fail` / `cannot_verify` for automated
fails; `verified_pass` / `verified_fail` / `leave` for `cannot_assess` items; `grader_false_pass` for a human verification
that overturns an automated pass; `confirmed_pass` for an author-verified automated pass). The adjudication layer holds
183 items in 197 records. The batches were recorded on 2026-11-02 local time (13:30:50Z, 18:56:21Z, 22:05:01Z,
22:45:29Z and later); the last one, the four `7d7fc9a7…` C1 decisions, is timestamped 2026-11-03T02:34:11Z. A later
record of an item supersedes an earlier one. The items: the 170 worksheet rows (every non-pass member of a critical criterion that
was fail or not_confirmed as graded, every draft model-error row and F06), three non-critical items imported from the
defect review, and ten `confirmed_pass` verifications of Opus 5.5 automated passes. Item mapping: `grader_false_fail`, `verified_pass` → pass;
`confirmed_fail`, `verified_fail`, `grader_false_pass` → fail; `leave` / `cannot_verify` → unresolved. Four baselines are
reported, all computed with the frozen `grading.grade.score_rows` on copies (`formal/human_layers_summary.json`):
**pure automated** (the frozen verdicts alone; the "critical overall" column of section 7.2); **as graded** (plus the
preregistered visual layer; the baseline of the item scores); **adjudicated** (plus the author's records: a confirmed fail
takes precedence over unresolved members; a criterion stays not_confirmed only when it has no confirmed failure and at
least one unresolved member; the final status); and the **R-2.7-21 sensitivity** (adjudicated, with the per-line
additions items 21 / 39 reverted to `cannot_assess` for both candidates). The frozen verdicts are unchanged. `2ea2e5b5…`
is the only task with a revised definition; its status is the same under the preregistered one. The deciding items are
given in the adjudicated columns.

| Task | Criterion | Opus pure automated | Opus as graded | Opus adjudicated (final) | Opus sensitivity | GPT pure automated | GPT as graded | GPT adjudicated (final) | GPT sensitivity |
|---|---|---|---|---|---|---|---|---|---|
| `b5d2e6f1…` | C1 Structure | pass | pass | pass | pass | pass | pass | pass | pass |
| `b5d2e6f1…` | C2 Brand totals | pass | pass | pass | pass | fail | fail | pass | pass |
| `b5d2e6f1…` | C3 PivotTable | pass | pass | pass | pass | fail | fail | fail (16, 25, 26 confirmed; 12 verified pass) | fail |
| `b5d2e6f1…` | C4 ST% logic | pass | pass | pass | pass | pass | pass | pass | pass |
| `f841ddcf…` | C1 June shipped total | pass | pass | pass | pass | fail | fail | pass | pass |
| `f841ddcf…` | C2 Auditable PO-level evidence | pass | pass | pass | pass | fail | fail | pass | pass |
| `f841ddcf…` | C3 Slipped cohort | pass | pass | pass | pass | fail | fail | pass | pass |
| `f841ddcf…` | C4 Row or account arithmetic | pass | pass | pass | pass | fail | fail | pass | pass |
| `f841ddcf…` | C5 Narrative consistency | pass | pass | pass | pass | not_confirmed | not_confirmed | pass | pass |
| `47ef842d…` | C1 Scope | pass | pass | pass | pass | pass | pass | pass | pass |
| `47ef842d…` | C2 Rate and WOS | pass | pass | pass | pass | pass | pass | pass | pass |
| `47ef842d…` | C3 Out-of-stock | pass | pass | pass | pass | pass | pass | pass | pass |
| `47ef842d…` | C4 Chart | fail | fail | fail (13 confirmed) | fail | fail | fail | fail (13 confirmed) | fail |
| `1137e2bb…` | C1 Line flags | pass | pass | pass | pass | pass | pass | pass | pass |
| `1137e2bb…` | C2 SKU summary | fail | fail | pass | pass | pass | pass | pass | pass |
| `1137e2bb…` | C3 Word summary | pass | pass | pass | pass | not_confirmed | not_confirmed | fail (23 confirmed) | fail |
| `c3525d4d…` | C1 Store reconciliation | pass | pass | pass | pass | pass | pass | pass | pass |
| `c3525d4d…` | C2 Budget arithmetic | fail | fail | pass | pass | fail | fail | pass | pass |
| `c3525d4d…` | C3 Email consistency | pass | pass | pass | pass | pass | pass | pass | pass |
| `7b08cd4d…` | C1 Withholding and net revenue | fail | fail | pass | pass | fail | fail | fail (16, 17 confirmed) | fail |
| `7b08cd4d…` | C2 Expenses | pass | pass | pass | pass | pass | pass | pass | pass |
| `7b08cd4d…` | C3 Net income | pass | pass | pass | pass | pass | pass | pass | pass |
| `7d7fc9a7…` | C1 Completeness | not_confirmed | not_confirmed | pass (13, 14, 33, 34 verified pass) | pass | pass | pass | pass | pass |
| `7d7fc9a7…` | C2 1250 reconciliation | not_confirmed | not_confirmed | fail (21 confirmed; 6 left) | not_confirmed | fail | fail | fail (21 confirmed) | not_confirmed |
| `7d7fc9a7…` | C3 1251 reconciliation | not_confirmed | not_confirmed | fail (39 confirmed; 8 left) | not_confirmed | fail | fail | fail (39 confirmed) | not_confirmed |
| `7d7fc9a7…` | C4 Summary linkage | fail | fail | pass | pass | not_confirmed | not_confirmed | pass | pass |
| `2ea2e5b5…` | C1 Deck structure | pass | pass | pass | pass | not_confirmed | not_confirmed | pass | pass |
| `2ea2e5b5…` | C2 Activity shares | pass | pass | pass | pass | fail | fail | pass | pass |
| `2ea2e5b5…` | C3 Classification | fail | fail | fail (27, 38 confirmed) | fail | not_confirmed | not_confirmed | fail (27, 38 confirmed; 28 left) | fail |
| `c357f0e2…` | C1 Plan structure | pass | pass | pass | pass | pass | pass | pass | pass |
| `c357f0e2…` | C2 Permission boundaries | pass | pass | pass | pass | fail | fail | fail (12, 50 confirmed) | fail |
| `c357f0e2…` | C3 Module and negative coverage | fail | fail | pass | pass | fail | fail | fail (15 confirmed) | fail |
| `a45bc83b…` | C1 Deliverable set | pass | pass | pass | pass | pass | pass | pass | pass |
| `a45bc83b…` | C2 Hard requirements met as an architecture, consistently | pass | pass | pass | pass | pass | pass | pass | pass |
| `a45bc83b…` | C3 Diagram | not_confirmed | pass | pass | pass | not_confirmed | pass | pass | pass |
Counts (pass / fail / not_confirmed), 35 criteria per candidate:

| Baseline | Opus 5.5 | GPT-6.1 Sol |
|---|---|---|
| Pure automated (frozen verdicts) | 24 / 7 / 4 | 15 / 14 / 6 |
| As graded (plus the preregistered visual layer) | 25 / 7 / 3 | 16 / 14 / 5 |
| **Adjudicated (final)** | **31 / 4 / 0** | **26 / 9 / 0** |
| R-2.7-21 sensitivity (adjudicated, additions items not evaluated) | 31 / 2 / 2 | 26 / 7 / 2 |

Remaining fails (13 criteria: Opus 5.5 4, GPT-6.1 Sol 9), each decided by human-confirmed items:
- Opus and GPT `47ef842d…` C4: item 13, the chart's categories are product names, not the five UPCs (M2).
- Opus and GPT `2ea2e5b5…` C3: items 27 and 38, no row or column labelled "Margin Impact" / "Time Sensitivity"
  (M2; the GPT items were re-graded by hand from `cannot_assess`, the same finding as Opus; 28 GPT members are left).
- Opus and GPT `7d7fc9a7…` C2 and C3: items 21 and 39, no per-line additions column (the additions line, under
  R-2.7-21; the Opus items were re-graded by hand from `cannot_assess`; 6 and 8 Opus members are left).
- GPT `b5d2e6f1…` C3: items 16, 25, 26, no per-store subtotal rows (M1; item 12, the PivotTable, is a verified pass).
- GPT `1137e2bb…` C3: item 23, the case-pack rule is never stated (M7, F06).
- GPT `7b08cd4d…` C1: items 16, 17, no per-stop withholding or net revenue (M1).
- GPT `c357f0e2…` C2: items 12 (plural role labels, M2) and 50 (no cross-organisation edit, M5); C3: item 15 (one
  required field named, M5).

No criterion remains `not_confirmed` as adjudicated. Opus `7d7fc9a7…` C1 (items 13, 14, 33, 34; the grader did not map
the vendor column) is pass on the author's decision of 2026-11-02: all 41 services invoices and all 25 insurance
invoices appear on Prepaid Expenses 1250 and Prepaid Insurance 1251 with their source amounts (totals 1,087,156.21 and
568,698.22), from an invoice-by-invoice reconciliation extracted by Claude and spot-checked by the author on four
invoices (batch 2026-11-03T02:34:11Z). The 42 `leave` items in all remain unresolved item-level coverage gaps, each
inside a criterion that already fails on another member (Opus `7d7fc9a7…` C2 / C3, GPT `2ea2e5b5…` C3); an item-key
comparison across candidates found no confirmed counterpart for any of them.

**Policy in force for `7d7fc9a7…` items 21 and 39 (both candidates, C2 and C3).** Both candidates' schedules present no
per-line additions column, and the items fail under the per-line additions rule R-2.7-21 (`preregistration.md` 2.7,
decided 2026-11-01, grader `7d7fc9a7-2026-11-01.7`): additions are never inferred, and a schedule that presents no
per-line additions column fails the Beginning + Adds − Amortization = Ending identity. The rule was frozen before
generation and is treated as binding; the Opus 5.5 items, `cannot_assess` as graded, were re-graded by hand to the same
finding. Sensitivity (computed, `adds_policy_not_binding` in `human_layers_summary.json`): if the rule were not binding,
items 21 and 39 would revert to `cannot_assess` for both candidates; GPT-6.1 Sol's C2 and C3 would become
`not_confirmed`, not pass (items 22 and 40 are grader false fails: a March section heading read as an amortization
cell), and Opus 5.5's C2 and C3 would return to `not_confirmed` on their unresolved members. The candidates would then
stand at Opus 31 / 2 / 2 and GPT 26 / 7 / 2.

### 7.4 Capability profile

The rubric-to-capability map (`grading/capability_map.json`, version `capability-map-2026-11-01.1`, `preregistration.md`
1.17) assigns each of the 580 rubric items one primary capability by rule (regular expressions over the criterion text;
no overrides recorded). It was authored before generation: committed once in `9b1df11` (2026-11-01T11:22:58Z) and
unchanged through `freeze-v1-generation` (`dda234f`), the formal run and the reveal (12:48:10Z). The author approved it
as-is on 2026-11-02, after the reveal, without changes. The classes are those of section 6.2.

Counts below join the map with each run's authoritative verdicts plus the visual layer (`~/turing-eval-runs/analysis/failures-v1/all_items.csv`,
section 7.3 "as graded"). P / E is the weight of passing items over the weight of evaluated items (pass or fail); "not
evaluated" is `cannot_assess`, a pending visual item or an invalid judge output. Items are counted once each; the counts are
rubric items, not independent errors, and no attribution (model, grader, task material) is made here: that is section 7.5,
after verification.

| Capability | Items | Opus 5.5 pass / fail / not evaluated | Opus 5.5 P / E (W) | GPT-6.1 Sol pass / fail / not evaluated | GPT-6.1 Sol P / E (W) |
|---|---|---|---|---|---|
| requirements | 280 | 237 / 32 / 11 | 352 / 395 = 0.891 (407) | 229 / 39 / 12 | 332 / 390 = 0.851 (407) |
| rule_execution | 197 | 144 / 30 / 23 | 214 / 253 = 0.846 (294) | 131 / 36 / 30 | 194 / 244 = 0.795 (294) |
| coverage | 46 | 40 / 3 / 3 | 57 / 60 = 0.950 (65) | 37 / 9 / 0 | 50 / 65 = 0.769 (65) |
| presentation | 22 | 13 / 1 / 8 | 15 / 16 = 0.938 (56) | 12 / 2 / 8 | 14 / 16 = 0.875 (56) |
| consistency | 17 | 13 / 3 / 1 | 19 / 25 = 0.760 (27) | 11 / 1 / 5 | 18 / 19 = 0.947 (27) |
| mechanics | 14 | 12 / 2 / 0 | 17 / 20 = 0.850 (20) | 11 / 1 / 2 | 15 / 16 = 0.938 (20) |
| grounding | 4 | 1 / 1 / 2 | 1 / 2 (6) | 4 / 0 / 0 | 6 / 6 (6) |
| **all** | **580** | **460 / 72 / 48** | **675 / 771 = 0.875 (875)** | **435 / 88 / 57** | **629 / 756 = 0.832 (875)** |

Reading notes:
- The totals differ from section 7.2 by the six visual items per candidate that the author passed (weight 7).
- The counts are as graded. The adjudication layer of section 7.3 (183 items) is not applied here; the adjudicated
  critical statuses are in section 7.3 and the confirmed failures by type in section 7.5.
- Not-evaluated items are concentrated where the grader could not read a deliverable (section 7.2): Opus
  `rule_execution` 23 and `requirements` 11 come mostly from `7d7fc9a7…`; GPT `rule_execution` 30 and `consistency` 5
  from `2ea2e5b5…` and `f841ddcf…`. Classes with different coverage are not compared by P / E alone.
- `grounding` has four items and supports no reading. `presentation` has eight pending visual items per candidate.
- Which of the failing items are model errors rather than grader errors is the subject of the verification in
  section 7.5; the draft triage (section 7.7) attributes a majority of the recorded fails to the graders.

### 7.5 Where the models fell short, and which gaps a dataset could close

The taxonomy below is built from the human-confirmed failures only: the 40 rubric items adjudicated `confirmed_fail`
(33), `verified_fail` (6) or `grader_false_pass` (1) across the whole adjudication layer on 2026-11-02
(`analysis/human_taxonomy.json`, built from the records by `formal/tooling/build_taxonomy.py`, which reconciles the
cluster total against the layer's unique confirmed item keys). Clusters M1-M6 keep the draft definitions of the Codex
review; M7 is new; R03 is kept as its own cluster; the per-line additions items of both candidates form their own line,
mutually exclusive with M1 and dependent on R-2.7-21. Each item belongs to exactly one cluster, so counts are additive;
the item total is never a count of independent incidents. Severity is the author's rating from critical-criterion
membership and the consequence for the deliverable's reader. "Flagged by" is the layer whose verdict the adjudication
confirmed. Failed critical criteria (adjudicated): Opus 5.5 4, GPT-6.1 Sol 9, 13 in all of 35 per candidate.

The submission page groups the nine clusters into four categories by what the task required (`site/content.json`,
counts in `site/data/metrics.json`, `categories`). The grouping is for display only: no item changes cluster and no
decision changes. A category's severity is the highest severity of its clusters among each model's items, shown as Opus 5.5 /
GPT-6.1 Sol (— where a model has no failure in the category). "Model was told (in the prompt)" counts the items
tagged `prompt` in "Requirement source" below: the clearest evidence of a model failure; severity is a separate scale
(business impact).

| Category | Clusters (failure types) | Opus 5.5 rubric items · tasks | GPT-6.1 Sol rubric items · tasks | Total rubric items | Model was told (in the prompt), Opus 5.5 / GPT-6.1 Sol | In critical criteria, Opus 5.5 / GPT-6.1 Sol | Severity, Opus 5.5 / GPT-6.1 Sol |
|---|---|---|---|---|---|---|---|
| A. Required content omitted: a level, measure or column the rubric requires is missing | M1, ADDS, R03 | 3 · 2 | 14 · 5 | 17 | 0 / 9 | 2 / 7 | medium / high |
| B. Label or display not as required: the information is there, in a different form than the rubric names | M2, M6 | 4 · 3 | 7 · 4 | 11 | 0 / 2 | 3 / 4 | low / low |
| C. Document content omitted: a design, test or explanation leaves out a specified control, condition or criterion | M3, M5, M7 | 3 · 2 | 5 · 3 | 8 | 0 / 1 | 0 / 3 | medium / medium |
| D. Added line breaks a rule: an added adjustment line conflicts with an accounting rule the rubric states | M4 | 0 | 4 · 1 | 4 | 0 / 0 | 0 / 0 | — / low |
| **Total** | 9 clusters | **10** | **30** | **40** | **0 / 12** | **5 / 14** | |

| Cluster | Definition | Severity | Opus 5.5 items / tasks | GPT-6.1 Sol items / tasks | Critical rubric items | Flagged by | Item keys |
|---|---|---|---|---|---|---|---|
| M1 Required reporting levels or measures are omitted | The workbook has the inputs or higher-level totals but omits a requested measure or aggregation level | high | 0 / 0 | 11 / 3 | 5 | deterministic 10, judge 1 | gpt `47ef842d…` 28; gpt `47ef842d…` 35; gpt `47ef842d…` 42; gpt `47ef842d…` 49; gpt `47ef842d…` 56; gpt `47ef842d…` 57; gpt `7b08cd4d…` 16; gpt `7b08cd4d…` 17; gpt `b5d2e6f1…` 16; gpt `b5d2e6f1…` 25; gpt `b5d2e6f1…` 26 |
| M2 Semantic substitutes do not meet explicit naming or display requirements | The information is present, but the exact identifier, label, sheet name or decimal presentation the rubric names is replaced by another form | low | 3 / 2 | 7 / 4 | 7 | deterministic 9, judge 1 | gpt `2ea2e5b5…` 27; opus `2ea2e5b5…` 27; gpt `2ea2e5b5…` 38; opus `2ea2e5b5…` 38; gpt `47ef842d…` 13; opus `47ef842d…` 13; gpt `47ef842d…` 17; gpt `7d7fc9a7…` 3; gpt `7d7fc9a7…` 4; gpt `c357f0e2…` 12 |
| M3 An operational control or concrete validation step is left unspecified | The design or test document discusses the goal but leaves the named control, access decision or validation procedure unspecified | medium | 2 / 1 | 2 / 2 | 0 | judge 4 | gpt `a45bc83b…` 60; opus `a45bc83b…` 64; opus `a45bc83b…` 68; gpt `c357f0e2…` 66 |
| M4 A disclosed rounding adjustment conflicts with a source-only accounting rule | A labelled fractional-cent line reconciles rounded lines to the exact balance and thereby shows negative amortization and an unfunded balance increase | low | 0 / 0 | 4 / 1 | 0 | judge 2, deterministic 2 | gpt `7d7fc9a7…` 31; gpt `7d7fc9a7…` 32; gpt `7d7fc9a7…` 49; gpt `7d7fc9a7…` 50 |
| M5 A nearby test scenario omits the exact required condition or assertion | A test covers the feature but not the required missing-input condition, specified fields or both-organisation mutation | medium | 1 / 1 | 2 / 1 | 2 | judge 3 | gpt `c357f0e2…` 15; opus `c357f0e2…` 34; gpt `c357f0e2…` 50 |
| M6 A grouped report lacks the requested prioritization interaction | The SKU summary cannot be sorted by total errors without breaking its grouping | low | 1 / 1 | 0 / 0 | 0 | deterministic 1 | opus `1137e2bb…` 22 |
| M7 A plain-language explanation of a check omits its decisive criterion | The rule is applied correctly in the workbook, but the narrative definition leaves out the condition that defines the check | medium | 0 / 0 | 1 / 1 | 1 | human 1 | gpt `1137e2bb…` 23 |
| R03 Missing separate invalid-case-pack indicator | No separate indicator for a missing or invalid case pack (rubric 21, beyond the prompt, A-21); no count affected | low | 1 / 1 | 1 / 1 | 0 | deterministic 2 | gpt `1137e2bb…` 21; opus `1137e2bb…` 21 |
| ADDS Per-line additions column absent (both models; depends on R-2.7-21) | Neither prepaid schedule presents a per-line monthly additions column; the roll-forwards are arithmetically valid; fails under the binding pre-run rule R-2.7-21 | medium | 2 / 1 | 2 / 1 | 4 | deterministic 4 | gpt `7d7fc9a7…` 21; opus `7d7fc9a7…` 21; gpt `7d7fc9a7…` 39; opus `7d7fc9a7…` 39 |
| **Total** | | | **10 / 6** | **30 / 8** | **19** | | 40 items, 8 tasks |

Notes on membership:
- `7b08cd4d…` items 16 and 17 follow the expert reference's country-level approach; the rubric item is stricter (per
  stop), and the deliverable states that no stop-level allocation is made. They are model failures against the rubric,
  recorded with that note.
- The additions line (`7d7fc9a7…` items 21 and 39, both candidates) depends on R-2.7-21 (section 7.3) and is kept out of
  M1 so that M1 counts only levels and measures omitted without a rule in play; the four items are one requirement on
  two schedules per candidate.
- M4's four items are one rounding strategy (a labelled fractional-cent line on each schedule), not four independent
  mistakes.
- `c357f0e2…` item 12 is in M2 by the author's assignment (a literal role-label failure under 2.9); GPT-6.1 Sol's
  `2ea2e5b5…` items 27 and 38 are in M2 as the same finding as Opus 5.5's (table headers read "Segment"). The
  prompt itself names the roles in the plural, as the deliverable does; the item is tagged `rubric` below.
- `c357f0e2…` item 50 (GPT-6.1 Sol): the recorded evidence says that no row edits records in two organizations with
  both edits allowed. Rows 68 (UAT-066, programs created in Org A and Org B) and 75 (UAT-073, settings changed in both
  organizations) do act in both organizations with both actions allowed, but on programs and settings, outside the
  rubric's "Idea, Proposal, or Project". The verdict stands under the rubric's scope; the evidence sentence is broader
  than the rows support. The record is not edited (adjudication records are append-only); the task verdict does not
  depend on it, because `c357f0e2…` C3 fails on item 15 as well.

What the clusters say, and which gaps a dataset could target (the author's reading; the single-run, ten-task sample
supports no rate):
- **M1 is the capability gap with business consequence, and it is GPT-6.1 Sol's.** Nine of its eleven items are stated
  in the prompt (store subtotals; the daily-sales figure behind the weekly rate, which the prompt defines and asks to
  show); the two tour items are rubric detail. In three tasks the workbook holds the
  inputs and the top-level totals, and the delivered report drops a level the task asked for: store subtotals, the
  per-stop withholding and net revenue, the daily-sales measure behind the weekly rate. Five of the eleven items are
  critical. Opus 5.5 has no confirmed failure of this kind and provides each of those levels: its 39 labelled store
  totals in an Excel PivotTable (`b5d2e6f1…` 12, 16, 25, 26), its per-stop withholding and net revenue on "Revenue
  Detail" L7:M13 (`7b08cd4d…` 16, 17) and its Daily Units Sold column for all five UPCs (`47ef842d…` 28-57), each
  author-verified and recorded (`confirmed_pass` / `grader_false_fail`, batches 2026-11-02). The `7b08cd4d…` items carry the qualification that the deliverable follows the expert reference's
  country-level approach and the rubric is stricter. The pattern is presentation simplification without a
  requirement-by-requirement check; a dataset of expert deliverables paired with the explicit list of required levels
  and measures, and a verifier that checks each level's presence and reconciliation, targets it directly (see "Data
  opportunity" below).
- **The additions line is shared.** Neither candidate presents a per-line additions column on the prepaid schedules;
  under the binding pre-run rule R-2.7-21 that fails C2 and C3 for both. The roll-forwards are arithmetically valid, so
  this is a presentation requirement both models missed, reported with its sensitivity in section 7.3.
- **M3 and M5 are shared and narrower:** a design or test plan that covers the feature but leaves the specific control
  (environment separation, bucket versioning, a load tool, identity-restricted admin access) or the exact test
  condition (a required date left blank, a cross-organisation edit) unstated. All seven items rest on judge verdicts
  that the author confirmed from the documents.
- **M7 (one item) is the kind of failure the automated layers miss:** the rule was applied correctly in the workbook and
  described incompletely in the narrative; only the blind human sample caught it.
- **M2 is the most widespread and the least consequential:** literal labels (UPCs on a chart, "Margin Impact" and "Time
  Sensitivity" as table labels, account numbers in sheet names, singular role names). It is the sole cause of Opus 5.5's
  two label-related critical fails and a contributor to three of GPT-6.1 Sol's nine (one of them together with M5),
  which is a statement about rubric literalness as much as about the models; those items are reported, not re-weighted.
  Only two of the ten M2 items are stated in the prompt (GPT-6.1 Sol's tab names without the account numbers the
  prompt's tab list gives); the other eight are the rubric's wording.

#### Requirement source

Each of the 40 confirmed failures is tagged by where the requirement it fails is stated (the page calls this the
failure source: in the prompt, rubric only, the additions rule) (`analysis/requirement_source.json`; display and analysis only, no verdict, adjudication or cluster changes). The
tags were drafted by Claude on 2026-11-03 from the task prompts and the adjudication evidence, after the runs, and
approved by the author on 2026-11-03 (status `approved` in the file). `site/build.py` checks that the tags cover
exactly the confirmed items, that every quoted prompt fragment occurs verbatim in the task prompt, and that the file
is approved with the author's decision recorded on each judgment call; otherwise the final build refuses.
- `prompt`: the prompt itself asks for the missing element (a level, measure, tab, section or statement), so a reader
  of the prompt alone would expect it.
- `rubric`: the prompt leaves the element open, and the rubric fixes its exact wording, form or detail, or adds it
  beyond the prompt. Where the deliverable covers what the prompt names in another form, the item is `rubric`.
- `rule`: the item fails only under a rule this evaluation added before the runs (R-2.7-21; the ADDS items).

| Source | Opus 5.5 rubric items | GPT-6.1 Sol rubric items | Failed tasks it decides, Opus 5.5 / GPT-6.1 Sol |
|---|---|---|---|
| `prompt` | 0 | 12 (4 tasks: `b5d2e6f1…` 16, 25, 26; `47ef842d…` 28, 35, 42, 49, 56, 57; `7d7fc9a7…` 3, 4; `1137e2bb…` 23) | 0 / 2 (`b5d2e6f1…`, `1137e2bb…`) |
| `rubric` | 8 | 16 | 2 / 4 |
| `rule` | 2 | 2 | 1 / 1 |
| **Total** | **10** | **30** | **3 / 7** |

A failed task counts under `prompt` if any confirmed item in its failing critical criteria is tagged `prompt`, else
under `rubric`, else `rule` (`site/data/metrics.json`, `task_verdicts.failed_tasks_by_requirement_source`).

Twelve tags are judgment calls (`debatable` in the file). The author approved each one as proposed on 2026-11-03
(recorded per item as `author_decision`). Read either way, they move GPT-6.1 Sol's prompt-stated failures from 3 to 15
rubric items and its failed tasks on a prompt-stated requirement from 1 to 4; all twelve are GPT-6.1 Sol failures, so
Opus 5.5's count does not depend on them
(`site/data/metrics.json`, `requirement_source_sensitivity`):
- `47ef842d…` 28, 35, 42, 49, 56, 57 (GPT-6.1 Sol), `prompt`, approved: the prompt defines the weekly rate as "daily
  inventory sold in the last 4 weeks multiplied by 7" and says "Ensure to show your work"; the deliverable shows only
  the weekly rate. Read as "the prompt asks for the weekly rate only", they would be `rubric`.
- `7d7fc9a7…` 3, 4 (GPT-6.1 Sol), `prompt`, approved: the prompt's tab list reads "Prepaid Expenses (Account #1250)" and
  "Prepaid Insurance (Account #1251)"; the deliverable's tabs omit the numbers, which appear in the sheet headers.
- `1137e2bb…` 23 (GPT-6.1 Sol), `prompt`, approved: the prompt asks for a summary "outlining the types of errors identified";
  the summary outlines them but never states what makes a case-pack line an error. Read as "outlining needs no
  definition", the item would be `rubric`, and GPT-6.1 Sol's prompt-stated task failures would fall from 2 to 1.
- `7b08cd4d…` 16, 17 (GPT-6.1 Sol), `rubric`, approved: the prompt applies withholding "by country"; per-stop amounts are the
  rubric's detail, and the expert reference also works by country.
- `c357f0e2…` 50 (GPT-6.1 Sol), `rubric`, approved: the prompt gives Super Admins access across organizations, which the
  deliverable tests in several rows; one row editing an Idea, Proposal or Project in two organizations is the rubric's
  form.

#### Data opportunity

Models leave out pieces a task asks for, and the rubrics that grade them mix what a task needs with exact wording. The
proposal: tasks where everything a deliverable must contain is listed, tagged with its source and verified by an expert,
each with a deliberately broken version of the deliverable. This is the proposal of the submission page (`site/`,
section "Data opportunity").

**Why it has to be expert-verified** (evidence from this evaluation):
- **Graders.** 67 of the 100 graded fails the author reviewed were grader errors (section 7.7).
- **Rubrics.** 8 of the 10 task failures (3 Opus 5.5, 7 GPT-6.1 Sol) turn only on rubric-only wording or detail, or
  R-2.7-21 (section 7.5).
- **Expert files.** GDPval's own expert file for the weekly sales task fails two source checks: sell-through averaged
  over rows, and a Data tab that differs from the export in 557 cells (section 6.3).

**The dataset.** One sample = one professional task, with:
1. the task prompt and its real source files;
2. a verified expert deliverable;
3. a checklist of everything the deliverable must contain (levels, measures, labels, controls, test conditions), each
   item tagged with its source (in the prompt, rubric only, or an evaluator's rule) and severity;
4. automated tests that compute expected values from the source files, and judge checks for explanations, controls
   and test conditions;
5. a deficient variant: the expert deliverable with one checklist item removed.

**Seed and scale.** The 10 tasks here, across 3 occupations, extended into task families: the same kind of work with
fresh source data. **Quality.** Built by domain experts. A second expert reviews each checklist. Every check passes on
the expert deliverable. Each deficient variant fails the checks for the item it removes and passes the rest. Where a
check and the expert disagree, a reviewer decides before the sample is accepted.

**What each lab gets.** GPT-6.1-sol: what the prompt asks for first (12 failures in 4 tasks, such as store
subtotals). Opus 5.5: none of its failures is something the prompt asked for; of its 10, 5 are professional detail the
rubric adds (environment separation, bucket versioning, a blank-date test case, sorting by error count, a case-pack
flag), 3 exact wording and 2 the additions rule. Standards an expert knows but the prompt doesn't state are its
opening; the suite also guards the breakdowns it delivers.

**Pilot and proof.** Grow 3 task families (weekly sales reporting, weeks of supply, PO entry audit); in each, 15 tasks
for training and 5 held out, on different source data; evaluate the held-out tasks, 3 runs per task. Accept if the
share of checklist items met rises by at least 10 percentage points while the numerical tests' pass rate stays within
2 points. Untested here.

**Size and cost (estimate, not measured).** 20 tasks per family, 60 samples. The GDPval paper reports that "Tasks
require an average of 7 hours of work for an expert professional to complete" (arXiv:2510.04374, section 1); with
about 4 more hours for the checklist, tests, deficient variant and a second expert's review (this proposal's
estimate), about 11 expert hours per sample, 660 in all. The parameters are in `site/content.json`
(`data.pilot_plan`) and `site/data/metrics.json` (`pilot_estimate`).

How it targets each gap (the categories above; "seen here" counts confirmed failures, rubric items, with those in the
prompt in parentheses):

| Gap | Seen here | In the dataset | What the model learns |
|---|---|---|---|
| A. Required content omitted | GPT-6.1 Sol 14 (9), Opus 5.5 3 (0) | the checklist lists every required level, measure and column; the deficient variant drops one | to deliver every required level, not only the totals |
| B. Label or display not as required | GPT-6.1 Sol 7 (2), Opus 5.5 4 (0) | the checklist marks which labels the prompt fixes and which only the rubric names, scored separately | to keep a label exact where the prompt fixes it |
| C. Document content omitted | GPT-6.1 Sol 5 (1), Opus 5.5 3 (0) | the checklist maps each required control or test condition to where it must appear; a judge check, validated on the complete / deficient pairs, tests it | to cover every specified case and control |
| D. Added line breaks a rule | GPT-6.1 Sol 4 (0), Opus 5.5 0 (0) | accounting rules, such as no unsupported adjustments, are checklist entries with tests | to respect accounting rules the task implies (low priority: one occurrence) |

**Three uses.**
- **Evaluate.** Score completeness against the checklist separately from numerical accuracy, and items in the prompt
  separately from rubric-only ones.
- **Train.** Expert deliverables as demonstrations; complete versus deficient pairs for preference training; the
  automated tests as rewards for reinforcement learning.
- **Guard.** Rerun as a regression suite on each new model version.

**Worked example and splits** (the page's worked example, M1 store subtotals):
- **Observed failure.** GPT-6.1 Sol, weekly sales analysis, rubric items 16 / 25 / 26: "Sales by Store" holds every
  store-brand row and a grand total that reconciles to the source, but no store subtotal rows, although the prompt
  asks the tab to "total the sales by store"; the store-level view cannot be read without re-aggregating. Claude Opus
  5.5's workbook carries a labelled total for each of the 39 stores.
- **Task input.** A weekly sales export (936 rows: store, brand, WTD / MTD / YTD sales quantity, sales dollars and
  stock on hand) and the instruction to build brand and store summaries with sell-through as pivot tables.
- **Business rule.** A store-level view carries one labelled subtotal per store equal to the sum of its brand rows, and
  a grand total equal to the sum of the subtotals; sell-through is the ratio of sums at each level.
- **Checklist (excerpt).** Sales by Store is a pivot table built from the Data tab (in the prompt); a labelled total for each store
  and a grand total equal to their sum (in the prompt: "total the sales by store", "include grand totals"; rubric items
  16 / 25 / 26); ST% = sales ÷ stock on hand at every level (in the prompt), computed from the totals, not averaged over rows
  (an evaluator's rule).
- **Target deliverable.** On the Sales by Store tab, a pivot table built from the Data tab with Store and Brand as row
  fields, a labelled total under each store block and a grand total, each reconciling to the export.
- **Automated test.** Sales by Store holds a pivot table whose source is the Data tab; for each of the 39 stores a labelled total equal to the independent
  recomputation from the export; the grand total equal to the sum of the store totals; ST% within 0.0005 of the ratio
  of sums; expected values computed from the source, not read from the deliverable.
- **Why verified.** GDPval's own expert file for this task fails two of these tests: its ST% averages row ratios
  (Clinique WTD 0.2467 against 0.2309 from the totals), and its Data tab differs from the source export in 557 cells,
  a difference the audit could not explain (an expert edit or another input version; section 6.3,
  `docs/expert_gold_fail_audit.md`).
- **Targeted failure type.** Dropping a requested aggregation level during presentation while the top-level totals stay
  correct.
- **Composition.** The evaluation's 10 tasks and three occupations (Order Clerks; Accountants and Auditors; Computer and
  Information Systems Managers) as the seed, extended with tasks of the same families built from real source data, each
  with an expert deliverable and its checklist.
- **Training use.** Complete / deficient pairs, the same task with and without the required level (the expert
  deliverable against a version that drops the level), labelled by the checklist.
- **Train / evaluation separation.** Within each family, training and held-out tasks use different source materials (no
  shared sales export, store list or rubric text); held-out tasks use the same frozen tests. A separate
  leave-one-family-out run measures transfer to a new family.
- **Hypothesis.** Expert deliverables carrying every requested level, with the task's checklist, raise level-presence
  pass rates on unseen same-family tasks without lowering top-line accuracy; untested.

### 7.6 Grader reliability on Formal outputs

Human blind labels vs the frozen graders on the 20 sampled items: one item per task, the same item on both candidates,
candidate identity hidden. There were no `cannot_assess`, `provider_error` or not-yet-judged items, so nothing was excluded.

| Items | All | Opus 5.5 | GPT-6.1 Sol |
|---|---|---|---|
| Deterministic | 8/10 | 4/5 | 4/5 |
| Judge (provisional label lifted under preregistration 1.25) | 9/10 | 5/5 | 4/5 |
| All | 17/20 | 9/10 | 8/10 |

Disagreements:
- F06, GPT-6.1 Sol, `1137e2bb…` item 23 (judge): human fail, grader pass.
- F15, Opus 5.5, `c3525d4d…` item 27 (deterministic): human pass, grader fail.
- F16, GPT-6.1 Sol, `c3525d4d…` item 27 (deterministic): human pass, grader fail.
- F15 and F16 are a deterministic false-fail pattern: the grader found 18.69 × 1,320 = 24,670.80 but recorded "no revised
  per-unit cost shown". The original verdicts are kept; the author's labels are recorded alongside them, and both are
  adjudicated `grader_false_fail` (section 7.3).
- F06 is a judge false pass: the Word summary gives a 1-unit / 24-pack example and names a CASE-only divisibility
  control, but never states that CASE quantities must be whole multiples of the case pack (p. 1, "Method & workbook use"
  and "Where to begin", points 2-3). It is adjudicated `grader_false_pass`; the judge verdict is kept, with the provisional label lifted under preregistration 1.25.
- False passes were searched only within this 20-item blind sample (`labeling/formal-v4-checkpoint/checkpoint.json`).
  The denominator is the number of sampled items originally graded pass, per layer: deterministic 0 of 8 (F15 and F16
  were graded fail), judge 1 of 10; 1 of 18 overall, as a count. Other false passes among the unsampled automated
  passes are not ruled out; no rate is estimated.

Formal judge coverage (provisional label lifted under preregistration 1.25): 330 of 332 judge items have a verdict (299 pass, 30 fail, 1 `cannot_assess`).
- 2 are `invalid_judge_output`, both Opus; neither is counted as a fail.
- Opus: 164/166 with a verdict. GPT: 166/166.
- Visual items (18 per candidate) await human verdicts and are not evaluated.

Verification scope, stated exactly:
- The author decided every one of the 170 worksheet rows. For each, the author reviewed the deliverable directly or a
  rendered page / extracted cell values located by an AI assistant (Claude), alongside the Codex draft.
- Adjudication of all 170 rows is complete; after a consistency review four rows were re-graded by hand from `leave` to
  `verified_fail` (Opus `7d7fc9a7…` 21 / 39, GPT `2ea2e5b5…` 27 / 38) and one from `leave` to `verified_pass` (GPT
  `b5d2e6f1…` item 12, the PivotTable confirmed in Excel). The 42 `leave` decisions remain unresolved item-level
  coverage gaps, not verified passes or fails, even where their criterion already fails on another member: grader read
  failures confirmed but not re-graded by hand (Opus `7d7fc9a7…` C2-C3, GPT `2ea2e5b5…` C3). An item-key comparison across candidates found no confirmed counterpart for any of them.
  Four leave decisions (Claude Opus 5.5, 7d7fc9a7 C1, items 13, 14, 33 and 34) were later changed to verified_pass
  after an invoice-by-invoice reconciliation, extracted by Claude and spot-checked by the author on four invoices.
- Separate from the worksheet and from the 20-item random blind sample above: 24 representative checks, one per
  grader-defect pattern (D01-D24), were blind-reviewed by a second model briefed only with the task materials, the item
  key and the rubric text (22 satisfied, 2 rubric ambiguous; `~/turing-eval-runs/analysis/critical_adjudication_checks.csv`).
  Author verification of the defect diagnosis is recorded on five (D07, D08, D11, D18, D23: the four disagreements plus
  D08, the site's example). Of the other 19, the ten whose items are among the adjudicated rows (D01, D04, D05, D09,
  D12, D14, D15, D16, D17, D22) carry an author item decision but no separate verification of the diagnosis; the nine
  whose items are non-critical and outside the worksheet (D02, D03, D06, D10, D13, D19, D20, D21, D24) carry neither.
  The author's item decisions on D07, D08 and D23 were imported into the adjudication layer as grader false fails
  (non-critical items); item adjudication and diagnosis verification are separate records.

Context:
- Dev judge agreement 4/6 on the first pass.
- Held-out Validation deterministic agreement 4/6 (V1).
- Judge Validation judge-only agreement 3/3, with the debug-set item excluded and all labels pass; Validation judge
  coverage 163/166.

### 7.7 Triage of the non-pass items (AI-assisted draft, not a human-adjudicated distribution)

An OpenAI Codex static review of the read-only failure bundle (`analysis/codex_failure_review/`, its README states its
scope) classifies the 239 reviewed non-pass items, of 265 in all (the other 26 are 24 pending non-critical visual items and
2 invalid judge outputs), as 33 `model_error`, 2 `model_format_deviation`, 92 `grader_false_fail`, 77 `grader_read_failure`
and 35 `rubric_ambiguous`. This is an AI-assisted draft, not a human-adjudicated distribution, and it changes nothing in the
scores: the frozen item-level verdicts stay as graded for the preregistered evaluation. Verified grader false fails can
understate a candidate's performance and verified false passes can overstate it; the net direction is unknown, and false
passes were searched only in the 20-item blind sample (section 7.6). Read failures and judge evidence-pack gaps are coverage
limits (section 7.2) and are reported separately from grading errors. Targeted human adjudication covers the critical
criteria and the draft's taxonomy rows (`~/turing-eval-runs/analysis/critical_adjudication.md`); the separate 20-item blind
sample and the visual reviews are reported independently of it.

Human adjudication of the 170 worksheet rows (every non-pass member of a critical criterion that was fail or
not_confirmed as graded, every draft model-error row and F06; `~/turing-eval-runs/analysis/critical_adjudication.csv`,
recorded as adjudication batches): 67 grader false fail, 33 confirmed fail, 21 verified pass, 6 verified fail, 1 false
pass, 42 left. This is the human-adjudicated breakdown of the worksheet; the adjudication layer holds 183 items (the
worksheet, three non-critical grader false fails imported from the defect review, and ten `confirmed_pass`
verifications of Opus 5.5 automated passes), and the 239-item breakdown above
remains the labelled AI draft of a different population (the worksheet adds one automated pass and leaves out 70
non-critical draft rows; corrected on 2026-11-03 from "69", which subtracted the 170 instead of the 169).

Count flow (`site/data/metrics.json`, `review_count_flow`, reconciled at build time): 265 non-pass items = 239 graded
fail or cannot assess + 24 visual items without a verdict + 2 invalid judge outputs. Of the 239, 169 were reviewed by
hand (145 inside critical criteria, 24 draft model errors) and 70 were not (60 graded fail, which the draft classes as
29 grader false fails and 31 ambiguous rubric items; 10 cannot assess; all outside critical criteria); with the one
automated pass from the blind audit (F06), 170 were reviewed. By graded verdict, the 170 are 100 fail (67 grader false
fail, 33 confirmed), 69 cannot assess (21 verified pass, 6 verified fail, 42 left) and 1 pass (the false pass). Grader
false fails are therefore 67 of the 100 reviewed graded fails (67%) and 39% of the 170. Not reviewed: 96 (70 + 26). Before the adjudication, a projection from the draft classes with the author's overrides
(`~/turing-eval-runs/analysis/projection.json`, kept as a record) put the critical criteria at Opus 5.5 28 / 2 / 5 and GPT-6.1 Sol 22 / 8 / 5;
the adjudicated result (section 7.3) is 31 / 4 / 0 and 26 / 9 / 0.

Verification of the draft: its citations were checked one by one and recorded as verified, mismatched or not mechanically
checkable (2,341 citations covering all 239 draft items: 1,567 verified, 774 not mechanically checkable, 0 mismatched;
`~/turing-eval-runs/analysis/citations.csv`). "Verified" means that record's mechanical check passed (for some, only that the file or
location exists), not that a value or conclusion is confirmed. One representative per defect pattern was blind-reviewed by
a second model, and the author verified the disagreements and the cited examples (section 7.6); the remaining rows under
each pattern stay draft classifications.

---

## 8. Limitations, costs, provenance and reproducibility

### 8.1 Costs

These are ledger settlements, the harness's own accounting from provider-reported usage. They are not provider
invoices. "Estimated" marks the inferred or conservative portions. Sources: `docs/status.md` "Final verification on
`df4a560`" (re-verified figures), "Judge Dev Pass 2 ...", "GPT compat reconciliation ..." and "Formal generation
complete".

| Workload | Model(s) | Settled (USD) | Of which estimated (USD) | Note |
|---|---|---|---|---|
| Dev generation (10 canonical plus the earlier attempts) | `gemini-3.8-flash` | 22.255219 | 5.452624 | ceiling 100 |
| Validation generation (10) | `gemini-3.8-flash` | 17.488478 | 4.808123 | ceiling 100 |
| Compatibility (task `87da214f…`, 2 samples) | Opus 5.5, GPT-6.1 Sol | 2.043342 | — | The GPT unit was reconciled at 0.472138 USD inferred from 24 usage-reporting calls, not invoice-verified. Ceiling 45 |
| Judge Dev (Pass 1 and Pass 2) | `gemini-3.1-pro-preview` | 11.636271 | 0.550000 | Conservative ledger. At the per-call standard tier: 6.525 + 0.031366. Ceiling 30 |
| Judge Validation (complete, three projects) | `gemini-3.1-pro-preview` | 4.847818 | 0.913046 | `~/turing-eval-runs/judge_validation/ledger.json` (`ledger_admin status`, 2026-11-02): 13 settlements after the two manual resolutions (0.856327 and 0.056719 USD inferred, not provider-confirmed; reconciliation with Google billing pending). Ceiling 15 |
| Formal generation (20) | Opus 5.5 / GPT-6.1 Sol | 17.979211 (14.900901 / 3.078310) | none recorded | No hold, estimate or stop |
| Formal judge pass | `gemini-3.1-pro-preview` | 12.079453 | 1.665296 | ceiling 30; `~/turing-eval-runs/judge_formal/ledger.json` |
| Human review time | — | about 3 hours in total (author estimate, not measured) | | Covers the 20 formal blind labels, the 12 visual verdicts, the 170 worksheet decisions and the five representative verifications; excludes reading the AI-assisted drafts |
| **Recorded subtotal** (sum of the rows above that have a value) | | **88.329792** | | All paid workloads; the inferred portions are listed per row |

Formal generation cost per run (run-level metadata; `docs/status.md` "Formal generation complete"):

| Task | Opus 5.5 (USD) | GPT-6.1 Sol (USD) |
|---|---|---|
| `b5d2e6f1…` | 1.493437 | 0.302156 |
| `f841ddcf…` | 0.921411 | 0.181770 |
| `47ef842d…` | 1.115620 | 0.324796 |
| `1137e2bb…` | 1.677193 | 0.243842 |
| `c3525d4d…` | 0.687388 | 0.230607 |
| `7b08cd4d…` | 0.917356 | 0.267212 |
| `7d7fc9a7…` | 1.673360 | 0.376698 |
| `2ea2e5b5…` | 0.588023 | 0.223819 |
| `c357f0e2…` | 1.644991 | 0.324154 |
| `a45bc83b…` | 4.182122 | 0.603256 |
| **Total** | **14.900901** | **3.078310** |

The two models are priced differently (section 2.1), so equal cost does not mean equal compute.

Budgets authorized for Formal (`config.json` `batches.formal.budget_decision`, `judge.formal`):
- Generation has a 150 USD admission threshold. The modeled worst case is 165 USD (150 − the last 5 USD reservation +
  one in-flight 20 USD sample), and the author approved that.
- The two-worker change raised the per-candidate ledger ceilings to 200 USD. The modeled worst case then became about
  361.80 USD, not measured. Realized spend was 17.979211 USD.
- The Formal judge has a 30 USD ceiling.

### 8.2 Known limitations

- **Sample size.** 10 tasks, k = 1, 20 samples, chosen purposively. There is no basis for confidence intervals on
  capability, and per-task results are single observations.
- **Protocol.** Item-by-item rubric scoring is not GDPval's pairwise expert preference, so the numbers are not
  comparable to published win rates.
- **Requirement source.** The `prompt` / `rubric` / `rule` tags of section 7.5 were made after the runs, from the
  prompt texts (Claude's draft, the author's review); they change no verdict. Twelve are judgment calls, listed there and
  each approved by the author;   read either way, GPT-6.1 Sol's prompt-stated failed tasks range from 1 to 4 (2 as tagged); all twelve are GPT-6.1 Sol
  failures.
- **Grader reliability.**
  - n = 36 blind item labels in all.
  - Dev judge agreement was 4/6 on the first pass. Held-out Validation deterministic agreement was 4/6, and both
    misses were grader defects that are now corrected but not re-validated on held-out data.
  - Judge Validation: 3/3 judge-only items agree with the author, all four labels and verdicts pass, so failure
    detection is untested. `1137e2bb…` item 28 also agrees but is excluded as a judge debug-set item. Coverage is
    163/166 Validation judge items; three are infrastructure failures, never fails (`docs/status.md` "Judge Validation
    complete").
  - The judge and the development model share a provider family.
  - 100% rubric coverage does not mean 100% definitive or accurate grading.
- **Deadline exception.**
  - The Formal judge pass started at `freeze-v1-grading` (11:57:25Z) before the Judge Validation agreement was
    measured and before the independent recheck of V1.9 (`preregistration.md` 1.25).
  - The agreement was measured at about 12:17Z with the same frozen judge.
  - The recheck then ran and was closed by the author with its findings recorded below. With both conditions recorded,
    the provisional label on the Formal judge verdicts was lifted under `preregistration.md` 1.25 (the author's
    decision of 2026-11-02). Held-out judge agreement is 3/3, all passes, so failure detection is untested.
- **Codex recheck 2 of V1.9 (`<tmp>/codex-recheck2/review-UaziWR8v/REVIEW.md`): known limitations.**
  - The author closed it without a code change, refreeze or further round before submission. All four findings
    concern stop / pause control, under conditions not present in this run.
  - B1 (Blocking): the Judge Validation terminal-stop marker (`resume_stop`) is written after the `recovery_done` /
    `run_done` record that already carries the non-quota halt. A process interrupted between the two writes would
    leave no durable refusal for a later resume.
  - B2 (Blocking): the formal entry removes `GOOGLE_API_KEY` from the environment before the project selector reads
    the refused other-workload keys. A selected key equal to the Dev project's key would then pass the generic
    cross-workload check; the fixed historical Dev-suffix check remains.
  - B3 (Blocking): pauses and switches are bound to the variable name. Two variables holding the same key would count
    as two projects, and a switch would close that same project's own quota pause.
  - N1 (Non-blocking): the Judge Validation CLI selects the project before checking for a terminal stop. Resume still
    refuses before any recovery or run.
  - Checks in this run, 2026-11-02, nothing printed but booleans and event kinds:
    - `GOOGLE_API_KEY`, `GOOGLE_API_KEY_VALIDATION` and `GOOGLE_API_KEY_JUDGE` hold three distinct values (compared
      by hash). The B2 and B3 conditions are therefore absent.
    - No `run_done` / `recovery_done` record of either judge pass carries a non-quota halt without its terminal
      marker, apart from two 2026-11-01 Judge Validation records. Those predate the V1.9 rule and were resolved by
      the author's authorized recoveries and resumption. The formal pass has no non-quota halt; its only halt is the
      12:40:03Z daily-quota pause. The B1 situation did not occur.
- **Judge-project quotas.**
  - The Dev and second Google projects each allow 250 `gemini-3.1-pro` requests per day (the provider's 429 detail).
    The second project's quota was exhausted at 12:40:03Z during the formal pass, which continued as the same pass
    on the third project (`project_switch`, only unfinished items, one worker).
  - The Formal pass needs 332 items before retries, so it may span quota days and projects.
  - Daily-quota pauses, project switches and exhausted items are recorded. Missing verdicts are never FAILs, but they
    reduce coverage and leave criteria `not_confirmed`.
- **Known grader defect, `c3525d4d…` item 27** (found by the formal blind labels F15 / F16, no grader change before
  submission):
  - The deterministic check recorded "no revised per-unit cost shown" on both candidates, although it found revised
    unit cost 18.69 x 1,320 = 24,670.80 in the recorded cells.
  - Adjudicated `grader_false_fail` for both; the frozen verdicts are kept.
  - Items 16-20, 26, 31 and 49 of the same criterion were adjudicated `grader_false_fail` for both candidates and items
    28-30 `verified_pass` (batch 22:05:01Z), so C2 is pass as adjudicated for both; the frozen verdicts stay fail.
- **Unresolved coverage gaps after adjudication.** 42 `cannot_assess` items were left (`leave`): grader read failures
  confirmed but not re-graded by hand. They remain item-level gaps inside criteria that already fail on another member
  (Opus `7d7fc9a7…` C2 / C3, GPT `2ea2e5b5…` C3), so they change no adjudicated critical status. They are not verified
  passes or fails, and an item-key comparison found no confirmed counterpart for any of them on the other candidate.
  Opus `7d7fc9a7…` C1's four unresolved items were verified pass by an invoice-by-invoice reconciliation (section 7.3).
- **Post-run adjudication policies** (section 5.5) were decided by the author after the reveal and applied to both
  candidates; the frozen rules are unchanged, and the sensitivity of the one binding pre-run rule involved (R-2.7-21)
  is stated in section 7.3.
- **False passes.** Searched only within the 20-item formal blind sample (`labeling/formal-v4-checkpoint`). Of the
  sampled items originally graded pass: deterministic 0 of 8, judge 1 of 10 (F06, GPT-6.1 Sol `1137e2bb…` item 23,
  adjudicated `grader_false_pass`); 1 of 18 overall, as a count. Other false passes among the unsampled automated
  passes are not ruled out; grader errors run in both directions and their net effect on the scores is unknown.
- **Grader read limits on two formal runs.** These items are `cannot_assess`, never FAIL:
  - Opus `7d7fc9a7…`: 29 items. The vendor synonyms include "description", which collides with a real Description
    column.
  - GPT `2ea2e5b5…`: 33 items. The slide heading is taken from the first text line, which is a repeated kicker on
    every slide.
- **Pre-existing stale harness test.** The harness suite passes 218/219. The one failure,
  `test_launcher_regressions…placeholder_ceiling`, expects the Formal ceiling to be a placeholder. It has been 150
  since `be84ff6` and fails identically on `b33cc37`. It has not been corrected (`docs/status.md` "Codex delta
  review" and "Grading freeze").
- **Blinding.**
  - Model identity is hidden in judge inputs and packet text.
  - The Formal deliverable files themselves are not blinded: their embedded file metadata were not altered, since
    raw outputs are immutable. Checked on 2026-11-02 (`docProps/core.xml` and `app.xml` of every packet workbook,
    document and deck): no creator, last-modified-by, application or company field names a model or vendor; the
    fields hold library defaults ("python-docx", "openpyxl", python-pptx's "Steve Canny") or role names the models
    wrote ("Solutions Architecture", "Finance Lead", "Wholesale Sales Operations"). The producing application differs
    by file (openpyxl, LibreOffice 7.4 or "Microsoft Excel" strings), which a reader familiar with the tooling could
    use as a weak fingerprint; the blind labellers were not told which was which.
- **Formal generation deviation.**
  - Units 3-20 ran in two per-candidate ledgers under a config snapshot that differs from the frozen config only in
    the ledger ceiling. Generation code and model-visible conditions were unchanged.
  - The units ran at concurrency 2 (one per candidate), not at the frozen concurrency of 1.
- **Unequal compute.** The two candidates share a nominal "high" effort with different mechanisms, prices and
  tokenizers.
- **Environment.**
  - The sandbox runs as root with every capability dropped.
  - The image ID is local to this Docker daemon (linux/arm64) and is not resolvable elsewhere unless exported.
  - The GCP resources are a fixed 2026-10-29 snapshot, and the live pages change.
- **Visual and image-only evidence.** The 18 visual items, and any picture-chart-dependent items, need human
  verdicts. Without one they are `not evaluated` or `cannot_assess`.
- **Post-dated rules.** Some adjudications and review-queue policies were adopted on 2026-11-01, after the initial
  preregistration. They are marked "not preregistered" in `preregistration.md` 1.14 and 1.18-1.19.
- **Deliverable integrity (observation, not a rubric result).** GPT-6.1 Sol's `Weekly Sales Analysis.xlsx` opens in
  Excel for Mac only after Excel's repair prompt ("[Repaired]"); Numbers and openpyxl open it without repair, and its
  PivotTables survive the repair (section 7.2). The package irregularity (both PivotTables share a cache id, one cache
  definition is unregistered) was noted by the blind reviewer of the defect representatives. No item scores it.
- **Author choices.** The author chose the 35 critical requirements (fixed before the runs) and rated severity (after
  review).
- **No domain expert.** No step was reviewed by an industry domain expert (`README.md`).
- **Costs.** All figures are ledger settlements. The inferred portions still need reconciliation with provider
  billing. Formal generation alone: Opus 5.5 14.900901 USD, GPT-6.1 Sol 3.078310 USD (page: $14.90 and $3.08), at the
  same "high" effort label (section 8.1; the three formal generation ledgers, by model).

### 8.3 Provenance

- **Dataset.** `openai/gdpval` at `11e7900cdcac61bc4daf59e65feb238acda98fbf`, parquet SHA-256 `f8422fab…`. Every
  input, expert deliverable, rubric and prompt is verified against the hash Hugging Face records for it
  (`data/dataset_revision.json`, `data/download_verification.json`, `data/manifest.json`).
- **Freeze records.** `harness/freeze/freeze-v1-generation.json`,
  `grading/freeze/freeze-v1-grading-deterministic.json` and `grading/freeze/freeze-v1-grading_manifest.json`. The
  calibration freeze is `grading/freeze/v1_manifest.json` (tag `v1-calibration-freeze`).
- **Per run and per pass.** The code commit with a dirty flag, the `config.json` SHA-256, the system prompt SHA-256,
  the image id, the grader version (`<engine>+<task>`) and the judge id are recorded. Run artifacts, ledgers, judge
  write-ahead logs and the sealed grades live outside the repository under `~/turing-eval-runs/`.
- **Test evidence at `freeze-v1-grading` (`cc684ef`):**
  - grading: 540 tests, 5 skipped, OK;
  - harness: 218/219, the stale test above;
  - Docker-gated suites 13/13 rc 0, with a clean tree before and after and no Formal unit running
    (`logs/docker-gated-cc684ef-20261102T115227Z/HEADER.txt`, `SUMMARY.txt`).

### 8.4 How to reproduce

The commands below are from `README.md` and `docs/codex_review_2.md`. Paid steps need an authorization and
credentials in `.env`, which the launcher reads.

```
# Environment and data (no credentials; network access to huggingface.co)
uv sync --frozen
.venv/bin/python scripts/fetch_dataset.py --revision-file data/dataset_revision.json --out data/gdpval.parquet
.venv/bin/python scripts/resolve_tasks.py --parquet data/gdpval.parquet --out data/selected_tasks.json \
    --deep b5d2e6f1 f841ddcf 47ef842d 1137e2bb c3525d4d \
    --supplementary 7b08cd4d 7d7fc9a7 2ea2e5b5 c357f0e2 a45bc83b
.venv/bin/python scripts/download_materials.py --parquet data/gdpval.parquet \
    --tasks data/selected_tasks.json --revision-file data/dataset_revision.json \
    --log data/download_verification.json
.venv/bin/python scripts/fetch_gcp_resources.py --parquet data/gdpval.parquet \
    --task-id a45bc83b-22f9-4def-8d89-9c5661b2b86f   # live pages change; hashes identify the 2026-10-29 fetch

# Sandbox image (re-pin the full image ID in harness/compose.yaml and config.json, see README "Sandbox image")
docker build -f docker/sandbox/Dockerfile -t gdpval-sandbox:stage2 docker/sandbox

# Check out a frozen state and verify its record
git checkout freeze-v1-generation        # or freeze-v1-grading
.venv/bin/python -m grading.freeze_manifest verify --manifest grading/freeze/freeze-v1-grading_manifest.json

# Generation: preflight without a provider call, then one batch per candidate (paid)
.venv/bin/python -m harness.launcher --dry-run --run-label formal --runs-root ~/turing-eval-runs/formal/runs \
    --ledger ~/turing-eval-runs/formal/ledger.json --task-id <task_id> --model <provider/model> --estimate-usd <usd>
.venv/bin/python -m harness.batch --run-label formal --model <provider/model> --runs-root <root> --ledger <ledger> \
    --real-run --confirm-batch '<label>|<model>|<n>|<usd>' --authorized-by '<name>' --authorization-ref '<ref>'

# Deterministic grading of one saved run (no provider call)
.venv/bin/python -m grading.run_grading --host-dir /abs/runs/<uuid> --eval-log /abs/runs/inspect_logs/<unit>/<log>.eval \
    --task-id <task_id> --out-dir /abs/grading/<uuid> --ledger /abs/ledger.json --unit-id '<generation unit id>'

# Tests (minimal environment, mockllm, no model API)
harness/tests/run_isolated.sh <module>
```

- The judged pass of a single run uses `run_grading --judge` (see `README.md`).
- The Formal and Validation judge runners are `grading.judge_formal` and `grading.judge_validation`, with
  `--credential-env` for project selection. Their commands (module docstrings): `python -m grading.judge_formal check | run | resume | status [--credential-env VAR]`, where `run` and `resume` restate the author's authorization with `--authorized-by WHO --authorization-ref REF --confirm 'judge-formal|<judge model>|<ceiling>'`, `check` performs every gate without a call and `status` reports the pass, the ledger and any stop; `python -m grading.judge_validation plan | check | run | status | recover | resume [--credential-env VAR] [--env-file PATH]`, with `recover --run-uuid <run> --items <i,j,...>` for the bounded per-item recovery and `resume` refusing at entry after a terminal stop (`preregistration.md` 1.24-1.25). `--credential-env` names the Google key variable (project) for the workload, one of `config.json` `judge.<workload>.credential_envs`.
- Results can be reproduced exactly only from the run artifacts under `~/turing-eval-runs/`, which are not in the
  repository. A fresh generation is a new sample, not a replication of these runs.
