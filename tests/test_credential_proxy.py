import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from nanoclaw import credential_proxy


class _UpstreamHandler(BaseHTTPRequestHandler):
    captured_headers = {}

    def log_message(self, _format, *_args):
        return

    def do_POST(self):
        _UpstreamHandler.captured_headers = {k.lower(): v for k, v in self.headers.items()}
        body = json.dumps({"ok": True}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_credential_proxy_injects_api_key(monkeypatch):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()

    upstream_port = upstream.server_address[1]

    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {
            "ANTHROPIC_API_KEY": "real-key",
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{upstream_port}",
        },
    )

    proxy = credential_proxy.start_credential_proxy(0, "127.0.0.1")
    proxy_port = proxy.server.server_address[1]

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/messages",
            data=b"{}",
            headers={"Content-Type": "application/json", "x-api-key": "placeholder"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            assert payload["ok"] is True

        assert _UpstreamHandler.captured_headers.get("x-api-key") == "real-key"
    finally:
        proxy.close()
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=1)


def test_detect_auth_mode_api_key(monkeypatch):
    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {"ANTHROPIC_API_KEY": "sk-key"},
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-key")
    assert credential_proxy.detect_auth_mode() == "api-key"


def test_detect_auth_mode_oauth(monkeypatch):
    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {},
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert credential_proxy.detect_auth_mode() == "oauth"


def test_proxy_oauth_token_injected(monkeypatch):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    upstream_port = upstream.server_address[1]

    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {
            "CLAUDE_CODE_OAUTH_TOKEN": "oauth-tok-123",
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{upstream_port}",
        },
    )
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)

    proxy = credential_proxy.start_credential_proxy(0, "127.0.0.1")
    proxy_port = proxy.server.server_address[1]

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/messages",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200

        auth = _UpstreamHandler.captured_headers.get("authorization", "")
        assert auth == "Bearer oauth-tok-123"
        assert "x-api-key" not in _UpstreamHandler.captured_headers
    finally:
        proxy.close()
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=1)


def test_proxy_upstream_error_returns_502(monkeypatch):
    # Start proxy pointing at a port with no server
    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {
            "ANTHROPIC_API_KEY": "key",
            "ANTHROPIC_BASE_URL": "http://127.0.0.1:1",  # nothing listening
        },
    )

    proxy = credential_proxy.start_credential_proxy(0, "127.0.0.1")
    proxy_port = proxy.server.server_address[1]

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/messages",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTPError")
        except urllib.error.HTTPError as exc:
            assert exc.code == 502
    finally:
        proxy.close()


def test_proxy_filters_disallowed_headers(monkeypatch):
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    upstream_port = upstream.server_address[1]

    monkeypatch.setattr(
        credential_proxy,
        "read_env_file",
        lambda _keys: {
            "ANTHROPIC_API_KEY": "key",
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{upstream_port}",
        },
    )

    proxy = credential_proxy.start_credential_proxy(0, "127.0.0.1")
    proxy_port = proxy.server.server_address[1]

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/messages",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-Custom-Evil": "should-be-filtered",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            assert resp.status == 200

        assert "x-custom-evil" not in _UpstreamHandler.captured_headers
    finally:
        proxy.close()
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=1)
