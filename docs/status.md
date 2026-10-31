# Status

Current stage: **Pilot A wiring U1–U3 implemented and mock-verified (2026-10-31): real-generation
CLI path, offline grading CLI, judge adapter with gated judged pass; no provider call; config
`judge` block, judge id, reservations, missing-usage hold and paid authorization PENDING; hard
stop before any paid run.** See sections "Pilot A wiring U1/U2" and "Pilot A wiring U3".
Earlier header, kept for the record: U1 + U2 implemented and mock-verified (2026-10-31). Baseline commit
`6761f0d52d145a7aa103cdef01171cddda956cd2`. Earlier header, kept for the record: Stage 3b
deterministic grader CLOSED by the independent final review (2026-10-31; 57/57 layout, 21/21
grading chain; no known Pilot-blocking scoring defect). Earlier header, kept for the record: last located
blocking fix applied (no FAIL inferred from the two extreme overlap scopes) and the Pilot A
request wording corrected (2026-10-31). Earlier header, kept for the record: two
review misjudgements fixed (item 7 applicability, split-table overlap) and the Pilot A request
corrected (2026-10-31). Earlier header, kept for the record: approved adjudication
(rubric 7, 18–20) applied and Pilot A request drafted (2026-10-31).
Earlier header, kept for the record: extraction-review remediation done (2026-10-31); hard stop before
the pilot, one adjudication PENDING. The independent extraction review
(`logs/extraction-review-0r3d__40/`) closed the ten close-out counter-examples and found R1–R6,
the XML validation-cap attribution and a rubric-scope question; R1–R3, R5, R6 and the XML cap
are fixed, R4 exits safely, the scope question is recorded as a PENDING proposed adjudication
in `preregistration.md` 2.4 (not in force), each with regressions (section "Extraction-review
remediation"). No model, judge or paid call; nothing committed, frozen or started.
Earlier header, kept for the record: close-out review remediation done (2026-10-31). The close-out review (`logs/pilot-closeout-review-wzwtf89y/`) closed B2, B4, I7
and I8 and kept four B3 points, the coverage threshold, I6, the pre-flight boundary and the
launcher's multi-sample case open; the extraction layer of the 1137e2bb checks was rebuilt as
an explicit pipeline and the other items fixed, each with regressions (section "Close-out
review remediation"). No model, judge or paid call; nothing committed, frozen or started.
Earlier header, kept for the record: final-review remediation done (2026-10-31). The independent final review (`logs/pilot-final-review-ogcsjzyp/`) kept B1, B5
and I1–I5 closed and found B2, B3, B4, B6 partly open and I6–I8 open, plus the Docker
tag-lookup misfire; every item was reproduced from its probe evidence, fixed, and covered
by in-repository regressions (section "Final-review remediation"). No model, judge or paid
call was made; nothing is committed, frozen or started. Earlier header, kept for the
record: Pilot-A pre-review remediation done (2026-10-31). An independent pre-review of the Pilot-A readiness found six blocking
and eight important defects (B1–B6, I1–I8; evidence in `logs/pilot-a-review-6uxm37u9/`);
all were reproduced from that evidence, fixed, and covered by targeted counter-example
regressions (section "Pilot-A pre-review remediation"). No model, judge or paid call was
made; nothing is committed, frozen or started. Earlier header, kept for the record:
Stage 3b complete through the grading chain for the pilot task; hard
stop before the pilot (2026-10-30). Infrastructure items (commit
`efea742bceb304af841d0515cc48f256b2e64a24`), then: C2 approved, provider model lists
queried, Inspect cost limit verified and wired as a safety net, partial-collection
attribution written into the grading decision, and the 1137e2bb grading chain
(extraction, deterministic checks, judge assembly with a stub, review materials, entry
point, fixtures, costs) implemented and tested without any real model or judge call. The
grading-chain work is uncommitted. Nothing is frozen; the pilot has not started.
Stage 3a is committed as `395d1da626c12fe5b5b0443c0737a8c02b2b614b`. Stage 2 is committed as
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
  deliverable failures *[superseded 2026-10-30/31: a partial collection is routed by the
  per-item attribution — model-caused items are treated as not delivered and the run is
  graded, harness-caused items make the run a harness error, unknown items require a
  recorded adjudication; see "Execution-budget attribution policy" and PLAN.md section 4]*.
  `for_grading=False` permits inspection of valid error records,
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
   outcome, persistent listing failure, unrecovered partial *[now: partial routed by the
   three-class attribution, see the policy section of 2026-10-30]*, execution error/limit,
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

### Second Stage 3b round (2026-10-30): rulings, commit, model lists, cost limit, attribution

- **1137e2bb C2** approved with the revised text (drill-down out of the critical core, graded
  under rubric 14); `preregistration.md` 2.4 updated, section 4 item 1 closed. Every critical
  criterion now carries APPROVED status.
- **Commit** `efea742bceb304af841d0515cc48f256b2e64a24` "feat: add launcher with budget
  ledger, input integrity and image checks" (16 files: PLAN.md, config.json, docs/status.md,
  pyproject.toml, uv.lock, harness/{collect,samples,tools,budget,launcher}.py, five new test
  modules, and `preregistration.md` added for the C2 ruling approved in the same message);
  pushed to origin. Exclusions confirmed before the commit (no .env, private/, plan/,
  parquet, inputs/prompts/gold/resources, PDFs, logs/, .eval files).
- **Provider model lists** (`.env` now exists with ANTHROPIC_API_KEY, OPENAI_API_KEY,
  GOOGLE_API_KEY; mode 0600; ignored): `scripts/list_provider_models.py` loaded the keys into
  the trusted process (names recorded, values never printed), queried each models-list
  endpoint with full pagination and wrote `data/provider_model_lists/20261030T223043Z.json`
  (queried 2026-10-30T22:30:39Z). Anthropic (SDK 2.3.0): 14 ids, 1 page, 1 request, cursor
  pagination with no further page, complete — `claude-haiku-5-5`, `claude-sonnet-5-5`,
  `claude-opus-5-5`, `claude-fable-5-1`, `claude-opus-5`, `claude-sonnet-5`, `claude-fable-5`,
  `claude-opus-4-8`, `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-opus-4-6`,
  `claude-opus-4-5-20251101`, `claude-haiku-4-5-20251001`, `claude-sonnet-4-5-20250929`.
  OpenAI (SDK 3.41.0): 134 ids, 1 page, 1 request (the list endpoint returns one page; the SDK
  reported no further page), complete; includes `gpt-6.1-sol`, `gpt-6.1-terra`, `gpt-6-astra`,
  `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`. Google
  (google-genai 2.34.0): 60 ids, 1 page, 1 request, page-token pagination, complete; includes
  `models/gemini-3.1-pro-preview` and `models/gemini-3.1-pro-preview-customtools`.
  Candidates visible for the respective keys: `claude-opus-5-5`, `claude-sonnet-5-5`,
  `gpt-6.1-sol`, `gemini-3.1-pro-preview`. No generation call was made; visibility does not
  establish generation, tool use, image input or reasoning-parameter availability.
- **Inspect cost limit** (0.3.286) verified in code and triggered with the mock model
  (`harness/tests/regress_cost_limit.py`, 14/14 checks, results under
  `logs/stage3b-20261030T220004Z/cost_limit_run2/`): `eval(cost_limit=X)` opens a per-sample
  dollar limit; after every generate call Inspect prices the usage (`model_usage_cost`),
  records it (`record_model_cost`) and checks the limit; a hit raises `LimitExceededError`
  type `cost` and records `SampleLimitEvent(type="cost", limit=X, message="Cost limit
  exceeded. value: $…; limit: $…")`; the sample ends `limit.type == "cost"`, scorer and
  cleanup still run. Price data: `set_model_cost()`/`model_cost_config` accept only models in
  Inspect's database; the mock needed `set_model_info(…, ModelInfo(cost=ModelCost(…)))`
  (synthetic 1,000 USD per MTok). Case a (limit 2.0 USD): first tool call wrote two files,
  the second generate tripped the limit → `limited`, `limit_types=["cost"]`, running value
  2.395 USD in the message, `collection_status=complete`, `grading_eligible=true`. Case b
  (limit 0.5 USD): tripped on the first generate (0.754 USD) → `no_files_confirmed`,
  eligible. Harness: `BUDGET_LIMIT_TYPES` now includes `cost`; `config.json` carries
  `cost_limit_usd` as a PLACEHOLDER (about 3× the expected per-task consumption after A/B
  selection; safety net, the ledger stays primary) and the policy text; the launcher's
  `eval_kwargs` adds `cost_limit` and `model_cost_config` only for a numeric value and
  `verify_cost_data()` fails closed when the model has no complete price data. The first
  cost-limit run did not start: `docker compose` reported "pull access denied for
  gdpval-sandbox" although the image is local — the third occurrence of the daemon's
  transient image-visibility fault (kept under `cost_limit/`; rerun passed).
- **Partial-collection attribution** written into `grading_decision()` as the single rule
  (`harness/collect.py`: `attribute_item`, `attribute_collection`, `effective_attribution`,
  `load_adjudication`): model-caused = entries the model created that are not regular
  files (symlink, broken symlink, symlinked directory, fifo, socket, device, unknown type),
  evidenced by the collector's lstat classification; harness/provider-caused = collector
  deadline (`read_deadline_exceeded`, `time_budget_exceeded`), host conflicts and host-side
  destination problems, enumeration failures; unknown = `read_failed:*`,
  `integrity_mismatch`, `oversized`, `file_limit`, `total_limit`, refused listing paths and
  item-level enumeration errors (never attributed by the reason name). Routing: any
  harness-caused item → `harness_collection_error`, `grading_eligible=false` (run error,
  never model failure); otherwise any unknown → `requires_adjudication`
  (`grading_eligible=false`, `harness_error=false`, no automatic verdict); only all-model-
  caused → eligible with `outcome_class=collected_with_model_caused_rejections` and the
  rejected files treated as not delivered. `no_files_confirmed` is graded as before. Each
  item carries source, path, reason, class, basis and an evidence locator
  (`collection.json skipped[i] / files[sandbox_path=…] / listing_errors[i]`); the collection
  record and `run_outcome.json` both store the attribution; `harness_error` is true only for
  enumeration failure or a harness-caused item. A human adjudication lives in a separate
  `adjudication.json` (run binding, `{path: model_caused|harness_caused}`, by, at, basis),
  is applied by `load_run_outcome()` to unknown items only, can never make a harness-caused
  item eligible, and never modifies the stored outcome (`effective` block in the loaded
  result). `load_run_outcome` re-derives the attribution from the evidence and fails closed
  on disagreement. Regressions: `harness.tests.test_attribution_unit` (10 tests: model-caused
  only gradable with rejections recorded; deadline → run error; read failure → adjudication;
  harness+model mixed → run error; unknown+model mixed → adjudication; adjudication resolves
  unknown without touching the outcome, cannot rescue harness-caused, rejected for another
  run; tampered attribution fails closed; `no_files_confirmed` unchanged; rule table) plus
  updated expectations in the collector, closeout, policy and limits tests; all 101 unit
  tests pass; `regress_inspect` 62/62 with the adversarial scenario now asserting 4
  model-caused special entries, 1 unknown (oversized), `harness_error=false`.

### Grading chain for 1137e2bb (2026-10-30; no real model or judge call)

New package `grading/` (trusted side, never model-visible):

1. **Extraction on copies** (`grading/extract.py`): inventory with sizes and SHA-256; every
   deliverable copied to a work directory before any read (collected originals are 0444
   and untouched); xlsx read twice with openpyxl (formulas and cached values per cell,
   pivot definitions with cache source and row/data fields, tables, auto-filters), docx
   paragraphs with style names and tables; LibreOffice headless recalculation of the copy
   inside the trusted image (`docker run --network none --cap-drop ALL`, scratch mount
   only) recorded next to the cached values with the three-way comparison equal / differs
   / cached_missing / recalculation_failed, and recalculated values filled into formula
   cells that had no cached value (each such cell recorded as `recalculated`). Verified on
   the Stage 2 formulas fixture: 4 formula cells, 0 cached → 4 recalculated, `C5 = 43.75`
   from `=SUM(C2:C4)`.
2. **Deterministic checks** (`grading/checks_1137e2bb.py`): D items 1–10, 12–22, 25, 26,
   31–62 (the earlier D list omitted the presence item 2 and item 21; corrected in
   `preregistration.md` 2.4 as a documentation fix, no semantic change). The detail sheet
   is located by matching the 41 (PO, SKU, units) keys of the input; flag, total and
   summary-text columns by header keywords; the summary sheet by a per-SKU block with
   price/case/total columns, its grand-total row, auto-filter or table or pivot, and a PO
   field anywhere on the sheet (rubric 14). Every item records pass / fail /
   cannot_assess, an evidence locator (file, sheet, header row, rows or cells), the
   deliverable value and the reference value from the independent recalculation (never
   the expert deliverable); prices are compared at two decimals half-up, counts exactly;
   missing structure yields `cannot_assess` with `extraction_failed: …`. Critical status
   from the deterministic items (C3 stays `not_confirmed` until its judge items are in).
3. **Judge assembly** (`grading/judge.py`): one unit per J item (11, 23, 24, 27–30) with
   task requirement, criterion text, the independent reference the item needs (counts per
   SKU and in total; reference flags per line for item 11; the prompt's definitions for
   item 23) and the deliverable excerpt (indexed docx paragraphs and tables, or the detail
   rows with flags and summary text); a fixed system prompt that demands one JSON object
   (verdict, locatable evidence, rationale), states that deliverable text is untrusted
   data and must never be followed as instructions, and forbids inferring the worker's
   identity; units carry the execution uuid only. `render_batch()` sends one task's units
   in one request with separate unit ids and evidence. `parse_judge_response()` validates
   verdict, evidence (file, location, quote; non-empty for pass/fail) and rationale.
   `StubJudge` (keyword rules) exercises assembly and parsing only. The items used with the
   stub are recorded in `grading/debug_set.json` and are excluded from judge validation.
4. **Human-review materials** (`grading/review.py`): `review_<uuid>_items.md` shows, per
   criterion, the criterion text, the deterministic result with the compared values, the
   reference and the deliverable excerpt — no judge verdict; `review_<uuid>_judge_verdicts.json`
   holds the verdicts separately ("open only after the independent judgments are
   recorded"); `review_<uuid>_independent_judgments.csv` is the record template (run,
   item, weight, criterion, judgment, evidence, time, reviewer).
5. **Grading entry point** (`grading/grade.py`): binding from the completed Inspect log;
   `load_run_outcome(for_grading=False)`; terminal-log join (sample error vs recorded
   errors, sample limit type vs recorded limit types, eval status terminal, not cancelled)
   — any mismatch is `log_join_mismatch` and blocks grading; routing by the effective
   outcome (adjudication applied if present): not eligible → results record with the
   reason, no grades; eligible (complete, no_files_confirmed, model-caused partial, limited)
   → extraction, deterministic checks, judge units (injected judge), `grades.jsonl` (one
   line per item with source D/J, verdict, evidence, compared values or rationale) and
   `results.jsonl` (run binding, gate, collection and execution status, limit types,
   attribution class and items, rejected files treated as not delivered, W/E/P, P/E, E/W,
   ungraded items with reasons, critical status per criterion, review-material paths).
6. **Fixtures** (`grading/fixtures_1137e2bb.py`): the positive deliverable is built from
   the original input workbook and the recalculation script's verified values (flag
   columns, missing-case-pack indicator, totals, error summary; Summary sheet with per-SKU
   counts sorted by total, grand total, auto-filter and a PO drill-down block; docx with
   the two definitions, the counts, the high-frequency SKUs and recommendations for
   SKU-0103 and SKU-0112). Six negatives plant one error each: one line flag wrong, one
   SKU total wrong, grand total off by one, an EA line treated as CASE, summary total
   inconsistent with the detail sheet, docx missing. The expert deliverable is not used.
