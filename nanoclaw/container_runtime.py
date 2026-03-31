from __future__ import annotations

import subprocess
import threading
import time

from .config import CONTAINER_RUNTIME_BIN
from .logger import logger

_OPTIONAL_RUNTIME_WARNING_EMITTED = False
_runtime_check_lock = threading.Lock()
_runtime_check_result: bool | None = None
_runtime_check_time: float = 0.0
_RUNTIME_CHECK_TTL = 30.0  # seconds


def _runtime_error_message(exc: Exception) -> str:
    return f"{CONTAINER_RUNTIME_BIN} runtime check failed: {exc}"


def ensure_container_runtime_running(required: bool = True) -> bool:
    global _OPTIONAL_RUNTIME_WARNING_EMITTED, _runtime_check_result, _runtime_check_time

    with _runtime_check_lock:
        now = time.monotonic()
        if _runtime_check_result is not None and (now - _runtime_check_time) < _RUNTIME_CHECK_TTL:
            if _runtime_check_result:
                return True
            # Cached failure: still need to handle required vs optional below.
            if not required and _OPTIONAL_RUNTIME_WARNING_EMITTED:
                return False

    try:
        subprocess.run(
            [CONTAINER_RUNTIME_BIN, "info"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        with _runtime_check_lock:
            _runtime_check_result = True
            _runtime_check_time = time.monotonic()
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        with _runtime_check_lock:
            _runtime_check_result = False
            _runtime_check_time = time.monotonic()
        msg = _runtime_error_message(exc)
        if required:
            logger.error(msg)
            raise RuntimeError(f"Container runtime is required but unavailable: {msg}") from exc

        if not _OPTIONAL_RUNTIME_WARNING_EMITTED:
            logger.warning(
                "%s; continuing in degraded mode (set NANOCLAW_REQUIRE_CONTAINER_RUNTIME=1 to enforce)",
                msg,
            )
            _OPTIONAL_RUNTIME_WARNING_EMITTED = True
        return False


def cleanup_orphans() -> None:
    try:
        output = subprocess.check_output(
            [CONTAINER_RUNTIME_BIN, "ps", "--filter", "name=nanoclaw-", "--format", "{{.Names}}"],
            text=True,
            timeout=10,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.warning("failed to list orphaned containers: %s", exc)
        return

    names = [line.strip() for line in output.splitlines() if line.strip()]
    for name in names:
        try:
            subprocess.run(
                [CONTAINER_RUNTIME_BIN, "stop", name],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("failed to stop orphan container %s: %s", name, exc)
            continue

    if names:
        logger.info("stopped orphaned containers count=%s", len(names))
