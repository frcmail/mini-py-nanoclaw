from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
import uuid
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..config import DATA_DIR
from ..types import NewMessage
from .common import atomic_write_json, ensure_dirs, utc_now_iso
from .registry import ChannelOpts, register_channel


class WebhookHttpChannel:
    """HTTP webhook channel that accepts inbound JSON and emits outbound messages."""

    name = "webhook-http"

    def __init__(
        self,
        opts: ChannelOpts,
        host: str | None = None,
        port: int | None = None,
        token: str | None = None,
        outbound_url: str | None = None,
        base_dir: Path | None = None,
    ) -> None:
        self._opts = opts
        self._host = host or os.getenv("NANOCLAW_WEBHOOK_HOST", "127.0.0.1")
        self._port = int(port if port is not None else os.getenv("NANOCLAW_WEBHOOK_PORT", "8787"))
        self._token = token if token is not None else os.getenv("NANOCLAW_WEBHOOK_TOKEN")
        self._outbound_url = outbound_url if outbound_url is not None else os.getenv("NANOCLAW_WEBHOOK_OUTBOUND_URL")
        self._base_dir = base_dir or (DATA_DIR / "channels" / "webhook")
        self._outbound_dir = self._base_dir / "outbound"

        self._connected = False
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._filename_seq = 0
        self._filename_lock = threading.Lock()

    @property
    def bound_port(self) -> int | None:
        if self._server is None:
            return None
        return int(self._server.server_address[1])

    async def connect(self) -> None:
        if not self._token:
            raise ValueError("NANOCLAW_WEBHOOK_TOKEN is required for webhook-http channel")

        ensure_dirs((self._outbound_dir,))

        handler = self._build_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._server_thread = threading.Thread(target=self._server.serve_forever, name="webhook-http-server", daemon=True)
        self._server_thread.start()
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._server_thread is not None:
            self._server_thread.join(timeout=1)
            self._server_thread = None

    def is_connected(self) -> bool:
        return self._connected

    def owns_jid(self, jid: str) -> bool:
        return jid.startswith("webhook:")

    async def send_message(self, jid: str, text: str) -> None:
        payload = {
            "jid": jid,
            "text": text,
            "timestamp": utc_now_iso(),
        }
        self._write_outbound_file(payload)

        if self._outbound_url:
            await asyncio.to_thread(self._post_outbound, payload)

    async def poll(self) -> None:
        if not self._connected:
            return

        while True:
            try:
                data = self._queue.get_nowait()
            except queue.Empty:
                break

            self._opts.on_chat_metadata(
                data["chat_jid"],
                data["timestamp"],
                data.get("chat_name"),
                "webhook-http",
                bool(data.get("is_group", True)),
            )
            self._opts.on_message(
                data["chat_jid"],
                NewMessage(
                    id=str(data.get("id") or uuid.uuid4().hex),
                    chat_jid=data["chat_jid"],
                    sender=data["sender"],
                    sender_name=data["sender_name"],
                    content=data["content"],
                    timestamp=data["timestamp"],
                    is_from_me=False,
                    is_bot_message=False,
                ),
            )

    def _build_handler(self):
        channel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format, *_args):
                return

            def do_POST(self):
                if self.path != "/inbound":
                    _write_json(self, 404, {"error": "not_found"})
                    return

                auth = self.headers.get("Authorization", "")
                if auth != f"Bearer {channel._token}":
                    _write_json(self, 401, {"error": "unauthorized"})
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    _write_json(self, 400, {"error": "invalid_content_length"})
                    return

                try:
                    body = self.rfile.read(content_length)
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    _write_json(self, 400, {"error": "invalid_json"})
                    return

                parsed = _validate_payload(payload)
                if parsed is None:
                    _write_json(self, 400, {"error": "invalid_payload"})
                    return

                channel._queue.put(parsed)
                _write_json(self, 202, {"status": "accepted"})

        return Handler

    def _write_outbound_file(self, payload: dict) -> None:
        with self._filename_lock:
            self._filename_seq += 1
            seq = self._filename_seq
        filename = f"{time.time_ns():020d}-{seq:08d}.json"
        path = self._outbound_dir / filename
        atomic_write_json(path, payload)

    def _post_outbound(self, payload: dict) -> None:
        if not self._outbound_url:
            return

        req = urllib.request.Request(
            self._outbound_url,
            data=json.dumps(payload, ensure_ascii=True).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                _ = resp.read()
        except Exception:
            # Local-use channel: ignore outbound callback errors in v1.
            return


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _validate_payload(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None

    required = ["chat_jid", "sender", "sender_name", "content"]
    if not all(isinstance(payload.get(key), str) for key in required):
        return None

    content = str(payload.get("content") or "").strip()
    if not content:
        return None

    timestamp = payload.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        timestamp = utc_now_iso()

    return {
        "id": payload.get("id"),
        "chat_jid": str(payload["chat_jid"]),
        "sender": str(payload["sender"]),
        "sender_name": str(payload["sender_name"]),
        "content": content,
        "timestamp": timestamp,
        "chat_name": payload.get("chat_name"),
        "is_group": bool(payload.get("is_group", True)),
    }


def create_webhook_http_channel(opts: ChannelOpts) -> WebhookHttpChannel:
    return WebhookHttpChannel(opts)


register_channel("webhook-http", create_webhook_http_channel)
