from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from datetime import datetime, timedelta, timezone
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter

from .config import SCHEDULER_POLL_INTERVAL, TIMEZONE
from .db import NanoClawDB
from .group_folder import resolve_group_folder_path
from .group_queue import GroupQueue
from .logger import logger
from .types import RegisteredGroup, ScheduledTask, TaskRunLog


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compute_next_run(task: ScheduledTask) -> str | None:
    if task.schedule_type == "once":
        return None

    now = datetime.now(timezone.utc)

    if task.schedule_type == "cron":
        try:
            tz = ZoneInfo(TIMEZONE)
        except ZoneInfoNotFoundError:
            logger.warning("scheduler: unknown timezone %s, falling back to UTC", TIMEZONE)
            tz = timezone.utc
        base = now.astimezone(tz)
        next_dt = croniter(task.schedule_value, base).get_next(datetime)
        return _utc_iso(next_dt)

    if task.schedule_type == "interval":
        try:
            interval_ms = int(task.schedule_value)
        except ValueError:
            return _utc_iso(now + timedelta(minutes=1))

        if interval_ms <= 0:
            return _utc_iso(now + timedelta(minutes=1))

        if task.next_run is None:
            return _utc_iso(now)

        scheduled = datetime.fromisoformat(task.next_run.replace("Z", "+00:00"))
        if scheduled.tzinfo is None:
            scheduled = scheduled.replace(tzinfo=timezone.utc)

        next_time = scheduled
        while next_time <= now:
            next_time = next_time + timedelta(milliseconds=interval_ms)
        return _utc_iso(next_time)

    return None


class TaskScheduler:
    def __init__(
        self,
        db: NanoClawDB,
        queue: GroupQueue,
        registered_groups: Callable[[], dict[str, RegisteredGroup]],
        get_sessions: Callable[[], dict[str, str]],
        run_task_fn: Callable[[ScheduledTask, dict[str, str]], Awaitable[str | None]],
        poll_interval_ms: int = SCHEDULER_POLL_INTERVAL,
    ) -> None:
        self._db = db
        self._queue = queue
        self._registered_groups = registered_groups
        self._get_sessions = get_sessions
        self._run_task_fn = run_task_fn
        self._poll_interval_ms = poll_interval_ms
        self._runner: asyncio.Task[None] | None = None
        self._stopped = False

    def start(self) -> None:
        if self._runner is None:
            self._runner = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self._stopped = True
        if self._runner is not None:
            self._runner.cancel()
            await asyncio.wait({self._runner}, timeout=1.0)

    async def run_once(self) -> None:
        due = self._db.get_due_tasks()
        for task in due:
            current = self._db.get_task_by_id(task.id)
            if current is None or current.status != "active":
                continue
            self._queue.enqueue_task(current.chat_jid, current.id, lambda t=current: self._run_and_record(t))

    async def _loop(self) -> None:
        while not self._stopped:
            try:
                await self.run_once()
            except Exception as exc:
                logger.warning("task scheduler loop iteration failed: %s", exc)
            await asyncio.sleep(self._poll_interval_ms / 1000)

    async def _run_and_record(self, task: ScheduledTask) -> None:
        start = datetime.now(timezone.utc)
        error: str | None = None
        result: str | None = None

        try:
            resolve_group_folder_path(task.group_folder)
        except ValueError as exc:
            self._db.update_task(task.id, status="paused")
            error = str(exc)
            self._db.log_task_run(
                TaskRunLog(
                    task_id=task.id,
                    run_at=_utc_iso(start),
                    duration_ms=int((datetime.now(timezone.utc) - start).total_seconds() * 1000),
                    status="error",
                    result=None,
                    error=error,
                )
            )
            return

        groups = self._registered_groups()
        group = next((g for g in groups.values() if g.folder == task.group_folder), None)
        if group is None:
            error = f"Group not found: {task.group_folder}"
        else:
            try:
                result = await self._run_task_fn(task, self._get_sessions())
            except Exception as exc:
                error = str(exc)

        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        self._db.log_task_run(
            TaskRunLog(
                task_id=task.id,
                run_at=_utc_iso(datetime.now(timezone.utc)),
                duration_ms=duration_ms,
                status="error" if error else "success",
                result=result,
                error=error,
            )
        )

        next_run = compute_next_run(task)
        summary = f"Error: {error}" if error else ((result or "Completed")[:200])
        self._db.update_task_after_run(task.id, next_run, summary)
