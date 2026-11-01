# Methods

This repository holds a small diagnostic evaluation of two frontier models on ten
tasks from the public GDPval gold set. The evaluation asks one question: can a model
carry explicit business rules and requirements correctly and consistently into a real
work deliverable, and when it cannot, which errors can be identified reliably and
mapped to useful data improvements. The deliverables are a one-page site, this
reproducible repository, and a dataset proposal.

Status of each component is tracked in `docs/status.md`. Nothing in this document
should be read as a result until the corresponding run artifacts (`results.jsonl`,
`grades.jsonl`, Inspect logs) exist and are referenced from the site.

## 1. Research question and evidence chain

Two concrete requirements are examined in every task:

1. Rules and constraints stated in the task (or in its attachments) are applied in the
   deliverable.
2. Source material, line-level detail, summaries, and the final narrative stay
   consistent with each other.

The evidence chain the site follows: which tasks were selected, under which conditions
they were run, what was delivered, on what grounds an error is called an error, whether
the error sits in the task material, the grading rule, the environment, or the model,
which errors data can address, what such data looks like, and what the evidence can and
cannot support.

The ten tasks are a purposive diagnostic sample. They do not represent an occupation's
overall level, all knowledge work, or any GDP-weighted capability.

## 2. Data and task selection

**Dataset.** `openai/gdpval` on Hugging Face at the v2 revision
`11e7900cdcac61bc4daf59e65feb238acda98fbf` (2026-02-10, "Release GDPval v2 (rubrics +
deliverables)"). The local parquet (`data/gdpval.parquet`, sha256
`f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202`) was matched against
the LFS hash recorded for that commit; every task input and expert deliverable was
downloaded from the same revision and verified against the hash Hugging Face records for
it (`data/download_verification.json`, `data/manifest.json`).

The v2 release adds per-task rubrics (`rubric_json`, human-authored, weighted
criteria) and expert deliverables. The official GDPval metric is expert pairwise
preference; the hosted automated grader is not used here. Rubric criteria are scored
one by one against the frozen public rubric, which is a different protocol with a
different meaning, so the numbers reported here are not comparable to published GDPval
win rates.

**Selection rule.** Examine one occupation's complete block of real business tasks,
then add tasks from other occupations that supplement the two requirements above with a
different domain or a different deliverable shape. All ten were fixed before any model
run; none is swapped or dropped on the basis of results.

| Group | Task (full UUID in `data/selected_tasks.json`) | Occupation | What it adds |
|---|---|---|---|
| Deep block | `b5d2e6f1…` weekly sales analysis with PivotTable | Order Clerks | Aggregation of a 936-row sales export into brand and store-brand totals; PivotTable object required |
| Deep block | `f841ddcf…` June shipment recap from a PO log | Order Clerks | Date-window rules, account-level totals, narrative that must match the tables |
| Deep block | `47ef842d…` weeks-of-supply for five UPCs | Order Clerks | Store-level inventory data to summary metrics and a chart; an "out-of-stock" definition must be inferred |
| Deep block | `1137e2bb…` PO entry audit (pilot task) | Order Clerks | Two explicit validation rules (price mismatch, case-pack multiple), line flags to SKU summary to Word memo |
| Deep block | `c3525d4d…` holiday floor-stand budget | Order Clerks | Cross-referencing two store lists, cost change, overage rule, budget workbook plus email |
| Supplementary | `7b08cd4d…` tour profit-and-loss | Accountants and Auditors | Country-specific withholding rates, source separation, rounding |
| Supplementary | `7d7fc9a7…` prepaid amortization schedules | Accountants and Auditors | 66 invoice pages (PDF) to schedules that must reconcile to stated GL balances |
| Supplementary | `2ea2e5b5…` work-time study deck | Computer and Information Systems Managers | 15,918-row source to tables, pie charts, and a five-slide deck; prompt-defined classification |
| Supplementary | `c357f0e2…` UAT test plan | Computer and Information Systems Managers | Business and permission rules to executable test cases in a template |
| Supplementary | `a45bc83b…` GCP migration design | Computer and Information Systems Managers | Multi-input, multi-output design task; official icons and pages are pre-staged offline |

The selection rule, the candidates that were examined and not selected (with the factual
basis for each), and the substitute rule are recorded in `preregistration.md`, section
"Task selection and exclusions". A pre-declared substitute for the GCP task exists in
case its pre-staged resources or visual verification cannot be completed before freeze;
substitution is triggered only before freeze and never on results.

## 3. Execution conditions

