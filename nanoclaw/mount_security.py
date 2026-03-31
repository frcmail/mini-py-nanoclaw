from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .config import MOUNT_ALLOWLIST_PATH
from .logger import logger
from .types import AdditionalMount


@dataclass
class AllowedRoot:
    path: str
    allowReadWrite: bool
    description: str | None = None


@dataclass
class MountAllowlist:
    allowedRoots: list[AllowedRoot]
    blockedPatterns: list[str]
    nonMainReadOnly: bool


DEFAULT_BLOCKED_PATTERNS = [
    ".ssh",
    ".gnupg",
    ".gpg",
    ".aws",
    ".azure",
    ".gcloud",
    ".kube",
    ".docker",
    "credentials",
    ".env",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "id_rsa",
    "id_ed25519",
    "private_key",
    ".secret",
]


@lru_cache(maxsize=1)
def load_mount_allowlist() -> MountAllowlist | None:
    if not MOUNT_ALLOWLIST_PATH.exists():
        logger.warning("mount-allowlist not found at %s", MOUNT_ALLOWLIST_PATH)
        return None

    try:
        parsed = json.loads(MOUNT_ALLOWLIST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("failed to load mount allowlist: %s", exc)
        return None

    try:
        roots = [
            AllowedRoot(
                path=str(root["path"]),
                allowReadWrite=bool(root.get("allowReadWrite", False)),
                description=root.get("description"),
            )
            for root in parsed["allowedRoots"]
            if isinstance(root, dict) and isinstance(root.get("path"), str)
        ]
        blocked = sorted(set(DEFAULT_BLOCKED_PATTERNS + list(parsed.get("blockedPatterns", []))))
        non_main_ro = bool(parsed.get("nonMainReadOnly", True))
        return MountAllowlist(allowedRoots=roots, blockedPatterns=blocked, nonMainReadOnly=non_main_ro)
    except Exception as exc:
        logger.error("invalid mount allowlist structure: %s", exc)
        return None


def _expand_path(path_str: str) -> Path:
    if path_str.startswith("~/"):
        return Path.home() / path_str[2:]
    if path_str == "~":
        return Path.home()
    return Path(path_str)


def _is_valid_container_path(container_path: str) -> bool:
    return bool(container_path.strip()) and ".." not in container_path and not container_path.startswith("/")


def _matches_blocked_pattern(real_path: Path, blocked_patterns: list[str]) -> str | None:
    parts = [p for p in real_path.parts if p]
    as_str = str(real_path)
    for pattern in blocked_patterns:
        if any(pattern in part for part in parts):
            return pattern
        if pattern in as_str:
            return pattern
    return None


def _find_allowed_root(real_path: Path, roots: list[AllowedRoot]) -> AllowedRoot | None:
    for root in roots:
        resolved_root = _expand_path(root.path).expanduser().resolve()
        if not resolved_root.exists():
            continue
        try:
            real_path.relative_to(resolved_root)
            return root
        except ValueError:
            continue
    return None


def validate_additional_mounts(mounts: list[AdditionalMount], group_name: str, is_main: bool) -> list[dict[str, object]]:
    allowlist = load_mount_allowlist()
    if allowlist is None:
        logger.warning("%s: mount allowlist unavailable, blocking additional mounts", group_name)
        return []

    validated: list[dict[str, object]] = []
    for mount in mounts:
        container_path = mount.container_path or os.path.basename(mount.host_path.rstrip("/"))
        if not _is_valid_container_path(container_path):
            logger.warning("%s: invalid container path %s", group_name, container_path)
            continue

        host_path = _expand_path(mount.host_path).expanduser()
        try:
            real_host_path = host_path.resolve(strict=True)
        except FileNotFoundError:
            logger.warning("%s: mount path does not exist %s", group_name, mount.host_path)
            continue

        blocked = _matches_blocked_pattern(real_host_path, allowlist.blockedPatterns)
        if blocked is not None:
            logger.warning("%s: mount blocked by pattern %s (%s)", group_name, blocked, real_host_path)
            continue

        allowed_root = _find_allowed_root(real_host_path, allowlist.allowedRoots)
        if allowed_root is None:
            logger.warning("%s: mount not under allowed roots (%s)", group_name, real_host_path)
            continue

        requested_rw = mount.readonly is False
        can_write = (
            requested_rw
            and allowed_root.allowReadWrite
            and (is_main or not allowlist.nonMainReadOnly)
        )
        readonly = not can_write

        validated.append(
            {
                "hostPath": str(real_host_path),
                "containerPath": f"/workspace/extra/{container_path}",
                "readonly": readonly,
            }
        )

    return validated
