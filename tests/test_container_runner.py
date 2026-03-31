import json
import sys
from pathlib import Path

import pytest

import nanoclaw.container_runner as container_runner_module
from nanoclaw.container_runner import (
    AvailableGroup,
    ContainerInput,
    run_container_agent,
    write_groups_snapshot,
    write_tasks_snapshot,
)
from nanoclaw.types import ContainerConfig, RegisteredGroup


@pytest.mark.asyncio
async def test_container_runner_success() -> None:
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at="2026-01-01T00:00:00.000Z",
        is_main=True,
    )

    output = await run_container_agent(
        group,
        ContainerInput(
            prompt="hello from test",
            group_folder="main",
            chat_jid="local:main",
            is_main=True,
        ),
        command=f"{sys.executable} -m nanoclaw.simple_agent",
    )

    assert output.status == "success"
    assert output.result is not None
    assert output.result.startswith("Echo:")


@pytest.mark.asyncio
async def test_container_runner_timeout() -> None:
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at="2026-01-01T00:00:00.000Z",
        container_config=ContainerConfig(timeout=10),
        is_main=True,
    )

    output = await run_container_agent(
        group,
        ContainerInput(
            prompt="slow",
            group_folder="main",
            chat_jid="local:main",
            is_main=True,
        ),
        command=f"{sys.executable} -c 'import time; time.sleep(2)'",
    )

    assert output.status == "error"
    assert output.error is not None
    assert "timed out" in output.error


@pytest.mark.asyncio
async def test_container_runner_skips_runtime_check_for_local_command(monkeypatch) -> None:
    group = RegisteredGroup(
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at="2026-01-01T00:00:00.000Z",
        is_main=True,
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("runtime check should be skipped for local commands")

    monkeypatch.setattr(container_runner_module, "ensure_container_runtime_running", fail_if_called)

    output = await run_container_agent(
        group,
        ContainerInput(
            prompt="hello from local runner",
            group_folder="main",
            chat_jid="local:main",
            is_main=True,
        ),
        command=f"{sys.executable} -m nanoclaw.simple_agent",
    )

    assert output.status == "success"
    assert output.result is not None
    assert output.result.startswith("Echo:")


def test_write_tasks_snapshot_filters_non_main_group(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(container_runner_module, "resolve_group_ipc_path", lambda _folder: tmp_path / "ipc" / "grp1")

    tasks = [
        {"id": "t1", "groupFolder": "grp1", "prompt": "one"},
        {"id": "t2", "groupFolder": "grp2", "prompt": "two"},
    ]

    write_tasks_snapshot("grp1", is_main=False, tasks=tasks)

    payload = json.loads((tmp_path / "ipc" / "grp1" / "current_tasks.json").read_text(encoding="utf-8"))
    assert payload == [{"id": "t1", "groupFolder": "grp1", "prompt": "one"}]


def test_write_groups_snapshot_writes_empty_for_non_main(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(container_runner_module, "resolve_group_ipc_path", lambda _folder: tmp_path / "ipc" / "grp1")

    groups = [
        AvailableGroup(
            jid="g1",
            name="Group 1",
            last_activity="2026-01-01T00:00:00Z",
            is_registered=True,
        )
    ]

    write_groups_snapshot("grp1", is_main=False, groups=groups, _registered_jids={"g1"})

    payload = json.loads((tmp_path / "ipc" / "grp1" / "available_groups.json").read_text(encoding="utf-8"))
    assert payload == {"groups": []}


def test_write_groups_snapshot_writes_visible_groups_for_main(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(container_runner_module, "resolve_group_ipc_path", lambda _folder: tmp_path / "ipc" / "main")

    groups = [
        AvailableGroup(
            jid="g1",
            name="Group 1",
            last_activity="2026-01-01T00:00:00Z",
            is_registered=True,
        ),
        AvailableGroup(
            jid="g2",
            name="Group 2",
            last_activity="2026-01-02T00:00:00Z",
            is_registered=False,
        ),
    ]

    write_groups_snapshot("main", is_main=True, groups=groups, _registered_jids={"g1"})

    payload = json.loads((tmp_path / "ipc" / "main" / "available_groups.json").read_text(encoding="utf-8"))
    assert payload["groups"][0]["jid"] == "g1"
    assert payload["groups"][0]["isRegistered"] is True
    assert payload["groups"][1]["jid"] == "g2"
    assert payload["groups"][1]["isRegistered"] is False