7. **Costs** (`grading/costs.py`): generation cost from usage × unit prices per model and
   category (reusing the ledger pricing), grading cost from judge usage, a human-time CSV
   template; unknown prices and retry estimates are flagged, never silently filled.

Results (`grading.tests.test_grading_chain`, 15 tests, exit 0; harness suites 101/101
unchanged):

*[Superseded 2026-10-31 (Pilot-A pre-review, I8): the independent probes showed that this
chain graded header synonyms as FAIL, passed swapped Word counts, graded a failed
recalculation as FAIL, accepted a log with an eval-level error, accepted the stub judge
without a test-mode gate, overwrote the human-review CSV, and that "harness suites 101/101
unchanged" stopped holding once the launcher test had to change. The corrected behaviour
and its regressions are in section "Pilot-A pre-review remediation".]*

- Deterministic discrimination: positive → every D item passes, C1 pass, C2 pass, C3
  not_confirmed (judge pending), no `cannot_assess`; `one_line_flag_wrong` → items 5, 15,
  17, 18, 20, 32 fail (C1 fail); `one_sku_total_wrong` → 58; `grand_total_off_by_one` →
  17; `case_ea_conversion_error` → 6, 7, 16, 17, 19, 20 (C1 fail); `detail_summary_mismatch`
  → 15; `docx_missing` → 2, 25, 26 (C3 fail). All six negatives are detected by the items
  that name the planted error.
- Judge assembly: 7 units on both fixture sets; all stub responses parse; stub verdicts
  pass on the positive and fail items 23–30 on `docx_missing`; malformed judge outputs
  (no JSON, invalid verdict, empty evidence for pass, incomplete evidence) are rejected.
- Entry point: complete → graded, W/E/P = 80/80/80, P/E = 1.0, E/W = 1.0, critical pass,
  62 grade lines (55 D + 7 J), review files written with the judge verdicts apart from the
  items file; negative → P/E < 1 and C1 fail; limited (time) + complete → graded and
  flagged; execution error → not graded; `listing_failed` → not graded (harness error);
  model-caused partial (a symlink the model left) → graded with the rejected path listed;
  harness-caused partial (collector deadline) → run error, not graded; unknown partial
  (read failure) → waits, then graded after a recorded adjudication with the undelivered
  docx failing its presence item; missing, corrupt and identity-mismatched outcomes
  refused at the gate; a log that records an error or a limit the outcome does not know
  → `log_join_mismatch`; `no_files_confirmed` → graded with P = 0 and critical fail.
- Costs: 1M input + 100k output on gpt-6.1-sol prices = 3.00 USD, one retry estimated at
  2.00 USD, flagged as estimated; unknown-price models are reported as unknown.

Not verified in this round: deterministic checks on a real model's deliverable (column
naming and layout heuristics were exercised on the fixtures only; unrecognised layouts
yield `cannot_assess` with `extraction_failed`, to be repaired before formal grading)
*[retracted 2026-10-31: the pre-review showed that renamed headers yielded FAIL, not
`cannot_assess`; the checks were rewritten, see the remediation section]*;
any real judge call, judge agreement, and the real judge's compliance with the output
schema; grading of the other nine tasks (checks and judge units exist for 1137e2bb only);
the recalculation path on a real deliverable (exercised on the Stage 2 fixture).

### Pilot A/B DRAFT configuration written (2026-10-30; config.json and this file only)

Scope: `config.json` updated with the proposed pilot models, limits, budget and reporting
labels for the independent re-check; `docs/status.md` records the decisions. No launcher,
harness, test or other file changed; no model, judge or provider API call; `.env` not read;
nothing committed, pushed or frozen.

- **Proposed models** (`models.pilot_models`, DRAFT): A = `claude-opus-5-5`
  (`anthropic/claude-opus-5-5`), B = `gpt-6.1-sol` (`openai/gpt-6.1-sol`), judge =
  `gemini-3.1-pro-preview` (`google/gemini-3.1-pro-preview`). All three were visible in the
  2026-10-30 models lists; generation, tool use, image input and reasoning behaviour are
  unverified until the pilot.
- **Identifier contract checked** (read-only, `harness/launcher.py` l. 31, 66, 196–205, 326
  and the Inspect providers): the launcher takes the Inspect name `provider/model_id` on
  `--model`, does not add or strip prefixes, resolves the credential variable from the
  prefix (a bare id raises `KeyError` before any call, it is not mis-routed), and the ledger
  price keys derived from the candidate facts (`claude-*` → `anthropic/`, `gpt-*` →
  `openai/`, else `google/`) match the three Inspect names; Inspect strips the prefix
  before the API call and the Google SDK accepts the bare `gemini-3.1-pro-preview` although
  the list endpoint returns `models/…`. No mismatch found. Two launcher gaps registered:
  **Blocking** — `eval_kwargs` does not pass `max_tokens` (and `token_limit` is still a CLI
  argument, not read from the config); **Important** — `--model` form is not validated.
- **Reasoning / effort**: nothing is set by the harness; provider defaults apply, and
  "not set" is recorded as "pilot verification pending", not as a verified default.
  Documented defaults (queried 2026-10-30): Opus 5.5 — thinking on and not disableable,
  default effort `medium`, thinking tokens billed as output and counted toward `max_tokens`
  (platform.claude.com effort and thinking pages); gpt-6.1-sol — default reasoning effort
  `medium`, `none`/`minimal` unsupported, reasoning tokens count toward `max_output_tokens`
  and are billed as output, cut-off → `status: incomplete`, `incomplete_details.reason:
  max_output_tokens` (developers.openai.com reasoning guide); gemini-3.1-pro-preview —
  thinking on at level `high` by default, `max_output_tokens` includes thought tokens,
  billed as output (ai.google.dev thinking page). Inspect 0.3.286 request construction
  (source): Anthropic sends `max_tokens` (default 32,000 if unset) and no `thinking` /
  `output_config` unless an effort is configured; OpenAI uses the Responses API for
  gpt-6.1 and sends `reasoning` only when configured, `max_output_tokens` only when
  `max_tokens` is set; Google sends `ThinkingConfig(include_thoughts=True)` without a level
  and `max_output_tokens` from `max_tokens`. Stop signals are preserved in the log
  (`StopReason` `max_tokens` from Anthropic `stop_reason`, OpenAI `incomplete_details`,
  Google `finish_reason MAX_TOKENS`). Metering differences recorded: Anthropic output
  includes thinking with no separate count in Inspect; OpenAI and Google report reasoning
  tokens separately and include them in output; input tokens exclude cached tokens on all
  three. The two models do not get equal compute budgets (effort semantics, prices and
  tokenizers differ); results are reported per model.
- **Limits and budget** (`generation`, `pilot`; DRAFT, pending final approval):
  `cost_limit_usd` 10 per sample (safety net, price data required, ledger primary),
  `token_limit` 10,000,000 per sample (Inspect type `all`: every call's input and output
  count), `max_tokens_per_request` 16,384 (reasoning tokens count toward it on all three
  providers), `time_limit` 3,600 s, `working_limit` 3,600 s, `message_limit` 200; pilot
  cumulative ceiling raised from 25 to 30 USD (A, B, judge, cache charges, billable
  retries). Tool timeout, concurrency, retry layers and sandbox settings unchanged. The judge
  now has numeric prices in `candidate_facts` (2 / 12 USD per MTok, ≤ 200k tier) so the
  ledger can settle judge batches; Gemini cache-write is modelled at the input price
  (no per-token write price exists) and OpenAI cache-write likewise.
- **Report labels** (`reporting.limit_labels`): `cost-capped` (Inspect `cost_limit` fired,
  event and amounts kept), `budget-limited` (time / working / message / token limit fired,
  `SampleLimitEvent` kept), `output-capped` (one generation cut by `max_tokens`, shown by the
  provider's stop signal only, never by length; not a sample-level exhaustion; detection
  logic is a **pre-freeze TODO**). Several limits in one execution keep every event.
  Limited attempts follow the approved `grading_decision` / `run_outcome.json` policy.

Pilot verification pending (cannot be settled from documentation or source): the effort
level each account actually applies; thinking/reasoning token shares and their effect on
the 16,384 cap in an agentic loop; Anthropic beta-header needs above 8,192 output tokens on
Claude 5; Responses API tool-schema and image delivery; judge schema compliance under
default thinking; preview availability of the judge; real cost per task.

### Hard stop (end of the second Stage 3b round)

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

## Pilot-A pre-review remediation (2026-10-31; B1–B6, I1–I8; no model, judge or paid call)

Scope and boundary: the independent pre-review (evidence in `logs/pilot-a-review-6uxm37u9/`,
read-only, kept) reported Blocking B1–B6 and Important I1–I8. Each finding was first
reproduced from the saved probe evidence and the probe scripts (static probes, launcher
and budget probes, extra probes, LibreOffice probe), then fixed with a targeted
counter-example regression. Only these items were changed: no harness redesign, no rubric
or policy change, no recalculation of another task, no real model or judge call, no commit,
push, freeze or Pilot A. Every active Inspect regression ran through
`harness/tests/run_isolated.sh` (`env -i`, external working directory with no `.env` on its
path, `INSPECT_DISABLE_MODEL_API=1`, `mockllm/model`); the project `.env` was not read,
loaded or printed; probe files live in temporary directories outside the repository; new
logs are under `logs/pilot-a-remediation-20261031T002107Z/` and no existing log was
overwritten (169 pre-existing `logs/stage2_fix` files: hashes unchanged, 44 files added by
the rerun); the sandbox image `gdpval-sandbox:stage2` (`18cde712cde1`) was reused, not
rebuilt; no container was left behind; no dependency was installed.

### Fixes (file references are to the working tree of 2026-10-31)

- **B1 — execution settings not dispatched.** `harness/launcher.py` `eval_kwargs` now
  passes `max_tokens` (from `generation.max_tokens_per_request`), `attempt_timeout`
  (`retries.layer_1_inspect_model_request.attempt_timeout_s`) and `token_limit` (from
  `generation.token_limit` unless overridden); each must be a positive integer or the
  launcher refuses to start. `run_sample` computes the settings *before* any ledger change,
  so a configuration defect creates neither a reservation nor a settlement. The DRAFT
  `config.json` gap entry is closed (`launcher_contract.gaps_registered`); the `--model`
  form validation gap stays open.
- **B2 — terminal eval-level error passed the gate.** `grading/grade.py` `join_log` blocks
  grading when `EvalLog.error` is present or the eval status is `error` without a sample
  error (the pre-review's `late_eval_error` probe). A human may exclude such an error only
  with a complete record `{"basis", "by", "at"}` passed as `eval_error_exclusion`; it is
  stored in `results.jsonl` (`log_join.eval_error_exclusion`). A consistent terminal error
  (sample error recorded in the log and the outcome) is not a join mismatch and is routed
  by the outcome policy as before.
- **B3 — layout mistaken for model failure.** `grading/checks_1137e2bb.py` rewritten:
  a canonical field schema with header synonyms (`SCHEMA`, `FLAG_SCHEMA`, `map_columns`;
  exact match, then containment, then keyword rules for the four added columns); the detail
  sheet is located by mapped PO / SKU / ordered-units headers *and* input line keys, never
  by sheet name or position; a required source field that cannot be mapped makes every
  dependent item `cannot_assess: extraction_failed` with attribution `grader_extraction`,
  and the summary sheet is never guessed when the detail sheet is not located. Extraction
  and verdict are separated per cell (`read_value`: ok / empty / formula_unrecalculated /
  error_value): a formula without cached value whose recalculation failed or did not run is
  `cannot_assess` with attribution `grader_caused_recalculation`, never FAIL. Before any
  model attribution the workbook's transfer integrity is checked in `grade.py` (collector
  `sha256_in_sandbox` == `sha256_collected` == hash of the copy on disk) and its format in
  `extract.format_check` (zip, `[Content_Types].xml`, workbook part, openpyxl load): an
  unreadable workbook with verified transfer is `model_caused_corrupt` (FAIL on item 1 and
  every workbook item), with unverified transfer `unknown` (`cannot_assess`), a missing
  workbook `model_caused_missing` (FAIL). Every grade line carries `attribution`; the
  result record carries `transfer_integrity` and `extraction_status`.
- **B4 — row set and narrative counts.** `row_completeness` compares the multiset of
  business rows (PO, SKU, units, entered and expected price at two decimals, UOM, case
  pack) with the input and names missing, extra and duplicated rows; the row-set items
  (5–9, 18–20) fail with the named rows while per-line items (31–55) are judged on the lines
  that are present; reordering is harmless. Items 18–20 still report the detail-sheet sum.
  `bound_counts` / `count_verdict` bind a number to its category phrase at paragraph level
  (number before the phrase, or phrase then a connector then a number); no bound number or
  conflicting numbers give `cannot_assess` (attribution `unknown`, routed to judge/human),
  never a pass.
- **B5 — recalculation reused an earlier result.** `grading/extract.py` `recalculate_xlsx`
  uses a fresh `mkdtemp` scratch directory per call with an empty output directory, checks
  soffice's own exit status (`SOFFICE_RC=` echoed by the in-container script, not the exit
  status of a later command), requires exactly one new non-empty `in.xlsx` in that
  directory, rejects "could not be loaded", runs `format_check` on the product, and records
  input and output SHA-256; any failure returns `status: failed` with a reason and no
  values. `extract_all` records `format` and `sha256` per workbook and routes unreadable
  workbooks separately.
- **B6 — engineering counts, stop conditions, unknown cost, ledger integrity.**
  `harness/budget.py` version 2: the event set is `reservation`, `settlement`, `void`,
  `engineering_failure`, `stop`, `review_cleared`; every event is schema-validated and the
  transitions are checked on every load (duplicate open reservation, settlement or void
  without reservation, kind mismatch, clearance without pending review) — an unknown event
  type or a malformed event raises `LedgerCorrupt` and the ledger refuses to load; the
  first creation happens under the inter-process file lock. A repeated reservation is
  idempotent only for the same kind, estimate and binding (model, task, sample, run),
  otherwise `LedgerConflict`. `launcher.classify_eval_log` turns an error *returned* in the
  Inspect log (`fail_on_error=False`) into a persisted `engineering_failure` (class from the
  message prefix, redacted detail); the second occurrence of a class is a stop condition; a
  settlement above twice its reservation records a `stop` event; stop state survives
  restarts. Usage with no reliable price is settled at max(priced part, reservation),
  flagged `estimated_unknown_cost`, kept with its raw usage, and holds every further start
  until a `review_cleared` event (`clear_review(unit, by, basis)`); nothing is settled as
  zero.
