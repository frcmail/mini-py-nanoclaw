from __future__ import annotations

import json
import uuid
from pathlib import Path

from .group_folder import resolve_group_ipc_path


def _input_dir(group_folder: str) -> Path:
    base = resolve_group_ipc_path(group_folder)
    input_dir = base / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    return input_dir


def write_ipc_json(directory: Path, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.json"
    path = directory / filename
    tmp = directory / f"{filename}.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
    tmp.rename(path)
    return path


def send_container_input(group_folder: str, text: str) -> Path:
    return write_ipc_json(_input_dir(group_folder), {"type": "message", "text": text})


def close_container_input(group_folder: str) -> Path:
    sentinel = _input_dir(group_folder) / "_close"
    sentinel.write_text("", encoding="utf-8")
    return sentinel


def should_close(group_folder: str) -> bool:
    sentinel = _input_dir(group_folder) / "_close"
    if sentinel.exists():
        sentinel.unlink(missing_ok=True)
        return True
    return False


def drain_container_inputs(group_folder: str) -> list[str]:
    messages: list[str] = []
    for file_path in sorted(_input_dir(group_folder).glob("*.json")):
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if data.get("type") == "message" and isinstance(data.get("text"), str):
                messages.append(data["text"])
        except json.JSONDecodeError:
            pass
        finally:
            file_path.unlink(missing_ok=True)
    return messages
