DRAFT FOR HUMAN ADJUDICATION — 239 eligible item rows reviewed: 160 fail + 79 cannot_assess; excluded 24 pending_human and 2 invalid_judge_output rows.
Opus: model_error 8; grader_false_fail 49; rubric_ambiguous 15; cannot_verify 0; grader_read_failure 33; model_format_deviation 1 (106 reviewed rows).
GPT: model_error 25; grader_false_fail 43; rubric_ambiguous 20; cannot_verify 0; grader_read_failure 44; model_format_deviation 1 (133 reviewed rows).
Biggest model-error clusters: omitted reporting levels/measures 11 (GPT 11), literal naming/display 9 (Opus 4/GPT 5), operational controls/validation 5 (2/3), and rounding-adjustment rule violations 4 (GPT 4).
Biggest grader defects: slide-heading detection blocks 33 rows; Vendor/Description collision blocks 30; floorstand unit/program confusion explains 22 false fails + 6 blocked rows; 92/160 recorded fails are draft false-fail diagnoses.

## Root-cause taxonomy

Counts are unweighted rubric-item counts, not numbers of independent mistakes or task scores. The clusters below partition only the 33 `model_error` rows. Shared symptoms caused by one omission remain separate item keys for auditability. The 35 `rubric_ambiguous` rows and two `model_format_deviation` rows are excluded from this model-error taxonomy. Judge-based findings are a second opinion of a provisional judge result; they are not a new human verdict.

`diagnosis.csv` has exactly the requested seven columns and 239 unique full item keys in the form `candidate|task_id|item_id`. Each `fail` has its own diagnosis. For `cannot_assess`, nine root causes are diagnosed once; 70 additional CSV rows carry a short cross-reference to that root's representative row. The representative includes the complete covered-key list. `criterion_id`, `is_critical` and `layer` are copied unchanged for each item; an empty criterion ID means the packet supplied none.

Report key notation below abbreviates the task UUID to its unique eight-character prefix and uses `{...}` for item numbers. Full UUIDs and exact file/sheet/cell/slide/paragraph evidence remain in the CSV. DOCX paragraph numbers are one-based python-docx paragraph indices, including empty paragraphs; tables are separately numbered one-based. These may be one higher than judge excerpts that omit blanks/titles.

Review method: read the packet README, task prompts, relevant original inputs, deliverables and expert references; recompute source sums/identities independently where needed; inspect formulas, saved values, chart series and document structure. Grader code was read to locate defects, not executed. No network or paid judge calls were made. No deliverables, original labels or grading files were modified. This is static artifact review, not live execution of cloud commands, UAT scenarios or Excel interactions.
### M1. Required reporting levels or measures are omitted

The workbook has the underlying inputs or higher-level totals, but omits a requested measure or aggregation level from the delivered report. Likely mechanism (inference): presentation simplification was not checked against a field-by-field and level-by-level requirement list. This is not evidence of an arithmetic propagation error.

**Count:** Opus 0; GPT 11. **Provisional judge subset:** 1/11.

All affected rows are GPT: country-level tour tax replaces stop-level tax/net (2 rows); the store/brand pivot omits store subtotal rows (3); the inventory summary omits daily sales (5 UPC checks plus the heading check). Opus provides these reporting levels.

**Item keys:** `gpt|47ef842d|{28,35,42,49,56,57}`; `gpt|7b08cd4d|{16,17}`; `gpt|b5d2e6f1|{16,25,26}`.

### M2. Semantic substitutes do not meet explicit naming or display requirements

The intended information is often present, but exact required identifiers, field labels, sheet names or decimal presentation are replaced with a different form. Likely mechanism (inference): readability and inherited source labels were prioritized without a final literal-contract check. These are predominantly presentation mismatches, not missing transactions.

**Count:** Opus 4; GPT 5. **Provisional judge subset:** 0/9.

Both use product names instead of UPC identifiers in the inventory chart and preserve long-form source Data headers in the beauty workbook. Opus uses generic Segment / Activity headers in two classification tables. GPT omits account numbers from prepaid sheet names and uses two-decimal OOS chart labels instead of one. The literal-label findings have lower substantive severity than a wrong value; check medium-confidence items before adopting them.

**Item keys:** `gpt|47ef842d|{13,17}`; `gpt|7d7fc9a7|{3,4}`; `gpt|b5d2e6f1|{22}`; `opus|2ea2e5b5|{27,38}`; `opus|47ef842d|{13}`; `opus|b5d2e6f1|{22}`.

