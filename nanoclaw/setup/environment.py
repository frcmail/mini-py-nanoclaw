from __future__ import annotations

import platform
import sys

from .status import emit_status


def run(_args: list[str]) -> None:
    py_ok = sys.version_info >= (3, 9)
    status = "success" if py_ok else "python_too_old"

    emit_status(
        "ENVIRONMENT",
        {
            "PYTHON_VERSION": platform.python_version(),
            "PYTHON_OK": str(py_ok).lower(),
            "PLATFORM": platform.system().lower(),
            "STATUS": status,
        },
    )

    if not py_ok:
        raise RuntimeError("Python 3.9+ is required")
