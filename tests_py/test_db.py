from typing import Optional

from mini_py_nanoclaw.db import NanoClawDB
from mini_py_nanoclaw.types import NewMessage, ScheduledTask


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
