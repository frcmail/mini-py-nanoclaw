from __future__ import annotations

import json

from ..config import MOUNT_ALLOWLIST_PATH
from .status import emit_status

DEFAULT_ALLOWLIST = {
    "allowedRoots": [
        {"path": "~/projects", "allowReadWrite": True, "description": "Projects workspace"},
    ],
    "blockedPatterns": [],
    "nonMainReadOnly": True,
}


def run(_args: list[str]) -> None:
    MOUNT_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if not MOUNT_ALLOWLIST_PATH.exists():
        MOUNT_ALLOWLIST_PATH.write_text(json.dumps(DEFAULT_ALLOWLIST, indent=2) + "\n", encoding="utf-8")
        created = True

    emit_status(
        "MOUNTS",
        {
            "ALLOWLIST_PATH": str(MOUNT_ALLOWLIST_PATH),
            "CREATED": str(created).lower(),
            "STATUS": "success",
        },
    )
