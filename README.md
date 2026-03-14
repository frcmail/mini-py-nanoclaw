# mini-py-nanoclaw

Pure Python NanoClaw runtime.

Chinese documentation: [README_zh.md](README_zh.md)

## What This Repo Provides

- Single Python runtime package: `nanoclaw`
- Python setup flow: `python -m nanoclaw.setup --step <name>`
- Python container agent runner: `python -m nanoclaw.agent_runner`
- Multi-channel runtime: `local-file`, `cli-stdio`, `webhook-http`

## Quick Start (3 Minutes)

1. Create a virtual environment and install dependencies.
```bash
python3 -m venv .venv
.venv/bin/pip install -e .[dev]
```

2. (Optional) copy env template.
```bash
cp .env.example .env
```

3. Start service.
```bash
.venv/bin/python -m nanoclaw
```

## Runtime Paths

Default runtime home is `~/.nanoclaw` (override with `NANOCLAW_HOME`):

```bash
export NANOCLAW_HOME=/path/to/nanoclaw-home
```

Key runtime directories:

- `$NANOCLAW_HOME/groups/<folder>/CLAUDE.md`: group memory files
- `$NANOCLAW_HOME/store/messages.db`: SQLite state
- `$NANOCLAW_HOME/data/`: channel and IPC runtime data

Optional (non-runtime-critical) repository assets:

- `assets/`: branding and presentation images
- `deploy/`: deployment templates (for example launchd)
- `config-examples/`: sample configs

## Setup Flow

Run individual setup steps:

```bash
python3 -m nanoclaw.setup --step environment
python3 -m nanoclaw.setup --step container
python3 -m nanoclaw.setup --step groups
python3 -m nanoclaw.setup --step register
python3 -m nanoclaw.setup --step mounts
python3 -m nanoclaw.setup --step service
python3 -m nanoclaw.setup --step verify
```

Compatibility wrappers (same behavior, optional): `./scripts/setup.sh`, `./setup.sh`

## Channels

Enable channels with `NANOCLAW_CHANNELS` (comma-separated):

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

`local-file` channel:

- Inbound dir: `$NANOCLAW_HOME/data/channels/local-file/inbound`
- Outbound dir: `$NANOCLAW_HOME/data/channels/local-file/outbound`

Inbound file example (`*.json`):
```json
{"chat_jid":"local:main","sender":"local:user","sender_name":"User","content":"hello"}
```

`cli-stdio` channel:

- Reads one line per inbound message from `stdin`
- Writes outbound messages as JSON lines to `stdout`

`webhook-http` channel:

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=your-bearer-token
NANOCLAW_WEBHOOK_OUTBOUND_URL=https://example.com/outbound  # optional
```

Inbound API: `POST /inbound` with `Authorization: Bearer <token>`

Required JSON fields: `chat_jid`, `sender`, `sender_name`, `content`  
Optional fields: `timestamp`, `chat_name`, `is_group`

## Recommended Commands

```bash
make lint        # ruff check nanoclaw tests
make test        # pytest
make build       # build sdist + wheel
make check       # lint + test + build
```

## Dockerized Run

Main service container (recommended flow):

```bash
make docker-build
make docker-up
docker compose logs -f nanoclaw
make docker-down
```

Prerequisite: Docker Engine + Docker Compose plugin.

Run Docker smoke test:

```bash
make docker-smoke
```

Smoke coverage:

- Build service + agent images
- Run setup steps in container (`environment/container/groups/register/verify`)
- Bring up `docker compose` and verify `nanoclaw` service is running

Docker socket note:

- Compose mounts `/var/run/docker.sock` into the service container so NanoClaw can continue to launch agent containers.
- This grants elevated host control to the container. Use only on trusted local/controlled environments.

### Container Roles

- Root `Dockerfile`: main NanoClaw service image (`python -m nanoclaw`)
- `container/Dockerfile`: agent runner image (`nanoclaw-agent`) used by task/container execution path

Build the agent image:

```bash
cd container
./build.sh
```

Compatibility:

- You can still use `docker compose ...` and `./scripts/docker-smoke.sh` directly.

## CI

- Lint: `ruff`
- Tests: `pytest` matrix (`3.9`, `3.11`, `3.12`)
- Packaging: `build` + `twine check`
- Docker smoke: `./scripts/docker-smoke.sh`