### M3. An operational control or concrete validation step is left unspecified

The artifact discusses a goal or supplies functional content but omits the named operational mechanism, access decision or performance validation procedure. Likely mechanism (inference): broad design coverage was accepted without checking that each required operational step had an executable or explicit counterpart.

**Count:** Opus 2; GPT 3. **Provisional judge subset:** 5/5.

Opus omits explicit environment separation and bucket object-versioning/lifecycle. GPT specifies load targets without a standard load tool, leaves the admin-interface access/not-applicable decision unstated, and has no performance acceptance case in UAT. All five findings remain provisional judge second opinions; none proves a deployed security or availability incident.

**Item keys:** `gpt|a45bc83b|{60,66}`; `gpt|c357f0e2|{66}`; `opus|a45bc83b|{64,68}`.

### M4. A disclosed rounding adjustment conflicts with a source-only accounting rule

A synthetic fractional-cent line aligns rounded invoice calculations with the full-precision account balance, creating negative amortization and a rising balance unsupported by a source invoice adjustment. Likely mechanism (inference): the model reconciled two rounding conventions by adding an explicit precision-adjustment line, without testing that line against the rubric's no-negative/no-unfunded-increase constraints.

**Count:** Opus 0; GPT 4. **Provisional judge subset:** 2/4.

GPT alone is affected: the 1250 and 1251 adjustment rows each trigger two rules. The maximum April adjustment is only $0.05 per account and is disclosed. Opus retains full precision and does not add these synthetic entries. These four rubric rows describe one rounding strategy, not four independent financial mistakes.

**Item keys:** `gpt|7d7fc9a7|{31,32,49,50}`.

### M5. A nearby test scenario omits the exact required condition or assertion

A test addresses the general feature but fails to instantiate the required missing-input condition, specified fields or both-organization mutation. Likely mechanism (inference): related scenarios were treated as interchangeable during coverage review; generic references to configured fields replaced concrete test data.

**Count:** Opus 1; GPT 2. **Provisional judge subset:** 3/3.

Opus tests invalid dates/durations but not a missing required date/duration. GPT's Idea creation names only one required field and its Super Admin cases edit only Org B rather than both organizations in one qualifying scenario. All three are provisional judge second opinions.

**Item keys:** `gpt|c357f0e2|{15,50}`; `opus|c357f0e2|{34}`.

### M6. A grouped report lacks the requested prioritization interaction

The summary is useful for drilldown but its interleaved group structure does not offer an easy sort of SKU totals by error count. Likely mechanism (inference): the author supplied a rank column and outline groups but did not validate the requested sorting workflow.

**Count:** Opus 1; GPT 0. **Provisional judge subset:** 0/1.

Opus alone: the SKU summary is alphabetical with PO child rows, no filter/table/pivot sorting aid and no descending total-error order. GPT preorders SKU groups by total errors. Medium confidence: ordinary Excel sorting exists, but sorting the interleaved rows would not preserve SKU groups.

**Item keys:** `opus|1137e2bb|{22}`.

### Adjudication boundaries outside the taxonomy

- **Tour category allocation — 16 rows:** both candidates' 7b08cd4d items 32–34, 38–40, 44–45 differ from the reference's allocation of $14,498, but source “Other Costs” does not identify Other/petty cash/fees as travel. Literal mismatches are confirmed; these are not arithmetic errors or omitted costs. If the reference allocation is deemed binding despite the source ambiguity, these would move to a category-mapping model-error cluster.
- **Serverless versus VM-specific architecture rules — 9 rows:** both a45bc83b candidates' items 14,16,36,55, plus Opus 63. Missing health-check/firewall/NAT wording is observed. The task and expert summary allow Cloud Run, while these rubric requirements presume VM-style controls or an outbound dependency. Local snapshots do not fully settle every technical applicability question; no live product validation was performed. Do not silently convert these to passes.
- **Per-line Adds policy — 2 rows:** GPT 7d7fc9a7 items 21/39 have mathematically valid dated-addition roll-forwards but no separate Adds columns. The grader code cites a 2026-11-01 human operational rule requiring those columns. This draft flags the prompt/rubric-versus-operational-rule boundary; it does not reverse that human policy. If the policy is binding, treat these as presentation failures.
- **Other wording/presentation boundaries — 8 rows:** Opus 2ea2e5b5:33 (Cost Impact aliases), Opus 47ef842d:17 (rounded display versus stored values), GPT 7d7fc9a7:53/54 (hidden precision helpers; “optional” Comments column), GPT b5d2e6f1:30 (superheaders versus field headers), GPT c357f0e2:12/28 (prompt-plural roles; Business Driver section assertion), GPT f841ddcf:57 (correct cents versus required whole-dollar narrative).