- **I1 — review records overwritten.** `grading/review.py` writes the items file and the
  judge-verdict file as new versions (`_v2`, `_v3`, …) with mode `x`, and never touches an
  existing independent-judgments CSV (its SHA-256 and `preserved` flag are returned).
- **I2 — stub and batch protocol.** `grade_run` refuses a judge with `is_stub` unless
  `allow_stub=True` (test mode) and records `judge_mode` (`real` / `stub-test-mode` / `none`)
  in `results.jsonl`. `grading/judge.py` adds the batch protocol: `parse_batch_response`
  requires a JSON array in which every expected unit id appears exactly once (missing,
  duplicated or extra ids fail the whole batch), `judge_batch` records a protocol violation
  as `cannot_assess` with `batch_error` for every unit, `StubBatchJudge` produces the
  deliberately corrupted responses for tests, and `estimate_judge_batch_usd` gives the
  ledger reservation estimate for one batch.
- **I3 — agreement disclosure.** All seven judge-only criteria of `1137e2bb…` (11, 23, 24,
  27–30) were used to debug the assembly with the stub (`grading/debug_set.json`), so no
  held-out criterion exists on the pilot task: judge agreement will be reported from the
  other tasks, and the pilot task's judge verdicts are checked by human review only
  (`PLAN.md` section 6).
- **I4 — concurrent initialisation.** Ledger creation and the ceiling check run under the
  file lock; a regression starts six processes (spawn) that each construct the ledger and
  reserve concurrently: exactly the affordable number of reservations is recorded (1 of 6
  at 20 USD each under a 30 USD ceiling; 2 of 6 at 12; 6 of 6 at 4), no duplicate or
  leftover temporary file. Acceptance conditions before any run with concurrency above 1:
  this process-level test green, plus observed reservation/settlement records from the
  concurrency-1 pilot.
- **I5 — compose pull behaviour.** `harness/compose.yaml` declares `x-local: true` and
  `pull_policy: never`. Verified against Inspect 0.3.286 source and by a mock run: with
  `x-local`, `docker.py` skips `compose pull` for the service and `compose.py`'s
  `sandbox_prebuilt` verification *applies* to it (it checks `docker image inspect <image>`
  and raises `PrerequisiteError` before any `compose up` when the image is absent); services
  without `x-local` are not checked there and would be pulled. The comment written earlier
  in this round ("x-local skips the prebuilt check") was wrong and is corrected in the file.
- **I6 — secrets in records.** `launcher.redact` (and the same rule in
  `scripts/list_provider_models.py`) replaces credential-like strings, `key=value` secrets,
  any long token carrying a digit, and the user name in host paths, then truncates; it is
  applied to every persisted error text (ledger failure details, launcher records, model
  list errors). Only the exception type and the redacted message are stored.
- **I7 — price tiers.** `config.json` candidate facts now carry the documented tiers and
  the usage-field mapping per provider: gpt-6.1-sol cache write 30 m 2.50 / 12 h 5.00 USD
  per MTok and long context above 272K input tokens (4 / 15 / cached 0.20 / cache write 5.00
  and 10.00); Opus 5.5 cache write 1 h 8.00 (5 m 5.00); gemini-3.1-pro-preview long context
  above 200k (4 / 18 / cached 0.40). The ledger (`prices_from_config`) prices each model
  call at its own tier from the per-call usage in the Inspect ModelEvents
  (`calls_from_eval_sample`), cache writes at the conservative longest-retention rate
  (the usage record does not split retention tiers; flagged), and aggregated usage above a
  threshold entirely at the long-context tier (flagged). The Inspect `cost_limit` safety
  net uses the same conservative rates. *[Corrected 2026-10-31 (final review, I7): the last
  sentence was wrong and the "longest-retention" rule was not verified against Inspect.
  Inspect 0.3.286 bills Anthropic cache writes at `ModelCost.input_cache_write` times 1.6
  when its provider reports a 1h TTL, so a pre-baked 1h rate would have been applied twice,
  and it has no long-context tier. The ModelCost passed to Inspect now carries the
  default-TTL rate (A 5, B 2.50, judge 2), the ledger uses 8 for A (auto-TTL escalation is
  invisible in usage; conservative, flagged) and 2.50 for B (the harness requests no
  extended retention); see section "Final-review remediation".]*
- **I8 — records.** Earlier claims corrected (notes added next to the old text, old
  records kept): "unrecognised layouts yield `cannot_assess`" (they yielded FAIL),
  "terminal log errors block grading" (an eval-level error with a clean sample passed),
  "the stub is never part of formal results" (no gate existed), "batch judge verified"
  (only the rendering existed; the response protocol did not), "harness suites 101/101
  unchanged" (the launcher test had to change in this round), and "all partial collections
  are harness errors" (superseded by the attribution policy of 2026-10-30).

### Regressions (2026-10-31; `run_isolated.sh`, `INSPECT_DISABLE_MODEL_API=1`, mockllm, prebuilt image; logs under `logs/pilot-a-remediation-20261031T002107Z/`)

| Suite | Command (via `harness/tests/run_isolated.sh /Users/yuning/turing-th …`) | Exit | Result | Class |
|---|---|---|---|---|
| grading chain (B2, I1, I2, transfer integrity) | `grading.tests.test_grading_chain -v` | 0 | 19/19 OK | synthetic (fake completed logs, real collector) |
| layout / integrity / row set / Word counts / recalc path (B3, B4, B5) | `grading.tests.test_layout_regressions -v` | 0 | 22/22 OK | synthetic fixtures, fake converter |
| launcher and ledger (B1, B6, I4, I6, I7) | `harness.tests.test_launcher_regressions -v` | 0 | 15/15 OK | synthetic (spy eval, fake logs, spawn processes) |
| existing harness unit suites | `unittest harness.tests.test_budget_unit … test_staging_unit -v` | 0 | 101/101 OK | synthetic |
| compose local image (I5) | `harness.tests.regress_compose_local --output-root …/compose-local` | 0 | 15/15 PASS | real Inspect + Docker chain, mock model |
| LibreOffice recalculation (B5) | `grading.tests.regress_recalc_docker --output-root …/recalc-docker` | 0 | 12/12 PASS | real Docker converter |
| Stage 2 Inspect scenarios | `harness.tests.regress_inspect` | 0 | 62/62 | real Inspect + Docker chain |
| close-out gate | `harness.tests.regress_closeout --output-root …/closeout` | 0 | 92/92 | real Inspect + Docker chain |
| execution limits | `harness.tests.regress_limits --output-root …/limits` | 0 | 74/74, 0 unverified | real Inspect + Docker chain |
| Inspect cost limit | `harness.tests.regress_cost_limit --output-root …/cost-limit` | 0 | 14/14 | real Inspect + Docker chain |
| image tools | `harness.tests.regress_tools --output-root …/tools` | 0 | 8/8 | real Inspect + Docker chain |

First attempts that failed and what they showed (logs kept): the grading chain's
consistent-error case was blocked by an extra sample-event count check added during the
fix (removed: not part of B2, and it coupled the gate to transcript details); the layout
suite found that `Item SKU` on the summary sheet was not recognised (summary locator now
uses the schema synonyms) and that item 10 lacked an attribution when recalculation failed
(added); the tier test expected the standard rate for a 1M-token cache-write prompt, which
is correctly the long-context tier (test corrected, not the code); the compose regression's
first attempt (`compose_local_attempt1_daemon_tag_misfire.log`) hit the Docker tag-lookup
misfire described under "Known issues" and showed that the `x-local` comment was wrong.

Layout table (`layout_table.json`; items in `fail` / `cannot_assess`, attribution):

| Variant | fail | cannot_assess | attribution | class |
|---|---|---|---|---|
| positive, sheet_names, header_row, column_order, header_aliases (review set), header_aliases_2, units_header_only, reordered_rows, formula_recalc_ok | none | none | — | graded like the positive fixture (C1 pass, C2 pass) |
| unrecognised_headers | none | all 51 workbook items | grader_extraction | grader-side, not model |
| formula_recalc_failed | none | 37 flag-dependent items | grader_caused_recalculation | grader-side, not model |
| corrupt_xlsx_transfer_verified | item 1 + 51 workbook items | none | model_caused_corrupt | model |
| corrupt_xlsx_transfer_unknown | none | item 1 + 51 workbook items | unknown | undetermined |
| missing_xlsx | item 1 + 51 workbook items | none | model_caused_missing | model |
| duplicate_and_missing_row | 5–9, 18–20 (missing PO1007/SKU-0101/2, duplicated PO1005/SKU-0101/60 named) | none | model_caused | model; 31–55 still pass |
| duplicated_zero_error_row | 5–9, 18–20 (42 rows, 1 extra) | none | model_caused | model (passed everything before) |
| swapped_word_counts | 25, 26 (10 vs 15, 15 vs 10) | none | — | model (passed before) |
| conflicting_word_counts | none | 25 ([14, 15]) | unknown | judge/human |
| unbound_word_counts | none | 25, 26 | unknown | judge/human |

B4 result classes: pass (bound number equals the reference; complete row multiset), fail
(bound number differs; missing, extra or duplicated business rows named), cannot_assess
(no bound number or conflicting numbers; unmapped field; unrecalculated formula) — never a
pass by coincidence of numbers, never a fail from layout.

B5 through the real converter (`recalc-docker/results.json`): formula workbook input
`98d53388…d30b` → output `808fe72b…a839`, `soffice_rc` 0, 123 formula cells filled, all
deterministic items pass from recalculated values; damaged input `1a658db4…1037` →
`status: failed`, `soffice_rc` 134 (LibreOffice aborted with a stack trace), produced only
a lock and a temp file, no values, fresh scratch directory; valid input again → ok with the
same recalculated values (output bytes differ between conversions, so output hashes are
recorded, not compared); the three input files' hashes are unchanged. The pre-review's
probe had seen LibreOffice exit 0 on a damaged input; both exits are now failures.

B6 stop conditions (ledger-derived, persisted): remaining budget below the next
reservation; ceiling reached; the same engineering failure class twice (returned error logs
count); a settlement above 2× its reservation; per-task cost above 2× its estimate; unknown
actual cost pending review; a recorded stop. Regression evidence: three returned error logs
→ two starts, the third refused with the class named, ledger `[reservation, settlement,
engineering_failure] × 2` and nothing added by the refusal, a restart still refuses and the
six original events are byte-identical; a 5 USD settlement on a 2 USD estimate → stop
recorded, next start and post-restart start refused; unpriced usage → settled at the 5 USD
reservation, flagged, next start refused until `clear_review`, then a priced start
settles at 0.002 USD; a damaged event type or a malformed/orphan event → `LedgerCorrupt`
on load; a repeat reservation with another estimate or binding → `LedgerConflict`.

### Verification classes (I8)

- Real Inspect / Docker chain with the mock model: I5 (compose, 15 checks), B5 (LibreOffice
  conversion, 12 checks), and the unchanged Stage 2 / Stage 3b scenario suites.
- Synthetic (fake logs, fake converter, fixtures, spawned processes): B1, B2, B3, B4, B6,
  I1, I2, I4, I6, I7 ledger arithmetic.
- Static (values transcribed from the pages queried 2026-10-30, not re-queried): I7 price
  tiers and usage-field mappings in `config.json`.
- Unverified until the pilot: a real judge's compliance with the batch protocol; the real
  providers' usage fields as Inspect populates them (cache-write split, reasoning tokens);
  whether Opus 5.5 has a long-context price tier (not recorded in the 2026-10-30 query;
  check before freeze); real per-task cost; output-capped detection (pre-freeze TODO).

### Remaining Pilot A gates

- Human approval of the final A/B ids, effort settings and judge; separate authorization for
  every paid call (the launcher's real mode stays disabled).
- Output-capped detection (pre-freeze TODO); `--model` form validation (Important).
- Judge: real response-format check on the first batch before any verdict is used;
  agreement on the pilot task is not available (I3).
- Docker tag-lookup misfire (see Known issues): run the launcher pre-flight immediately
  before each start; a `docker run --rm <image> true` warm-up resolved the misfire here
  but is not implemented as a launcher step (would need approval).
- Concurrency stays at 1 until the acceptance conditions under I4 are met.

Files changed in this round: `grading/checks_1137e2bb.py` (rewritten), `grading/grade.py`,
`grading/judge.py`, `grading/extract.py`, `grading/review.py`, `grading/tests/test_grading_chain.py`,
new `grading/tests/test_layout_regressions.py`, new `grading/tests/regress_recalc_docker.py`,
`harness/budget.py` (rewritten, version 2), `harness/launcher.py`, `harness/compose.yaml`,
`harness/tests/run_isolated.sh` (passes the regression table path only),
`harness/tests/test_budget_unit.py`, new `harness/tests/test_launcher_regressions.py`, new
`harness/tests/regress_compose_local.py`, `scripts/list_provider_models.py`, `config.json`
(I7 tiers, closed B1 gap, budget-protection notes), `PLAN.md`, this file. Nothing was
committed.

## Final-review remediation (2026-10-31; B2, B3, B4, B6, I6–I8, Docker image ID; no model, judge or paid call)

Scope and boundary as in the previous round: every finding was first reproduced from the
probe evidence and scripts of `logs/pilot-final-review-ogcsjzyp/` (kept unchanged, 20
files), then fixed with a counter-example regression. Only the listed items changed; no
rubric, policy or other-task change; no real model, judge or provider call; the project
`.env` was not read; all Inspect regressions ran through `harness/tests/run_isolated.sh`;
new logs are under `logs/pilot-final-remediation-20261031T032654Z/`; the 213 pre-existing
`logs/stage2_fix` files are unchanged (44 added by the rerun); no container left behind;
the image, its tag and the daemon were not modified. Nothing is committed.

### Fixes

- **B2 — no human override of a terminal eval error.** `grading/grade.py` `join_log` and
  `grade_run` no longer take an exclusion record: `EvalLog.error`, or eval status `error`
  without a sample error, blocks grading (`gate: log_join_mismatch`, `gate_reason`), with the
  original error kept redacted (`log_join.eval_error_type`, `eval_error_message`). The
  review's three-string override is rejected by the signature (`TypeError`). The block is
  evaluated before the outcome policy, so the adjudication file for unknown collection items
  cannot release a run with an eval-level or runtime error. A future exclusion mechanism, if
  ever needed, is a separate approved design.
- **B3 — unique column mapping.** `grading/checks_1137e2bb.py` `map_columns` collects every
  candidate column per field (exact synonyms; containment and keyword rules only without an
  exact candidate), withdraws a column exactly claimed by one field from the weak candidate
  lists of others, and maps a field only when exactly one candidate remains that no other
  field claims; otherwise the field is `ambiguous` with its candidates recorded. Column order
  and agreement with the reference never decide. `locate_detail_sheet` locates by PO/SKU and
  the input's (PO, SKU) pairs and accepts a sheet only when it carries at least half of them
  (`MIN_MATCH_FRACTION`), so an error drill-down block is never taken for the detail sheet.
- **B3 — explicit dependency sets.** `DEPENDENCIES` lists the inputs of every item
  (`line_identity`, `row_set`, column names, `summary_sheet`, `docx`); `blocker()` returns
  the first unmet dependency and `blocked()` writes a `cannot_assess` with the root field,
  its status (ambiguous / unmapped / unrecalculated / unverifiable) and the candidates as
  evidence, attribution `grader_extraction` or `grader_caused_recalculation`. Items 8 and 9
  depend on both flag columns and the total: a formula failure in either column makes them
  `cannot_assess` (the review had them FAIL on `None`), and C1 is `not_confirmed`, never FAIL,
  for a grader-side cause. Items 8, 9, 10 and 15–17 are per-row / column-sum checks and no
  longer depend on the row set.
- **B3 — working-copy lifecycle.** `grading/extract.py`: `copy_originals` hashes every copy
  against the original right after copying (`copy_verified`); `extract_all` runs the
  structural `format_check` on the **original** (read-only), re-hashes the copy immediately
  before parsing (`copy_verified_before_parse`), and classifies failures as
  `original_corrupt`, `copy_fault` or `parser_fault` (exception type recorded); it records
  `originals_unchanged` after all work. `recalculate_xlsx` records input path, output path,
  input and output SHA-256, `converter_version` (LibreOffice 7.4.7.2 in the pinned image) and
  the image ID. In the checks, only `original_corrupt` with verified transfer is
  `model_caused_corrupt`; `copy_fault` / `parser_fault` give `cannot_assess` with attribution
  `grader_caused_extraction` and item 1 passes (the original is a valid workbook);
  `original_corrupt` with unverified transfer stays `unknown`.
- **B4 — exact quantities.** `qty()` normalises quantities as decimals (`Decimal(str(x))`,
  no truncation: 60 → "60", 60.5 → "60.5"); the business key uses it for quantity and case
  pack; `row_completeness` keeps multiset counts and additionally pairs missing/extra rows
  of the same PO and SKU as `changed` rows with the differing fields and the Excel rows.
- **B6 — two usage sources.** `harness/budget.py` `reconcile_usage` compares the sample's
  aggregated usage with the sum of its per-call usages per category (input excludes cached
  tokens; output already includes reasoning tokens, which are never added again). The
  launcher passes a `scope` (same sample, sample uuid, sources); without a confirmed scope the
  per-call figures are not used for pricing. Equal sources → exact per-call tier pricing.
  Conflicting sources → both raw views and the differences are stored
  (`usage_reconciliation`, `raw_usage`, `raw_calls`), the unit is settled at the larger of the
  per-call price and the conservative aggregated price, flagged `usage_sources_conflict`,
  `estimated` and `manual_review_required`, which holds every further paid start until a
  `review_cleared` event and survives restarts. Inspect's own per-call `total_cost` is taken
  as a floor. The review's case (aggregated 1,000,000 input tokens vs one 1,000-token call,
  Opus prices) settles at 4.000000 USD instead of 0.004000.
