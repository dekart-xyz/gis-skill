#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

REMOTE="${1:-origin}"
REF="${2:-HEAD}"

# First push triggers release hook and is expected to fail with new commits created.
set +e
git push "$REMOTE" "$REF"
rc=$?
set -e

if [[ $rc -ne 0 ]]; then
  echo "[release-and-push] First push stopped by pre-push hook (expected)."
fi

# Second push sends the newly created release commit(s).
git push "$REMOTE" "$REF"

echo "[release-and-push] Done."
