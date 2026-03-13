from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, Optional, Protocol, Union


@dataclass
class AdditionalMount:
    host_path: str
    container_path: str | None = None
    readonly: bool = True


@dataclass
class ContainerConfig:
    additional_mounts: list[AdditionalMount] | None = None
    timeout: int | None = None


@dataclass
class RegisteredGroup:
    name: str
    folder: str
    trigger: str
    added_at: str
    container_config: ContainerConfig | None = None
    requires_trigger: bool | None = None
    is_main: bool | None = None


@dataclass
class NewMessage:
    id: str
    chat_jid: str
    sender: str
    sender_name: str
    content: str
    timestamp: str
    is_from_me: bool = False
    is_bot_message: bool = False


ScheduleType = Literal["cron", "interval", "once"]
ContextMode = Literal["group", "isolated"]
TaskStatus = Literal["active", "paused", "completed"]


@dataclass
class ScheduledTask:
    id: str
    group_folder: str
    chat_jid: str
    prompt: str
    schedule_type: ScheduleType
    schedule_value: str
    context_mode: ContextMode
    next_run: str | None
    last_run: str | None
    last_result: str | None
    status: TaskStatus
    created_at: str


@dataclass
class TaskRunLog:
    task_id: str
    run_at: str
    duration_ms: int
    status: Literal["success", "error"]
    result: str | None
    error: str | None


class Channel(Protocol):
    name: str

    async def connect(self) -> None: ...

    async def send_message(self, jid: str, text: str) -> None: ...

    def is_connected(self) -> bool: ...

    def owns_jid(self, jid: str) -> bool: ...

    async def disconnect(self) -> None: ...


OnInboundMessage = Callable[[str, NewMessage], Union[Awaitable[None], None]]
OnChatMetadata = Callable[
    [str, str, Optional[str], Optional[str], Optional[bool]],
    Union[Awaitable[None], None],
]
