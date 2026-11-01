# GDPval diagnostic evaluation

A small diagnostic evaluation of two frontier models on ten GDPval v2 tasks, graded against
the public GDPval v2 rubrics with deterministic checks, an LLM judge and human review, with
documented pre-run adjudications for identified inconsistencies. `PLAN.md` describes the
methods, `preregistration.md` the grading rules and adjudications, `docs/status.md` the
current stage and every decision taken, and `docs/pilot_a_request.md` the (draft) request for
the first paid run.

## Architecture overview

| Module | Responsibility |
|---|---|
| `harness/launcher.py` | Trusted host process: configuration and image pre-flight, credential names (never values), budget reservation and settlement through the ledger, the single Task / single EvalLog / single sample contract, run provenance and the run ↔ ledger binding. `--dry-run` performs every check without calling a provider; `--real-run` is the only paid path. |
| `harness/task.py`, `harness/samples.py`, `harness/tools.py` | The Inspect Task: frozen system prompt, four tools (`bash`, `python`, `view_image`, `render_document`), docker sandbox with no network, per-task input allowlist verified by hash. Nothing from `private/`, `preregistration.md` or the grader enters the sandbox. |
| `harness/collect.py` | Collects `/output/final/` from the sandbox onto the host with fail-closed validation and writes the authoritative `run_outcome.json`. Collected files are never modified afterwards. |
| `harness/budget.py` | The one authority for cost: reservations, settlements (exact, estimated, held), stops, manual reconciliations; append-only JSON ledger with a persistent `ledger_id`. `harness/ledger_admin.py` is the minimal manual-reconciliation command. |
| `grading/run_grading.py` | Offline grading of one saved run: binds run directory, Inspect log and task id, reads rubric / reference / prompt from host paths, runs `grade_run`, optionally the judged pass behind the judge gate, and writes the provenance record. |
| `grading/grade.py`, `grading/extract.py`, `grading/checks_1137e2bb.py` | Deterministic grading: outcome gate and log join, extraction on copies (with the LibreOffice recalculation in the trusted image), the task-specific pipeline that produces PASS / FAIL / cannot_assess per rubric item with locatable evidence and error attribution. |
| `grading/judge.py` | Judge units (task requirement, criterion, independent reference, deliverable excerpt), the provider adapter with structured call records and a write-ahead call log, response parsing. |
| `grading/review.py` | Human-review materials: deliverable and criterion first, the judge verdicts sealed in a separate file, the independent-judgment template never overwritten. |
| `grading/costs.py` | Cost records per run from ledger settlements. |

## Evaluation workflow

generation (`launcher --real-run`, one Task, one sample, k = 1) → collection (`run_outcome.json`, deliverables under `runs_root/<uuid>/final/`) → deterministic grading (`run_grading`, judge items pending) → human review from the sealed materials → judged pass (`run_grading --judge`, one provider call per judge-only criterion) → cost reconciliation (`ledger_admin`). Every paid step is gated: explicit scope restatement, audit metadata, budget reservation, no open reservation or hold on the ledger, and for a judge pass the run's ledger binding.

## Execution commands

Dry run (no provider call; every check, the reservation logic and a voided reservation):

```
.venv/bin/python -m harness.launcher --dry-run --runs-root /abs/runs --ledger /abs/ledger.json     --task-id 1137e2bb-bdf9-4876-b572-f29b7de5e595 --model anthropic/claude-opus-5-5 --estimate-usd 5
```

Paid generation (example only; requires the approvals recorded in `docs/status.md`, a credential in `.env` read by the launcher, and an environment that is not in mock mode):

```
.venv/bin/python -m harness.launcher --real-run --runs-root /abs/runs --ledger /abs/ledger.json     --task-id <task_id> --model <provider/model> --estimate-usd <usd>     --confirm '<task_id>|<provider/model>|<usd>' --authorized-by '<name>' --authorization-ref '<status.md entry>'
```

Offline deterministic grading of a saved run (no provider call):

