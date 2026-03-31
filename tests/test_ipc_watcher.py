import json
from datetime import datetime, timezone

import pytest

from nanoclaw.db import NanoClawDB
from nanoclaw.ipc import IpcDeps, IpcWatcher
from nanoclaw.types import RegisteredGroup


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_ipc_watcher_processes_messages_and_tasks(tmp_path) -> None:
    db = NanoClawDB.in_memory()
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at=_now_iso(),
        is_main=True,
        requires_trigger=False,
    )
    db.set_registered_group("local:main", group)

    sent = []

    async def send_message(jid: str, text: str) -> None:
        sent.append((jid, text))

    base = tmp_path / "ipc"
    (base / "main" / "messages").mkdir(parents=True, exist_ok=True)
    (base / "main" / "tasks").mkdir(parents=True, exist_ok=True)

    (base / "main" / "messages" / "m1.json").write_text(
        json.dumps({"type": "message", "chatJid": "local:main", "text": "hello"}),
        encoding="utf-8",
    )

    (base / "main" / "tasks" / "t1.json").write_text(
        json.dumps(
            {
                "type": "schedule_task",
                "targetJid": "local:main",
                "prompt": "do work",
                "schedule_type": "interval",
                "schedule_value": "60000",
                "context_mode": "isolated",
            }
        ),
        encoding="utf-8",
    )

    watcher = IpcWatcher(
        IpcDeps(db=db, send_message=send_message, registered_groups=lambda: db.get_all_registered_groups()),
        base_dir=base,
    )

    await watcher.run_once()

    assert sent == [("local:main", "hello")]
    tasks = db.get_all_tasks()
    assert len(tasks) == 1
    assert tasks[0].prompt == "do work"


@pytest.mark.asyncio
async def test_ipc_message_processing_handles_malformed_data(tmp_path) -> None:
    """Malformed message (chatJid is int) must not crash; file gets cleaned up."""
    db = NanoClawDB.in_memory()
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at=_now_iso(),
        is_main=True,
        requires_trigger=False,
    )
    db.set_registered_group("local:main", group)

    sent = []

    async def send_message(jid: str, text: str) -> None:
        sent.append((jid, text))

    base = tmp_path / "ipc"
    msg_dir = base / "main" / "messages"
    msg_dir.mkdir(parents=True, exist_ok=True)

    # chatJid is int, not str — should be skipped without crash
    (msg_dir / "bad.json").write_text(
        json.dumps({"type": "message", "chatJid": 42, "text": "hello"}),
        encoding="utf-8",
    )
    # Valid message alongside
    (msg_dir / "good.json").write_text(
        json.dumps({"type": "message", "chatJid": "local:main", "text": "ok"}),
        encoding="utf-8",
    )

    watcher = IpcWatcher(
        IpcDeps(db=db, send_message=send_message, registered_groups=lambda: db.get_all_registered_groups()),
        base_dir=base,
    )

    await watcher.run_once()

    # Bad message skipped, good message delivered
    assert sent == [("local:main", "ok")]
    # Both files cleaned up
    assert list(msg_dir.glob("*.json")) == []