The two format deviations, both 1137e2bb item 21, omit the explicit missing/invalid Case Pack indicator. All supplied CASE packs are positive, so this omission does not change current data counts. Opus guards against nonpositive packs but gives no separate flag; GPT has neither the separate flag nor a guard. The task prompt does not explicitly request this extra flag, although item 21 does.

### Critical and shared failures

For the three priority families: inventory C4 has a literal UPC-label mismatch in both candidates (item 13), but its separate chart-value check (item 14) is a false fail in both; tour C1 contains two genuine GPT omissions at per-stop tax/net level (16/17), while Opus provides them on Revenue Detail; floorstand C2's recorded fails are false-fail diagnoses and its three blocked items per candidate are parser read failures. The already-adjudicated floorstand item 27 remains grader_false_fail for both.

Across all critical-criterion fail rows, Opus has 3 model errors, 34 false fails and 1 ambiguity; GPT has 8 model errors, 29 false fails and 3 ambiguities. This does not assign whole-criterion passes because blocked and unreviewed rows still matter.

Of 84 recorded shared-fail rows (42 candidate-paired item IDs), 51 are draft false fails, 26 ambiguous and 7 model errors. There are 24 pairs where both candidates' fail is diagnosed false, plus three pairs where only one candidate's fail is false. Counts below attribute each false/read-failure row to one primary defect; do not sum multiple symptoms as separate mistakes.

## Grader defects

Each entry identifies the affected item keys, likely code cause and one suggested fix. “Shared fail rows” counts only originally failed rows marked shared_fail in the packet; cannot_assess rows are not counted as shared fails. A defect affecting one side of a pair does not clear the other side. The 24 patterns cover all 92 grader_false_fail and 77 grader_read_failure classifications.

### D01. Slide kicker mistaken for the section heading

**Affected:** `gpt|2ea2e5b5|{5,6,7,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56}`. **Count:** 0 false-fail rows + 33 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_2ea2e5b5.py:116–149](grader_code/grading/checks_2ea2e5b5.py:116) (slide_heading / locate_sections). The topmost text shape is the repeated kicker, while the actual required title is the second text shape; all three segment sections disappear from extraction.

**Suggested fix:** Match expected section titles across candidate heading shapes and validate against the table/chart, rather than selecting frames[0].

### D02. Vendor and Description resolve to the same semantic field

**Affected:** `opus|7d7fc9a7|{11,13,14,19,20,21,22,23,24,25,26,27,28,29,30,33,34,36,37,38,39,40,41,42,43,44,47,48,49,50}`. **Count:** 0 false-fail rows + 30 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_7d7fc9a7.py:59](grader_code/grading/checks_7d7fc9a7.py:59),237–257 (SCHEMA / parse_schedule). Description is an equal vendor synonym, so two legitimate separate columns trigger vendor_ambiguous; downstream item 11 loses the detail totals too.

**Suggested fix:** Prefer the explicit Vendor column and use Description only as a fallback when no vendor field exists.

### D03. Per-stand and program money are conflated

**Affected:** `gpt|c3525d4d|{3,16,17,18,19,20,26,27,28,29,30,31,46,49}`; `opus|c3525d4d|{3,16,17,18,19,20,26,27,28,29,30,31,46,49}`. **Count:** 22 false-fail rows + 6 read-failure rows; **shared fail rows explained:** 22.

**Likely cause:** [checks_c3525d4d.py:190–230](grader_code/grading/checks_c3525d4d.py:190),236–270,750–760 (metric_of / facts_of). The program-total branch precedes unit-cost classification and excludes only per-unit wording, not per-floor-stand or /stand; the same mislabeled row turns G9/G10's $1 unit delta into a budget delta. This explains the supplied item-27 adjudication and the other cited leads.

**Suggested fix:** Classify measurement units first, including /stand and per floor stand, then bind each original/revised/delta within that unit.

### D04. One-sheet P&L selection suppresses supporting tax schedules

**Affected:** `opus|7b08cd4d|{15,16,17,19,21,22,23,24}`. **Count:** 8 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 8.

