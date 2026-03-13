# mini-py-nanoclaw (Python Rewrite)

This repository now includes a Python rewrite of NanoClaw core orchestration modules.

## Scope in this pass

Implemented in `mini_py_nanoclaw/`:

- `config.py`: env/config loading and constants
- `types.py`: core data models and channel protocol
- `timezone.py`: UTC -> local display formatting
- `router.py`: XML formatting, outbound cleanup, channel lookup
- `group_folder.py`: secure group folder/path validation
- `db.py`: SQLite schema + message/task/group/session state operations
- `group_queue.py`: per-group queue + global concurrency + retry backoff
- `task_scheduler.py`: due-task scheduling and next-run computation
- `app.py`: orchestrator state skeleton

## Tests

Python tests are in `tests_py/`.

```bash
python3 -m venv .venv
.venv/bin/pip install croniter==2.0.7 pytest==7.4.4 pytest-asyncio==0.23.8
.venv/bin/python -m pytest tests_py
```

## Notes

- The TypeScript implementation is kept intact.
- This Python rewrite focuses on core logic/state modules first.
- Channel adapters and container runtime integration can be ported next.
