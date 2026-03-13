import asyncio
import io
import json
from datetime import datetime, timezone

import pytest

from mini_py_nanoclaw.app import NanoClawApp, _resolve_channel_names, build_default_main_group
from mini_py_nanoclaw.channels.cli_stdio import CliStdioChannel
from mini_py_nanoclaw.channels.local_file import LocalFileChannel
from mini_py_nanoclaw.channels.registry import ChannelOpts
from mini_py_nanoclaw.db import NanoClawDB
from mini_py_nanoclaw.types import RegisteredGroup


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_app_processes_local_and_cli_messages_in_one_poll_cycle(tmp_path) -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    app.load_state()

    main_jid, main_group = build_default_main_group()
    app.register_group(main_jid, main_group)

    cli_group = RegisteredGroup(
        name="CLI Group",
        folder="cli",
        trigger="@Andy",
        added_at=_now_iso(),
        requires_trigger=False,
        is_main=False,
    )
    app.register_group("cli:main", cli_group)

    local_channel = LocalFileChannel(
        ChannelOpts(
            on_message=app._on_inbound_message,
            on_chat_metadata=app._on_chat_metadata,
            registered_groups=lambda: app.registered_groups,
        ),
        base_dir=tmp_path / "local",
    )

    cli_input = io.StringIO('{"chat_jid":"cli:main","sender":"cli:user","sender_name":"CLI","content":"ping cli"}\n')
    cli_output = io.StringIO()
    cli_channel = CliStdioChannel(
        ChannelOpts(
            on_message=app._on_inbound_message,
            on_chat_metadata=app._on_chat_metadata,
            registered_groups=lambda: app.registered_groups,
        ),
        input_stream=cli_input,
        output_stream=cli_output,
    )

    await local_channel.connect()
    await cli_channel.connect()
    app.channels = [local_channel, cli_channel]

    inbound = tmp_path / "local" / "inbound" / "one.json"
    inbound.write_text(
        json.dumps(
            {
                "chat_jid": "local:main",
                "sender": "local:user",
                "sender_name": "Local",
                "content": "ping local",
                "timestamp": _now_iso(),
            }
        ),
        encoding="utf-8",
    )

    await app.run_once()

    for _ in range(30):
        local_outbound = list((tmp_path / "local" / "outbound").glob("*.json"))
        cli_lines = [line for line in cli_output.getvalue().splitlines() if line.strip()]
        if local_outbound and cli_lines:
            break
        await asyncio.sleep(0.05)

    local_outbound = list((tmp_path / "local" / "outbound").glob("*.json"))
    assert local_outbound, "expected local-file outbound response"

    local_payload = json.loads(local_outbound[0].read_text(encoding="utf-8"))
    assert local_payload["jid"] == "local:main"
    assert local_payload["text"].startswith("Echo:")

    cli_lines = [line for line in cli_output.getvalue().splitlines() if line.strip()]
    assert cli_lines, "expected cli-stdio outbound response"
    cli_payload = json.loads(cli_lines[0])
    assert cli_payload["jid"] == "cli:main"
    assert cli_payload["text"].startswith("Echo:")


def test_resolve_channel_names_from_env(monkeypatch) -> None:
    monkeypatch.setenv("NANOCLAW_CHANNELS", "local-file,cli-stdio,webhook-http")
    resolved = _resolve_channel_names(["cli-stdio", "local-file", "webhook-http"])
    assert resolved == ["local-file", "cli-stdio", "webhook-http"]
