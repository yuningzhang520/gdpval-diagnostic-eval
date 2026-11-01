# Expert gold FAIL audit

Written for: the human adjudicator, before Formal Freeze. Date 2026-11-01. Graders: the tagged Grader v0 of each task
(`b5d2e6f1` .2, `f841ddcf` .1, `47ef842d` .1, `1137e2bb` .2, `c3525d4d` .2, `7b08cd4d` .1, `7d7fc9a7` .5, `2ea2e5b5` .1,
`c357f0e2` .2, `a45bc83b` .2; engine-2026-11-01.2), run on the expert deliverables without recalculation (the expert
workbooks carry cached values). Scope: every deterministic item whose verdict on the expert deliverable is not `pass`,
plus the non-rubric critical checks. Judge items and visual items have not been assessed for the expert deliverables
(no judge call, no human visual review); they are listed in the last table and carry no verdict here.

Classification. Four classes are used:
- **Expert error**: the expert artifact does not meet a requirement that the prompt itself states.
- **Rubric beyond prompt**: the expert meets the prompt, but the rubric asks for more. These rows are recorded as
  "unresolved" when they touch a critical criterion.
- **Dataset artifact**: a transformation of the dataset, not the expert's work.
- **Grader reading**: a grader error. None was found.
- **Unresolved**: the evidence cannot decide.

No grading rule was changed to make the expert pass.

## 1. Critical criteria failed or not confirmed for the expert deliverable (for adjudication)

