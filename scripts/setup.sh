#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

STEP="${1:-environment}"
shift || true

if [[ -x "${PROJECT_ROOT}/.venv/bin/python" ]]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
else
  PYTHON_BIN="${PYTHON_BIN:-python3}"
fi

cd "$PROJECT_ROOT"
PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH:-}" "$PYTHON_BIN" -m nanoclaw.setup --step "$STEP" "$@"
