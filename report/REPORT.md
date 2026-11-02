# GDPval diagnostic evaluation: report

Draft scaffold, written 2026-11-02. Formal results are sealed until the human's 20 Formal blind labels are
checkpointed. Every Formal score, pass rate, comparison, judge verdict and failure example in this document is a
placeholder. Every number that is filled in names the file it comes from.

Placeholder conventions:
- `TBD (Formal results sealed)`: a Formal result.
- `{{FORMAL: ...}}`: what goes here once Formal results are unsealed.
- `{{PENDING: ...}}`: a non-Formal measurement or record that does not exist yet.

How this report maps to the assignment brief (`Field-Engineer-Take-Home-Project.pdf`):

| Brief part | Section |
|---|---|
| 1. Run an evaluation: what ran, how it was graded, what it cost | 2, 3, 5, 8.1 |
| 2. Failure modes, classified by hand | 6 |
| 3. Gaps and opportunities: where the models fell short, which gaps data could close | 7.5 and `report/dataset_proposal.md` |
| 4. Live pitch | not in this document; audience notes are placeholders in `report/dataset_proposal.md` section 7 |
| Limits: sample size, grader reliability, cost | 4, 8 |

---

## 1. Summary

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

**Headline findings.**
- {{FORMAL: 3-5 findings, each with its numerator/denominator, the human-verification status of every cited
  critical FAIL, and the file that holds it (`results.jsonl` / `grades.jsonl` pass id)}}
- {{FORMAL: where the two candidates differ, stated per task with coverage (E/W). Models with different coverage
  are not ranked by P/E alone}}
- {{FORMAL: which observed gaps a dataset could close (section 7.5)}}

**State of the measurement on 2026-11-02** (`docs/status.md`, sections from "Formal generation complete" onward):

| Step | State |
|---|---|
| Formal generation | Complete: 20/20 samples. No hold, stop, limit event or engineering failure. 17.979211 USD settled (run-level metadata, not a quality result) |
| Deterministic grading | 20/20 sealed deterministic-only passes at `freeze-v1-grading-deterministic` |
| Formal judge pass | Launched 2026-11-02 11:57:25Z at `freeze-v1-grading` under a deadline exception, so its verdicts are provisional (section 8.2). {{PENDING: completion state, items judged, provider errors}} |
| Formal blind labels (20) | Packets built. {{PENDING: label checkpoint timestamp and SHA-256}} |
| Judge Validation agreement | Not yet measured. {{PENDING}} |
| Independent recheck of V1.9 (`freeze-v1-grading`) | Not done (section 4.5) |

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
3. **Units 3-20: one `harness.batch` worker per candidate**, on the human's deadline decision. Each worker ran the
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
101 and 87. They were not recomputed for this draft because the rubric files are not read here.
{{PENDING: recompute W per task from the rubric files in the reporting script}}

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

`f841ddcf…` carries five criteria, but `PLAN.md` section 4 says each task carries two to four. {{PENDING: correct
`PLAN.md`}}

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
cases. It found no grader-reading defect. The human's decisions on the audit are recorded in `preregistration.md`
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
  - The human labelled the 10 queue-v4 Validation items from verdict-free packets. The labels were checkpointed at
    2026-11-01T23:26:55Z, before any verdict was revealed.
  - **Held-out deterministic stratum: 4/6 agreement against grader V1.** The two disagreements (`2ea2e5b5…` item 45,
    `c3525d4d…` item 32) were false fails. They were diagnosed as grader implementation defects and corrected as V1.3
    for both candidates, and that held-out result stays as first recorded.
  - Re-grades under V1.3 and V1.3.1 are regression evidence only (`preregistration.md` 1.21, 1.23).
  - Judge-only stratum (4 items: `1137e2bb…` 28, `47ef842d…` 57, `7d7fc9a7…` 18, `c357f0e2…` 24): {{PENDING: needs
    the Judge Validation verdicts}}.
  - `PLAN.md` section 6 states that every judge-only criterion of `1137e2bb…` was used to debug the judge assembly,
    which leaves that task no held-out judge criterion. {{PENDING: check `1137e2bb…` item 28 against
    `grading/debug_set.json`; if it is a debug item, exclude it from the judge agreement statistic}}
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
- **Agreement:** {{PENDING: judge-human agreement on the 4 judge-only Validation labels, numerator/denominator;
  judge coverage and infrastructure-verdict counts}}.

