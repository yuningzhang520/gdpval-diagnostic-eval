# Submission page (`site/`)

One static page in five sections: findings (task results, key terms), results (task verdicts after review with each
failed task's failure source, what author review changed), failures (four display categories of the confirmed
failures, three example cards with evidence), the data opportunity, and method and limits (with grader reliability:
the author-review result and the blind audit). Detail sits in expandables.

## How it is built

`index.html` and `data/metrics.json` are generated; do not edit them by hand. Copies of the run-store records the
build reads are in `results/` (hash-checked against the inputs listed in `data/metrics.json`). The evidence crops in `img/` are rendered
from the deliverables by `render_crops.py`.

```
.venv/bin/python site/render_crops.py         # evidence crops of cards A-C (Docker + the sandbox image)
.venv/bin/python site/build.py                # draft build: visible banner listing pending blocks and failed checks
.venv/bin/python site/build.py --final        # refuses while any block is not approved or any check fails
.venv/bin/python site/build.py --preview PATH # banner-free rendering outside site/ for review
```

Every displayed number is read at build time from its canonical source and written to `data/metrics.json` with a
descriptive source and verification status, so the page updates after each human adjudication:

| On the page | Canonical source |
|---|---|
| tasks, models | `data/selected_tasks.json`, `config.json` |
| task verdicts and failure labels, before / after review | `~/turing-eval-runs/formal/human_layers_summary.json`, `formal/human_review/*.jsonl`, `analysis/human_taxonomy.json`; labels in `content.json`, checked against the confirmed items |
| rubric items, critical requirements | `~/turing-eval-runs/analysis/failures-v1/all_items.csv`, the critical membership in the human-layer summary |
| author-review result, review scope | `~/turing-eval-runs/analysis/critical_adjudication.csv`, the adjudication records, `~/turing-eval-runs/analysis/failures-v1/all_items.csv` |
| categories, failure types, cards | `analysis/human_taxonomy.json` grouped by the `content.json` categories, cross-checked against the adjudication records |
| failure source (in the prompt / rubric only / additions rule) | `analysis/requirement_source.json` (tags `prompt` / `rubric` / `rule`), prompt quotes checked against the task prompts in the local run store |
| weekly sales expert file (worked example) | `docs/expert_gold_fail_audit.md`, the ST% example recomputed from the task input |
| pilot size and cost (estimate) | `content.json` `data.pilot_plan`; GDPval's average expert hours per task from the GDPval paper (arXiv:2510.04374) |
| AI draft | `analysis/codex_failure_review/diagnosis.csv` (AI-assisted draft) |
| grader agreement, false-pass check | `~/turing-eval-runs/labeling/formal-v4-reveal/reveal_*.json` |
| judge status | `preregistration.md` 1.25 and the two `docs/status.md` records it names |
| run configuration, dates, limits reached | `config.json` at the two freeze tags, the 20 formal Inspect logs, run inventories, the formal judge registry |
| weekly sales example | the task's rubric under `private/rubric/` (not published) and the item bundle |
| crops | `img/crops.json` (deliverable hashes checked against the artifact manifests; shown cell text, chart labels or paragraph words checked in the rendering) |
| cost | every paid-workload ledger (`ledger.json` settlements) |

Reader copy lives in `content.json`; each block carries a status (`draft`, `approved`). The build inserts numbers as
`{{token}}` placeholders; no number is typed into the copy. The final build refuses while any block is not `approved`
or any build check fails: taxonomy items without a confirmed record; categories not covering every failure type once;
a not-re-graded item outside a failing critical requirement; a failing task cell without a label, or a label whose
failure types differ from the confirmed items; rubric-item totals that disagree; card items out of their type or
grader record; run settings that differ from the frozen config; an evaluation run that reached a limit; crop hashes that
differ; the judge verdicts still provisional; requirement-source tags that do not cover exactly the confirmed items,
quote the prompt inexactly, or are not approved by the author; a forbidden term on the page (the report-only terms
listed in `build.py`).

## Deploying

`.github/workflows/pages.yml` publishes the committed page to GitHub Pages
(https://yuningzhang520.github.io/gdpval-diagnostic-eval/): `index.html`, `img/` and `data/` only, as committed, with no
build step (the build needs the local run store). It runs on a push to `main` that touches those files, or by hand; it
refuses a draft build (a banner, `"build"` other than `"final"`, a pending block or a warning in `data/metrics.json`) and
is skipped while the repository is private. Before deploying: run the final build, commit `index.html`, `img/` and
`data/metrics.json` together, and run the publication checks (no secrets, no `private/`, `plan/`, `.env`, parquet or
sealed labels in the repository or its history; every evidence link resolves inside the repository).