**Likely cause:** [checks_7b08cd4d.py:294–303](grader_code/grading/checks_7b08cd4d.py:294),356–374,393–400. The best-sheet score selects P&L Summary and all checks use that model; country-row matching also excludes city-containing labels. Revenue Detail contains the required per-stop tax/net calculations.

**Suggested fix:** Resolve each required revenue/tax measure across relevant workbook sheets and distinguish country deductions from performances.

### D05. Valid negative tax deductions are compared with positive tax amounts

**Affected:** `gpt|7b08cd4d|{15,19,21,22,23,24}`. **Count:** 6 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 6.

**Likely cause:** [checks_7b08cd4d.py:375–400](grader_code/grading/checks_7b08cd4d.py:375) and withholding total checks. Tax magnitude is correct, but direct signed comparison interprets its P&L subtraction sign as a wrong rate or amount.

**Suggested fix:** Normalize the sign only for rows explicitly labeled as withholding deductions, and check the gross-minus-tax identity.

### D06. A real SKU summary is discarded during sheet discovery

**Affected:** `opus|1137e2bb|{12,13,14,15,16,17,56,57,58,59,60,61,62}`. **Count:** 13 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 1.

**Likely cause:** [checks_1137e2bb.py:241–310](grader_code/grading/checks_1137e2bb.py:241),600–607,977–987. Any detail candidate is excluded from summary search, including the grouped SKU/PO summary; its SKU, PO and quantity fields resemble a detail table.

**Suggested fix:** Exclude only confirmed raw-detail tables and allow a separate sheet with aggregate measures and grouped PO rows to qualify as a summary.

### D07. Order cost / Shipped cost are missing from the column vocabulary

**Affected:** `gpt|f841ddcf|{11,13,21,27,28,29,30,31,35,36,37,47}`. **Count:** 11 false-fail rows + 1 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_f841ddcf.py:41–43](grader_code/grading/checks_f841ddcf.py:41),95–121,445–450,528–562,591. Both unambiguous cost columns exist; absent aliases cascade into ratio, conditional arithmetic, totals, account summary and narrative comparison failures.

**Suggested fix:** Map Order cost and Shipped cost to their cost-value fields before running dependent checks.

### D08. Hyphenated On-hand is not recognized as inventory

**Affected:** `gpt|47ef842d|{27,34,41,48,55}`; `opus|47ef842d|{27,34,41,48,55}`. **Count:** 10 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 10.

**Likely cause:** [checks_47ef842d.py:38–56](grader_code/grading/checks_47ef842d.py:38) (COLS / column_of). The inventory regex accepts on\s*hand but the delivered headers use On-Hand/On-hand, so ten correct inventory totals appear absent.

**Suggested fix:** Normalize hyphens or match on[\s-]*hand before checking inventory values.

### D09. Asset GL identifiers become monetary candidates

**Affected:** `gpt|7d7fc9a7|{7,8,9}`. **Count:** 0 false-fail rows + 3 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_7d7fc9a7.py:561–603](grader_code/grading/checks_7d7fc9a7.py:561),607–617. The account-number exclusion checks account/acct/# but misses the Asset GL caption; 1250/1251 compete with real balances and formula links.

**Suggested fix:** Recognize GL identifier captions and exclude identifier columns from monetary target discovery.

### D10. A narrative's word increase mis-scopes common component quantities

**Affected:** `opus|c3525d4d|{12,13,14}`. **Count:** 3 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_c3525d4d.py:175–186](grader_code/grading/checks_c3525d4d.py:175),241–264,294–302. Opus B6:B8 are correctly recognized as quantities, but A2's explanatory sentence contains increase and is treated as a delta heading; fallback assigns all three common quantities to delta instead of both scenarios.

**Suggested fix:** Limit scenario inheritance to structural headers and keep shared quantity columns scenario-neutral.

### D11. Section headings are scanned as invoice rows

**Affected:** `gpt|7d7fc9a7|{22,40}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_7d7fc9a7.py:259–305](grader_code/grading/checks_7d7fc9a7.py:259) (parse_schedule). The scanner crosses register totals and blanks until it sees the next month header; N55/N39's text section heading is counted as March amortization on a supposed invoice.

**Suggested fix:** Bound the invoice register by its total/table region and reject rows without invoice identity and numeric amounts.

### D12. Post-total explanatory notes become spurious brands

**Affected:** `gpt|b5d2e6f1|{5,24}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_b5d2e6f1.py:210–276](grader_code/grading/checks_b5d2e6f1.py:210) (parse_summary). The scan continues after Grand Total and blank rows, so HOW TO READ/METHOD/etc. below the table are counted as extra brand labels.

