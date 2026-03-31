from __future__ import annotations

from importlib.resources import files

from ..config import GROUPS_DIR
from .status import emit_status

DEFAULT_MAIN = "# Main group memory\n"
DEFAULT_GLOBAL = "# Global shared memory\n"
TEMPLATE_BASE = ("templates", "groups")


def _ensure(path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def _load_template(folder: str, fallback: str) -> str:
    try:
        template = files("nanoclaw")
        for segment in (*TEMPLATE_BASE, folder, "CLAUDE.md"):
            template = template.joinpath(segment)
        if template.is_file():
            return template.read_text(encoding="utf-8")
    except Exception:
        return fallback
    return fallback


def run(_args: list[str]) -> None:
    main_dir = GROUPS_DIR / "main"
    global_dir = GROUPS_DIR / "global"
    main_dir.mkdir(parents=True, exist_ok=True)
    global_dir.mkdir(parents=True, exist_ok=True)

    main_template = _load_template("main", DEFAULT_MAIN)
    global_template = _load_template("global", DEFAULT_GLOBAL)

    created_main = _ensure(main_dir / "CLAUDE.md", main_template)
    created_global = _ensure(global_dir / "CLAUDE.md", global_template)

    emit_status(
        "GROUPS",
        {
            "GROUPS_DIR": str(GROUPS_DIR),
            "MAIN_CREATED": str(created_main).lower(),
            "GLOBAL_CREATED": str(created_global).lower(),
            "STATUS": "success",
        },
    )
