---
name: setup
description: Run Python-first NanoClaw setup end-to-end. Use when user needs first-time setup, environment checks, channel enablement, or quick recovery.
---

# NanoClaw Setup (Python)

Use this skill to complete setup with the Python runtime only.

## Principles

- Do the setup work directly; only ask the user for secrets or account actions.
- Keep commands Python-first: no Node tooling.
- Verify each step before moving on.

## 1) Preflight

Run:

```bash
git remote -v
python3 --version
```

If `upstream` is missing, add:

```bash
git remote add upstream https://github.com/qwibitai/nanoclaw.git
```

## 2) Run setup steps

Execute in order and parse status blocks:

```bash
python -m mini_py_nanoclaw.setup --step environment
python -m mini_py_nanoclaw.setup --step container
python -m mini_py_nanoclaw.setup --step groups
python -m mini_py_nanoclaw.setup --step register
python -m mini_py_nanoclaw.setup --step mounts
python -m mini_py_nanoclaw.setup --step service
python -m mini_py_nanoclaw.setup --step verify
```

Expected behaviors:
- `environment`: `STATUS=success` and Python 3.9+
- `container`: `success`, `docker_not_running`, or `docker_missing` (all are valid setup outcomes)
- `verify`: `STATUS=success`

If `verify` fails, rerun `groups` and `register`, then `verify`.

## 3) Channel configuration

Default channel is `local-file`.

To enable multiple channels, set:

```bash
NANOCLAW_CHANNELS=local-file,cli-stdio,webhook-http
```

For webhook channel, require token:

```bash
NANOCLAW_WEBHOOK_HOST=127.0.0.1
NANOCLAW_WEBHOOK_PORT=8787
NANOCLAW_WEBHOOK_TOKEN=<required>
NANOCLAW_WEBHOOK_OUTBOUND_URL=<optional>
```

Webhook inbound contract (`POST /inbound`):
- required: `chat_jid`, `sender`, `sender_name`, `content`
- optional: `timestamp`, `chat_name`, `is_group`

## 4) Start and validate runtime

Run service:

```bash
python -m mini_py_nanoclaw
```

Run tests:

```bash
python -m pytest tests
```

## 5) Quick recovery checklist

- Setup check: `python -m mini_py_nanoclaw.setup --step verify`
- Re-register main group: `python -m mini_py_nanoclaw.setup --step register`
- Recreate mount allowlist: `python -m mini_py_nanoclaw.setup --step mounts`
