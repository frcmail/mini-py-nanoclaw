from __future__ import annotations

from datetime import datetime, timezone

from ..config import ASSISTANT_NAME, DATA_DIR
from ..db import NanoClawDB
from ..types import RegisteredGroup
from .status import emit_status


def run(_args: list[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = NanoClawDB()
    jid = "local:main"
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger=f"@{ASSISTANT_NAME}",
        added_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        requires_trigger=False,
        is_main=True,
    )
    db.set_registered_group(jid, group)
    db.close()

    emit_status(
        "REGISTER",
        {
            "MAIN_JID": jid,
            "ADDED_AT": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "STATUS": "success",
        },
    )
