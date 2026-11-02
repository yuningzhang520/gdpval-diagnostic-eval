# Dataset proposal: what a better GDPval-style dataset would need to contain

Draft scaffold, 2026-11-02. It uses the placeholder conventions of `report/REPORT.md`: `{{FORMAL: ...}}` and
`{{PENDING: ...}}`.

**Scope of the evidence.** Sections 2-4 rest only on non-Formal work:
- the stage-1 material checks and independent recalculations from the task inputs;
- the adjudication records in `preregistration.md`;
- the expert-gold FAIL audit (`docs/expert_gold_fail_audit.md`);
- grader calibration on the Gemini development and validation outputs (`docs/status.md`).

Evidence from the candidate (Formal) runs goes into section 6 once those results are unsealed. The ten tasks are 10
of the 220 public gold tasks, and nothing here is claimed about the other 210.

## 1. Summary

- **Task materials.** In 9 of the 10 tasks, the material check recorded at least one input, expert-deliverable or
  rubric finding that needed a decision before grading (`docs/status.md` "Known issues and findings"). The tenth,
  `a45bc83b…`, recorded none.
- **Expert deliverables.** For 7 of the 10 tasks, the expert-gold audit lists a preregistered critical criterion that
  the expert deliverable fails, or leaves unresolved, under the rubric as written (`docs/expert_gold_fail_audit.md`
  section 1). Judge and visual items were not assessed for the expert deliverables, so this count covers the
  deterministic side only.
- **Repeatable classes.** The findings fall into a few classes (section 2):
  - expert deliverables inconsistent with their source or prompt;
  - rubric figures copied from the expert deliverable;
  - rubric items beyond or against the prompt;
  - under-specified operational definitions;
  - one dataset artifact (re-identified ids);
  - an unused schema field;
  - candidate tasks with incomplete inputs.
- **Proposal.** Release each task as a verified task package (section 4):
  - complete inputs;
  - an executable reference computation;
  - a typed rubric whose items name the prompt clause they enforce and their evidence location;
  - an expert deliverable checked against both;
  - a grader-validation variant set;
  - blind human labels.
- {{FORMAL: one sentence linking the human-verified candidate failures to the package elements that would have
  caught or trained against them}}

## 2. Issues found in the GDPval v2 materials (non-Formal evidence)