### 4.5 Independent reviews (OpenAI Codex, read-only)

The author reviewed every finding before any change was made. Each correction is recorded in `preregistration.md`
with its old rule, its evidence and its new rule, and each has regression tests that fail on the pre-fix code.

| Review | Target | Verdict | Findings and corrections | State |
|---|---|---|---|---|
| Stage-1 re-check | materials and recalculations, 2026-10-29/30 | findings | Several corrections followed (`docs/status.md` "Independent re-check"): exact rational arithmetic for `7d7fc9a7…` (929,354.31); withdrawal of the blanket ±0.50 USD tolerance; source-based store counts for `47ef842d…`; operational definitions for under-specified tasks | closed |
| Harness and pilot-grader reviews | 2026-10-30 to 2026-11-01 (Stage 2, Pilot-A pre-review, final, close-out, extraction, Stage 3b, B2) | blocking findings | collector containment, run binding, ledger atomicity, usage recovery, extraction pipeline, pass selection | closed (B2: "READY FOR B2 COMMIT") |
| Review 1 | shared spreadsheet grading core (`bd5713b`) | BLOCKED | B1-B4 and P1 fixed (`9b1df11`). The closure checks found two further B2 remainders, also fixed. READY at `a9a1f88` | closed, accepted by the human |
| Review 2 | `5121e1a` | BLOCKED | R2-B1 (WAL merged schema-retry attempts), R2-B2 (a failed latest recovery hidden by an older complete pass), R2-B3 (inferred cost marked reliable), R2-B4 (budget guard excluded inferred liability), R2-B5 (labels accepted across runs). Corrected in V1.4 (`7e30849`). Non-blocking N1-N5: N1 and N3 fixed (N3 at `b33cc37`), N2 and N4 accepted as limitations, N5 closed by Docker evidence | B1-B5 confirmed by the later recheck |
| Delta review | `b33cc37` | BLOCKED | D1 (per-request budget bound), D2 (Judge Validation stops), D3 (recovery base selection), N1 (no-hold exception basis). Corrected at engine .12 (`2eb4060`, `v1.7-delta-review-corrections`) | D1, D3 and N1 confirmed by the recheck |
| Recheck | `v1.8-formal-roots` (`b7ce2db`) | BLOCKED on one D2 path | It confirmed D1, D3, N1, N3 and the six original Review 2 probes. The blocking path: a standalone `recover()` halt was not persisted as a terminal stop. Corrected in V1.9 (`e081f6d`) and frozen with explicit judge projects at `cc684ef` | **open: V1.9 not yet independently rechecked** |

`docs/status.md` states that no claim is made that the grading pipeline passed independent review in full. The V1.9
changes (D2 terminal stops, the formal stop result, task-order judging, explicit judge projects) are unreviewed.
{{PENDING: outcome of the V1.9 recheck}}

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

- Judge Validation agreement. {{PENDING}}
- Independent recheck of V1.9. {{PENDING}}
- 20 Formal blind labels and their agreement statistics. TBD (Formal results sealed)
- Human verification of every critical FAIL cited in sections 1, 6 or 7. TBD (Formal results sealed)
- The rubric-to-capability map (`preregistration.md` 1.17) is a rule-based draft "approved at `freeze-v1`". No
  approval record was found in `docs/status.md`. {{PENDING: confirm the review and approval status before it is
  used in section 7.4}}

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
  - an image-only critical member needs the human's visual judgment before its criterion status is reported.
- **Reporting.** n = 36 labels is a limited reliability check, not a precise accuracy estimate. Agreement measures
  consistency, not correctness.
- **Human review time:** {{PENDING: labelling and verification time per phase}}.

### 5.4 How the layers combine

| Item route | Verdict source | Counted in E (graded weight) | Effect on critical status |
|---|---|---|---|
| Deterministic | grader | `pass` / `fail` yes; `cannot_assess` no (stays in W, listed with its reason) | a member `fail` fails the criterion; `cannot_assess` leaves it `not_confirmed` |
| Judge-only | judge | `pass` / `fail` yes; the judge's own `cannot_assess` no | as above |
| Judge infrastructure verdicts (`provider_error`, `not_run`, `judge_parse_error`, `invalid_judge_output`) | none | no. They are excluded from E like any ungraded row | `not_confirmed`, **never a FAIL** |
| Visual | human | `pass` / `fail` yes; no human verdict: `not evaluated` (stays in W) | `not_confirmed` |
| Picture-chart-dependent items | grader (`cannot_assess`, `visual_review`) | no, until a human verdict | the human's visual judgment is needed before the criterion status is reported |

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

