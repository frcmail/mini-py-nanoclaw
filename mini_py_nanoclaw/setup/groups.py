from __future__ import annotations

from .status import emit_status
from ..config import GROUPS_DIR


DEFAULT_MAIN = "# Main group memory\n"
DEFAULT_GLOBAL = "# Global shared memory\n"


def _ensure(path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def run(_args: list[str]) -> None:
    main_dir = GROUPS_DIR / "main"
    global_dir = GROUPS_DIR / "global"
    main_dir.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)

    created_main = _ensure(main_dir / "CLAUDE.md", DEFAULT_MAIN)
    created_global = _ensure(global_dir / "CLAUDE.md", DEFAULT_GLOBAL)

    emit_status(
        "GROUPS",
        {
            "GROUPS_DIR": str(GROUPS_DIR),
            "MAIN_CREATED": str(created_main).lower(),
            "GLOBAL_CREATED": str(created_global).lower(),
            "STATUS": "success",
        },
    )
