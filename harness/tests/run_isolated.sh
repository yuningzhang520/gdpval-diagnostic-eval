#!/usr/bin/env bash
# Launch a harness test module with a minimal environment from a working directory that has no
# .env in itself or any ancestor, so neither the harness nor Inspect can pick up real credentials.
# Usage: harness/tests/run_isolated.sh <project_root> <module> [args...]
#   e.g. harness/tests/run_isolated.sh /abs/project harness.tests.test_collect_unit -v
# The project .venv interpreter is used by absolute path. INSPECT_DISABLE_MODEL_API=1 is forced.
# No environment value is printed by this script.
set -euo pipefail
ROOT="$1"; shift
MODULE="$1"; shift
case "$ROOT" in /*) ;; *) echo "project root must be absolute" >&2; exit 2;; esac
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "missing interpreter $PY" >&2; exit 2; }
# The collector walks every host path component with O_NOFOLLOW, so temporary directories must be
# real paths (macOS: /var and /tmp are symlinks; use /private/var/..., /private/tmp).
TMP_REAL="$(cd "${TMPDIR:-/tmp}" && pwd -P)"
WORK="${ISOLATED_CWD:-$(mktemp -d "$TMP_REAL/harness_isolated.XXXXXX")}"
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd -P)"
d="$WORK"
while :; do
  if [ -e "$d/.env" ]; then echo "refusing to run: $d/.env exists on the working-directory path" >&2; exit 3; fi
  [ "$d" = "/" ] && break
  d="$(dirname "$d")"
done
if [ -e "$ROOT/.env" ]; then
  echo "note: $ROOT/.env exists; it is not on the working-directory path and is not loaded by this launcher" >&2
fi
cd "$WORK"
exec /usr/bin/env -i \
  PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin" \
  HOME="$HOME" \
  TMPDIR="$TMP_REAL" \
  LANG="${LANG:-en_US.UTF-8}" \
  INSPECT_DISABLE_MODEL_API=1 \
  PYTHONPATH="$ROOT" \
  PYTHONDONTWRITEBYTECODE=1 \
  HARNESS_PROJECT_ROOT="$ROOT" \
  "$PY" -m "$MODULE" "$@"
