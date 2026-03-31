from __future__ import annotations

import os
from pathlib import Path


def read_env_file(keys: list[str], env_path: Path | None = None) -> dict[str, str]:
    """Read a subset of keys from a dotenv-style file."""
    if env_path is not None:
        path = env_path
    else:
        home = os.getenv("NANOCLAW_HOME")
        base = Path(home).expanduser() if home else (Path.home() / ".nanoclaw")
        path = base / ".env"
    if not path.exists():
        return {}

    wanted = set(keys)
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
