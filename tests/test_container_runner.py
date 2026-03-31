import sys

import pytest

import nanoclaw.container_runner as container_runner_module
from nanoclaw.container_runner import ContainerInput, run_container_agent
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
        command=f"{sys.executable} -c 'import time; time.sleep(0.2)'",
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
