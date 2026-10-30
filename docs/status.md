# Status

Current stage: **Stage 1 complete — materials downloaded and verified, rules drafted and
revised after an independent re-check (2026-10-29 and 2026-10-30).** Awaiting the human's decisions on the
items marked PENDING in `preregistration.md` section 4 before the toolchain-validation
stage. No model, judge, or paid API call has been made. Stage 1 is recorded in the first
commit on `main`.

## Done (2026-10-29)

- Project environment: `pyproject.toml` + `uv.lock` (Python 3.11.4, uv 0.12.1);
  dependencies limited to reading, downloading, and checking materials (pyarrow,
  huggingface_hub, openpyxl, python-docx, python-pptx, pymupdf 1.x, requests,
  beautifulsoup4). `.venv/` is ignored.
- Dataset provenance: local parquet sha256
  `f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202` moved to
  `data/gdpval.parquet` (hash identical before and after). It matches exactly one
  commit of `openai/gdpval`: `11e7900cdcac61bc4daf59e65feb238acda98fbf` (2026-02-10,
  "Release GDPval v2 (rubrics + deliverables)", also the current head). All later
  downloads use this fixed revision (`data/dataset_revision.json`).
- Task selection resolved from the pre-declared prefixes to full UUIDs
  (`data/selected_tasks.json`); the deep group is the complete Order Clerks block.
- Downloads at the fixed revision: 18 inputs → `data/inputs/<uuid>/`, 14 expert
  deliverables → `private/gold/<uuid>/`, 10 rubrics (byte-for-byte) →
  `private/rubric/<uuid>.json`, 10 prompts → `data/prompts/<uuid>.txt`. Every file
  verified against the hash Hugging Face records (5 by LFS sha256, 27 by git blob
  sha1); log in `data/download_verification.json`; manifest in `data/manifest.json`
  (67 entries; 580 rubric items computed from the files).
- GCP pre-staged resources for `a45bc83b…`: 11 listed URLs fetched (all HTTP 200, real
  article text) plus 3 official icon packs discovered on the icons page (zip integrity
  checked, SVG/PNG counts recorded). Stored under `data/resources/<uuid>/` (ignored),
  recorded with URL, fetch time, size, sha256 in the manifest. No gaps.
- `.gitignore` covers `plan/`, `private/`, `.env`, `.venv/`, `logs/`,
  `data/gdpval.parquet`, `data/inputs/`, `data/resources/`, `data/prompts/` (rebuilt from
  the parquet), `.DS_Store`, and the two third-party PDFs kept locally (take-home brief,
  GDPval paper; README links to the public sources). `data/manifest.json`, the other
  `data/*.json` records, scripts and the lock file are tracked (verified with
  `git check-ignore`).
- Material check per task (structure dumps in `private/checks/materials/`, PDF renders
  in `private/checks/renders/`) and recalculations from the source files for the eight
  numeric tasks (`scripts/recalc/`, outputs in `private/checks/recalc/`); every rubric
  figure reproduces from the inputs under the rules now recorded in
  `preregistration.md`. Re-check scope: four of the eight tasks were re-derived blind
  from the source files and reproduced the stage-1 figures; the conflicts identified in
  the sales-analysis (`b5d2e6f1…`) and inventory (`47ef842d…`) tasks were re-examined in
  detail. Corrections that followed are listed in the next section.
- Clean-clone rebuild path: `scripts/fetch_dataset.py` added (downloads the parquet at the
  recorded revision and checks its sha256; the existing scripts had no parquet download
  step). On 2026-10-30 the staged tree was exported to an empty directory and run with
  fresh uv and Hugging Face caches: `uv sync --frozen`, `fetch_dataset.py` (hash match),
  `resolve_tasks.py`, `download_materials.py` (32/32 files verified); the rebuilt
  `data/selected_tasks.json` and the ten prompt texts are byte-identical to the local
  copies. `data/prompts/` is therefore not tracked. Steps are in the README.
- Drafts: `PLAN.md` (methods), `preregistration.md` (task selection and exclusions,
  global rules, per-task critical
  criteria with status, deterministic checks, judge inputs, visual checks, findings,
  five-field adjudication records, open decisions).

## Independent re-check (2026-10-29 and 2026-10-30): findings and corrections

Each entry: what was found, the technical basis, what was changed.

- `scripts/recalc/task_7d7fc9a7_prepaid.py` accumulated the schedules in floats and
  reported balances and variances through Python `round()`. Basis: the GL balances are
  reproduced only by unrounded accumulation (March 1251 = 415,537.125 → 415,537.13);
  rounding each invoice's monthly charge first drifts −0.01 (Jan) to −0.05 (Apr) on both
  accounts. Change: Decimal arithmetic throughout, ROUND_HALF_UP to cents only at the GL
  comparison, per-line rounding variant kept only as documentation; rule recorded as the
  task's numeric policy.
