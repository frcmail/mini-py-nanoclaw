---
name: debug
description: Debug Python NanoClaw runtime issues, including channel ingress/egress, scheduler/IPC flow, and container execution.
---

# NanoClaw Debug (Python)

Use this guide for runtime failures, message routing issues, or container execution problems.

## 1) Baseline checks

Run:

```bash
python -m nanoclaw.setup --step environment
python -m nanoclaw.setup --step verify
python -m pytest tests
```

If tests fail, fix test-reported regressions first.

## 2) Run service in foreground

```bash
LOG_LEVEL=debug python -m nanoclaw
```

Observe stdout/stderr directly for:
- channel connect failures
- container runtime check failures
- webhook token validation errors

## 3) Channel-level diagnostics

### local-file

- inbound dir: `data/channels/local-file/inbound`
- outbound dir: `data/channels/local-file/outbound`
- input files must be valid JSON and include non-empty `content`.

### cli-stdio

- ensure each input line is either plain text or JSON with `content`.
- empty lines and empty `content` are ignored.

### webhook-http

- endpoint: `POST /inbound`
- require header: `Authorization: Bearer <token>`
- token source: `NANOCLAW_WEBHOOK_TOKEN`
- outbound files: `data/channels/webhook/outbound/*.json`

## 4) IPC and task flow

- IPC base: `data/ipc/<group-folder>/`
- input queue: `data/ipc/<group-folder>/input/*.json`
- close sentinel: `data/ipc/<group-folder>/input/_close`
- ordering is filename-based timestamp+sequence; do not rename files manually.

## 5) Container runtime checks

If setup container step reports `docker_not_running` or `docker_missing`, run:

```bash
python -m nanoclaw.setup --step container
```

Then start/repair Docker and retest.

## 6) Fast triage outcome

At the end of debugging, report:
- failing subsystem (`channel`, `ipc`, `container`, or `scheduler`)
- exact failing command
- minimal reproduction input
- suggested fix with one verification command
