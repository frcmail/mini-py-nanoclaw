from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Union

from .config import SENDER_ALLOWLIST_PATH
from .logger import logger

AllowType = Union[str, List[str]]


@dataclass
class ChatAllowlistEntry:
    allow: AllowType
    mode: str


@dataclass
class SenderAllowlistConfig:
    default: ChatAllowlistEntry = field(default_factory=lambda: ChatAllowlistEntry(allow="*", mode="trigger"))
    chats: Dict[str, ChatAllowlistEntry] = field(default_factory=dict)
    log_denied: bool = True


DEFAULT_CONFIG = SenderAllowlistConfig()


def _is_valid_entry(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    allow = value.get("allow")
    mode = value.get("mode")
    valid_allow = allow == "*" or (isinstance(allow, list) and all(isinstance(x, str) for x in allow))
    valid_mode = mode in {"trigger", "drop"}
    return valid_allow and valid_mode


def load_sender_allowlist(path_override: str | Path | None = None) -> SenderAllowlistConfig:
    file_path = Path(path_override) if path_override else SENDER_ALLOWLIST_PATH

    try:
        raw = file_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return SenderAllowlistConfig()
    except OSError as exc:
        logger.warning("sender-allowlist: cannot read config %s (%s)", file_path, exc)
        return SenderAllowlistConfig()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("sender-allowlist: invalid JSON %s", file_path)
        return SenderAllowlistConfig()

    if not isinstance(parsed, dict) or not _is_valid_entry(parsed.get("default")):
        logger.warning("sender-allowlist: invalid default entry %s", file_path)
        return SenderAllowlistConfig()

    default = ChatAllowlistEntry(allow=parsed["default"]["allow"], mode=parsed["default"]["mode"])
    chats: Dict[str, ChatAllowlistEntry] = {}

    raw_chats = parsed.get("chats")
    if isinstance(raw_chats, dict):
        for jid, entry in raw_chats.items():
            if not isinstance(jid, str):
                continue
            if _is_valid_entry(entry):
                chats[jid] = ChatAllowlistEntry(allow=entry["allow"], mode=entry["mode"])
            else:
                logger.warning("sender-allowlist: skipping invalid chat entry %s", jid)

    return SenderAllowlistConfig(
        default=default,
        chats=chats,
        log_denied=(parsed.get("logDenied") is not False),
    )


def _get_entry(chat_jid: str, cfg: SenderAllowlistConfig) -> ChatAllowlistEntry:
    return cfg.chats.get(chat_jid, cfg.default)


def is_sender_allowed(chat_jid: str, sender: str, cfg: SenderAllowlistConfig) -> bool:
    entry = _get_entry(chat_jid, cfg)
    if entry.allow == "*":
        return True
    return isinstance(entry.allow, list) and sender in entry.allow


def should_drop_message(chat_jid: str, cfg: SenderAllowlistConfig) -> bool:
    return _get_entry(chat_jid, cfg).mode == "drop"


def is_trigger_allowed(chat_jid: str, sender: str, cfg: SenderAllowlistConfig) -> bool:
    allowed = is_sender_allowed(chat_jid, sender, cfg)
    if not allowed and cfg.log_denied:
        logger.debug("sender-allowlist: trigger denied chat=%s sender=%s", chat_jid, sender)
    return allowed