| Class | Task | Finding | How this evaluation handled it | Source |
|---|---|---|---|---|
| Expert deliverable inconsistent with its source | `b5d2e6f1…` | The expert "Data" tab differs from the input in 557 cells: 234 category relabels and 323 stock-on-hand edits, all on rows where source stock is below the period's sales. Brand totals differ from the source sums (e.g. Shiseido MTD SOH +30,654). Neither an expert edit nor a different input version can be ruled out | The source is the reference. Reported as unresolved | `docs/status.md` "Independent re-check", "Known issues"; audit §1 |
| Expert metric differs from the rubric's | `b5d2e6f1…` | The expert ST% is the pivot average of row ratios (Clinique WTD 0.2467); the rubric's ratio of sums gives 0.2309 | Ratio of sums governs (C4) | audit §1 |
| Expert narrative mislabels a metric | `f841ddcf…` | The narrative states 145,219 as shipped, which is the June order value; the recomputed June shipped total is 140,008.20 over 48 POs. "13,248" is the slipped POs' shipped value, not their PO value (13,300) | Narrative figures are graded by the metric they name | `docs/status.md` "Known issues"; audit §1 |
| Rubric requires structure the expert omits | `f841ddcf…` | Rubric items 5-21 describe PO-level tables; the expert gives account-level summaries only | PO-level evidence is an original requirement (C2) | `preregistration.md` 2.2; audit §1 |
| Rubric copies an expert error | `47ef842d…` | Rubric and expert store counts 729 / 1,223; the input has 728 / 1,222 distinct stores, with no duplicates and no blanks | Graded against the source (A-31, A-52) | `docs/status.md` "Independent re-check" |
| Prompt references a field that does not exist | `47ef842d…` | The prompt defines active stores via an "out-of-stock percentage" field that is not in the data | Operational definitions fixed before any output (OOS := Current Week Inv = 0) | `preregistration.md` 2.3 |
| Rubric beyond the prompt | `1137e2bb…` | Item 21 asks for a missing-case-pack indicator the prompt does not ask for, and the data hold no blank or non-positive case pack | Graded as written, excluded from critical (A-21) | audit §2 |
| Rubric beyond the prompt | `2ea2e5b5…` | Item 10 asks for Total Hours per category; the prompt asks only for a table and a pie chart | C2 revised (R-2.8-1); both definitions reported | audit §1; `preregistration.md` 1.18 |
| Criterion text conflicts with its item list | `7b08cd4d…` | C1 says "rates applied per country"; its items 16-17 require per-stop withholding. The expert meets the text and fails the items | Kept (decision 2026-11-01); disclosed | audit §1, §5 |
| Rubric encodes an undefined split | `7b08cd4d…` | The expense-category allocation is not defined by the prompt; the rubric encodes the expert's split. Rounded rubric figures do not add up (120,423 vs 120,422) | Identities checked unrounded (A-53); allocation classified before reporting | `docs/status.md` "Known issues" |
| No rounding rule | `7d7fc9a7…` | The prompt asks for reconciliation to the GL but states no rounding rule. Per-line cent rounding drifts −0.01 to −0.05 per month; exact accumulation reconciles to the cent | Reconciliation and rounding rule (`preregistration.md` 2.7) | `docs/status.md` "Independent re-check" |
| Expert omits required checks | `7d7fc9a7…` | The expert summary has no total prepaid balance (item 10, 929,354.31) and no per-month variance checks (item 30), although its numbers reconcile | Standard kept (A-10b, A-30) | audit §1 |
| Rubric contradicts the template | `c357f0e2…` | Rubric 2 places the headers in row 1; the template has them in row 2 | Either row accepted (A-2) | `docs/status.md` "Independent re-check" |
| Expert below the rubric's range | `c357f0e2…` | 75 test cases against a rubric range of 80-100 ("approximately" in the prompt); 20 counted rows have no expected result; the date column is General-formatted | Range applied literally (item 4) | audit §1-§2 |
| Dataset artifact | `c3525d4d…` | The expert store list holds 1,257 six-digit ids with no overlap with the input. 26 "CAPITAL PLAN" notes sit in the same row positions, and the substitution is not order-preserving (49.9 % concordance) | Classified as a dataset artifact; items 6 and 32 not charged to the expert | audit §3 |
| Input type mismatch | `c3525d4d…` | Store ids are integers in one list and 4-character text with leading zeros in the other. 610 match raw, 1,226 after normalisation | Normalised comparison | `docs/status.md` "Known issues" |
| Rubric duplicate and label noise | `2ea2e5b5…` | Rubric 8 lists 13 entries (one duplicate); the source labels carry stray spaces | Label normalisation (A-8) | `docs/status.md` "Known issues" |
| Unused schema field | all | `rubric_json.form_content` is null in 8,036 items and absent in 2,417, with no value in any of the 10,453 items | Not used | `docs/status.md` "Known issues" |
| Task not usable offline from its inputs | excluded candidates | The audit-sampling task's rubric contradicts itself and its prompt on columns. The month-end task names `AP_TB-1.xlsx`, which is missing from its 17 reference files. Several tasks have no reference files or need the open web | Not selected | `preregistration.md` section 2 |

## 3. What grader development showed about rubric specification (Gemini outputs, non-Formal)

- **Layout.** Deliverables that meet the same requirement take very different shapes:
  - headings in text boxes instead of title placeholders;
  - charts delivered as pictures;
  - duplicate totals rows, and split tables;
  - a second table below a list;
  - uncached formulas.

  Calibration on the Dev outputs changed 122 of 396 deterministic verdicts between grader V0 and V1. On held-out
  Validation, deterministic agreement with the human was 4/6, and both misses were layout-reading defects (`docs/status.md`).
  A rubric item that states its evidence location and the forms it accepts would reduce this ambiguity.
- **Literal or by meaning.** Some items are literal labels (`2ea2e5b5…` item 27, "Margin Impact"; `c357f0e2…` items
  12-13), while others are judged by meaning (`c357f0e2…` items 49-58, permissions). The rubric does not say which
  reading applies. This evaluation had to decide it per item.
- **Judge evidence.** Both first-pass Dev judge disagreements came from an evidence excerpt that missed the
  deliverable's real headings, not from the judge prompt (`docs/status.md` "Dev labels saved and compared"). Judge
  items need a defined evidence scope.

## 4. Proposed contents of a verified task package

