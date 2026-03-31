from typing import Optional

from nanoclaw.db import NanoClawDB
from nanoclaw.types import NewMessage, ScheduledTask


def make_task(task_id: str, next_run: Optional[str]) -> ScheduledTask:
    return ScheduledTask(
        id=task_id,
        group_folder="main",
        chat_jid="group@g.us",
        prompt="run",
        schedule_type="once",
        schedule_value="2026-01-01T00:00:00.000Z",
        context_mode="isolated",
        next_run=next_run,
        last_run=None,
        last_result=None,
        status="active",
        created_at="2026-01-01T00:00:00.000Z",
    )


def test_store_and_get_messages_since() -> None:
    db = NanoClawDB.in_memory()
    db.store_chat_metadata("group@g.us", "2024-01-01T00:00:00.000Z")
    db.store_message(
        NewMessage(
            id="m1",
            chat_jid="group@g.us",
            sender="alice",
            sender_name="Alice",
            content="hello",
            timestamp="2024-01-01T00:00:01.000Z",
        )
    )
    db.store_message(
        NewMessage(
            id="m2",
            chat_jid="group@g.us",
            sender="bot",
            sender_name="Bot",
            content="Andy: reply",
            timestamp="2024-01-01T00:00:02.000Z",
            is_bot_message=False,
        )
    )

    messages = db.get_messages_since("group@g.us", "", "Andy")
    assert len(messages) == 1
    assert messages[0].id == "m1"


def test_due_tasks() -> None:
    db = NanoClawDB.in_memory()
    db.create_task(make_task("t1", "2000-01-01T00:00:00.000Z"))
    due = db.get_due_tasks()
    assert len(due) == 1
    assert due[0].id == "t1"


def test_update_task() -> None:
    db = NanoClawDB.in_memory()
    db.create_task(make_task("t1", "2000-01-01T00:00:00.000Z"))
    db.update_task("t1", status="paused")
    task = db.get_task_by_id("t1")
    assert task is not None
    assert task.status == "paused"


def test_update_task_rejects_invalid_column() -> None:
    db = NanoClawDB.in_memory()
    db.create_task(make_task("t1", "2000-01-01T00:00:00.000Z"))
    import pytest
    with pytest.raises(ValueError, match="Invalid column"):
        db.update_task("t1", **{"bad_col": "value"})


def test_delete_task() -> None:
    db = NanoClawDB.in_memory()
    db.create_task(make_task("t1", "2000-01-01T00:00:00.000Z"))
    db.delete_task("t1")
    assert db.get_task_by_id("t1") is None


def test_get_all_tasks() -> None:
    db = NanoClawDB.in_memory()
    db.create_task(make_task("t1", "2000-01-01T00:00:00.000Z"))
    db.create_task(make_task("t2", "2001-01-01T00:00:00.000Z"))
    tasks = db.get_all_tasks()
    assert len(tasks) == 2


def test_sessions() -> None:
    db = NanoClawDB.in_memory()
    assert db.get_session("main") is None
    db.set_session("main", "sess-123")
    assert db.get_session("main") == "sess-123"
    sessions = db.get_all_sessions()
    assert sessions == {"main": "sess-123"}


def test_router_state() -> None:
    db = NanoClawDB.in_memory()
    assert db.get_router_state("cursor") is None
    db.set_router_state("cursor", "abc")
    assert db.get_router_state("cursor") == "abc"
    db.set_router_state("cursor", "def")
    assert db.get_router_state("cursor") == "def"


def test_registered_groups() -> None:
    from nanoclaw.types import RegisteredGroup

    db = NanoClawDB.in_memory()
    group = RegisteredGroup(
        name="Test",
        folder="test",
        trigger="@Andy",
        added_at="2024-01-01T00:00:00.000Z",
        is_main=False,
    )
    db.set_registered_group("local:test", group)
    retrieved = db.get_registered_group("local:test")
    assert retrieved is not None
    assert retrieved.folder == "test"

    all_groups = db.get_all_registered_groups()
    assert "local:test" in all_groups