- The global numeric conventions applied one tolerance (+/- 0.50 USD) and half-up rounding
  to every figure. Basis: rubric items state their own tolerances and quantization points
  differ by task (cents vs GL, whole dollars vs rubric, percentages with stated ranges).
  Change: tolerance and blanket rounding withdrawn; quantization method defined per task
  and per item (`preregistration.md` 1.7 and section 3).
- Rerunning the prepaid task under a 34-digit Decimal policy showed the total prepaid
  balance at 4/30 as 929,354.3049… (quantizing to 929,354.30), while rubric item 10
  states 929,354.31. Basis (re-check of 2026-10-30): the exact total is 185,870,861/200 =
  929,354.305; the Decimal division residue fell just below the tie. Exact rational
  arithmetic gives 929,354.31 under HALF_UP, and the sum of the two cent-quantized
  balances is also 929,354.31. Change: `task_7d7fc9a7_prepaid.py` rewritten with
  `fractions.Fraction` (amounts from invoice decimal text; HALF_UP quantization done on
  the rational; Decimal context rounding set explicitly; both total paths kept);
  regression test `scripts/recalc/test_7d7fc9a7_quantization.py` asserts
  q_cents(185870861/200) = 929354.31, the task's sum of quantized balances = 929354.31,
  the quantized-once total = 929354.31, and the April/March account balances; A-10 ruled
  on 929,354.31 with no exception; C4 approved for linkage and account balances.
- `47ef842d…`: the draft proposed accepting either 728/729 and 1,222/1,223 store counts.
  Basis: Store Number is text, each UPC has one row per store (no duplicates), so the
  distinct counts are 728 and 1,222; the rubric's 729 and 1,223 copy the gold. Change:
  rubric 31 and 52 graded against the source counts with five-field records (A-31,
  A-52); items 33 and 54 are unaffected under either denominator.
- `47ef842d…`: "-" appears only in "Avg Days On Hand" and exactly on the 5,531 rows
  whose daily sales are 0 (both directions); on every numeric row the column equals
  Current Week Inv / daily sales. Change: "-" fixed as "turnover not computable"; rows
  kept in every aggregate, never treated as zero inventory, never averaged; the three
  operational definitions (active store with its denominator, OOS, WOS with a
  zero-rate rule) written out and labelled as this evaluation's definitions. The
  recalc script records these rules and the dash/zero-sales coincidence.
- `c3525d4d…`: the draft stated that a raw string comparison yields no matches. Basis:
  610 of the final-list ids have no leading zero and match as strings; normalisation
  gives 1,226 common ids, 31 added, 2 removed. The gold's final tab holds 1,257
  six-digit ids with zero overlap and no derivable mapping (positional 4-digit
  substrings hit the input list at chance level, 74–173 of 1,257, non-unique). Change:
  both comparisons recorded with both sides named; recalc script reports them; the
  nearest-integer overage rounding is labelled an operational rule of this evaluation
  (A-24/25), not the task's or the author's rule.
- `b5d2e6f1…`: the gold's pivot data fields aggregate the three ST% fields with
  `subtotal="average"` (pivot XML), and the gold "Sales by Brand" ST% equals the mean of
  row-level ratios (Clinique WTD 0.24668 vs ratio of sums 0.23087). Basis: rubric 7–9,
  18–21 require ratio of sums and SUM aggregation. Change: recorded as a gold defect
  (K3); ratio-of-sums kept as the C4 reference; gold percentages not used for
  calibration. The gold's 557 changed Data cells are now split: 234 category relabels
  (no numeric effect) and 323 stock-on-hand edits, all on rows where the source stock
  is below the period's sales; the source holds more such rows than the gold edited.
- `f841ddcf…` (re-check of 2026-10-30): the "compared at the precision the deliverable displays"
  wording was withdrawn. Change: per-item precision list declared (rubric item, output
  location, exact and reference amount, allowed precision, rounding rule); table amounts
  at cents HALF_UP; narrative items allowing whole dollars listed one by one (37, 55, 56,
  57); the +/- 1 USD tolerance confined to item 55; whole-dollar figures must equal the
  HALF_UP result (truncations that differ fail; no inference about the algorithm when the
  value cannot distinguish them); numeric correctness checked on stored cell values,
  display format graded separately. The entries await review.
- `a45bc83b…` (re-check of 2026-10-30): C2, the three requirement layers and the POC rule approved
  with three edits: "multi-zone or regional configuration" (rubric 13); POC steps may rely
  on explicitly declared prerequisites or existing resources; non-compensability stated
  by layer, and an unmet Layer 2 item is recorded as a rubric compliance failure while
  any architectural functional error is judged separately from Layer 1 and the design
  evidence.
