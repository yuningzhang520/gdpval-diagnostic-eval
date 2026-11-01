# Pre-registration (DRAFT, not frozen)

Status: draft under human review. Items marked **APPROVED** were approved by the human on
2026-10-29 and 2026-10-30 after an independent re-check of the stage-1 materials and recalculations; items
marked **PENDING** await the human's decision; items marked **TOOLCHAIN** depend on results of
the toolchain-validation stage. Nothing is frozen until `freeze-v1` is tagged; after freeze,
changes follow the amendment policy in section 1.12.

Rubric items are referenced by their 1-based position in the task's `rubric_json`
(`private/rubric/<task_id>.json`); grading code maps positions to `rubric_item_id`.
Figures marked "recomputed" come from `scripts/recalc/` run on the task inputs only
(outputs in `private/checks/recalc/`); none of them is copied from a rubric or from an
expert deliverable. Expert deliverables ("gold") are references to be checked, never the
single correct answer.

Dataset revision for every task: `openai/gdpval` @ `11e7900cdcac61bc4daf59e65feb238acda98fbf`.

---

## 1. Global rules (apply to all tasks)

### 1.1 Rubric first; adjudications recorded, never substituted (APPROVED)
- Every rubric item is graded individually, as written. Critical criteria name the errors
  that matter most for the business outcome; they do not replace, re-weight, or shortcut
  the rubric.
- Public wording for every outward-facing text: "graded against the public GDPval v2
  rubrics, with documented pre-run adjudications for identified inconsistencies".
- Adjudication record. For every rubric item that conflicts with the task materials, the
  independent computation, or the prompt, five fields are recorded: (1) the original
  rubric text verbatim; (2) the independent result from the source data; (3) the
  adjudication; (4) the rationale; (5) the effect on scoring. Items without a conflict
  receive no adjudication. Records are labelled `A-<item>` in section 3.
- Three classes of problem are kept apart and handled differently:
  - (a) Expert-deliverable defect: the standard is not lowered. The item is graded against
    the task requirement and the reliable independent computation; the gold is not a value
    reference for that item.
  - (b) Rubric defect: the rubric text is preserved; the record states the correction, or
    `cannot_assess` where the item genuinely cannot be decided.
  - (c) Under-specified task: an evidence-based operational rule is fixed before any model
    output is seen, labelled as this evaluation's definition, and the ambiguity is disclosed.
  No conflict is labelled "gold error" by default and none defaults to `cannot_assess`.
- `cannot_assess` is reserved for specific items that the materials genuinely cannot
  decide. It is never used to excuse a confirmed missing or incomplete deliverable.

### 1.2 Scoring
- W = sum of weights of all rubric items for the task; E = weight of items judged
  `pass` or `fail`; P = weight confirmed `pass`. Reported: graded score P/E, coverage E/W,
  and the list of ungraded items with reasons. If E = 0 the score is "not computable".
- Ungraded items stay in W. Reasons allowed: `environment_unsupported` (needs evidence
  that the missing capability was necessary and nothing else could substitute),
  `cannot_assess` (section 1.1), `extraction_failed` (recorded as a pipeline issue,
  repaired before formal grading).
- A required deliverable that was not produced, as established from the collected
  `/output/final/` contents, fails every criterion that depends on it. A launch,
  infrastructure, or collection failure is a run error and is kept in the run inventory.
- Critical status per task and model: `pass` (all critical criteria confirmed pass),
  `fail` (any critical criterion confirmed fail), `not_confirmed` (no confirmed fail but
  at least one critical criterion ungraded). Reported separately from P/E.
- Models with different coverage are not ranked by P/E alone.

### 1.3 One attempt
`attempts=1`. One complete agent trajectory per task and model, any number of tool
calls and self-checks, no scorer feedback, no resubmission. Transport retries follow the
approved policy and are logged.

Execution budgets (Inspect `time_limit`, `working_limit`, `message_limit`,
`token_limit`; values set in `config.json`, identical for both models): exhausting one
ends the attempt and is recorded as `execution.status=limited` with the limit type and
the Inspect event evidence. Such an attempt is graded when its final collection is
`complete` or `no_files_confirmed` and no provider, harness or collection failure was
recorded: collected deliverables are graded against the rubric, requirements whose
deliverable is missing fail as not delivered, and the attempt stays in the k=1 results
and in every sample denominator. Grading eligibility is not task completion. A provider
request that finally failed, a transport fault, a container or harness exception, or an
unrecovered collection fault is a run error (section 1.2), kept in the run inventory
with `grading_eligible=false`. A single tool call that timed out while the trajectory
continued is not a run error. Attribution uses the recorded exception type and the
Inspect events, never the word "timeout" alone.

### 1.4 Blinding
Judge inputs and human-review materials hide model identity wherever feasible
(candidate labels A/B assigned per task, file metadata stripped from excerpts).

### 1.5 Judge inputs and validation
Each judged criterion receives: the task requirement (prompt excerpt), the criterion,
the source material or independent computation the criterion needs, and the deliverable
excerpt (extracted text with formulas and recalculated values). Evidence must be
locatable (file, sheet, cell / page / slide / paragraph). Visual criteria are not judged
from text. Items used to debug the judge are never reused to validate it; human
judgments for agreement are recorded before the judge verdict is shown.

### 1.6 Deterministic check validation
Every deterministic check is validated gold-first before any model output of its task is
opened: the expert deliverables are graded (the original first-pass result is preserved
unchanged), numeric expectations are reconciled independently with the source materials,
findings are classified (expert-deliverable defect, rubric ambiguity, source-data issue,
grader defect), and a catalog of seeded corruptions and layout transformations derived
from the expert deliverables declares the expected verdict transitions item by item
(neutral transformations must leave the complete verdict map unchanged; rubric-relevant
ones must produce exactly their declared map). Records: `grading/validation/<task_id>/`;
suite: `grading/tests/test_gold_<task>.py`. Implemented for `1137e2bb…` on 2026-11-01
(section 2.4).

### 1.7 Numeric conventions (APPROVED)
- Currency amounts are handled as `Decimal` with intermediate precision preserved; where
  a computation divides (amortization terms), exact rationals are used and quantized on
  the rational. Quantization happens only at the point of comparison with a GL balance, a rubric figure,
  or a deliverable value, and the quantum, rounding mode, and compared quantity are defined
  per item in section 3. There is no global rounding mode (ROUND_HALF_UP is not applied to
  every number by default) and no global tolerance; the former blanket +/- 0.50 USD
  tolerance is withdrawn.
- Where a rubric item states a tolerance, that tolerance applies to that item.
- Counts and 1/0 flags are compared exactly. Percentages follow the rule stated in the
  task's section.
- Identities (for example net income = net revenue − expenses) are checked on unrounded
  values; rubric figures that are individually rounded need not add up, and that is not an
  error.

### 1.8 Alternative interpretations in a model's output (APPROVED)
Where this file fixes an operational definition (section 1.1, class c), a model output
that uses a different interpretation is recorded as such and checked against the original
task requirement. An alternative is accepted only if the original task materials
explicitly support it; a different number is not evidence for a different rule. Only when
the materials genuinely cannot decide which interpretation applies are the specific
affected items marked `cannot_assess`; the remaining items are graded as written.

### 1.9 Extraction rules (grader side, on copies)
- xlsx: formulas and cached values via openpyxl; LibreOffice recalculation on a copy;
  pivot and chart objects via the package XML (including data-field aggregation
  attributes); drawing text boxes read from `xl/drawings/*.xml` (the PO-log gold narrative
  lives in a text box).
- docx: paragraphs, tables, text boxes. pptx: shapes, tables, chart XML; both 2D
  (`pieChart`) and 3D (`pie3DChart`) chart parts are read (python-pptx alone cannot parse
  the latter; the work-study gold uses it).
- pdf: text layer plus page renders for human review.

### 1.10 Trajectory record (attribution only, never scored)
Three levels: file access observed; relevant content returned to the model's context;
content used correctly in the deliverable. Absence of evidence is reported as "no
confirmed read observed".

### 1.11 Failure record fields
Primary observable error; other errors; cause judgment (evidenced / probable /
undetermined); evidence used; business impact and rework need in one sentence; severity
by business impact; "original verdict overturned on review" as a separate status.

### 1.12 Change policy and run labels
Any change to inputs, prompt, tools, or execution budget: assess impact, rerun affected
tasks for both models if needed. Grader bug with deliverables intact: re-grade both,
no rerun. Amendments record old rule, evidence, new rule, and re-grading of both models.
Runs are labelled by run class: `dev`, `validation`, `compat` or `formal` (2026-11-01;
the earlier `pilot` label is retired, the candidate pilot was not run); a rerun after an
approved change keeps its class and is recorded as an intervention in `docs/status.md`.
Classes keep separate roots, ledgers, logs, inventories and artifact manifests.


### 1.13 Pre-declared substitutes and fallbacks (APPROVED 2026-10-30, as written)
- GCP task `a45bc83b…`: if pre-staged resources or visual verification cannot be
  completed before freeze, substitute `bf68f2ad…` (First-Line Supervisors of Production
  and Operating Workers) or `b7a5912e…` (Counter and Rental Clerks). Triggered only
  before freeze, never on results.
- Single-model fallback: if budget, access, or human-review capacity triggers before
  freeze, run one model on all ten tasks; the model is chosen by access reliability and
  cost, not by performance.

### 1.16 Grader development and sealed validation protocol (2026-11-01)
Development samples: one `google/gemini-3.8-flash` sample per selected task (`dev`),
generated under the candidate generation configuration. Before a task's development
output (deliverables, `.eval` messages, trajectory, tool output) is opened, that task's
Grader v0 must be verified against the expert deliverables and the corruption catalog
(1.6), its regressions run, and the complete code state committed and tagged with the
version and hashes recorded; only programmatic collection, hashing and the predefined
run-level metadata (execution status, limits, usage, cost) may be read earlier. The
first-pass Grader v0 result is preserved before any evidence-backed fix. Human labels
come from verdict-free review packets (criteria, source evidence, deliverable references
and excerpts; no grader or judge verdict, suggested answer or diagnosis) and are saved
with a SHA-256 and timestamp before any automated verdict is revealed; labels are
requested in groups of at least three tasks. Validation samples: a second, independently
generated sample per task (`validation`: own run uuid, unit, root, ledger, provenance,
label and artifact manifest) sealed until the grader candidate is committed and tagged;
then labelled the same way, graded by the frozen deterministic grader and the separately
authorized judge, with false PASS, false FAIL, coverage loss and human-grader and
human-judge agreement reported with numerators and denominators. Fixes after validation
are versioned and symmetric; post-fix scores on the same samples are regression
evidence, not independent validation. Development outputs are examples, never
validation evidence; the development model's samples do not establish cross-family
generalisation. Compatibility runs (`compat`, task `87da214f…`, outside the formal
ten) verify provider, tool, artifact, rendering and accounting behaviour only.

Amendment (approved by the human 2026-11-01, before any canonical development or validation
sample of the development model exists): the Gemini `dev` and `validation` classes run
without an Inspect message limit (`config.batches.<label>.message_limit` null); the time
and working-time limits (7,200 s), the token limit (20 M), the per-sample cost limit
(10 USD), the reservation and every ledger stop condition are unchanged; the candidate
classes keep `generation.message_limit` 200. Reason: the earlier 200-message attempt of
`b5d2e6f1…` (run `LJbb8ZyPWZgPE8VCFRbLGD`) ended on the message limit after 99 single-call
turns with no tool error; it is kept as a diagnostic run outside the canonical ten. A
canonical Gemini unit is accepted when its execution is `completed`, or `limited` by the
time, working-time, cost or token limit only, with a grading-eligible outcome, complete
(or confirmed empty) collection, structurally valid collected files, a consistent
artifact manifest, a clean settlement and no suspected tool-error loop; the actual status
and limit reason are kept. Two distinct canonical Gemini units across `dev` and
`validation` limited by time or cost stop further Gemini launches (token limits are
recorded, not counted). Designations (canonical, diagnostic) are append-only records
next to each class's run inventory.