---

## 6. Failure taxonomy and critical-case analysis

This section gives the structure only. It is built from `PLAN.md` section 5 and `preregistration.md` 1.10, 1.11,
1.14, 1.17 and 1.19.

### 6.1 Unit and scope

- **Failure event.** A rubric-item FAIL, or a critical-criterion FAIL, on a Formal candidate output. A critical FAIL
  counts as confirmed only after human verification.
- **Triage.** All failures, incomplete runs, `cannot_assess` items and critical disagreements enter triage after the
  blind labels are saved, and passes are sampled for false passes. Triage never adds items to the agreement sample.
- **Depth.** About 20-30 events are investigated in depth. They are selected by business impact, severity,
  uncertainty and capability family, and kept separate from the agreement statistics.

### 6.2 Classification axes

1. **Observable error class.** This is the primary capability of the rubric item, from the draft map in
   `preregistration.md` 1.17:

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

### 6.5 Results of the failure analysis (placeholders)

| Error class | Opus 5.5: events (critical) | GPT-6.1 Sol: events (critical) | Tasks affected |
|---|---|---|---|
| requirements | TBD (Formal results sealed) | TBD | TBD |
| grounding | TBD | TBD | TBD |
| rule_execution | TBD | TBD | TBD |
| coverage | TBD | TBD | TBD |
| consistency | TBD | TBD | TBD |
| mechanics | TBD | TBD | TBD |
| presentation | TBD | TBD | TBD |
| task-material / grader / environment (not model) | TBD | TBD | TBD |

Exemplar critical cases:
- {{FORMAL: 3-5 human-verified critical failures, each with the task, criterion, observable error, evidence location,
  cause judgment, business impact and verification record}}
- {{FORMAL: overturned verdicts and reclassifications (grader, dataset, rubric, environment), with counts}}

---

## 7. Results

All values in this section are placeholders. Each figure, once filled in, must trace to a versioned `results.jsonl`
or `grades.jsonl`, the selected pass id and `config.json`.

### 7.1 Run inventory and deliverables

| Task | Opus 5.5: deliverables present / required | GPT-6.1 Sol: deliverables present / required | Wall time (Opus / GPT) |
|---|---|---|---|
| each of the 10 tasks | TBD (Formal results sealed) | TBD | {{FORMAL: from run_outcome / Inspect log}} |

### 7.2 Scores per task and model

| Task | Model | P/E | E/W | Ungraded items (reason: count) | Critical status (current) | Critical status (preregistered) | Judge completeness |
|---|---|---|---|---|---|---|---|
| each of the 10 tasks x 2 | | TBD (Formal results sealed) | TBD | TBD | TBD | TBD (differs only for `2ea2e5b5…`) | {{PENDING: complete / partial}} |

### 7.3 Critical criteria (35 per candidate)

| Criterion | Opus 5.5 | GPT-6.1 Sol | Human verification of each FAIL |
|---|---|---|---|
| each of the 35 criteria | TBD (Formal results sealed) | TBD | TBD |

### 7.4 Capability profile

Per task and capability class, with numerators and denominators and no pooled headline percentage
(`preregistration.md` 1.17): TBD (Formal results sealed). {{PENDING: the capability-map approval status, section
4.7}}

### 7.5 Where the models fell short, and which gaps a dataset could close

- {{FORMAL: gaps observed, by error class and task, with evidence}}
- {{FORMAL: for each gap, whether better data could address it (evaluation, training or both), linked to the
  proposals in `report/dataset_proposal.md`}}

### 7.6 Grader reliability on Formal outputs

| Measure | Opus 5.5 | GPT-6.1 Sol |
|---|---|---|
| Human vs automated verdict on the 10 blind items (5 critical-member, 5 judge-only) | TBD (Formal results sealed) | TBD |
| Judge items with an evidence-based verdict / 166 | TBD | TBD |
| Judge infrastructure verdicts (`provider_error`, `not_run`, `invalid_judge_output`) | TBD | TBD |
| Judge vs deterministic disagreements adjudicated | TBD | TBD |
| Visual items evaluated / 18 | TBD | TBD |