- `c3525d4d…` (re-check of 2026-10-30): recalc amounts moved to Decimal from the email's decimal
  text; A-24/25 now states that 1,289 units are inferred back from the email's total
  (22,802.41 / 17.69), since the email states no unit count. `b5d2e6f1…` K2 no longer
  says the source difference makes the gold fail rubric 6 and 10 (internal-consistency
  items).
- `f841ddcf…`: the draft treated the gold narrative's "$13,248" as a figure that would
  simply fail. Basis: 13,248 is the actual shipped value of the five slipped POs
  (recomputed), a correct figure for a different metric than rubric 36/37 name
  (PO value at cost, 13,300); "$145,219" is the June order value labelled as shipped.
  Change: three matters separated and graded independently (June amount with reference
  140,008.20 = half-up cents of 140,008.204; PO-level structure as an original
  requirement, missing → confirmed fail; PO membership evidence → `cannot_assess` only
  when just hard-coded account totals exist); auditable PO-level evidence made a critical
  criterion; rubric 5–21 graded item by item; narrative figures graded by the metric
  they name; recalc script extracts the drawing text box and the cents-quantized
  reference figures.
- `c357f0e2…`: rubric 2 says the headers are in the first row; the task's template has
  the title in row 1 and the headers in row 2. Change: A-2 accepts either row. Naming
  compliance (exact labels, items 12–13) and permission correctness (items 49–58, by
  meaning) are graded and reported separately.
- `7b08cd4d…`: identity checks moved explicitly to unrounded values with whole-dollar
  quantization only for rubric comparison (A-53); rubric 45's "Transfer cards" / "Other"
  labels matched to the source's "Car Service" / "Fees" by amount and party (A-45);
  allocation failures to be classified as misclassification vs documented alternative
  split before reporting.
- `2ea2e5b5…`: label normalisation now also collapses internal whitespace; the merged
  raw labels are recorded ("Audit / Compliance" → "Audit/Compliance", "Break/ Fix" →
  "Break/Fix"); 2D and 3D pie chart parts both accepted (A-8).
- `1137e2bb…`: rubric 21 recorded as A-21 (graded as written, not critical, disclosed).
- `a45bc83b…`: C2 rewritten with three requirement layers (prompt hard requirements,
  rubric-specific services, allowed design differences) and judge/human checks on
  architecture relationships, cross-file consistency and POC executability (approved in
  the re-check of 2026-10-30, see above).

## Known issues and findings (material check)

- `rubric_json.form_content`: 8,036 items hold `null`, 2,417 items lack the key, zero
  items hold a value (all 10,453; for the ten tasks: 293 null, 287 missing). Not used.
- `b5d2e6f1…`: gold "Data" tab differs from the source in 557 cells (see above); gold
  SOH totals differ from source sums for four brands (Estee Lauder WTD +9,816; Lancome
  MTD +11,154; Laura Mercier MTD +8,424; Shiseido MTD +30,654); gold ST% is an average
  of row ratios. Source is the reference (approved).
- `f841ddcf…`: recomputed June (48 POs, 140,008.204 shipped) and slipped (5 POs, PO
  value 13,300, shipped 13,248) match the gold tables; the gold narrative (drawing text
  box) states 145,219 and 13,248. Rubric items 5–21 describe PO-level tables the gold
  does not provide.
- `47ef842d…`: the prompt's "out-of-stock percentage" field does not exist; OOS :=
  Current Week Inv = 0 under this evaluation's definitions. Rubric/gold store counts 729
  and 1,223 are one above the distinct counts (728, 1,222). "-" in "Avg Days On Hand"
  marks the 5,531 zero-sales rows. A few daily-sales values are negative and are used as
  recorded.
- `1137e2bb…`: recomputed 15 / 10 / 25 and per-SKU totals match gold and rubric.
  Rubric 21 (missing case-pack indicator) is beyond the prompt.
- `c3525d4d…`: store ids are integers in one list and 4-character text (620 with leading
  zeros) in the other; 610 match raw, 1,226 after normalisation; 31 added, 2 removed
  (3737, 4099); budget 22,802.41 → 24,670.80 reproduces. The gold's final-list tab
  holds six-digit ids with no overlap and no derivable mapping.
- `7b08cd4d…`: all rubric figures reproduce after half-up rounding to whole dollars;
  rounded figures do not add (120,423 vs 120,422); identity holds unrounded.
  Expense-category allocation is not defined by the prompt; rubric encodes the gold's
  split.
