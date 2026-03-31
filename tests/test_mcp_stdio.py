from __future__ import annotations

import json

import pytest


@pytest.fixture()
def mcp_env(tmp_path, monkeypatch):
    """Set up env vars for mcp_stdio module-level constants."""
    ipc_dir = tmp_path / "ipc"
    ipc_dir.mkdir()
    (ipc_dir / "messages").mkdir()
    (ipc_dir / "tasks").mkdir()
    monkeypatch.setenv("NANOCLAW_CHAT_JID", "test:chat")
    monkeypatch.setenv("NANOCLAW_GROUP_FOLDER", "testgroup")
    monkeypatch.setenv("NANOCLAW_IS_MAIN", "0")
    return ipc_dir


def _get_mod(mcp_env):
    """Get mcp_stdio module with patched paths."""
    import nanoclaw.mcp_stdio as mod
    mod.IPC_DIR = mcp_env
    mod.MESSAGES_DIR = mcp_env / "messages"
    mod.TASKS_DIR = mcp_env / "tasks"
    mod.CHAT_JID = "test:chat"
    mod.GROUP_FOLDER = "testgroup"
    mod.IS_MAIN = False
    return mod


def test_send_message(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("send_message", {"text": "hello"})
    assert "isError" not in result

    files = list((mcp_env / "messages").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["text"] == "hello"
    assert data["chatJid"] == "test:chat"


def test_send_message_empty_text(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("send_message", {"text": ""})
    assert result["isError"] is True


def test_schedule_task(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("schedule_task", {
        "prompt": "do work",
        "schedule_type": "interval",
        "schedule_value": "60000",
    })
    assert "isError" not in result

    files = list((mcp_env / "tasks").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["type"] == "schedule_task"
    assert data["prompt"] == "do work"


def test_pause_task_requires_id(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("pause_task", {})
    assert result["isError"] is True


def test_pause_task_writes_ipc(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("pause_task", {"task_id": "test-task-1"})
    assert "isError" not in result

    files = list((mcp_env / "tasks").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert data["type"] == "pause_task"
    assert data["taskId"] == "test-task-1"


def test_list_tools(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    tools = mod._list_tools()
    names = {t["name"] for t in tools}
    assert "send_message" in names
    assert "schedule_task" in names
    assert "list_tasks" in names


def test_unknown_tool(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    result = mod._call_tool("nonexistent", {})
    assert result["isError"] is True


def test_list_tasks_filters_for_non_main(mcp_env) -> None:
    mod = _get_mod(mcp_env)
    tasks = [
        {"groupFolder": "testgroup", "id": "t1"},
        {"groupFolder": "other", "id": "t2"},
    ]
    (mcp_env / "current_tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
    result = mod._call_tool("list_tasks", {})
    parsed = json.loads(result["content"][0]["text"])
    assert len(parsed) == 1
    assert parsed[0]["id"] == "t1"
