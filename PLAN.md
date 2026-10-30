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
  Transport-level retries follow a documented policy and are logged.
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
  the formal run. Results describe the two models under this common scaffold.

## 4. Grading

Grading combines three layers. None of them is tuned to make a model pass; any change
to a grading rule after freeze is recorded with the old rule, the evidence it was wrong,
the new rule, and both models are re-graded.

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
validate it. Visual criteria are not judged from text.

**Human review.** Every deliverable is opened (rendered where needed). All critical
criteria and pre-defined visual requirements are checked by hand. Disagreements between
judge and deterministic checks are adjudicated and recorded. Non-critical criteria are
sampled, stratified by model and criterion type; the human judgment is written down
before the judge verdict is revealed. Agreement rates are reported per model with
numerators and denominators. Agreement measures consistency, not correctness.

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

## 7. Workflow and controls

Stages run in order: read-only check, material download and rule drafting, toolchain
validation without model calls, model and budget configuration, pilot (one task, model
A end-to-end through grading and human review, then model B), freeze, formal run with
human review, deliverables. Each stage ends with a report in `docs/status.md`.

Paid calls (candidate models, judge, connectivity tests) need explicit approval of the
scope, expected cost, ceiling, and stop conditions. The first paid batch is the pilot.
Concurrency starts at one or two and is raised only on evidence.

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
