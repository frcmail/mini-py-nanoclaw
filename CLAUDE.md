# NanoClaw

Personal Claude assistant. See [README.md](README.md) and [README_py.md](README_py.md) for runtime and setup.

## Quick Context

Single Python process with a pluggable channel registry. Core channels include `local-file`, `cli-stdio`, and `webhook-http`. Messages route to Python container runner/agent runtime with per-group filesystem and memory isolation.

## Key Files

| File | Purpose |
|------|---------|
| `mini_py_nanoclaw/app.py` | Orchestrator: state, polling loop, agent invocation |
| `mini_py_nanoclaw/channels/registry.py` | Channel registry |
| `mini_py_nanoclaw/ipc.py` | IPC watcher and task processing |
| `mini_py_nanoclaw/router.py` | Message formatting and outbound routing |
| `mini_py_nanoclaw/config.py` | Trigger pattern, paths, intervals |
| `mini_py_nanoclaw/container_runner.py` | Agent runner interface + output marker parsing |
| `mini_py_nanoclaw/task_scheduler.py` | Scheduled task engine |
| `mini_py_nanoclaw/db.py` | SQLite operations |
| `mini_py_nanoclaw/setup/` | Python setup steps and status output |
| `mini_py_nanoclaw/agent_runner.py` | Container-side Python agent runtime |
| `mini_py_nanoclaw/mcp_stdio.py` | Container-side Python MCP stdio service |
| `groups/{name}/CLAUDE.md` | Per-group memory (isolated) |
| `container/skills/agent-browser.md` | Browser automation tool (available to all agents via Bash) |

## Skills

| Skill | When to Use |
|-------|-------------|
| `/setup` | First-time installation, authentication, service configuration |
| `/customize` | Adding channels, integrations, changing behavior |
| `/debug` | Container issues, logs, troubleshooting |
| `/update-nanoclaw` | Bring upstream NanoClaw updates into a customized install |
| `/update-skills` | Refresh core skill instructions and alignment |

## Development

Run commands directly—don't tell the user to run them.

```bash
python -m mini_py_nanoclaw                        # Start service
python -m mini_py_nanoclaw.setup --step verify    # Run setup verification step
python -m pytest tests_py                         # Run Python tests
./container/build.sh # Rebuild agent container
```

Service management:
```bash
# macOS (launchd)
launchctl load ~/Library/LaunchAgents/com.nanoclaw.plist
launchctl unload ~/Library/LaunchAgents/com.nanoclaw.plist
launchctl kickstart -k gui/$(id -u)/com.nanoclaw  # restart

# Linux (systemd)
systemctl --user start nanoclaw
systemctl --user stop nanoclaw
systemctl --user restart nanoclaw
```

## Troubleshooting

**Webhook channel returns 401:** set `NANOCLAW_WEBHOOK_TOKEN` and send `Authorization: Bearer <token>` on `POST /inbound`.

**No channel receives messages:** verify `NANOCLAW_CHANNELS` (comma-separated), for example `local-file,cli-stdio,webhook-http`.

## Container Build Cache

The container buildkit caches the build context aggressively. `--no-cache` alone does NOT invalidate COPY steps — the builder's volume retains stale files. To force a truly clean rebuild, prune the builder then re-run `./container/build.sh`.
