from __future__ import annotations

import asyncio
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mini_py_nanoclaw.channels.registry import ChannelOpts
from mini_py_nanoclaw.channels.webhook_http import WebhookHttpChannel


def _post(url: str, payload: dict, token: str | None = None) -> tuple[int, str]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


@pytest.mark.asyncio
async def test_webhook_http_auth_and_inbound_validation(tmp_path) -> None:
    received = []
    metadata = []
    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: received.append((jid, msg.content, msg.sender_name)),
            on_chat_metadata=lambda jid, ts, name, ch, is_group: metadata.append((jid, ch)),
            registered_groups=lambda: {},
        ),
        host="127.0.0.1",
        port=0,
        token="secret-token",
        base_dir=tmp_path,
    )

    await channel.connect()
    try:
        port = channel.bound_port
        assert port is not None
        url = f"http://127.0.0.1:{port}/inbound"

        status, _ = _post(url, {"chat_jid": "webhook:main"}, token=None)
        assert status == 401

        status, _ = _post(url, {"chat_jid": "webhook:main"}, token="secret-token")
        assert status == 400

        status, body = _post(
            url,
            {
                "chat_jid": "webhook:main",
                "sender": "u1",
                "sender_name": "Tester",
                "content": "hello webhook",
                "is_group": False,
            },
            token="secret-token",
        )
        assert status == 202
        assert "accepted" in body

        await asyncio.sleep(0.05)
        await channel.poll()

        assert received == [("webhook:main", "hello webhook", "Tester")]
        assert metadata[0] == ("webhook:main", "webhook-http")
    finally:
        await channel.disconnect()


class _OutboundSinkHandler(BaseHTTPRequestHandler):
    received_payloads = []

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length)
        _OutboundSinkHandler.received_payloads.append(json.loads(data.decode("utf-8")))
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.mark.asyncio
async def test_webhook_http_outbound_file_and_callback(tmp_path) -> None:
    _OutboundSinkHandler.received_payloads = []
    sink_server = ThreadingHTTPServer(("127.0.0.1", 0), _OutboundSinkHandler)
    sink_thread = threading.Thread(target=sink_server.serve_forever, daemon=True)
    sink_thread.start()

    sink_port = int(sink_server.server_address[1])
    outbound_url = f"http://127.0.0.1:{sink_port}/callback"

    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: None,
            on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
            registered_groups=lambda: {},
        ),
        host="127.0.0.1",
        port=0,
        token="token",
        outbound_url=outbound_url,
        base_dir=tmp_path,
    )

    try:
        await channel.connect()
        await channel.send_message("webhook:main", "reply")

        outbound_files = list((tmp_path / "outbound").glob("*.json"))
        assert len(outbound_files) == 1

        for _ in range(20):
            if _OutboundSinkHandler.received_payloads:
                break
            await asyncio.sleep(0.05)

        assert _OutboundSinkHandler.received_payloads
        assert _OutboundSinkHandler.received_payloads[0]["jid"] == "webhook:main"
        assert _OutboundSinkHandler.received_payloads[0]["text"] == "reply"
    finally:
        await channel.disconnect()
        sink_server.shutdown()
        sink_server.server_close()
        sink_thread.join(timeout=1)