Both models run under one shared agent scaffold built on Inspect AI:

- **Common prompt.** One frozen system prompt, identical for both models, stating the
  available tools and packages, the output location, the absence of network access,
  and a short generic work-quality self-check (verify requirements against the final
  files, open the final files, render visual deliverables and look at them, check key
  calculations and cross-file consistency, fix what is found). It contains no
  task-specific hints and no rubric information.
- **One attempt.** `attempts=1`. A run is one complete agent trajectory with as many
  tool calls as the model chooses; there is no scorer feedback and no resubmission.
  Transport-level retries follow a documented policy and are logged. Execution budgets
  (time, working time, message and token limits) are fixed in `config.json` and
  identical for both models; exhausting one ends the attempt, which is then graded on
  what was delivered (section 4, "Execution budgets").
- **Tools.** Bash and Python in a sandbox, plus a `view` tool that returns an image of a
  PDF page, attachment, or rendered deliverable so the model can inspect its own output.
  Provider server-side tools (web search, code interpreter) are off.
- **Sandbox.** One container per sample, built from the repository Dockerfile with
  LibreOffice and a documented subset of the packages listed in the GDPval paper
  (Appendix A.6.4), `network_mode: none`. Only that task's inputs and pre-staged
  resources enter the container through `Sample.files`; deliverables are written to
  `/output/final/` and collected by the harness, on normal completion and on timeout.
- **Isolation.** Expert deliverables, rubrics, the parquet, `preregistration.md`, grader
  code, other runs' outputs, and credentials are never mounted, copied into the image,
  readable through any tool, or quoted in any prompt. The boundary is verified before
  every run and the verification is described in the run record.
- **Pre-staged resources.** Only the GCP task lists external resources (official icon
  packs and ten official pages). They are fetched once, hashed, recorded with URL and
  fetch date in `data/manifest.json`, and provided identically to both models.
- **Provider settings.** Exact model ids, reasoning settings, execution limits, image
  digest, and code commit are recorded in `config.json` and frozen (`freeze-v1`) before
  the formal run. Results describe the two models under this common scaffold. The
  candidate generation configuration (explicit `reasoning_effort` high on both candidates,
  `max_tokens` 32,000, the time, working, message and token limits, timeouts, tools and
  `attempts=1`) is carried unchanged into `freeze-v1` and the formal runs; the only
  permitted change is an explicitly documented and approved compatibility change.
- **Run classes.** Every execution belongs to one run class with its own root, ledger,
  Inspect logs, run inventory and artifact manifests: `dev` and `validation` (one Gemini
  Flash sample each per formal task, generated independently: separate run uuid, unit,
  root, ledger, provenance, label and SHA-256 artifact manifest; never two epochs in one
  log), `compat` (one sample of each candidate on a GDPval task outside the formal ten,
  for provider, tool, artifact, rendering and accounting behaviour only; its outputs
  calibrate no grading rule and report no capability) and `formal` (the evaluation
  proper). Classes are never mixed in execution or accounting records.

## 4. Grading

Grading combines three layers. None of them is tuned to make a model pass; any change
to a grading rule after freeze is recorded with the old rule, the evidence it was wrong,
the new rule, and both models are re-graded.

**Architecture.** A shared grading engine (XLSX, DOCX and PPTX extraction and
recalculation, table recognition, row and column matching, numeric comparison and
evidence location, the `pass` / `fail` / `cannot_assess` semantics, model / grader /
environment attribution, scoring, coverage, critical status, judge and human-review
infrastructure) carries one engine version; each task has a thin specification (rubric
item mapping, expected values from the authoritative source materials, business rules
and applicability, task-specific evidence and calculation requirements) with its own
version; a cross-task capability analysis (requirements adherence, reference grounding,
business-rule execution, coverage, cross-file consistency, deliverable mechanics and
usability, the preregistered failure taxonomy) is produced after the formal run. Shared
code is extracted only where a second real task demonstrates the need. Every grading
pass records the engine version, the task version and the full git commit of the code.

**Gold-first grader development.** For each task the grader is first run against the
expert deliverables, the numeric expectations are reconciled independently with the
source materials, and findings are classified as expert-deliverable defects, rubric
ambiguities, source-data issues or grader defects. A catalog of seeded corruptions
derived from the expert deliverables declares, for every corruption, the affected items
and the expected verdict transitions (dependencies between items included), and layout
transformations are classified as neutral (the full verdict map must not change) or
rubric-relevant (the declared result must appear); the suite compares complete item
maps, never subsets. The original first-pass result on the expert deliverables is
preserved before any fix. Grader v0 of a task is committed and tagged before that task's
development sample is opened.

