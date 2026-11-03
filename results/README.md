# Results: the records behind the page

Copies of the records that `site/build.py` reads to produce every number on the submission page, so each number can be
checked from the repository. `results/<path>` is a copy of `~/turing-eval-runs/<path>` in the local run store; the
originals are unchanged.

How the copies were checked (`SHA256SUMS` lists the hash of each copy and of its source):
- each record's source hash equals the build input hash listed under `sources` in `site/data/metrics.json`;
- two records contained absolute paths of the run store; in the copies these read `~/turing-eval-runs/`, and the copies
  are otherwise byte-identical to their sources (`formal/results_summary.json`, `labeling/formal-v4-reveal/…`);
- the ledgers give the same settled totals as in `site/data/metrics.json` (`cost_all_workloads_usd.per_ledger`);
- each deliverable matches the SHA-256 in its run's artifact manifest.

Not included: the Inspect logs and transcripts; the ledgers of the development, validation, compatibility and
judge-calibration work, which make up the rest of the $88.33 (report section 8.1); the GDPval prompts, rubrics and
expert files, which `scripts/download_materials.py` downloads from the public dataset. The failure taxonomy and the
failure-source tags are in `analysis/`.

## Records

| File | What it is | Backs on the page |
|---|---|---|
| [`analysis/failures-v1/all_items.csv`](analysis/failures-v1/all_items.csv) | Every rubric item of both models: task, critical requirement, rubric text, grader (code grader, LLM judge or visual), graded verdict, grader reason, judge citation, adjudication | 580 rubric items per model; 320 inside the 35 critical requirements; 239 graded fail or cannot assess; the 96 not reviewed (60 fail, 10 cannot assess, 24 visual items without a verdict, 2 invalid judge outputs); the quoted rubric items |
| [`formal/results_summary.json`](formal/results_summary.json) | One record per evaluation run (20): model, task, run ID, scores and verdict counts as graded, judge coverage, generation cost of the run | Generation alone: Opus 5.5 $14.90, GPT-6.1-sol $3.08 (sum of `generation_cost_usd` per model); the run IDs |
| [`formal/human_layers_summary.json`](formal/human_layers_summary.json) | Critical-requirement status of each run on four bases (graders only, before review, after review, without the additions rule) and the rubric items in each critical requirement | 7/10 and 3/10 tasks passed and the task grid; the bars 25/7/3 → 31/4/0 and 16/14/5 → 26/9/0; † 7/2/1 and 3/6/1; the additions rule deciding 1 failed task per model |
| [`analysis/critical_adjudication.csv`](analysis/critical_adjudication.csv) | The author-review worksheet: the 170 reviewed rubric items (section 1: the 145 inside critical requirements; section 2: the 24 the AI draft suspected and the blind audit's false pass) with graded verdict, grader reason, AI-draft class, and the author's decision and evidence | 170 reviewed; 100 graded fail (78 could change a verdict, 22 suspected model failures); 69 cannot assess; 67 grader false fails; 21 cannot assess → pass; 42 left |
| [`formal/human_review/adjudication_20261102T133050Z.jsonl`](formal/human_review/adjudication_20261102T133050Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 2 records: grader false fails found by the blind audit (holiday floor-stand budget, rubric item 27, both models) | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261102T185621Z.jsonl`](formal/human_review/adjudication_20261102T185621Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 1 record: the blind audit's grader false pass (PO entry audit, rubric item 23) | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261102T220501Z.jsonl`](formal/human_review/adjudication_20261102T220501Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 167 records: the author's decisions on the worksheet, with evidence | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261102T224529Z.jsonl`](formal/human_review/adjudication_20261102T224529Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 12 records: hand re-grades for consistency between the two models, further grader false fails, and the blind audit's false pass (PO entry audit, rubric item 23) | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261102T232302Z.jsonl`](formal/human_review/adjudication_20261102T232302Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 10 records: author-verified passes of Opus 5.5 (its store subtotals and daily sales figures) | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261102T232303Z.jsonl`](formal/human_review/adjudication_20261102T232303Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 1 record: GPT-6.1-sol's Sales by Store confirmed as a PivotTable (weekly sales, rubric item 12) | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/adjudication_20261103T023411Z.jsonl`](formal/human_review/adjudication_20261103T023411Z.jsonl) | Author decision records, append-only (the latest record per rubric item counts); 4 records: verified passes from the invoice-by-invoice reconciliation of Opus 5.5's prepaid schedule | the 40 confirmed failures and their failure types; the cards' rubric items; the 67 grader false fails; the after-review verdicts |
| [`formal/human_review/visual_20261102T133023Z.jsonl`](formal/human_review/visual_20261102T133023Z.jsonl) | The pre-registered human visual review: 12 verdicts on chart and layout items | the before-review basis (graders plus visual review) |
| [`labeling/formal-v4-reveal/reveal_20261102T125548Z.json`](labeling/formal-v4-reveal/reveal_20261102T125548Z.json) | The 20 blind-audit labels, saved before results were seen, with the frozen graders' verdicts | 8/10 (code grader) and 9/10 (LLM judge) agreement; 1 false pass in 18 audited passes; the false pass in card C |
| [`formal/ledger.json`](formal/ledger.json) | Generation ledger, units 1-2 (weekly sales, both models): reservations and settlements with provider-reported usage | $30.06 for the 20 evaluation runs; generation per model |
| [`formal/opus/ledger.json`](formal/opus/ledger.json) | Generation ledger, Opus 5.5 worker (9 runs) | $30.06; Opus 5.5 $14.90 |
| [`formal/gpt/ledger.json`](formal/gpt/ledger.json) | Generation ledger, GPT-6.1-sol worker (9 runs) | $30.06; GPT-6.1-sol $3.08 |
| [`judge_formal/ledger.json`](judge_formal/ledger.json) | LLM-judge ledger for the 20 runs | $30.06 (judging $12.08) |
| [`SHA256SUMS`](SHA256SUMS) | SHA-256 of every copy and of its source, and how it was copied | the checks above |

## Deliverables of the 20 evaluation runs

The final files each model delivered (workbooks, documents, decks, diagrams), as collected from the sandbox; no
transcripts or logs. The run ID is the one in `site/data/metrics.json` and `formal/results_summary.json`.

| Task | Model | Run | File | Backs on the page |
|---|---|---|---|---|
| Weekly sales analysis | Opus 5.5 | `Mae4tizWVH2BiinB5zKQV2` | [Weekly Sales Data - Beauty Sales Analysis.xlsx](formal/runs/Mae4tizWVH2BiinB5zKQV2/final/Weekly%20Sales%20Data%20-%20Beauty%20Sales%20Analysis.xlsx) | card A (store subtotals); the weekly sales worked example |
| Weekly sales analysis | GPT-6.1-sol | `d5sypgfTdCCwfsFV9jdzLd` | [Weekly Sales Analysis.xlsx](formal/runs/d5sypgfTdCCwfsFV9jdzLd/final/Weekly%20Sales%20Analysis.xlsx) | card A (store subtotals); the weekly sales worked example |
| June shipment recap | Opus 5.5 | `hdDnxUR6sUhQD6PHLnhKSm` | [June 2025 Shipment Recap.xlsx](formal/opus/runs/hdDnxUR6sUhQD6PHLnhKSm/final/June%202025%20Shipment%20Recap.xlsx) | its task verdicts |
| June shipment recap | GPT-6.1-sol | `P8gA2U2jR7VzNWKqqdJ5SZ` | [June_2025_Shipment_Recap.xlsx](formal/gpt/runs/P8gA2U2jR7VzNWKqqdJ5SZ/final/June_2025_Shipment_Recap.xlsx) | its task verdicts |
| Weeks of supply | Opus 5.5 | `LVyjBBcU4iFqDKviwY2YJz` | [Top5_UPC_Inventory_Position_Wk28_2025.xlsx](formal/opus/runs/LVyjBBcU4iFqDKviwY2YJz/final/Top5_UPC_Inventory_Position_Wk28_2025.xlsx) | card B (chart labels); the weeks-of-supply note |
| Weeks of supply | GPT-6.1-sol | `dPR5yvN9wEfcMyQiAC2njB` | [Inventory_Health_Top_5_2025_W28.xlsx](formal/gpt/runs/dPR5yvN9wEfcMyQiAC2njB/final/Inventory_Health_Top_5_2025_W28.xlsx) | card B (chart labels); the weeks-of-supply note |
| PO entry audit | Opus 5.5 | `iS5pLfPvTxhxxXScg7HXVw` | [PO_Audit_Error_Summary.docx](formal/opus/runs/iS5pLfPvTxhxxXScg7HXVw/final/PO_Audit_Error_Summary.docx) | card C (the case-pack definition) |
| PO entry audit | Opus 5.5 | `iS5pLfPvTxhxxXScg7HXVw` | [PO_Line_Error_Audit.xlsx](formal/opus/runs/iS5pLfPvTxhxxXScg7HXVw/final/PO_Line_Error_Audit.xlsx) | card C (the case-pack definition) |
| PO entry audit | GPT-6.1-sol | `mE6xrcKcirXrQgh4ugBfbE` | [Wholesale_Order_Audit.xlsx](formal/gpt/runs/mE6xrcKcirXrQgh4ugBfbE/final/Wholesale_Order_Audit.xlsx) | card C (the case-pack definition) |
| PO entry audit | GPT-6.1-sol | `mE6xrcKcirXrQgh4ugBfbE` | [Wholesale_Order_Audit_Summary.docx](formal/gpt/runs/mE6xrcKcirXrQgh4ugBfbE/final/Wholesale_Order_Audit_Summary.docx) | card C (the case-pack definition) |
| Holiday floor-stand budget | Opus 5.5 | `fAFHskFwVPcLzn89SuYaxv` | [Holiday_Floorstand_Budget_Revision.xlsx](formal/opus/runs/fAFHskFwVPcLzn89SuYaxv/final/Holiday_Floorstand_Budget_Revision.xlsx) | its task verdicts |
| Holiday floor-stand budget | Opus 5.5 | `fAFHskFwVPcLzn89SuYaxv` | [Holiday_Floorstand_Budget_Update_Email.docx](formal/opus/runs/fAFHskFwVPcLzn89SuYaxv/final/Holiday_Floorstand_Budget_Update_Email.docx) | its task verdicts |
| Holiday floor-stand budget | GPT-6.1-sol | `SJbeNCc6EYF5dHerim5UD6` | [Draft Email - Holiday Floorstand Budget Approval.docx](formal/gpt/runs/SJbeNCc6EYF5dHerim5UD6/final/Draft%20Email%20-%20Holiday%20Floorstand%20Budget%20Approval.docx) | its task verdicts |
| Holiday floor-stand budget | GPT-6.1-sol | `SJbeNCc6EYF5dHerim5UD6` | [Holiday Floorstand Budget and Store Reconciliation.xlsx](formal/gpt/runs/SJbeNCc6EYF5dHerim5UD6/final/Holiday%20Floorstand%20Budget%20and%20Store%20Reconciliation.xlsx) | its task verdicts |
| Tour profit and loss | Opus 5.5 | `KU4bWmuqsWUUbkTXEu9Fpj` | [2024_Fall_Music_Tour_PL_Report_As_of_12-31-2024.xlsx](formal/opus/runs/KU4bWmuqsWUUbkTXEu9Fpj/final/2024_Fall_Music_Tour_PL_Report_As_of_12-31-2024.xlsx) | the per-stop tax failure (*) |
| Tour profit and loss | GPT-6.1-sol | `hX4B29t5iE2v3rFKMtqWqz` | [2024_Fall_Music_Tour_Profit_and_Loss.xlsx](formal/gpt/runs/hX4B29t5iE2v3rFKMtqWqz/final/2024_Fall_Music_Tour_Profit_and_Loss.xlsx) | the per-stop tax failure (*) |
| Prepaid amortization | Opus 5.5 | `czgd84YmwwTZzDpVKD5vhD` | [Aurisic_Prepaid_Amortization_Schedule_Apr2025.xlsx](formal/opus/runs/czgd84YmwwTZzDpVKD5vhD/final/Aurisic_Prepaid_Amortization_Schedule_Apr2025.xlsx) | the additions column (†) and the rounding line (D) |
| Prepaid amortization | GPT-6.1-sol | `FDVJTwSvqDJFQj6JyTpkHY` | [Aurisic_Prepaid_Amortization_April_2025.xlsx](formal/gpt/runs/FDVJTwSvqDJFQj6JyTpkHY/final/Aurisic_Prepaid_Amortization_April_2025.xlsx) | the additions column (†) and the rounding line (D) |
| Work-time study deck | Opus 5.5 | `SaDUDAyEP45E3gNRVZWjgp` | [Work_Time_Study_Analysis.pptx](formal/opus/runs/SaDUDAyEP45E3gNRVZWjgp/final/Work_Time_Study_Analysis.pptx) | the exact-label failures (B) |
| Work-time study deck | GPT-6.1-sol | `ehpELnbiUfAp5dFTeDNwt9` | [IT_Work_Time_Study.pptx](formal/gpt/runs/ehpELnbiUfAp5dFTeDNwt9/final/IT_Work_Time_Study.pptx) | the exact-label failures (B) |
| UAT test plan | Opus 5.5 | `AbudpM6dPVjwu2NSnwrZ6D` | [ProjMGR Tool - UAT Test Plan.xlsx](formal/opus/runs/AbudpM6dPVjwu2NSnwrZ6D/final/ProjMGR%20Tool%20-%20UAT%20Test%20Plan.xlsx) | the label and test-case failures |
| UAT test plan | GPT-6.1-sol | `4FAJ3AmGzujC6FZ67Krt9B` | [ProjMGR_Tool_UAT_Test_Plan.xlsx](formal/gpt/runs/4FAJ3AmGzujC6FZ67Krt9B/final/ProjMGR_Tool_UAT_Test_Plan.xlsx) | the label and test-case failures |
| GCP migration design | Opus 5.5 | `BVeKQk8ZWp6j2uxp9hsuGf` | [POC_Implementation_Guide_GCP.docx](formal/opus/runs/BVeKQk8ZWp6j2uxp9hsuGf/final/POC_Implementation_Guide_GCP.docx) | the document failures (C) |
| GCP migration design | Opus 5.5 | `BVeKQk8ZWp6j2uxp9hsuGf` | [Proposed_Architecture_GCP.pdf](formal/opus/runs/BVeKQk8ZWp6j2uxp9hsuGf/final/Proposed_Architecture_GCP.pdf) | the document failures (C) |
| GCP migration design | Opus 5.5 | `BVeKQk8ZWp6j2uxp9hsuGf` | [Proposed_Architecture_Summary.docx](formal/opus/runs/BVeKQk8ZWp6j2uxp9hsuGf/final/Proposed_Architecture_Summary.docx) | the document failures (C) |
| GCP migration design | GPT-6.1-sol | `NHSUKRMDDbYoJoGyWnpjcN` | [GCP_Modernization_POC_Runbook.docx](formal/gpt/runs/NHSUKRMDDbYoJoGyWnpjcN/final/GCP_Modernization_POC_Runbook.docx) | the document failures (C) |
| GCP migration design | GPT-6.1-sol | `NHSUKRMDDbYoJoGyWnpjcN` | [Proposed_GCP_Architecture.pdf](formal/gpt/runs/NHSUKRMDDbYoJoGyWnpjcN/final/Proposed_GCP_Architecture.pdf) | the document failures (C) |
| GCP migration design | GPT-6.1-sol | `NHSUKRMDDbYoJoGyWnpjcN` | [Proposed_GCP_Architecture_Summary.docx](formal/gpt/runs/NHSUKRMDDbYoJoGyWnpjcN/final/Proposed_GCP_Architecture_Summary.docx) | the document failures (C) |