- **I6 — redaction in grading records.** `harness/redact.py` now holds the one redaction
  rule (launcher, ledger, grading, model-list script import it). `grade.py` redacts the
  eval error message, the gate reasons and the mismatch texts, and strips the user name from
  the log path (`/Users/<user>/…`) before writing `results.jsonl`.
- **I7 — Inspect `ModelCost` checked against the source.** `compute_model_cost` (Inspect
  0.3.286) = input × input + output × output + cache-write × `input_cache_write` (× 2.0/1.25
  only when the Anthropic provider reports a 1h TTL) + cache-read × `input_cache_read`; no
  long-context tier; no multiplier for OpenAI or Google. The Anthropic provider's default
  `auto` mode starts at 5m and may escalate a sample to 1h writes after a cached-request gap
  above the 5m TTL; `ModelUsage` does not show the TTL. Consequences, now implemented and
  recorded in `config.json` (`pilot.budget_protection.inspect_cost_model_checked_2026_10_31`,
  per-model `cache_write_basis`): the ModelCost passed to Inspect carries the default-TTL
  rate (A 5, B 2.50, judge 2) — the previous 8 for A would have been multiplied again to
  12.8 on a 1h sample; the ledger prices A's cache writes at 8 (conservative, flagged, with
  Inspect's per-call `total_cost` as a floor), B's at 2.50 (the harness sets no
  `prompt_cache_retention`, so the 30m rate matches the request; the 12h rate is recorded,
  not charged), the judge's at the input-price stand-in. Long-context tiers remain
  ledger-only: the 10 USD safety net under-prices such calls and never fires early; the
  remaining ledger/Inspect difference (A's cache writes) affects reservations and stops only
  and is never read as a capability difference. The earlier status wording "the Inspect
  cost_limit safety net uses the same conservative rates" is corrected in place.
- **I8 — attribution policy wording.** `PLAN.md` section 4 now states the three-class rule
  (model-caused → not delivered and graded; harness-caused → run error; unknown → recorded
  adjudication) in place of "unrecovered partial outcomes are harness collection errors";
  the two Stage 2 sentences in this file that carried the old wording are marked superseded.
  `preregistration.md` has no occurrence.
- **Docker — image pinned by full local ID.** `harness/compose.yaml` `image:` is the full
  ID `sha256:18cde712…ea9ee` (tag informational, `x-local: true` and `pull_policy: never`
  kept); `config.json` `sandbox.image`/`image_id` carry the same ID, `sandbox.platform`
  (linux/arm64), `compose_sha256`, scope notes and the rebuild procedure; `harness/image.py`
  reads the ID for `grading/extract.py` (the LibreOffice conversion runs `docker run --rm
  --pull=never <id>`) and the launcher; `launcher.preflight_sandbox` requires compose ==
  config, queries the daemon by ID only (bounded retry), checks the platform and records the
  tags; `main()` uses it. README section "Sandbox image" documents rebuild, ID lookup, the
  files to update, and that a local ID is not a cross-machine reference (registry digest at
  freeze). No warm-up is implemented; the tag was not modified.

### Six review counter-examples, before → after

| Review probe | Before (review evidence) | After (this round) |
|---|---|---|
| `three_strings_override` | graded, gate passed with `{"basis":"anything","by":"anyone","at":"not-a-date"}` | `TypeError` (no parameter); error log → `log_join_mismatch`, not graded |
| `ambiguous_generic_first` / `ambiguous_alias_first` | generic-first: all pass; alias-first: 36 FAIL (`model_caused`), C1/C2 fail | both orders identical: 0 FAIL, 32 `cannot_assess` (3, 5–7, 18–20, 31–55) with `ordered_units` candidates `ordered units / units / units ordered`; 27 unrelated items graded (C2 pass) |
| `parser_fault` / `copy_fault` | 52 FAIL, `model_caused_corrupt` | 0 FAIL; item 1 pass; 51 `cannot_assess`, `grader_caused_extraction`; error class `parser_fault` (RuntimeError) / `copy_fault`; original hash unchanged |
| `price_formula_only_failed` / `case_formula_only_failed` | item 8 FAIL (and 9 in the case variant), C1 fail | 0 FAIL; price: `cannot_assess` 5, 8, 9, 10, 15, 18, 31–45; case: 6, 7, 8, 9, 10, 16, 19, 46–55; C1 not_confirmed |
| `fractional_units` (60 → 60.5) | all pass (int truncation) | FAIL 5, 6, 7, 18, 19, 20; `changed` = PO1005 / SKU-0101, field `units`, "60" → "60.5", Excel row 2 |
| `incomplete_call_usage` | 0.004000 USD, not estimated, no review, no stop | 4.000000 USD, `estimated`, `manual_review_required`, raw views and difference (999,000 input tokens) stored, next start refused, hold persists after restart |

### Regressions (2026-10-31; `run_isolated.sh`, `INSPECT_DISABLE_MODEL_API=1`, mockllm, pinned image; logs under `logs/pilot-final-remediation-20261031T032654Z/`)

| Suite | Module | Exit | Result |
|---|---|---|---|
| grading chain (B2 gate, no override, adjudication cannot release errors, I6 redaction, provenance in results) | `grading.tests.test_grading_chain` | 0 | 21/21 OK |
| layout / provenance / row set / formulas (B3, B4, B5) | `grading.tests.test_layout_regressions` | 0 | 29/29 OK |
| launcher and ledger (B1, B6 incl. usage conflict, I4 incl. delayed-create race, I6, I7 incl. Inspect cost model, Docker pre-flight) | `harness.tests.test_launcher_regressions` | 0 | 23/23 OK |
| existing harness unit suites | eight `harness.tests.test_*_unit` modules | 0 | 101/101 OK |
| compose pinned by ID (Inspect + Docker; tag lookup was failing during the run: `rc=1 No such image`, ID pre-flight succeeded) | `harness.tests.regress_compose_local` | 0 | 15/15 PASS |
| LibreOffice conversion by image ID (valid formula workbook → graded; damaged → `soffice_rc` 134, no values; valid again → ok; hashes unchanged) | `grading.tests.regress_recalc_docker` | 0 | 14/14 PASS |
| Stage 2 Inspect scenarios | `harness.tests.regress_inspect` | 0 | 62/62 |
| close-out gate | `harness.tests.regress_closeout` | 0 | 92/92 |
| execution limits | `harness.tests.regress_limits` | 0 | 74/74, 0 unverified |
| Inspect cost limit | `harness.tests.regress_cost_limit` | 0 | 14/14 |
| image tools | `harness.tests.regress_tools` | 0 | 8/8 |

First-attempt failures during the round (fixed, logs overwritten within this round's own
directory only): a `UnboundLocalError` in the new recalculation record; the ambiguity
evidence was nested under `blocked_by` (the root field is now surfaced); the damaged-copy
probe was classified as a parser fault because the copier verified before damaging (the
copy is now re-hashed immediately before parsing); the delayed-create test asserted an
unordered snapshot (relaxed to the final ledger state); a tier test called `settle`
without a scope; the PO/SKU-unrecognised variant let the summary drill-down block pass as
the detail sheet (the half-of-pairs acceptance threshold was added).

### Long-term regression inventory (Codex findings → in-repository tests)

| Finding | Test |
|---|---|
| B2 override / terminal error (rounds 2 and 3) | `test_grading_chain.test_eval_level_error_blocks_grading_and_no_override_parameter_exists`, `…cannot_release_an_eval_or_runtime_error` |
| B3 synonym conflict, column order (round 3) | `test_layout_regressions.test_synonym_conflict_is_ambiguous_in_either_column_order`, `test_map_columns_requires_a_unique_mapping` |
| B3 parser fault, working-copy damage (round 3) | `test_parser_exception_on_a_valid_original_is_grader_side`, `test_damaged_working_copy_is_grader_side_and_the_original_is_untouched` |
| B3 mixed formula dependencies (round 3), all-formula failure (round 2) | `test_single_formula_column_failure_propagates_to_items_8_and_9_without_fail`, `test_formula_workbook_with_failed_recalculation_is_cannot_assess_not_fail` |
| B4 60 → 60.5, multiset duplicates/missing (rounds 2 and 3) | `test_fractional_quantity_is_a_changed_row`, `test_quantity_normalisation_is_lossless`, `test_duplicate_plus_missing_row_fails_with_both_named`, `test_duplicated_zero_error_row_is_an_extra_row_failure`, `test_reordered_rows_are_not_a_failure` |
| B5 stale conversion result (round 2) | `RecalculationPathTests` (3 tests) and `regress_recalc_docker` |
| B6 usage conflict, hold, restart (round 3); returned errors, 2× stop, unknown price (round 2) | `test_launcher_regressions.test_aggregated_and_per_call_usage_conflict_settles_conservatively_and_holds`, `…outside_the_sample_scope…`, `…total_cost_is_a_floor`, `EngineeringFailureStopTests` |
| I4 two-process first initialisation (rounds 2 and 3) | `test_delayed_first_creation_is_not_overwritten_by_a_second_process`, `test_concurrent_initialisation_and_reservation_across_processes` |
| Docker: ID when the tag fails, missing image → no pull (round 3) | `regress_compose_local` (tag state recorded), `SandboxPreflightTests` (fake daemon), `test_repository_compose_config_and_converter_agree_on_the_image_id` |

### Still unverified before Pilot A

The real providers' usage fields as Inspect populates them (cache-write totals, TTL
escalation events, reasoning tokens); whether Opus 5.5 has a long-context price tier;
the real judge's compliance with the batch protocol; the real per-task cost; output-capped
detection (pre-freeze TODO); `--model` form validation; Inspect's float `timeout`
acceptance versus the launcher's integer-only validation (noted by the review, not in this
round's scope). Gates unchanged otherwise: human approval of ids/effort/judge, separate
paid authorization, concurrency 1, no warm-up for the tag misfire (the pin by ID removes
the dependency on the tag).

## Close-out review remediation (2026-10-31; extraction pipeline, launcher single-sample contract, status enum, YAML pre-flight; no model, judge or paid call)

Scope and boundary as before: every finding was reproduced from the probes in
`logs/pilot-closeout-review-wzwtf89y/` (22 files, unchanged) and their scripts, then fixed with
regressions that assert specific criteria, attribution and evidence fields. No rubric or policy
change, no other task, no real provider or judge, the project `.env` was not read, every Inspect
regression ran through `run_isolated.sh`, new logs are under
`logs/pilot-closeout-remediation-20261031T065912Z/`, the 257 pre-existing `logs/stage2_fix` files
are unchanged (44 added), no container left, image and tag untouched. Nothing is committed.

### Extraction layer rebuilt as a pipeline (`grading/checks_1137e2bb.py`)

Stages and the intermediate result each returns (all cell reads go through `read_value`,
statuses `ok` / `empty` / `formula_unrecalculated` / `error_value`):

| Stage | Output and statuses |
|---|---|
| `identify_tables` | `{status: ok / not_found / ambiguous, detail: {sheet, header_row, mapping, structural_score, source_fields_present, added_fields_present, match_fraction}, candidates}`. Identity comes from the header structure (PO, SKU and at least two further source fields); `MIN_MATCH_FRACTION` only disambiguates several candidates with equal structural score; a unique candidate is accepted at any coverage. |
| `map_columns` | `{cols, method, ambiguous: {field: [candidates]}, field_status: {field: ok / ambiguous / unmapped / confirmed_missing}, unmapped_headers}`. `confirmed_missing` only when no unrecognised header remains in the row; otherwise `unmapped`. |
| `parse_rows` | per row `{excel_row, class: identified / unidentified / no_id, reason, ids: {po, sku: {raw, norm, status: ok / unparseable / empty, rules}}, units: {status, value (exact decimal)}, cells, identity}`, plus `collisions` (two rows whose original (PO, SKU) strings differ but whose normalised row identity coincides: originals, normalised value, rows), `id_variants` (the same id written in several forms across lines), `id_normalisation` (original → normalised, rules: strip_outer_spaces / remove_inner_spaces / uppercase / number_leading_zeros / separator). |
| `evaluate_dependencies` | per field `{status: ok / ambiguous / unmapped / confirmed_missing / grader_error (kind unrecalculated, cells, recalc) / confirmed_invalid (error_cells) / unknown (uninterpretable values)}`; `line_identity` (ok / ambiguous / unmapped / confirmed_missing / collision); `row_set` (`status` ok / partial / collision / blocked, identified U-free multiset vs input: `missing_count` M, `unidentified_rows` U with reasons, `confirmed_missing_lower_bound` = max(0, M − U), `missing_identity_certain`, `extra`, `duplicates`, `changed`, `unidentified_grader_side`). |
| checks | per item a `_Decision` collects every violation and every unreliable input (no first-blocker short circuit): any confirmed violation → FAIL (even with other inputs unassessable); otherwise any unreliable required input → cannot_assess with attribution from the blocking kind (`grader_extraction` for ambiguous/unmapped, `grader_caused_recalculation` for unrecalculated formulas, `unknown` for uninterpretable values, collisions and unidentified rows); otherwise PASS. Each grade line carries `dependencies`, `fail_on_own` and the evidence lists `violations` / `unassessable`. |