```
.venv/bin/python -m grading.run_grading --host-dir /abs/runs/<uuid> --eval-log /abs/runs/inspect_logs/<unit>/<log>.eval     --task-id <task_id> --out-dir /abs/grading/<uuid> --ledger /abs/ledger.json --unit-id '<generation unit id>'
```

Judged pass (paid; example only): add `--judge --judge-model <provider/model> --judge-estimate-usd <usd> --confirm-judge '<uuid>|<provider/model>|<usd>' --authorized-by '<name>' --authorization-ref '<ref>'`; a second judged pass of the same run needs `--rejudge`.

Manual reconciliation of a unit whose cost is unknown or held: `.venv/bin/python -m harness.ledger_admin resolve --ledger /abs/ledger.json --unit-id <unit> --resolution settled_amount --amount-usd <verified> --basis '<evidence>' --by '<name>'` (or `--resolution unresolvable`, which records the investigation and releases nothing); `... status --ledger /abs/ledger.json [--run-uuid <uuid>]` shows open reservations, holds and resolutions.

## Run artifacts

| Artifact | Location |
|---|---|
| Inspect log (trajectory, messages, tool events, usage) | `runs_root/inspect_logs/<unit>/*.eval` (one directory per execution; usage recovery after a failure reads only that directory) |
| Collected deliverables, `run.json`, `collection.json`, `run_outcome.json`, `ledger_binding.json` | `runs_root/<TaskState uuid>/` |
| Launcher records (pre-call provenance with commit, config sha256, prompt sha256, image id, authorization metadata; settlement) | `runs_root/launcher_records/` |
| Budget ledger (reservations, settlements, stops, holds, manual resolutions) and judge write-ahead call logs | `ledger.json`, `judge_logs/<run uuid>/*.jsonl` next to it |
| Grades and results (one results record and one set of grade rows per grading pass), judge call logs, provenance per pass, review materials | `out_dir/grades.jsonl`, `out_dir/results.jsonl`, `out_dir/judge_calls_*.json`, `out_dir/grading_run_<uuid>_<pass>.json`, `out_dir/review/` |

Runs, ledgers and grading outputs are kept outside the repository (or under the gitignored `logs/`); raw model outputs are immutable once collected.

## Grading interpretation

Each rubric item is graded `pass`, `fail` or `cannot_assess` from evidence that names a file, sheet, cell or paragraph. A confirmed violation of the item's own text gives FAIL even when another input could not be assessed; an unreliable required input without a confirmed violation gives `cannot_assess`; every required comparison must be completed before a PASS. Attribution separates model-caused outcomes (`model_caused`, `model_caused_missing`, `model_caused_corrupt`) from grader-side ones (`grader_extraction`, `grader_caused_recalculation`, `grader_caused_extraction`) and `unknown`; judge-only items carry `error_class` `provider_error`, `judge_parse_error` or `not_attempted` when they could not be judged. Critical criteria (`C1` line flags, `C2` SKU summary, `C3` Word summary for the pilot task) fail when any of their items fails and are `not_confirmed` while items are pending or unassessable. The rules and every adjudication are in `preregistration.md`.

## Grading pass versioning

