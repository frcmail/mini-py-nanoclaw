import asyncio
import io
import json
from datetime import datetime, timezone

import pytest

from nanoclaw.app import NanoClawApp, _resolve_channel_names, build_default_main_group
from nanoclaw.channels.cli_stdio import CliStdioChannel
from nanoclaw.channels.local_file import LocalFileChannel
from nanoclaw.channels.registry import ChannelOpts
from nanoclaw.container_runner import ContainerOutput
from nanoclaw.db import NanoClawDB
from nanoclaw.types import RegisteredGroup


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_app_processes_local_and_cli_messages_in_one_poll_cycle(tmp_path) -> None:
    async def fake_agent_runner(_group, _input_data, on_process=None, on_output=None, command=None):
        output = ContainerOutput(status="success", result="Echo: stubbed response")
        if on_output is not None:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_agent_runner)
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

    for _ in range(10):
        local_outbound = list((tmp_path / "local" / "outbound").glob("*.json"))
        cli_lines = [line for line in cli_output.getvalue().splitlines() if line.strip()]
        if local_outbound and cli_lines:
            break
        await asyncio.sleep(0.02)

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

    await app.shutdown()


def test_resolve_channel_names_from_env(monkeypatch) -> None:
    monkeypatch.setenv("NANOCLAW_CHANNELS", "local-file,cli-stdio,webhook-http")
    resolved = _resolve_channel_names(["cli-stdio", "local-file", "webhook-http"])
    assert resolved == ["local-file", "cli-stdio", "webhook-http"]


@pytest.mark.asyncio
async def test_poll_channels_continues_after_channel_error() -> None:
    class BrokenChannel:
        name = "broken"

        async def poll(self) -> None:
            raise RuntimeError("boom")

    class HealthyChannel:
        def __init__(self) -> None:
            self.polled = False

        async def poll(self) -> None:
            self.polled = True

    app = NanoClawApp(db=NanoClawDB.in_memory())
    healthy = HealthyChannel()
    app.channels = [BrokenChannel(), healthy]

    await app.poll_channels()

    assert healthy.polled is True


@pytest.mark.asyncio
async def test_shutdown_continues_after_channel_disconnect_error() -> None:
    class BrokenChannel:
        name = "broken"

        async def disconnect(self) -> None:
            raise RuntimeError("disconnect failed")

    class HealthyChannel:
        def __init__(self) -> None:
            self.disconnected = False

        async def disconnect(self) -> None:
            self.disconnected = True

    app = NanoClawApp(db=NanoClawDB.in_memory())
    healthy = HealthyChannel()
    app.channels = [BrokenChannel(), healthy]

    await app.shutdown()

    assert healthy.disconnected is True
