from __future__ import annotations

import subprocess

import pytest

import nanoclaw.container_runtime as runtime


@pytest.fixture(autouse=True)
def _reset_runtime_cache(monkeypatch):
    monkeypatch.setattr(runtime, "_OPTIONAL_RUNTIME_WARNING_EMITTED", False)
    monkeypatch.setattr(runtime, "_runtime_check_result", None)
    monkeypatch.setattr(runtime, "_runtime_check_time", 0.0)

def test_ensure_runtime_required_failure_raises(monkeypatch) -> None:
    def _fail(*_args, **_kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(runtime.subprocess, "run", _fail)
    logged: list[str] = []
    monkeypatch.setattr(runtime.logger, "error", lambda msg, *args: logged.append(msg % args))

    with pytest.raises(RuntimeError, match="Container runtime is required but unavailable"):
        runtime.ensure_container_runtime_running(required=True)

    assert len(logged) == 1
    assert "runtime check failed" in logged[0]


def test_ensure_runtime_optional_failure_warns_once_and_uses_cache(monkeypatch) -> None:
    calls = {"count": 0}

    def _fail(*_args, **_kwargs):
        calls["count"] += 1
        raise subprocess.CalledProcessError(1, ["docker", "info"])

    monkeypatch.setattr(runtime.subprocess, "run", _fail)
    warnings: list[str] = []
    monkeypatch.setattr(runtime.logger, "warning", lambda msg, *args: warnings.append(msg % args))

    assert runtime.ensure_container_runtime_running(required=False) is False
    assert runtime.ensure_container_runtime_running(required=False) is False

    assert calls["count"] == 1
    assert len(warnings) == 1
    assert "continuing in degraded mode" in warnings[0]


def test_ensure_runtime_success_uses_cache(monkeypatch) -> None:
    calls = {"count": 0}

    def _ok(*_args, **_kwargs):
        calls["count"] += 1
        return subprocess.CompletedProcess(["docker", "info"], 0, stdout="ok", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", _ok)

    assert runtime.ensure_container_runtime_running(required=True) is True
    assert runtime.ensure_container_runtime_running(required=True) is True
    assert calls["count"] == 1


def test_cleanup_orphans_stops_listed_containers(monkeypatch) -> None:
    monkeypatch.setattr(runtime.subprocess, "check_output", lambda *_args, **_kwargs: "nanoclaw-a\n\nnanoclaw-b\n")

    stopped: list[str] = []

    def _stop(args, **_kwargs):
        stopped.append(args[-1])
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(runtime.subprocess, "run", _stop)

    runtime.cleanup_orphans()

    assert stopped == ["nanoclaw-a", "nanoclaw-b"]


def test_cleanup_orphans_logs_when_list_fails(monkeypatch) -> None:
    def _fail(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(["docker", "ps"], timeout=10)

    monkeypatch.setattr(runtime.subprocess, "check_output", _fail)
    warnings: list[str] = []
    monkeypatch.setattr(runtime.logger, "warning", lambda msg, *args: warnings.append(msg % args))

    runtime.cleanup_orphans()

    assert len(warnings) == 1
    assert "failed to list orphaned containers" in warnings[0]