### 1.17 Rubric-to-capability mapping (DRAFT, 2026-11-01; approved at `freeze-v1`)
Every rubric item of the ten tasks carries one primary capability for the cross-task analysis:
requirements (deliverable-spec compliance), grounding (figures and items taken from the attached
sources), rule_execution (computed figures, flags, classifications by the task's rules), coverage
(every required element present, no omissions or extras), consistency (one part of the deliverable
agrees with another, incl. document versus workbook), mechanics (formulas and links, pivot and chart
objects, error-free and sortable cells), presentation (formatting, readability, style). The map is
built deterministically by `scripts/capability_map.py` from the rubric text with an ordered rule list
(the first matching rule decides; the rule is recorded per item) into `grading/capability_map.json`;
item-level overrides are recorded in the script with their reason. Status: rule-based draft; a full
item-by-item review (assistant pass, then human approval) is required before freeze, and the mapping
is fixed before any formal result is seen. Capability results are reported per task and capability
with numerators and denominators; items are never pooled into a single headline percentage.

### 1.14 Review entry and result boundaries
All failures, incomplete runs, `cannot_assess` items, and critical disagreements enter
review; passes are sampled for false passes. Investigation order: task material,
grading rule, environment, model. If no critical failure is observed, that is reported
as such; tasks are not swapped to manufacture failures.

### 1.15 Budget, concurrency, timeouts
Values are in `config.json` (high-reasoning configuration approved 2026-11-01 as the initial
Pilot A/B condition; fixed at `freeze-v1` after the pilot cost report): `reasoning_effort` high on
both candidates (explicit; the same nominal level, not equal compute; reported per model), tool
timeout 600 s, sample `time_limit` and `working_limit` 7,200 s, `message_limit` 200, `token_limit`
20,000,000 (type `all`), `max_tokens` 32,000 per request, 3 GiB per sandbox, collector
limits from `harness/collect.py`, `attempts=1`; pilot concurrency 1 on every axis, formal
concurrency 2 as a candidate pending memory and stability evidence; three fixed retry
layers (Inspect `max_retries=3` with exponential backoff for transport-class errors only,
request timeout 2,700 s and attempt timeout 900 s, provider SDK retries 0, whole-sample reruns
off); per-sample Inspect `cost_limit` 20 USD as a safety net; pilot ceiling 45 USD; reservations
A 8 USD, B 5 USD (forecasts). Final values are fixed at
`freeze-v1` after the pilot cost report. Budget exhaustion is graded under section 1.3.

---

## 2. Task selection and exclusions

Selection rule (fixed before any model run). One occupation-complete block, all five
tasks of one occupation, plus five supplementary tasks from other occupations. Every task
has to serve the two requirements of the research question: (1) rule execution, where
business rules stated in the prompt or the source materials are applied to produce a
computed, classified, or structured deliverable that can be traced back to the inputs;
(2) cross-deliverable consistency, where detail, summary, and narrative (or several
files) agree with each other. The deep block (Order Clerks, five tasks) gives one real
business context in full; each supplementary task adds a different domain or deliverable
shape to the same two requirements (`PLAN.md`, section 2, lists what each one adds). The
ten task ids are in `data/selected_tasks.json`; none is swapped or dropped on the basis of
results.

Candidates examined and not selected (full UUID; factual basis):
- `cebf301e-5ea7-41ae-b117-ad8f43e7ac22` (Computer and Information Systems Managers,
  customer-portal design document): no reference files, so requirement (1) cannot be
  checked against source material.
- `c2e8f271-7858-412f-b460-472463ad81d9` (Computer and Information Systems Managers,
  coding-standards document): no reference files; same basis.
- `83d10b06-26d1-4636-a32c-23f92c57f30b` (Accountants and Auditors, audit sample
  selection): the prompt places the variance in column J and the sample flag in column K
  (Q2 and Q3 in H and I); rubric items 9–12 place the variance in column I, items 13–14
  the flag in column J, item 15 sums the flags in column K, and items 16–17 refer to the
  variance as |J|. The rubric is inconsistent with itself and with the prompt; kept as a
  data-quality example, not run.
- `43dc9778-450b-4b46-b77e-b6d82b202035` (Accountants and Auditors, individual tax
  return): 15 PDF inputs and completed IRS forms as the deliverable; verification needs
  tax-law judgments that cannot be derived from the inputs by the rubric-based protocol.
- `ee09d943-5a11-430a-b7a2-971b4e9b01b5` (Accountants and Auditors, month-end
  financials): the prompt names `AP_TB-1.xlsx` among its inputs, but the 17 reference
  files (16 .xlsx, 1 .txt) do not include it.
- Financial and Investment Analysts, all five tasks: `8079e27d-b6f3-4f75-a9b5-db27903c798d`,
  `e21cd746-404d-4602-b9d2-01d2812c5b87` and `9e8607e7-a38a-491f-ace1-e5ea7dc477cb` have
  no reference files and ask for public market or company data as of a stated date (the
  first explicitly "on the open web"); `c7d83f01-2874-4876-b7fd-52582ec99e1a` has no
  reference files and its deliverable is a Python notebook; `46b34f78-6c06-4416-87e2-77b6d8b20ce9`
  supplies one research memo and asks for a ten-page trading-strategy memo, a judgment
  deliverable with little computation traceable to the memo. None offers a deliverable
  determined by provided inputs in an offline sandbox.

Other occupations were not assessed task by task; no claim is made about their
suitability.

Substitutes and fallback: section 1.13 (pre-declared, human-triggered, before freeze
only). The substitute candidates `bf68f2ad-eac5-490a-adec-d847eb45bd6f` (First-Line
Supervisors of Production and Operating Workers, capacity catch-up plan, .xlsx in and
out) and `b7a5912e-0e63-41f5-8c22-9cdb8f46ab01` (Counter and Rental Clerks, daily closed
operational report) each have one reference file and one expert deliverable and need no
network access.

---

## 3. Per-task sections

Notation: C = critical criterion, D = deterministic check, J = judge item group,
V = visual check (human, on rendered output), K = known defect or finding,
A-<n> = adjudication record for rubric item n (five fields, section 1.1),
DECISION = needs the human's call. Each C carries its status (APPROVED / PENDING /
TOOLCHAIN).

### 2.1 `b5d2e6f1-62a2-433a-bcdd-95b260cdd860` — Weekly sales analysis (Order Clerks)
Inputs: `Weekly Sales Data.xlsx` (sheet "Store Sales Report", 936 rows, 18 columns).
Deliverable: one .xlsx with tabs "Data", "Sales by Brand", "Sales by Store"; PivotTable
on "Sales by Store" sourced from "Data"; grand totals; ST% = Sales / Stock On Hand.
Rubric: 32 items, weight 65.

Recomputed (from source): 39 stores, 8 brands, 312 store-brand pairs. Grand totals:
WTD qty 55,380; WTD $ 3,036,844.59; WTD SOH 220,584; MTD qty 332,943; MTD $
25,169,419.47; YTD qty 1,270,386; YTD $ 106,940,338.83; YTD SOH 1,754,025. Per-brand
totals and ST% (ratio of sums) in `private/checks/recalc/b5d2e6f1-….json`.

Numeric rule for this task: sums of quantities and stock are integers and compared
exactly; $ sums are compared at cents (|difference| < 0.005); ST% is compared as an
unrounded ratio with |difference| < 0.0005 (0.05 percentage points) unless the rubric
item states otherwise.

- C1 Structure (APPROVED). Requirement: the three tabs with the required column sets
  (rubric 2, 3, 4, 11, 13). Evidence: sheet names, header rows. Check: D identifies the
  tables and columns by content and position; a literal label difference (for example
  "WTD Sales Qty" for "WTD Sales Quantity") is graded on the rubric items that ask for
  exact headers but is not escalated to critical. Not compensable: the buying team
  cannot use a workbook without the agreed tabs and columns.
- C2 Brand totals (APPROVED). Requirement: for every brand and the grand total, the nine
  numeric columns equal sums over the attached source data (rubric 5, 6, 10, 24).
  Reference: recomputation from the SOURCE file (the prompt says "using the attached
  weekly sales data sheet"), not from the deliverable's own "Data" tab. Rubric 6, 16, 17
  (internal consistency with the deliverable's Data tab) are graded as written in
  addition. Not compensable: wrong totals defeat the purpose of the analysis.
- C3 PivotTable (APPROVED 2026-10-30). Requirement: "Sales by Store" is a PivotTable
  object sourced from "Data", store as outer group, brand inner, store subtotals, grand
  total (rubric 12, 14–17, 25, 26). Check: D on the package structure — a
  `xl/pivotTables/pivotTable*.xml` part and its `xl/pivotCache/` definition and records
  exist, the cache's worksheet source references the Data sheet's data range, and the
  row, column and data fields match the task's grouping and measures (store outer, brand
  inner, SUM of the required measures) — plus value checks against recomputed pair sums.
  The toolchain stage showed that such an object can be created inside the sandbox
  (LibreOffice UNO), so the requirement stands and no `environment_unsupported` ruling
  applies. Whether Excel can open or refresh a given pivot is recorded as a limitation of
  this evaluation's toolchain (no Excel available), not used as a basis for pass or fail.
  Not compensable: the prompt explicitly requires a pivot table.
- C4 ST% logic (APPROVED). Requirement: ST% = Sales Quantity / Stock On Hand computed as a
  ratio of sums on both tabs for all three horizons, no division errors (rubric 7–9,
  18–20, 21). Check: D. Not compensable: the only derived metric in the task. The gold's
  percentages are not used for calibration (K3).
- D: items 1–10, 12–26, 30, 31 (names, headers, sums, pivot object, SUM aggregation,
  numeric storage, merged cells). J: 21 (aggregation type if not readable from XML),
  27–29 (formats, confirmable deterministically from number formats). V: 32 (overall
  formatting) after rendering.
- K1 (class c): prompt wording "modify this spreadsheet to insert a pivot table and
  rename it the 'Data' tab" is ambiguous; the rubric resolves it (Data = source data tab,
  pivot on Sales by Store). Graded per rubric.
- K2 (class a): the gold "Data" tab differs from the source in 557 cells. Category
  changes: 234 cells (Lancome 117, Shiseido 117) relabelled; no numeric effect. Value
  changes: 89 "Week to Date Stock on Hand" cells (all Estee Lauder) and 234 "Month to
  Date Stock on Hand" cells (Shiseido 117, Lancome 78, Laura Mercier 39). In every
  changed value cell the source stock is below the period's sales quantity (sell-through
  above 100 %) and the gold value is above it; the source holds 117 (WTD), 390 (MTD) and
  312 (YTD) such rows, so the edit is partial and undocumented. Effect on brand totals:
  WTD SOH Estee Lauder +9,816; MTD SOH Lancome +11,154, Laura Mercier +8,424, Shiseido
  +30,654. The gold is not a value reference: under C2 its totals for those four brands differ
  from the source-based reference. Items 6 and 10 are internal-consistency checks
  (deliverable against its own Data tab) and are not affected by the source difference.
  Reported in the data-quality section.
- K3 (class a): the gold's pivot data fields aggregate the three ST% fields with
  `subtotal="average"` (mean of row-level ST%), and the gold "Sales by Brand" ST% equals
  that mean (for example Clinique WTD 0.24668 versus ratio of sums 0.23087). The rubric
  (items 7–9, 18–21) requires the ratio of sums and SUM aggregation; the gold would fail
  those items. Recorded as a gold defect; the rubric governs.
