from __future__ import annotations

import json
import queue
import sys
import threading
import time
import uuid
from typing import TextIO

from ..types import NewMessage
from .common import utc_now_iso
from .registry import ChannelOpts, register_channel


class CliStdioChannel:
    """Simple stdin/stdout channel for local development."""

    name = "cli-stdio"

    def __init__(
        self,
        opts: ChannelOpts,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        self._opts = opts
        self._input_stream = input_stream or sys.stdin
        self._output_stream = output_stream or sys.stdout
        self._connected = False
        self._stop_event = threading.Event()
        self._queue: queue.Queue[str] = queue.Queue()
        self._reader_thread: threading.Thread | None = None

    async def connect(self) -> None:
        self._connected = True
        self._stop_event.clear()
        self._reader_thread = threading.Thread(target=self._read_loop, name="cli-stdio-reader", daemon=True)
        self._reader_thread.start()

    async def disconnect(self) -> None:
        self._connected = False
        self._stop_event.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2)

    def is_connected(self) -> bool:
        return self._connected

    def owns_jid(self, jid: str) -> bool:
        return jid.startswith("cli:")

    async def send_message(self, jid: str, text: str) -> None:
        payload = {
            "type": "outbound",
            "jid": jid,
            "text": text,
            "timestamp": utc_now_iso(),
        }
        self._output_stream.write(json.dumps(payload, ensure_ascii=True) + "\n")
        flush = getattr(self._output_stream, "flush", None)
        if callable(flush):
            flush()

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                line = self._input_stream.readline()
            except OSError:
                break
            if line == "":
                # Interactive stdin may temporarily have no completed line.
                if self._input_stream is sys.stdin:
                    time.sleep(0.05)
                    continue
                break
            self._queue.put(line.rstrip("\n"))

    async def poll(self) -> None:
        if not self._connected:
            return

        while True:
            try:
                raw = self._queue.get_nowait()
            except queue.Empty:
                break

            payload = self._parse_line(raw)
            if payload is None:
                continue

            self._opts.on_chat_metadata(
                payload["chat_jid"],
                payload["timestamp"],
                payload.get("chat_name"),
                "cli-stdio",
                bool(payload.get("is_group", False)),
            )
            self._opts.on_message(
                payload["chat_jid"],
                NewMessage(
                    id=str(payload.get("id") or uuid.uuid4().hex),
                    chat_jid=payload["chat_jid"],
                    sender=payload["sender"],
                    sender_name=payload["sender_name"],
                    content=payload["content"],
                    timestamp=payload["timestamp"],
                    is_from_me=bool(payload.get("is_from_me", False)),
                    is_bot_message=bool(payload.get("is_bot_message", False)),
                ),
            )

    def _parse_line(self, raw: str) -> dict | None:
        stripped = raw.strip()
        if not stripped:
            return None

        parsed: dict
        try:
            decoded = json.loads(stripped)
            if isinstance(decoded, str):
                parsed = {"content": decoded}
            elif isinstance(decoded, dict):
                parsed = decoded
            else:
                return None
        except json.JSONDecodeError:
            parsed = {"content": stripped}

        content = str(parsed.get("content") or "").strip()
        if not content:
            return None

        return {
            "id": parsed.get("id"),
            "chat_jid": str(parsed.get("chat_jid") or "cli:main"),
            "sender": str(parsed.get("sender") or "cli:user"),
            "sender_name": str(parsed.get("sender_name") or "CLI User"),
            "chat_name": parsed.get("chat_name"),
            "is_group": parsed.get("is_group", False),
            "content": content,
            "timestamp": str(parsed.get("timestamp") or utc_now_iso()),
            "is_from_me": bool(parsed.get("is_from_me", False)),
            "is_bot_message": bool(parsed.get("is_bot_message", False)),
        }


def create_cli_stdio_channel(opts: ChannelOpts) -> CliStdioChannel:
    return CliStdioChannel(opts)


register_channel("cli-stdio", create_cli_stdio_channel)