**Suggested fix:** Use the PivotTable/table range or stop at its grand total before classifying brand rows.

### D13. Non-money measures are sent through currency checks

**Affected:** `gpt|c3525d4d|{43}`; `opus|7d7fc9a7|{53}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 1.

**Likely cause:** [checks_c3525d4d.py:190–230](grader_code/grading/checks_c3525d4d.py:190),763–769; [checks_7d7fc9a7.py:561–603](grader_code/grading/checks_7d7fc9a7.py:561),1152–1198. The budget-increase percentage G19 and invoice counts C8:C10 are treated as monetary amounts; their percentage/integer formats are appropriate.

**Suggested fix:** Determine units from both row and column labels, excluding percentage and count fields before currency validation.

### D14. A label mismatch blocks an independent chart-value check

**Affected:** `gpt|47ef842d|{14}`; `opus|47ef842d|{14}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 2.

**Likely cause:** [checks_47ef842d.py:387–433](grader_code/grading/checks_47ef842d.py:387). Product-name charts exist with correct OOS values, but the item-13 UPC-label predicate prevents item 14 from assessing numeric agreement at all.

**Suggested fix:** Discover the chart via its OOS series and source-cell mapping, then assess literal category labels and numeric consistency separately.

### D15. A chart's explicit ID legend is ignored

