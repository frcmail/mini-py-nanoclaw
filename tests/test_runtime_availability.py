from __future__ import annotations

import sys

import pytest

from nanoclaw import app as app_module
from nanoclaw import container_runner as container_runner_module
from nanoclaw.app import NanoClawApp
from nanoclaw.container_runner import ContainerInput, run_container_agent
from nanoclaw.db import NanoClawDB
from nanoclaw.types import RegisteredGroup


class _FakeProxy:
    def close(self) -> None:
        return None


class _FakeScheduler:
    def __init__(self, **_kwargs) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class _FakeWatcher:
    def __init__(self, _deps) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


@pytest.mark.asyncio
async def test_app_start_background_services_degraded_without_runtime(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "REQUIRE_CONTAINER_RUNTIME", False)
    monkeypatch.setattr(app_module, "ensure_container_runtime_running", lambda required: False)
    monkeypatch.setattr(app_module, "cleanup_orphans", lambda: None)
    monkeypatch.setattr(app_module, "start_credential_proxy", lambda _port, _host: _FakeProxy())
    monkeypatch.setattr(app_module, "TaskScheduler", _FakeScheduler)
    monkeypatch.setattr(app_module, "IpcWatcher", _FakeWatcher)

    app = NanoClawApp(db=NanoClawDB.in_memory())
    await app.start_background_services()
    await app.shutdown()


@pytest.mark.asyncio
async def test_app_start_background_services_strict_runtime_failure(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "REQUIRE_CONTAINER_RUNTIME", True)

    def _raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(app_module, "ensure_container_runtime_running", _raise_runtime_error)

    app = NanoClawApp(db=NanoClawDB.in_memory())
    with pytest.raises(RuntimeError, match="runtime unavailable"):
        await app.start_background_services()


@pytest.mark.asyncio
async def test_run_container_agent_returns_runtime_error_in_strict_mode(monkeypatch) -> None:
    monkeypatch.setattr(container_runner_module, "REQUIRE_CONTAINER_RUNTIME", True)

    def _raise_runtime_error(*_args, **_kwargs):
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(container_runner_module, "ensure_container_runtime_running", _raise_runtime_error)

    group = RegisteredGroup(name="Main", folder="main", trigger="@Andy", added_at="now", is_main=True)
    output = await run_container_agent(
        group,
        ContainerInput(prompt="hello", group_folder="main", chat_jid="local:main", is_main=True),
        command=f"{sys.executable} -m nanoclaw.simple_agent",
    )

    assert output.status == "error"
    assert output.error is not None
    assert "runtime unavailable" in output.error


@pytest.mark.asyncio
async def test_run_container_agent_degraded_mode_still_executes(monkeypatch) -> None:
    monkeypatch.setattr(container_runner_module, "REQUIRE_CONTAINER_RUNTIME", False)
    monkeypatch.setattr(container_runner_module, "ensure_container_runtime_running", lambda required: False)

    group = RegisteredGroup(name="Main", folder="main", trigger="@Andy", added_at="now", is_main=True)
    output = await run_container_agent(
        group,
        ContainerInput(prompt="hello", group_folder="main", chat_jid="local:main", is_main=True),
        command=f"{sys.executable} -m nanoclaw.simple_agent",
    )

    assert output.status == "success"
    assert output.result == "Echo: hello"
