from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import DATA_DIR
from ..types import NewMessage
from .registry import ChannelOpts, register_channel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LocalFileChannel:
    """Local development channel using filesystem inbox/outbox JSON files."""

    name = "local-file"

    def __init__(self, opts: ChannelOpts, base_dir: Path | None = None) -> None:
        self._opts = opts
        self._base_dir = base_dir or (DATA_DIR / "channels" / "local-file")
        self._inbound_dir = self._base_dir / "inbound"
        self._outbound_dir = self._base_dir / "outbound"
        self._connected = False

    async def connect(self) -> None:
        self._inbound_dir.mkdir(parents=True, exist_ok=True)
        self._outbound_dir.mkdir(parents=True, exist_ok=True)
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def owns_jid(self, jid: str) -> bool:
        return jid.startswith("local:")

    async def send_message(self, jid: str, text: str) -> None:
        payload = {
            "jid": jid,
            "text": text,
            "timestamp": _now_iso(),
        }
        filename = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid.uuid4().hex[:8]}.json"
        path = self._outbound_dir / filename
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        tmp.rename(path)

    async def poll(self) -> None:
        if not self._connected:
            return

        files = sorted(self._inbound_dir.glob("*.json"))
        for file_path in files:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                file_path.unlink(missing_ok=True)
                continue

            chat_jid = str(data.get("chat_jid") or "local:main")
            timestamp = str(data.get("timestamp") or _now_iso())
            sender = str(data.get("sender") or "local:user")
            sender_name = str(data.get("sender_name") or "User")
            content = str(data.get("content") or "")
            if not content.strip():
                file_path.unlink(missing_ok=True)
                continue

            self._opts.on_chat_metadata(
                chat_jid,
                timestamp,
                data.get("chat_name"),
                "local-file",
                bool(data.get("is_group", True)),
            )

            msg = NewMessage(
                id=str(data.get("id") or uuid.uuid4().hex),
                chat_jid=chat_jid,
                sender=sender,
                sender_name=sender_name,
                content=content,
                timestamp=timestamp,
                is_from_me=bool(data.get("is_from_me", False)),
                is_bot_message=bool(data.get("is_bot_message", False)),
            )
            self._opts.on_message(chat_jid, msg)
            file_path.unlink(missing_ok=True)


def create_local_file_channel(opts: ChannelOpts) -> LocalFileChannel:
    return LocalFileChannel(opts)


register_channel("local-file", create_local_file_channel)
