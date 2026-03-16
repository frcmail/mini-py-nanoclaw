---
name: customize
description: Customize Python NanoClaw behavior, channels, routing, scheduling, and container execution while preserving current runtime contracts.
---

# NanoClaw Customize (Python)

Use this skill for behavior changes in the Python codebase.

## Workflow

1. Clarify target behavior and acceptance criteria.
2. Identify the smallest Python subsystem to change.
3. Implement directly in `nanoclaw/`.
4. Add or update tests in `tests/`.
5. Verify with `python -m pytest tests`.

## Primary extension points

- `nanoclaw/app.py`: orchestration loop and channel setup
- `nanoclaw/channels/`: channel implementations and registry
- `nanoclaw/router.py`: message formatting and outbound normalization
- `nanoclaw/task_scheduler.py`: schedule computation and dispatch
- `nanoclaw/container_runner.py`: agent invocation and output parsing
- `nanoclaw/ipc.py` + `nanoclaw/ipc_io.py`: IPC watcher and file protocol
- `nanoclaw/config.py`: runtime/env configuration

## Common customization patterns

### Add or adjust channel behavior

- Implement or update a channel in `nanoclaw/channels/`.
- Register via registry self-registration.
- Keep channel selection compatible with `NANOCLAW_CHANNELS`.

### Adjust routing or triggers

- Update trigger or routing logic in `app.py` and `router.py`.
- Preserve message cursor rollback behavior on agent failure.

### Add setup behavior

- Extend `nanoclaw/setup/` with a new step only if needed.
- Keep setup status-block output format unchanged.

### Modify container interaction

- Keep output markers and IPC contracts stable.
- Preserve timeout, retry, and session semantics.

## Validation standard

Always run:

```bash
python -m pytest tests
```

For runtime-impacting changes, also run:

```bash
python -m nanoclaw.setup --step verify
```
