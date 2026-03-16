from __future__ import annotations

import subprocess

from .config import CONTAINER_RUNTIME_BIN
from .logger import logger


_OPTIONAL_RUNTIME_WARNING_EMITTED = False


def _runtime_error_message(exc: Exception) -> str:
    return f"{CONTAINER_RUNTIME_BIN} runtime check failed: {exc}"


def ensure_container_runtime_running(required: bool = True) -> bool:
    global _OPTIONAL_RUNTIME_WARNING_EMITTED

    try:
        subprocess.run(
            [CONTAINER_RUNTIME_BIN, "info"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except Exception as exc:
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
    except Exception as exc:
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
        except Exception:
            continue

    if names:
        logger.info("stopped orphaned containers count=%s", len(names))