- `7d7fc9a7…`: 41 + 25 invoices parsed; 1250 and 1251 reconcile to the GL to the cent
  under six-month and policy-period rules with BCBS amortized in the following month,
  with exact accumulation only. Total at 4/30: exactly 929,354.305 → 929,354.31 (A-10).
- `2ea2e5b5…`: all percentages reproduce; rubric 8 lists 13 entries (duplicate);
  source labels carry stray spaces; gold uses `pie3DChart` (python-pptx cannot parse;
  chart XML read directly).
- `c357f0e2…`: gold has 75 cases, non-matching role/module labels, General-formatted
  date column; would fail rubric 4, 12, 13, 67. Template headers are in row 2.
- `a45bc83b…`: inputs readable; renders checked; resources complete.
- Toolchain requirements surfaced for the next stage: read xlsx drawing text boxes;
  parse `pieChart`/`pie3DChart` from chart XML; read pivot data-field aggregation
  attributes; normalise store ids; LibreOffice recalculation; PivotTable creation test;
  PDF rendering for visual review.

## In flight

Nothing. Waiting for the human's decisions on `preregistration.md` section 4
(pending critical criteria, the PO-log per-item precision entries, 1.13 confirmation).

## Decisions taken (date · what · commit)

- 2026-10-29 · Fixed dataset revision `11e7900cdcac61bc4daf59e65feb238acda98fbf`,
  established by hash match rather than by `main` · (Stage 1 initial commit)
- 2026-10-29 · Verification method for non-LFS files: git blob sha1 against the Hub's
  `blob_id` · (Stage 1 initial commit)
- 2026-10-29 · pymupdf pinned to 1.x to avoid unrelated heavy dependencies · (Stage 1 initial commit)
- 2026-10-29 · Adjudication policy: original rubric kept and graded item by item;
  conflicts recorded in five fields (rubric text, independent result, adjudication,
  rationale, scoring effect); three problem classes (expert-deliverable defect, rubric
  defect, under-specified task) handled separately; `cannot_assess` only for items the
  materials cannot decide; public wording "graded against the public GDPval v2 rubrics,
  with documented pre-run adjudications for identified inconsistencies" · (Stage 1 initial commit)
- 2026-10-29 · Numeric policy: Decimal with intermediate precision; quantization only at
  comparison, defined per task and item; no global tolerance or rounding mode · (Stage 1 initial commit)
- 2026-10-29 · Approved per task: b5d2e6f1 C1, C2 (source reference), C4 (ratio of sums);
  f841ddcf three-way separation, C1, C2 (PO-level evidence critical); 47ef842d
  operational definitions, A-5, A-31, A-52, C2, C3; 1137e2bb A-21; c3525d4d comparisons,
  C1, C2, A-24/25; 7b08cd4d identity rule, allocation classification, A-45, A-53;
  7d7fc9a7 C1–C4, BCBS following month, COA alternatives, numeric policy; 2ea2e5b5 A-8;
  c357f0e2 C1, C2, A-2, naming/semantics separation · (Stage 1 initial commit)
- 2026-10-29 · b5d2e6f1 PivotTable `environment_unsupported` not ruled; waits for the
  toolchain test · (Stage 1 initial commit)
- 2026-10-29 · Take-home brief and GDPval paper PDFs excluded from the repository;
  README links to the public sources · (Stage 1 initial commit)
- 2026-10-30 · `data/prompts/` left untracked and rebuilt from the parquet;
  `scripts/fetch_dataset.py` added; clean-clone rebuild verified; `preregistration.md`
  gains a "Task selection and exclusions" section that `PLAN.md` points to · (Stage 1 initial commit)
- 2026-10-30 · Commits are authored by the repository owner (local git config); commit
  messages carry no Co-Authored-By trailer; the README records the coding-agent workflow
  · (Stage 1 initial commit)
- 2026-10-30 · Re-check outcomes of 2026-10-30: 7d7fc9a7 A-10 ruled on 929,354.31 (exact rational
  arithmetic, two total paths, regression test), C4 approved without a total exception;
  f841ddcf precision rules approved (per-item entries pending review); a45bc83b C2,
  requirement layers and POC rule approved with three edits; c3525d4d A-24/25 wording
  and Decimal amounts; b5d2e6f1 K2 wording · (Stage 1 initial commit)

## Next stage (not started)

Toolchain validation without model calls: project Dockerfile (arm64) with LibreOffice
and the package subset, Inspect sandbox with `network_mode: none`, `Sample.files`
staging, `/output/final/` collection including on timeout, `view` tool, extraction
(formulas, cached values, drawings, chart XML, pivot aggregation attributes), LibreOffice
recalculation on copies, deterministic checks validated on one good and one corrupted
example, PivotTable creation test (<= 1 h), judge-input assembly dry run, isolation
verification. Requires starting Docker Desktop (human approval).