**Affected:** `gpt|2ea2e5b5|{9,25}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_2ea2e5b5.py:417–424](grader_code/grading/checks_2ea2e5b5.py:417) and item-25 chart-category comparison. GPT's 01–12 slices map to the adjacent table's exact 12 activities, but the checker compares ID strings directly with activity names.

**Suggested fix:** Resolve explicit chart-ID-to-table mappings before checking semantic category membership.

### D16. Cost Impact and Investment Impact miss exact slice lookup

**Affected:** `opus|2ea2e5b5|{31,32}`. **Count:** 2 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_2ea2e5b5.py:234–252](grader_code/grading/checks_2ea2e5b5.py:234) (chart_shares), SEGMENT_PIE / segment percentage checks. Opus uses the prompt's longer labels, so the correct 58.0%/42.0% values are treated as nonexistent Cost/Investment slices.

**Suggested fix:** Normalize the two prompt-defined aliases for numeric share checks while leaving literal-label item 33 for its own ruling.

### D17. Overall counts and per-SKU counts are not distinguished

**Affected:** `gpt|1137e2bb|{25,26}`. **Count:** 0 false-fail rows + 2 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_1137e2bb.py:654–680](grader_code/grading/checks_1137e2bb.py:654) (bound_counts / count_verdict). The regex misses 'Price mismatches occur on 15 lines' and mixes '2 case-pack errors each' with the explicitly stated overall ten.

**Suggested fix:** Bind counts to their sentence/table scope and support occur-on phrasing before testing overall totals.

### D18. First matching snapshot cell overrides direct summary links elsewhere

**Affected:** `opus|7d7fc9a7|{7}`. **Count:** 1 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_7d7fc9a7.py:607–617](grader_code/grading/checks_7d7fc9a7.py:607),1125–1150. Equal-value candidates are marked unique_value, then verdicts[0] is checked; the summary's monthly April ending totals directly reference detail sheets even though snapshot G8/G9 use local roll-forwards.

**Suggested fix:** Assess all identified qualifying summary totals and trace formula dependencies instead of taking the first candidate.

### D19. Level / PO plus grouped PO identifiers is not recognized as drilldown

**Affected:** `gpt|1137e2bb|{14}`. **Count:** 1 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 1.

**Likely cause:** [checks_1137e2bb.py:645](grader_code/grading/checks_1137e2bb.py:645),1000–1002. The detector requires a synonym-matching header or a PivotTable; it misses actual PO IDs nested under each SKU with working outline metadata.

**Suggested fix:** Recognize Level / PO and validate grouped child PO rows as the rubric's allowed drilldown form.

### D20. London withholding is counted as a second London performance

**Affected:** `opus|7b08cd4d|{6}`. **Count:** 1 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_7b08cd4d.py:167–188](grader_code/grading/checks_7b08cd4d.py:167) (stop_rows). The scanner excludes expense sections but not tax sections; a country withholding row containing London becomes another show.

**Suggested fix:** Require a performance/revenue identity and exclude labeled tax/country subtotal rows from stop detection.

### D21. Footnotes become account names

**Affected:** `opus|f841ddcf|{39}`. **Count:** 1 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_f841ddcf.py:184–230](grader_code/grading/checks_f841ddcf.py:184) (find_tables). Rows below totals are appended until a blank row, so two narrative footnotes are tested as account values.

**Suggested fix:** Use table boundaries and require account-row measures before checking membership in the source account set.

### D22. Valid named PivotTable source cannot be resolved

**Affected:** `gpt|b5d2e6f1|{12}`. **Count:** 0 false-fail rows + 1 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [checks_b5d2e6f1.py:531–544](grader_code/grading/checks_b5d2e6f1.py:531); extract.py PivotTable source extraction. worksheetSource.name=WeeklySalesData is valid but source_ref is empty; a literal A1-range-only check returns cannot_assess.

**Suggested fix:** Resolve worksheetSource.name through Excel Tables/defined names to Data!A1:R937.

### D23. Provisional judge over-literalizes equivalent assertions or date wording

**Affected:** `gpt|f841ddcf|{38}`; `opus|c357f0e2|{42,60}`. **Count:** 3 false-fail rows + 0 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [judge.py:26–31](grader_code/grading/judge.py:26) (SYSTEM prompt), build_units_c357f0e2 and build_units_f841ddcf. The actual UAT rows assert saved/shown risk and seeded search results; the shipment narrative gives the exact June interval in words. The judge adds log-appearance, standalone-list-load or numeric-date-string requirements. No deterministic-code defect is established here; this is a second-opinion disagreement.

**Suggested fix:** Require semantic-equivalence reasoning for these criteria and reserve exact-string enforcement for rubrics that explicitly demand it.

### D24. Judge receives the P&L summary without the needed expense detail

**Affected:** `gpt|7b08cd4d|{41}`. **Count:** 0 false-fail rows + 1 read-failure rows; **shared fail rows explained:** 0.

**Likely cause:** [judge.py:383–415](grader_code/grading/judge.py:383) (build_units_7b08cd4d). The evidence builder serializes only the chosen P&L sheet, though the item asks for line items located on Expense Detail.

**Suggested fix:** Include the criterion-relevant supporting worksheet and formula-linked source rows in the judge unit.

### Related defects that do not by themselves overturn a fail

- GPT f841ddcf item 57: [checks_f841ddcf.py:564–572](grader_code/grading/checks_f841ddcf.py:564) takes the first dollar amount in a sentence containing “short”, so it reads $140,008.20 instead of $5,210.60; its own precision-aware comparator would accept the latter. The item remains rubric_ambiguous because the rubric explicitly asks for $5,211. Suggested fix: bind the amount to the shortfall phrase before applying the separately adjudicated rounding policy. Shared fail rows: 0.
- Opus 1137e2bb item 22, GPT 47ef842d item 17, and GPT 7d7fc9a7 item 50 have faulty original rationales, but independent evidence still supports a literal failure (sorting, decimal display, and the synthetic rounding row respectively); none is counted as a false fail.
- Opus 47ef842d item 17 and GPT 7d7fc9a7:21/39 also expose display-versus-storage and explicit-column policy questions; these need an adjudication rule before any checker patch can assign a final result.

### Grouped cannot_assess diagnoses

These groups cover all 79 cannot_assess items once. A read-failure classification is not a blanket pass after repair: for example, GPT time-study tables still use generic Segment headers, and Opus prepaid schedules may face the same explicit-Adds presentation policy as GPT.

**R01 — grader_read_failure (1 item rows).** Judge evidence excerpt omits supporting worksheet.

Covered keys: `gpt|7b08cd4d|{41}`. Full diagnosis: representative CSV key `gpt|7b08cd4d-df60-41ae-9102-8aaa49306ba2|41`.

2024_Fall_Music_Tour_Profit_and_Loss.xlsx Expense Detail!B16:F17 attributes Agency Commission $114,812.50 (=11%×$1,043,750, rounded $114,813) and Insurance $22,024 to Tour Manager and Other Tour Costs. Source Fall Music Tour Ref File.xlsx 'Inc & Costs Tracked by Tour Mgr'!E43:E44 agrees. Task requires separated source details and the workbook supplies them. The judge received only the high-level Tour P&L excerpt, omitting Expense Detail; this is an evidence-pack selection failure, not missing deliverable content. Second opinion of provisional cannot_assess: relevant evidence is available.

**R02 — grader_read_failure (6 item rows).** Floorstand per-stand labels classified as program totals.

Covered keys: `gpt|c3525d4d|{28,29,30}`; `opus|c3525d4d|{28,29,30}`. Full diagnosis: representative CSV key `gpt|c3525d4d-2012-45df-853e-2d2a0e902991|28`.

Both floorstand workbooks clearly separate unit and program totals. Opus Holiday_Floorstand_Budget_Revision.xlsx Budget Comparison!D23=$22,802.41, D24=$24,670.80 and E24=D24-D23=$1,868.39; GPT Holiday Floorstand Budget and Store Reconciliation.xlsx Cost Comparison!B19/C19/D19 show the same values. Source counts 1,228/1,257, common 5% overage rounded to 1,289/1,320 and $17.69/$18.69 per stand independently reproduce them. Task requests original/revised comparison without prescribed headings. metric_of/facts_of mistakes per-floor-stand costs E9/F9 or E10/F10 (and Opus B23/B24 unit-cost column) for program totals and mistakes $1 unit delta for program delta. No genuine ambiguity remains after using the row/column units.

**R03 — model_format_deviation (2 item rows).** Missing separate invalid-case-pack indicator.

Covered keys: `gpt|1137e2bb|{21}`; `opus|1137e2bb|{21}`. Full diagnosis: representative CSV key `gpt|1137e2bb-bdf9-4876-b572-f29b7de5e595|21`.

Both Excel deliverables omit a separate missing/invalid Case Pack indicator: Opus PO_Line_Error_Audit.xlsx RawData!I1:O42 and GPT Wholesale_Order_Audit.xlsx RawData!I1:M42. Opus J excludes G<=0 but creates no dedicated flag; GPT J directly calls MOD on CASE rows without an invalid-pack guard. All source CASE rows have positive Case Pack, so current 41-row counts are unaffected. Task prompt explicitly asks price/case/total/error-type columns and CASE divisibility; the extra missing-pack indicator is an explicit item-21 requirement, not an explicit prompt field. This is a real missing rubric structure, not an unreadable synonymous indicator; classify as format deviation while flagging the prompt/rubric scope difference.

**R04 — grader_read_failure (2 item rows).** Narrative count parser misses grammar and scope.

Covered keys: `gpt|1137e2bb|{25,26}`. Full diagnosis: representative CSV key `gpt|1137e2bb-bdf9-4876-b572-f29b7de5e595|25`.

Wholesale_Order_Audit_Summary.docx paragraph 5 explicitly says 'Price mismatches occur on 15 lines' and 'Case-pack violations occur on 10 CASE lines'; table 1 also states 15 price / 10 case pack. Source Reference_PO Data.xlsx RawData's 41 rows independently yield 15 price and 10 CASE-multiple errors. Paragraph 9's '2 case-pack errors each' is a per-SKU count, not a conflicting overall total. Task asks a brief Word summary without a fixed syntax. checks_1137e2bb.py bound_counts/count_verdict only binds a narrow phrase grammar and ignores count scope.

**R05 — grader_read_failure (33 item rows).** Slide section detector reads kicker as title.

Covered keys: `gpt|2ea2e5b5|{5,6,7,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56}`. Full diagnosis: representative CSV key `gpt|2ea2e5b5-257f-42e6-a7dc-93763f28b19d|5`.

IT_Work_Time_Study.pptx slides 3–5 have the required titles Margin Impact by Activities, Time Sensitivity by Activities and Strategic Level by Activities in TextBox 3, plus Table 11 and pie charts. The repeated TextBox 2 kicker sits above each title. Task prompt requires five named slides with tables/charts, not PowerPoint title placeholders or first-text-shape titles. checks_2ea2e5b5.py slide_heading/section identification reads the topmost line and discards all three sections. Coverage includes items 5–7 and 27–56 as explicitly listed; re-grade each after fixing detection. In particular Table 11 uses generic Segment headers, so literal header items 27/38 need separate assessment rather than automatic pass.

**R06 — grader_read_failure (30 item rows).** Prepaid vendor schema collides with Description.

Covered keys: `opus|7d7fc9a7|{11,13,14,19,20,21,22,23,24,25,26,27,28,29,30,33,34,36,37,38,39,40,41,42,43,44,47,48,49,50}`. Full diagnosis: representative CSV key `opus|7d7fc9a7-21a7-4b83-906f-416dea5ad04f|11`.

Aurisic_Prepaid_Amortization_Schedule_Apr2025.xlsx, Prepaid Expenses 1250 and Prepaid Insurance 1251 row 7 separately label A=Vendor, D=Description. A holds actual vendors and D holds service types; the task explicitly asks vendor-sorted schedules, not a combined vendor/description field. checks_7d7fc9a7.py SCHEMA.vendor at line 59 accepts Description as an equal synonym, so parse_schedule returns vendor_ambiguous before reading either register; item 11 subsequently cannot find totals. Actual monthly totals are Expenses!L57:P57 and Insurance!L35:P35, with summary references F8/F9. All 41 services invoices and 25 insurance invoices are identifiable by vendor/invoice/source amount. Group covers 29 direct ambiguity rows plus dependent summary item 11. Resolving extraction must not automatically pass per-line additions requirements, whose applicability needs adjudication.

**R07 — grader_read_failure (3 item rows).** Prepaid Asset GL identifiers treated as balances.

Covered keys: `gpt|7d7fc9a7|{7,8,9}`. Full diagnosis: representative CSV key `gpt|7d7fc9a7-21a7-4b83-906f-416dea5ad04f|7`.

Aurisic_Prepaid_Amortization_April_2025.xlsx, Prepaid Summary!A8 says Asset GL and A9:A10 are identifiers 1250/1251. E9:E10 directly reference detail YTD amortization; F9:F10 reference detail April balances; G9:G10 reference GL balances $559,377.61/$369,976.70, matching the prompt. The parser's account-caption exclusion recognizes account/acct/# but not Asset GL, so it admits account numbers as competing monetary balances. Task requires a summary and account identification; this standard layout is not a format deviation.

**R08 — grader_read_failure (1 item rows).** Pivot source resolver ignores named Excel Tables.

Covered keys: `gpt|b5d2e6f1|{12}`. Full diagnosis: representative CSV key `gpt|b5d2e6f1-62a2-433a-bcdd-95b260cdd860|12`.

Weekly Sales Analysis.xlsx contains SalesByStore PivotTable at Sales by Store!A6:N319. xl/pivotCache/pivotCacheDefinition2.xml worksheetSource names WeeklySalesData on Data; xl/tables/table1.xml resolves WeeklySalesData to Data!A1:R937 (936 source records). Task requires a PivotTable from Data and is satisfied structurally. checks_b5d2e6f1.py lines 535–544 requires a literal range source_ref and cannot resolve a valid named Excel Table source.

**R09 — grader_read_failure (1 item rows).** Shipment cost-column aliases not recognized.

Covered keys: `gpt|f841ddcf|{37}`. Full diagnosis: representative CSV key `gpt|f841ddcf-2a28-4f6d-bac3-61b607219d3e|37`.

June_2025_Shipment_Recap.xlsx June Recap!A4 states $140,008.20 June shipped and $13,300.00 slipped order cost; June Shipped POs!G55 and June to July POs!F12 show matching totals. Source PO Log.xlsx actual-ship-date June cohort (48 POs) and June-window July cohort (5 POs) independently confirm them. Task asks for those two narrative totals, not prescribed cost-column strings. The same missing Order cost/Shipped cost aliases prevent table_total from obtaining values for comparison.

### Scope and key map

All reviewed material is within the bundle root (`failures-v1/`); paths below are relative to it. The two invalid_judge_output rows and all pending_human visual rows are excluded from counts, taxonomy and diagnoses. Existing human adjudications were preserved; no new grader calls or label edits were made. Confidence describes confidence in this draft classification, not that a proposed pass has been approved. No claim is made that the expert reference is automatically correct where it disagrees with the original source.

| Task prefix | Full task UUID |
|---|---|
| 1137e2bb | 1137e2bb-bdf9-4876-b572-f29b7de5e595 |
| 2ea2e5b5 | 2ea2e5b5-257f-42e6-a7dc-93763f28b19d |
| 47ef842d | 47ef842d-8eac-4b90-bda8-dd934c228c96 |
| 7b08cd4d | 7b08cd4d-df60-41ae-9102-8aaa49306ba2 |
| 7d7fc9a7 | 7d7fc9a7-21a7-4b83-906f-416dea5ad04f |
| a45bc83b | a45bc83b-22f9-4def-8d89-9c5661b2b86f |
| b5d2e6f1 | b5d2e6f1-62a2-433a-bcdd-95b260cdd860 |
| c3525d4d | c3525d4d-2012-45df-853e-2d2a0e902991 |
| c357f0e2 | c357f0e2-963d-4eb7-a6fa-3078fe55b3ba |
| f841ddcf | f841ddcf-2a28-4f6d-bac3-61b607219d3e |