`DEPENDENCIES` (inputs; which confirmed states fail the item on their own):

| Items | Inputs | Fails on its own |
|---|---|---|
| 3 | the seven source columns incl. Ship-to (presence) | any confirmed_missing |
| 4 | price_flag, case_flag, total, summary_text (presence) | any confirmed_missing |
| 5 / 6 / 7 | line_identity, row_set, price_flag (5) or case_flag (6, 7) | flag column confirmed_missing or confirmed_invalid; a confirmed row-set defect (missing lower bound > 0, extra or changed rows); a reliable wrong flag on an identified row |
| 8 | price_flag, case_flag, total (every row) | any of the three confirmed_missing or confirmed_invalid; a row with reliable values where total ≠ price + case |
| 9 | price_flag, case_flag | confirmed_missing or confirmed_invalid; a reliable non-binary or blank flag |
| 10 | the four added columns (values) | confirmed_invalid (error values); confirmed_missing is not blocking |
| 12 / 14 / 22 / 56–62 | summary sheet | no other sheet (confirmed absent) |
| 13 | summary sheet, its three measures | a measure confirmed missing (no unrecognised header on the summary row) |
| 15 / 16 / 17 | summary sheet, measure, detail column sum over every row | detail column confirmed_missing / confirmed_invalid, measure confirmed missing; reliable sums that differ |
| 18 / 19 / 20 | line_identity, row_set, column | column confirmed_missing / confirmed_invalid; confirmed row-set defect; complete reliable sum ≠ reference |
| 21 | case_missing (presence) | confirmed_missing (A-21) |
| 31–45 / 46–55 | line_identity, price_flag / case_flag | flag column confirmed_missing / confirmed_invalid; the line absent while no unidentified row remains; a reliable flag ≠ 1 |
| 2, 25, 26 | docx | absent |

Error attribution follows the evidence (`grading/extract.py`): `format_check` validates the
original independently of the parser (zip integrity, `[Content_Types].xml`, `xl/workbook.xml`,
every XML part parsed with the standard library) and classifies `error_kind` as `zip_error` /
`missing_part` / `xml_error` (structural → `original_corrupt`: model-caused when the transfer is
verified, unknown otherwise), `resource_error` (MemoryError, I/O → `grader_error`), `parser_error`
(a parser failed on a structurally valid file → `parser_undetermined`, cannot_assess with the
reason kept, attribution unknown); a structural exception raised later in `extract_xlsx` is
still `original_corrupt`; a damaged working copy is `copy_fault` (grader).

### Other fixes

- `harness/launcher.py` `run_sample`: single-sample contract — a returned log with ≠ 1 samples is
  never settled from `samples[0]`; the reservation stays open, every sample's usage is recorded
  (`all_sample_usage`), the unit is `manual_review_required`, a stop event blocks further paid
  starts and survives restarts (`sample_cardinality` record).
- `grading/grade.py` `join_log`: `log.status` is validated against Inspect's `EvalStatus`
  literal; a value outside it is recorded as `invalid_status` with a redacted repr in the
  mismatch text and never echoed (the review's marker reached `results.jsonl` through
  `log_status`).
- `harness/image.py` `compose_image` parses the compose YAML (`yaml.safe_load`) instead of a
  regular expression, so a quoted image id is accepted; `launcher.preflight_sandbox` requires
  `sandbox.image == sandbox.image_id`, a `sandbox.platform` with non-empty `os` and
  `architecture` strings, and the daemon's platform to match.
- Long-term regressions corrected: `regress_recalc_docker` now overwrites the same input path
  (same parent work directory) with damaged bytes after a valid conversion; the launcher suite
  checks `run_outcome.json` and the collected deliverable hashes across the error, 2×-cost and
  two-sample stop paths; the usage-conflict test uses the review's 1 USD estimate and asserts
  that `clear_review` lifts the review hold while the 2× rule still stops; the duplicate/missing
  tests document that items 8 and 9 are per-row checks since round 2.

### Review counter-examples, before → after

| Probe | Before (review evidence) | After |
|---|---|---|
| `missing_rows_keep_5/18/19/20` | 51 cannot_assess (coverage threshold rejected the only table) | identity ok; 36 / 23 / 22 / 21 confirmed missing; row-set items, absent named lines and (no other sheet) the summary items FAIL, missing rows listed |
| `threshold_49/50/51` (100-line synthetic source) | 49 % → extraction_failed | identity ok at every coverage; item 5 FAIL with lower bound 51 / 50 / 49 |
| `format_all_*` (lower, zero padding, inner spaces) / `format_one_*` | 51 cannot_assess / FAIL 5, 6, 7, 18–20 (one row lost) | all PASS; normalisation recorded per row; no collision |
| `new_price_flag_ambiguity` (second price-flag candidate with `#VALUE!`) | item 10 pass | item 10 cannot_assess (`grader_extraction`), the candidate column is never read; 4, 5, 8, 9, 15, 18, 31–45 cannot_assess |
| `new_formula_and_missing_column` (price formulas unrecalculated + case column deleted) | 35 cannot_assess incl. item 4 | item 4 FAIL (confirmed missing column; the price input is presence-only); 6, 7, 8, 9, 16, 19, 46–55 FAIL (confirmed_missing on its own); 5, 10, 15, 18, 31–45 cannot_assess (grader) |
| `source_quantity_formula_failed` | FAIL 5, 6, 7, 18–20 as a changed row (model) | row unidentified for a grader-side reason: 5, 6, 7, 18, 19, 20 cannot_assess (`grader_caused_recalculation`); named lines in other rows pass |
| `new_format_fault` (MemoryError in the structural check) | 52 FAIL `model_caused_corrupt` | 0 FAIL; item 1 pass (zip and XML parts valid); 51 cannot_assess `grader_caused_extraction` |
| valid zip, malformed `sheet1.xml` | — (new) | `xml_error` → `original_corrupt` → 52 FAIL `model_caused_corrupt` with verified transfer; unknown without |
| wrong but parseable PO / SKU | — (new) | extra + missing rows (bound 2): FAIL 5, 6, 7, 18–20 and the absent lines 32, 35, 48 |
| unidentified rows U = 2, missing M = 3 / U = 1, M = 1 | — (new) | bound 1 → FAIL (model) / bound 0 → cannot_assess (unknown), unidentified rows listed with reasons |
| identity collision (`PO1005/SKU-0101/60` also written `po1005/sku-0101`) | — (new) | collision recorded (originals, identity, rows 2 and 43); identity items cannot_assess (unknown); per-row items 8, 9 still graded |
| `Case Packaging Validation` | — (new) | `unmapped` → cannot_assess 4, 6–10, 16, 19, 46–55 (`grader_extraction`); deleted column → `confirmed_missing` → FAIL |
| recalculated `#VALUE!` in a flag cell | — (new) | `confirmed_invalid` → FAIL 5, 8, 9, 10, 15, 18, 31–45 (`model_caused`) |
| `new_two_samples` | settled 0.004 USD from `samples[0]` | no settlement, reservation 3 USD kept open, both samples' usage recorded, stop + manual review, next start refused, state kept after restart |
| `redaction_mismatch` (marker as `log.status`) | marker in `log_status` | `invalid_status`, marker count 0 |
| `preflight_quoted_image` / `missing_platform` / `image_alias_mismatch` | LauncherError / accepted / accepted | accepted / LauncherError / LauncherError |
| `original_conflict` 1 USD estimate (exact-old-stop) | — | after `clear_review` the 2× stop still applies (asserted) |

The 29 earlier layout cases are unchanged except `parser_fault`: a parser exception on a
structurally valid file is now `parser_undetermined` with attribution `unknown` (reason kept)
instead of `grader_caused_extraction`, per the review's attribution semantics (a resource
exception stays grader-caused: `format_memory_error`). Twenty-two cases were added
(`layout_table.json`: 49 variants).

### Regressions (2026-10-31; `run_isolated.sh`, `INSPECT_DISABLE_MODEL_API=1`, mockllm, pinned image; logs under `logs/pilot-closeout-remediation-20261031T065912Z/`)

| Suite | Module | Exit | Result |
|---|---|---|---|
| layout / pipeline semantics | `grading.tests.test_layout_regressions` | 0 | 41/41 OK |
| grading chain (gate, no override, adjudication, redaction incl. invalid status) | `grading.tests.test_grading_chain` | 0 | 21/21 OK |
| launcher and ledger (dispatch, stops, usage conflict 1 USD, two samples, outcome hashes, concurrency, redaction, tiers, YAML pre-flight) | `harness.tests.test_launcher_regressions` | 0 | 27/27 OK |
| existing harness unit suites | eight `harness.tests.test_*_unit` modules | 0 | 101/101 OK |
| compose pinned by ID (tag lookup failing during the run, ID pre-flight ok) | `harness.tests.regress_compose_local` | 0 | 15/15 PASS |
| LibreOffice conversion incl. same-path valid → damaged | `grading.tests.regress_recalc_docker` | 0 | 16/16 PASS |
| Stage 2 Inspect scenarios / close-out / limits / cost limit / tools | `regress_inspect`, `regress_closeout`, `regress_limits`, `regress_cost_limit`, `regress_tools` | 0 | 62/62, 92/92, 74/74, 14/14, 8/8 |

First-attempt failures in this round (all test-expectation updates to the new evidence shapes,
plus one code fix: normalisation rules were recorded for ids whose value did not change) are in
the round's `layout_regressions.log` history; no behaviour was weakened to pass a test.

### Still unverified before Pilot A

Unchanged from the previous section (real provider usage fields, judge protocol compliance,
Opus 5.5 long-context tier, real cost, output-capped detection, `--model` form validation,
Inspect float timeouts). The pipeline semantics are exercised on synthetic fixtures only; the
first real deliverable will be graded with the human review reading every `cannot_assess`
reason.

## Extraction-review remediation (2026-10-31; R1–R6, XML validation cap, R4 safe exit, PENDING scope question; no model, judge or paid call)

Evidence reviewed first: `logs/extraction-review-0r3d__40/` (70 files, hashes unchanged against
its `final-audit.json` after this round) and the probe code outside the repository
(`/private/tmp/extraction-review-0r3d__40/work/`). Every counter-example was reproduced on the
unchanged code before any fix (`logs/extraction-remediation-20261031T193444Z/probe-summary.json`
holds the after-state of 34 probes; the before-state is Codex's `independent-summary.json`,
`additional-summary.json` and `followup-summary.json`). Boundary kept: every active test through
`harness/tests/run_isolated.sh` (`env -i`, external cwd without an ancestor `.env`,
`INSPECT_DISABLE_MODEL_API=1`, mockllm); the project `.env` was never read; no provider or
judge call; probe code in the session scratch directory; the review directory untouched; own
containers cleaned (0 running before and after); image, tags and existing containers untouched.

### Fixes (file references are to the working tree of 2026-10-31)

| Item | Change | Where |
|---|---|---|
| R1 required numeric cells | `numeric_cell` / `flag_cell` classify every read cell: ok, empty, formula_unrecalculated, error_value, non_numeric, non_finite (NaN, Infinity), non_binary. `_num` returns only finite numbers. A reliably read cell that is not what the rubric requires is a confirmed invalid value → violation of every item that needs it (cell, row, original value recorded); only unreadable cells (unrecalculated formulas) are unreliable → cannot_assess. No comparison is skipped into a PASS: every row loop registers each cell it needs. Rule recorded in `preregistration.md` 2.4 ("Cell-value rule"); it replaces the earlier unwritten "blank flag reads as 0" for items 5/6/7/18/19 | `grading/checks_1137e2bb.py` `numeric_cell` l.236, `flag_cell` l.253, `_num` l.172, `_Decision.cell` l.793, row loops in `run_checks` l.855–1220 |
| R2 formula state of source fields and summary cells | `row_set_status` holds identified rows whose business cells (entered, expected, uom, case pack) are unrecalculated by identity against an input line: not missing, not changed, not zero; `verified_rows` / `held_rows` / `held_by_identity` reported; the row set is `partial` for a grader-side reason. `locate_summary_sheet` reads every label and measure cell through `read_value`; items 15–17 and 56–62 register the summary cell with its status (unrecalculated → grader_error unassessable; blank / NaN / error → confirmed invalid; absent SKU row → violation unless labels are unresolved formulas). Item 22 is cannot_assess when the totals are unreadable and the sheet is not sortable | `row_set_status` l.553, `locate_summary_sheet` l.698, `run_checks` items 15–17 and 56–62 |
| R3 row-precise dependencies | `column_record` keeps BOTH lists for every mapped column: `invalid_cells` (kind, value) and `unreliable_cells`; `status` summarises but never replaces them. `_apply_column_dependencies` applies mapping-level statuses to every item and column-wide value lists only to items without a row loop (item 10, `column_values`, `invalid_kinds=("error_value",)`); items 5–9, 15–20 register every row's cell themselves; items 31–55 (`row_scoped`) read only their own row and never a column status. `_Decision` keeps `violations` and `unassessable` side by side; a confirmed violation decides FAIL and the unassessable inputs stay in the evidence | `column_record` l.625, `evaluate_dependencies` l.671, `_apply_column_dependencies` l.814, `DEPENDENCIES` l.105 (`row_scoped`, `column_values`, `invalid_kinds`) |
| R5 id normalisation and reference entities | `reference_ids` normalises the reference ids; two distinct reference originals with one normalised id are a reference collision (originals, normalised id, entities with their lines, reference rows, reason). `parse_rows` resolves every deliverable id to its reference entity: a legal variant is that entity (never a collision, recorded under `id_variants` / `id_normalisation`); an id matching two entities is `ambiguous_entity` (row unidentified, listed under `collision_affected_rows`); an id matching none keeps its normalised form (a parsed-but-wrong id → extra row). `line_identity` = collision blocks the row set; named lines are cannot_assess only when their own PO or SKU collides. Attribution of a reference collision: grader_extraction. The real reference has no collision (Codex audit: 10 PO, 16 SKU originals) | `reference_ids` l.445, `parse_rows` l.465, `evaluate_dependencies` l.671, `_apply_column_dependencies` l.814, named lines in `run_checks` |
| R6 single Task / EvalLog / sample | Before any call: `run_sample` refuses anything but one Task object (list, tuple, set, None, str), with a `refused` record and no stop check, reservation or eval. After the call: the returned list must be exactly one EvalLog holding exactly one sample; otherwise no settlement, every log (status, location, task, sample uuids) and every sample's usage recorded, reservation kept open, `manual_review_required`, engineering stop recorded (persists across restarts), `sample_cardinality` record | `harness/launcher.py` l.372–377 (pre-call), l.393–412 (post-call) |
| XML validation cap | An XML part above `XML_PART_LIMIT` is `error_kind: resource_limit` (part name, bytes, limit, file bytes recorded), never `xml_error`; a genuinely malformed part still wins with the over-limit parts recorded next to it. `extract_all` maps `resource_limit` to `error_class: grader_error` (`exception_type: XmlPartLimit`); the checks give item 1 and the workbook items cannot_assess with `grader_caused_extraction` and carry `resource_limit` in the evidence | `grading/extract.py` `format_check` l.128–180, `extract_all` l.348–353; `run_checks` unreadable branch |
| R4 complementary detail sheets (safe exit, no merge) | `identify_tables`: among equal structures a candidate covering every input pair the candidates jointly cover is preferred (a flagged-lines subset or a drill-down copy never displaces the full table); complementary candidates are a `split`: primary = largest coverage, every candidate with `coverage` (`covered_input_pairs`, `only_in_this_sheet`) and the reason recorded. `run_checks` on a split: row_set = `split_tables` → 5–7, 18–20 cannot_assess (grader_extraction); 15–17 cannot_assess (no column sum across sheets); items 8, 9, 10 run over every candidate's rows (cells prefixed `sheet!cell`); named lines are looked up in every candidate (absent everywhere with no unidentified row → confirmed absent); a confirmed error or wrong flag in any sheet still FAILs its item; the summary search excludes every detail candidate | `identify_tables` l.386, `merge_column_records` l.655, `run_checks` split branch |
| rows without source data | A row with no source-field cell at all (notes, footers) is class `no_id` and is not read by the per-row items; a row with any source data but no resolvable identity stays `unidentified` and counts in U | `parse_rows` l.465 |

