---
name: customize
description: Customize Python NanoClaw behavior, channels, routing, scheduling, and container execution while preserving current runtime contracts.
---

# NanoClaw Customize (Python)

Use this skill for behavior changes in the Python codebase.

## Workflow

1. Clarify target behavior and acceptance criteria.
2. Identify the smallest Python subsystem to change.
3. Implement directly in `mini_py_nanoclaw/`.
4. Add or update tests in `tests/`.
5. Verify with `python -m pytest tests`.

## Primary extension points

- `mini_py_nanoclaw/app.py`: orchestration loop and channel setup
- `mini_py_nanoclaw/channels/`: channel implementations and registry
- `mini_py_nanoclaw/router.py`: message formatting and outbound normalization
- `mini_py_nanoclaw/task_scheduler.py`: schedule computation and dispatch
- `mini_py_nanoclaw/container_runner.py`: agent invocation and output parsing
- `mini_py_nanoclaw/ipc.py` + `mini_py_nanoclaw/ipc_io.py`: IPC watcher and file protocol
- `mini_py_nanoclaw/config.py`: runtime/env configuration

## Common customization patterns

### Add or adjust channel behavior

- Implement or update a channel in `mini_py_nanoclaw/channels/`.
- Register via registry self-registration.
- Keep channel selection compatible with `NANOCLAW_CHANNELS`.

### Adjust routing or triggers

- Update trigger or routing logic in `app.py` and `router.py`.
- Preserve message cursor rollback behavior on agent failure.

### Add setup behavior

- Extend `mini_py_nanoclaw/setup/` with a new step only if needed.
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
python -m mini_py_nanoclaw.setup --step verify
```
