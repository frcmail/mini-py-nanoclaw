from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

IPC_DIR = Path("/workspace/ipc")
MESSAGES_DIR = IPC_DIR / "messages"
TASKS_DIR = IPC_DIR / "tasks"
CHAT_JID = os.getenv("NANOCLAW_CHAT_JID", "local:main")
GROUP_FOLDER = os.getenv("NANOCLAW_GROUP_FOLDER", "main")
IS_MAIN = os.getenv("NANOCLAW_IS_MAIN", "0") == "1"


def _write_ipc_file(directory: Path, payload: dict) -> str:
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{time.time_ns():020d}-{uuid.uuid4().hex[:8]}.json"
    path = directory / filename
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    tmp.rename(path)
    return filename


def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


_TOOLS = [
    {"name": "send_message", "description": "Send a message to the active chat"},
    {"name": "schedule_task", "description": "Create a scheduled task"},
    {"name": "list_tasks", "description": "List current tasks snapshot"},
    {"name": "pause_task", "description": "Pause a task"},
    {"name": "resume_task", "description": "Resume a task"},
    {"name": "cancel_task", "description": "Cancel a task"},
    {"name": "list_available_groups", "description": "List available groups snapshot"},
]


def _list_tools() -> list[dict]:
    return _TOOLS


def _tool_send_message(arguments: dict) -> dict:
    text = str(arguments.get("text") or "").strip()
    if not text:
        return {"isError": True, "content": [{"type": "text", "text": "text is required"}]}
    _write_ipc_file(
        MESSAGES_DIR,
        {
            "type": "message",
            "chatJid": str(arguments.get("chatJid") or CHAT_JID),
            "text": text,
            "sender": arguments.get("sender"),
            "groupFolder": GROUP_FOLDER,
            "timestamp": time.time(),
        },
    )
    return {"content": [{"type": "text", "text": "Message sent."}]}


def _tool_schedule_task(arguments: dict) -> dict:
    payload = {
        "type": "schedule_task",
        "taskId": arguments.get("taskId") or f"task-{uuid.uuid4().hex[:8]}",
        "prompt": arguments.get("prompt"),
        "schedule_type": arguments.get("schedule_type"),
        "schedule_value": arguments.get("schedule_value"),
        "context_mode": arguments.get("context_mode") or "group",
        "targetJid": arguments.get("targetJid") or CHAT_JID,
        "timestamp": time.time(),
    }
    _write_ipc_file(TASKS_DIR, payload)
    return {"content": [{"type": "text", "text": f"Task {payload['taskId']} scheduled."}]}


def _tool_task_mutation(name: str, arguments: dict) -> dict:
    task_id = arguments.get("task_id")
    if not task_id:
        return {"isError": True, "content": [{"type": "text", "text": "task_id is required"}]}
    _write_ipc_file(TASKS_DIR, {"type": name, "taskId": task_id, "timestamp": time.time()})
    return {"content": [{"type": "text", "text": f"{name} requested for {task_id}."}]}


def _tool_list_tasks(_arguments: dict) -> dict:
    tasks = _read_json(IPC_DIR / "current_tasks.json", [])
    if not IS_MAIN:
        tasks = [task for task in tasks if task.get("groupFolder") == GROUP_FOLDER]
    return {"content": [{"type": "text", "text": json.dumps(tasks, ensure_ascii=True)}]}


def _tool_list_available_groups(_arguments: dict) -> dict:
    payload = _read_json(IPC_DIR / "available_groups.json", {"groups": []})
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=True)}]}


_TOOL_DISPATCH: dict[str, object] = {
    "send_message": _tool_send_message,
    "schedule_task": _tool_schedule_task,
    "pause_task": lambda args: _tool_task_mutation("pause_task", args),
    "resume_task": lambda args: _tool_task_mutation("resume_task", args),
    "cancel_task": lambda args: _tool_task_mutation("cancel_task", args),
    "list_tasks": _tool_list_tasks,
    "list_available_groups": _tool_list_available_groups,
}


def _call_tool(name: str, arguments: dict) -> dict:
    handler = _TOOL_DISPATCH.get(name)
    if handler is None:
        return {"isError": True, "content": [{"type": "text", "text": f"unknown tool: {name}"}]}
    return handler(arguments)


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stderr.write("mcp: invalid JSON-RPC input\n")
            continue

        method = req.get("method")
        req_id = req.get("id")
        params = req.get("params") if isinstance(req.get("params"), dict) else {}

        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": _list_tools()}}
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            resp = {"jsonrpc": "2.0", "id": req_id, "result": _call_tool(str(name), args)}
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }

        sys.stdout.write(json.dumps(resp, ensure_ascii=True) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
