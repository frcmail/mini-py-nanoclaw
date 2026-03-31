from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from croniter import croniter

from .config import DATA_DIR, IPC_POLL_INTERVAL
from .container_runner import AvailableGroup, write_groups_snapshot
from .db import NanoClawDB
from .logger import logger
from .types import RegisteredGroup, ScheduledTask


@dataclass
class IpcDeps:
    db: NanoClawDB
    send_message: Callable[[str, str], Awaitable[None]]
    registered_groups: Callable[[], dict[str, RegisteredGroup]]


class IpcWatcher:
    def __init__(self, deps: IpcDeps, base_dir: Path | None = None, poll_interval_ms: int = IPC_POLL_INTERVAL) -> None:
        self._deps = deps
        self._base_dir = base_dir or (DATA_DIR / "ipc")
        self._poll_interval_ms = poll_interval_ms
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            await asyncio.wait({self._task}, timeout=1.0)

    async def _loop(self) -> None:
        while self._running:
            await self.run_once()
            await asyncio.sleep(self._poll_interval_ms / 1000)

    async def run_once(self) -> None:
        if not self._base_dir.exists():
            return

        groups = self._deps.registered_groups()
        folder_to_is_main = {group.folder: bool(group.is_main) for group in groups.values()}

        for group_dir in sorted(self._base_dir.iterdir()):
            if not group_dir.is_dir() or group_dir.name == "errors":
                continue
            source_group = group_dir.name
            is_main = folder_to_is_main.get(source_group, False)
            await self._process_messages(source_group, group_dir / "messages", groups, is_main)
            await self._process_tasks(source_group, group_dir / "tasks", groups, is_main)

            # Keep available groups snapshot fresh for agents.
            available = [
                AvailableGroup(
                    jid=jid,
                    name=group.name,
                    last_activity=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                    is_registered=True,
                )
                for jid, group in groups.items()
            ]
            write_groups_snapshot(source_group, is_main, available, set(groups.keys()))

    async def _process_messages(
        self,
        source_group: str,
        directory: Path,
        groups: dict[str, RegisteredGroup],
        is_main: bool,
    ) -> None:
        if not directory.exists():
            return

        for file_path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if data.get("type") != "message":
                    continue
                chat_jid = data.get("chatJid")
                text = data.get("text")
                if not isinstance(chat_jid, str) or not isinstance(text, str):
                    continue

                target = groups.get(chat_jid)
                if is_main or (target and target.folder == source_group):
                    await self._deps.send_message(chat_jid, text)
            except json.JSONDecodeError:
                logger.warning("ipc: invalid JSON in %s", file_path.name)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                logger.warning("ipc: error processing message %s: %s", file_path.name, exc)
            finally:
                file_path.unlink(missing_ok=True)

    async def _process_tasks(
        self,
        source_group: str,
        directory: Path,
        groups: dict[str, RegisteredGroup],
        is_main: bool,
    ) -> None:
        if not directory.exists():
            return

        for file_path in sorted(directory.glob("*.json")):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                await self._process_task_payload(data, source_group, groups, is_main)
            except json.JSONDecodeError:
                logger.warning("ipc: invalid task JSON in %s", file_path.name)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                logger.warning("ipc: error processing task %s: %s", file_path.name, exc)
            finally:
                file_path.unlink(missing_ok=True)

    async def _process_task_payload(
        self,
        data: dict,
        source_group: str,
        groups: dict[str, RegisteredGroup],
        is_main: bool,
    ) -> None:
        payload_type = data.get("type")
        task_id = data.get("taskId")

        if payload_type == "schedule_task":
            self._handle_schedule_task(data, source_group, groups, is_main)
            return

        self._handle_task_mutation(payload_type, task_id, source_group, is_main)

    def _handle_schedule_task(
        self,
        data: dict,
        source_group: str,
        groups: dict[str, RegisteredGroup],
        is_main: bool,
    ) -> None:
        target_jid = data.get("targetJid")
        prompt = data.get("prompt")
        schedule_type = data.get("schedule_type")
        schedule_value = data.get("schedule_value")
        if not all(isinstance(v, str) for v in [target_jid, prompt, schedule_type, schedule_value]):
            return

        target_group = groups.get(target_jid)
        if target_group is None:
            return
        if not is_main and target_group.folder != source_group:
            return

        next_run = _compute_first_run(schedule_type, schedule_value)
        if next_run is None:
            return

        task_id = data.get("taskId")
        new_id = task_id if isinstance(task_id, str) else f"task-{uuid.uuid4().hex[:8]}"
        task = ScheduledTask(
            id=new_id,
            group_folder=target_group.folder,
            chat_jid=target_jid,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            context_mode="group" if data.get("context_mode") == "group" else "isolated",
            next_run=next_run,
            last_run=None,
            last_result=None,
            status="active",
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        self._deps.db.create_task(task)

    def _handle_task_mutation(
        self,
        payload_type: str | None,
        task_id: str | None,
        source_group: str,
        is_main: bool,
    ) -> None:
        if not isinstance(task_id, str):
            return

        task = self._deps.db.get_task_by_id(task_id)
        if task is None:
            return

        if not is_main and task.group_folder != source_group:
            return

        if payload_type == "pause_task":
            self._deps.db.update_task(task_id, status="paused")
        elif payload_type == "resume_task":
            self._deps.db.update_task(task_id, status="active")
        elif payload_type == "cancel_task":
            self._deps.db.delete_task(task_id)


def _compute_first_run(schedule_type: str, schedule_value: str) -> str | None:
    now = datetime.now(timezone.utc)
    if schedule_type == "cron":
        next_dt = croniter(schedule_value, now).get_next(datetime)
        return next_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    if schedule_type == "interval":
        try:
            ms = int(schedule_value)
        except ValueError:
            return None
        if ms <= 0:
            return None
        next_dt = now + timedelta(milliseconds=ms)
        return next_dt.isoformat().replace("+00:00", "Z")

    if schedule_type == "once":
        try:
            parsed = datetime.fromisoformat(schedule_value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return None