**Development and sealed validation samples.** One Gemini Flash sample per task
(`dev`) calibrates the grader after Grader v0 exists: the human labels the deliverable
from a verdict-free review packet (criteria, source evidence, deliverable references and
excerpts; no grader or judge verdict, no suggested answer) before any automated verdict
is revealed, the labels are saved with a hash and timestamp, and disagreements are
diagnosed as model failures, grader defects, rubric ambiguity or environment faults;
evidence-backed grader defects are repaired with versioned changes that preserve the
original grades. Human labels are requested in groups of at least three tasks. A second,
independently generated sample per task (`validation`) stays sealed - content,
trajectory and logs unopened - until the grader candidate is committed and tagged;
it is then labelled the same way before the frozen deterministic grader and the judge
run, and false passes, false fails, coverage loss and agreement are reported with
numerators and denominators. Post-fix scores on the same samples are regression
evidence, not new held-out validation; the development model's samples support
validation on unseen outputs of one model family only. Judge debug criteria are never
reused as held-out judge-validation criteria.

**Execution and collection gate.** Before any capability grading, the grading entry
point must load and validate the final `run_outcome.json` using
`harness.collect.load_run_outcome(..., for_grading=True)`. Its expected identity must
come from the completed Inspect log: execution UUID, actual model, Inspect task ID and
eval ID, sample ID (the GDPval task UUID), and epoch. Validate `run.json`, the final
collection record, history, and original artifact hashes as well. A launcher label is
not execution identity. Only Task cleanup publishes the authoritative outcome; the
collector's historical ScoreEvent is provisional and unscored (`Score.unscored()`, no
metrics), never an accuracy or capability score. Cleanup recovery can change a partial
collection into a complete one while retaining the first pass's failures.

Missing, corrupt, non-final or identity-mismatched outcomes fail closed. A persistent
`listing_failed` outcome is a harness collection error. A `partial` collection is routed
by the attribution of each non-collected item: model-caused items (symlinks, special
files, oversized or deleted files the model left) are treated as not delivered and the
run is graded; a harness-caused item (collector limit, deadline, host-side read fault)
makes the run a harness collection error, never model non-delivery; an item of unknown
cause requires a recorded human adjudication before any grading. An execution error (a provider
request that finally failed, a transport fault, a container or harness exception) or an
unknown execution state keeps `grading_eligible=false` and requires run review even when
files were collected; such runs stay in the run inventory as run errors under the
approved error and retry policy. Only confirmed empty collection after completed or
budget-limited execution establishes that no final files were produced; applying
criterion-level failures remains the grader's job.

**Execution budgets.** The sample limits configured in `config.json` (Inspect
`time_limit`, `working_limit`, `message_limit`, `token_limit`) are identical for both
models. Exhausting one is a result of the model under fixed resources, not a harness
error: the outcome records `execution.status=limited` with the limit type and the
Inspect event evidence, and the run is `grading_eligible` when its final collection is
`complete` or `no_files_confirmed` and no provider, harness or collection failure was
recorded. Collected deliverables are graded against the rubric; requirements whose
deliverable is missing fail as not delivered; the attempt stays in the k=1 results and
in every sample denominator. `grading_eligible` states only that the run may enter
grading, never that a task was completed or any criterion passed. A single tool call
that timed out while the sample continued is a tool error inside a completed execution,
not a run error. Attribution uses the recorded exception type and Inspect events, not
the presence of the word "timeout" in a log. Limit types outside this budget set
(operator, custom) require review.

The grading entry point (`grading/grade.py`) loads the final outcome with the identity
taken from the completed Inspect log, cross-checks that log (errors or limits recorded
after cleanup block grading), routes the run by the per-file attribution of any
non-complete collection (harness- or provider-caused faults are run errors; undetermined
items wait for a recorded human adjudication; only model-caused rejections let the run
proceed, with the rejected files treated as not delivered), grades eligible runs
including budget-limited ones, and writes `grades.jsonl` and `results.jsonl`. Its
integration tests run on synthetic run directories built from fixtures through the real
collector. Collection limits are cumulative per sample across the
scorer and cleanup passes (file count and total bytes over the merged set; an idempotent
re-collection is not counted twice) with a hard per-pass deadline enforced on in-flight
reads; limit hits are recorded per file and leave collected originals untouched. Before a
sample starts, every staged input and pre-staged resource is verified against the hashes
in `config.json` (source path real and inside the task's own directory, no symlink, no
traversal, no duplicate target); any mismatch stops the sample. Images returned by the
`view` tools are decoded and bounded on the host before they reach a provider.

