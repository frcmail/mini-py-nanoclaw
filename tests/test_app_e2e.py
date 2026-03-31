import asyncio
import json
from datetime import datetime, timezone

import pytest

from nanoclaw.app import NanoClawApp, build_default_main_group
from nanoclaw.channels.local_file import LocalFileChannel
from nanoclaw.channels.registry import ChannelOpts
from nanoclaw.container_runner import ContainerOutput
from nanoclaw.db import NanoClawDB


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_app_end_to_end_with_local_channel(tmp_path) -> None:
    async def fake_agent_runner(_group, _input_data, on_process=None, on_output=None, command=None):
        output = ContainerOutput(status="success", result="Echo: stubbed response")
        if on_output is not None:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_agent_runner)
    app.load_state()

    jid, group = build_default_main_group()
    app.register_group(jid, group)

    channel = LocalFileChannel(
        ChannelOpts(
            on_message=app._on_inbound_message,
            on_chat_metadata=app._on_chat_metadata,
            registered_groups=lambda: app.registered_groups,
        ),
        base_dir=tmp_path / "channel",
    )
    await channel.connect()
    app.channels = [channel]

    inbound = tmp_path / "channel" / "inbound" / "inbound.json"
    inbound.write_text(
        json.dumps(
            {
                "chat_jid": "local:main",
                "sender": "local:user",
                "sender_name": "Tester",
                "content": "ping",
                "timestamp": _now_iso(),
            }
        ),
        encoding="utf-8",
    )

    await app.run_once()
    await asyncio.sleep(0.05)

    outbound_files = list((tmp_path / "channel" / "outbound").glob("*.json"))
    assert outbound_files, "expected outbound response"
    payload = json.loads(outbound_files[0].read_text(encoding="utf-8"))
    assert payload["jid"] == "local:main"
    assert payload["text"].startswith("Echo:")

    await app.shutdown()