- Deterministic rules of grader v0 (2026-11-01; operational detail, for human review at the labeling checkpoint):
  sheets by name (case-insensitive, whitespace-normalised) with a keyword fallback for the content items (the name
  items 2, 3, 11 need the exact name); columns identified by content (horizon WTD / Week to Date, MTD, YTD; measure
  sales quantity, sales $, stock on hand, ST%) and the literal-label items 4, 13 and 22 graded as written; summary rows
  classified from the Data tab's brands and stores (compact pivot layout or tabular store and brand columns; store
  subtotal rows carry the store label or "<store> Total"); a bare "Total" row is the grand total for the value items
  while item 31 tests the literal "Grand Total"; item 17 passes when the Grand Total equals either the sum of the store
  rows or the sum of the store subtotals (the rubric's "or"); ST% within 0.0005 of the row's quantity / stock, or within
  0.05 as a percent number when the cell is not percent-formatted, ST% excluded from the summed columns; item 21 from
  the pivot data fields' aggregation, else from the formulas (AVERAGE, COUNT, MAX, MIN, MEDIAN fail), values only
  `cannot_assess`; item 29 needs a currency symbol and two decimals in the number format; item 30 looks for merged
  ranges starting in the header rows. C1 adds a content-identified column-set check and C2 the comparison of every
  brand and the grand total with the source recomputation (non-rubric checks in the critical status only).
  Expert workbook: 4, 7-9, 13, 18-22 and 29 fail; the C2 source comparison fails (K2); C1 and C3 pass, C2 and C4 fail.
- A-1 (OPEN, provisional rule in grader v0; section 4): the expert "Sales by Store" pivot shows two figure-less rows
  labelled "(blank)" (empty groups from the whole-column source range B1:V1048576). Read literally ("no extra ...
  pairs") they are extra rows and item 14 fails, which also fails C3 for the expert. Grader v0 records a figure-less
  "(blank)" row as an empty pivot group, not a (store, brand) pair; a "(blank)" row with figures still counts as an
  extra row. The first pass under the literal reading is kept (item 14 fail).

### 2.2 `f841ddcf-2a28-4f6d-bac3-61b607219d3e` — June shipment recap (Order Clerks)
Inputs: `PO Log.xlsx` (66 POs, all status "Shipped", no blank actual ship dates,
7 accounts). Deliverable: one .xlsx with a June-shipped summary (filterable by
account, % shipped, $ short-shipped), a second table for June-window POs that shipped
in July, and a narrative. Rubric: 59 items, weight 88.

Recomputed: June (actual ship 6/1–6/30): 48 POs, order value at cost 145,218.80,
shipped value 140,008.204, 96.41 % shipped, short 5,210.596. Per account:
Marchand 27,081 / 26,883.288; Five O Fore 25,766 / 24,993.02; Thread Up 24,563.40 /
22,300.354; Sigma 22,687.60 / 21,154.294; Pronto 18,903 / 18,794.44; Hunt's 15,451.40 /
15,439.40; Dolce 10,766.40 / 10,443.408. Slipped (start >= 6/1, cancel <= 6/30, actual
ship in July): 5 POs (8452724, 8794337, 7147904, 7348247, 7969527), PO value at cost
13,300, actual shipped value 13,248. A looser reading (ship start in June, cancel
unconstrained) gives 16 POs / 43,634.40; the rubric (item 24) uses the strict rule.

Numeric rules for this task (rules APPROVED; the per-item entries below were declared on
2026-10-30 and reviewed the same day against the rubric text — see the basis column;
entries marked APPROVED follow from the rubric wording, none is based on the expert
deliverable's own formatting):
- Table amounts are compared at cents: the reference is the exact figure from the log
  quantized HALF_UP to cents, and the deliverable's stored cell value is quantized the
  same way; the two must be equal. A truncated value that differs from the HALF_UP
  result fails.
- Narrative items that allow whole dollars are listed individually below. A whole-dollar
  figure must equal the exact reference rounded HALF_UP to whole dollars; a truncated
  figure that differs from that result fails. When the displayed value alone cannot
  distinguish two rounding algorithms (140,008 arises under HALF_UP and under
  truncation), no inference is made about which one the model used.
- The +/- 1 USD tolerance of rubric 55 applies to item 55 only.
- Numeric correctness and display format are graded separately. The numeric check uses
  the cell's stored value, not its displayed text, so a reduced display precision does
  not hide an underlying error. A figure given only in whole dollars passes a
  whole-dollar item; nothing is inferred about cents that are not shown.
- Percentages: the rubric's range where it states one (48–54, 56); for item 27 the
  stored value is compared with the exact row ratio with |difference| <= 0.0005.

Per-item precision list (rubric item · output location · correct amount, exact →
reference · allowed precision · rounding rule · rubric-text basis and status):

| Item | Location | Correct amount (exact → reference) | Precision | Rounding | Rubric-text basis · status |
|---|---|---|---|---|---|
| 27 | June table, each row, % shipped | row shipped / row ordered | ratio, ±0.0005 | none (exact ratio) | "Percent of Order Shipped equals (PO Actual Shipped Value at Cost) divided by (PO Value at Cost)": an equality with no stated precision; the tolerance is the approved general rule for ratios · APPROVED |
| 28 | June table, each row, short-shipped $ | max(ordered − shipped, 0) per row (log values carry up to 3 decimals) | cents | HALF_UP | "Short-Shipped Dollars equals max((PO Value at Cost) − (PO Actual Shipped Value at Cost), 0)": an equality of dollar amounts; the general rule compares table amounts at cents · APPROVED |
| 35 | June table, labelled total | 140,008.204 → 140,008.20 | cents | HALF_UP; must also equal the sum of the table's own column | "a clearly labeled total for June shipped that equals the sum of the PO Actual Shipped Value at Cost column": table amount, cents under the general rule · APPROVED |
| 36 | Slipped table, labelled total | 13,300 → 13,300.00 | cents | HALF_UP | "a clearly labeled total ... that equals the sum of the PO Value at Cost column": table amount · APPROVED |
| 37 | Narrative, both totals | 140,008.20 and 13,300.00; whole dollars allowed: 140,008 and 13,300 | cents, or whole dollars | HALF_UP | "states the June shipped total dollar amount and the slipped-to-July total dollar amount, and both numbers exactly match the respective table totals": the item demands agreement with the table totals, not a precision; a whole-dollar narrative figure equal to the table total rounded HALF_UP to whole dollars matches it at the precision shown, a figure that differs at the precision shown fails · APPROVED |
| 48 | Account summary, Marchand | % 99.2699 (rubric range 99.0–99.6); short 197.712 → 197.71 (cents) / 198 (whole $) | range; cents or whole $ | HALF_UP | "percent shipped between 99.0% and 99.6% inclusive and $ Short Shipped equals $198": the rubric itself states the amount in whole dollars, so the HALF_UP whole-dollar value passes; a cents value equal to the exact figure at cents also passes (197.71 → 198); 197 fails · APPROVED |
| 49 | Account summary, Five O Fore | % 97.0000 (rubric: equal to 97.0 %); short 772.98 → 772.98 / 773 | 1 dp of %; cents or whole $ | HALF_UP | "percent shipped equal to 97.0% and $ Short Shipped equals $773": whole dollars stated by the rubric; percent at one decimal · APPROVED |
| 50 | Account summary, Thread Up | % 90.7869 (90.6–91.0); short 2,263.046 → 2,263.05 / 2,263 | range; cents or whole $ | HALF_UP | "between 90.6% and 91.0% inclusive and $ Short Shipped equals $2,263": whole dollars stated by the rubric · APPROVED |
| 51 | Account summary, Sigma | % 93.2417 (93.0–93.4); short 1,533.306 → 1,533.31 / 1,533 | range; cents or whole $ | HALF_UP | "between 93.0% and 93.4% inclusive and $ Short Shipped equals $1,533": whole dollars stated by the rubric · APPROVED |
| 52 | Account summary, Pronto | % 99.4257 (99.0–99.8); short 108.56 → 108.56 / 109 | range; cents or whole $ | HALF_UP | "between 99.0% and 99.8% inclusive and $ Short Shipped equals $109": whole dollars stated by the rubric (108.56 → 109; 108 fails) · APPROVED |
| 53 | Account summary, Hunt's | % 99.9223 (99.8–100.0); short 12.000 → 12.00 / 12 | range; cents or whole $ | HALF_UP | "between 99.8% and 100.0% inclusive and $ Short Shipped equals $12": whole dollars stated by the rubric · APPROVED |
| 54 | Account summary, Dolce | % 97.0000 (rubric: equal to 97.0 %); short 322.992 → 322.99 / 323 | 1 dp of %; cents or whole $ | HALF_UP | "percent shipped equal to 97.0% and $ Short Shipped equals $323": whole dollars stated by the rubric; percent at one decimal · APPROVED |
| 55 | Narrative sentence, June shipped | 140,008.204 → 140,008 | whole dollars, ±1 (this item only) | HALF_UP | "'Shipped a total of $140,008 for the month.' (numeric value present must be $140,008 +/- $1)": explicit whole dollars and explicit tolerance · APPROVED |
| 56 | Narrative, June completion % | 96.4119 % → 96 % (rubric: ±0.5) | per rubric | HALF_UP to whole percent | "shipped at 96% complete (numeric value present must be 96% +/- 0.5%)": explicit · APPROVED |
| 57 | Narrative, June shortfall | 5,210.596 → 5,211 | whole dollars (exact) | HALF_UP (5,210 fails) | "short by $5,211 (numeric value present must be $5,211)": explicit exact whole dollars · APPROVED |

Items 47–54 are conditional ("If an account-level summary is present"); when no
account-level summary exists they are graded per the rubric's own condition, not as
precision failures.

Items 22, 24, 26, 39, 40 concern PO-set membership, not amounts; items 29–31 are edge
cases that do not arise in this log (no zero-value PO, no over-shipment).

Three matters are recorded and graded separately; none offsets another (APPROVED):
1. June shipped amount — reference 140,008.20 as above (rubric 35, 37, 55; C1).
2. PO-level deliverable structure — the prompt describes the log "at the PO level" and
   asks to "identify all orders that shipped" in June; a PO-level table is an original
   requirement. Absence is a confirmed `fail` on the items that need it, never
   `cannot_assess` (rubric 5–21, graded item by item; C2).
3. PO membership evidence — when a deliverable carries only hard-coded account totals,
   the June and slipped PO sets cannot be verified; rubric 22 and 24 are `cannot_assess`
   for that deliverable. This does not offset matter 2 and does not affect matter 1.

- C1 June shipped total (APPROVED). Requirement: the June shipped total equals the
  reference under the numeric rule above and is labelled as such (rubric 35). Check: D.
  Not compensable: the recap exists to report what shipped.
- C2 Auditable PO-level evidence (APPROVED). Requirement: the June table lists the POs
  (PO number, account, dates, ordered and shipped value at cost) so that the total can be
  audited against the log (rubric 7–15, 22). Check: D (PO numbers present and matched to
  the log). Not compensable: an account-level summary cannot be audited by the account
  managers; missing PO-level evidence is a critical fail.
- C3 Slipped cohort (APPROVED 2026-10-30). Requirement: exactly the 5 POs under the strict window rule,
  PO value at cost 13,300 (rubric 24, 36). Check: D. Not compensable: the second explicit
  ask.
- C4 Row or account arithmetic (APPROVED 2026-10-30). Requirement: % shipped = shipped / ordered and
  short = max(ordered − shipped, 0) wherever reported (rubric 27, 28 for PO-level; 47–54
  for account-level). Check: D. Not compensable: wrong derived columns mislead account
  managers.
- C5 Narrative consistency (APPROVED 2026-10-30). Requirement: the narrative states the June shipped
  total and the slipped total and both match the tables (rubric 37). Check: D on
  extracted text including drawing text boxes, J for phrasing. Each narrative figure is
  graded by the metric it names (K2). Not compensable: the cross-file consistency
  requirement of the research question.
- D: 1–36, 39–41, 47–57 where values are extractable; J: 38, 42–46, 58 (phrasing);
  V: 59.
- K1 (class a): rubric 5–21 describe PO-level tables (Account, PO Number, Start Ship
  Date, Cancel Date, PO Value at Cost, Actual Ship Date, Shipped Value, % Shipped,
  Short-Shipped $; Excel Table with AutoFilter). The gold provides account-level pivot
  summaries only; it lacks PO Number and date columns and the Table/AutoFilter objects
  and would fail those items individually. Items are graded one by one, not failed as a
  block: a PO-level table with some columns missing fails only the items for the
  missing columns.
- K2 (class a, metric semantics): the gold narrative (drawing text box) reads "Shipped a
  total of $145,219 for the month … short by $5,211 … five PO's with a June ship window,
  a total value of $13,248 (actual shipped value)". $145,219 is the June order value at
  cost (145,218.80) labelled as shipped: a labelling error against rubric 55 and 37.
  $13,248 is the slipped group's actual shipped value, a correctly computed figure for a
  different metric than rubric 36/37 ask for (PO value at cost, 13,300): graded `fail`
  on 37 as written and recorded as "metric mismatch", not as an arithmetic error.
- K3: rubric 22/24 name the input "Reference_PO_Log.xlsx"; the actual file is
  `PO Log.xlsx`. No grading effect.
- K4: narratives may sit in a text box; extraction reads drawings (section 1.9).
- Deterministic rules of grader v0 (2026-11-01; operational definitions, class c, fixed before any output of this
  task was opened; for human review at the labeling checkpoint): tables are header rows naming at least two recap
  fields with an account or PO column (the rubric's labels and the log's own labels, case, punctuation, "Sum of", "$"
  and "at" ignored), their rows down to the first blank row, labelled total rows, and caption text above the table's
  own columns; PO-level tables are classified by their actual ship months (all June, all July; mixed months = another
  table such as a log copy), account-level tables by their caption; "the June shipments table" is the PO-level June
  table, else the June account-level table (likewise for the slipped table); the account-level summary of 47-54 is the
  June account-level table. Conditional items (29, 31, 41, 47-57) whose condition does not arise pass ("condition not
  met"); 22 and 24 are cannot_assess without PO numbers (matter 3), 23 without an actual-ship column; 26 and 40 hold
  when no PO number appears; a required column that is absent fails the item that tests it, 32 included; a formula
  without a cached value is unreadable (cannot_assess), never blank or wrong. Expert workbook: 5, 6, 8-10, 12, 17-20,
  32, 37 and 55 fail; 22-24 cannot_assess; C1 and C4 pass, C2 and C5 fail, C3 not confirmed.

### 2.3 `47ef842d-8eac-4b90-bda8-dd934c228c96` — Weeks of supply (Order Clerks)
Inputs: `Reference Inventory.xlsx` (sheet DATA, 6,612 rows, one snapshot: 2025 week 28,
45 UPCs; Store Number stored as text; no duplicate store rows within any UPC; "Avg Days
On Hand" holds "-" in 5,531 rows). Deliverable: .xlsx summary for five UPCs with weekly
rate of sale, WOS, store count, OOS count, % OOS, a chart, and shown work. Rubric: 58
items, weight 99.

Operational definitions, fixed before any model output is seen (APPROVED). The prompt
defines an active store as one that "appears in the dataset for that item … and also if
it has an out-of-stock percentage"; no out-of-stock percentage field exists in the data.
The following are therefore this evaluation's definitions (class c), not the data
dictionary's:
- Active store (per UPC): a distinct Store Number that has a row for that UPC in the
  snapshot. Denominator of Percent OOS = count of active stores for the UPC.
- Out of stock: the store row has Current Week Inv = 0 (the data holds no negative
  inventory). Count of OOS stores = number of such active stores.
- Weekly unit rate of sale = 7 × Σ "Daily Inv Sold In Last 4 Wks" over the UPC's active
  stores, recorded values used as they are (a few rows are negative: 3 / 2 / 3 / 8 / 1 for
  the five UPCs in the order below).
- WOS = Σ Current Week Inv over active stores / weekly unit rate of sale. If the weekly
  rate is 0, WOS is "not computable" (blank, NA, or similar); a finite number is wrong.
- "-" in "Avg Days On Hand" appears exactly on the rows whose daily sales are 0 (5,531
  rows both ways; on every numeric row Avg Days On Hand = Current Week Inv / daily sales).
  It is read as "turnover days not computable", an operational reading supported by the
  data, not a data-dictionary definition. Those rows stay in every inventory and sales
  aggregate; they are not dropped and not treated as zero inventory. "-" stays
  not-computable: never filled with 0, never included in a numeric average of that column.

Recomputed per UPC (active stores, current inv, daily sold, weekly rate, WOS, OOS count,
% OOS):
875218534223: 1,064 / 2,223 / 10.535714 / 73.75 / 30.142 / 123 / 11.56 %;
375301052429: 728 / 794 / 2.25 / 15.75 / 50.413 / 64 / 8.79 %;
567219040266: 1,131 / 3,890 / 5.928571 / 41.50 / 93.735 / 26 / 2.30 %;
901153373247: 1,232 / 4,797 / 14.464286 / 101.25 / 47.378 / 7 / 0.57 %;
217313054556: 1,222 / 3,805 / 6.714286 / 47.00 / 80.957 / 2 / 0.16 %.

Numeric rule for this task: counts exact; rate, WOS and % OOS within the tolerance each
rubric item states (ranges or nearest integer); where an item states none, the value is
compared unrounded with |difference| < 0.005 for rates and WOS and < 0.05 percentage
points for percentages.

- C1 Scope (APPROVED 2026-10-30). Requirement: exactly the five UPCs, each once, full 12-digit display
  (rubric 2, 3, 21). Check: D. Not compensable: wrong products.
- C2 Rate and WOS (APPROVED). Requirement: weekly rate and WOS per the definitions above,
  within rubric tolerances for all five (rubric 7, 8, 22, 23, 29, 30, 36, 37, 43, 44, 50,
  51). Check: D. Not compensable: the inventory health metric is the deliverable.
- C3 Out-of-stock (APPROVED). Requirement: OOS count and % OOS per UPC under the
  definitions above (rubric 5, 6, 25, 26, 32, 33, 39, 40, 46, 47, 53, 54). Check: D. Not
  compensable: the prompt's stated purpose is to expose stock risk. A deliverable that
  uses another interpretation is handled under section 1.8: recorded, checked against
  the prompt; accepted only with explicit support in the task materials; `cannot_assess`
  only for the specific items the materials cannot decide.
- C4 Chart (APPROVED 2026-10-30). Requirement: a chart of % OOS by UPC with exactly the five
  categories and values matching the table (rubric 13, 14). Check: D on chart XML + V.
- D: 1–14, 17–57 (values, formulas present per item 12, formats). J: none beyond
  label wording in 57. V: 15, 16, 58.
- A-5 (also 25, 32, 39, 46, 53). Rubric text: "Count of Stores Out of Stock per UPC
  equals the number of Active Stores with Out-of-Stock Percentage > 0%". Independent
  result: no out-of-stock percentage field exists; under "Current Week Inv = 0" the
  counts are 123 / 64 / 26 / 7 / 2. Adjudication: items graded under the operational
  definition above. Rationale: zero on-hand inventory is the direct reading of "out of
  stock" for a snapshot; the data holds no negative values; the counts are internally
  consistent with the rubric's own figures. Scoring effect: items 5, 25, 32, 39, 46, 53
  are gradable; the prompt gap is disclosed as a task-material defect. Status: APPROVED.
- A-31. Rubric text: "For UPC 375301052429, Number of Stores equals 729". Independent
  result: 728 distinct Store Numbers (728 rows, no duplicates). Adjudication: graded
  against 728. Rationale: the rubric figure copies the gold; the data supports 728 and
  the task's own active-store rule counts distinct stores. Scoring effect: item 31 passes
  only for 728; item 33 is unaffected (64/728 = 8.79 %, 64/729 = 8.78 %, both inside
  8.7–8.9 %). Status: APPROVED.
- A-52. Rubric text: "For UPC 217313054556, Number of Stores equals 1223". Independent
  result: 1,222 distinct Store Numbers (1,222 rows, no duplicates). Adjudication: graded
  against 1,222. Rationale: as A-31. Scoring effect: item 52 passes only for 1,222; item
  54 is unaffected (2/1,222 = 0.16 %, 2/1,223 = 0.16 %, both inside 0.1–0.3 %). Status:
  APPROVED.
- K1: rubric 9 (division by zero) cannot occur with this data; graded `pass` if no error
  is shown and the WOS cells are numeric.

### 2.4 `1137e2bb-bdf9-4876-b572-f29b7de5e595` — PO entry audit (Order Clerks, pilot task)
Inputs: `Reference_PO Data.xlsx` (41 lines, UOM CASE 24 / EA 17, no blank case packs;
prices carry float noise such as 5.090000000000001). Deliverables: .xlsx with error
columns and a SKU-level summary/pivot with PO drill-down; .docx summary with
recommendations. Rubric: 62 items, weight 80.

Recomputed: 15 price mismatches, 10 case-pack errors, 25 total. Per SKU: 0103 (4+1),
0104 (0+1), 0107 (4+2), 0108 (3+1), 0111 (0+2), 0112 (4+1), 0118 (0+2). Flagged
lines listed in `private/checks/recalc/1137e2bb-….json`.

Numeric rule for this task: prices compared at two decimals (half-up) before testing
equality, so float noise is not a mismatch; counts exact.

- C1 Line flags (APPROVED 2026-10-30). Requirement: price mismatch and case-pack flags correct on all
  41 lines, totals 15 / 10 / 25 (rubric 5–8, 18–20, 31–55). Check: D. Not compensable:
  the audit's purpose is to find these lines.
- C2 SKU summary (APPROVED 2026-10-30, revised text). Requirement: a separate summary
  tab with the three measures per SKU (rubric 12, 13), each SKU's totals equal to the
  recomputed values (rubric 56–62), and the summary totals reconciling to the detail-sheet
  flags (rubric 15–17). Check: D. Not compensable: management acts on the SKU view; a
  wrong SKU count misdirects the follow-up. Drill-down to PO (rubric 14) is graded as
  written in the ordinary rubric pass (a PO Number field, or a pivot or table that opens
  detail) and is not part of the critical criterion.
  Record of the revision. Superseded text: summary tab with the three measures per SKU,
  reconciling to the line flags, drill-down to PO (rubric 12–17, 56–62); check D (values)
  + D on pivot XML or table structure for drill-down. Drill-down check of 2026-10-30: the prompt asks for "a summary table or pivot table
  that aggregates errors at the SKU level, with the ability to drill down to the PO
  level"; rubric 14 (weight 2 of 80) is the only item that requires it: "The Summary
  worksheet allows drill-down to the PO level (e.g., includes PO Number as a field or
  enables double-click into detail that shows PO Number)"; rubric 56–62 require only the
  per-SKU totals (SKU-0103 5, 0104 1, 0107 6, 0108 4, 0111 2, 0112 5, 0118 2) and say
  nothing about PO-level detail or drill-down. Non-compensability test: the PO-level
  detail managers need to act on is already present in the flagged line sheet (C1), and
  a summary with correct SKU counts that lacks a drill-down field does not misstate the
  audit's findings or misdirect the follow-up; the drill-down is a navigational
  convenience whose absence other satisfied items can compensate. The revision above was
  approved by the human on 2026-10-30; the drill-down requirement stays in the
  item-by-item rubric grading.
- C3 Word summary (APPROVED 2026-10-30). Requirement: .docx present, defines the two checks, states
  counts consistent with the workbook, names SKUs with the highest frequency (0103, 0107,
  0108, 0112 each have >= 4 errors), gives a starting recommendation (rubric 2, 23–30).
  Check: D for presence and numbers, J for content. Not compensable: cross-file
  consistency and the business recommendation.
- D: 1–10, 12–22, 25, 26, 31–62 (items 2, docx present, and 21, graded as written under
  A-21, were omitted from the earlier list and are deterministic presence/structure checks;
  corrected 2026-10-30 when the checks were implemented). J: 11, 23, 24, 27–30. V: none (no
  formatting item).
- A-21. Rubric text: "Excel includes a separate indicator for missing/invalid Case Pack
  when UOM = CASE and Case Pack is blank or ≤ 0 (e.g., a 'Case Pack Missing' flag), and
  such rows are not counted as Case Pack errors". Independent result: the prompt does not
  ask for this indicator and no such rows exist (0 blank or non-positive case packs).
  Adjudication: graded as written (an absent indicator fails the item); excluded from
  critical; disclosed separately under "rubric requirements beyond the prompt".
  Rationale: the rubric text is unambiguous and the item is gradable; its weight (1) is
  reported, not removed. Scoring effect: item 21 counts in W and E; critical status is
  unaffected. Status: APPROVED.
- K1: rubric 22 (sorted or easily sortable): a pivot or Excel table counts as sortable.
- Cell-value rule for the deterministic checks (implemented 2026-10-31 after the independent
  extraction review; APPROVED by the human 2026-10-31, including a blank flag as a confirmed
  invalid value; applies to every item that reads a value). A cell that is reliably read
  but is not what the rubric requires at that place — blank, an Excel error value, NaN or
  Infinity, text that is not a number (for Total Errors and the summary measures) or not a 0/1
  flag (for the two flag columns) — is a confirmed invalid value: the items that need that
  value FAIL on it (rubric 5–9, 15–20, 31–55, 56–62 as applicable), with the cell and the
  original value recorded. Only a cell whose value cannot be read (a formula without a cached
  value after a failed recalculation, an ambiguous or unrecognised column, a grader fault) is
  unreliable → `cannot_assess` with grader-side attribution. No comparison is ever skipped into
  a PASS. Note: the implementation before this review read a blank flag as 0 for rubric
  5/6/7/18/19 (an implementation choice, never recorded here); under this rule a blank flag is
  a confirmed invalid value for those items too, because rubric 5–7 require "0 otherwise" and
  rubric 9 requires 0/1 on every row. Per-PO/SKU items 31–55 read only the cell of their own
  line; an error in another row never affects them.
- Identity rule for PO / SKU ids (2026-10-31). Ids are normalised with the rules the source
  format supports (case, outer and inner spaces, an optional separator after the prefix,
  leading zeros of the number) and resolved to the reference entity. A legal variant of one
  reference id is that entity and takes part in the row-multiset comparison like any other
  row (a lowercase duplicate is a duplicate row). Two distinct reference entities whose ids
  normalise to one identifier are a reference collision: recorded (originals, normalised id,
  entities, rows), the row-set items and the named lines whose ids collide are
  `cannot_assess` (grader side), nothing is merged. The actual source has no such collision
  (10 PO and 16 SKU originals, none shared after normalisation).
- Several detail tables (2026-10-31). When more than one sheet has the detail-table structure
  and the sheets hold complementary input rows, the grader does not merge them: every
  candidate and its coverage is recorded, the row-set and reconciliation items (5–7, 15–20) are
  `cannot_assess`, named lines are looked up in every candidate, per-row items (8, 9, 10) run
  over every candidate, and no row is asserted missing from a single sheet. A confirmed
  violation found in any candidate still FAILs its item.
- APPROVED 2026-10-31 (proposed by the independent extraction review the same day; the
  proposal below is kept verbatim as the record; the approved rule and the amendment record
  follow it). Question: which items carry the "all 41 lines" completeness requirement of C1,
  and what exactly fails rubric 7 and 18–20.
  Rubric text, verbatim:
  - 7: "When UOM is not 'CASE' (e.g., 'EA') or blank, Case Pack Error is 0 regardless of Case
    Pack value"
  - 18: "Overall dataset totals are correct: 15 Price Mismatch errors across all rows"
  - 19: "Overall dataset totals are correct: 10 Case Pack errors across all rows"
  - 20: "Overall dataset totals are correct: 25 Total Errors across all rows"
  Necessary conditions stated by the text: 7 — on every line whose UOM is not CASE (or blank)
  the case flag is 0; 18–20 — the sum of the respective column over all rows of the delivered
  dataset equals 15 / 10 / 25.
  Current implementation (in force): 7 and 18–20 FAIL on (a) a confirmed invalid or missing
  flag/total column, (b) a reliable wrong value (7: a non-CASE line with case flag ≠ 0; 18–20:
  a sum ≠ 15 / 10 / 25 over the identified rows of a complete row set), and (c) any confirmed
  row-set defect: a missing input line (lower bound > 0), an extra row, a duplicated row or a
  changed row — because C1 ("flags correct on all 41 lines, totals 15 / 10 / 25") was mapped
  onto 5–8, 18–20 and 31–55 and the row-set rule was attached to 5, 6, 7, 18, 19, 20 alike.
  Proposed rule: keep (a) and (b); keep (c) for 5 and 6 (the two flag-logic items are where
  "every line" is tested, and C1 fails through them); drop (c) from 7 and from 18–20, which
  would then fail only when their own stated condition is violated (7: a non-CASE line with a
  non-zero case flag, or such a line absent so that its flag cannot be 0 — proposed: an absent
  non-CASE line is a confirmed violation of 7 only when its identity is certain, i.e. U = 0;
  18–20: the column sum over all delivered rows ≠ 15 / 10 / 25, or an invalid cell in the
  column; extra zero-error rows and duplicated zero-error rows leave the sums unchanged and
  do not fail 18–20).
  The three things kept apart: row-set completeness (all 41 input lines present exactly once;
  C1 through 5 and 6), per-line flag correctness (5, 6, 7, 31–55), aggregate correctness
  (18–20, and 15–17 against the summary).
  Scenario "a zero-error line is duplicated and every aggregate is still correct": current →
  5, 6, 7, 18, 19, 20 FAIL (12 of 80 points), C1 fails. Proposed → 5 and 6 FAIL (the flag
  logic is not "implemented" on a dataset that is not the input dataset; C1 fails), 7 PASS
  (every non-CASE line, including the duplicate, carries 0), 18–20 PASS (the sums across all
  rows are 15 / 10 / 25 as the text requires). The duplicate itself is reported under 5 and 6
  with the row named.
  Why "all rows" applies where it does: 18–20 say "across all rows" — the sum is over the rows
  that exist, so a duplicated zero-error row or an extra zero-error row does not change it;
  a missing flagged row does (sum < 15) and FAILs. 7 says "when UOM is not CASE" — a
  per-line condition over the lines present. Neither text says "all 41 input lines are
  present"; that requirement is C1's and is carried by 5 and 6 under the proposal.
  Comparison with the approved C1 and false-PASS risk: C1 still fails on any missing, extra,
  duplicated or changed row (through 5 and 6), so no row-set defect produces a passing C1.
  At the item level the proposal can PASS 7 and 18–20 for a deliverable with duplicated or
  extra zero-error rows (which the text literally allows) and for a deliverable that drops a
  zero-error line while 5 and 6 FAIL for it; it cannot PASS 18–20 for a deliverable that
  drops a flagged line (the sum is short) or hard-codes 15 / 10 / 25 in a cell (the sum is
  over the column, not a reported number). Weight effect of the scenario above: 4 instead of
  12 points lost. Possible conflict reported, not adjudicated: the current implementation
  fails 18–20 for a duplicated zero-error row although the column sums equal 15 / 10 / 25 as
  the item text requires; the human decides whether the C1 mapping or the item text governs.
  Status: APPROVED 2026-10-31. Approved rule, as decided by the human: (1) a missing, extra,
  duplicated or changed row acts on C1 through items 5 and 6 only and does not by itself fail
  any other ordinary rubric item; (2) item 7 checks, on the reliably identified non-CASE lines
  only, that Case Pack Error = 0; an absent line never fails item 7; (3) items 18, 19, 20
  compare the column sums over all delivered rows with 15 (Price Mismatch), 10 (Case Pack
  Error) and 25 (Total Errors) and are judged independently, never failed because C1 fails;
  (4) the approved evidence priority stays: a reliably read invalid cell in the column is a
  confirmed violation, an unreadable cell makes the item `cannot_assess`.
  Amendment record. Old rule: the row-set violation (`row_set_violation`) was attached to
  items 5, 6, 7, 18, 19, 20 alike, and 18–20 compared the sum over identified rows only when
  the row set was complete. Evidence that it was wrong: a duplicated or extra zero-error row
  and a deleted zero-error row failed 7 and 18–20 although the item texts ("when UOM is not
  CASE", "across all rows") are satisfied by the delivered rows and the column sums equal
  15 / 10 / 25 (extraction review, 2026-10-31). New rule: as above; in `DEPENDENCIES` of
  `grading/checks_1137e2bb.py` items 7, 18, 19, 20 no longer require `row_set` and carry
  `row_set_violation: False`; 18–20 sum every readable cell of the column over all delivered
  business rows and compare directly. Re-grading: no graded model run exists yet (pre-pilot);
  nothing to re-grade. Scoring effect on the documented scenario (duplicated zero-error row):
  5 and 6 FAIL, 7 and 18–20 PASS, C1 fails; a deleted flagged line fails the sum items whose
  column it affects and its own named line.

- Gold-first verification (2026-11-01; `grading/validation/1137e2bb-…/`). Independent
  recomputation from `Reference_PO Data.xlsx` equals the stored reference and the expert
  workbook's own flags on all 41 lines (15 / 10 / 25; per-SKU identical). Original first
  pass of the grader of 2026-10-31 on the expert deliverables: 49 pass, 0 fail, 6
  `cannot_assess` (4, 8, 10, 17, 20, 21; grader side). Classification and amendments,
  all grader-side extraction rules (no grading rule, critical criterion or adjudication
  changed; no model output existed):
  - Grader defect: the expert's total column is headed "Number of Errors", which the
    synonym table did not know. New rule: the total-column synonyms and keywords include
    "number of errors", "# of errors", "error count per line" and the like; a column is
    `confirmed_missing` only when every other header maps (unchanged). Effect: 4, 8, 17,
    20 become assessable.
  - Grader defect: a formula whose result is the empty string (the expert's TEXTJOIN on
    zero-error lines) was read as a formula without a cached value (both Excel and
    LibreOffice store it as a string-typed cell with an empty value; openpyxl returns
    None, as for an uncached formula). New rule: the extraction keeps such a result as the
    value "" (data type `str`), in the original and in the recalculated copy. Effect: 10
    becomes assessable; the recalculation comparison counts 164 of 164 formulas equal.
  - Expert-deliverable defect (A-21, unchanged): the expert workbook has no Case Pack
    Missing indicator; with the total column mapped, `case_missing` is `confirmed_missing`
    and item 21 fails as written (the only non-pass of the expert deliverables).
  - Grader defect found by the corruption catalog (R14): a workbook whose only other sheet
    is a copy of the raw input returned `cannot_assess` for the summary items instead of a
    confirmed FAIL. New rule: sheets that are identified detail-table candidates (the raw
    copy is one) can never hold the summary; with no other sheet the summary is confirmed
    absent (C2 fails). The conservative `cannot_assess` stays for genuinely unrecognised
    sheets.
  - Grader defect found by the layout catalog (N02–N04): footer TOTAL rows, legend and
    note rows and Excel subtotal rows ("PO1001 Total") under the detail table were read
    as business rows with blank or non-binary flags and failed 5–7. New rule: a row with a
    blank quantity cell and blank business cells (entered, expected, UOM, case pack),
    whatever its id cells hold, is an annotation row (`no_id`): never summed, matched or
    counted as a row that could hold a missing input line.
  Result after the fixes: 54 pass, 1 fail (21), 0 `cannot_assess`; C1 pass, C2 pass,
  C3 not confirmed (judge items pending); identical through the LibreOffice path. The
  catalog (24 rubric-relevant corruptions, 20 neutral transformations) and the two
  recalculation-path cases land exactly on their declared maps.
- Rubric 9 format rule (DECIDED by the human 2026-11-01; grader 1137e2bb-2026-11-01.2).
  Item 9 ("flags are binary (0 or 1) across all rows") requires numeric 0/1: Excel
  booleans TRUE/FALSE, Yes/No and the text "0"/"1" fail its format requirement. Items
  5–8, 15–20 and 31–55 evaluate semantics independently and read an unambiguous
  representation (TRUE/FALSE, Yes/No, Y/N, the text "1"/"0") as its value, so a format
  failure never cascades into a business-rule failure. Anything else ("x" marks, words,
  other numbers) is not a flag value and a blank stays a confirmed invalid flag (cell-value
  rule). Superseded implementation: "x", "error", "mismatch" read as 1 and "ok", "none" as 0
  for every item, and no format distinction existed. Regressions: gold variants R25–R28.
- Business-row population rule (verified 2026-11-01; grader 1137e2bb-2026-11-01.2). Rows
  below the header are `identified` (PO, SKU and quantity resolved to one input entity),
  `unidentified` (business data present but identity unresolved: blank or unparseable id,
  reference collision, unresolved quantity) or `no_id` (no source data, or an annotation
  row: blank quantity with blank business cells, or no parseable id with blank prices and
  UOM - footer TOTAL rows including one that sums the quantity column, Excel subtotal rows,
  legends, notes). An identified row that matches no input line is an extra row and a
  missing input line is a missing row: both fail C1 through 5 and 6. An unidentified row is
  a delivered row: it counts in the column sums of 18–20 and in the reconciliation 15–17,
  it may hold a missing input line (the row-set items are `cannot_assess`, attribution
  unknown, never FAIL on its account), and it never matches a named line. Annotation rows
  are never business rows. Regressions: gold variants N02–N04, N21, R17, R29.
- Rubric-valid grouped SKU roll-up with PO-level drill-down (one row per SKU with the three
  measures, PO rows beneath, grand total, sorted, filterable): graded like the expert
  pivot (gold variant R30, neutral).

### 2.5 `c3525d4d-2012-45df-853e-2d2a0e902991` — Holiday floor-stand budget (Order Clerks)
Inputs: `Email Trail Floorstands.docx` (base 5.65; side panels 2.24 × 2; shelf strips
1.89 × 4; unit 17.69; 1,228 stores; 5 % overage; total 22,802.41),
`Holiday Floorstand Store List Original.xlsx` (1,228 integer store numbers, 1–4
digits), `Holiday Matrix final count.xlsx` (1,257 store numbers stored as 4-character
text, 620 with leading zeros, 26 marked "CAPITAL PLAN"). Deliverables: .xlsx (cost
comparison tab; final list tab with added stores highlighted) and .docx draft email.
Rubric: 52 items, weight 86.

Set comparisons (APPROVED): ids are normalised (leading zeros removed, integer text)
before comparison; the id as written in the final list is kept for display. Two
comparisons are reported with both sides named:
- A. Original input list vs revised input list: raw string comparison matches 610 ids
  (the 4-digit ids without leading zeros); after normalisation 1,226 ids are common,
  31 added (557, 657, 679, 893, 1031, 1034, 1039, 1057, 1067, 1162, 1365, 1484, 1537,
  2609, 2612, 3020, 3399, 5119, 5120, 5850, 5872, 5890, 5891, 5996, 6024, 6771, 6781,
  6795, 6981, 7977, 9589), 2 removed (3737, 4099), neither in the final list.
- B. Gold final-list tab vs revised input list: the gold lists 1,257 six-digit ids
  (100246–999585); 0 are common with the revised list and 0 with the original list;
  positional 4-digit substrings hit the revised list at chance level (74 / 157 / 173 of
  1,257, non-unique), so no mapping is derivable. The gold flags 31 rows ADDED (count
  equal to A, ids not).

Recomputed budget: unit cost 17.69 → 18.69. Overage 5 %: 1,228 × 0.05 = 61.4 → 61 →
1,289 units; 1,257 × 0.05 = 62.85 → 63 → 1,320 units. Totals 22,802.41 → 24,670.80;
change 1,868.39.

Numeric rule for this task: counts and units exact; costs compared at cents (half-up)
unless the rubric item states a percentage tolerance (items 28, 29, 31), which then
applies.

- C1 Store reconciliation (APPROVED). Requirement: counts 1,228 / 1,257, the added and
  removed sets as in comparison A, explicit status of 4099 and 3737 (rubric 22, 23,
  32–36). Reference: the two input files, compared after normalisation. Check: D. Not
  compensable: the production quantity follows from it. Store numbers and list
  correctness are verified against the original inputs; the absence of provenance for
  the gold's ids (comparison B) does not make any item `cannot_assess`. Only an item
  that demanded a specific id not derivable from the provided materials, with no
  reasonable adjudication, would be marked `cannot_assess`, with the basis recorded; no
  such item exists in this rubric.
- C2 Budget arithmetic (APPROVED). Requirement: unit costs 17.69 / 18.69, units 1,289 /
  1,320, totals 22,802.41 / 24,670.80, change 1,868.39 within rubric tolerances (rubric
  15–20, 24–31, 49). Check: D. Not compensable: the budget is the deliverable.
- C3 Email consistency (APPROVED 2026-10-30). Requirement: email states 1,320 units, the change and
  the new total, both drivers, and the numbers match the workbook (rubric 37–42). Check:
  D for numbers, J for content. Not compensable: cross-file consistency.
- D: 1, 3–36, 42–47, 49; J: 2, 40, 48, 50, 51; V: 52.
- K1 (class c, input format): a raw comparison of the two lists matches only 610 ids
  because 620 final-list ids carry leading zeros. Grading normalises; a deliverable that
  fails to normalise fails C1 by rubric text and is tagged "input format trap" in the
  failure analysis.
- K2 (class a): the gold's final-list tab holds re-identified six-digit ids
  (comparison B); it would fail rubric 32 as written. The gold is not the id reference.
- A-24/25 (operational rounding rule, class c). Rubric text: "Original total units to
  produce (including overage) are shown as 1,289." / "Revised total units to produce
  (including overage) are shown as 1,320." Independent result: 1,228 × 1.05 = 1,289.4 and
  1,257 × 1.05 = 1,319.85; the source email states the unit cost 17.69 and the total
  22,802.41 but no unit count and no rounding rule; 1,289 units are inferred back from
  the email's total (22,802.41 / 17.69 = 1,289 exactly). Adjudication: overage units are
  rounded to the nearest integer, HALF_UP (1,289 / 1,320), the operational rule for this
  evaluation. Rationale: the unit count inferred from the email's total is consistent
  with nearest-integer rounding; the rule is not stated in the task and is not proven to
  be the author's algorithm, so it is recorded as this evaluation's rule.
  Scoring effect: items 24, 25 graded as written; floor (1,319) fails 25 and passes 29
  within its 0.5 % tolerance; ceiling (1,290) fails 24 and passes 28 within 0.1 %.
  Status: APPROVED.

### 2.6 `7b08cd4d-df60-41ae-9102-8aaa49306ba2` — Tour profit and loss (Accountants and Auditors)
Inputs: `Fall Music Tour Ref File.xlsx` (three sheets: tour manager income and costs,
withholding assumptions, production company costs; all amounts USD). Deliverable: new
.xlsx P&L with Tour Manager / Production Company / Total columns, stops by city and
country, withholding by country, four expense categories, net income, "As of
12/31/2024" header. Rubric: 59 items, weight 89.

Recomputed (unrounded): gross 1,043,750; withholding UK 46,150.80, France 51,646.80,
Spain 56,821.20, Germany 36,702.76425, total 191,321.56425; net revenue 852,428.43575.
Expenses: tour manager 549,612.50 (band & crew 15,160; hotel & restaurants 47,560;
other costs 486,892.50 of which agency commission 114,812.50, insurance 22,024,
private jet 341,000, transfer cars 4,237, other 4,819); production 182,393 (band & crew
91,000; hotel & restaurants 78,738; petty cash 8,000, car service 2,976, fees 1,679);
combined 732,005.50. Net income 120,422.93575 (TM 302,815.93575; PC −182,393).

Numeric rule for this task (APPROVED): identities are checked on unrounded values.
Rubric figures are stated in whole dollars; a deliverable figure is compared with the
recomputed value after both are quantized half-up to the precision the deliverable
displays (whole dollars or cents). Rounded figures need not add up (852,428 − 732,006 =
120,422 while the rubric's 120,423 is the correctly rounded net income).

- C1 Withholding and net revenue (APPROVED 2026-10-30). Requirement: rates applied per country, net
  revenue 852,428.44 (rubric 15–24). Check: D. Not compensable: the stated rule.
- C2 Expenses (APPROVED 2026-10-30). Requirement: combined 732,005.50, TM 549,612.50, PC 182,393
  (rubric 49–51). Check: D. Not compensable: the P&L's other half.
- C3 Net income (APPROVED 2026-10-30). Requirement: 120,422.94 combined, 302,815.94 TM, −182,393 PC,
  and the identity net income = net revenue − expenses on unrounded values (rubric
  52–58). Check: D. Not compensable: the headline figure.
- D: 1, 3, 6–24, 29–51, 53–58 (values, structure); J: 2, 4 (USD; passes when all
  figures are USD and no conversion is misapplied), 25–28 (category labels), 41–48
  (item attribution; match by amount and party, labels may differ); V: 5, 59.
- K1 (class c, allocation): the prompt's four expense categories do not map one-to-one
  onto the source's "Other Costs" blocks. The rubric (items 32–34, 38–41, 44–45) encodes
  the gold's split: Other Tour Costs = agency commission + insurance (136,836.50); Other
  Travel Costs = private jet, transfer cars, other, petty cash, car service, fees
  (362,711). Adjudication (APPROVED): those items are graded as written. A failure is
  classified before it is reported: a clear misclassification (an item attributed to the
  wrong party, omitted, double-counted, or placed in a category it cannot belong to,
  such as hotel costs under withholding) is a model error; a documented, reasonable
  alternative split of the "Other Costs" items between Other Tour and Other Travel is
  tagged "allocation ambiguity (task material)". The critical criteria are
  allocation-invariant.
- A-45. Rubric text: "Other Travel Costs includes Petty cash: 8,000 USD, Transfer cards:
  2,976 USD, Other: 1,679 USD, all attributed to the production company." Independent
  result: the source labels are "Petty Cash" 8,000, "Car Service" 2,976, "Fees" 1,679
  on the production company sheet. Adjudication: matched by amount and party; the labels
  "Transfer cards" and "Other" are rubric wording errors. Rationale: the amounts and the
  party are unambiguous in the source. Scoring effect: a deliverable using the source
  labels passes; one using the rubric labels also passes. Status: APPROVED.
- A-53 (also 49, 50, 54). Rubric text: "Total Combined Net Income equals 120,423 USD."
  Independent result: 120,422.93575 unrounded; 120,423 half-up to dollars; the rounded
  components give 852,428 − 732,006 = 120,422. Adjudication: 120,423 (or 120,422.94 at
  cents) passes; 120,422 passes only if it is the deliverable's own rounded difference
  of correctly rounded components and the unrounded identity holds. Rationale:
  presentation rounding is not an arithmetic error (section 1.7). Scoring effect: items
  49, 50, 53, 54 graded on the quantized comparison; items 56–58 on unrounded values.
  Status: APPROVED.

### 2.7 `7d7fc9a7-21a7-4b83-906f-416dea5ad04f` — Prepaid amortization (Accountants and Auditors)
Inputs: `COA.xlsx` (46 expense accounts, including 6760 IT Services/Agreements, 6762
Subscription Fees/Service Agreements, 7001 Technical Services Fee, 6020 Building
Maintenance, 5400 Insurance, 5015 Healthcare Insurance), 41 expense invoices across
four PDFs (Jan 24, Feb 2, Mar 7, Apr 8; total 1,087,156.21), 25 insurance invoices in
one PDF (Good Insurance 21 dated 1/1/2025; BCBS 4 monthly at 5,493.27; total
568,698.22). All PDFs have a text layer. Deliverable: .xlsx with Prepaid Summary,
Prepaid Expenses (1250), Prepaid Insurance (1251). Rubric: 56 items, weight 95.

Numeric rule for this task (APPROVED): invoice amounts are exact rationals built from the
decimal text of the invoices (a float read from a workbook would go through
Decimal(str(x)) first with the raw cell value kept; that conversion is not claimed
lossless for arbitrary Excel floats); the monthly charge is amount / term as an exact
fraction; balances accumulate exactly; quantization HALF_UP to cents is performed on the
exact rational only where a figure is compared with the GL or a rubric figure, and the
Decimal context for the quantized figures is set to ROUND_HALF_UP explicitly. For the
total prepaid balance two paths are computed and both kept: (i) each account's balance
quantized to cents, then summed; (ii) the exact balances summed, then quantized once.
Rounding each invoice's monthly charge to cents before accumulating is not allowed: it
drifts from the GL by −0.01 (Jan) to −0.05 (Apr) on 1250 and by −0.01 to −0.05 on 1251,
while exact accumulation reconciles to 0.00 in every month. Precision settings and
tolerances are never adjusted to absorb a boundary case; the regression test
`scripts/recalc/test_7d7fc9a7_quantization.py` asserts the specific values in A-10.

Recomputed: 1250 with six-month straight-line amortization from the invoice month:
ending balances 518,934.8583… / 426,673.1283… / 473,655.55 / 559,377.6083… →
518,934.86 / 426,673.13 / 473,655.55 / 559,377.61, variance 0.00 against the GL every
month; YTD amortization 527,778.60. 1251 with Good Insurance over 12 months from January
and each BCBS payment amortized in the following month (coverage from 2/1/2025, first
payment due 1/15/2025): 506,657.9816… / 461,097.5533… / 415,537.125 / 369,976.6966… →
506,657.98 / 461,097.55 / 415,537.13 / 369,976.70, variance 0.00; YTD amortization
198,721.52. Amortizing BCBS in its own month misses the GL by 5,493.27 from February on.
Total prepaid at 4/30: exactly 185,870,861/200 = 929,354.305; HALF_UP once gives
929,354.31, and the sum of the two cent-quantized balances (559,377.61 + 369,976.70) is
also 929,354.31 (A-10).

- C1 Completeness (APPROVED). Requirement: every invoice present with its exact amount
  (rubric 13, 14, 33, 34). Check: D against the parsed invoice list (vendor, number,
  amount). Not compensable: a missing invoice breaks the reconciliation.
- C2 1250 reconciliation (APPROVED). Requirement: monthly ending balances equal the GL to
  the cent under the numeric rule, variance line shows 0.00 (rubric 21–26, 30). Check: D.
  Not compensable: the prompt requires reconciliation.
- C3 1251 reconciliation (APPROVED). Requirement: same for 1251 under the coverage
  periods stated in the prompt, BCBS amortized from the month after each payment (rubric
  36, 37, 39–44, 48). Check: D. Not compensable: as C2.
- C4 Summary linkage (APPROVED: linkage and account-balance principle, no exception for
  the total). Requirement: summary tab pulls from the detail tabs by formula and shows
  the two April balances (559,377.61 / 369,976.70), the total prepaid balance 929,354.31,
  and YTD amortization per account (rubric 7–11). Check: D (formula references + values
  at cents, HALF_UP). Not compensable: the snapshot is what management reads.
- Reconciliation and rounding rule (APPROVED 2026-10-30; closes section 4 item 5; the
  human's approval names it the C4 rule, and it governs the balances under C2, C3 and
  C4). The prompt requires the schedules to "reconcile to the end of month balances" and
  to "confirm that all figures reconcile accurately"; the given GL balances agree with
  the independently computed exact values after HALF_UP to cents. Rule: (a) an account
  whose monthly ending balances equal the given GL balances to the cent passes; (b) when
  a balance differs from the GL, the deliverable passes only if it provides an explicit,
  quantified reconciliation bridge or adjustment detail (for example a labelled rounding
  adjustment line with its amount) that closes the difference to the given GL balance and
  can be re-performed by the grader; (c) a textual statement that differences are due to
  rounding, without a quantified and checkable adjustment, fails; (d) an undisclosed
  difference between a schedule balance and the GL fails. Rubric items 23–26, 30, 41–44
  and 48 ("equals $… (rounded to the nearest cent), matching the GL balance provided";
  "Variance equals $0.00 (rounded to the nearest cent)") are graded item by item on their
  own text: the balance or variance the schedule actually shows, after any quantified
  bridge, is quantized HALF_UP to cents and compared with the GL figure or with 0.00. The
  expert deliverable is a reference only and never the sole evidence of correctness; the
  independent recalculation (`scripts/recalc/task_7d7fc9a7_prepaid.py`) is the reference.
  The per-line-rounding variant figures listed by that script document the drift and are
  not allowed values.
- D: 1–11, 13, 14, 19–30, 33, 34, 36–44, 47–50, 53 (structure and values);
  J: 12, 15–18, 31, 32, 35, 45, 46, 51, 52, 54, 55 (period documentation, organisation, COA
  mapping, column structure "or an equivalent structure" per K1); V: 56. (Corrected
  2026-11-01: the earlier D list also carried 55, in conflict with K1; K1 governs.)
- COA mapping (APPROVED): any account from `COA.xlsx` whose description reasonably covers
  the invoice's service passes items 45, 46, 51, 52 when the deliverable states the
  basis; the gold's mapping is not the reference (K2).
- A-10. Rubric text: "Prepaid Summary shows the total prepaid balance as of 4/30/2025
  equal to $929,354.31 (the sum of the April GL balances for 1250 and 1251) when rounded
  to the nearest cent." Independent result: exact total 185,870,861/200 = 929,354.305;
  HALF_UP once → 929,354.31; sum of the two cent-quantized balances → 929,354.31. (An
  earlier draft reported 929,354.30 from a 34-digit Decimal computation whose division
  residue fell just below the tie; exact rational arithmetic removes the artefact.)
  Adjudication: graded against 929,354.31, the rubric's own definition; no exception
  for any other figure. Rationale: both quantization paths give 929,354.31 on this data
  and the item is unambiguous. Scoring effect: item 10 passes only for 929,354.31.
  Regression test: `scripts/recalc/test_7d7fc9a7_quantization.py` asserts
  q_cents(185870861/200) = 929354.31 and that this task's sum of quantized balances is
  929354.31. Status: APPROVED.
- K1: rubric 55 ("seventeen columns") mirrors the gold layout; the clause "or an
  equivalent structure" governs. Judge item.
- K2 (class a): the gold maps UHY "Advising" to account 6600 "Advertising"; not used as
  the COA reference.
- K3 (class c): the BCBS treatment is pinned down by the GL balances and the prompt's
  coverage/payment dates, not stated explicitly; recorded as an inference the model must
  make from the reconciliation requirement.
- Gold-first verification (2026-11-01; grader 7d7fc9a7-2026-11-01.1; records in
  `grading/validation/7d7fc9a7-…/`). First pass of the new grader on the expert workbook:
  39 pass, 2 fail, 0 `cannot_assess`; C1 pass, C3 pass, C2 fail, C4 fail. Findings:
  - A-10b (class a, expert-deliverable defect): the expert summary shows no total prepaid
    balance; rubric 10 fails as written. The standard is not lowered.
  - A-30 (class a, expert-deliverable defect): the expert 1250 schedule's "variance" row
    carries no per-month figures (only a column-O residual) and its "G.L. Balance" row holds
    the schedule's own unrounded balances; rubric 30 ("for each month a GL Balance and
    Variance check is present and the Variance equals $0.00") fails as written. The 1251
    schedule has both rows. Consequence to decide (section 4): with 30 inside C2, the expert
    workbook fails C2 although every 1250 balance reconciles to the cent.
  - Expert workbook amounts carry Excel's accounting format without a currency symbol.
    Operational definition (class c) for rubric 53: an amount is "formatted as dollars" when
    its number format carries a currency symbol or shows exactly two decimals with thousands
    separators (accounting or number format); date cells must carry a date format. The expert
    passes; the General format fails (gold variant R17).
  - Operational definition (class c) for rubric 6: the reporting period is read from the
    summary's header block (the rows above the first amount) and must name April 30, 2025 or
    the April 2025 period (4/30/2025, April 30, 2025, 2025-04-30, "through April 2025"); a
    date inside a body label does not count (variant R16).
  - Invoice presence (rubric 13, 14, 33, 34), operational definition: an invoice is present
    when a line of its vendor (names normalised for case, spacing and company suffixes)
    carries its exact amount as the addition of its invoice month, or as the line's original
    amount; a consolidated vendor line with one addition per month satisfies several invoices
    (the expert's single BCBS line carries the four monthly invoices). A line of the vendor in
    the invoice month with a different amount is a wrong amount (14/34), not an omission.
  - Ending balances (23–26, 41–44) are read from the ending-balance row, else the totals
    row, else the sum of the lines; a labelled rounding adjustment row that closes the
    difference to the GL is applied (rule (b)); any other difference fails.
  - Rubric 22/40 compare the amortization and ending totals with the sums of the lines
    (additions are not named by the text; variant R02).
  The catalog (`grading/gold_variants_7d7fc9a7.py`: 20 rubric-relevant corruptions and
  transitions, 15 neutral layouts incl. one-row headers, header synonyms, extra columns,
  title rows, label variants, "$" formats, no beginning-balance column) lands on its declared
  maps; formula-dependent cases (summary linkage) run through LibreOffice when the docker
  path is free.
- Amendments after Codex Review 1 (2026-11-01; grader 7d7fc9a7-2026-11-01.2; review
  `logs/shared-core-review-wm_mg0v2/review.md`; no model output of this task had been graded or
  opened, nothing to re-grade). Grading rules unchanged; implementation brought in line with them:
  - Evidence states (B2). Old implementation: an unreadable cell (formula without a cached
    value) was summed as zero, treated as an absent figure, or skipped; an ambiguous month
    column took the first candidate; rows with figures but no vendor were dropped as notes.
    Evidence it was wrong: Codex B2 and gold variants R23-R28 (each gave a model FAIL or a PASS
    on the pre-fix code). New implementation: cells are ok / blank / unreliable / invalid;
    a blank cell is zero in schedule arithmetic (the spreadsheet's own evaluation) and an
    absent figure where a figure must be shown; unreliable cells, ambiguous month columns or
    bottom rows and unmapped or ambiguous vendor columns make the dependent items
    `cannot_assess` (grader side); rows with figures but no vendor are unidentified rows that
    bound the confirmed missing-invoice count (as in 1137 2.4) and turn an unexplained totals
    difference into `cannot_assess`; independently confirmed violations still FAIL.
  - Summary identity (B3). Old implementation: a summary figure was located by searching for
    the expected value first. New: each summary figure's account and measure are read from its
    row label and the heading above it (1250 / expense, 1251 / insurance; balance, amortization,
    additions; a labelled total balance naming no single account is the total); the value is
    compared only afterwards; no labelled candidate with every figure identified as another
    measure is a confirmed absence, unrecognised labels give `cannot_assess`, several labelled
    candidates with different values give `cannot_assess` unless all differ from the target.
    Regression: R22 (B9 / B14 amounts exchanged under unchanged labels fail 8 and 9).
  - Rubric 53 (B4). Old implementation: 53 failed only when more than 10 % of the schedule
    amount cells lacked the format - an allowance neither the rubric nor the operational
    definition above grants. New: every nonzero monetary cell (schedule lines, bottom rows,
    summary figures) must carry a currency symbol or a two-decimal thousands format; blank or
    zero cells carry no amount and are not tested; an unreadable figure with a non-currency
    format gives `cannot_assess`. Regression: R21 (one General-formatted invoice amount fails 53).
  - Item contract (B1): every deterministic item row carries weight, criterion, dependencies;
    the production `grade_run` path is pinned by an integration regression (judge disabled).
  - Catalog scope (P1): expectations cover deterministic items only; N11 (lines sorted by
    amount) is D-neutral only - judge-only item 17 (organised by vendor) is expected to change.
  The expert workbook's deterministic verdicts are unchanged (39 of 41 pass; 10 and 30 fail
  as before, A-10b / A-30); C2 keeps rubric 30 (decided 2026-11-01).

### 2.8 `2ea2e5b5-257f-42e6-a7dc-93763f28b19d` — Work-time study deck (CIS Managers)
Inputs: `Work Time Study - Source.xlsx` (15,918 rows; labels "Audit / Compliance" (546
rows) and "Break/ Fix" (1,738 rows) carry extra spaces; no categories outside the
twelve). Deliverable: .pptx with five slides (title; activity analysis; margin impact;
time sensitivity; strategic level), each analysis slide with a table and a pie chart.
Rubric: 60 items, weight 85.

Recomputed: total 44,258.685 hours. Shares: Audit/Compliance 1.91 %, Automation 8.40,
Break/Fix 11.65, Change Management Meeting 3.67, Deployment of Upgrades 6.77,
Develop/Integrate Tooling 8.99, Patching 7.86, Problem Management 11.09, Process
Improvement 6.03, Service Request 27.73, Shift Handover Meeting 2.06, Training 3.84.
Segments: Cost 57.98 / Investment 42.02; Time High 11.65 / Medium 75.69 / Low 12.66;
Strategic High 25.53 / Medium 48.20 / Low 26.27.

Numeric rule for this task (APPROVED): percentages compared within the tolerance each
rubric item states (±0.20 or ±1.0 percentage points); totals of percentages checked
with the rubric's own tolerance; hours compared at two decimals (half-up).

- C1 Deck structure (APPROVED 2026-10-30). Requirement: exactly five slides with the required titles;
  each analysis slide has a table and a pie chart (rubric 1–7, 57–60). Check: D on the
  package (slide count, chart parts — `pieChart` or `pie3DChart` both count — table
  shapes). Not compensable: the deliverable form.
- C2 Activity shares (APPROVED 2026-10-30). Requirement: all twelve shares within rubric tolerance,
  summing to 100 within tolerance (rubric 8–26). Check: D on table text and chart XML
  values. Not compensable: the source-to-summary step.
- C3 Classification (APPROVED 2026-10-30). Requirement: segment membership exactly as the prompt
  defines and segment shares as recomputed (rubric 27–56). Check: D. Not compensable:
  the prompt states the classification rule explicitly.
- D: 1–56 (tables and chart XML); J: 57–60 if titles need semantic matching; V: slide
  rendering (no explicit formatting item in this rubric; visual check is recorded but
  not scored).
- A-8. Rubric text: "The Activity Analysis table includes the following 12 categories as
  distinct rows or columns: Audit / Compliance; Automation; Problem Management; Process
  Improvement; Deployment of Upgrades; Patching; Break/Fix; Training; Develop/Integrate
  Tooling; Service Request; Change Management Meeting; Audit/Compliance; Shift Handover
  Meeting." Independent result: the list holds thirteen entries because Audit/Compliance
  appears twice (once with the source's spacing); the source holds exactly twelve
  categories after whitespace normalisation. Adjudication: the twelve prompt categories;
  "Audit / Compliance" and "Audit/Compliance" are one category; label whitespace is
  normalised before matching. Rationale: duplicate entry is a rubric typo; the prompt
  lists twelve. Scoring effect: a table with twelve rows passes; a table that keeps the
  source's two spellings as separate rows fails item 8 and the affected share items.
  Status: APPROVED.
- K1 (class a): rubric 10 asks for total hours per category; the gold table shows
  percentages only (gold would fail 10). Rubric governs.
- K2: the gold uses `pie3DChart`; 2D and 3D pie chart parts are both read and accepted
  (section 1.9).
- A-9 (rubric 34, 55, 56; APPROVED by the human 2026-11-01, Option A; recorded before any
  Task 3 development output is opened). Rubric text: the total hours represented in the
  Margin Impact / Time Sensitivity / Strategic Level table equal the total hours
  represented in the Activity Analysis table. Interpretation: compare each segment table's
  total hours with the total hours the Activity Analysis table represents. Where the
  Activity table prints a clearly identifiable hour total, that printed total is used
  (these items test consistency between the tables, not correctness against the source,
  which other items cover). Where it shows percentages only, its represented hours are
  derived from the source data, provided category coverage, denominator and mapping are
  unambiguous and independently verifiable (every row maps to exactly one source category,
  no duplicates, and the printed shares agree with the source shares over the covered
  categories within the rubric's ±0.20 point tolerance); percentages summing to 100 % alone
  do not establish the hours. A segment table's total is its printed hour total when one
  is identifiable, otherwise the sum of its readable hour cells, otherwise derived the
  same way. When either side cannot be determined reliably the item is `cannot_assess`;
  the expert value is never assumed. Hours are compared at two decimals (half-up). Item 10
  keeps its separate requirement to display hours; items 34, 55 and 56 are not failed for
  the same missing display when the independently verifiable hours agree. Rubric
  requirements and the C3 composition are unchanged.

### 2.9 `c357f0e2-963d-4eb7-a6fa-3078fe55b3ba` — UAT test plan (CIS Managers)
Inputs: `UAT Plan - Template.xlsx` (one sheet; row 1 holds the title "UAT Test Plan",
row 2 the headers: Test No., Role, Module, Source Event (user Action), Test scenario,
Other Conditions/Notes, Expected Result, Actual result, Tested Date). Deliverable: .xlsx
test plan with 80–100 cases by role and module, Actual Result and Tested Date blank.
Rubric: 70 items, weight 101.

Naming and semantics are graded separately (APPROVED): items that demand exact labels
(12, 13) are checked by label; permission coverage and expected results (49–58 and the
module-coverage items) are checked by the meaning of the row. "System Administrator",
"System Admin" and "Sys Admin" describe the same role for permission correctness; the
label items still record the naming deviation. Both results are reported: naming
compliance and permission correctness.

- C1 Plan structure (APPROVED). Requirement: template headers present (row 2 accepted,
  A-2); 80–100 counted cases; Actual Result and Tested Date blank on every counted row;
  Role, Module, User Action, Scenario, Expected Result populated (rubric 2–11). Check: D.
  Not compensable: the template must circulate as-is. The 80–100 range is retained; the
  gold's 75 cases do not lower it (K1).
- C2 Permission boundaries (APPROVED). Requirement: cases for all four roles including
  Viewer view-allowed / edit-denied / create-denied, Project Manager own-allowed /
  other-PM-denied, System Admin own-organisation allowed / other-organisation denied,
  Super Admin cross-organisation allowed (rubric 12, 49–58). Check: J with the prompt's
  permission outline as source, by meaning (above). Not compensable: the explicit
  business rule set.
- C3 Module and negative coverage (APPROVED 2026-10-30). Requirement: cases for Idea, Proposal (incl.
  Business Case sub-fields), Project (both types), Programs, System Administration,
  IRAD, each with at least one mandatory-input-missing case where the rubric asks
  (rubric 13, 15–21, 31, 35–37, 45–48, 59–63). Check: J. Not compensable: coverage is the
  plan's purpose.
- D: 1–11, 14, 67, 68, 69 (counts, blanks, headers, date format, wrap/width);
  J: 12, 13, 15–66; V: 70.
- A-2. Rubric text: "Workbook contains a worksheet whose first row includes,
  case-insensitive, these headers: Role, Module, User Action, Test Scenario, Expected
  Result, Actual Result, and one date header equal to one of: Tested Date, Execution
  Date, or Date." Independent result: the task's own template places a title in row 1
  and the headers in row 2. Adjudication: headers in row 2 (the template's layout) or
  row 1 both pass; the header set is checked wherever the header row is. Rationale: the
  prompt requires building on the template; penalising the template's own layout would
  contradict the task. Scoring effect: item 2 passes for either row. Status: APPROVED.
- K1 (class a): the gold has 75 counted cases, role labels "All", "Sys Admin", "Super
  User" and module labels that do not match the rubric's exact names, and a
  General-formatted date column; it would fail rubric 4, 12, 13, 67. Rubric governs; the
  gold is used only to calibrate what a reasonable scenario looks like.
- K2: rubric 67 requires an Excel date type on blank cells; checked via the cells'
  number format.

### 2.10 `a45bc83b-22f9-4def-8d89-9c5661b2b86f` — GCP migration design (CIS Managers)
Inputs: `Current_Architecture.pdf` (one-page diagram: user → NGFW → DNS → load
balancer → web server → app server → SQL Server; Redis user profiles),
`Current_Architecture_Summary.docx` (8 bullets). Pre-staged resources (fetched
2026-10-29 UTC, hashes in `data/manifest.json`): the icons page and three official icon
packs (category 130 entries, core products 89, legacy 432), and the ten listed pages
(all HTTP 200, 664–8,423 words of article text; `cloud.google.com/docs` redirects to
`docs.cloud.google.com/docs`). Deliverables: Proposed Architecture Summary .docx
(bulleted), Proposed Architecture .pdf diagram with official icons, POC Implementation
Guide .docx with step-by-step instructions. Rubric: 72 items, weight 87. Design task;
no cloud resources are created.

Requirement layers (APPROVED 2026-10-30):
- Layer 1, prompt hard requirements (business): easily scalable; modernised web and
  application servers; static content hosting; Layer 3 and Layer 4 DDoS protection;
  enterprise-grade security and availability; data flow documented in the summary;
  diagram with official GCP icons; POC with ordered steps and purposes.
- Layer 2, rubric-specific service requirements (items 6–13): Global External HTTP(S)
  Load Balancer at the ingress; Cloud Armor policies on that load balancer (or Google
  Front End protections cited with Cloud Armor); Cloud CDN enabled on the load
  balancer; static assets in Cloud Storage integrated with Cloud CDN; application tier
  on a managed platform (any of Cloud Run, GKE, App Engine, Compute Engine MIG) with
  autoscaling; managed database (Cloud SQL, Firestore, or AlloyDB); compute in a
  multi-zone or regional configuration (rubric 13).
- Layer 3, allowed design differences (not errors): the choice among the platforms and
  databases the rubric lists; additional services (Cloud DNS, Memorystore, Secret
  Manager, VPC design, IAM, logging); treatment of the NGFW and Redis components;
  organisation and ordering of the documents; migration sequencing.

- C1 Deliverable set (APPROVED 2026-10-30). Requirement: the three files in the required formats,
  summary in bullets, POC with ordered steps (rubric 1–3, 5). Check: D. Not compensable:
  the customer review needs all three.
- C2 Hard requirements met as an architecture, consistently (APPROVED).
  Requirement: every Layer 2 service is present AND placed in the relationship the
  requirement implies — Cloud Armor attached to the external load balancer that fronts
  the application; Cloud CDN enabled on that load balancer's backend; Cloud Storage as
  the CDN's static origin; the application platform behind the load balancer with an
  autoscaling policy stated; the managed database reached from the application tier;
  multi-zone or regional placement stated for the compute — and the same primary
  services appear
  in the summary, the diagram, and the POC without contradiction (rubric 6–13, 49).
  Check: J on extracted text with the Layer 1 and Layer 2 lists as source, with the
  judge required to cite, per service, the sentence or step that establishes the
  relationship, not only the service name; D for service-name presence as support only;
  human review confirms. Mentioning a service without its role or relationship does not
  satisfy the item. When a Layer 2 requirement is not met, the specific rubric compliance
  failure is recorded (item number, what is missing); separately, whether the design has
  an architectural functional error is judged from the Layer 1 business requirements and
  the actual design evidence: it is not asserted merely because the specified service was
  not used, and it is not denied automatically either. Not compensable: Layer 1 is the
  customer's stated business requirement set; Layer 2 is the rubric's concrete service
  requirement set.
- C3 Diagram (APPROVED 2026-10-30). Requirement: official GCP icons; depicts Armor at ingress, CDN at
  the load balancer, the app platform, the database, Storage as static origin (rubric 4,
  26–30). Check: V against the pre-staged icon packs; D for page count and text labels.
  Not compensable: the diagram is one of the three deliverables.
- POC executability (APPROVED; feeds rubric 3, 31–48 as applicable): steps are ordered;
  each step names the resource it creates or configures and the purpose where not
  obvious; no step depends on a resource that no earlier step created unless the POC
  explicitly declares it as a prerequisite or an existing resource; the services in the
  POC are the ones in the summary and the diagram. Judge
  and human check these properties; a list of service names is not a POC.
- D: 1–3, 5 (formats), service-name presence as support for J; J: 6–25, 31–71 (presence,
  relationships and consistency; Layer 3 differences are not errors; items are graded on
  whether the design establishes the thing, not on whether it matches the gold); V: 4,
  26–30, 70, 72.
- K1: open-ended task; organisation different from the gold is not an error.
- K2: the gold diagram uses a non-GCP icon for "Users / Website"; irrelevant to grading.
- Deterministic rules of grader v0 (2026-11-01; operational detail of C1, for human review at the labeling
  checkpoint): document identity from the file name, else the opening text (summary: "summary" / "proposed
  architecture"; POC: "POC" / "proof of concept" / "implementation guide"); with exactly two .docx files and one
  identified, the other takes the remaining role; a file matching both roles or several unidentified files leave the
  role unknown (`cannot_assess`, never `fail`). Item 2 needs a readable PDF with graphic content (vector drawings or an
  embedded image); a text-only PDF fails. Item 3 needs ordered steps: at least three numbered list paragraphs or three
  paragraphs opening with "Step <n>" (bullets are not ordered steps). Item 5 needs at least three bullet paragraphs (Word
  bullet numbering, a "List Bullet" style or a typed bullet glyph) making up at least half of the summary's non-empty,
  non-heading paragraphs. Expert deliverables: 1, 2, 3, 5 pass.
- Item 70 (DECIDED by the human 2026-11-01, recorded before any Task 10 development output is opened): human visual
  review is authoritative and the criterion is scored once, as a V item. The judge also assesses item 70 (summary text
  and the diagram's text labels as evidence) whenever a separately authorized judge batch runs; that verdict is used
  only for judge-human agreement, never for scoring. Grader a45bc83b-2026-11-01.2.
- DECISION (APPROVED 2026-10-30): the pre-staged resources enter the sandbox as the HTML
  snapshot plus the extracted text of each page plus the icon-pack zips (not pre-extracted),
  identical for both models: 2 task inputs + 11 HTML + 11 text + 3 zips = 27 files under
  `/workspace/inputs` and `/workspace/resources/{pages,icons}`. The per-file SHA-256 list
  of all 27 staged files is recorded in `config.json` (`pre_staged_resources.files`);
  automatic verification at staging time is Stage 3b item I1.

---

## 4. Decisions still needed from the human before freeze

- 2026-11-01, `b5d2e6f1…` A-1 (OPEN): whether a figure-less "(blank)" pivot row counts as an extra (store, brand) row
  under rubric 14 (literal reading: fail, and C3 fails for the expert) or is an empty pivot group (grader v0's
  provisional rule). Section 2.1.

- 2026-11-01, `a45bc83b…` item 70: DECIDED the same day by the human - human visual review is authoritative, the
  criterion is counted once; the judge verdict on it is used for judge-human agreement only (section 2.10).

- 2026-11-01, `7d7fc9a7…` C2 composition: DECIDED the same day by the human - rubric 30 stays
  in C2 as preregistered. The requirement includes monthly GL Balance and Variance checks for
  January-April 2025 with the variance equal to 0.00; correct account balances alone do not
  satisfy it when the monthly reconciliation evidence is missing. The expert failures on 10 and
  30 remain documented data-quality findings (A-10b, A-30); the critical composition and the
  rubric are not relaxed. Recorded before any development output of the task was opened.

- 2026-11-01, `1137e2bb…` rubric 9 and 5–8: DECIDED the same day (rule recorded in
  section 2.4: item 9 numeric 0/1 only; 5–8 and 18–20 coerce unambiguous representations;
  no cascade).

1. Critical criteria: closed. 17 of the 18 criteria listed as PENDING were APPROVED on
   2026-10-30 as written (f841ddcf C3–C5; 47ef842d C1, C4; 1137e2bb C1, C3; c3525d4d
   C3; 7b08cd4d C1–C3; 2ea2e5b5 C1–C3; c357f0e2 C3; a45bc83b C1, C3); 1137e2bb C2 was
   APPROVED on 2026-10-30 with the revised text in section 2.4 (drill-down to PO leaves
   the critical core and stays a rubric-14 item). Every critical criterion now carries
   APPROVED status.
2. 2.2 per-item precision list: reviewed 2026-10-30 against the rubric text; the general
   principles and all listed entries are APPROVED with their basis recorded in the table.
3. 2.1 C3 and 2.10 resource form: APPROVED 2026-10-30 and recorded in sections 2.1 and
   2.10 (structural PivotTable determination; HTML + text + zip snapshot with per-file
   hashes in `config.json`).
4. 1.13 (substitutes and fallbacks): APPROVED 2026-10-30 as written.
5. 3.7 (`7d7fc9a7…`), rounding policy at the rubric and critical level (registered
   2026-10-30; APPROVED 2026-10-30 as the "Reconciliation and rounding rule" recorded in
   section 2.7: reconcile to the cent passes; a quantified, re-performable bridge that
   closes a difference to the GL passes; a textual rounding note alone fails; an
   undisclosed difference fails; items 23–26, 30, 41–44, 48 graded on their own text).
   The question as registered: how a deliverable that rounds each invoice's monthly
   charge to cents before accumulating is treated. Task requirements checked: the prompt says "Use the GL
   balances below to ensure your schedules reconcile to the end of month balances" and
   "confirm that all figures reconcile accurately", and states no rounding rule; rubric
   items 23–26 and 41–44 require each monthly ending balance to equal the GL balance
   "(rounded to the nearest cent)"; items 30 and 48 require the variance to equal $0.00
   "(rounded to the nearest cent)"; items 21/39 require the per-line identity and items
   22/40 require the totals to equal the sum of the lines. The recalculation shows that
   per-line cents rounding ends −0.01 to −0.05 from the GL in every month on both
   accounts. Open: whether such a deliverable fails items 23–26, 30, 41–44 and 48 as
   written (variance not 0.00), and whether the critical status under C2–C4 follows from
   that or treats the method as a documented policy difference. The alternative figures
   that `scripts/recalc/task_7d7fc9a7_prepaid.py` lists for that variant document the
   drift; they are not allowed values.