**Deterministic checks.** File presence and type; required sheets, columns, sections;
formulas versus hard-coded values, with LibreOffice recalculation on a copy to separate
"wrong formula", "missing cached value", and "recalculation failed"; key figures
compared with values computed independently from the source files (`scripts/recalc/`),
never copied from the rubric; detail-to-summary and workbook-to-document consistency;
presence of PivotTable and chart objects; page and slide counts. Layout heuristics only
raise flags for human confirmation.

**LLM judge.** One fixed model and prompt judges both candidates. Each criterion is
judged pass / fail / cannot_assess with locatable evidence (file, page, sheet, cell).
Every call carries the task requirement, the criterion, the source material or
independent computation needed for that criterion, and the relevant deliverable
excerpt. Model identity is hidden. Items used to debug the judge are never reused to
validate it. Visual criteria are not judged from text. A deterministic stub stands in for
the judge only in tests and is refused by the grading entry point outside an explicit test
mode; the batch form of the judge call (all units of one task in one request) is accepted
only when every unit id comes back exactly once, otherwise the whole batch is recorded as a
parse error and its criteria stay ungraded.

**Judge calibration on development outputs.**
- Model and settings: `google/gemini-3.1-pro-preview`, pinned to thinking level high, temperature 1.0, at most 16,384
  output tokens including thinking, and Inspect `max_retries` 3.
- Recorded with every call: the prompt hash, the settings, the evidence-builder version and the usage.
- Failed responses: a truncated, malformed or evidence-free response is recorded as an assessment failure and the
  criterion stays ungraded. It is never a rubric fail.
- Coverage: on the development outputs, the judge runs on every judge-scored criterion.
- Stability: a fixed random subset of 20 judged criteria, drawn before any verdict was seen, is judged a second time
  with an identical request. The agreement between the two runs measures stability, not correctness.
- Prompt revisions: allowed only on development outputs, after comparison with saved human labels, with at most three
  passes in all.
- Freeze: the shared prompt and settings are frozen before any validation output is revealed.
- Budget: judge calibration costs have their own ledger and ceiling.

**Human review.**
- Approach: time-bounded and blind, from a frozen, seeded queue whose membership never depends on a verdict.
- Development outputs: three tasks, one per deliverable family (spreadsheet, presentation, document), calibrate the
  judge prompt and the graders. Each gets one critical criterion, two deterministic items and three judge-only items.
- Validation and formal outputs: one deterministic and one judge-only item per task (the same ids for both
  candidates, candidate identity hidden), plus a small stratified critical and visual subset fixed in advance.
- Packets: the human labels from verdict-free packets, and the labels are saved with a hash and timestamp before any
  automated verdict is shown.
- Agreement: reported per model with its actual numerators and denominators. Agreement measures consistency, not
  correctness. A small random sample bounds false-pass risk only loosely, and no precise false-pass rate is claimed.
- Visual criteria: those without a human verdict are reported as not evaluated. A judge verdict never stands in for
  them.
- Reported critical failures: every critical fail used in the candidate comparison, the headline findings or the
  failure taxonomy is verified by a human against the deliverable, the source data and the rubric. Until then it is
  reported as an unverified finding, and any reclassification (grader, dataset, rubric, environment) is recorded.
- Failure analysis: about 20-30 failure events, chosen by impact, severity, uncertainty and capability family, are
  investigated in depth, separately from the agreement statistics.
- Disagreements: those between the judge and the deterministic checks are adjudicated and recorded.

**Scores.** For each task and model: W is the total rubric weight, E the weight of
criteria judged pass or fail, P the weight confirmed pass. Reported figures are the
graded score P/E, the coverage E/W, and the list of ungraded criteria with reasons.
Criteria that the environment cannot support (for example a PivotTable object if the
toolchain cannot produce one) stay in W and are reported as ungraded. Models with
different coverage are not ranked by P/E alone.

**Critical status.** Each task carries two to four critical criteria, pre-registered
with the business requirement, evidence location, check method, and why a failure is
not compensated by other points. Status is pass / fail / not confirmed. A deliverable
that was not produced fails the applicable criteria; a launch or collection failure is
recorded as a run error, not as model non-delivery. Critical status is reported
separately from P/E and is not a "GDPval score".

