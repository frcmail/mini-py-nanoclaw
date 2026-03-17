# mini-py-nanoclaw

Pure Python NanoClaw runtime (`nanoclaw` package), with no Node runtime dependency in the main service path.

Chinese version: [README_zh.md](README_zh.md)

## Overview

This repository provides:

- Runtime entry: `python -m nanoclaw`
- Setup entry: `python -m nanoclaw.setup --step <name>`
- Agent runtime entry: `python -m nanoclaw.agent_runner`
- Channels: `local-file`, `cli-stdio`, `webhook-http`

Main runtime data is stored in `NANOCLAW_HOME` (default: `~/.nanoclaw`).

## Quick Start

1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
cp .env.example .env  # optional
```

2. Run setup checks

```bash
./setup.sh environment
./setup.sh groups
./setup.sh register
./setup.sh verify
```

3. Start service

```bash
.venv/bin/python -m nanoclaw
```

4. Send a test message via `local-file`

```bash
mkdir -p ~/.nanoclaw/data/channels/local-file/inbound
cat > ~/.nanoclaw/data/channels/local-file/inbound/hello.json <<'JSON'
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello"}
JSON
```

Then check outbound files under:

- `~/.nanoclaw/data/channels/local-file/outbound/`

## Runtime Layout

Default `NANOCLAW_HOME` is `~/.nanoclaw`.

Important paths:

- `$NANOCLAW_HOME/groups/<folder>/CLAUDE.md`: per-group memory file
- `$NANOCLAW_HOME/store/messages.db`: SQLite state
- `$NANOCLAW_HOME/data/channels/`: channel runtime files
- `$NANOCLAW_HOME/data/ipc/`: IPC runtime files

Repository directories that are not required at runtime:

- `assets/` (branding)
- `deploy/` (deployment templates)
- `config-examples/` (sample configs)

## Setup Steps

Use either `python -m nanoclaw.setup --step <name>` or wrapper `./setup.sh <step>`.

Available steps:

1. `environment`: verify Python version and platform
2. `container`: check container runtime availability
3. `groups`: create default group memory files
4. `register`: register main local group
5. `mounts`: generate mount allowlist config if missing
6. `service`: print service mode hint
7. `verify`: verify required runtime directories

Full sequence:

```bash
python -m nanoclaw.setup --step environment
python -m nanoclaw.setup --step container
python -m nanoclaw.setup --step groups
python -m nanoclaw.setup --step register
python -m nanoclaw.setup --step mounts
python -m nanoclaw.setup --step service
python -m nanoclaw.setup --step verify
```

Compatibility wrappers:

- `./setup.sh`
- `./scripts/setup.sh`

## Configuration

Key environment variables:

| Variable | Default | Description |
|---|---|---|
| `NANOCLAW_HOME` | `~/.nanoclaw` | Runtime home (groups/store/data) |
| `ASSISTANT_NAME` | `Andy` | Assistant display/trigger name |
| `LOG_LEVEL` | `INFO` | Log level |
| `NANOCLAW_CHANNELS` | `local-file` | Comma-separated channel list |
| `NANOCLAW_WEBHOOK_HOST` | `127.0.0.1` | Webhook bind host |
| `NANOCLAW_WEBHOOK_PORT` | `8787` | Webhook bind port |
| `NANOCLAW_WEBHOOK_TOKEN` | empty | Required when webhook channel is enabled |
| `NANOCLAW_WEBHOOK_OUTBOUND_URL` | empty | Optional webhook outbound callback URL |
| `CONTAINER_TIMEOUT` | `1800000` | Agent execution timeout (ms) |
| `MAX_CONCURRENT_CONTAINERS` | `5` | Group queue concurrency limit |
| `NANOCLAW_REQUIRE_CONTAINER_RUNTIME` | `0` | `1` = fail-fast if runtime unavailable; `0` = degraded startup |

## Channels

Enable multiple channels:

```bash
export NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

### local-file

- Inbound: `$NANOCLAW_HOME/data/channels/local-file/inbound/*.json`
- Outbound: `$NANOCLAW_HOME/data/channels/local-file/outbound/*.json`

Inbound example:

```json
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello","is_group":true}
```

### cli-stdio

- Inbound: one line from `stdin` (plain text or JSON)
- Outbound: JSON lines to `stdout`

Example:

```bash
echo '{"chat_jid":"cli:main","sender":"cli:user","sender_name":"CLI","content":"hello"}' | \
  NANOCLAW_CHANNELS=cli-stdio .venv/bin/python -m nanoclaw
```

### webhook-http

Required when enabled:

```bash
export NANOCLAW_CHANNELS=webhook-http
export NANOCLAW_WEBHOOK_TOKEN=your-token
```

Inbound endpoint:

- `POST /inbound`
- Header: `Authorization: Bearer <token>`
- Required JSON fields: `chat_jid`, `sender`, `sender_name`, `content`
- Optional fields: `timestamp`, `chat_name`, `is_group`

Outbound behavior:

- Always writes JSON files to `$NANOCLAW_HOME/data/channels/webhook/outbound/`
- Optionally POSTs to `NANOCLAW_WEBHOOK_OUTBOUND_URL`

## Development Commands

```bash
make install-dev
make lint
make test
make build
make check
make run
make setup-verify
```

## Docker

### Main Service

```bash
make docker-build
make docker-up
docker compose logs -f nanoclaw
make docker-down
```

### Smoke Test

```bash
make docker-smoke
```

Smoke includes:

- Build service image
- Build agent image
- Validate agent entrypoint output markers
- Run setup smoke (`environment/container/groups/register/verify`)
- Bring up compose and check service status

### Container Roles

- Root `Dockerfile`: main service image (`python -m nanoclaw`)
- `container/Dockerfile`: agent image (`nanoclaw-agent`)

Build agent image directly:

```bash
./container/build.sh local
```

### Security Note for `docker.sock`

Compose mounts `/var/run/docker.sock` into service container to keep container runtime ability.
This effectively grants elevated host-level capability. Use only in trusted environments.

## CI

Current CI jobs:

- Ruff lint
- Pytest matrix (`3.9`, `3.11`, `3.12`)
- Package build + `twine check`
- Docker smoke script

## Troubleshooting

1. `./setup.sh` fails with module import error

- Use repository root as working directory
- Ensure `.venv` exists or `python3` has `nanoclaw` installed

2. Webhook returns `401 unauthorized`

- Verify `NANOCLAW_WEBHOOK_TOKEN`
- Verify header format `Authorization: Bearer <token>`

3. Service starts but no response

- Confirm `NANOCLAW_CHANNELS`
- Check inbound payload has non-empty `content`
- Run `python -m nanoclaw.setup --step verify`

4. Docker unavailable but service should still run

- Keep `NANOCLAW_REQUIRE_CONTAINER_RUNTIME=0` (default)
- Set to `1` only when fail-fast behavior is required
