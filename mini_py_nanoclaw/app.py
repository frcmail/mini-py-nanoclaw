from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from .config import ASSISTANT_NAME, POLL_INTERVAL, TIMEZONE, TRIGGER_PATTERN
from .container_runner import ContainerInput, ContainerOutput, run_container_agent
from .db import NanoClawDB
from .group_folder import resolve_group_folder_path
from .group_queue import GroupQueue
from .ipc_io import close_container_input
from .router import find_channel, format_messages, format_outbound
from .types import NewMessage, RegisteredGroup


class NanoClawApp:
    """Python orchestrator with pluggable channels and local agent runner."""

    def __init__(
        self,
        db: Optional[NanoClawDB] = None,
        queue: Optional[GroupQueue] = None,
        agent_runner: Callable = run_container_agent,
    ) -> None:
        self.db = db or NanoClawDB()
        self.queue = queue or GroupQueue()
        self.agent_runner = agent_runner

        self.last_timestamp = ""
        self.last_agent_timestamp: dict[str, str] = {}
        self.sessions: dict[str, str] = {}
        self.registered_groups: dict[str, RegisteredGroup] = {}
        self.channels: list[object] = []

        self.queue.set_process_messages_fn(self.process_group_messages)
        self.queue.set_close_stdin_fn(self._close_group_stdin)

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

    def register_group(self, jid: str, group: RegisteredGroup) -> None:
        self.registered_groups[jid] = group
        self.db.set_registered_group(jid, group)
        group_dir = resolve_group_folder_path(group.folder)
        (group_dir / "logs").mkdir(parents=True, exist_ok=True)

    async def setup_channels(self, channel_names: Optional[list[str]] = None) -> None:
        from . import channels as _channels  # noqa: F401
        from .channels.registry import ChannelOpts, get_channel_factory, get_registered_channel_names

        _ = _channels
        self.channels = []
        names = channel_names or get_registered_channel_names()

        opts = ChannelOpts(
            on_message=self._on_inbound_message,
            on_chat_metadata=self._on_chat_metadata,
            registered_groups=lambda: self.registered_groups,
        )

        for name in names:
            factory = get_channel_factory(name)
            if factory is None:
                continue
            channel = factory(opts)
            connect = getattr(channel, "connect", None)
            if callable(connect):
                await connect()
            self.channels.append(channel)

    async def shutdown(self) -> None:
        await self.queue.shutdown()
        for channel in self.channels:
            disconnect = getattr(channel, "disconnect", None)
            if callable(disconnect):
                await disconnect()

    def _on_chat_metadata(
        self,
        chat_jid: str,
        timestamp: str,
        name: Optional[str] = None,
        channel: Optional[str] = None,
        is_group: Optional[bool] = None,
    ) -> None:
        self.db.store_chat_metadata(chat_jid, timestamp, name, channel, is_group)

    def _on_inbound_message(self, chat_jid: str, message: NewMessage) -> None:
        self.db.store_chat_metadata(chat_jid, message.timestamp, message.sender_name, "local-file", True)

        if chat_jid not in self.registered_groups:
            return

        self.db.store_message(message)
        self.queue.enqueue_message_check(chat_jid)

    async def poll_channels(self) -> None:
        for channel in self.channels:
            poll = getattr(channel, "poll", None)
            if callable(poll):
                await poll()

    async def run_once(self) -> None:
        await self.poll_channels()

    async def run_loop(self) -> None:
        while True:
            await self.run_once()
            await asyncio.sleep(POLL_INTERVAL / 1000)

    async def send_message(self, jid: str, text: str) -> None:
        channel = find_channel(self.channels, jid)
        if channel is None:
            raise ValueError(f"No channel for JID: {jid}")
        await channel.send_message(jid, text)

        self.db.store_message(
            NewMessage(
                id=uuid.uuid4().hex,
                chat_jid=jid,
                sender=f"{ASSISTANT_NAME.lower()}@nanoclaw.local",
                sender_name=ASSISTANT_NAME,
                content=text,
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                is_from_me=True,
                is_bot_message=True,
            )
        )

    async def process_group_messages(self, chat_jid: str) -> bool:
        group = self.registered_groups.get(chat_jid)
        if group is None:
            return True

        channel = find_channel(self.channels, chat_jid)
        if channel is None:
            return True

        since = self.last_agent_timestamp.get(chat_jid, "")
        messages = self.db.get_messages_since(chat_jid, since, ASSISTANT_NAME)
        if not messages:
            return True

        is_main = bool(group.is_main)
        if (not is_main) and (group.requires_trigger is not False):
            has_trigger = any(TRIGGER_PATTERN.search(message.content.strip()) for message in messages)
            if not has_trigger:
                return True

        prompt = format_messages(messages, TIMEZONE)

        previous_cursor = self.last_agent_timestamp.get(chat_jid, "")
        self.last_agent_timestamp[chat_jid] = messages[-1].timestamp
        self.save_state()

        output_sent = False
        had_error = False

        async def _on_output(output: ContainerOutput) -> None:
            nonlocal output_sent, had_error
            if output.result:
                text = format_outbound(output.result)
                if text:
                    await self.send_message(chat_jid, text)
                    output_sent = True
            if output.status == "error":
                had_error = True
            if output.status == "success":
                self.queue.notify_idle(chat_jid)

        result = await self.agent_runner(
            group,
            ContainerInput(
                prompt=prompt,
                session_id=self.sessions.get(group.folder),
                group_folder=group.folder,
                chat_jid=chat_jid,
                is_main=is_main,
                assistant_name=ASSISTANT_NAME,
            ),
            on_output=_on_output,
        )

        if result.status == "error" or had_error:
            if output_sent:
                return True
            self.last_agent_timestamp[chat_jid] = previous_cursor
            self.save_state()
            return False

        if result.new_session_id:
            self.sessions[group.folder] = result.new_session_id
            self.db.set_session(group.folder, result.new_session_id)

        return True

    def _close_group_stdin(self, chat_jid: str) -> None:
        group = self.registered_groups.get(chat_jid)
        if group is None:
            return
        close_container_input(group.folder)


def build_default_main_group(assistant_name: str = ASSISTANT_NAME) -> tuple[str, RegisteredGroup]:
    jid = "local:main"
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger=f"@{assistant_name}",
        added_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        requires_trigger=False,
        is_main=True,
    )
    return jid, group
