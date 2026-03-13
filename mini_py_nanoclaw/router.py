from __future__ import annotations

import html
import re
from collections.abc import Iterable

from .timezone import format_local_time
from .types import Channel, NewMessage

_INTERNAL_RE = re.compile(r"<internal>[\s\S]*?</internal>", re.IGNORECASE)


def escape_xml(value: str) -> str:
    if not value:
        return ""
    return html.escape(value, quote=True)


def format_messages(messages: list[NewMessage], timezone: str) -> str:
    lines = []
    for message in messages:
        display_time = format_local_time(message.timestamp, timezone)
        lines.append(
            f'<message sender="{escape_xml(message.sender_name)}" '
            f'time="{escape_xml(display_time)}">{escape_xml(message.content)}</message>'
        )
    header = f'<context timezone="{escape_xml(timezone)}" />\n'
    body = "\n".join(lines)
    return f"{header}<messages>\n{body}\n</messages>"


def strip_internal_tags(text: str) -> str:
    return _INTERNAL_RE.sub("", text).strip()


def format_outbound(raw_text: str) -> str:
    return strip_internal_tags(raw_text)


async def route_outbound(channels: Iterable[Channel], jid: str, text: str) -> None:
    channel = find_channel(channels, jid)
    if channel is None:
        raise ValueError(f"No channel for JID: {jid}")
    await channel.send_message(jid, text)


def find_channel(channels: Iterable[Channel], jid: str) -> Channel | None:
    for channel in channels:
        if channel.owns_jid(jid):
            return channel
    return None