| Task · item (weight) | Requirement (rubric) | Expert evidence (location) | Input evidence | Critical | Class | Rationale | Needed |
|---|---|---|---|---|---|---|---|
| `c3525d4d` · 32 (2) | "Tab 2 contains exactly the set of store IDs in 'Holiday Matrix final count.xlsx'" | `Deliverable Holiday Floorstand Budget.xlsx` 'STORE LIST FINAL' A6:A1262: 1,257 six-digit ids (100246-999585); 0 shared with the input | final list: 1,257 ids of 1-4 digits (620 with leading zeros) | C1 | **Dataset artifact** | Positional re-identification (section 3). The expert list has the same length and the same 26 "CAPITAL PLAN" notes in the same 26 row positions; the id substitution is unrelated to the input order (concordance 0.499) | Dataset-quality annotation; adjudicate the expert's C1 status |
| `c3525d4d` · 33 (1) | "highlighted stores … equals precisely the set difference (Final − Original)" | 'STORE LIST FINAL' D-column "ADDED" + yellow fill on 31 rows | 31 added stores (Final − Original) | C1 | **Expert error** (under the positional mapping) | Mapped by position, 25 of 31 flags hit added stores. Rows 14-19 (input ids 6494, 9688, 7987, 0058, 6782, 6780: capital-plan stores already on the original list) are flagged. Rows 31-36 (6795, 5119, 6981, 5120, 5996, 5872: added) are not flagged. The ids themselves cannot match (artifact above) | Human adjudication (depends on accepting the positional mapping) |
| `c3525d4d` · 34 (1) | identifies the removed store IDs (Original − Final) | workbook and `Final Email Deliverable.docx`: no removal statement | removed: 3737, 4099 | C1 | **Expert error** | The prompt asks explicitly ("Store 4099 and 3737 were on the original list; confirm whether they are still included") | None (rubric applies) |
| `c3525d4d` · 35 / 36 (1 / 1) | explicit status of store 4099 / 3737 | email paragraphs 1-5 and workbook: neither id appears | both absent from the final list | C1 | **Expert error** | Same explicit prompt request | None |
| `7b08cd4d` · 16 / 17 (2 / 2) | per-stop withholding = rate × row gross; per-stop net = gross − withholding | `Fall Music Tour Output.xlsx` 'P&L Tour': stop rows 7-13 carry gross only (E-G); withholding by country in rows 17-20 (46,150.8 / 51,646.8 / 56,821.2 / 36,702.76), total 191,321.56 (row 21); net revenue 852,428.44 (row 23); all correct | reference file: per-stop gross and the four country rates | C1 | **Unresolved** (rubric beyond prompt) | The prompt says "apply foreign tax withholding rates by country"; the expert did exactly that, and every figure is right. C1's approved requirement text says "rates applied per country, net revenue 852,428.44" (met), but its item list includes the per-stop items 16 and 17. The criterion's own text and its item list conflict | **Critical adjudication**: keep 16 and 17 in C1, or treat them as non-critical rubric items |
| `c357f0e2` · 4 (2) | 80-100 counted test cases | `UAT Plan.xlsx` 'UAT Test Plan' rows 3-78: 75 counted cases | prompt: "approximately 80 to 100 test cases" | C1 | **Expert error** vs the approved range (K1) | 75 is outside the rubric's inclusive range, which K1 retained. The prompt's "approximately" is the only argument for leniency | Confirm K1 (range retained) |
| `c357f0e2` · 10 (2) | Expected Result non-empty on every counted row | 'UAT Test Plan' column G: 20 counted rows empty (G19, G55-G58, …) | prompt asks for an expected result per case | C1 | **Expert error** | Incomplete rows | None |
| `7d7fc9a7` · 10 (2) | Prepaid Summary shows the total prepaid balance as of 4/30/2025 = 929,354.31 | `Aurisic_Amortization_4-25.xlsx` 'Prepaid Summary': no cell labelled as the total prepaid balance | GL balances 1250 + 1251 (April) = 929,354.31 | C4 | **Expert error** (A-10b) | The summary omits the requested total | Confirm (A-10b kept the standard; no separate C4 decision recorded) |
| `7d7fc9a7` · 30 (2) | 1250: per-month GL balance and variance check, variance 0.00 | 'PPD Exp #1250' rows 49 (variance) and 50 (GL): no per-month variance figures (only a residual) | every 1250 month reconciles to the cent | C2 | **Expert error** (A-30; presentation) | The check is required and absent although the numbers reconcile | Already decided 2026-11-01 (C2 keeps 30) |
| `2ea2e5b5` · 10 (1) | Activity Analysis table includes Total Hours per category | `WorkStudy.pptx` slide 2: columns "Activity", "% of Total Hours" (no hours) | prompt: "Activity Analysis (a table and Pie chart)", no hours named | C2 | **Unresolved** (rubric beyond prompt; K1) | The expert follows the prompt; the rubric asks for hours | **Critical adjudication**: item 10 in C2 or not |
| `b5d2e6f1` · 7, 8, 9, 18, 19, 20, 21 (2 each) | ST% = sales qty / stock on hand (ratio of sums); SUM aggregation | `Weekly Sales Analysis.xlsx` 'Sales by Brand' E4, I4, M4… and 'Sales by Store' E5…: ST% is the pivot's average of row-level ratios (`subtotal="average"`), e.g. Clinique WTD 0.2467 vs 0.2309 | source rows give the ratio of sums | C4 | **Expert error** (K3; method) | Averaging ratios is not the stated metric | None (rubric governs) |
| `b5d2e6f1` · `c2_source_totals` (non-rubric) | brand and grand totals equal the source recomputation | expert 'Data' tab differs from the source in 557 cells (WTD SOH Estee Lauder +9,816; MTD SOH Lancome +11,154, Laura Mercier +8,424, Shiseido +30,654; 234 category relabels) | `Weekly Sales Data.xlsx` 936 rows | C2 | **Unresolved** (K2) | In every changed value cell the source stock was below the sales quantity, but only part of those rows changed (89 of 117 WTD). This is either an undocumented expert edit or a different input version; no evidence decides | Annotation; adjudicate whether the expert's C2 failure is reported as expert error |
| `f841ddcf` · 8, 9, 10, 12 (2, 1, 1, 2) | June table has PO number, start, cancel, actual ship date columns | `PO Log June Ships.xlsx` 'Summary Table' (header row 5): account-level pivot summaries only | `PO Log.xlsx`: 66 POs; prompt "identify all orders that shipped" | C2 | **Expert error** (K1) | PO-level evidence is an original requirement; the expert summarised by account | None |
| `f841ddcf` · 22, 24 (2, 2) | exact June / slipped PO sets | no PO numbers in either table | 48 June POs; 5 slipped | C2 / C3 | **cannot_assess** (matter 3) | The sets cannot be verified without PO numbers (the approved rule) | None |
| `f841ddcf` · 37 (2) | narrative states the June shipped total and the slipped total, matching the tables | drawing text box: "Shipped a total of $145,219 …", "… a total value of $13,248" | June shipped 140,008.20; slipped PO value 13,300 | C5 | **Expert error** (K2) | $145,219 is the June order value labelled as shipped; $13,248 is a different metric | None |

## 2. Non-critical items failed for the expert deliverable

