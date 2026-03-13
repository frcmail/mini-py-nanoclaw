import json
from datetime import datetime, timezone

import pytest

from nanoclaw.channels.local_file import LocalFileChannel
from nanoclaw.channels.registry import ChannelOpts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_local_file_channel_inbound_and_outbound(tmp_path) -> None:
    received = []
    metadata = []

    channel = LocalFileChannel(
        ChannelOpts(
            on_message=lambda jid, msg: received.append((jid, msg.content)),
            on_chat_metadata=lambda jid, ts, name, ch, is_group: metadata.append((jid, ch, is_group)),
            registered_groups=lambda: {},
        ),
        base_dir=tmp_path,
    )

    await channel.connect()

    inbound_file = tmp_path / "inbound" / "message.json"
    inbound_file.write_text(
        json.dumps(
            {
                "chat_jid": "local:main",
                "sender": "local:user",
                "sender_name": "Tester",
                "content": "hello",
                "timestamp": _now_iso(),
            }
        ),
        encoding="utf-8",
    )

    await channel.poll()

    assert received == [("local:main", "hello")]
    assert metadata[0][0] == "local:main"
    assert not inbound_file.exists()

    await channel.send_message("local:main", "ack")
    outbound_files = list((tmp_path / "outbound").glob("*.json"))
    assert len(outbound_files) == 1
    payload = json.loads(outbound_files[0].read_text(encoding="utf-8"))
    assert payload["jid"] == "local:main"
    assert payload["text"] == "ack"
