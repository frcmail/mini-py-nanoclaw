from __future__ import annotations

import re
from pathlib import Path

from .config import DATA_DIR, GROUPS_DIR

GROUP_FOLDER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
RESERVED_FOLDERS = {"global"}


def is_valid_group_folder(folder: str) -> bool:
    if not folder:
        return False
    if folder != folder.strip():
        return False
    if GROUP_FOLDER_PATTERN.fullmatch(folder) is None:
        return False
    if "/" in folder or "\\" in folder or ".." in folder:
        return False
    if folder.lower() in RESERVED_FOLDERS:
        return False
    return True


def assert_valid_group_folder(folder: str) -> None:
    if not is_valid_group_folder(folder):
        raise ValueError(f'Invalid group folder "{folder}"')


def _ensure_within_base(base_dir: Path, resolved_path: Path) -> None:
    try:
        resolved_path.relative_to(base_dir)
    except ValueError as exc:
        raise ValueError(f"Path escapes base directory: {resolved_path}") from exc


def resolve_group_folder_path(folder: str) -> Path:
    assert_valid_group_folder(folder)
    group_path = (GROUPS_DIR / folder).resolve()
    _ensure_within_base(GROUPS_DIR.resolve(), group_path)
    return group_path


def resolve_group_ipc_path(folder: str) -> Path:
    assert_valid_group_folder(folder)
    ipc_base = (DATA_DIR / "ipc").resolve()
    ipc_path = (ipc_base / folder).resolve()
    _ensure_within_base(ipc_base, ipc_path)
    return ipc_path
