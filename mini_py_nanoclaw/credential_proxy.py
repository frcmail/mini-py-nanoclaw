from __future__ import annotations

import threading
import urllib.parse
import urllib.request
import os
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import PROXY_BIND_HOST
from .env import read_env_file
from .logger import logger


@dataclass
class CredentialProxyServer:
    server: ThreadingHTTPServer
    thread: threading.Thread

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def detect_auth_mode() -> str:
    secrets = read_env_file(["ANTHROPIC_API_KEY"])  # pragma: no cover - simple accessor
    api_key = os.getenv("ANTHROPIC_API_KEY") or secrets.get("ANTHROPIC_API_KEY")
    return "api-key" if api_key else "oauth"


def start_credential_proxy(port: int, host: str = PROXY_BIND_HOST) -> CredentialProxyServer:
    secrets = read_env_file(
        ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"]
    )

    api_key = os.getenv("ANTHROPIC_API_KEY") or secrets.get("ANTHROPIC_API_KEY")
    oauth_token = (
        os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or secrets.get("CLAUDE_CODE_OAUTH_TOKEN")
        or secrets.get("ANTHROPIC_AUTH_TOKEN")
    )
    upstream_base = os.getenv("ANTHROPIC_BASE_URL") or secrets.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
    auth_mode = "api-key" if api_key else "oauth"

    class ProxyHandler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args) -> None:
            return

        def _proxy(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            upstream = upstream_base.rstrip("/") + self.path

            headers = {k: v for k, v in self.headers.items()}
            headers["Host"] = urllib.parse.urlparse(upstream).netloc
            headers.pop("Connection", None)
            headers.pop("Keep-Alive", None)
            headers.pop("Transfer-Encoding", None)

            if auth_mode == "api-key":
                headers.pop("x-api-key", None)
                headers["x-api-key"] = api_key or ""
            elif "Authorization" in headers and oauth_token:
                headers["Authorization"] = f"Bearer {oauth_token}"

            request = urllib.request.Request(
                upstream,
                data=body if body else None,
                method=self.command,
                headers=headers,
            )

            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    response_body = response.read()
                    self.send_response(response.status)
                    for key, value in response.headers.items():
                        if key.lower() in {"connection", "transfer-encoding"}:
                            continue
                        self.send_header(key, value)
                    self.end_headers()
                    self.wfile.write(response_body)
            except Exception as exc:
                logger.error("credential proxy upstream error: %s", exc)
                body = b"Bad Gateway"
                self.send_response(502)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def do_GET(self) -> None:  # pragma: no cover - simple proxy pass-through
            self._proxy()

        def do_POST(self) -> None:
            self._proxy()

        def do_PUT(self) -> None:  # pragma: no cover
            self._proxy()

        def do_DELETE(self) -> None:  # pragma: no cover
            self._proxy()

    server = ThreadingHTTPServer((host, port), ProxyHandler)
    thread = threading.Thread(target=server.serve_forever, name="credential-proxy", daemon=True)
    thread.start()
    logger.info("credential proxy started host=%s port=%s auth_mode=%s", host, port, auth_mode)
    return CredentialProxyServer(server=server, thread=thread)
