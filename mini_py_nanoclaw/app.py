from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable

from .config import POLL_INTERVAL
from .db import NanoClawDB
from .group_queue import GroupQueue
from .types import RegisteredGroup


class NanoClawApp:
    """Python orchestrator skeleton mirroring NanoClaw core state flow."""

    def __init__(self) -> None:
        self.db = NanoClawDB()
        self.queue = GroupQueue()
        self.last_timestamp = ""
        self.last_agent_timestamp: dict[str, str] = {}
        self.sessions: dict[str, str] = {}
        self.registered_groups: dict[str, RegisteredGroup] = {}
        self._message_worker: Callable[[], Awaitable[None]] | None = None

    def load_state(self) -> None:
        self.last_timestamp = self.db.get_router_state("last_timestamp") or ""
        raw = self.db.get_router_state("last_agent_timestamp")
        if raw:
            try:
                self.last_agent_timestamp = json.loads(raw)
            except json.JSONDecodeError:
                self.last_agent_timestamp = {}
        self.sessions = self.db.get_all_sessions()
        self.registered_groups = self.db.get_all_registered_groups()

    def save_state(self) -> None:
        self.db.set_router_state("last_timestamp", self.last_timestamp)
        self.db.set_router_state("last_agent_timestamp", json.dumps(self.last_agent_timestamp))

    async def start(self, message_worker: Callable[[], Awaitable[None]]) -> None:
        self.load_state()
        self._message_worker = message_worker
        while True:
            await self._message_worker()
            await asyncio.sleep(POLL_INTERVAL / 1000)