| Element | Contents | Motivating evidence (section 2-3) |
|---|---|---|
| 1. Complete, typed inputs | Every file the prompt names is present and hash-pinned, with a data dictionary of field types (for example, store ids as text with leading zeros) | missing `AP_TB-1.xlsx`; `c3525d4d…` id types |
| 2. Executable reference | Scripts that compute every rubric figure from the inputs, with a declared numeric policy (precision, rounding mode, quantization point) and the outputs | `7d7fc9a7…` rounding; `7b08cd4d…` rounded totals; `47ef842d…` counts |
| 3. Operational definitions | An explicit definition for every term the deliverable must compute, written into the prompt or a task annex | `47ef842d…` OOS and active store; `7b08cd4d…` allocation |
| 4. Typed rubric | Each item carries: the prompt clause it enforces, or a "beyond prompt" flag; its route (deterministic, judge or visual); its evidence location and accepted forms; its tolerance; its dependencies; a literal or by-meaning flag; and a critical flag with its business rationale. Expected values come from the reference, not the expert file. `form_content` is populated or removed | §2 rubric rows; §3 |
| 5. Verified expert deliverable | Checked against the reference and the rubric before release, with a published defect list. Never the value source for rubric figures | `b5d2e6f1…`, `f841ddcf…`, `47ef842d…`, `7d7fc9a7…`, `c357f0e2…` |
| 6. Grader-validation variants | Seeded corruptions and layout transformations of the expert deliverable, with declared item-level verdict transitions | this project's catalogs (for example 51 variants for `1137e2bb…`, 43 for `7d7fc9a7…`); §3 layout defects |
| 7. Visual evidence protocol | Page and slide renders, the visual items listed, and a human-verdict procedure | 18 visual items in the ten tasks; picture charts |
| 8. Blind human labels | Item-level labels from verdict-free packets, with hashes and timestamps, split into calibration and held-out sets | queue v4 design (36 labels) |
| 9. Adjudication records | A five-field record (rubric text, independent result, adjudication, rationale, scoring effect) for every rubric-input conflict | `preregistration.md` 1.1 |
| 10. Artifact checks | Automatic checks that the expert files and the inputs share identifiers, units and versions | `c3525d4d…` re-identified ids; `b5d2e6f1…` edited Data tab |

## 5. Use for evaluation and for training

- **Evaluation.** With elements 1-6, the rule-execution and consistency items can be graded deterministically and
  reproducibly, and critical status can be reported per criterion. Element 8 gives a measured reliability for the
  judge-graded rest.
- **Training** (a proposal, not tested in this project). Tasks whose figures follow from an executable reference
  (element 2) allow outcome checks that need no model judge. The critical tags (element 4) allow weighting by business
  impact. The variant sets (element 6) give labelled negative examples. {{FORMAL: which observed failure classes this
  would target}}

## 6. Formal-derived evidence (placeholders)

- {{FORMAL: human-verified critical failures per error class and task, mapped to the package element that addresses
  each}}
- {{FORMAL: the share of candidate failures on items with a section-2 confound, against items on clean task
  material}}
- {{FORMAL: failures common to both candidates, and failures specific to one}}
- {{FORMAL: 2-3 short case examples with evidence locations}}

## 7. Audience notes for the live pitch (placeholders)

- OpenAI researcher. GDPval is OpenAI's own benchmark. Documented basis: the v2 material findings in section 2 and
  the protocol difference from pairwise preference. {{FORMAL: results on `gpt-6.1-sol` relevant to this audience}}
- Anthropic researcher. {{FORMAL: results on `claude-opus-5-5` relevant to this audience}}

## 8. Cost and effort

- **Measured in this project** (ledger settlements; `docs/status.md`): building the grader-validation layer for ten
  tasks used 20 Gemini generation samples, at 22.255219 USD (Dev) and 17.488478 USD (Validation), plus Judge Dev at
  11.636271 USD.
- {{PENDING: human hours for the material checks, adjudications and labels (not recorded)}}
- {{PENDING: estimated effort per verified task package, labelled as an estimate}}

## 9. Limits of this proposal

- Ten tasks, chosen purposively; the rate of defects in the other 210 tasks is unknown.
- The findings rest on this project's recomputations and on one author's adjudications. No domain expert reviewed
  them.
- Judge and visual items of the expert deliverables were not assessed.
- The training uses in section 5 are proposals and were not tested.
