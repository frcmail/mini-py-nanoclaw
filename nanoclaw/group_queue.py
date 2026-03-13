from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .config import MAX_CONCURRENT_CONTAINERS


@dataclass
class QueuedTask:
    id: str
    group_jid: str
    fn: Callable[[], Awaitable[None]]


@dataclass
class GroupState:
    active: bool = False
    idle_waiting: bool = False
    is_task_container: bool = False
    running_task_id: str | None = None
    pending_messages: bool = False
    pending_tasks: deque[QueuedTask] = field(default_factory=deque)
    retry_count: int = 0


class GroupQueue:
    def __init__(
        self,
        max_concurrent_containers: int = MAX_CONCURRENT_CONTAINERS,
        max_retries: int = 5,
        base_retry_ms: int = 5000,
    ) -> None:
        self._groups: dict[str, GroupState] = {}
        self._active_count = 0
        self._waiting_groups: deque[str] = deque()
        self._process_messages_fn: Callable[[str], Awaitable[bool]] | None = None
        self._shutting_down = False
        self._max_concurrent = max(1, max_concurrent_containers)
        self._max_retries = max_retries
        self._base_retry_ms = base_retry_ms
        self._close_stdin_fn: Callable[[str], None] | None = None

    def _get_group(self, group_jid: str) -> GroupState:
        state = self._groups.get(group_jid)
        if state is None:
            state = GroupState()
            self._groups[group_jid] = state
        return state

    def set_process_messages_fn(self, fn: Callable[[str], Awaitable[bool]]) -> None:
        self._process_messages_fn = fn

    def set_close_stdin_fn(self, fn: Callable[[str], None]) -> None:
        self._close_stdin_fn = fn

    def enqueue_message_check(self, group_jid: str) -> None:
        if self._shutting_down:
            return

        state = self._get_group(group_jid)

        if state.active:
            state.pending_messages = True
            return

        if self._active_count >= self._max_concurrent:
            state.pending_messages = True
            if group_jid not in self._waiting_groups:
                self._waiting_groups.append(group_jid)
            return

        self._start_run_for_group(group_jid)

    def enqueue_task(self, group_jid: str, task_id: str, fn: Callable[[], Awaitable[None]]) -> None:
        if self._shutting_down:
            return

        state = self._get_group(group_jid)

        if state.running_task_id == task_id:
            return

        if any(task.id == task_id for task in state.pending_tasks):
            return

        queued = QueuedTask(id=task_id, group_jid=group_jid, fn=fn)

        if state.active:
            state.pending_tasks.append(queued)
            if state.idle_waiting:
                self.close_stdin(group_jid)
            return

        if self._active_count >= self._max_concurrent:
            state.pending_tasks.append(queued)
            if group_jid not in self._waiting_groups:
                self._waiting_groups.append(group_jid)
            return

        self._start_run_task(group_jid, queued)

    def notify_idle(self, group_jid: str) -> None:
        state = self._get_group(group_jid)
        state.idle_waiting = True
        if state.pending_tasks:
            self.close_stdin(group_jid)

    def close_stdin(self, group_jid: str) -> None:
        if self._close_stdin_fn is not None:
            self._close_stdin_fn(group_jid)

    async def _run_for_group(self, group_jid: str) -> None:
        state = self._get_group(group_jid)

        try:
            success = True
            if self._process_messages_fn is not None:
                success = await self._process_messages_fn(group_jid)

            if success:
                state.retry_count = 0
            else:
                self._schedule_retry(group_jid, state)
        except Exception:
            self._schedule_retry(group_jid, state)
        finally:
            state.active = False
            self._active_count -= 1
            await self._drain_group(group_jid)

    async def _run_task(self, group_jid: str, task: QueuedTask) -> None:
        state = self._get_group(group_jid)

        try:
            await task.fn()
        finally:
            state.active = False
            state.idle_waiting = False
            state.is_task_container = False
            state.running_task_id = None
            self._active_count -= 1
            await self._drain_group(group_jid)

    def _schedule_retry(self, group_jid: str, state: GroupState) -> None:
        state.retry_count += 1
        if state.retry_count > self._max_retries:
            state.retry_count = 0
            return

        delay_ms = self._base_retry_ms * (2 ** (state.retry_count - 1))

        async def _retry() -> None:
            await asyncio.sleep(delay_ms / 1000)
            if not self._shutting_down:
                self.enqueue_message_check(group_jid)

        asyncio.create_task(_retry())

    async def _drain_group(self, group_jid: str) -> None:
        if self._shutting_down:
            return

        state = self._get_group(group_jid)

        if state.pending_tasks:
            task = state.pending_tasks.popleft()
            self._start_run_task(group_jid, task)
            return

        if state.pending_messages:
            self._start_run_for_group(group_jid)
            return

        await self._drain_waiting()

    async def _drain_waiting(self) -> None:
        while self._waiting_groups and self._active_count < self._max_concurrent:
            group_jid = self._waiting_groups.popleft()
            state = self._get_group(group_jid)
            if state.pending_tasks:
                task = state.pending_tasks.popleft()
                self._start_run_task(group_jid, task)
            elif state.pending_messages:
                self._start_run_for_group(group_jid)

    async def shutdown(self, _grace_period_ms: int = 0) -> None:
        self._shutting_down = True

    def _start_run_for_group(self, group_jid: str) -> None:
        state = self._get_group(group_jid)
        state.active = True
        state.idle_waiting = False
        state.is_task_container = False
        state.pending_messages = False
        self._active_count += 1
        asyncio.create_task(self._run_for_group(group_jid))

    def _start_run_task(self, group_jid: str, task: QueuedTask) -> None:
        state = self._get_group(group_jid)
        state.active = True
        state.idle_waiting = False
        state.is_task_container = True
        state.running_task_id = task.id
        self._active_count += 1
        asyncio.create_task(self._run_task(group_jid, task))