### Counter-examples, before → after (Codex probe name; `logs/extraction-remediation-20261031T193444Z/<name>.json`)

| Probe | Before (Codex evidence) | After | Attribution |
|---|---|---|---|
| new_blank_total / blank_nonzero (Total Errors blank on PO1002/SKU-0103/120) | 0 FAIL, 8/17/20 PASS, C1 and C2 pass | 8, 17, 20 FAIL (`empty` at L5, value None); C1, C2 fail | model_caused |
| new_nonfinite_total / nan_nonzero ("NaN"), plus "Infinity" and "n/a" | 0 FAIL | 8, 17, 20 FAIL (`non_finite` / `non_numeric` at L5) | model_caused |
| blank total on a zero-error row (L2) | — | 8, 17, 20 FAIL (`empty` at L2) | model_caused |
| blank or text price flag on a zero-error row (I2) | 5/6/7/18/19 read blank as 0 (9 FAIL only) | 5, 8, 9, 15, 18 FAIL; 10 pass (not an error value); 31–55 pass | model_caused |
| new_source_price_formula / new_source_case_formula (D2 or G2 `=value`, conversion failed) | 5, 6, 7, 18, 19, 20 FAIL as "changed row" | 5, 6, 7, 18, 19, 20 cannot_assess; row 2 held by identity (`held_by_identity` D2 / G2); 8, 9, 10, 15–17, 31–55 pass | grader_caused_recalculation |
| new_summary_formulas_failed (every summary measure `=value`, conversion failed) | 56–62 FAIL "total unreadable"; 15–17 PASS with zero comparisons | 15, 16, 17, 56–62 cannot_assess, cell named (`Summary!D3` …, grand total `Summary!B18`); nothing FAILs | grader_caused_recalculation |
| summary grand-total price cell unrecalculated + detail I5 `#VALUE!` (conjunction) | — | 15 FAIL on I5 with the summary cell kept as unassessable; 5, 8, 9, 10, 18 FAIL; 32 FAIL (its own cell I5); 31 pass | model_caused + grader side recorded |
| new_unrelated_price_error (I2 `#VALUE!`, no named line) | 31–45 FAIL from the column status | 5, 8, 9, 10, 15, 18 FAIL; 31–45 PASS from their own rows | model_caused |
| new_error_and_unrecalculated (I2 `#VALUE!`, I3 `=0` unrecalculated) | 10 cannot_assess (column status grader_error took precedence) | 10 FAIL (I2) with I3 recorded unassessable; column record `invalid_cells` [I2], `unreliable_cells` [I3]; 31–45 pass | model_caused + grader side recorded |
| same_entity_variant_duplicate (row 2 duplicated with lowercase PO/SKU) | collision → 5–7, 18–20, 31–55 cannot_assess | duplicate row: 5, 6, 7, 18, 19, 20 FAIL (extra 1, duplicated 1); no collision; variants recorded; 31–55 pass | model_caused |
| reference_collision_po (reference holds PO1005 and PO01005 as distinct entities) | 5–7, 18–20 FAIL (second entity's row treated as extra) | 5, 6, 7, 18, 19, 20 and 37, 38, 39, 50 cannot_assess; collision recorded with originals, normalised id, entities, rows; 8, 9, 10, 12–17 and the other named lines pass | grader_extraction |
| reference_collision_sku (SKU-0101 vs SKU-00101) | 5–7, 18–20 FAIL | 5, 6, 7, 18, 19, 20 cannot_assess; 31–55 pass | grader_extraction |
| every PO/SKU lowercase | all pass | all pass (legal variants of the same entities) | — |
| detail_two_sheets (21 + 20 rows over two sheets) | 5–7, 15–20 and 10 named lines FAIL as missing | identify `split` with both candidates and coverage; 0 FAIL; 5, 6, 7, 15, 16, 17, 18, 19, 20 cannot_assess; 31–55 found in either sheet and pass; 8, 9, 10 over both sheets | grader_extraction |
| split + `#VALUE!` in the second sheet | — | 5, 8, 9, 10, 15, 18 FAIL (`RawData continued!I3`) | model_caused |
| split + wrong named flag in the second sheet | — | 5, 8, 45 FAIL | model_caused |
| full table + flagged-lines subset sheet | — | status ok, full table chosen, all pass | — |
| new_xml_limit (`XML_PART_LIMIT` = 10) | 52 FAIL incl. item 1, `model_caused_corrupt` | 0 FAIL; item 1 and the workbook items cannot_assess; `error_kind resource_limit`, `error_class grader_error`, parts, sizes, limit and file size recorded | grader_caused_extraction |
| two_eval_logs (Codex `followup`, two EvalLogs with one executed sample each) | settled 0.004 USD from logs[0]; no stop; `all_sample_usage` None | no settlement; 2 logs / 2 samples recorded with 1,000 and 1,000,000 input tokens; reservation 3 USD open; stop recorded; next start refused; refusal kept after restart | — |
| real two-task Inspect + mockllm replay (`launcher-contract/`) | Codex `real-scope.json`: settled 0.004 USD, stops [] | 11/11 checks: both `.eval` logs detected and persisted, both usages recorded, no settlement, reservation open, stop, manual review, next and post-restart starts refused, a task list refused before any call | — |
| earlier-round probes (missing_rows_keep_5, threshold, M3_U*, format variants, price_ambiguity, formula_and_missing, quantity_formula, format_memory, case_column_missing, strange_plus_deleted, summary_drilldown, changed units, exact duplicate) | as in the close-out round | unchanged outcomes (`probe-summary.json`) | unchanged |

### Test expectations changed (old → new, basis, scoring effect)

| Test | Old expectation | New expectation | Basis | Scoring behaviour |
|---|---|---|---|---|
| `test_identity_collision_blocks_row_level_comparison` → `test_legal_id_variant_duplicate_is_a_duplicate_row_not_a_collision` | lowercase duplicate of row 2 is a collision; identity items cannot_assess | duplicate business row; 5, 6, 7, 18, 19, 20 FAIL; no collision; variants recorded; 31–55 pass | R5 (collision = two distinct reference entities); approved duplicate-row rule | cannot_assess → FAIL for this layout |
| `test_recalculated_error_values_are_confirmed_invalid` | fails = {5, 8, 9, 10, 15, 18} ∪ 31–45 | fails = {5, 8, 9, 10, 15, 18}; 31–45 pass from their own rows | rubric 31–45 are per-PO/SKU checks (R3) | FAIL → PASS for 31–45 when the error sits in another row |
| `test_single_formula_column_failure_propagates_to_items_8_and_9_without_fail` | `fail_on_own` = {missing, invalid, row_set} | plus `row_scoped`, `invalid_kinds` | contract fields added by R3 | none |
| `test_more_than_one_sample_is_never_settled_from_the_first` | stop text "2 sample(s), expected exactly 1" | "1 EvalLog(s) with 2 sample(s) in total, expected exactly 1 and 1" | R6 wording (log count added) | none |

New tests (expectations from the rubric text and the approved semantics, not from the output):
layout suite `test_blank_and_non_finite_totals_are_confirmed_invalid_not_skipped`,
`test_blank_or_text_flag_is_a_confirmed_invalid_value_for_every_item_that_reads_it`,
`test_unrecalculated_source_price_or_case_pack_holds_the_row_by_identity`,
`test_unrecalculated_summary_cells_are_grader_side_not_fail_and_not_pass`,
`test_summary_cell_unassessable_plus_confirmed_detail_error_fails_with_both_recorded`,
`test_error_value_in_an_unrelated_row_does_not_fail_the_named_lines`,
`test_error_value_and_unrecalculated_formula_in_one_column_keep_both_records`,
`test_reference_collision_makes_the_affected_identity_items_cannot_assess`,
`test_whole_sheet_id_variants_resolve_to_the_reference_entities`,
`test_detail_rows_split_over_two_sheets_are_not_reported_missing`,
`test_full_table_plus_flagged_subset_sheet_selects_the_full_table`,
`test_xml_part_above_the_validation_cap_is_a_grader_resource_limit`; launcher suite
`test_two_eval_logs_are_never_settled_from_the_first`,
`test_a_list_of_tasks_is_refused_before_any_call_or_reservation`; new module
`harness/tests/regress_launcher_contract.py` (real Inspect eval, mockllm, two tasks).

### PENDING adjudication registered (not in force) — superseded: APPROVED and applied 2026-10-31, see section "Approved adjudication applied"

Question: which items carry the "all 41 lines" completeness of C1, and what exactly fails
rubric 7 and 18–20 (text, necessary conditions, current FAIL conditions, proposed FAIL
conditions, the duplicated-zero-error-row scenario, the C1 comparison and the false-PASS
analysis are written under "PENDING — proposed adjudication" in `preregistration.md` 2.4).
Items concerned: 7, 18, 19, 20 (and, as the proposed carriers of completeness, 5 and 6).
Possible conflict reported, not adjudicated: the current implementation FAILs 18–20 for a
duplicated zero-error row although the column sums equal 15 / 10 / 25 as the item text
requires. Nothing in `DEPENDENCIES` or the tests was changed for this; the grader keeps the
row-set rule on 5, 6, 7, 18, 19, 20 until the human decides. If approved, both models are
re-graded with a new grader version.

### Regressions (2026-10-31; `run_isolated.sh`, `INSPECT_DISABLE_MODEL_API=1`, mockllm, pinned image; logs under `logs/extraction-remediation-20261031T193444Z/`)

| Suite | Module | Exit | Result |
|---|---|---|---|
| layout / pipeline semantics incl. R1–R5, R4, XML cap | `grading.tests.test_layout_regressions` | 0 | 53/53 OK (first run after the rewrite: 37/41, the four failures being the two Codex-flagged expectations and the `fail_on_own` shape; two new tests first assumed the grand-total row at B10, the fixture has 16 SKU rows → B18, assertion now reads the row) |
| grading chain | `grading.tests.test_grading_chain` | 0 | 21/21 OK |
| launcher and ledger incl. R6 | `harness.tests.test_launcher_regressions` | 0 | 29/29 OK (first run: 28/29, the stop-text wording) |
| real Inspect + mockllm two-task replay | `harness.tests.regress_launcher_contract` | 0 | 11/11 PASS (`launcher-contract/results.json`, two `.eval` logs) |
| existing harness unit suites | eight `harness.tests.test_*_unit` modules | 0 | 101/101 OK |
| compose pinned by ID | `harness.tests.regress_compose_local` | 0 | 15/15 PASS (tag lookup resolved to the pinned ID during this run; evidence only) |
| LibreOffice conversion incl. same-path valid → damaged | `grading.tests.regress_recalc_docker` | 0 | 16/16 PASS |
| Stage 2 Inspect scenarios / close-out / limits / cost limit / tools | `regress_inspect`, `regress_closeout`, `regress_limits`, `regress_cost_limit`, `regress_tools` | 0 | 62/62, 92/92, 74/74, 14/14, 8/8 |

`logs/stage2_fix`: 301 files before, 345 after, 0 changed, 0 removed. Review directory
`logs/extraction-review-0r3d__40/`: 70 listed files, 0 changed. Credential-pattern scan of the
new log directory: 0 files. Containers: 0 before and after. No weakening of any check to
pass a test; the three code-level corrections during the round were test fixtures (openpyxl
`cell(r, c, None)` is a no-op, replaced by `.value = None`) and the grand-total row.

### Still unverified before Pilot A

Unchanged from the previous section (real provider usage fields, judge protocol compliance,
Opus 5.5 long-context tier, real cost, output-capped detection, `--model` form validation,
Inspect float timeouts). New: the cell-value rule (blank flag = confirmed invalid for 5/6/7/
18/19) and the PENDING scope question need the human's reading before the first real
deliverable is graded; the split-table exit and the reference-collision path are exercised on
synthetic fixtures only; the real-Inspect two-task replay prices mockllm with Opus data for
the cost-limit check only (the real launcher refuses unpriced models).

## Approved adjudication applied (2026-10-31; rubric 7, 18–20 scope; cell-value rule APPROVED; Pilot A request drafted; no model, judge or paid call)

Plan stated before the change: two targeted edits in `grading/checks_1137e2bb.py`, test
re-derivation, `preregistration.md`, this file, a new `docs/pilot_a_request.md`; direct consumers
(`grade.py`, `review.py`, `judge.py`) read only verdict / evidence keys that did not change
shape, confirmed through the grading-chain suite; no Docker, Inspect or LibreOffice operation.

### Changes

- `preregistration.md` 2.4: the cell-value rule (blank flag = confirmed invalid) marked
  APPROVED 2026-10-31; the item 7 / 18–20 proposal marked APPROVED with the approved rule and
  the amendment record (old rule, evidence, new rule, re-grading: no graded run exists).
- `grading/checks_1137e2bb.py`, `DEPENDENCIES`: items 7, 18, 19, 20 no longer require
  `row_set` and carry `row_set_violation: False` (7 keeps `line_identity` + `case_flag`;
  18–20 require only their column). Items 18–20 branch of `run_checks`: the sum runs over
  every readable cell of the column across all delivered business rows (identified and
  unidentified, every candidate sheet), `rows_summed` recorded, compared directly with
  15 / 10 / 25; an invalid cell is a violation, an unrecalculated cell is unassessable. The
  row-set violation acts through items 5 and 6 only. No other function touched.
- `grading/tests/test_layout_regressions.py`: `ROWSET_ITEMS` = {5, 6}; `IDENTITY_ITEMS` =
  {3, 5, 6, 7} ∪ 31–55; eight assertions re-derived (duplicate+missing, duplicated zero-error
  row, reference collision: 7 cannot_assess with the identity while 18–20 pass, held rows,
  split tables: 18 FAILs when the price column sums to 14 across both sheets); new
  `test_row_set_defects_act_through_items_5_and_6_only`.
- `docs/pilot_a_request.md` created (draft request; nothing executed).

### The four required regressions (`scope_*` variants; `logs/stage3b-closeout-20261031T202005Z/layout_table.json`)

| Scenario | FAIL | PASS (asserted) | C1 |
|---|---|---|---|
| duplicated zero-error row (PO1005/SKU-0101/60) | 5, 6 | 7, 18, 19, 20 (sums 15 / 10 / 25 over 42 rows) | fail |
| deleted price-only line (PO1001/SKU-0112/96) | 5, 6, 18, 20, plus 31 (its own named line) and 15, 17 (summary no longer reconciles with the detail column: 14 / 24) | 7, 19 | fail |
| deleted case-only line (PO1003/SKU-0111/52) | 5, 6, 19, 20, plus 47 and 16, 17 | 7, 18 | fail |
| deleted zero-error row (PO1005/SKU-0101/60) | 5, 6 | 7, 18, 19, 20 | fail |

### Tests run (first execution captured; nothing rerun)

| Command (through `harness/tests/run_isolated.sh`, `/usr/bin/time -p`) | Wall clock | Exit | Result |
|---|---|---|---|
| `unittest grading.tests.test_layout_regressions` | 3.76 s | 0 | 54/54 OK |
| `unittest grading.tests.test_grading_chain` | 2.67 s | 0 | 21/21 OK |

Not run, by the testing-tier rule: harness unit suites, launcher / budget suites, Inspect, Docker,
LibreOffice and compose regressions (no change to those modules, the config, dependencies or
the environment since their last green run in `logs/extraction-remediation-20261031T193444Z/`).

### Open before Pilot A

Pilot A request (`docs/pilot_a_request.md`) awaits approval: model A final approval, judge id,
reservation amounts, real-launcher enabling (code change in `main()`), the stale
`launcher_wiring` note in `config.json`, and `freeze-v1` before any formal run.

## Stage 3b review fixes (2026-10-31; `logs/stage3b-review-js7f8gca/`; item 7 applicability, split-table overlap, Pilot A request; no model, judge or paid call)

Plan stated first: two targeted edits in `grading/checks_1137e2bb.py` (the item 7 branch of the
items 5–7 loop and the `DEPENDENCIES[7]` inputs; a `cross_sheet_overlap` helper used only in the
split branch of items 18–20), two targeted tests, corrections to `docs/pilot_a_request.md`; no
change to `launcher.py`, `budget.py`, `judge.py` or `config.json`; no Docker, Inspect or
LibreOffice operation.

### A. Item 7 — applicability before the flag

Evidence: `review-results.json` `item7_case_blank`: J5 (case flag of the CASE line
PO1002/SKU-0103/120) blank → item 7 FAILed. Rubric 7 covers lines whose UOM is not CASE or
blank. Fix: in the items 5–7 loop, item 7 reads the row's own UOM cell first; a CASE line is
skipped (items 6, 8, 9, 16, 19 still judge the invalid cell); an unreadable UOM makes the row
unassessable; on a non-CASE line (including blank UOM) a blank, text or non-zero flag is a
confirmed violation. `DEPENDENCIES[7]` requires `line_identity`, `uom`, `case_flag`
(`fail_if_missing`: `case_flag` only; a missing UOM column is cannot_assess, item 3 carries it).
Items 5 and 6 unchanged. Before → after on the Codex fixture: FAIL {6, 7, 8, 9, 16, 19} →
FAIL {6, 8, 9, 16, 19}, item 7 PASS.

### B. Items 18–20 — a repeated identity across split sheets is uncertainty, not a count

Evidence: `review-results.json` `candidate_overlap`: 41 input rows over two sheets plus one
price-error line (flags 1 / 0 / total 1) shown again in the second sheet → summed as 42 rows
(16 / 10 / 26), items 18 and 20 FAILed as model-caused. Fix: `cross_sheet_overlap` records every
business identity present in more than one candidate sheet (sheet, row, flag and total values;
`extraction_status.dependencies.cross_sheet_overlap`, `detail_sheet.cross_sheet_overlap`). In the
18–20 branch, per column: copies whose value is 0 cannot move the sum (the item stays
reliable); otherwise both scopes are reported (all rows / one copy per repeated identity) and
the item is cannot_assess with `split_overlap` (grader_extraction) — unless both scopes give a
wrong total, which is a confirmed violation; a reliably invalid cell in the column is a
violation regardless. No deduplication is presented as truth; no general merger added. Before →
after on the Codex fixture: FAIL {18, 20} → cannot_assess {18, 20} (sums 16 / 15 recorded),
19 PASS (10), 5, 6, 15, 16, 17 cannot_assess as before, 0 FAIL.

### C. `docs/pilot_a_request.md` corrections

Cost range recomputed from the stated assumptions: ≈ 2.1–11.2 USD (arithmetic shown; earlier
≈ 1.5–11). Removed the claim that the 2× rule coincides with the 10 USD cost limit; stated that
the 5 USD reservation, the 10 USD per-sample `cost_limit` and the 30 USD ceiling are harness
accounting/stop controls that do not cap the provider's bill. Missing usage described as
implemented: settled at max(priced part, reservation), flagged `estimated`, no
`manual_review_required` and no hold (only unpriced or conflicting usage holds); a stricter
missing-usage stop listed as a pre-pilot decision. Judge described as implemented:
`grade_run` → `judge_units`, one call per unit (7 per run); batch helpers exist but are not
wired; cost basis restated per call (≈ 0.08–0.14 USD per run, FORECAST); real protocol
unverified; the 7 judge-only items are in the debug set and support no agreement claim.
Stated that a paid pilot cannot run with the current code (`main()` not wired, no real judge
callable). Document stays DRAFT with placeholders.

### Tests (first execution captured; nothing rerun; `logs/stage3b-closeout2-20261031T203847Z/`)

| Command (through `harness/tests/run_isolated.sh`, `/usr/bin/time -p`) | Wall clock | Exit | Result |
|---|---|---|---|
| `unittest grading.tests.test_layout_regressions` (+ `test_item_7_applies_only_to_non_case_lines_decided_from_the_row_uom`, `test_split_tables_with_a_repeated_identity_do_not_double_count_into_a_fail`) | 4.12 s | 0 | 56/56 OK |
| `unittest grading.tests.test_grading_chain` | 2.43 s | 0 | 21/21 OK |

Not run (unchanged modules, config and environment): harness unit, launcher/budget, Inspect,
Docker, LibreOffice, compose regressions.

### Open before Pilot A

Model A final approval; judge id, real judge callable and protocol check; `main()` real-mode
wiring; missing-usage stop decision; stale `launcher_wiring` note in `config.json`;
`freeze-v1`.

## Stage 3b close-out 2 fix (2026-10-31; `logs/stage3b-closeout2-review-07fvnged/`; overlap aggregation, Pilot A wording; no model, judge or paid call)

Item 7 is CLOSED and untouched. One targeted edit in `grading/checks_1137e2bb.py`, items 18–20
branch (around l.1100–1112): the inference "all-rows sum and one-copy-per-identity sum both differ
from the reference → FAIL" is removed. With several repeated identities the two extremes do not
bound the correct total (each repeat may need a different reading), so when a column's repeated
rows contribute non-zero values the item is cannot_assess (`split_overlap`, grader_extraction) with
the identities, their sheet/row occurrences, both candidate totals and the reference kept as
evidence; when the repeated rows contribute 0 the reliable total still decides PASS/FAIL; a
reliably invalid cell in the column still FAILs the item. `cross_sheet_overlap`, items 5, 6, 7 and
the approved 18–20 semantics are unchanged; no merger or combinatorial solver added.

New regression `test_multiple_overlaps_never_infer_a_fail_from_the_two_extreme_scopes`
(two price-only lines repeated across the split sheets, one other price-only line deleted):
price column 16 over all rows, 14 with one copy per identity, reference 15 → item 18 and item 20
cannot_assess with both extremes recorded; item 19 PASS on its reliable total (10); the deleted
line's own named item (44, PO1009/SKU-0103/120) FAILs as confirmed absent; 5, 6, 15–17
cannot_assess under the split rule. Earlier overlap regressions kept and passing: single
repeated price-error line → 18, 20 cannot_assess, 19 PASS; repeated zero-error line → 18–20
PASS; overlap plus `#VALUE!` → 18 FAIL (not masked).

`docs/pilot_a_request.md`: judge path stated as one call per judge-only criterion (7 per run),
no wired batch (lines 15 and 107); returned-eval-error settlement stated per the actual
`settle` branches (usage present → priced; no usage → max(priced, reservation) `estimated`,
no hold; unpriced or conflicting usage → `manual_review_required` hold; raised exception →
`estimated` at the reservation) with the paths that need human handling (line 62).

### Tests (first execution captured; `logs/stage3b-closeout3-20261031T205035Z/`)

| Command (through `harness/tests/run_isolated.sh`, `/usr/bin/time -p`) | Wall clock | Exit | Result |
|---|---|---|---|
| `unittest grading.tests.test_layout_regressions` | 4.37 s | 0 | 57/57 OK |
| `unittest grading.tests.test_grading_chain` | 2.58 s | 0 | 21/21 OK |

Not run (unchanged modules, config and environment): harness unit, launcher/budget, Inspect,
Docker, LibreOffice, compose regressions.

## Stage 3b grader close-out and checkpoint (2026-10-31)

- Independent final review of the 1137e2bb deterministic grader: CLOSED. The last blocking item
  (no FAIL inferred from the two extreme overlap scopes) was confirmed; `grading.tests.test_layout_regressions`
  57/57 and `grading.tests.test_grading_chain` 21/21 pass. No known Pilot-blocking scoring defect.
  Scoring-logic fixes and open-ended review of this grader stop here.
- Known maintenance issue (recorded, not scheduled): the `DEPENDENCIES` declarations and the
  rubric-specific scoring loops in `grading/checks_1137e2bb.py` are not fully unified; some
  declaration fields are unused (`line_absent_fails`, `fail_if_invalid` for items with their
  own row loop, `ATTRIBUTION["not_located"]`); the split-table handling of items 15–17
  (always cannot_assess) and 18–20 (overlap-aware) differs in a conservative direction.
- Decision: DEFER REFACTOR. No architecture cleanup is required before Pilot A/B.
- After Pilot A/B and before the remaining task-specific graders are implemented, evaluate
  briefly whether a shared scoring contract or declarative interface (applicable objects,
  PASS/FAIL evidence, uncertainty propagation) would reduce errors and development time. This
  is not a commitment to convert the whole 1137e2bb checker to table-driven logic. Other tasks
  may use lightweight task-specific deterministic checks plus the evidence-grounded judge and
  human review. Any refactor is justified only by actual task requirements or observed
  failures, lands in separate commits, and preserves the existing scoring semantics.
- Approved rubrics, grading implementations and tests are unchanged by this entry.

## Pilot A wiring U1/U2 (2026-10-31; mock-verified; no model, judge or paid call; logs under `logs/pilot-wiring-20261031T214901Z/`)

### U1 — real generation wiring (`harness/launcher.py`, CLI section only)

- `build_unit` (shared by `--dry-run` and `--real-run`): `build_samples(verify_config)` (I1 allowlist and
  hashes), `verify_system_prompt` (the prompt file must hash to `generation.system_prompt_sha256`;
  the config records the stripped text that `make_task` sends; mismatch refuses), `make_task` with the
  config tool timeout, one sample enforced, unit id.
- `main(argv, *, eval_fn=None, environ=None, docker_runner=subprocess.run)`: `--dry-run` or
  `--real-run` is mandatory (mutually exclusive). `--real-run` additionally requires an environment
  not in mock mode (`refuse_disabled_model_api`), `--confirm '<task_id>|<model>|<estimate_usd>'`
  restating the paid scope exactly, `--authorized-by` and `--authorization-ref` (audit metadata
  recorded verbatim; the launcher does not verify an approval), a known provider with its credential
  name present (names only), the image pre-flight by ID and the prompt hash check. `inspect_ai.eval`
  is imported only inside the real branch; `eval_fn`/`environ`/`docker_runner` are test seams.
- A `real_run_provenance` record (commit, dirty flag, config sha256 and status, prompt file/sha/form,
  image id and platform, task id, model, sample ids, staging verification, env variable names,
  authorization metadata) is written before `run_sample`; `run_sample`, its single Task/EvalLog/
  sample contract, the ledger and every stop rule are unchanged.
- Preflight coverage check: file isolation (allowlist + hashes), image (ID, platform), credentials
  (name presence, never values), budget and stop state (`run_sample` → `_refuse_if_stopped`,
  `reserve`), prompt hash (new). Not added: a check that `runs_root` is outside the repository
  (policy text only; not a provider-call risk).

### U2 — offline deterministic grading CLI (`grading/run_grading.py`, new)

- Inputs: `--host-dir runs_root/<uuid>`, `--eval-log`, `--task-id`, `--out-dir`, optional
  `--ledger --unit-id`, `--no-recalc`. `resolve_run`: run.json binding, directory name, the log's
  sample uuid, sample id (= task id), eval id, model and epoch must agree, else refused.
  `load_materials`: rubric, independent reference and task prompt from host paths (`private/`,
  `data/prompts`; prompt hashed against `config.tasks`), never from a sandbox.
- Grades with `grade_run(judge=None)`: the 7 judge-only items are `pending_judge`, excluded from E,
  `judge_mode: none`; human-review materials written by `grade_run`; a
  `grading_run_<uuid>_<ts>.json` provenance record links run binding, eval-log sha256, code commit,
  config sha256, material hashes, grader version, pending judge items and the launcher settlement
  (cost source "launcher ledger settlement" when given, otherwise "not linked").

### Verification (first execution captured unless a test defect required a rerun)

| Command (`run_isolated.sh`, `/usr/bin/time -p`) | Wall clock | Exit | Result |
|---|---|---|---|
| `unittest harness.tests.test_launcher_regressions` (+4 `RealRunCliTests`: explicit mode and scope, prompt-hash refusal, real path with injected eval incl. provenance and no key leakage, dry-run via the shared unit) | 6.04 s / 6.09 s | 1 / 0 | 32/33 then 33/33 (first run: a test helper dropped the `config` argument; fixed) |
| `harness.tests.regress_pilot_cli` — `main --real-run` with real Inspect eval, docker sandbox, mockllm scripted tool call (`pilot-cli`, `-2`, `-3`) | 8.62 s / 6.71 s / 7.49 s | 1 / 1 / 0 | 10/10 on the third run; first: the scripted tool call used `cmd` instead of `command` (no file written, still a valid no-files run); second: the leak scan counted the test's own env file |
| `grading.tests.regress_grading_cli` on the saved mock run of `pilot-cli-2` (real `.eval`, run_outcome.json, note.txt) | 1.29 s / see log | 1 / 0 | 14/15 then 15/15 (first: expectation written for the no-files run; the graded run has one collected file → `complete`) |

Not run (unchanged): grading layout/chain, harness unit suites, Inspect/limits/closeout/tools/compose/
recalc regressions.

### Still unverified / pending

Real provider compatibility (Anthropic usage fields, cache tokens, stop reasons, `.eval` content for
a paid run) remains unverified by design. Pending human decisions: Model A final approval,
reservation amount, missing-usage hold, judge model id, real-run authorization and its reference.
Pilot A request wording of the enabling steps still says `main()` is not wired (now wired behind
`--real-run`; a paid run still cannot start without the pending approvals and U3) — to be updated
with the next documentation pass.

## Pilot A wiring U3 (2026-10-31; judge adapter and judged grading pass; mock-verified; no provider call; logs under `logs/pilot-wiring-20261031T214901Z/`)

### Call chain
`grading.run_grading.main --judge` → `judge_gate` (scope restatement `--confirm-judge '<run_uuid>|<judge_model>|<estimate>'`,
`--authorized-by`/`--authorization-ref` recorded verbatim and never verified, `--ledger`, non-mock environment and
credential name for a real provider, refusal when a judged pass already exists unless `--rejudge`) →
`PilotLauncher.record("judge_authorization")` → `PilotLauncher.run_judge_batch(unit_id="<uuid>:judge:<ts>", estimate, batch_fn)`
→ `batch_fn` = `grade_run(judge=ProviderJudge)` (deterministic checks re-run unchanged; `judge_units` calls the adapter once per
judge-only item; review materials written with the judge verdicts sealed in a new versioned file) → `ProviderJudge.batch_result()`
→ `ledger.settle` → `judge_calls_<uuid>_<ts>.json` (every call: unit id, item, request sha256, status, raw response, usage,
error, seconds) → provenance `grading_run_<uuid>_<pass>.json` with the selected pass. Without `--judge` the CLI is byte-for-byte
the U2 behaviour (no provider import, no ledger write).

### Files
- `grading/judge.py`: `ProviderJudge` (Inspect `get_model` + `generate`, injectable `generate`; structured call record, never a
  sentinel string), `usage_dict`, `judge_units` accepting str (stubs) or call records; error classes `provider_error`
  (request failed or provider-reported error: cannot_assess, no parse) and `judge_parse_error` (answer outside the protocol:
  cannot_assess); `usage_status` ok / missing / uncertain / not_reported is a cost flag that never changes a verdict.
- `grading/grade.py`: pass identity on every results record and grade row (`grading_pass`, `pass_kind`
  deterministic_only / deterministic_plus_judge / stub_test, `supersedes_pass`, `pass_index`), J rows carry `error_class`,
  `call_status`, `usage_status`; `judge_call_summary` in results; `grading_passes(out_dir, run_uuid)` and
  `select_pass(passes, prefer="latest_with_judge")` define how a report picks exactly one pass per run (two passes of one
  run are never two samples). Additive schema fields only; deterministic verdicts and rubric unchanged.
- `harness/launcher.py` `run_judge_batch`: accepts the adapter's dict result; incomplete usage (any call missing/uncertain)
  is settled at the larger of the priced known part and the reservation, flagged `estimated`, the known usage kept in the
  note and the call log (never priced as if complete, never zero); tuple results keep the old behaviour; `BudgetExhausted`
  from a recorded stop or hold surfaces in the CLI as a clean refusal before any call.
- `grading/run_grading.py`: `--judge`, `--judge-model`, `--judge-estimate-usd`, `--confirm-judge`, `--authorized-by`,
  `--authorization-ref`, `--rejudge`, `--env-file`; `judge_factory` / `environ` injection points; cost record gains
  `grading` (judge settlement, priced-from-calls, calls log).

### Partial failure and repeats
A provider exception or provider-reported error on one call leaves the other calls' usage and verdicts intact; that unit is
cannot_assess (`provider_error`) and the batch is `usage_incomplete` → conservative settlement. A second `--judge` on a run
that already has a judged pass is refused with no reservation unless `--rejudge` (a new paid pass, new pass id). After a
restart the ledger's stops/holds persist and refuse the judge pass before any call (shown with the mock run's unpriced
generation hold, cleared by `clear_review` in the regression as a human would).

