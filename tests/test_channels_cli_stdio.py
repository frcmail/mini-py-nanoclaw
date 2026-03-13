import asyncio
import io
import json

import pytest

from nanoclaw.channels.cli_stdio import CliStdioChannel
from nanoclaw.channels.registry import ChannelOpts


@pytest.mark.asyncio
async def test_cli_stdio_inbound_parse_and_outbound_print() -> None:
    incoming = io.StringIO(
        "\n"
        "plain text message\n"
        '{"chat_jid":"cli:main","sender":"cli:user","sender_name":"Tester","content":"json message"}\n'
        '{"content":"   "}\n'
    )
    outgoing = io.StringIO()

    received = []
    metadata = []
    channel = CliStdioChannel(
        ChannelOpts(
            on_message=lambda jid, msg: received.append((jid, msg.content)),
            on_chat_metadata=lambda jid, ts, name, ch, is_group: metadata.append((jid, ch)),
            registered_groups=lambda: {},
        ),
        input_stream=incoming,
        output_stream=outgoing,
    )

    await channel.connect()
    await asyncio.sleep(0.05)
    await channel.poll()

    assert received == [("cli:main", "plain text message"), ("cli:main", "json message")]
    assert metadata[0] == ("cli:main", "cli-stdio")

    await channel.send_message("cli:main", "reply")
    line = outgoing.getvalue().strip()
    payload = json.loads(line)
    assert payload["type"] == "outbound"
    assert payload["jid"] == "cli:main"
    assert payload["text"] == "reply"
