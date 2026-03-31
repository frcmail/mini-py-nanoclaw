from __future__ import annotations

import shutil
import subprocess

from .status import emit_status


def run(_args: list[str]) -> None:
    docker_path = shutil.which("docker")
    if not docker_path:
        emit_status("CONTAINER", {"DOCKER_FOUND": "false", "STATUS": "docker_missing"})
        return

    ok = False
    try:
        subprocess.run([docker_path, "info"], check=True, capture_output=True, text=True, timeout=10)
        ok = True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        ok = False

    emit_status(
        "CONTAINER",
        {
            "DOCKER_FOUND": "true",
            "DOCKER_PATH": docker_path,
            "DOCKER_RUNNING": str(ok).lower(),
            "STATUS": "success" if ok else "docker_not_running",
        },
    )