`grade_run` appends one results record and one set of grade rows per pass and never overwrites: a deterministic-only pass (`pass_kind: deterministic_only`, judge items `pending_judge`) and later judged passes (`deterministic_plus_judge`, `supersedes_pass` naming the previous pass). `judge_completeness` is `complete`, `partial` (a provider error, parse error or not-attempted criterion) or `none`; a judge unit whose write-ahead log holds a started event without a terminal event is UNKNOWN. A report uses exactly one pass per model run: `grading.grade.select_pass` (with the run's persisted judge attempts from the ledger and the write-ahead logs, as `grading.run_grading.report_selection` assembles them) returns the latest judged pass with its basis and warnings; a partial latest pass is selected and flagged, never hidden behind an older complete one; when the latest judge attempt is UNKNOWN, open or held and produced no pass, the selection is `blocked` (no current pass, history kept) until it is reconciled. The selection fails closed: `report_selection` resolves the run's `ledger_binding.json` and opens the bound ledger itself, and is `blocked` when the binding is missing, names another run, or a supplied ledger is not the bound one; `selected_grades` requires the loaded attempt history and returns `blocked` with no rows without it; `select_pass` called without attempts is historical inspection (`authoritative: false`), never a report input; `authoritative_selection` is the statistics entry (selection plus the selected pass's rows, none while blocked). Two passes of one run are never two samples.

## Budget and safety

Every paid unit is claimed atomically on the ledger before it starts (`BudgetLedger.reserve(claim=True)`: inside one lock, no other open reservation, the unit not already claimed, no stop condition) and settled from the provider-reported usage afterwards. A unit whose cost is not fully known - a model call without reported usage, an exception after calls were made, a judge batch with a missing or uncertain usage - is settled at the larger of the priced known part and the reservation, flagged `estimated`, and puts a persistent hold on further paid starts until a human reconciles it (`ledger_admin resolve` with the verified amount; `unresolvable` releases nothing). Known usage is recovered from durable evidence before such a settlement, bound to the execution: for generation, only Inspect logs in the execution's own log directory (`inspect_logs/<unit>/`) whose eval task and model match the unit, each (eval id, sample, epoch) counted once; a log that cannot be attributed is excluded and the settlement is flagged `attribution_uncertain`; for judge calls, the judge write-ahead log. What cannot be recovered stays unknown and is never counted as zero. A judge batch stops sending requests after the first call whose usage cannot be accounted (remaining criteria `not_attempted`). Open reservations of unknown outcome, UNKNOWN judge calls, holds, recorded stops (two engineering failures of one class, a unit above twice its estimate, the pilot ceiling) all refuse new paid starts and survive restarts because they are ledger events; a unit that was claimed and never settled is never re-run until reconciled. Cost records read the ledger's effective settlement (manual reconciliations applied), never a raw event. The reservation, the per-sample cost limit and the pilot ceiling are harness controls, not caps on the provider's bill; every pre-run cost figure is a forecast until reconciled with the account.

## Reproducibility

Private inputs that are not tracked: `data/inputs/<task_id>/` (task inputs), `data/prompts/`, `private/rubric/`, `private/gold/`, `private/checks/recalc/` (independent recalculations), the dataset parquet, and `.env` (credentials, read only by the launcher). Versions recorded with every run and grading pass: the code commit (`git rev-parse HEAD`, with a dirty flag), `config.json` sha256, the system prompt sha256 (checked against the config at launch), the sandbox image id and platform, the grader version (`grading.grade.GRADER_VERSION`, checked against `config.grading.grader_version` at grading), the judge id. Tests run through `harness/tests/run_isolated.sh` (minimal environment, external working directory, `INSPECT_DISABLE_MODEL_API=1`, mockllm); the unit suites are `harness/tests/test_*_unit.py`, `harness/tests/test_launcher_regressions.py`, `grading/tests/test_layout_regressions.py` and `grading/tests/test_grading_chain.py`; the mock integration regressions are `harness/tests/regress_*.py`, `grading/tests/regress_grading_cli.py` (which produces a fresh run through the real Inspect + docker + mockllm path) and `grading/tests/regress_recalc_docker.py`.

## Limitations

Everything above the provider boundary is verified with mockllm and fake adapters only: the real providers' usage fields, cache accounting, stop reasons, refusal behaviour and the judge's real response format are unverified until the first authorized paid run. Model and judge ids, reservations and the pilot budget are proposals in a DRAFT configuration until `freeze-v1`. The deterministic grader covers one task; the other nine tasks' graders are not implemented. No step was reviewed by an industry domain expert.

## Rebuilding the data from a clean clone

The repository tracks the records that identify the data (`data/dataset_revision.json`,
`data/selected_tasks.json`, `data/download_verification.json`, `data/manifest.json`) and
the scripts that fetch it. The dataset copy, task inputs, prompt texts, expert
deliverables, rubrics, and pre-staged web resources are not tracked. Requirements: `uv`
(0.12 was used), Python 3.11, and network access to huggingface.co; no credentials.

```
uv sync --frozen
.venv/bin/python scripts/fetch_dataset.py --revision-file data/dataset_revision.json \
    --out data/gdpval.parquet
.venv/bin/python scripts/resolve_tasks.py --parquet data/gdpval.parquet \
    --out data/selected_tasks.json \
    --deep b5d2e6f1 f841ddcf 47ef842d 1137e2bb c3525d4d \
    --supplementary 7b08cd4d 7d7fc9a7 2ea2e5b5 c357f0e2 a45bc83b
.venv/bin/python scripts/download_materials.py --parquet data/gdpval.parquet \
    --tasks data/selected_tasks.json --revision-file data/dataset_revision.json \
    --log data/download_verification.json
```

Step 2 downloads the parquet at the recorded dataset revision and stops if its SHA-256
differs from the recorded value. Step 3 resolves the ten task ids. Step 4 downloads the
task inputs to `data/inputs/<task_id>/` and the expert deliverables to
`private/gold/<task_id>/`, writes the rubrics to `private/rubric/<task_id>.json` and the
prompt texts to `data/prompts/<task_id>.txt`, and verifies every downloaded file against
the hash Hugging Face records at that revision. On 2026-10-30 this sequence was run in an
empty directory with fresh package and Hugging Face caches; it reproduced
`data/selected_tasks.json` and the ten prompt texts byte for byte.

Optional steps. `scripts/fetch_gcp_resources.py --parquet data/gdpval.parquet --task-id
a45bc83b-22f9-4def-8d89-9c5661b2b86f` re-fetches the public Google Cloud pages and icon
packs used by the design task (about 23 MB); live pages change, so the hashes in
`data/manifest.json` identify the 2026-10-29 fetch rather than a reproducible download.
`scripts/build_manifest.py` rebuilds the manifest from the records.
`scripts/recalc/run_all.py` runs the independent recalculations (needs the inputs and,
for the comparisons with expert deliverables, `private/gold/`);
`scripts/recalc/test_7d7fc9a7_quantization.py` runs the quantization regression checks.

## Sandbox image

The model under test runs in a locally built Docker image (`docker/sandbox/Dockerfile`,
`docker/sandbox/requirements.txt`). The harness refers to that image by its **full local
image ID** (`sha256:<64 hex>`), never by tag: `harness/compose.yaml` (`image:`),
`config.json` (`sandbox.image_id`) and the trusted LibreOffice conversion path in
`grading/extract.py` must all carry the same ID, and the launcher pre-flight refuses to
start when they differ, when the daemon does not know the ID, or when the image platform
differs from `sandbox.platform`. The tag `gdpval-sandbox:stage2` is informational only
(the local daemon has answered tag lookups with "No such image" while the tag was listed).

To rebuild and re-pin:

```
docker build -f docker/sandbox/Dockerfile -t gdpval-sandbox:stage2 docker/sandbox   # on a host whose platform matches sandbox.platform
docker image inspect gdpval-sandbox:stage2 --format '{{.Id}}'      # -> sha256:<64 hex>
```

Write that ID into `harness/compose.yaml` (`image:`) and `config.json`
(`sandbox.image_id`, `sandbox.image`), recompute `sandbox.compose_sha256` as the SHA-256 of
the compose file, and run the launcher `--dry-run` pre-flight. A local image ID identifies
the image content on this daemon only; it is not resolvable on another machine until the
image is pushed or exported, so the cross-machine reference (`sandbox.image_digest`) is
pinned at freeze.

## How this repository was produced

Research design, grading rules, adjudications, and every approval are the author's.
Claude Code (Anthropic) implemented the scripts, drafts, and documentation under those
instructions. OpenAI Codex performed limited-scope, read-only independent re-checks of
the stage-1 materials and recalculations; the author reviewed its findings before any
change was made. No step was reviewed by an industry domain expert.

## References

- GDPval paper: Patwardhan et al., "GDPval: Evaluating AI Model Performance on Real-World
  Economically Valuable Tasks", arXiv:2510.04374 — https://arxiv.org/abs/2510.04374
- GDPval dataset (v2 rubrics and expert deliverables), revision
  `11e7900cdcac61bc4daf59e65feb238acda98fbf` — https://huggingface.co/datasets/openai/gdpval
- GDPval automated grading service (not used in this evaluation) — https://evals.openai.com
