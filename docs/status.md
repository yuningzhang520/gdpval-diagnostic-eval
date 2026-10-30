# Status

Current stage: **Stage 3b infrastructure items 8, 7, 3, 4, 5 done and mock-verified; hard
stop; awaiting the human's A/B model decision and approval of the remaining Stage 3b work
(2026-10-30).** Stage 3a is committed as `395d1da626c12fe5b5b0443c0737a8c02b2b614b`;
the Stage 3b work is uncommitted. Stage 2 is committed as
`1941d4ac69566fdbc0a6dff821de57664e84f284` on `main` (pushed). Stage 3a made no model,
judge or paid call (the `.env` file does not exist, so the permitted models-list calls were
skipped); nothing is frozen; the pilot has not started. Second-round approvals of
2026-10-30 (17 critical criteria, f841ddcf precision table, 7d7fc9a7 reconciliation rule,
system prompt additions, run parameters, model-candidate strategies, 25 USD pilot ceiling)
are recorded in section "Stage 3a"; 1137e2bb C2 and the final A/B ids stay PENDING.
Details in section "Stage 3a".

Earlier header, kept for the record: **Stage 2 closeout accepted in substance; execution-budget attribution
policy corrected; pre-commit check done, committed to main as the Stage 2 commit (2026-10-30; hash reported in chat).**
The second narrow review kept B4 and I4 closed but found B1–B3 only partially closed;
the closeout fixed them (section "Stage 2 closeout after the second narrow review").
A final correction (section "Execution-budget attribution policy") makes a run that
exhausted a pre-configured budget grading-eligible when its collection is `complete` or
`no_files_confirmed`; execution errors and unrecovered collection faults stay
ineligible. The earlier closure claims below are historical. The Stage 2 commit was made
and pushed to origin with the human's approval; no freeze, Stage 3 work, real model/judge
call, or business-grading change was made.

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

## Stage 2 — toolchain validation (2026-10-30)

Guard settings during this stage: `INSPECT_DISABLE_MODEL_API=1` is set by
`harness/smoke.py` before Inspect loads (inspect_ai 0.3.286 exempts only `mockllm`; every
other provider raises `RuntimeError`). Dummy credentials
(`ANTHROPIC_API_KEY=dummy-test-key-not-real-0001` and two more) are placed in the harness
process environment so the in-sandbox probe can show they do not reach the sandbox. Both
guards are for smoke tests only and are lifted for the pilot (the pilot runner must not set
`INSPECT_DISABLE_MODEL_API`; real keys come from `.env` via the launcher).

### Exit conditions and results

0. **Clean rebuild from GitHub — passed.** `gh repo clone` into an empty directory under the
   session scratch area, `git checkout 2f2f9c27…`, fresh `UV_CACHE_DIR` and `HF_HOME`,
   then the README sequence (`uv sync --frozen`, `fetch_dataset.py`, `resolve_tasks.py`,
   `download_materials.py`). Parquet sha256 `f8422fab…ae0202` matched; 32/32 files
   verified; the ten rebuilt prompts and `data/selected_tasks.json` are byte-identical to
   the project's copies.
1. **Isolated build context — done.** `docker/sandbox/` holds `Dockerfile`,
   `.dockerignore` (admits only `Dockerfile` and `requirements.txt`) and the pinned
   `requirements.txt` (31 pins compiled by `uv pip compile` for linux/aarch64, Python
   3.11; `pymupdf` pinned to 1.x). Image `gdpval-sandbox:stage2`, id
   `sha256:18cde712cde1867c94b8f23ae1f4066b0aa3146fdbd8deac70d1b4aa043ea9ee` (arm64,
   python:3.11-slim-bookworm base, LibreOffice 7.4.7.2 calc/writer/impress, python3-uno,
   poppler-utils, fonts). Dockerfile sha256 `e75210fe71bd8ac88c8169c124b7895c8c337a3d555bd280d8b58c9903811587`; requirements.txt sha256 `a44ef1b4e1904bab57a7ccc8328d76d8fd0580c423c7328afd124c227c04cf0c`.
   Image content check (plain `docker run`, not the Inspect path): no parquet, rubric,
   gold, preregistration, plan or .env files anywhere in the image.
2. **Explicit Sample.files allowlist — done.** `harness/samples.py` lists every staged
   file from `data/manifest.json` (role `input`, same task id) and, for `a45bc83b…`, from
   `data/resources/<uuid>/resources.json`; `check_allowlist()` rejects globs, any path
   outside `data/inputs/` or `data/resources/`, any path containing `private/`, `plan/`,
   `preregistration`, `gdpval.parquet`, `scripts/`, `harness/`, `docs/`, `.env`, and any
   other task's id. Result for the ten tasks: 43 staged entries (one to six inputs per
   task; 27 for the GCP task = 2 inputs + 11 HTML + 11 extracted text + 3 icon zips).
3. **Isolation verified at two boundaries.**
   - Model-visible boundary (inside the real Inspect sandbox, via mockllm-issued `bash`
     calls dispatched by Inspect): `/Users`, `/private/gold`, `/private/rubric`,
     `/workspace/private`, `/workspace/preregistration.md`, `/workspace/plan`,
     `/data/gdpval.parquet`, `/workspace/scripts`, `/workspace/harness`, `.env` paths and
     `/run/secrets` are all absent; a filesystem-wide `find` for parquet, rubric, gold,
     preregistration, plan and `.env` names returns nothing; `/proc/mounts` shows only
     Docker's `/etc/resolv.conf`, `/etc/hostname`, `/etc/hosts`; the environment holds no
     credential-like variable (the only hit, `GPG_KEY`, is the public signing-key
     fingerprint baked into the python base image) and zero occurrences of the dummy
     marker *[the probe that produced this printed matching variables with their values
     into the tool result and the log; finding I4, fixed in the fix round — the
     observation stands, the probe did not]*; `CapEff` and `CapBnd` are
     `0000000000000000`; TCP to 1.1.1.1:53 and
     8.8.8.8:443 and DNS for huggingface.co fail; the only interfaces are `lo` and
     unconfigured kernel tunnel devices.
   - Container configuration (host-side `docker inspect` of a sandbox kept alive with
     `sandbox_cleanup=False`, then removed with `inspect sandbox cleanup docker`):
     `NetworkMode=none`, network `none` only, no ports, `CapDrop=[ALL]`, `CapAdd=null`,
     `SecurityOpt=[no-new-privileges:true]`, memory 3 GiB, 2 CPUs, `PidsLimit=512`,
     `Init=true`, `Privileged=false`, `Binds=null`, `Mounts=[]`, env without credentials.
   - Trusted-side boundary (host-side tools): `harness/tools.py` performs every file
     operation through `sandbox().exec()` / `sandbox().read_file()` and never opens a host
     path (static check: no `open()` in the module; the `os.path` calls are inside the
     script string executed in the sandbox). Runtime check through the Inspect tool
     dispatch: `view_image("/Users/yuning/turing-th/harness/fixtures/sample.png")` and
     `render_document("/Users/yuning/turing-th/README.md")` return "no such file in the
     sandbox" / "not a file" although both files exist on the host, and
     `view_image("/workspace/private/secret.png")` fails the same way. The collector
     (`harness/collect.py`) opens host paths only to write collected copies under
     `logs/stage2/runs/`; the scorer stub never passes private data back to the model.
     *[Overturned in part by the independent re-check (B1): the collector of this
     version derived the host write path from the unvalidated sandbox listing, checked
     it by string prefix only, hashed symlink targets, and opened destinations for
     overwrite. Rewritten in the fix round; see "Stage 2 fix round".]*
   - Other tasks' artifacts: one compose project per sample, no volumes; outputs leave
     only through the collector onto the host.
4. **Dummy credentials, network, image, mounts — done** (see 3; no real key was read or
   passed; `.env` does not exist in the working tree).
5. **Trusted recalculations — passed.** All eight recalculation scripts rerun on the host
   (`scripts/recalc/run_all.py`); `test_7d7fc9a7_quantization.py` passes all 10 checks,
   total prepaid 4/30 = 929,354.31 on both paths. No recalculation script was run inside
   the model sandbox; sandbox tool capability was tested only with the synthetic fixtures
   in `harness/fixtures/` (generated by `make_fixtures.py`; no task answers).
6. **Artifact collection, file handling, rendering, LibreOffice, end-to-end chain.**
   Mock/stub used: `mockllm/model` with `custom_outputs` built by
   `ModelOutput.for_tool_call` (scripted tool calls) and `ModelOutput.from_content` (final
   message); solver chain `system_message` → `use_tools([bash, python, view_image,
   render_document])` → `generate(tool_calls="loop")`; scorer = collector; Task
   `cleanup` = collector fallback. Every tool call appears as a `ToolEvent` in the Inspect
   log, i.e. it went through Inspect's tool dispatch; the test script never calls
   `sandbox.exec` itself. Scenarios and results (logs in `logs/stage2/inspect/`, collected
   files and `collection.json` under `logs/stage2/runs/<scenario>/`):
   - `normal` (13 tool events): Sample.files injection confirmed (fixture content read
     back); `python` tool wrote `.xlsx`/`.docx` to `/output/final/`; `soffice` inside the
     sandbox converted the docx to PDF and recalculated the fixture workbook (formula
     `=SUM(C2:C4)` had no cached value on input; cached 43.75 after recalculation; the
     literal 42 untouched); `view_image` returned the PNG (5,182 bytes, image content
     stored in the log as an attachment); `render_document` rendered pptx, docx, pdf page
     2 and xlsx; collector returned 3 files with sandbox-side and host-side sha256 equal.
     *[Three `normal` logs exist. The first (08:21 UTC, 11 tool events) carries four
     argument-validation errors on `bash` calls (the script passed `cmd` instead of
     `command`) and does not count as a complete pass; the statements above rest on the
     08:23 and 08:29 UTC logs (13 tool events each). The re-check also showed that the
     collector's "passed" covered the happy path only (B2) and that `render_document`'s
     failure path returned a stale image (B4); both fixed in the fix round.]*
   - `tool_timeout` (`bash(timeout=5)`, `sleep 20`): tool error "Command timed out before
     completing." with the partial output `start`; the next call ran in the same
     container; sample completed and was scored.
   - `sample_timeout` (`time_limit=25`, a `sleep 120` after writing `early.txt`): sample
     ended with `limit=time`; the scorer still ran and collected `early.txt` (11 bytes,
     intact) before container cleanup. The cleanup-hook fallback (collection when the
     scorer does not run) was therefore not exercised — **not verified**. *[In this
     version a `collection.json` written by a failed or partial scorer pass blocked the
     cleanup hook entirely (B2/B3); the fix round makes the hook resume any pass that did
     not reach `complete`. The resume path is now exercised in the Inspect chain; the
     scorer-never-ran path still is not.]*
   - `resources` (GCP snapshot staged through the allowlist): 27 files present; the three
     icon-zip sha256 values computed inside the sandbox equal the manifest values;
     `unzip` works (category pack: 26 SVG, 26 PNG); extracted text, HTML, the input PDF
     and DOCX are readable.
   - `pivot` (see 7): a real PivotTable was created inside the Inspect sandbox and
     collected intact (sha256 equal on both sides).
   - Trusted container (plain `docker run --network none` with a scratch mount, same
     image): LibreOffice recalculation fills missing cached values (fixture: 4 formulas,
     0 cached → 4 cached) and reproduces Excel's cached values on a real input
     (`Fall Music Tour Ref File.xlsx`: 22 formulas, 22 equal, 0 different), which gives
     the "wrong formula / missing cached value / recalculation failed" separation;
     docx, pptx, pdf and xlsx render to PNG (the 154-page render of the sales-analysis
     gold workbook also worked); a LibreOffice round-trip of that gold workbook keeps its
     7 pivot parts.
   Not verified in this stage: timeouts inside LibreOffice conversions specifically
   (only the generic tool timeout was tested), the cleanup-hook fallback, behaviour under
   memory pressure, concurrency above one sample.
