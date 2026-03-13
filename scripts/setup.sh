#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

STEP="${1:-environment}"
shift || true

python3 -m nanoclaw.setup --step "$STEP" "$@"
