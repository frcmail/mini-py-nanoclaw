from __future__ import annotations

import os
import platform
import re
import socket
from datetime import datetime
from pathlib import Path

from .env import read_env_file


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


env_config = read_env_file(["ASSISTANT_NAME", "ASSISTANT_HAS_OWN_NUMBER"])

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME") or env_config.get("ASSISTANT_NAME") or "Andy"
ASSISTANT_HAS_OWN_NUMBER = _as_bool(
    os.getenv("ASSISTANT_HAS_OWN_NUMBER") or env_config.get("ASSISTANT_HAS_OWN_NUMBER"),
    default=False,
)

POLL_INTERVAL = 2000
SCHEDULER_POLL_INTERVAL = 60000
IPC_POLL_INTERVAL = 1000

PROJECT_ROOT = Path.cwd()
HOME_DIR = Path.home()

MOUNT_ALLOWLIST_PATH = HOME_DIR / ".config" / "nanoclaw" / "mount-allowlist.json"
SENDER_ALLOWLIST_PATH = HOME_DIR / ".config" / "nanoclaw" / "sender-allowlist.json"
STORE_DIR = PROJECT_ROOT / "store"
GROUPS_DIR = PROJECT_ROOT / "groups"
DATA_DIR = PROJECT_ROOT / "data"

CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "nanoclaw-agent:latest")
CONTAINER_TIMEOUT = _as_int(os.getenv("CONTAINER_TIMEOUT"), 1800000)
CONTAINER_MAX_OUTPUT_SIZE = _as_int(os.getenv("CONTAINER_MAX_OUTPUT_SIZE"), 10485760)
CREDENTIAL_PROXY_PORT = _as_int(os.getenv("CREDENTIAL_PROXY_PORT"), 3001)
IDLE_TIMEOUT = _as_int(os.getenv("IDLE_TIMEOUT"), 1800000)
MAX_CONCURRENT_CONTAINERS = max(1, _as_int(os.getenv("MAX_CONCURRENT_CONTAINERS"), 5))
CONTAINER_RUNTIME_BIN = os.getenv("CONTAINER_RUNTIME_BIN", "docker")
CONTAINER_HOST_GATEWAY = os.getenv("CONTAINER_HOST_GATEWAY", "host.docker.internal")

TRIGGER_PATTERN = re.compile(rf"^@{re.escape(ASSISTANT_NAME)}\\b", re.IGNORECASE)
TIMEZONE = os.getenv("TZ") or str(datetime.now().astimezone().tzinfo or "UTC")


def _detect_proxy_bind_host() -> str:
    env_override = os.getenv("CREDENTIAL_PROXY_HOST")
    if env_override:
        return env_override

    if platform.system().lower() == "darwin":
        return "127.0.0.1"

    if Path("/proc/sys/fs/binfmt_misc/WSLInterop").exists():
        return "127.0.0.1"

    # Best effort for Linux: bind docker bridge if available.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            _ = s.getsockname()[0]
    except OSError:
        pass
    return "0.0.0.0"


PROXY_BIND_HOST = _detect_proxy_bind_host()
