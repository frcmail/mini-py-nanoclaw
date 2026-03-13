# mini-py-nanoclaw

Pure Python NanoClaw implementation.

## Status

- Runtime is Python-only (`mini_py_nanoclaw`).
- Setup is Python-only (`python -m mini_py_nanoclaw.setup --step ...`).
- Container agent runner is Python-only (`mini_py_nanoclaw.agent_runner`).
- Legacy Node/TypeScript runtime paths were removed from the main execution path.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install croniter==2.0.7 pytest==7.4.4 pytest-asyncio==0.23.8
.venv/bin/python -m mini_py_nanoclaw
```

## Setup Steps

Run setup steps individually:

```bash
python3 -m mini_py_nanoclaw.setup --step environment
python3 -m mini_py_nanoclaw.setup --step container
python3 -m mini_py_nanoclaw.setup --step groups
python3 -m mini_py_nanoclaw.setup --step register
python3 -m mini_py_nanoclaw.setup --step mounts
python3 -m mini_py_nanoclaw.setup --step service
python3 -m mini_py_nanoclaw.setup --step verify
```

Or via helper script:

```bash
./setup.sh environment
```

## Channels

Configure channels via `NANOCLAW_CHANNELS`:

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

Webhook channel variables:

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=your-bearer-token
NANOCLAW_WEBHOOK_OUTBOUND_URL=https://example.com/outbound  # optional
```

Inbound webhook payload (`POST /inbound`):

- Required: `chat_jid`, `sender`, `sender_name`, `content`
- Optional: `timestamp`, `chat_name`, `is_group`

## Running Tests

```bash
.venv/bin/python -m pytest tests_py
```

## Container Build

```bash
cd container
./build.sh
```
