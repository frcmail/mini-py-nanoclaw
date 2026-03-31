from __future__ import annotations

import asyncio
import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import nanoclaw.channels.webhook_http as webhook_http_module
from nanoclaw.channels.registry import ChannelOpts
from nanoclaw.channels.webhook_http import WebhookHttpChannel


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


def _post_raw(url: str, body: bytes, token: str | None = None) -> tuple[int, str]:
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
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


@pytest.mark.asyncio
async def test_webhook_http_rejects_invalid_json_body(tmp_path) -> None:
    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: None,
            on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
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

        status, body = _post_raw(url, b"{not-json", token="secret-token")
        assert status == 400
        assert "invalid_json" in body
    finally:
        await channel.disconnect()


@pytest.mark.asyncio
async def test_webhook_http_rejects_oversized_payload(tmp_path) -> None:
    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: None,
            on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
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

        # Send a small body but with a Content-Length claiming over 1 MB
        small_body = b"{}"
        req = urllib.request.Request(
            url,
            data=small_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer secret-token",
                "Content-Length": str(2 * 1024 * 1024),  # 2 MB claim
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            body = exc.read().decode("utf-8")

        assert status == 413
        assert "payload_too_large" in body
    finally:
        await channel.disconnect()


@pytest.mark.asyncio
async def test_webhook_http_rejects_whitespace_token(tmp_path) -> None:
    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: None,
            on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
            registered_groups=lambda: {},
        ),
        host="127.0.0.1",
        port=0,
        token="   ",
        base_dir=tmp_path,
    )

    with pytest.raises(ValueError, match="NANOCLAW_WEBHOOK_TOKEN is required"):
        await channel.connect()


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


def test_webhook_http_logs_outbound_callback_failure(tmp_path, monkeypatch) -> None:
    channel = WebhookHttpChannel(
        ChannelOpts(
            on_message=lambda jid, msg: None,
            on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
            registered_groups=lambda: {},
        ),
        host="127.0.0.1",
        port=0,
        token="token",
        outbound_url="http://127.0.0.1:9/callback",
        base_dir=tmp_path,
    )

    warnings: list[str] = []

    def _raise_url_error(*_args, **_kwargs):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(webhook_http_module.urllib.request, "urlopen", _raise_url_error)
    monkeypatch.setattr(webhook_http_module.logger, "warning", lambda msg, *args: warnings.append(msg % args))

    channel._post_outbound({"jid": "webhook:main", "text": "reply"})

    assert len(warnings) == 1
    assert "webhook outbound callback failed" in warnings[0]


def test_webhook_channel_rejects_invalid_port() -> None:
    with pytest.raises(ValueError, match="webhook port out of range"):
        WebhookHttpChannel(
            ChannelOpts(
                on_message=lambda jid, msg: None,
                on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
                registered_groups=lambda: {},
            ),
            port=-1,
            token="tok",
        )

    with pytest.raises(ValueError, match="webhook port out of range"):
        WebhookHttpChannel(
            ChannelOpts(
                on_message=lambda jid, msg: None,
                on_chat_metadata=lambda jid, ts, name, ch, is_group: None,
                registered_groups=lambda: {},
            ),
            port=70000,
            token="tok",
        )