### Verification (first execution captured unless a test defect required a rerun)

| Command (`run_isolated.sh`, `/usr/bin/time -p`) | Wall clock | Exit | Result |
|---|---|---|---|
| `unittest grading.tests.test_grading_chain` (+ `JudgeAdapterTests` ×2, pass-identity test) | 2.62 → 2.49 → 2.59 s | 1, 1, 0 | 24/24 (fixture defects: synthetic unit lacked two render keys; usage sum expectation counted 4 instead of 3 responses) |
| `unittest harness.tests.test_launcher_regressions` (+ `JudgeBatchSettlementTests`) | 5.59 → 5.40 → 5.55 s | 1, 1, 0 | 34/34 (string estimate; the 2× stop case had to come last) |
| `grading.tests.regress_grading_cli` on the saved mock run (D-only pass, gate refusals, hold refusal, cleared review, judged pass via real `get_model("mockllm/model")`, ledger, call log, review isolation, repeat refusal) | 0.98 → 1.00 → 1.36 → 1.70 → 1.68 s | 1, 1, 1, 1, 0 | 33/33 (code fixes: mock-mode refusal surfaced as `GradingCliError`; ledger refusal surfaced cleanly; provenance file named by pass id after a same-second collision; test fixes: ledger copy with cleared hold; mockllm attaches its own usage, so the missing-usage branch is covered by the unit test) |

