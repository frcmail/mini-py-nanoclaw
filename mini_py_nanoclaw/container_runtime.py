from __future__ import annotations

import subprocess

from .config import CONTAINER_RUNTIME_BIN, PROXY_BIND_HOST
from .logger import logger

def ensure_container_runtime_running() -> None:
    try:
        subprocess.run(
            [CONTAINER_RUNTIME_BIN, "info"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        logger.error("container runtime check failed: %s", exc)
        raise RuntimeError("Container runtime is required but failed to start") from exc


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
