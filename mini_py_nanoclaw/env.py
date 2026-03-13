from __future__ import annotations

from pathlib import Path


def read_env_file(keys: list[str], env_path: Path | None = None) -> dict[str, str]:
    """Read a subset of keys from a dotenv-style file."""
    path = env_path or Path.cwd() / ".env"
    if not path.exists():
        return {}

    wanted = set(keys)
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in wanted:
            continue
        values[key] = value.strip().strip('"').strip("'")
    return values