Not run (unchanged): layout suite, harness unit suites, Inspect/limits/closeout/tools/compose/recalc, `regress_pilot_cli`.

### Pending (not approved, not changed)
config `judge` block (model id, temperature, max_tokens, max_retries, timeout: the adapter reads `cfg["judge"]` when present,
defaults temperature 0 / max_tokens 1024 otherwise); judge model id (candidate `google/gemini-3.1-pro-preview`); judge
reservation per run; missing-usage hold policy (an incomplete judge batch is settled conservatively but not held — pending);
Model A approval; real-run and judge paid authorizations. Real Gemini response format, refusal behaviour and usage fields
are unverified until the first authorized call.

### To review before Architecture Cleanup
`grade_run` re-runs extraction and deterministic checks for a judged pass (correct and cheap, but a judge-only pass is not
possible without refactoring); `run_judge_batch` prices the incomplete-usage case in the launcher rather than in
`budget.settle`; `usage_from_eval_sample`/`usage_dict` are two ModelUsage mappings; the review file versioning and the pass
identity are linked only by timestamps in the results record.

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
- Docker Desktop 29.6.1 (containerd image store): on 2026-10-31 `docker image inspect
  gdpval-sandbox:stage2` answered "No such image" for about two minutes and across several
  calls while `docker image ls` listed the tag and inspect by image ID
  (`18cde712cde1…`) succeeded; after a `docker run --rm gdpval-sandbox:stage2 true` by tag
  (exit 0) the tag lookup resolved again. Fourth observation of the misfire, first time
  seen to persist. Inspect's prebuilt verification uses exactly `docker image inspect
  <image>` and raises `PrerequisiteError` before any container starts when it misfires
  (fast fail, no cost, no eval log); the launcher pre-flight retries a bounded number of
  times. Evidence: `logs/pilot-a-remediation-20261031T002107Z/compose_local_attempt1_daemon_tag_misfire.log`.
- Toolchain requirements surfaced for the next stage: read xlsx drawing text boxes;
  parse `pieChart`/`pie3DChart` from chart XML; read pivot data-field aggregation
  attributes; normalise store ids; LibreOffice recalculation; PivotTable creation test;
  PDF rendering for visual review.

## In flight

Nothing. Waiting for the human's decisions listed under "Next stage".

## Decisions taken (date · what · commit)

- 2026-10-31 · Close-out review remediation: 1137e2bb extraction layer rebuilt as the pipeline
  identify_tables → map_columns → parse_rows → evaluate_dependencies → checks (table identity
  from structure, coverage only disambiguates; confirmed_missing vs unmapped; unidentified rows
  bound the confirmed missing count; evidence-based verdicts without first-blocker short
  circuit; id normalisation with identity-level collisions; error attribution by evidence
  incl. independent XML validation); launcher single-sample contract; EvalStatus validation;
  YAML pre-flight with platform and alias checks; long-term regressions corrected. All suites
  green · uncommitted
- 2026-10-31 · Final-review remediation: B2 eval-error override removed (fail closed,
  adjudication cannot release errors); B3 unique column mapping with explicit dependency
  sets, working-copy lifecycle and grader-side fault classes; B4 exact decimal quantities
  with changed-row reporting; B6 aggregated/per-call usage reconciliation with conservative
  settlement and review hold; I6 redaction in grading records; I7 Inspect ModelCost on
  default-TTL rates, ledger assumptions recorded; I8 PLAN attribution wording; sandbox
  image pinned by full local ID in compose, config, converter and pre-flight. All suites
  green (see the section's table) · uncommitted
- 2026-10-31 · Pilot-A pre-review remediation: B1 launcher dispatches `max_tokens`,
  `attempt_timeout` and `token_limit` (fail closed, before any ledger change); B2 eval-level
  log errors block grading unless an auditable exclusion is recorded; B3/B4 deterministic
  checks rewritten (schema with synonyms, extraction separated from verdict, transfer and
  format-based attribution, row multiset, phrase-bound Word counts); B5 fresh-directory
  recalculation with soffice exit status; B6 ledger v2 (schema-validated events, persisted
  engineering failures and stops, unknown-cost hold, locked init, strict reservation
  idempotence); I1 no overwrite of review records; I2 stub gate and batch protocol; I3/I8
  disclosures and retractions; I4 process-level concurrency test; I5 `x-local` +
  `pull_policy: never` with corrected semantics; I6 redaction of persisted error text; I7
  price tiers. All suites green (see the section's table) · uncommitted
- 2026-10-30 · Pilot A/B DRAFT configuration: A `claude-opus-5-5`, B `gpt-6.1-sol`, judge
  `gemini-3.1-pro-preview` (ids and Inspect names recorded; launcher contract checked, no
  mismatch); no reasoning effort set, provider defaults documented separately from
  Inspect's request construction and from pilot-pending behaviour; `cost_limit` 10 USD per
  sample, `token_limit` 10,000,000 (type all), `max_tokens` 16,384, time / working 3,600 s,
  `message_limit` 200, pilot ceiling 30 USD; report labels cost-capped / budget-limited /
  output-capped recorded. Blocking before the pilot: launcher must pass `max_tokens` and
  read `token_limit` from the config; output-capped detection is a pre-freeze TODO · config
  and status only, uncommitted
- 2026-10-30 · Second Stage 3b round: 1137e2bb C2 APPROVED (revised); Stage 3b
  infrastructure committed as `efea742bceb304af841d0515cc48f256b2e64a24`; provider model
  lists recorded (`data/provider_model_lists/20261030T223043Z.json`); Inspect `cost_limit`
  verified and triggered with the mock, `cost` added to the budget limit types, launcher
  fails closed without price data; partial-collection attribution (model-caused /
  harness-caused / unknown, adjudication in a separate file) written into
  `grading_decision` and the loader; grading chain for 1137e2bb implemented with fixtures
  and 15 integration tests; preregistration 2.4 D list corrected to include items 2 and 21
  · grading-chain work uncommitted
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

- 2026-10-31 · Extraction review (`logs/extraction-review-0r3d__40/`): R1 cell-value rule (blank,
  NaN, Infinity, non-numeric, non-binary = confirmed invalid; unrecalculated = grader side; no
  skipped comparison), R2 held-by-identity rows and summary cells through `read_value`, R3
  two-list column records and row-scoped named lines, R5 reference-entity resolution and
  reference collisions, R6 single Task / EvalLog / sample contract (pre- and post-call), XML
  validation cap = `resource_limit` (grader), R4 split-table safe exit; two Codex-flagged test
  expectations corrected with their basis recorded; rubric 7 / 18–20 scope question recorded as
  PENDING proposed adjudication in `preregistration.md` 2.4, not applied · (uncommitted)

- 2026-10-31 · Human approved: cell-value rule (blank flag = confirmed invalid) and the scope of
  rubric 7 / 18–20 (row-set defects act on C1 through items 5 and 6 only; 7 per identified
  non-CASE line; 18–20 column sums over all delivered rows vs 15 / 10 / 25, independent) ·
  applied in `DEPENDENCIES` and the 18–20 branch; amendment record in `preregistration.md`
  2.4; Pilot A request drafted in `docs/pilot_a_request.md` · (uncommitted)

- 2026-10-31 · Stage 3b review (`logs/stage3b-review-js7f8gca/`): item 7 decides applicability
  from the row's own UOM before reading the flag (CASE lines outside rubric 7); split tables
  with a business identity repeated across sheets make the affected sum items cannot_assess
  (both scopes recorded) instead of a double-counted FAIL; Pilot A request corrected to the
  implementation (cost arithmetic, no bill cap, missing-usage accounting, per-unit judge,
  not executable yet) · (uncommitted)

- 2026-10-31 · Stage 3b close-out 2 review: no FAIL is inferred from the two extreme overlap
  scopes in items 18–20 (cannot_assess with both candidate totals and the occurrences as
  evidence; zero-contribution overlaps still decided on the reliable total; invalid cells still
  FAIL); Pilot A request wording corrected (per-criterion judge calls, settlement branches of a
  returned eval error) · (uncommitted)

- 2026-10-31 · Stage 3b deterministic grader final review CLOSED (no Pilot-blocking defect);
  DEFER REFACTOR of the declaration/loop split recorded as maintenance; CLAUDE.md gains the
  scoring proof-obligation rule; Git checkpoint prepared, commit awaiting authorization ·
  (uncommitted)

- 2026-10-31 · Pilot A wiring U1 (real-run CLI path: shared `build_unit`, prompt-hash check,
  explicit `--real-run --confirm --authorized-by --authorization-ref`, provenance record, injected
  eval for tests) and U2 (`grading/run_grading.py`: run identity binding, host-only materials,
  judge pending, provenance/cost link) implemented and mock-verified; no provider call ·
  (uncommitted)

- 2026-10-31 · Pilot A wiring U3: `ProviderJudge` adapter (structured call records, error classes
  provider_error / judge_parse_error, usage status as a cost flag), gated `--judge` pass in
  `run_grading.py` through `run_judge_batch` (conservative settlement of incomplete usage), grading
  pass identity and `select_pass` rule; mock-verified; config `judge` block and all paid decisions
  PENDING · (uncommitted)

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
