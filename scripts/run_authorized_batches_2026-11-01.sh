#!/usr/bin/env bash
# Authorized paid batches of 2026-11-01 (docs/status.md decision entry of that date): Gemini dev (10) -> candidate
# compat (Opus 5.5, then GPT-6.1 Sol) -> Gemini sealed validation (10). Sequential, concurrency 1, every unit through
# the launcher gates (harness.batch -> harness.launcher.main). The chain stops at the first batch that does not
# complete; nothing is retried or restarted automatically. The config snapshot taken at launch is passed as --config
# (taken by this script at launch) so later repository edits (grader versions) cannot change a running batch's recorded conditions. Logs: one console
# log per batch plus driver.log under ~/turing-eval-runs/batch_console/. Credentials: .env read by the launcher only.
set -uo pipefail
ROOT=/Users/yuning/turing-th
R=/Users/yuning/turing-eval-runs
SHA="$(shasum -a 256 "$ROOT/config.json" | cut -c1-12)"
mkdir -p "$R/config_snapshots"
CFG="${CFG_OVERRIDE:-$R/config_snapshots/config_$SHA.json}"   # CFG_OVERRIDE: reuse an earlier snapshot so one run class keeps one config sha (generation keys unchanged)
[ -f "$CFG" ] || cp "$ROOT/config.json" "$CFG"   # snapshot taken at launch; recorded as config_path + sha256 in every unit's provenance
LOGD="$R/batch_console"
AUTH_BY='Yuning Zhang (human approval in chat, 2026-11-01)'
AUTH_REF='docs/status.md decision 2026-11-01: paid batches dev / compat / validation authorized'
export INSPECT_DISPLAY=plain PYTHONUNBUFFERED=1
cd "$ROOT" || exit 1
run() {
  local label=$1 model=$2 units=$3 est=$4
  local log="$LOGD/${label}_$(echo "$model" | tr '/' '_')_$(date -u +%Y%m%dT%H%M%SZ).log"
  echo "=== $(date -u +%FT%TZ) start $label $model units=$units estimate=$est log=$log" >> "$LOGD/driver.log"
  "$ROOT/.venv/bin/python" -m harness.batch --config "$CFG" --run-label "$label" --model "$model" --runs-root "$R/$label/runs" --ledger "$R/$label/ledger.json" \
    --real-run --confirm-batch "$label|$model|$units|$est" --authorized-by "$AUTH_BY" --authorization-ref "$AUTH_REF" > "$log" 2>&1
  local rc=$?
  echo "=== $(date -u +%FT%TZ) end $label $model rc=$rc" >> "$LOGD/driver.log"
  return $rc
}
# Usage: run_authorized_batches_2026-11-01.sh [BATCHES]   BATCHES defaults to "dev compat validation"; e.g. "compat validation" to resume
BATCHES="${1:-dev compat validation}"
for b in $BATCHES; do
  case "$b" in
    dev)        run dev google/gemini-3.8-flash 10 5.00 || { echo "dev batch did not complete; chain stopped" >> "$LOGD/driver.log"; exit 1; } ;;
    compat)     run compat anthropic/claude-opus-5-5 1 8.00 || { echo "compat (Opus) did not complete; chain stopped" >> "$LOGD/driver.log"; exit 1; }
                run compat openai/gpt-6.1-sol 1 5.00 || { echo "compat (GPT) did not complete; chain stopped" >> "$LOGD/driver.log"; exit 1; } ;;
    validation) run validation google/gemini-3.8-flash 10 5.00 || { echo "validation batch did not complete; chain stopped" >> "$LOGD/driver.log"; exit 1; } ;;
    *) echo "unknown batch $b" >> "$LOGD/driver.log"; exit 2 ;;
  esac
done
echo "=== $(date -u +%FT%TZ) all authorized batches completed" >> "$LOGD/driver.log"
