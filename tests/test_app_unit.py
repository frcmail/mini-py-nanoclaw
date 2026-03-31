"""Unit tests for NanoClawApp — isolated from end-to-end channel integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import nanoclaw.app as app_module
from nanoclaw.app import NanoClawApp, build_default_main_group
from nanoclaw.container_runner import ContainerOutput
from nanoclaw.db import NanoClawDB
from nanoclaw.types import NewMessage, RegisteredGroup, ScheduledTask


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _make_msg(chat_jid: str, content: str, sender: str = "user1", **kw) -> NewMessage:
    return NewMessage(
        id=kw.get("id", "msg-1"),
        chat_jid=chat_jid,
        sender=sender,
        sender_name=kw.get("sender_name", "Tester"),
        content=content,
        timestamp=kw.get("timestamp", _now_iso()),
        is_from_me=kw.get("is_from_me", False),
        is_bot_message=kw.get("is_bot_message", False),
    )


# ── _on_inbound_message ──


def test_on_inbound_message_ignores_unregistered_chat() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    msg = _make_msg("unregistered@jid", "hello")

    app._on_inbound_message("unregistered@jid", msg)

    # No message stored → DB should have zero messages
    assert db.get_messages_since("unregistered@jid", "", "Andy") == []


def test_on_inbound_message_stores_message_for_registered_chat() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    msg = _make_msg(jid, "hello")
    app._on_inbound_message(jid, msg)

    msgs = db.get_messages_since(jid, "", "Andy")
    assert len(msgs) >= 1


def test_on_inbound_message_drops_disallowed_sender(monkeypatch) -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    from nanoclaw.sender_allowlist import ChatAllowlistEntry, SenderAllowlistConfig

    cfg = SenderAllowlistConfig()
    cfg.chats[jid] = ChatAllowlistEntry(allow=["alice"], mode="drop")

    monkeypatch.setattr(app_module, "load_sender_allowlist", lambda: cfg)

    msg = _make_msg(jid, "evil message", sender="bob")
    app._on_inbound_message(jid, msg)

    # Should not store
    assert db.get_messages_since(jid, "", "Andy") == []


def test_on_inbound_message_bypasses_allowlist_for_from_me(monkeypatch) -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    from nanoclaw.sender_allowlist import ChatAllowlistEntry, SenderAllowlistConfig

    cfg = SenderAllowlistConfig()
    cfg.chats[jid] = ChatAllowlistEntry(allow=["alice"], mode="drop")
    monkeypatch.setattr(app_module, "load_sender_allowlist", lambda: cfg)

    msg = _make_msg(jid, "from me", sender="bob", is_from_me=True)
    app._on_inbound_message(jid, msg)

    # Should store because is_from_me bypasses allowlist
    msgs = db.get_messages_since(jid, "", "Andy")
    assert len(msgs) >= 1


def test_on_inbound_message_bypasses_allowlist_for_bot(monkeypatch) -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    from nanoclaw.sender_allowlist import ChatAllowlistEntry, SenderAllowlistConfig

    cfg = SenderAllowlistConfig()
    cfg.chats[jid] = ChatAllowlistEntry(allow=["alice"], mode="drop")
    monkeypatch.setattr(app_module, "load_sender_allowlist", lambda: cfg)

    queued: list[str] = []
    monkeypatch.setattr(app.queue, "enqueue_message_check", lambda jid: queued.append(jid))

    msg = _make_msg(jid, "bot msg", sender="bob", is_bot_message=True)
    app._on_inbound_message(jid, msg)

    # Bot message bypasses allowlist, gets stored and enqueued
    assert jid in queued


# ── send_message ──


@pytest.mark.asyncio
async def test_send_message_raises_for_unknown_channel() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    app.channels = []

    with pytest.raises(ValueError, match="No channel for JID"):
        await app.send_message("unknown@jid", "hello")


@pytest.mark.asyncio
async def test_send_message_stores_and_routes() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    sent: list[tuple[str, str]] = []

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

        async def send_message(self, j, text):
            sent.append((j, text))

    app.channels = [FakeChannel()]
    await app.send_message(jid, "outbound text")

    assert sent == [(jid, "outbound text")]
    # Outbound message stored with is_bot_message=True (filtered by get_messages_since)
    # Verify via direct SQL that the message was stored
    row = db._conn.execute(
        "SELECT content FROM messages WHERE chat_jid = ? AND is_bot_message = 1", (jid,)
    ).fetchone()
    assert row is not None
    assert "outbound text" in row["content"]


# ── process_group_messages ──


@pytest.mark.asyncio
async def test_process_group_messages_no_messages_early_return() -> None:
    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        raise AssertionError("agent should not be called")

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

    app.channels = [FakeChannel()]

    result = await app.process_group_messages(jid)
    assert result is True


@pytest.mark.asyncio
async def test_process_group_messages_unknown_group_early_return() -> None:
    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        raise AssertionError("agent should not be called")

    app = NanoClawApp(db=NanoClawDB.in_memory(), agent_runner=fake_runner)
    result = await app.process_group_messages("no_such_jid")
    assert result is True


@pytest.mark.asyncio
async def test_process_group_messages_updates_cursor_on_success() -> None:
    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        output = ContainerOutput(status="success", result="done")
        if on_output:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

        async def send_message(self, j, text):
            pass

    app.channels = [FakeChannel()]

    msg = _make_msg(jid, "hello", timestamp="2026-01-01T12:00:00Z")
    db.store_message(msg)

    result = await app.process_group_messages(jid)
    assert result is True
    assert app.last_agent_timestamp.get(jid) == "2026-01-01T12:00:00Z"


@pytest.mark.asyncio
async def test_process_group_messages_returns_output_sent_on_error() -> None:
    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        # Send a result first, then return error
        if on_output:
            await on_output(ContainerOutput(status="success", result="partial"))
        return ContainerOutput(status="error", result=None, error="boom")

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

        async def send_message(self, j, text):
            pass

    app.channels = [FakeChannel()]

    msg = _make_msg(jid, "hello")
    db.store_message(msg)

    result = await app.process_group_messages(jid)
    # output_sent is True because partial result was sent
    assert result is True
    # But cursor should NOT be updated (error status)
    assert jid not in app.last_agent_timestamp


@pytest.mark.asyncio
async def test_process_group_messages_requires_trigger_for_non_main() -> None:
    called = {"count": 0}

    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        called["count"] += 1
        output = ContainerOutput(status="success", result="done")
        if on_output:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)

    non_main_group = RegisteredGroup(
        name="Secondary",
        folder="secondary",
        trigger="@Andy",
        added_at=_now_iso(),
        requires_trigger=True,
        is_main=False,
    )
    app.register_group("ext:grp", non_main_group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == "ext:grp"

        async def send_message(self, j, text):
            pass

    app.channels = [FakeChannel()]

    # Message without trigger → should not invoke agent
    msg = _make_msg("ext:grp", "hello without trigger")
    db.store_message(msg)

    result = await app.process_group_messages("ext:grp")
    assert result is True
    assert called["count"] == 0  # agent was NOT called


@pytest.mark.asyncio
async def test_process_group_messages_stores_new_session_id() -> None:
    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        output = ContainerOutput(status="success", result="done", new_session_id="ses-abc")
        if on_output:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

        async def send_message(self, j, text):
            pass

    app.channels = [FakeChannel()]

    msg = _make_msg(jid, "hello")
    db.store_message(msg)

    await app.process_group_messages(jid)
    assert app.sessions.get(group.folder) == "ses-abc"


# ── _run_scheduled_task ──


@pytest.mark.asyncio
async def test_run_scheduled_task_success() -> None:
    sent: list[str] = []

    async def fake_runner(_g, _i, on_process=None, on_output=None, command=None):
        output = ContainerOutput(status="success", result="task done")
        if on_output:
            await on_output(output)
        return output

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fake_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    class FakeChannel:
        name = "fake"

        def owns_jid(self, j):
            return j == jid

        async def send_message(self, j, text):
            sent.append(text)

    app.channels = [FakeChannel()]

    task = ScheduledTask(
        id="t1",
        group_folder=group.folder,
        chat_jid=jid,
        prompt="run it",
        schedule_type="once",
        schedule_value="",
        context_mode="isolated",
        next_run=None,
        last_run=None,
        last_result=None,
        status="active",
        created_at=_now_iso(),
    )

    result = await app._run_scheduled_task(task, {})
    assert result == "task done"
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_run_scheduled_task_error_raises() -> None:
    async def fail_runner(_g, _i, on_process=None, on_output=None, command=None):
        return ContainerOutput(status="error", result=None, error="agent failed")

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db, agent_runner=fail_runner)
    jid, group = build_default_main_group()
    app.register_group(jid, group)
    app.channels = []

    task = ScheduledTask(
        id="t1",
        group_folder=group.folder,
        chat_jid=jid,
        prompt="run",
        schedule_type="once",
        schedule_value="",
        context_mode="isolated",
        next_run=None,
        last_run=None,
        last_result=None,
        status="active",
        created_at=_now_iso(),
    )

    with pytest.raises(RuntimeError, match="agent failed"):
        await app._run_scheduled_task(task, {})


@pytest.mark.asyncio
async def test_run_scheduled_task_group_not_found_raises() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)

    task = ScheduledTask(
        id="t1",
        group_folder="nonexistent",
        chat_jid="jid",
        prompt="run",
        schedule_type="once",
        schedule_value="",
        context_mode="isolated",
        next_run=None,
        last_run=None,
        last_result=None,
        status="active",
        created_at=_now_iso(),
    )

    with pytest.raises(RuntimeError, match="Group not found"):
        await app._run_scheduled_task(task, {})


# ── shutdown & lifecycle ──


@pytest.mark.asyncio
async def test_shutdown_handles_none_services() -> None:
    app = NanoClawApp(db=NanoClawDB.in_memory())
    app._scheduler = None
    app._ipc_watcher = None
    app._credential_proxy = None
    app.channels = []

    await app.shutdown()  # should not raise


@pytest.mark.asyncio
async def test_setup_channels_raises_when_none_connect(monkeypatch) -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)

    monkeypatch.setattr(
        "nanoclaw.channels.registry.get_registered_channel_names",
        lambda: [],
    )

    with pytest.raises(RuntimeError, match="No channels connected"):
        await app.setup_channels(channel_names=[])


# ── load_state / save_state ──


def test_load_state_handles_invalid_json() -> None:
    db = NanoClawDB.in_memory()
    db.set_router_state("last_agent_timestamp", "NOT JSON {{")
    app = NanoClawApp(db=db)
    app.load_state()
    assert app.last_agent_timestamp == {}


def test_save_state_persists_last_agent_timestamp() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    app.last_agent_timestamp = {"jid1": "2026-01-01T00:00:00Z"}
    app.save_state()

    raw = db.get_router_state("last_agent_timestamp")
    assert raw is not None
    loaded = json.loads(raw)
    assert loaded == {"jid1": "2026-01-01T00:00:00Z"}


# ── _on_chat_metadata ──


def test_on_chat_metadata_stores_metadata() -> None:
    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    app._on_chat_metadata("jid1", "2026-01-01T00:00:00Z", "TestGroup", "local-file", True)

    chats = db.get_all_chats()
    assert any(c.get("jid") == "jid1" for c in chats)


# ── _close_group_stdin ──


def test_close_group_stdin_calls_close_for_registered(monkeypatch) -> None:
    closed: list[str] = []
    monkeypatch.setattr(app_module, "close_container_input", lambda folder: closed.append(folder))

    db = NanoClawDB.in_memory()
    app = NanoClawApp(db=db)
    jid, group = build_default_main_group()
    app.register_group(jid, group)

    app._close_group_stdin(jid)
    assert closed == [group.folder]


def test_close_group_stdin_skips_unregistered(monkeypatch) -> None:
    closed: list[str] = []
    monkeypatch.setattr(app_module, "close_container_input", lambda folder: closed.append(folder))

    app = NanoClawApp(db=NanoClawDB.in_memory())
    app._close_group_stdin("unknown@jid")
    assert closed == []
