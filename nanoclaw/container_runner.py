from __future__ import annotations

import asyncio
import json
import os
import shlex
import sys
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from .config import CONTAINER_TIMEOUT, REQUIRE_CONTAINER_RUNTIME
from .container_runtime import ensure_container_runtime_running
from .group_folder import resolve_group_ipc_path
from .mount_security import validate_additional_mounts
from .types import RegisteredGroup

OUTPUT_START_MARKER = "---NANOCLAW_OUTPUT_START---"
OUTPUT_END_MARKER = "---NANOCLAW_OUTPUT_END---"
DEFAULT_AGENT_COMMAND = os.getenv(
    "NANOCLAW_AGENT_COMMAND",
    f"{sys.executable} -m nanoclaw.agent_runner",
)


@dataclass
class ContainerInput:
    prompt: str
    group_folder: str
    chat_jid: str
    is_main: bool
    session_id: Optional[str] = None
    is_scheduled_task: bool = False
    assistant_name: Optional[str] = None


@dataclass
class ContainerOutput:
    status: str
    result: Optional[str]
    new_session_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class AvailableGroup:
    jid: str
    name: str
    last_activity: str
    is_registered: bool


def _extract_markers(stdout: str) -> list[ContainerOutput]:
    outputs: list[ContainerOutput] = []
    cursor = 0
    while True:
        start = stdout.find(OUTPUT_START_MARKER, cursor)
        if start == -1:
            break
        end = stdout.find(OUTPUT_END_MARKER, start)
        if end == -1:
            break
        raw = stdout[start + len(OUTPUT_START_MARKER) : end].strip()
        cursor = end + len(OUTPUT_END_MARKER)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        outputs.append(
            ContainerOutput(
                status=str(data.get("status") or "error"),
                result=data.get("result"),
                new_session_id=data.get("newSessionId") or data.get("new_session_id"),
                error=data.get("error"),
            )
        )
    return outputs


async def run_container_agent(
    group: RegisteredGroup,
    input_data: ContainerInput,
    on_process: Optional[Callable[[asyncio.subprocess.Process, str], None]] = None,
    on_output: Optional[Callable[[ContainerOutput], Awaitable[None]]] = None,
    command: Optional[str] = None,
) -> ContainerOutput:
    try:
        ensure_container_runtime_running(required=REQUIRE_CONTAINER_RUNTIME)
    except RuntimeError as exc:
        return ContainerOutput(status="error", result=None, error=str(exc))

    cmd = command or DEFAULT_AGENT_COMMAND
    try:
        args = shlex.split(cmd)
    except ValueError as exc:
        return ContainerOutput(status="error", result=None, error=f"Invalid agent command: {exc}")

    if not args:
        return ContainerOutput(status="error", result=None, error="Agent command is empty")

    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return ContainerOutput(status="error", result=None, error=f"Failed to start agent process: {exc}")

    container_name = f"nanoclaw-py-{group.folder}-{uuid.uuid4().hex[:8]}"
    if on_process is not None:
        on_process(proc, container_name)

    if group.container_config and group.container_config.additional_mounts:
        # Validate mounts early to enforce security policy even in local-run mode.
        _ = validate_additional_mounts(
            group.container_config.additional_mounts,
            group.name,
            bool(group.is_main),
        )

    payload = json.dumps(
        {
            "prompt": input_data.prompt,
            "sessionId": input_data.session_id,
            "groupFolder": input_data.group_folder,
            "chatJid": input_data.chat_jid,
            "isMain": input_data.is_main,
            "isScheduledTask": input_data.is_scheduled_task,
            "assistantName": input_data.assistant_name,
        },
        ensure_ascii=True,
    )

    timeout_ms = (
        group.container_config.timeout
        if group.container_config and group.container_config.timeout
        else CONTAINER_TIMEOUT
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(payload.encode("utf-8")), timeout=timeout_ms / 1000)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return ContainerOutput(status="error", result=None, error=f"Container timed out after {timeout_ms}ms")

    outputs = _extract_markers(stdout.decode("utf-8", errors="ignore"))
    if on_output is not None:
        for output in outputs:
            await on_output(output)

    if proc.returncode != 0:
        return ContainerOutput(
            status="error",
            result=None,
            error=f"Container exited with code {proc.returncode}: {stderr.decode('utf-8', errors='ignore')[-200:]}",
        )

    if outputs:
        return outputs[-1]

    return ContainerOutput(status="error", result=None, error="Failed to parse container output")


def write_tasks_snapshot(
    group_folder: str,
    is_main: bool,
    tasks: list[dict],
) -> None:
    group_ipc_dir = resolve_group_ipc_path(group_folder)
    group_ipc_dir.mkdir(parents=True, exist_ok=True)
    filtered = tasks if is_main else [task for task in tasks if task.get("groupFolder") == group_folder]
    (group_ipc_dir / "current_tasks.json").write_text(json.dumps(filtered, indent=2, ensure_ascii=True), encoding="utf-8")


def write_groups_snapshot(
    group_folder: str,
    is_main: bool,
    groups: list[AvailableGroup],
    _registered_jids: set[str],
) -> None:
    group_ipc_dir = resolve_group_ipc_path(group_folder)
    group_ipc_dir.mkdir(parents=True, exist_ok=True)
    visible = groups if is_main else []
    payload = {
        "groups": [
            {
                "jid": group.jid,
                "name": group.name,
                "lastActivity": group.last_activity,
                "isRegistered": group.is_registered,
            }
            for group in visible
        ]
    }
    (group_ipc_dir / "available_groups.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
