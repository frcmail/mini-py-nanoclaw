from __future__ import annotations

import os
import platform
import re
import socket
from datetime import datetime
from functools import lru_cache
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


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


env_config = read_env_file(["ASSISTANT_NAME", "ASSISTANT_HAS_OWN_NUMBER"])

ASSISTANT_NAME = os.getenv("ASSISTANT_NAME") or env_config.get("ASSISTANT_NAME") or "Andy"
if not re.fullmatch(r"[A-Za-z0-9 _-]{1,64}", ASSISTANT_NAME):
    ASSISTANT_NAME = "Andy"
ASSISTANT_HAS_OWN_NUMBER = _as_bool(
    os.getenv("ASSISTANT_HAS_OWN_NUMBER") or env_config.get("ASSISTANT_HAS_OWN_NUMBER"),
    default=False,
)

POLL_INTERVAL = 2000
SCHEDULER_POLL_INTERVAL = 60000
IPC_POLL_INTERVAL = 1000

def _resolve_nanoclaw_home() -> Path:
    configured = os.getenv("NANOCLAW_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".nanoclaw").resolve()


NANOCLAW_HOME = _resolve_nanoclaw_home()
PROJECT_ROOT = NANOCLAW_HOME
HOME_DIR = Path.home()

MOUNT_ALLOWLIST_PATH = HOME_DIR / ".config" / "nanoclaw" / "mount-allowlist.json"
SENDER_ALLOWLIST_PATH = HOME_DIR / ".config" / "nanoclaw" / "sender-allowlist.json"
STORE_DIR = PROJECT_ROOT / "store"
GROUPS_DIR = PROJECT_ROOT / "groups"
DATA_DIR = PROJECT_ROOT / "data"

CONTAINER_IMAGE = os.getenv("CONTAINER_IMAGE", "nanoclaw-agent:latest")
CONTAINER_TIMEOUT = _clamp_int(_as_int(os.getenv("CONTAINER_TIMEOUT"), 1800000), 1000, 3600000)
CONTAINER_MAX_OUTPUT_SIZE = _as_int(os.getenv("CONTAINER_MAX_OUTPUT_SIZE"), 10485760)
CREDENTIAL_PROXY_PORT = _as_int(os.getenv("CREDENTIAL_PROXY_PORT"), 3001)
IDLE_TIMEOUT = _as_int(os.getenv("IDLE_TIMEOUT"), 1800000)
MAX_CONCURRENT_CONTAINERS = max(1, _as_int(os.getenv("MAX_CONCURRENT_CONTAINERS"), 5))
CONTAINER_RUNTIME_BIN = os.getenv("CONTAINER_RUNTIME_BIN", "docker")
CONTAINER_HOST_GATEWAY = os.getenv("CONTAINER_HOST_GATEWAY", "host.docker.internal")
REQUIRE_CONTAINER_RUNTIME = _as_bool(
    os.getenv("NANOCLAW_REQUIRE_CONTAINER_RUNTIME"),
    default=False,
)

TRIGGER_PATTERN = re.compile(
    rf"^@{re.escape(ASSISTANT_NAME)}\b", re.IGNORECASE
) if ASSISTANT_NAME else re.compile(r"(?!)")
TIMEZONE = os.getenv("TZ") or str(datetime.now().astimezone().tzinfo or "UTC")


@lru_cache(maxsize=1)
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
    return "0.0.0.0"  # noqa: S104


PROXY_BIND_HOST = _detect_proxy_bind_host()
