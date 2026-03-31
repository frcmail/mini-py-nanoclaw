from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..types import Channel, NewMessage, RegisteredGroup

OnInboundMessage = Callable[[str, NewMessage], None]
OnChatMetadata = Callable[[str, str, Optional[str], Optional[str], Optional[bool]], None]


@dataclass
class ChannelOpts:
    on_message: OnInboundMessage
    on_chat_metadata: OnChatMetadata
    registered_groups: Callable[[], dict[str, RegisteredGroup]]


ChannelFactory = Callable[[ChannelOpts], Channel]

_registry: dict[str, ChannelFactory] = {}


def register_channel(name: str, factory: ChannelFactory) -> None:
    _registry[name] = factory


def get_channel_factory(name: str) -> ChannelFactory | None:
    return _registry.get(name)


def get_registered_channel_names() -> list[str]:
    return sorted(_registry.keys())
