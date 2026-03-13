from __future__ import annotations

from .status import emit_status


def run(_args: list[str]) -> None:
    emit_status(
        "SERVICE",
        {
            "MODE": "manual",
            "STATUS": "success",
            "NEXT": "Run `python -m mini_py_nanoclaw` to start service",
        },
    )