## 5. Failure analysis

All failures, incomplete runs, cannot_assess items, and critical disagreements enter
review; passes are sampled for false passes. For each failure the record states the
observable error, the cause judgment (evidenced / probable / undetermined), the
evidence used (input rule, output, trajectory, cross-check), and the business impact in
one sentence. The order of investigation is: task material consistency, grading rule,
environment, model. That is an order of investigation, not a proof of root cause.

Trajectory evidence is recorded at three levels (file access observed, content returned
to the model's context, content used correctly in the deliverable) and is used for
attribution only, never for scoring. Absence of a filename in the log is reported as
"no confirmed read observed", not as "did not read".

Observable error classes: deliverable-spec compliance, attachment content use, rule
execution, cross-file consistency, coverage, mechanics (hard-coded values, broken
formulas, missing pivot or chart), presentation. Environment faults, defective rubric
items, and extraction errors are reported in their own categories.

## 6. Reporting

Per task and model: deliverables present, critical status, P/E, E/W, ungraded items
with reasons, wall time, and cost. Generation cost, grading cost, and human review time
are reported separately. Every reported metric traces to versioned `results.jsonl` and
`grades.jsonl` and the applicable `config.json`; counts such as rubric totals are
computed from the data.

Known limits are reported with the results: ten tasks, one run per task per model,
agreement reported per model with numerators and denominators, debug and validation
sets kept separate, ungraded items, cost, grader status, pre-staged resources, the
protocol difference from the GDPval paper, unknown authorship independence across
tasks, and the rule that models with different coverage are not compared by P/E alone.
Two further limits:
- The judge and the development model come from the same provider family (Gemini Pro judging Gemini Flash
  outputs). Agreement measured on development and validation samples may be inflated by shared style or shared blind
  spots, and does not transfer directly to the candidate models.
- 100% rubric coverage does not mean 100% definitive grading or 100% grading accuracy. Evaluated-item coverage,
  definitive-verdict coverage and human agreement are reported separately.
For the pilot task (`1137e2bb…`) every judge-only criterion was used to debug the judge
assembly, so no held-out criterion exists on that task: judge agreement is reported from
the other tasks, and the pilot task's judge verdicts are checked by human review only.

## 7. Workflow and controls

Stages run in order: read-only check, material download and rule drafting, toolchain
validation without model calls, model and budget configuration, gold-first grader
development with development and sealed validation samples (section 4), candidate
compatibility runs, judge preparation, freeze, formal run with human review,
deliverables. Each stage ends with a report in `docs/status.md`. Two independent
engineering reviews gate the work: one of the shared spreadsheet grading core after the
second task, before it is scaled to the remaining tasks, and one of measurement
readiness (coverage, independent validation, judge reliability, candidate fairness,
provenance, unresolved blockers) before the freeze request.

Paid calls (candidate models, judge, connectivity tests) need explicit approval of the
scope, expected cost, ceiling, and stop conditions; one authorization covers one defined
batch (model ids, task and sample counts, forecast cost, internal controls, destinations,
stop conditions and retry policy). A batch stops when its ledger reaches a stop
condition; ceilings are never raised, holds never cleared and paid samples never
retried without explicit authorization. Concurrency starts at one and is raised only on
evidence.

## 8. Reproducibility

- Dataset revision, file hashes, and resource hashes: `data/manifest.json`,
  `data/dataset_revision.json`, `data/download_verification.json`.
- Task selection: `data/selected_tasks.json` (resolved by `scripts/resolve_tasks.py`).
- Downloads: `scripts/fetch_dataset.py` (parquet at the recorded revision),
  `scripts/download_materials.py`, `scripts/fetch_gcp_resources.py`,
  `scripts/build_manifest.py`; the clean-clone sequence is in the README.
- Independent recalculations: `scripts/recalc/`.
- Environment: `pyproject.toml` and `uv.lock` (Python 3.11).
- Run and grading configuration: `config.json` (frozen at `freeze-v1`).
- Per-task critical criteria, checks, judge inputs, known data defects, adjudications:
  `preregistration.md`.
- Gold-first validation records per task (original first pass, post-fix result,
  corruption catalog with declared transitions, observed transitions):
  `grading/validation/<task_id>/`; grader versions: `grading.grade.ENGINE_VERSION`
  and each task module's `VERSION`, stated in `config.json` `grading`.
- Compatibility task (outside the formal ten): `data/compat_tasks.json`,
  `data/compat_manifest.json`, `config.json` `compat_tasks`.
