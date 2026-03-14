#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-docker}"
SERVICE_IMAGE="${SERVICE_IMAGE:-nanoclaw-service:smoke}"

echo "[docker-smoke] building service image: ${SERVICE_IMAGE}"
${CONTAINER_RUNTIME} build -t "${SERVICE_IMAGE}" -f Dockerfile .

echo "[docker-smoke] running setup smoke in container"
${CONTAINER_RUNTIME} run --rm \
  -e NANOCLAW_HOME=/tmp/nanoclaw-smoke \
  -v /var/run/docker.sock:/var/run/docker.sock \
  "${SERVICE_IMAGE}" \
  sh -lc 'python -m nanoclaw.setup --step environment && \
          python -m nanoclaw.setup --step groups && \
          python -m nanoclaw.setup --step register && \
          python -m nanoclaw.setup --step verify'

echo "[docker-smoke] success"
