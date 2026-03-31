from __future__ import annotations

import os
import tempfile

from ..config import DATA_DIR, GROUPS_DIR, STORE_DIR
from .status import emit_status


def _is_writable(path: os.PathLike[str]) -> bool:
    try:
        fd, tmp = tempfile.mkstemp(dir=path)
        os.close(fd)
        os.unlink(tmp)
        return True
    except OSError:
        return False


def run(_args: list[str]) -> None:
    dirs = {"GROUPS_DIR": GROUPS_DIR, "STORE_DIR": STORE_DIR, "DATA_DIR": DATA_DIR}
    missing = [name for name, d in dirs.items() if not d.exists()]
    readonly = [name for name, d in dirs.items() if d.exists() and not _is_writable(d)]

    ok = not missing and not readonly
    status = "success" if ok else ("incomplete" if missing else "not_writable")

    emit_status(
        "VERIFY",
        {
            "GROUPS_DIR": str(GROUPS_DIR),
            "STORE_DIR": str(STORE_DIR),
            "DATA_DIR": str(DATA_DIR),
            "STATUS": status,
            **({"MISSING": ",".join(missing)} if missing else {}),
            **({"NOT_WRITABLE": ",".join(readonly)} if readonly else {}),
        },
    )
    if not ok:
        raise RuntimeError(f"setup verification failed: {status}")