Context:
- Dev judge agreement was 4/6 on the first pass.
- Held-out Validation deterministic agreement was 4/6.
- Judge Validation agreement: {{PENDING}}.

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
| Judge Validation, as of the 2026-11-02 final verification | `gemini-3.1-pro-preview` | 1.241102 | 1.191394 | Includes inferred settlements that need reconciliation with Google billing. Ceiling 15. {{PENDING: spend after the 2026-11-02 resumption and the third-project handoff}} |
| Formal generation (20) | Opus 5.5 / GPT-6.1 Sol | 17.979211 (14.900901 / 3.078310) | none recorded | No hold, estimate or stop |
| Formal judge pass | `gemini-3.1-pro-preview` | {{FORMAL: settled cost}} | | ceiling 30 |
| Human review time | — | {{PENDING: hours per phase}} | | |
| **Recorded subtotal** (sum of the rows above that have a value) | | **72.643623** | | Excludes Judge Validation spend after its 2026-11-02 resumption and the Formal judge pass |

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
  one in-flight 20 USD sample), and the human approved that.
- The two-worker change raised the per-candidate ledger ceilings to 200 USD. The modeled worst case then became about
  361.80 USD, not measured. Realized spend was 17.979211 USD.
- The Formal judge has a 30 USD ceiling.

### 8.2 Known limitations

- **Sample size.** 10 tasks, k = 1, 20 samples, chosen purposively. There is no basis for confidence intervals on
  capability, and per-task results are single observations.
- **Protocol.** Item-by-item rubric scoring is not GDPval's pairwise expert preference, so the numbers are not
  comparable to published win rates.
- **Grader reliability.**
  - n = 36 blind item labels in all.
  - Dev judge agreement was 4/6 on the first pass. Held-out Validation deterministic agreement was 4/6, and both
    misses were grader defects that are now corrected but not re-validated on held-out data.
  - Judge Validation agreement has not been measured yet.
  - The judge and the development model share a provider family.
  - 100% rubric coverage does not mean 100% definitive or accurate grading.
- **Deadline exception.** The Formal judge pass started at `freeze-v1-grading` before the Judge Validation
  agreement was measured and before the independent recheck of V1.9 (`preregistration.md` 1.25). The Formal judge
  verdicts are **provisional** until both exist.
- **Open review.** The Codex recheck of V1.9 (D2 terminal stops, the formal stop result and task-order judging,
  explicit judge projects) has not been done (section 4.5).
- **Judge-project quotas.**
  - The Dev Google project allows 250 `gemini-3.1-pro` requests per day, measured from the provider's 429 detail. The
    second project's quota is unverified.
  - The Formal pass needs 332 items before retries, so it may span quota days and projects.
  - Daily-quota pauses, project switches and exhausted items are recorded. Missing verdicts are never FAILs, but they
    reduce coverage and leave criteria `not_confirmed`.
- **Pre-existing stale harness test.** The harness suite passes 218/219. The one failure,
  `test_launcher_regressions…placeholder_ceiling`, expects the Formal ceiling to be a placeholder. It has been 150
  since `be84ff6` and fails identically on `b33cc37`. It has not been corrected (`docs/status.md` "Codex delta
  review" and "Grading freeze").
- **Blinding.**
  - Model identity is hidden in judge inputs and packet text.
  - The Formal deliverable files themselves are not blinded: their embedded file metadata were not altered, since
    raw outputs are immutable. {{PENDING: record this in `docs/status.md`, and say whether any packet deliverable
    carries identifying metadata}}
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
- **No domain expert.** No step was reviewed by an industry domain expert (`README.md`).
- **Costs.** All figures are ledger settlements. The inferred portions still need reconciliation with provider
  billing.

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
  `--credential-env` for project selection. {{PENDING: document their exact `run` / `resume` / `status` command
  lines in `README.md`}}
- Results can be reproduced exactly only from the run artifacts under `~/turing-eval-runs/`, which are not in the
  repository. A fresh generation is a new sample, not a replication of these runs.