| Task · item (weight) | Requirement (short) | Expert evidence (location) | Class | Rationale / record |
|---|---|---|---|---|
| `c3525d4d` · 6 (2) | Tab 2 lists the final store list from the input | 'STORE LIST FINAL': re-identified ids | **Dataset artifact** | Section 3 |
| `c3525d4d` · 7 (2) | added stores highlighted | 6 of the 31 added positions not flagged | **Expert error** (under the mapping) | Section 3 |
| `c3525d4d` · 46 (1) | per-unit cost change line 1.00 | 'BUDGET': no change line (only the budget variance H16) | **Expert error** (omission) | — |
| `c357f0e2` · 67 (1) | date column formatted as Excel dates | column I: 64 counted rows General (K1) | **Expert error** | — |
| `1137e2bb` · 21 (1) | separate Case Pack Missing indicator | `PO_Order_Entry_Audit.xlsx` 'Formatted Data' header row 1: no such column | **Rubric beyond prompt** (A-21) | Adjudicated: graded as written, excluded from critical; the data hold no blank or non-positive case pack |
| `b5d2e6f1` · 4, 13, 22 (2 each) | literal header / field labels | 'Sales by Brand' row 3 ("WTD Sales Qty"), 'Sales by Store' compact pivot without "Store" / "Brand Name", 'Data' source field names | **Expert error** (labelling) | Content columns identified (C1 passes) |
| `b5d2e6f1` · 29 (1) | Sales $ currency, two decimals | both tabs, e.g. C4, G4, K4: General | **Expert error** | — |
| `f841ddcf` · 5, 6 (2 each) | Excel Table with AutoFilter | no Table objects | **Expert error** (K1) | — |
| `f841ddcf` · 17-20 (2, 1, 1, 2) | slipped table: PO number and date columns | account-level summary | **Expert error** (K1) | — |
| `f841ddcf` · 23 (1) | no blank actual ship date | no actual-ship column | **cannot_assess** | approved rule |
| `f841ddcf` · 32 (1) | date columns as Excel dates | no date columns | **Expert error** | — |
| `f841ddcf` · 55 (1) | "Shipped a total of $140,008 for the month." | text box: $145,219 | **Expert error** (K2) | — |
| `47ef842d` · 4, 31, 52 (2, 1, 1) | active stores per UPC 728 / 1,222 (A-31, A-52) | `Inventory final.xlsx` 'Summary' G6 = 729, G9 = 1,223 (typed constants) | **Unresolved** (probable expert counting error) | Input: 728 and 1,222 rows, distinct stores, none blank. The rubric copies the expert figures; adjudicated (graded against the data) |
| `47ef842d` · 11, 12 (1, 2) | store-level sheet; formulas referencing it | no store-level sheet; counts typed | **Expert error** (omission) | — |
| `47ef842d` · 17 (1) | chart values rounded to one decimal | chart1 values e.g. 11.560150 % | **Expert error** (minor) | — |

## 3. `c3525d4d` store numbers: re-identification evidence

- Input `Holiday Matrix final count.xlsx`: 1,257 rows below 'STORE #', 4-character ids with leading zeros, 26 notes
  "CAPITAL PLAN". Input `Holiday Floorstand Store List Original.xlsx`: 1,228 ids.
- Expert 'STORE LIST FINAL': 1,257 rows of distinct six-digit ids. The 26 "CAPITAL PLAN" notes sit in exactly the same
  26 row positions as in the input. Row k of the expert list therefore corresponds to row k of the input.
- The id substitution is not order-preserving. The direction of change between consecutive rows agrees in 49.9 % of the
  pairs (chance level). No id is shared with either input. Positional four-digit substrings hit the input at chance
  level (74 / 157 / 173 of 1,257). No arithmetic mapping was found; the remapping is consistent only by position.
- The budget tab uses the input's counts (1,228 / 1,257, units 1,289 / 1,320, totals correct).
- Conclusion: the expert's ids are a dataset re-identification (anonymization or remapping) of the input ids. Items 6
  and 32 fail because of the artifact, not because of the expert.
- Flags under the positional mapping: 25 of 31 "ADDED" rows are added stores. Rows 14-19 (capital-plan stores of the
  original list) are flagged instead of rows 31-36 (added stores), a contiguous block of six. Items 7 and 33 would fail
  even under the mapping: an expert error, conditional on accepting the mapping.

## 4. Not assessed for the expert deliverables (no verdict here)

| Task | Judge items (pending: no judge call) | Visual items (pending human review) |
|---|---|---|
| `1137e2bb` | 11, 23, 24, 27-30 | — |
| `7d7fc9a7` | 12, 15-18, 31, 32, 35, 45, 46, 51, 52, 54, 55 | 56 |
| `2ea2e5b5` | 57-60 | — |
| `a45bc83b` | 6-25, 31-69, 71 (item 70 judged for agreement only) | 4, 26-30, 70, 72 |
| `b5d2e6f1` | — | 32 |
| `f841ddcf` | 38, 42-46, 58 | 59 |
| `47ef842d` | 57 | 15, 16, 58 |
| `c3525d4d` | 2, 40, 48, 50, 51 | 52 |
| `7b08cd4d` | 2, 4, 25-28, 41-48 | 5, 59 |
| `c357f0e2` | 12, 13, 15-66; 69 routed to the judge (no Cross-functional Testing label; module "Cross browser Testing") | 70 |

## 5. Decisions requested before freeze (critical first)

1. `7b08cd4d` C1: the criterion's text ("rates applied per country") and its item list (per-stop items 16 and 17)
   conflict, and the expert meets the text. Keep 16 and 17 critical, or keep them as non-critical rubric items.
2. `2ea2e5b5` C2 item 10 (Total Hours): the requirement goes beyond the prompt. Keep it critical or not.
3. `c3525d4d` C1: accept the dataset-artifact classification of 6 and 32 (section 3), and the conditional expert-error
   classification of 7 and 33.
4. `b5d2e6f1` C2 source check (K2): report the expert's edited Data tab as unresolved (expert edit or input version).
5. `7d7fc9a7` C4 item 10 (A-10b): confirm it stays critical. C2 / 30 was already decided on 2026-11-01.
6. `c357f0e2` C1 item 4: confirm that K1's 80-100 range stands against the prompt's "approximately".
7. Non-critical (record only): A-31 and A-52 unresolved; the A-21 classification as rubric beyond prompt.
