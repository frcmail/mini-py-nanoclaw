# mini-py-nanoclaw (Pure Python)

This repository is now a pure Python NanoClaw implementation.

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
- `app.py`: orchestrator runtime loop + channel orchestration
- `channels/local_file.py`: filesystem-based local channel
- `channels/cli_stdio.py`: stdin/stdout local channel
- `channels/webhook_http.py`: webhook channel (`POST /inbound`)
- `ipc_io.py`: IPC input file protocol helpers (ordered delivery)

## Tests

Python tests are in `tests_py/`.

```bash
python3 -m venv .venv
.venv/bin/pip install croniter==2.0.7 pytest==7.4.4 pytest-asyncio==0.23.8
.venv/bin/python -m pytest tests_py
```

## Notes

- Main runtime, setup chain, and container agent runner are all Python.
- Legacy TypeScript runtime paths were removed from the executable path.

## Channel Configuration

Set enabled channels via `NANOCLAW_CHANNELS` (comma-separated):

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

Webhook channel environment variables:

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=your-bearer-token
NANOCLAW_WEBHOOK_OUTBOUND_URL=https://example.com/webhook-outbound  # optional
```

Inbound webhook payload (`POST /inbound`) fields:
- required: `chat_jid`, `sender`, `sender_name`, `content`
- optional: `timestamp`, `chat_name`, `is_group`
