from __future__ import annotations

from ..config import DATA_DIR, GROUPS_DIR, STORE_DIR
from .status import emit_status


def run(_args: list[str]) -> None:
    ok = GROUPS_DIR.exists() and STORE_DIR.exists() and DATA_DIR.exists()
    emit_status(
        "VERIFY",
        {
            "GROUPS_DIR": str(GROUPS_DIR),
            "STORE_DIR": str(STORE_DIR),
            "DATA_DIR": str(DATA_DIR),
            "STATUS": "success" if ok else "incomplete",
        },
    )
    if not ok:
        raise RuntimeError("setup verification failed")