7. **PivotTable object — creatable (time box used: about 25 minutes).** Debian's
   `python3-uno` (added to the image; importable from `/usr/bin/python3`, not from the
   image's default `python3`) drives a headless `soffice` listening on loopback; a
   DataPilot built on the Data sheet and exported with the `Calc MS Excel 2007 XML` filter
   yields `xl/pivotTables/pivotTable1.xml` and `xl/pivotCache/*` with a worksheet source
   (`Data!A1:D13`) and SUM data fields; openpyxl reads it. This worked both in a trusted
   container and inside the Inspect sandbox (`network_mode: none`, all capabilities
   dropped). Not verified: whether Excel opens and refreshes the exported pivot (no Excel
   available). No `environment_unsupported` ruling is made; the decision on `b5d2e6f1…`
   C3 and item 12 stays with the human (section "Next stage").
8. **GCP snapshot — verified; reproduction limit recorded.** All 14 resource files match
   the manifest sha256 on the host; the three zips match inside the sandbox. Re-fetching
   from the public URLs today: `category-icons.zip` is byte-identical; the three HTML
   pages tried (`docs`, `solutions/web-hosting`, `load-balancing`) differ from the snapshot
   (dynamic pages, sizes 289,960 vs 290,142; 2,315,713 vs 2,081,653; 2,349,210 vs
   2,115,141 bytes). The 2026-10-29 snapshot, identified by the manifest hashes, is the
   fixed artifact for both models; refetched pages were written to scratch only and not
   substituted. Form tested in the sandbox: HTML + extracted text + zips (the form
   decision in `preregistration.md` 3.10 stays PENDING).
9. **Pending pilot verification (needs a real model):** tool-schema compatibility and
   image delivery to the provider (`ContentImage` from `view_image`/`render_document`),
   token and message limits, provider-side retry behaviour, real agent behaviour under
   the shared prompt, cost per task, and whether a model discovers the UNO route to a
   PivotTable on its own.

### Added in this stage (Stage 2 commit)
`docker/sandbox/{Dockerfile,.dockerignore,requirements.in,requirements.txt}`;
`harness/{__init__,samples,tools,collect,task,smoke}.py`, `harness/compose.yaml`,
`harness/system_prompt_draft.txt` (draft only; the frozen prompt is a Stage 3 item),
`harness/fixtures/make_fixtures.py`, `harness/fixtures/pivot_uno.py` (generated fixtures
are ignored); `inspect-ai` added to `pyproject.toml`/`uv.lock`; `.gitignore` entries for
generated fixtures; `preregistration.md` section 4 item 5 (rounding-policy decision
registered, PENDING). Inspect logs and collected smoke outputs live under `logs/stage2/`
(ignored). Fix round (same day): `harness/collect.py`, `harness/tools.py`,
`harness/task.py`, `harness/smoke.py` rewritten or changed as described in "Stage 2 fix
round"; new `harness/tests/{__init__,test_collect_unit,regress_inspect}.py` and
`harness/tests/run_isolated.sh`; regression logs under `logs/stage2_fix/` (ignored).

### Engineering notes and limits
- The sandbox runs as root with all capabilities dropped and no network; a non-root user
  was not configured (Inspect copies files as the container user; hardening left as a
  decision).
- `inspect_ai` 0.3.286 sample `time_limit` lets the scorer run after the limit, which is
  what the collector relies on; this is an observed behaviour of this version, not a
  documented guarantee, so the cleanup-hook fallback stays in place.
- Docker Desktop allocates 8 CPUs / 7.75 GiB to its VM; with `mem_limit: 3gb` per sandbox,
  concurrency above two is not advisable without evidence.
- Host-side `uv add inspect-ai` pulled 0.3.286; the dependency set is now larger than the
  stage-1 reading tools (reflected in `uv.lock`).

## Stage 2 fix round — independent re-check findings (2026-10-30)

An independent read-only re-check of the Stage 2 harness (coding-agent review; the
workflow is described in the README) reported four blocking findings (B1–B4) and five
further findings (I1–I5), each reported with a reproduction through the Inspect chain.
This round fixed B1–B4 and I4 only, added targeted regressions, and registered I1–I3 and
I5. No grading rule, Stage 1 recalculation, harness design, prompt, sandbox image or
compose setting changed. No model, judge or paid API call was made.

### Findings and what they overturn

- **B1 — collector trusted the sandbox listing.** `collect.py` joined the host write path
  from the unvalidated `path` field (`os.path.relpath` + `os.path.join`), so a listing
  entry such as `/output/final/../../tmp/x/sentinel.txt` resolved outside the collection
  directory; the containment check was a string prefix; symlinks inside `/output/final`
  were hashed and read through their targets; destinations were opened with `"wb"`
  (overwrite). Overturns the Stage 2 statement that the collector only writes collected
  copies under the run directory: that held for the files observed, not by construction.
- **B2 — enumeration failure read as "no files".** A failed or unparsable listing became
  an empty list; `all([])` is true, so `all_intact` was `true` with `file_count` 0, the
  state a model that wrote nothing would produce. A `collection.json` written by such a
  pass also stopped the cleanup hook. Overturns "artifact collection — passed": it passed
  on the happy path only.
- **B3 — collected outputs could be overwritten.** The smoke runner used one fixed
  directory per scenario (`logs/stage2/runs/<scenario>/<sample>/epoch1/`), so a repeated
  run of the same scenario overwrote the earlier run's collected files; no run id bound a
  record to its model, task and epoch. The project rule "raw model outputs are immutable
  once collected" was not enforced by the harness.
- **B4 — `render_document` could return a stale image.** The conversion directory was
  derived from the input path (`/tmp/render_<sha1(path)>`) and reused; the only check was
  that a PDF existed. When LibreOffice fails it exits 0 and writes nothing (verified: a
  truncated DOCX gives "source file could not be loaded", exit status 0), so a second
  call on a now-corrupt file returned the first call's PDF and image. Overturns
  "`render_document` rendered pptx, docx, pdf, xlsx" only for the failure path; the
  renders of valid inputs stand.
- **I4 — the environment probe printed values.** `PROBE_FS` ran `env | grep -i -E
  'key|token|secret|password'`, which writes matching variables with their values into
  the tool result, the `ToolEvent`, the eval log and the model-visible message. In the
  Stage 2 logs the only value printed was the python base image's `GPG_KEY` fingerprint
  (public); with a real key present the probe would have logged it. The Stage 2
  observation "no credential-like variable" stands; the probe did not.
- **I1** (allowlist: path and symlink checks and a hash of every model-visible file at
  staging time), **I2** (`view_image`: decode the bytes and bound pixel dimensions, not
  only the byte count), **I3** (synthetic counter-examples for the three-way "wrong
  formula / missing cached value / recalculation failed" separation), **I5** (model
  configuration, concurrency, image digest). Registered, not implemented in this round:
  I1 and I2 are due before the first real-model pilot run, I3 before the first full
  pilot grading, I5 is Stage 3 configuration fixed before `freeze-v1`.

### Fixes

- `harness/collect.py` (rewritten). Sandbox-side `LIST_SCRIPT` (l. 51–119): `lstat`
  classification, `os.walk(followlinks=False)` with symlinked directories removed from
  descent, regular files hashed with `O_NOFOLLOW`, symlink / broken symlink / fifo /
  socket / device entries reported as `skipped` with a reason, item-level errors
  reported, root state (`dir`, `missing`, `symlink`, `not_a_directory`, `unreadable`)
  reported; files above the size limit are listed with `sha256: null` and not hashed.
  Host side: `validate_sandbox_path` (l. 146) checks the raw string before any
  normalisation (prefix `/output/final/`, no empty, `.` or `..` segment, no NUL,
  `normpath` identity); `_prepare_host_root` (l. 165) requires `host_dir/final` to be a
  real directory and takes its real path; `_host_destination` (l. 182) creates
  intermediate directories one segment at a time, refusing any symlink or non-directory
  component, and requires the parent's real path to be inside the root; destinations are
  created with `O_CREAT | O_EXCL | O_NOFOLLOW` (l. 384) and made read-only (l. 394) so
  downstream steps work on copies. Every rejected entry is recorded with its reason and
  does not affect other files.
- Status model (`_status`, l. 221): `listing_failed` / `no_files_confirmed` / `complete`
  / `partial` as defined in the module docstring; `all_intact` is true only for
  `complete`; `harness_error` is true for `listing_failed` and `partial`;
  `outcome_class` names `harness_collection_error` explicitly so a collection failure
  enters the run result as a harness error, never as model non-delivery. Per-file
  outcomes (`collected`, `already_collected`, `error` with reason: `read_failed`,
  `integrity_mismatch`, `oversized`, `file_limit`, `total_limit`,
  `time_budget_exceeded`, `conflict_existing_differs`, …). Limits are explicit and
  recorded in every record (`LIMITS`, l. 39): 200 files, 64 MiB per file (below
  Inspect's 100 MiB `read_file` limit so the oversized status is ours), 512 MiB total,
  600 s per pass, 120 s listing timeout.
- Run binding and resume: `make_task` (`harness/task.py` l. 26–34) assigns a unique run
  id (`<UTC stamp>-<8 hex>`) or takes one, creates `runs_root/<run_id>/run.json`, refuses
  a directory that belongs to another run id, and binds scorer and cleanup to that id;
  each sample collects into `<run_dir>/<task id>/epoch<n>/`. `collection.json` records
  `run` = {run_id, model, task_id, epoch}, the merged file table and the full `passes`
  history. A later pass of the same run skips a host file whose hash equals the sandbox
  hash (`already_collected`), records `conflict_existing_differs` without touching a
  differing file, collects files that failed earlier, and keeps every earlier pass's
  status and errors. A record from another run id is never modified
  (`collection_conflict_<stamp>.json`, l. 284). The cleanup hook (l. 419) resumes
  whenever the existing record is not `complete`; a failed or partial marker no longer
  blocks it.
- `harness/tools.py` `render_document` (l. 21–72, 105–149): each call converts into its
  own `tempfile.mkdtemp(prefix="render_")` directory; the converter's exit status is
  checked; the exact expected PDF must exist, be non-empty, open in PyMuPDF and have at
  least one page; the PNG must exist and be non-empty in the sandbox and carry the PNG
  signature on the host; every failure returns a specific `ToolError` and removes the
  temporary directory inside the script (`finally`); on success the host removes the
  directory after reading the image. There is no earlier PDF or image to fall back on.
  `view_image` is unchanged (I2 pending).
- `harness/smoke.py` (I4): `PROBE_FS` (l. 71–74) reports only whether each of the three
  test variables is present, the count of environment values containing the dummy
  sentinel, and the count of values matching known key prefixes; no name=value line is
  printed. `scrub_inherited_credentials()` (l. 20) removes inherited credential-like
  variables from the harness process before Inspect loads and reports a count only. The
  runner now calls `make_task(samples, runs_root)` and records the run directory.
- `harness/tests/run_isolated.sh`: launches a module with `env -i` (PATH, HOME for the
  Docker CLI, TMPDIR, LANG, `INSPECT_DISABLE_MODEL_API=1`, `PYTHONPATH`), from a fresh
  temporary working directory after checking that no `.env` exists in it or any ancestor;
  it uses the project interpreter by absolute path. Checked before use: the harness has
  no `dotenv` or `.env` loading code (grep), and inspect_ai 0.3.286 calls `init_dotenv()`
  only from its CLI and `inspect view`, not from the `eval()` Python API used here; the
  project has no `.env` file at present.
  **Correction from the second narrow review:** the claim that Python `eval()` does
  not load dotenv is false. In installed Inspect 0.3.286 the path is `eval` →
  `eval_async` → `eval_init` → `init_eval_context` → `init_runtime_context` →
  `init_dotenv`; `_util/dotenv.py:23` calls `find_dotenv(usecwd=True)` and searches
  cwd and its ancestors. Mock safety depends on the clean process environment AND
  external temporary cwd with no ancestor `.env`, not on choosing the Python API.
  Only file existence was checked; no real `.env` or credential was read. Formal
  credentials must stay in the trusted host process; the sandbox boundary was
  verified with dummy sentinels, not by exposing real credentials.

### Regression results (all 2026-10-30, mockllm only, `INSPECT_DISABLE_MODEL_API=1`)

- Unit tests, no Docker (`harness.tests.test_collect_unit`, fake sandbox): 22/22 pass.
  Covered: `..` and outside paths rejected with no write outside the root (sentinel
  check), prefix trick `/output/finalx/`, NUL, non-string path; host component symlink,
  host final-root symlink and host destination symlink rejected with target unchanged;
  hardlink entry collected as a regular file with `nlink` recorded; names without
  extension and with spaces; listing exec failure / garbage output / timeout / unreadable
  root → `listing_failed`, `all_intact` false, `harness_error` true, not
  `no_files_confirmed`; empty or missing directory → `no_files_confirmed`; only
  special entries → `partial`; one read failure does not block others; integrity
  mismatch recorded and not written; oversized file between two small files; file-count
  limit; resume skips identical, collects missing, keeps history, inode and mtime of the
  earlier copy unchanged; same-name different-content conflict not overwritten; record of
  another run id refused; two runs in two directories.
- Inspect chain (`harness.tests.regress_inspect`, real Task + docker sandbox, scripted
  tool calls dispatched by Inspect as `ToolEvent`s): 62/62 checks pass across seven
  scenarios; summaries `logs/stage2_fix/regress_summary_20261030T102523Z.json` and
  `…T102556Z.json`, eval logs under `logs/stage2_fix/inspect/`.
  - `adversarial`: a.txt, `sub dir/deep/b.txt`, `README`, a hardlink (`nlink` 2) and
    z.txt collected intact; a 65 MiB file between a.txt and z.txt recorded `oversized`
    and not read; symlink to `/etc/hostname`, broken symlink, symlinked directory (not
    descended) and a fifo recorded as skipped with reasons; status `partial`; every host
    path inside the sample's `final/` root; no other host file written.
  - `listing_failed`: `chmod 000 /output/final` (root without `CAP_DAC_OVERRIDE` cannot
    read it) → `listing_failed`, `all_intact` false, `harness_error` true,
    `outcome_class` `harness_collection_error`, `root_state` `unreadable`, scorer answer
    `listing_failed`; the cleanup hook ran a second pass despite the marker.
  - `render_corrupt`: valid DOCX renders; the same path truncated → `ToolError`
    "conversion produced no PDF" with no image; non-PDF bytes named `.pdf` → "PDF could
    not be opened"; empty file → "file is empty"; page out of range → error; no
    `/tmp/render_*` directory left in the sandbox afterwards.
  - `resume` (scorer pass with a simulated read failure on b.txt): passes "collected in
    scorer" (partial) then "collected in cleanup (resume of earlier pass)"; a.txt
    collected once and seen identical in pass 2; b.txt collected in pass 2; final status
    `complete`, contents intact.
  - `two_runs`: two runs of the same task land in two run directories with different run
    ids; the first run's file hash is unchanged after the second; records carry model,
    task id and epoch; collected files are mode 0444.
  - `conflict`: a pre-existing host file of the same run with different content →
    `conflict_existing_differs`, file unchanged, the other file still collected, status
    `partial`, both passes recorded.
  - `probe_creds`: the probe reports the three test variables absent and both counts 0;
    none of the three dummy values appears in the parsed log, in any `ToolEvent`
    argument or result, or in the raw `.eval` archive; no name=value line is printed.
- `harness.smoke normal` re-run through the isolated launcher: 13 tool events, same
  outcomes as before, collection status `complete`, 3 files, `harness_error` false.

### Classification

**Superseded by the second narrow review:** B4/I4 remained closed; B1–B3 were only
partially closed. The list below records the first repair round's claim, not the
current acceptance state. See the subsequent closeout record for evidence and gates.

- Fixed and tested (unit + Inspect chain): B1 path validation and host-side boundaries;
  B2 status model, per-file isolation, oversized handling, listing failure as harness
  error, cleanup not blocked by a marker; B3 unique run directories, run binding, resume
  without overwrite, conflict detection; B4 fresh directory, exit status, PDF validity,
  no stale image, temporary cleanup; I4 value-free probe.
- Code check only (branch exists, not exercised end to end): the cleanup pass when the
  scorer never ran ("scorer did not run" note); `render_document`'s 170 s conversion
  timeout branch; `time_budget_exceeded`, `total_limit` and `host_write_failed`
  branches; the `collection_error_<stamp>.json` path when the cleanup collector itself
  raises.
- Still unverified: behaviour above Inspect's own 100 MiB `read_file` limit (our limit
  is lower, so it should not be reached); memory pressure; concurrency above one; the
  hardlink regression of the re-check was re-implemented from its description (its
  script was not available), as "collected as a regular file, `nlink` recorded".

## Stage 2 closeout after the second narrow review (2026-10-30)

The second Codex narrow review confirmed B4 and I4 closed, but found B1–B3 only
partially closed. Its findings supersede the first fix-round closure claims without
removing those historical records. Baseline remains
`2f2f9c27bd35401ed6ccbd381a4776a8522b7eb6`; Stage 2 is in the Stage 2 commit on `main`.

### Implemented scope and acceptance contract

- **B1:** host directory validation walks every raw absolute ancestor from `/` with
  directory file descriptors and `O_DIRECTORY | O_NOFOLLOW`, including the trusted
  collection root's ancestors. No `realpath` normalization can hide a supplied
  symlink. Collection and outcome records use random temporary filenames, exclusive
  `O_CREAT | O_EXCL | O_NOFOLLOW` creation (mkstemp semantics), fsync and an atomic
  directory-FD-relative rename. Fixed `collection.json.tmp` is never used. Record
  targets must be regular, single-link files; symlink targets and invalid record names
  are refused. Raw deliverables retain exclusive creation, hash comparison and
  non-overwrite behavior. Mode 0444 is a convention, not an absolute immutability
  guarantee; the outcome loader checks original bytes/hashes before grading.
- **B2:** the enumerator response validates the outer object, root, root state, all
  three lists, every item and its required field types. Malformed enumeration, including
  `entries=[42]`, is `listing_failed`, never an empty successful listing. Valid but
  unsafe path strings remain per-item rejections, allowing other valid files through.
  Each `passes[]` entry now includes its own complete `files[]` results; cleanup
  recovery cannot erase the original read failure from the final record.
- **B2 final attribution:** cleanup always publishes `run_outcome.json`, including
  when the scorer is disabled, errors before running, or already collected completely.
  It embeds the final collection and pass history, execution errors/limits linked to
  Inspect event UUIDs, real identity, `harness_error`, `grading_eligible`, and
  `outcome_class`. `harness_error` identifies collection faults; execution error/limit/
  unknown status separately blocks grading even if collection succeeded. Inspect sets
  `TaskState.completed=True` after an error too, so the outcome uses transcript events
  plus a trusted solver-finished marker. It does not equate that flag with success.
- **Provisional collector events:** installed Inspect 0.3.286 `Score.value` is required;
  `Score.unscored()` (`scorer/_metric.py:178`) supplies its NaN unscored sentinel,
  excluded from metrics/reducers. The collector now uses this mechanism with
  `@scorer(metrics=[])`, not numeric 0/1 accuracy or status strings as scores. An
  original partial ScoreEvent remains partial even after successful recovery; only
  the cleanup outcome is authoritative. Existing historical evals are not rewritten.
- **Grading gate:** `load_run_outcome(..., for_grading=True)` requires identity supplied
  independently from the completed eval log. It checks finality, schema/flags,
  run/collection identity, complete pass history, record consistency, and artifact
  locations/hashes. Missing/corrupt/mismatched/stale/non-final outcomes fail closed.
  Persistent listing failures and unrecovered partials cannot become model missing-
  deliverable failures. `for_grading=False` permits inspection of valid error records,
  not bypass of schema/identity/integrity validation. The actual grader consumer and
  terminal-log join have NOT been implemented or integration-tested in Stage 2.
- **B3:** `make_task()` no longer generates execution IDs or creates a run manifest.
  Each actual sample collects under `runs_root/<TaskState.uuid>/`. `run.json` is bound
  when the first trusted TaskState reaches `bind_execution`, with scorer/cleanup
  fallback. Binding is `{uuid, model, task_id, eval_id, sample_id, epoch}`: Inspect's
  registered task/eval IDs, actual runtime model, dataset sample ID (GDPval UUID for
  real tasks) and epoch. Legacy `run_id` input is only a `run_label`, never a directory
  selector. `run_binding()` explicitly requires Inspect 0.3.286; its two internal
  context accessors are verified against actual eval logs and fail closed if missing
  or inconsistent. There is no synthetic replacement for unresolved identity.
  Full binding is checked against every existing record before any metadata update.
  Same UUID with another model/task/sample/epoch/eval is refused with originals intact.
- **B4/I4:** remain closed. No change to custom rendering or credential probe logic.
  Old regressions are adapted only for UUID directories and the additional outcome
  file; all failures and rerun logs are retained.

### Evidence and remaining gates

All active tests use the existing pinned sandbox image, no builds/pulls, `mockllm/model`,
`INSPECT_DISABLE_MODEL_API=1`, `run_isolated.sh` (`env -i`), a temporary HOME with benign
Docker configuration, and an external cwd with no ancestor `.env`. No real credentials
are inherited/read. The external supervisor enforces 300 seconds per command, 384 MiB
and 4,000 files across scratch/new logs, 96 MiB per host file; the sandbox probe file
limit is 80 MiB. New logs are only under `logs/stage2-closeout-g5mk9l3i/`.

Before implementing UUID binding, lifecycle probes used actual Inspect tasks with
mock tool calls. Eight executed samples across five evals established: scorer/cleanup
UUID equality; cleanup identity with no scorer; independent eval UUID separation;
different sample separation; different epoch separation; runtime model/task/eval/sample/
epoch agreement with the logged identity. A probe initially used a list instead of
MemoryDataset, and then confused runtime eval ID with definition task ID; these probe
errors were corrected and the final six lifecycle checks passed. The complete evidence
is `lifecycle/result-with-task-id.json`. No unsupported fallback identity was introduced.

The first legacy regression run after this round reported two failures because its
assertions still expected `<sample>/epoch1/final` and allowed only two metadata files.
The observed artifacts were correctly inside `<uuid>/final`; the assertions were
updated to that layout and to include `run_outcome.json`, then rerun. The failed logs
remain under `batch1/`; the passing rerun is under `batch1fixed/`.

Final regression results (exit code 0 unless explicitly noted above):

| Command after the isolated launcher / external bounded supervisor | Result |
| --- | --- |
| `unittest harness.tests.test_collect_unit harness.tests.test_closeout_unit -v` | 35/35 tests pass (22 existing + 13 closeout; malformed-schema subcases included) |
| `closeout_bridge batch1fixed` → existing `regress_inspect` first batch | 33/33 checks pass; initial `batch1` exit 1 was the two obsolete layout assertions described above |
| `closeout_bridge batch2` → existing `regress_inspect` second batch | 29/29 checks pass |
| `closeout_bridge closeout2` → `regress_closeout` | 91/91 checks pass over 10 evals / 13 sample executions |
| `closeout_bridge normal` → `smoke.run(normal)` | 13 ToolEvents, 3 original files, complete collection, valid eligible final outcome |

The external supervisor command prefix was
`.venv/bin/python -B /private/tmp/stage2-closeout-g5mk9l3i/launch.py`; it invokes
`/bin/bash /Users/yuning/turing-th/harness/tests/run_isolated.sh /Users/yuning/turing-th`
with the module/arguments above. `closeout_bridge.py` is an external adapter that
pins the existing image ID/Compose file, enforces `sandbox_prebuilt=True`, redirects
all logs into the new ignored directory, and uses concurrency 1 and zero task retries.
The final closeout suite is reproducible from `harness/tests/regress_closeout.py` with
`--output-root <new-log-directory>` through the same isolated launcher and prebuilt
image setup. Console records, including unsuccessful probe development attempts, are
preserved under `logs/stage2-closeout-g5mk9l3i/console/`.

Measured final-outcome cases (`closeout2/suite/results.json`):

- Persistent listing failure: Inspect eval status `success` means orchestration finished;
  the collector ScoreEvent is NaN/unscored, metrics empty, final collection
  `listing_failed`, `harness_error=true`, grading gate rejects. No capability score.
- Scorer partial → cleanup complete: first pass's `read_failed:RuntimeError` remains
  in `passes[0].files`; original a.txt bytes/inode/mtime unchanged, b.txt recovered;
  final complete, `harness_error=false`, original ScoreEvent still partial/unscored.
- `score=False`: zero ScoreEvents, scorer-executed flag false; cleanup collects both
  files and publishes a valid completed-execution outcome.
- Mock generation exception: zero ScoreEvents, Inspect status error, cleanup collects
  both files and publishes a valid outcome with the ErrorEvent UUID/message, execution
  status error, `grading_eligible=false`. Complete collection does not erase execution
  failure; `harness_error=false` here means no collection fault, not a successful run.
- Sample timeout: both files preserved, execution limited, grading ineligible.
  *[Superseded on the same day by the execution-budget policy below: a budget limit
  with `complete` or `no_files_confirmed` collection is grading-eligible. The
  `regress_closeout` assertion was updated and rerun; see that section.]*
- `entries=[42]`: final listing_failed with schema error and no file reads.
- Same UUID with a changed model, task ID or epoch: refused before updates; all original
  record bytes unchanged. Unit tests also cover sample/eval/UUID mismatches.
- Same Task object evaluated twice: `oEVW43pHRvoM8ERgz3SqYU` and
  `neS8Qfr2b3WHnGDwhuS7hk`, separate directories, first artifact unchanged. Two samples
  × two epochs produced four distinct UUIDs. All 13 samples' full bindings matched
  their logged EvalSpec/EvalSample identities; manifests were first bound in the solver.

Final workspace check: 1,023 original non-secret project files were snapshotted
(excluding `.git`, `.venv`, credential/config directories, `.env*`, and caches).
Exactly seven original files changed intentionally: `PLAN.md`, `docs/status.md`,
`harness/collect.py`, `harness/task.py`, `harness/smoke.py`, and the two existing
collector regression files. Two new test modules were added. No original file was
removed; all other original hashes, including every pre-existing log and B4's
`tools.py`, remained unchanged. New ignored logs are isolated under the path above.
Git HEAD remains the Stage 1 baseline; there was no commit, push, or ref update.

No existing container was stopped or removed. At completion, Docker listed only the
four pre-existing stopped database containers; no test container remained. B4's stale
image regression and I4's count-only dummy credential probe passed again. No real
model, judge, paid API, dependency install, image build/pull, business calculation or
rubric change occurred.

**Still mandatory before the first real model pilot (Stage 3 implementation):**

1. Wire the actual scoring entry point to the validated final outcome, using identity
   from the completed Inspect log; integration-test no score on missing/invalid/mismatched
   outcome, persistent listing failure, unrecovered partial, execution error/limit,
   and teardown/logging errors after Task.cleanup. A successful Inspect eval alone is
   NOT successful collection. The current producer/loader contract is tested; this
   consumer integration is not.
2. Enforce cumulative file count and byte limits across collection passes, and a hard
   overall read/collection deadline. Current `max_files`/`max_total_bytes` reset per
   pass; `time_budget_s` is checked before reads, not an in-flight read timeout.
   Preserve already collected originals on any limit. These are not described as
   completed sample-wide controls. *[Implemented and mock-verified 2026-10-30, Stage 3b
   item 5; see that section.]*
3. **I1:** staging allowlist realpath/symlink checks and hashes of every model-visible
   input. **I2:** decode `view_image` bytes and bound image dimensions. Both are hard
   preconditions to the first real candidate-model call, not optional hardening.
   *[Implemented and mock-verified 2026-10-30, Stage 3b items 3 and 4.]*

**Other unchanged nodes:** I3's wrong-formula/missing-cache/recalculation-failure
counterexamples are due before the first full pilot grading; I5's model/budget/
concurrency/image-digest settings are Stage 3 configuration, fixed before freeze.
Real-provider behavior, resource pressure/concurrency, process termination before
cleanup, and teardown/log-write failures are not claimed validated by mock success.
A process killed before cleanup may have no outcome; that must remain a run error.

## Execution-budget attribution policy (2026-10-30)

Scope of this round: one policy correction in the final-outcome contract, its tests and
documents. No rubric, GDPval data, recalculation, harness design, prompt, image or
compose change; no real model or judge call; no commit, push, freeze or Stage 3 work.

### Policy

- A pre-configured execution budget, identical for both models (Inspect `time_limit`,
  `working_limit`, `message_limit`, `token_limit`; `BUDGET_LIMIT_TYPES` in
  `harness/collect.py`), is a resource constraint of the run. Exhausting one is a
  result of the model under fixed resources, not a harness error. The outcome keeps
  `execution.status=limited`, the limit type(s) and the Inspect `SampleLimitEvent`
  UUIDs. When the final `collection_status` is `complete` or `no_files_confirmed` and no
  provider, harness or collection failure was recorded, `grading_eligible=true`:
  collected deliverables are graded against the formal rubric, requirements whose
  deliverable is missing fail as not delivered, `no_files_confirmed` enters grading
  (confirmed non-delivery is not an invalid run), and the attempt stays in the k=1
  results and in every sample denominator. `grading_eligible` means only that the run
  may enter grading.
- A provider request that finally failed, a transport fault, a container or harness
  exception (`execution.status=error`, Inspect `ErrorEvent` UUIDs kept), an unknown
  execution state, or an unrecovered collection fault (`partial`, `listing_failed`,
  `harness_error=true`) keeps `grading_eligible=false` and is recorded under the
  approved error and retry policy. Collection faults are never model non-delivery;
  execution errors are never model failures. A recovered single tool timeout (a
  `ToolEvent` error while the sample continued) is not a run error. Attribution reads
  the recorded exception type and the Inspect events, never the word "timeout" in a
  log. Limit types outside the budget set (`operator`, `custom`, `turn`, `cost`) are
  not pre-declared budgets and require review (`execution_limit_requires_review`).
- Unchanged: the collector's `Score.unscored()` provisional events with
  `@scorer(metrics=[])`; no accuracy or other metric that could be confused with a
  rubric score is reintroduced. The four fields `execution.status`,
  `collection_status`, `harness_error` and `grading_eligible` stay distinct;
  `outcome_class` is one of `collected`, `no_deliverable_files_confirmed`,
  `harness_collection_error`, `execution_error`, `execution_unknown`,
  `execution_limit_requires_review`, and `grading_basis` states the reason in words.

### Changes

- `harness/collect.py`: module docstring (policy, l. 26–50); `BUDGET_LIMIT_TYPES`,
  `EXECUTION_STATUSES`, `OUTCOME_CLASSES` (l. 527–530); `execution_snapshot` records
  `limit_types` (l. 589–602); `_execution_status` (l. 605); `grading_decision` (l. 609),
  the single rule used by `write_run_outcome` (l. 635; adds `grading_basis` and
  `budget_limit_types`) and re-derived by `load_run_outcome` (l. 654; now also
  validates each limit's `type` and `event_uuid`, each error's `event_uuid`,
  `limit_types`, and the attribution against `grading_decision`, l. 705–720).
- `harness/tests/regress_closeout.py` l. 135–140: the sample-timeout assertion now
  expects `grading_eligible=true`, class `collected`, `limit_types=["time"]`.
  `harness/tests/test_closeout_unit.py` l. 177: class name `execution_error`.
- New `harness/tests/test_outcome_policy_unit.py` (decision table of 20 cases, write and
  load round trips for limited/complete, limited/no-files, limited/partial, operator
  limit, error/complete, tampered limited outcomes fail closed).
- New `harness/tests/regress_limits.py`: real Inspect limits and errors through the
  Task + docker chain with mockllm; `--output-root` must be a new directory.
- `harness/tests/run_isolated.sh`: `TMPDIR` and the working directory are resolved to
  real paths (`pwd -P`), because the collector refuses symlinked host path components
  and macOS's `/var` and `/tmp` are symlinks. The closeout suite had been run through an
  external supervisor that already supplied real paths; without this change the unit
  tests fail under the plain launcher (`NotADirectoryError: 'var'`), which is what
  happened on the first attempt of this round.
- `PLAN.md` section 4 ("Execution budgets" paragraph; error wording) and section 3 (one
  attempt); `preregistration.md` 1.3 (budget paragraph).

### Inspect 0.3.286 semantics checked

`SampleLimitEvent.type` is one of `message`, `time`, `working`, `token`, `turn`,
`cost`, `operator`, `custom`; `EvalSample.limit` carries the same type. Message and
token limits are raised at their detection points inside model generation
(`check_message_limit`, `check_token_limit`) and record their own events; the working
limit is recorded by the sample runner; the time limit raises at the `time_limit()`
scope exit. mockllm reports default token usage, so `token_limit` fires. In every
limited case the scorer and the cleanup hook still ran and the sandbox was alive for
collection. A tool timeout surfaces as a `ToolEvent` error only, with no `ErrorEvent`
and no `SampleLimitEvent`.

### Regressions (2026-10-30, `run_isolated.sh`, `INSPECT_DISABLE_MODEL_API=1`, mockllm, prebuilt image, new log directories)

| Command | Exit | Result |
| --- | --- | --- |
| `unittest harness.tests.test_collect_unit harness.tests.test_closeout_unit harness.tests.test_outcome_policy_unit` | 0 | 44/44 (22 + 13 + 9) |
| `harness.tests.regress_limits --output-root logs/stage2-limits-20261030T205027Z/suite` (a–h) | 1 | 61 PASS, 2 FAIL, 0 UNVERIFIED: (1) scenario a did not start: Inspect's prebuilt check (`docker image inspect gdpval-sandbox:stage2`) reported the image absent on the first Docker call of the process although `docker images` lists it and scenarios b–h used it seconds later; (2) scenario b's assertion expected `root_state=missing`, but the image creates `/output/final`, so an untouched directory reports `dir`; the outcome itself (`no_files_confirmed`, eligible) was correct and the assertion was corrected |
| `harness.tests.regress_limits --output-root …/suite_rerun_ab a b` | 0 | 23/23 PASS |
| `harness.tests.regress_closeout --output-root …/closeout_rerun` | 0 | 92/92 PASS (91 earlier checks + the new sample-timeout policy check) |
| `harness.tests.regress_inspect` (fix-round suite, unaffected by the policy; new files only under `logs/stage2_fix/`) | 0 | 62/62 |

Measured outcomes (`logs/stage2-limits-20261030T205027Z/{suite,suite_rerun_ab}/results.json`):

- a: `time_limit=3`, two files written then `sleep 20` → Inspect `sample.limit.type=time`,
  `SampleLimitEvent` in the transcript; `execution.status=limited`,
  `limit_types=["time"]`, `collection_status=complete` (2 files, bytes intact),
  `harness_error=false`, `grading_eligible=true`, `outcome_class=collected`; gate accepts.
- b: `time_limit=3`, `sleep 20`, nothing written → limited, `root_state=dir`, no
  entries/skipped/rejected/errors, `collection_status=no_files_confirmed`,
  `grading_eligible=true`, `outcome_class=no_deliverable_files_confirmed`; gate accepts.
- c: file written, `chmod 000 /output/final`, `sleep 20`, `time_limit=3` → limited and
  `collection_status=listing_failed`, `harness_error=true`, `grading_eligible=false`,
  `outcome_class=harness_collection_error`, `file_count=0`; gate refuses; not
  `no_files_confirmed`.
- d: mock raises `RuntimeError` after the tool result; both files already written →
  Inspect status `error`, `execution.status=error` with the original message and the
  `ErrorEvent` UUID, `collection_status=complete` (cleanup collected 2 files),
  `harness_error=false`, `grading_eligible=false`, `outcome_class=execution_error`;
  gate refuses.
- e: `bash(timeout=3)` with `sleep 20` → one `ToolEvent` error "timed out", no
  `ErrorEvent`, no limit; `execution.status=completed`, `grading_eligible=true`.
- f/g/h: `message_limit=6`, `token_limit=400`, `working_limit=3` each fired with the
  matching `sample.limit.type` and event; outcomes limited and eligible (`complete`,
  `no_files_confirmed`, `complete`). None was left `UNVERIFIED`.

Not verified in this round: `turn` and `cost` limits (not used by this evaluation;
treated as requiring review), real-provider request failures and retries (mock only),
a process killed before cleanup (no outcome → run error by construction of the gate).

### Registered for Stage 3 (policy only; no scoring entry point implemented)

- Per-file attribution of a `partial` collection happens at the formal grading entry
  point, file by file: a model-created symlink, special file, or a file over the
  pre-fixed size limit is ordinarily model delivery behaviour, and the invalid or missing
  deliverable is graded against the rubric; `read_failed`, `integrity_mismatch` and
  similar reasons are judged together with the execution log as model behaviour,
  harness fault, or undeterminable, never by the reason name alone; an unrecovered
  harness collection fault is never a model failure; with insufficient evidence the
  item stays `unknown` and goes to human adjudication.
- Still mandatory before the first real-model pilot (unchanged, not completed): the
  grading entry point that consumes `run_outcome.json` with identity from the completed
  Inspect log and the terminal-log join; cumulative file-count and byte caps across
  passes and a hard overall read deadline; I1 and I2. I3 before the first full pilot
  grading; I5 with the Stage 3 configuration before `freeze-v1`.

### Pre-commit check (2026-10-30; commit made afterwards with approval)

Proposed content: the five modified tracked files (`.gitignore`, `PLAN.md`,
`docs/status.md`, `preregistration.md`, `pyproject.toml`, `uv.lock`) and the untracked
`docker/sandbox/` (4 files) and `harness/` (19 files: package, collector, tools, task,
samples, smoke, compose, neutral draft system prompt, fixture generators, tests).
Excluded by `.gitignore` and confirmed absent from the proposed set: `.env`, `private/`,
`plan/`, `data/gdpval.parquet`, `data/inputs/`, `data/prompts/`, `data/resources/`,
the two third-party PDFs, `logs/` (all `.eval` logs and synthetic test outputs),
generated fixtures. Scans of the proposed files: no key-like strings (the only matches
are the probe's grep pattern and the dummy sentinel text), no Chinese text, no
reference to internal plan contents. See the chat report for the file list, the
proposed commit message, and the `git status` at the time of the check.

## Stage 3a — model, budget and pilot configuration (2026-10-30)

Scope: approved rulings recorded, `config.json` drafted (DRAFT, not frozen), public prices
recorded, Stage 3b work list estimated. No candidate-model, judge or other paid call; no
generation; no freeze; no pilot. The permitted one-per-provider models-list calls were
not made because `.env` does not exist (checked; no key was read, printed or logged).

### Rulings approved by the human on 2026-10-30 (written into `preregistration.md`)

- 1.13 substitutes and single-model fallback: APPROVED as written.
- `b5d2e6f1…` C3 / rubric 12: the real PivotTable object requirement stands; graded by
  structure (pivotTable and pivotCache parts present, cache source referencing the Data
  range, row/column/data fields matching the task); "can Excel open or refresh it" is a
  recorded toolchain limitation, not a basis for pass or fail (section 2.1).
- GCP pre-staged resources: HTML snapshot + extracted text + icon zips, identical for both
  models; the per-file SHA-256 list of all 27 staged files (2 inputs, 11 HTML, 11 text, 3
  zips; 11 text files are not in `data/manifest.json` and were hashed now) is in
  `config.json` (`pre_staged_resources.files`); runtime verification at staging is Stage
  3b item I1 (section 2.10).
- Hardening: no non-root sandbox user (known limitation, recorded in `config.json`
  `sandbox.user`); image pinned by digest at freeze (a local build has no repository
  digest until pushed or exported; the image id `sha256:18cde712…` is recorded now).
- Run directory: `runs_root` must be a real path (macOS `/tmp` and `/var` are symlinks);
  the launcher resolves it, compares, and refuses to start on mismatch. Recorded in
  `config.json` (`collection.runs_root_policy`); the launcher that enforces it is Stage
  3b work. The test launcher already resolves `TMPDIR` the same way.

### Approvals of 2026-10-30, second round (after the verbatim review in chat)

- **Critical criteria.** 17 of the 18 PENDING criteria APPROVED as written (f841ddcf
  C3–C5; 47ef842d C1, C4; 1137e2bb C1, C3; c3525d4d C3; 7b08cd4d C1–C3; 2ea2e5b5
  C1–C3; c357f0e2 C3; a45bc83b C1, C3). **1137e2bb C2 stays PENDING.** Check made: the
  prompt asks for a SKU summary "with the ability to drill down to the PO level"; rubric
  14 (weight 2 of 80) is the only item requiring drill-down ("includes PO Number as a
  field or enables double-click into detail that shows PO Number"); rubric 56–62 require
  per-SKU totals only. Non-compensability: the PO-level detail is already in the flagged
  line sheet (C1), and a correct SKU summary without a drill-down field does not misstate
  the audit or misdirect the follow-up, so the drill-down fails the critical standard.
  Proposed revision recorded in `preregistration.md` 2.4: C2 = separate summary tab,
  three measures per SKU, per-SKU totals equal to the recomputed values, summary totals
  reconciling to the detail flags; rubric 14 graded as written in the ordinary pass.
  Awaits the human's decision.
- **f841ddcf precision table.** General numeric and rounding principles APPROVED. Items
  48–54 checked against the rubric text: each states the short-shipped amount in whole
  dollars ("$ Short Shipped equals $198", "$773", "$2,263", "$1,533", "$109", "$12",
  "$323") and the percentage as a range or "equal to 97.0%"; the HALF_UP whole-dollar
  value therefore passes, a cents value equal to the exact figure at cents passes, a
  truncated whole dollar fails; the basis is the rubric's own wording, not the expert
  deliverable's formatting. Items 27, 28, 35, 36 (equalities of amounts: cents under the
  general rule), 37 (agreement with table totals at the precision shown) and 55–57
  (explicit tolerances and exact whole dollars in the rubric) recorded with their basis.
  All entries APPROVED; a basis column was added to the table. Conditional items 47–54
  are graded per their own "if present" condition when no account summary exists.
- **7d7fc9a7 reconciliation and rounding rule** APPROVED (recorded in 2.7, closes
  section 4 item 5): balances equal to the given GL to the cent pass; a difference passes
  only with an explicit, quantified, re-performable reconciliation bridge that closes it
  to the GL; a textual rounding note alone fails; an undisclosed difference fails; rubric
  23–26, 30, 41–44, 48 graded on their own text after any quantified bridge; the expert
  gold is never the sole evidence; the independent recalculation is the reference.
- **System prompt.** Three additions approved and made in
  `harness/system_prompt_draft.txt`: LibreOffice "with python3-uno bindings"; "Tools to
  view images and render document pages are provided."; "No one is available to answer
  questions; make reasonable assumptions and state them in the deliverable." Everything
  else unchanged. `config.json` carries the new text and SHA-256. Comparability rule
  recorded in `config.json`: A and B must run under the same prompt, tool schema and
  environment with identical recorded hashes; a prompt or tool change after pilot A turns
  that A into a technical trial or intervention, and A is rerun before any comparison.
- **Run parameters approved as pilot candidates** (`config.json`, `approved_2026_10_30`):
  `time_limit` 3,600 s, `working_limit` 3,600 s, `message_limit` 200, tool timeout 600 s,
  3 GiB per sandbox, `attempts=1`, `epochs=1`, pilot concurrency 1/1/1/1; formal
  concurrency 2 stays a PENDING candidate. Four retry layers fixed: Inspect
  `max_retries=3`; provider SDK `max_retries=0` through `model_args` (effect to be
  verified when the SDKs are installed, Stage 3b item 8); `retry_on_error` off and
  `fail_on_error=false`; `eval()` is the entry point (if `eval_set()` were used,
  `retry_attempts=0` is mandatory since its default is 10 in 0.3.286). No unapproved
  whole-sample or whole-task rerun. `token_limit` and per-request `max_tokens` are set
  after A/B selection and approved before the first real pilot run.
- **Model candidates recorded, not decided.** Capability-first (preferred):
  `claude-opus-5-5` and `gpt-6.1-sol`; same-price general alternative: `claude-sonnet-5-5`
  and `gpt-6.1-sol`. Basis: each provider's current representative general-purpose model.
  Recorded limitations: 2x price asymmetry in the capability-first pairing (4/20 vs 2/10
  USD per MTok), different reasoning controls (adaptive thinking with effort levels vs
  `reasoning_effort` low–max; Opus 5.5 default effort medium, Sonnet 5.5 high, gpt-6.1-sol
  default not stated), non-comparable tokenizers. Actual ids and callability await the
  provider list queries and the pilot; the human approves A/B. Judge candidate
  `gemini-3.1-pro-preview` (2/12 USD per MTok up to 200k; ai.google.dev pricing, queried
  2026-10-30) with the preview-withdrawal risk recorded; not frozen.
- **Pilot budget.** Cumulative ceiling 25 USD for A, B, judge, cache charges and billable
  retries; each paid call still needs separate authorization. The launcher must
  implement reservation before each sample and judge batch, settlement from actual usage
  by category, a persistent ledger with distinct reservation and settlement records,
  conservative handling of unknown retry usage, and the stop conditions (no start without
  budget cover; no new sample after the ceiling; 2x per-task estimate; second engineering
  failure of a class; ceiling reached). It is not an absolute billing hard cap. Inspect
  0.3.286 offers `eval(cost_limit=…, model_cost_config=…)` (per-sample dollars with
  `ModelCost` prices) as a supplement only. Mock verification of the ledger is Stage 3b
  item 7.

### `config.json` (DRAFT)

Written at the repository root (tracked candidate, not yet committed). Content: dataset
revision and parquet hash; the ten tasks with prompt SHA-256, rubric item count computed
from the rubric files (580 in total), and every staged file (43 entries, sandbox path,
source path, bytes, SHA-256); pilot task `1137e2bb…` with the sequence A → review
checkpoint → B; model ids as placeholders; generation: `attempts=1`, `epochs=1`, tool
timeout 600 s, `time_limit` 3,600 s, `message_limit` 200, no token or working limit,
budget-limit types that keep grading eligibility, the four tools, the draft system
prompt (text and SHA-256), server-side tools off; sandbox: compose file hash, image tag
and id, digest placeholder, `network_mode: none`, 3 GiB, 2 CPUs, 512 pids, `cap_drop`
ALL, root-user limitation; collection limits from `harness/collect.py` plus the
`runs_root` real-path policy; concurrency: pilot 1/1/1/1 (`max_samples`, `max_tasks`,
`max_sandboxes`, `max_connections`), formal 2 as a PENDING candidate; retries in three
fixed layers (below); budget: pilot ceiling 15 USD PENDING, no estimate claimed, three
stop conditions.

Retry layers, as checked in installed inspect_ai 0.3.286 and the official SDK docs
(queried 2026-10-30):

1. Inspect model request: `GenerateConfig.max_retries` defaults to **unlimited** when
   unset (`_generate_config.py`), with tenacity `wait_exponential_jitter(initial=3,
   max=1800, jitter=3)` (`model/_retry.py`); retried errors are those the provider's
   `should_retry` classifies (Anthropic: 429 as rate limit, 5xx, connection; OpenAI:
   `openai_classify_retry`, quota-exceeded never retried). Draft: `max_retries=3`,
   `timeout=1800` (whole request including retries), `attempt_timeout=600`.
2. Provider SDK: Inspect constructs `AsyncAnthropic(... **model_args)` and
   `AsyncOpenAI(... **model_args)` without setting `max_retries`, so the SDK default
   applies: 2 retries with short exponential backoff on connection errors, 408, 409, 429
   and >= 500; default request timeout 10 minutes (Anthropic Python SDK docs; openai-python
   README). Neither SDK is installed in the project environment yet (Inspect imports them
   lazily; adding them changes `uv.lock` and needs approval). Proposed (PENDING): pass
   `max_retries=0` as a model arg so layer 1 is the only retry layer; otherwise up to
   4 × 3 = 12 HTTP attempts per request.
3. Whole-sample reruns: `retry_on_error` off (0), `fail_on_error=false` so one errored
   sample does not abort the eval and its outcome records `execution.status=error`.
   Retry cost counts against the budget.

### Public prices (official pages, queried 2026-10-30; recorded apart from any list call)

Prices in USD per million tokens. Server-side tools are off in this evaluation, so their
prices are not reproduced. All current Claude models and all latest OpenAI models accept
image input and tool/function calls per their pages; image input is billed as tokens.

| Provider / model id | Input | Cached input | Output | Notes |
|---|---|---|---|---|
| Anthropic `claude-fable-5-1` | 10 | 0.25 (read); 12.50 / 20 (5 min / 1 h write) | 50 | 1M context, 128K max output, adaptive thinking always on, default effort high |
| Anthropic `claude-opus-5-5` | 4 | 0.20; 5 / 8 | 20 | 1M context, 128K out; fast mode 8 / 40 |
| Anthropic `claude-sonnet-5-5` | 2 | 0.10; 2.50 / 4 | 10 | 1M context, 128K out |
| Anthropic `claude-haiku-5-5` | 0.10 (prompt ≤ 100k) / 0.50 (> 100k) | 0.01 / 0.05 | 0.50 / 2.50 | priced by prompt length |
| OpenAI `gpt-6-astra` | 10 | 1.00 | 50 | 1.05M context, 128K out, efforts low–max, cutoff Apr 30 2026; page calls it the flagship |
| OpenAI `gpt-6.1-sol` | 2 | 0.10 | 10 | 1.05M / 128K |
| OpenAI `gpt-6.1-terra` | 1 | 0.05 | 5 | 1.05M / 128K |
| OpenAI `gpt-6-luna` | 0.10 | 0.01 | 0.50 | 1.05M / 128K |
| OpenAI `gpt-5.6-sol` | 4 | 0.40 | 20 | — |
| OpenAI `gpt-5.5` | 5 (10 above 272K input) | 0.50 | 30 (45 above 272K) | — |
| Google `gemini-3.1-pro-preview` (judge candidate) | 2 (≤ 200k) / 4 | 0.20 / 0.40 | 12 / 18 | — |
| Google `gemini-2.5-pro` (judge candidate) | 1.25 / 2.50 | 0.125 / 0.25 | 10 / 15 | — |
| Google `gemini-4-argon` | 2 (4 from 2026-12-01) | 0.10 | 10 (20 from 2026-12-01) | announced price step |

Sources: platform.claude.com pricing and models overview; developers.openai.com pricing
and models pages; ai.google.dev Gemini pricing. Caveats: the OpenAI models page is
truncated ("View more"; a full catalog exists) and its pricing page shows layout gaps, so
these rows are not a complete list of available models; Anthropic Batch API is 50 % off
and its Mythos models are limited-availability; a successful list call (not made) would
not establish generation or tool compatibility either. Prices are a planning input, not a
billing basis.

**Budget.** The pilot ceiling of 15 USD is pending approval. No estimate is claimed:
models are not selected and no run exists. For orientation only (not an estimate), one
agentic task that accumulates 1.5M input tokens (mostly cache reads) and 40k output
tokens would cost about 1–2 USD on `claude-opus-5-5` or `gpt-5.5` with caching and
7–9 USD without; two models on the pilot task therefore range from a few dollars to above
the ceiling depending on caching, retries and judge calls, which is why the pilot
measures cost before any formal run. The estimate written at model selection will state
whether judge and retry costs are included.

### Engineering notes from this stage

- Docker Desktop (server 29.6.1) twice answered `docker image inspect gdpval-sandbox:stage2`
  with "No such image" while `docker images` listed the image (once as the first call of
  the `regress_limits` process, once during this stage's checks); seconds later the same
  call succeeded. Inspect's `sandbox_prebuilt` check uses exactly this command. The
  Stage 3b launcher should pre-flight the image with a bounded retry and record the
  response; this is a daemon behaviour, not a harness defect, and it is tracked here.
- `anthropic` and `openai` SDKs are not in `pyproject.toml`; the first real call needs
  them (approval for the dependency change) and the `.env` file.

### Stage 3b work list (not started; estimates are working time, not calendar time)

| # | Item | Estimate |
|---|---|---|
| 1 | `1137e2bb…` grading chain: extraction (xlsx formulas and cached values, docx text), LibreOffice recalculation on copies, deterministic checks per section 2.4, judge input assembly and judge prompt, human-review material generator (deliverable and criterion first; judge verdict in a separate file) | 2–3 days |
| 2 | Grading entry point consuming `run_outcome.json` with identity from the completed Inspect log and the terminal-log join; integration tests: no score on missing, invalid, mismatched, non-final, `listing_failed`, unrecovered `partial`, `execution_error`; `limited` handled per the budget policy | 1 day |
| 3 | I1: staging allowlist real-path and symlink checks; SHA-256 verification of every model-visible file against `config.json` at staging | 0.5 day |
| 4 | I2: `view_image` decodes the bytes and bounds pixel dimensions | 0.25 day |
| 5 | Cumulative file-count and byte caps across passes; hard overall read deadline; originals preserved on any limit | 0.5 day |
| 6 | Deterministic-check fixtures for `1137e2bb…`: positive fixture built from the original inputs with independently verified expected values; negative fixtures with explicit planted errors; expert gold used as reference only, known gold/rubric conflicts marked separately | 1 day |
| 7 | Pilot launcher: loads `.env` in the trusted process only, resolves and validates `runs_root` (real path), pre-flights the image with bounded retry, refuses `INSPECT_DISABLE_MODEL_API`, checks key presence by name only, snapshots `config.json` and commit into the run directory | 0.5 day |
| 8 | Dependencies and access: add the provider SDKs (lock change, approval), one models-list call per provider, record pagination handling | 0.25 day |
| 9 | Cost and time accounting for the pilot report (generation, grading, human review) | 0.25 day |

Total about 6–7 working days before the first paid call; human review time is extra and
is measured in the pilot. I3 (synthetic counter-examples for the recalculation three-way
split) stays due before the first full pilot grading; I5 (model, concurrency, image
digest) is fixed at freeze.

### Decisions still open after the second round

1. ~~1137e2bb C2~~ — APPROVED 2026-10-30 with the revised text (drill-down out of the
   critical core, graded under rubric 14); every critical criterion is now APPROVED and
   `preregistration.md` section 4 item 1 is closed.
2. Final A/B model ids and reasoning settings (from the two recorded strategies) after the
   provider list queries; `token_limit` and per-request `max_tokens`; judge freeze.
3. Formal concurrency 2 (after memory and stability evidence; reservation atomicity).
4. Stage 3b work after the infrastructure items (grading chain, fixtures, grading entry
   point, cost accounting: former items 1, 6, 2, 9) — not started without approval.

## Stage 3b — infrastructure items (2026-10-30)

Authorized scope: items 8 (provider SDKs and model lists), 7 (pilot launcher with budget
ledger), 3 (I1 staging integrity), 4 (I2 image validation), 5 (cumulative collection limits
and deadline), in that order, each verified with mocks; then a hard stop. No grading chain,
judge prompt, grading entry point, real generation, pilot or freeze. Stage 3a is committed as
`395d1da626c12fe5b5b0443c0737a8c02b2b614b` (pushed).

### Item 8 — provider SDKs and model lists

- Added with `uv add anthropic openai google-genai`: anthropic 2.3.0, openai 3.41.0,
  google-genai 2.34.0 (Inspect 0.3.286's own dev pins are anthropic>=2.0.0, openai>=3.4.0,
  google-genai>=2.14.0; all satisfied; Inspect itself unchanged). Side effect recorded by
  uv: tenacity 9.2.1 → 9.1.4 (Inspect requires tenacity without a version bound; the
  provider modules `anthropic`, `openai`, `google` import, and the 44 collector unit tests
  still pass). `pyproject.toml` and `uv.lock` updated (uncommitted).
- Retry plumbing verified without network (dummy key, `INSPECT_DISABLE_MODEL_API=1`,
  client construction only): `get_model("anthropic/claude-opus-5-5")` builds an
  `AsyncAnthropic` client with `max_retries=2` by default and `max_retries=0` when
  `max_retries=0` is passed as a model arg; `get_model("openai/gpt-6.1-sol")` builds an
  `AsyncOpenAI` client with 2 → 0 the same way; both SDK request timeouts are 600 s by
  default. The `model_args` route therefore works for layer 2. The Google provider exposes
  `should_retry` and `retry_wait` only (no SDK retry count to set).
- Models-list calls: **not made**. `.env` does not exist and no provider key variable is
  present in the environment (checked by name only), so the permitted Anthropic, OpenAI and
  Google list queries were skipped for lack of credentials. Consequences: no API-returned
  model ids, no pagination record, and no visibility confirmation for the candidates
  `claude-opus-5-5`, `claude-sonnet-5-5`, `gpt-6.1-sol`, `gemini-3.1-pro-preview`; their ids
  rest on the official documentation pages queried 2026-10-30 (section "Stage 3a"). A list
  call, when made, confirms visibility for that key only, not generation, tool use, image
  input or reasoning-parameter availability.

### Item 7 — pilot launcher and budget ledger

- `harness/budget.py` (new): persistent JSON ledger with append-only entries
  (`reservation`, `settlement`, `void`); totals are always derived from the entries, so a
  restart loses nothing and never double-counts; atomic writes (temporary file, rename,
  fsync) under an advisory `flock`. `reserve()` refuses when ceiling − settled − open
  reservations cannot cover the estimate (`BudgetExhausted`), is idempotent for an open
  reservation of the same unit, and refuses settled or voided units. `settle()` prices
  actual usage per model and category (input, output, cache read, cache write; judge units
  are the same four under `kind=judge`) with Decimal arithmetic, releases the reservation
  exactly once (a second settlement returns the first and changes nothing), charges each
  recorded retry conservatively as one more uncached input cost of that unit and flags
  the result as an estimate, settles units with no usable usage at the reserved amount
  (flagged, never silently zero), and refuses a settlement with no usage unless that
  fallback is requested. `void()` releases only a unit that never started.
  `stop_reasons()` returns the approved conditions that apply: ceiling reached, next
  reservation not covered, per-task cost above 2× the estimate, same engineering failure
  class twice. A ledger reopened with a different ceiling is refused.
- `harness/launcher.py` (new): `.env` loaded into the trusted process only (names returned,
  values never printed, existing variables not overwritten); required key checked by name;
  `INSPECT_DISABLE_MODEL_API` refused in real mode; `runs_root` must be absolute,
  normalised and real at every component (macOS `/tmp`, `/var` refused); Docker image
  pre-flight by `docker image inspect` with a bounded number of attempts (3 by default,
  10 maximum, never unbounded) and a per-attempt record; `eval_kwargs()` builds the fixed
  settings from `config.json` — `inspect_ai.eval()` as the entry point, `max_retries=3`,
  `timeout=1800`, `model_args={"max_retries": 0}`, `retry_on_error=0`,
  `fail_on_error=False`, `task_retry_attempts=0`, `time_limit=3600`, `working_limit=3600`,
  `message_limit=200`, `token_limit` from the CLI until A/B are chosen, pilot concurrency
  1/1/1/1, `epochs=1`, and refuses `attempts`/`epochs` other than 1. `PilotLauncher`
  runs one unit at a time: stop check → reserve → `eval()` → settle from the eval log's
  `model_usage` and `ModelEvent.retries` → stop check; an eval failure settles the unit
  conservatively at its reservation (estimated) and counts the failure class; a judge
  batch follows the same contract through `run_judge_batch()`; open reservations found
  after a restart stay reserved until a human settles or voids them. Real mode is not
  enabled in this stage (`main()` refuses after the checks); `--dry-run` performs every
  check and the reserve/void cycle without calling `eval()`. No per-request interception
  in the agent loop and no provider monkeypatch.
- Mock verification (`harness.tests.test_budget_unit`, 25 tests, exit 0, no Docker, no
  model): (1) insufficient budget → `eval()` never called, refusal recorded, no reservation
  left open; judge batches gated the same way; (2) simulated usage settles by category
  (example: 1M input + 100k output + 2M cache read + 500k cache write on Opus 5.5 prices =
  8.90 USD, plus 2 retries estimated at 8.00 USD, flagged); (3) a sample whose actual cost
  exceeds the ceiling leaves remaining −2.00 USD and the next sample is refused before
  start (one `eval()` call in total; the ceiling is not a hard cap); (4) restart from the
  persisted ledger recovers settled 2.00 / reserved 5.00 / remaining 3.00, keeps the
  interrupted unit reserved, applies the stop condition, and a different ceiling is
  refused; (5) duplicate settlement does not double-charge, duplicate reservation is not
  additive, a settled unit cannot be re-reserved or voided, a failed `eval()` settles at the
  reservation and the second failure of the same class stops the run; (6) reservation
  atomicity under concurrency is **not verified** (formal-run gate). Pre-flight tests:
  `.env` parsing returns names only, bounded image retry (2 attempts then success; 3
  failures raise; 50 attempts refused), real-path refusal for a symlinked `runs_root` and
  for `/tmp`, `INSPECT_DISABLE_MODEL_API` refusal, the four retry layers read from
  `config.json`.
- Inspect 0.3.286 supplement available but not wired: `eval(cost_limit=…,
  model_cost_config=…)` (per-sample dollar limit with `ModelCost` prices). Decision for the
  human: whether to add it as a second guard once A/B prices are fixed.

### Item 3 — I1, staged-file integrity

- `harness/samples.py`: `task_files()` refuses a destination listed twice with different
  sources (`StagingError`); `expected_staged_from_config()` reads the per-task file lists
  from `config.json`; `verify_staged_files()` checks, for every staged entry, that the
  destination is a normalised path under `/workspace/inputs` or `/workspace/resources`
  (no empty, `.` or `..` segment), that the source is an absolute normalised path, a regular
  file, not a symlink and not behind a symlinked component (real path compared with the
  real repository root), inside `data/inputs/<task id>/` or `data/resources/<task id>/` and
  naming no other task, and that its size and SHA-256 equal the recorded values; the staged
  set must equal the recorded set (nothing missing, nothing extra). Every problem is
  collected and reported in one `StagingError`; any problem fails closed.
  `build_samples(verify_config=…)` runs it per task and stores the report in the sample
  metadata; the launcher always verifies (`--dry-run` included).
- Regressions (`harness.tests.test_staging_unit`, 11 tests, exit 0): synthetic root with
  two tasks — clean set passes; tampered file (size, and same-size byte change) fails;
  symlinked source and symlinked directory component fail; traversal in the destination or
  the source and a destination outside the mounts fail; a source under another task's
  directory fails; missing and extra files fail; a duplicate destination with a different
  source is refused when the map is built; several problems are reported together. Real
  data: all 10 tasks, 43 staged files (27 for the GCP task) verify against `config.json`;
  a hash mismatch for the pilot task fails closed.

### Item 4 — I2, image validation before provider delivery

- `harness/tools.py`: `validate_image_bytes()` (host side, Pillow 13.0.0, now an explicit
  dependency) requires non-empty data within 8,000,000 bytes, a Pillow-decodable image
  whose actual format (PNG, JPEG, GIF, WEBP) matches the file extension, dimensions at
  most 8000 px per side and 20,000,000 pixels in total (Pillow's decompression-bomb guard
  is set to this limit as well), and a full decode (`load()`) that succeeds; the MIME type
  sent to the provider is derived from the actual format. `view_image` and
  `render_document` both apply it; failures return a specific `ToolError` and no
  `ContentImage` is produced.
- Regressions: host-side (`harness.tests.test_image_unit`, 5 tests, exit 0) — PNG, JPEG,
  GIF and WEBP pass with their real MIME; random bytes, a truncated PNG and an empty file
  are refused; JPEG bytes named `.png`, PNG named `.jpg`, BMP named `.png` and an
  unsupported extension are refused; a 9000×9000 1-bit PNG (a few kB) and an 8001×1 PNG
  are refused by the pixel guard before decoding while a 4000×4000 image passes; data
  over the byte limit is refused. Inspect chain (`harness.tests.regress_tools`, mockllm,
  real sandbox, images created inside the sandbox): 8/8 checks pass (results in
  `logs/stage3b-20261030T220004Z/tools_run3/`): the valid PNG returns an image with
  decoded dimensions; random bytes, JPEG-named-PNG, 9000×9000, truncated and 8.5 MB files
  each return the specific error with no image; `render_document` still returns a
  validated PNG. The first two runs of this script failed on the script's own assertions
  (expected 9 events instead of 8; expected one wording for the pixel guard) and are kept
  under `tools/` and `tools_run2/`.

### Item 5 — cumulative collection limits and read deadline

- `harness/collect.py`: `max_files` and `max_total_bytes` now apply to the merged set of
  a sample across scorer and cleanup passes: files and bytes collected in earlier passes
  count first, an idempotent re-collection of a known path is not counted again, new
  admissions are limited to the remaining budget, and repeated passes cannot bypass the
  caps. `time_budget_s` is a hard per-pass deadline: checked before each read and enforced
  on the in-flight read with `anyio.fail_after`; a read cut off at the deadline is recorded
  as `read_deadline_exceeded`, later files as `time_budget_exceeded` without being
  attempted, and the pass records `deadline_hit` and the cumulative counts. Collected
  originals are never touched by a later pass (exclusive creation and hash comparison are
  unchanged). A limited collection stays `partial` → `harness_error=true`,
  `grading_eligible=false`, `outcome_class=harness_collection_error`; per-file reasons are
  preserved for the Stage 3 attribution policy.
- Regressions (`harness.tests.test_collect_limits_unit`, 6 tests, exit 0): with a cap of 3,
  pass 1 collects 2 files and pass 2 admits exactly one of three new files (the other two
  `file_limit`; only the new file is read); four passes over five files never exceed two
  files with a cap of 2; byte cap 150 with 100 bytes already collected admits a 40-byte
  file and refuses the next (`total_limit`), with 140 bytes recorded; a 5 s read against a
  0.4 s deadline is interrupted (whole pass under 3 s), the fast file is intact, the slow
  file is `read_deadline_exceeded`, the untried file `time_budget_exceeded`; a later pass
  that hits limits leaves the first pass's bytes, inode and mtime unchanged; the outcome
  contract records such a collection as a harness error that the grading gate refuses.
  All 91 unit tests across the seven modules pass after these changes. Inspect-chain
  reruns after the change (mockllm, prebuilt image, isolated launcher, new log directories
  under `logs/stage3b-20261030T220004Z/`): `regress_closeout` 92/92 (`closeout_rerun/`),
  `regress_limits` scenarios a–h 74 PASS / 0 FAIL / 0 UNVERIFIED (`limits_rerun/`; the
  image pre-flight did not misfire this time), `regress_inspect` 62/62 (summary
  `logs/stage2_fix/regress_summary_20261030T220655Z.json`), `regress_tools` 8/8.

### Hard stop after item 5

Not started, by instruction: the grading chain for `1137e2bb…`, the judge prompt, the
grading entry point that consumes `run_outcome.json`, any real provider generation, the
pilot, and the freeze. Stage 3b files are uncommitted (see the chat report for the list).

Remaining before the first real-model pilot (gates, unchanged in substance):

- **Blocking.** Human approval of the final A/B model ids and effort settings and of the
  judge; `token_limit` and per-request `max_tokens` set and approved; the provider
  models-list queries once `.env` exists; the grading entry point consuming
  `run_outcome.json` with identity from the completed Inspect log and the terminal-log
  join, with its integration tests; the 1137e2bb grading chain and its positive/negative
  fixtures (former Stage 3b items 1, 6, 2, 9); separate authorization for every paid call.
- **Important.** 1137e2bb C2 final wording; reservation atomicity before any concurrency
  above one; the Docker image pre-flight behaviour observed twice (bounded retry now in
  the launcher, not yet exercised against a real misfire); whether to add Inspect's
  per-sample `cost_limit` as a second guard; the `tenacity` downgrade pulled in by the SDK
  dependencies (imports and all suites pass, no further evidence); the image digest to be
  recorded at freeze; the non-root sandbox limitation.

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

Nothing. Waiting for the human's decisions listed under "Next stage".

## Decisions taken (date · what · commit)

- 2026-10-30 · Stage 3a second-round approvals (17 critical criteria, f841ddcf precision
  table with rubric-text basis, 7d7fc9a7 reconciliation and rounding rule, system prompt
  additions, run parameters, model-candidate strategies, 25 USD pilot ceiling) recorded
  and committed as `395d1da626c12fe5b5b0443c0737a8c02b2b614b`; 1137e2bb C2 PENDING with a
  proposed revision · (Stage 3a commit)
- 2026-10-30 · Stage 3b infrastructure: provider SDKs added (anthropic 2.3.0, openai
  3.41.0, google-genai 2.34.0, pillow declared); model_args `max_retries=0` verified to
  reach both SDK clients; models-list calls skipped (no `.env`); launcher and budget
  ledger implemented and mock-verified (25 tests); I1 staging verification (11 tests);
  I2 image validation (5 unit tests, 8/8 Inspect-chain); cumulative collection caps and
  in-flight read deadline (6 tests); all Inspect-chain suites re-run green (92/92, 74/74,
  62/62). Hard stop before the grading chain · uncommitted
- 2026-10-30 · Stage 3a rulings approved by the human: 1.13 as written; `b5d2e6f1…` C3 /
  rubric 12 graded by PivotTable structure (Excel open/refresh is a limitation, not a
  basis); GCP resources staged as HTML + text + zips with the 27-file SHA-256 list in
  `config.json`, runtime verification in Stage 3b (I1); no non-root sandbox user (known
  limitation), image digest pinned at freeze; `runs_root` must be a real path, enforced
  by the launcher. `config.json` DRAFT written (placeholders for model ids; tool timeout
  600 s, `time_limit` 3,600 s, `message_limit` 200, 3 GiB, collector limits, `attempts=1`,
  pilot concurrency 1, three fixed retry layers, pilot ceiling 15 USD PENDING). No model,
  judge or paid call; `.env` absent so list calls skipped · uncommitted
- 2026-10-30 · Execution-budget attribution policy: exhausting a pre-configured budget
  identical for both models (time / working / message / token limit) keeps
  `execution.status=limited` with Inspect evidence and is grading-eligible when the final
  collection is `complete` or `no_files_confirmed` and no error was recorded; graded on
  the collected deliverables, missing deliverables fail, attempt kept in k=1 results and
  denominators. Execution errors, unknown states, non-budget limit types and unrecovered
  collection faults stay ineligible and in the run inventory. Collector stays unscored
  with empty metrics. Per-file attribution of `partial` collections registered as a
  Stage 3 grading-entry policy. Regressions a–h, closeout rerun and unit tests pass
  (section "Execution-budget attribution policy") · (Stage 2 commit)
- 2026-10-30 · Second narrow Codex review: B4/I4 closed, B1–B3 only partially
  closed. Confirmed ancestor-symlink and fixed `.tmp` record-write paths, malformed
  enumeration being read as empty, incomplete run binding, provisional accuracy
  scores disagreeing with cleanup, lost per-file recovery history, and the incorrect
  dotenv claim. Authorized limited Stage 2 closeout: final outcome producer/validator,
  strict enumeration and record paths, actual TaskState UUID binding, and corrected
  audit records. Formal grading consumer integration, cumulative caps and hard
  deadline remain explicit Stage 3 pre-pilot gates. No rubric/data changes; no
  commit/push or Stage 3 authorization. · (Stage 2 commit)

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

- 2026-10-30 · Stage 2 toolchain: sandbox image built from the isolated context
  `docker/sandbox/` (python3-uno added after the PivotTable experiment); compose with
  `network_mode: none`, `cap_drop: [ALL]`, 3 GiB / 2 CPUs / 512 pids; explicit per-task
  Sample.files allowlist; outputs collected from `/output/final/` with sandbox-side and
  host-side sha256; smoke tests run only with `mockllm` under
  `INSPECT_DISABLE_MODEL_API=1` and dummy credentials · (Stage 2 commit)
- 2026-10-30 · GCP resources staged as HTML + extracted text + icon zips for the toolchain
  test; the 2026-10-29 snapshot is the fixed artifact for both models; refetched pages
  are not substituted · (Stage 2 commit)
- 2026-10-30 · Generated smoke fixtures are not tracked (regenerated by
  `harness/fixtures/make_fixtures.py`) · (Stage 2 commit)
- 2026-10-30 · Independent re-check finding B1 (collector trusted the sandbox listing;
  traversal, symlink and overwrite exposure) · fixed: raw-path validation, real-path
  containment, `O_EXCL | O_NOFOLLOW`, per-entry rejection · (Stage 2 commit)
- 2026-10-30 · Finding B2 (enumeration failure read as "no files"; marker blocked
  cleanup) · fixed: four-state status, `harness_error` / `outcome_class`, per-file
  outcomes, explicit limits, cleanup resumes any non-complete pass; a collection failure
  is a harness error, never model non-delivery · (Stage 2 commit)
- 2026-10-30 · Finding B3 (collected outputs overwritable across runs; no run binding) ·
  fixed: unique run id and directory per run, `run.json`, record bound to model / task /
  epoch, idempotent resume, conflicts recorded not overwritten, read-only copies · (Stage 2
  commit)
- 2026-10-30 · Finding B4 (`render_document` reused a per-path directory and could
  return a stale image) · fixed: fresh directory per call, exit status and PDF validity
  checks, specific `ToolError`, cleanup on both paths · (Stage 2 commit)
- 2026-10-30 · Finding I4 (environment probe printed variable values) · fixed: presence
  and counts only; inherited credential-like variables scrubbed from the harness
  process; isolated launcher for all mock runs · (Stage 2 commit)
- 2026-10-30 · Findings I1 (allowlist path/symlink/hash checks), I2 (`view_image` decode
  and dimension limits), I3 (synthetic counter-examples for the recalculation three-way
  split), I5 (model configuration, concurrency, image digest) · registered; I1, I2 due
  before the first real-model pilot run, I3 before the first full pilot grading, I5 in
  Stage 3 before `freeze-v1` · (Stage 2 commit)
- 2026-10-30 · The first Stage 2 `normal` smoke log (08:21 UTC) is not counted as a
  complete pass (four `bash` argument-validation errors); the 08:23 and 08:29 UTC logs
  are the valid evidence · (Stage 2 commit)

## Next stage (not started)

Stage 3b (grading chain for the pilot task, pre-pilot gates, launcher, dependencies), then
the pilot on `1137e2bb…` (model A end-to-end through grading and human review, then model
B). The current decision list is in section "Stage 3a"; the list below is the earlier
Stage 3 list, kept for the record (items 1 and 4 are partly settled by the rulings of
2026-10-30 recorded above):

1. `preregistration.md` section 4: pending critical criteria; the PO-log per-item precision
   entries; 1.13 substitutes and fallback; item 5 (`7d7fc9a7…` rounding policy, due before
   `freeze-v1`); `b5d2e6f1…` C3 / rubric 12 handling now that a PivotTable object can be
   created through LibreOffice UNO in the sandbox; the form of the GCP resources in the
   sandbox (tested: HTML + text + zips).
2. Shared prompt text (draft in `harness/system_prompt_draft.txt`; whether it may name
   the UNO route generically), tool set (`bash`, `python`, `view_image`,
   `render_document`), per-call tool timeout (tested 600 s / 5 s), sample time limit,
   message or token limits, concurrency (1–2), memory limit.
3. Candidate model ids and parameters, judge model, budget ceiling, retry policy, and
   whether to commit Stage 2 together with the fix round (harness, tests, Dockerfile,
   pinned requirements) before the pilot.
4. Hardening options: non-root sandbox user; pinning the image by digest in
   `config.json`.
5. Scheduling of the registered findings: I1 and I2 before the first real-model pilot
   call (mandatory); I3 before the first full pilot grading; I5 with the Stage 3
   configuration. Current collector defaults are 200 files and 512 MiB per pass,
   64 MiB per file, and a 600 s check before starting another read. Cumulative sample
   caps and a hard overall reading deadline must be implemented before the pilot;
   these defaults are not evidence that those sample-wide controls already exist.
6. Before any capability scoring, integrate and test the final-outcome gate and the
   completed Inspect log join. Producer/loader mock tests do not constitute approval
   or validation of the future grading consumer.
