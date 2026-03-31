from pathlib import Path

from nanoclaw import group_folder
from nanoclaw.ipc_io import (
    close_container_input,
    drain_container_inputs,
    send_container_input,
    should_close,
)


def test_ipc_input_and_close_signal(tmp_path) -> None:
    group_folder.DATA_DIR = tmp_path / "data"
    group_folder.GROUPS_DIR = tmp_path / "groups"
    (group_folder.GROUPS_DIR / "main").mkdir(parents=True, exist_ok=True)

    send_container_input("main", "hello")
    send_container_input("main", "world")

    drained = drain_container_inputs("main")
    assert drained == ["hello", "world"]

    close_path = close_container_input("main")
    assert isinstance(close_path, Path)
    assert should_close("main") is True
    assert should_close("main") is False
