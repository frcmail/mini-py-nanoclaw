#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

CONTAINER_RUNTIME="${CONTAINER_RUNTIME:-docker}"
SERVICE_IMAGE="${SERVICE_IMAGE:-nanoclaw-service:smoke}"
AGENT_IMAGE="${AGENT_IMAGE:-nanoclaw-agent:smoke}"
COMPOSE_STARTED=0

cleanup() {
  if [[ "${COMPOSE_STARTED}" -eq 1 ]]; then
    CONTAINER_IMAGE="${AGENT_IMAGE}" ${CONTAINER_RUNTIME} compose down --remove-orphans >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

if ! command -v "${CONTAINER_RUNTIME}" >/dev/null 2>&1; then
  echo "[docker-smoke] missing container runtime: ${CONTAINER_RUNTIME}" >&2
  exit 127
fi

if [[ "${CONTAINER_RUNTIME}" == "docker" ]]; then
  "${CONTAINER_RUNTIME}" info >/dev/null
fi

if [[ ! -S /var/run/docker.sock ]]; then
  echo "[docker-smoke] missing /var/run/docker.sock" >&2
  exit 1
fi

echo "[docker-smoke] validating compose config"
${CONTAINER_RUNTIME} compose config -q

echo "[docker-smoke] building service image: ${SERVICE_IMAGE}"
${CONTAINER_RUNTIME} build -t "${SERVICE_IMAGE}" -f Dockerfile .

echo "[docker-smoke] building agent image: ${AGENT_IMAGE}"
${CONTAINER_RUNTIME} build -t "${AGENT_IMAGE}" -f container/Dockerfile container

echo "[docker-smoke] running setup smoke in container"
${CONTAINER_RUNTIME} run --rm \
  -e NANOCLAW_HOME=/tmp/nanoclaw-smoke \
  -e CONTAINER_IMAGE="${AGENT_IMAGE}" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  "${SERVICE_IMAGE}" \
  sh -lc 'python -m nanoclaw.setup --step environment && \
          python -m nanoclaw.setup --step container && \
          python -m nanoclaw.setup --step groups && \
          python -m nanoclaw.setup --step register && \
          python -m nanoclaw.setup --step verify'

echo "[docker-smoke] starting compose stack"
CONTAINER_IMAGE="${AGENT_IMAGE}" ${CONTAINER_RUNTIME} compose up -d
COMPOSE_STARTED=1

if ! ${CONTAINER_RUNTIME} compose ps --status running --services | grep -qx "nanoclaw"; then
  echo "[docker-smoke] nanoclaw service is not running" >&2
  ${CONTAINER_RUNTIME} compose ps >&2 || true
  ${CONTAINER_RUNTIME} compose logs --tail 100 nanoclaw >&2 || true
  exit 1
fi

echo "[docker-smoke] compose stack is running"
${CONTAINER_RUNTIME} compose logs --tail 20 nanoclaw || true

echo "[docker-smoke] success"
