# GDPval diagnostic evaluation

A small diagnostic evaluation of two frontier models on ten GDPval v2 tasks, graded against
the public GDPval v2 rubrics, with documented pre-run adjudications for identified
inconsistencies. `PLAN.md` describes the methods, `preregistration.md` the grading rules
and adjudications, and `docs/status.md` the current stage.

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
