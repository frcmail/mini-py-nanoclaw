from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from .config import (
    ASSISTANT_NAME,
    CREDENTIAL_PROXY_PORT,
    POLL_INTERVAL,
    PROXY_BIND_HOST,
    TIMEZONE,
    TRIGGER_PATTERN,
)
from .container_runner import (
    AvailableGroup,
    ContainerInput,
    ContainerOutput,
    run_container_agent,
    write_groups_snapshot,
    write_tasks_snapshot,
)
from .container_runtime import cleanup_orphans, ensure_container_runtime_running
from .credential_proxy import CredentialProxyServer, start_credential_proxy
from .db import NanoClawDB
from .group_folder import resolve_group_folder_path
from .group_queue import GroupQueue
from .ipc import IpcDeps, IpcWatcher
from .ipc_io import close_container_input
from .logger import logger
from .router import find_channel, format_messages, format_outbound
from .sender_allowlist import (
    is_sender_allowed,
    is_trigger_allowed,
    load_sender_allowlist,
    should_drop_message,
)
from .task_scheduler import TaskScheduler
from .types import NewMessage, RegisteredGroup, ScheduledTask


class NanoClawApp:
    """Python orchestrator with pluggable channels and pure-Python runtime."""

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

        self._scheduler: TaskScheduler | None = None
        self._ipc_watcher: IpcWatcher | None = None
        self._credential_proxy: CredentialProxyServer | None = None

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
        names = channel_names or _resolve_channel_names(get_registered_channel_names())

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

        if not self.channels:
            raise RuntimeError("No channels connected")

    async def start_background_services(self) -> None:
        ensure_container_runtime_running()
        cleanup_orphans()

        self._credential_proxy = start_credential_proxy(CREDENTIAL_PROXY_PORT, PROXY_BIND_HOST)

        self._scheduler = TaskScheduler(
            db=self.db,
            queue=self.queue,
            registered_groups=lambda: self.registered_groups,
            get_sessions=lambda: self.sessions,
            run_task_fn=self._run_scheduled_task,
        )
        self._scheduler.start()

        self._ipc_watcher = IpcWatcher(
            IpcDeps(
                db=self.db,
                send_message=self.send_message,
                registered_groups=lambda: self.registered_groups,
            )
        )
        await self._ipc_watcher.start()

        self.recover_pending_messages()

    async def shutdown(self) -> None:
        await self.queue.shutdown()

        if self._scheduler is not None:
            await self._scheduler.stop()
        if self._ipc_watcher is not None:
            await self._ipc_watcher.stop()
        if self._credential_proxy is not None:
            self._credential_proxy.close()

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
        if chat_jid not in self.registered_groups:
            return

        if not message.is_from_me and not message.is_bot_message:
            cfg = load_sender_allowlist()
            if should_drop_message(chat_jid, cfg) and not is_sender_allowed(chat_jid, message.sender, cfg):
                return

        self.db.store_message(message)
        self.queue.enqueue_message_check(chat_jid)

    def recover_pending_messages(self) -> None:
        for jid in self.registered_groups.keys():
            since = self.last_agent_timestamp.get(jid, "")
            pending = self.db.get_messages_since(jid, since, ASSISTANT_NAME)
            if pending:
                self.queue.enqueue_message_check(jid)

    async def poll_channels(self) -> None:
        for channel in self.channels:
            poll = getattr(channel, "poll", None)
            if callable(poll):
                await poll()

    async def run_once(self) -> None:
        await self.poll_channels()

    async def run_loop(self) -> None:
        logger.info("NanoClaw running (trigger: @%s)", ASSISTANT_NAME)
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

    def get_available_groups(self) -> list[AvailableGroup]:
        chats = self.db.get_all_chats()
        registered_jids = set(self.registered_groups.keys())

        groups: list[AvailableGroup] = []
        for chat in chats:
            jid = str(chat.get("jid") or "")
            if jid == "__group_sync__":
                continue
            if not bool(chat.get("is_group")):
                continue
            groups.append(
                AvailableGroup(
                    jid=jid,
                    name=str(chat.get("name") or jid),
                    last_activity=str(chat.get("last_message_time") or ""),
                    is_registered=jid in registered_jids,
                )
            )
        return groups

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
            allowlist = load_sender_allowlist()
            has_trigger = any(
                TRIGGER_PATTERN.search(message.content.strip())
                and (message.is_from_me or is_trigger_allowed(chat_jid, message.sender, allowlist))
                for message in messages
            )
            if not has_trigger:
                return True

        prompt = format_messages(messages, TIMEZONE)

        previous_cursor = self.last_agent_timestamp.get(chat_jid, "")
        self.last_agent_timestamp[chat_jid] = messages[-1].timestamp
        self.save_state()

        output_sent = False
        had_error = False

        # Snapshot tasks/groups for this group before running.
        tasks = self.db.get_all_tasks()
        write_tasks_snapshot(
            group.folder,
            is_main,
            [
                {
                    "id": t.id,
                    "groupFolder": t.group_folder,
                    "prompt": t.prompt,
                    "schedule_type": t.schedule_type,
                    "schedule_value": t.schedule_value,
                    "status": t.status,
                    "next_run": t.next_run,
                }
                for t in tasks
            ],
        )
        write_groups_snapshot(group.folder, is_main, self.get_available_groups(), set(self.registered_groups.keys()))

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

    async def _run_scheduled_task(self, task: ScheduledTask, sessions: dict[str, str]) -> str | None:
        group = next((g for g in self.registered_groups.values() if g.folder == task.group_folder), None)
        if group is None:
            raise RuntimeError(f"Group not found: {task.group_folder}")

        is_main = bool(group.is_main)
        streamed_result: str | None = None

        async def _on_output(output: ContainerOutput) -> None:
            nonlocal streamed_result
            if output.result:
                streamed_result = output.result
                await self.send_message(task.chat_jid, format_outbound(output.result))
            if output.status == "success":
                self.queue.notify_idle(task.chat_jid)

        output = await self.agent_runner(
            group,
            ContainerInput(
                prompt=task.prompt,
                session_id=sessions.get(group.folder) if task.context_mode == "group" else None,
                group_folder=group.folder,
                chat_jid=task.chat_jid,
                is_main=is_main,
                assistant_name=ASSISTANT_NAME,
                is_scheduled_task=True,
            ),
            on_output=_on_output,
        )

        if output.status == "error":
            raise RuntimeError(output.error or "scheduled task failed")

        if output.new_session_id and task.context_mode == "group":
            self.sessions[group.folder] = output.new_session_id
            self.db.set_session(group.folder, output.new_session_id)

        return streamed_result or output.result

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


def _resolve_channel_names(registered_channel_names: list[str]) -> list[str]:
    configured = os.getenv("NANOCLAW_CHANNELS", "").strip()
    if configured:
        names = [name.strip() for name in configured.split(",") if name.strip()]
        return names if names else ["local-file"]

    if "local-file" in registered_channel_names:
        return ["local-file"]
    return registered_channel_names
