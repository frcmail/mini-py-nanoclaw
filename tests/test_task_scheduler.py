from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import nanoclaw.task_scheduler as task_scheduler_module
from nanoclaw.task_scheduler import TaskScheduler, compute_next_run
from nanoclaw.types import RegisteredGroup, ScheduledTask


def _make_task(
    schedule_type: str = "interval",
    schedule_value: str = "60000",
    next_run: str | None = None,
    status: str = "active",
    group_folder: str = "main",
) -> ScheduledTask:
    return ScheduledTask(
        id="task-1",
        group_folder=group_folder,
        chat_jid="group@g.us",
        prompt="run",
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        context_mode="isolated",
        next_run=next_run,
        last_run=None,
        last_result=None,
        status=status,
        created_at="2026-01-01T00:00:00.000Z",
    )


def make_interval_task(next_run: str, value_ms: int = 60000) -> ScheduledTask:
    return ScheduledTask(
        id="task-1",
        group_folder="main",
        chat_jid="group@g.us",
        prompt="run",
        schedule_type="interval",
        schedule_value=str(value_ms),
        context_mode="isolated",
        next_run=next_run,
        last_run=None,
        last_result=None,
        status="active",
        created_at="2026-01-01T00:00:00.000Z",
    )


def test_compute_next_run_interval_anchor() -> None:
    scheduled = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    task = make_interval_task(scheduled)
    next_run = compute_next_run(task)
    assert next_run is not None
    expected = datetime.fromisoformat(scheduled.replace("Z", "+00:00")) + timedelta(minutes=1)
    got = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
    assert int(got.timestamp()) == int(expected.timestamp())


def test_compute_next_run_once() -> None:
    task = make_interval_task("2026-01-01T00:00:00.000Z")
    task.schedule_type = "once"
    assert compute_next_run(task) is None


def test_compute_next_run_skips_missed_intervals() -> None:
    ms = 60000
    scheduled = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    task = make_interval_task(scheduled, value_ms=ms)
    next_run = compute_next_run(task)
    assert next_run is not None
    got = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
    assert got > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_scheduler_loop_continues_after_run_once_error(monkeypatch) -> None:
    scheduler = task_scheduler_module.TaskScheduler(
        db=SimpleNamespace(),
        queue=SimpleNamespace(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda task, sessions: None,
        poll_interval_ms=1,
    )

    calls = {"count": 0}
    warnings: list[str] = []

    async def fake_run_once() -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")
        scheduler._stopped = True

    monkeypatch.setattr(scheduler, "run_once", fake_run_once)
    monkeypatch.setattr(task_scheduler_module.logger, "warning", lambda msg, *args: warnings.append(msg % args))

    await scheduler._loop()

    assert calls["count"] == 2
    assert len(warnings) == 1
    assert "task scheduler loop iteration failed" in warnings[0]


# ── compute_next_run additional scenarios ──


def test_compute_next_run_cron() -> None:
    task = _make_task(schedule_type="cron", schedule_value="0 12 * * *")
    result = compute_next_run(task)
    assert result is not None
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    assert dt > datetime.now(timezone.utc)


def test_compute_next_run_invalid_interval_defaults_to_1min() -> None:
    task = _make_task(schedule_type="interval", schedule_value="not-a-number")
    result = compute_next_run(task)
    assert result is not None
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    diff = dt - datetime.now(timezone.utc)
    assert 50 < diff.total_seconds() < 70


def test_compute_next_run_non_positive_interval_defaults_to_1min() -> None:
    task = _make_task(schedule_type="interval", schedule_value="0")
    result = compute_next_run(task)
    assert result is not None
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    diff = dt - datetime.now(timezone.utc)
    assert 50 < diff.total_seconds() < 70


def test_compute_next_run_interval_no_next_run_returns_now() -> None:
    task = _make_task(schedule_type="interval", schedule_value="60000", next_run=None)
    result = compute_next_run(task)
    assert result is not None
    dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
    diff = abs((dt - datetime.now(timezone.utc)).total_seconds())
    assert diff < 2


def test_compute_next_run_unknown_type_returns_none() -> None:
    task = _make_task(schedule_type="unknown", schedule_value="x")
    assert compute_next_run(task) is None


def test_compute_next_run_cron_bad_timezone(monkeypatch) -> None:
    monkeypatch.setattr(task_scheduler_module, "TIMEZONE", "Invalid/NoSuchZone")
    warnings: list[str] = []
    monkeypatch.setattr(task_scheduler_module.logger, "warning", lambda msg, *args: warnings.append(msg % args))
    task = _make_task(schedule_type="cron", schedule_value="0 12 * * *")
    result = compute_next_run(task)
    assert result is not None
    assert any("unknown timezone" in w for w in warnings)


# ── TaskScheduler.run_once ──


class _FakeDB:
    def __init__(self, due_tasks=None, tasks_by_id=None):
        self._due = due_tasks or []
        self._by_id = tasks_by_id or {}
        self.logged_runs: list[object] = []
        self.updated_tasks: dict[str, dict] = {}

    def get_due_tasks(self):
        return self._due

    def get_task_by_id(self, task_id):
        return self._by_id.get(task_id)

    def update_task(self, task_id, **kwargs):
        self.updated_tasks[task_id] = kwargs

    def log_task_run(self, run_log):
        self.logged_runs.append(run_log)

    def update_task_after_run(self, task_id, next_run, summary):
        self.updated_tasks.setdefault(task_id, {})
        self.updated_tasks[task_id]["next_run"] = next_run
        self.updated_tasks[task_id]["summary"] = summary


@pytest.mark.asyncio
async def test_run_once_enqueues_due_active_tasks() -> None:
    task = _make_task(status="active")
    db = _FakeDB(due_tasks=[task], tasks_by_id={"task-1": task})
    enqueued: list[str] = []

    class _FakeQueue:
        def enqueue_task(self, jid, task_id, fn):
            enqueued.append(task_id)

    scheduler = TaskScheduler(
        db=db,
        queue=_FakeQueue(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
    )
    await scheduler.run_once()
    assert enqueued == ["task-1"]


@pytest.mark.asyncio
async def test_run_once_skips_inactive_tasks() -> None:
    task = _make_task(status="active")
    paused = _make_task(status="paused")
    db = _FakeDB(due_tasks=[task], tasks_by_id={"task-1": paused})
    enqueued: list[str] = []

    class _FakeQueue:
        def enqueue_task(self, jid, task_id, fn):
            enqueued.append(task_id)

    scheduler = TaskScheduler(
        db=db,
        queue=_FakeQueue(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
    )
    await scheduler.run_once()
    assert enqueued == []


@pytest.mark.asyncio
async def test_run_once_skips_deleted_tasks() -> None:
    task = _make_task(status="active")
    db = _FakeDB(due_tasks=[task], tasks_by_id={})  # task-1 not found
    enqueued: list[str] = []

    class _FakeQueue:
        def enqueue_task(self, jid, task_id, fn):
            enqueued.append(task_id)

    scheduler = TaskScheduler(
        db=db,
        queue=_FakeQueue(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
    )
    await scheduler.run_once()
    assert enqueued == []


# ── TaskScheduler._run_and_record ──


@pytest.mark.asyncio
async def test_run_and_record_invalid_folder_pauses_task(monkeypatch) -> None:
    task = _make_task(group_folder="INVALID/../../path")
    db = _FakeDB()

    def _bad_resolve(folder):
        raise ValueError("bad folder")

    monkeypatch.setattr(task_scheduler_module, "resolve_group_folder_path", _bad_resolve)

    scheduler = TaskScheduler(
        db=db,
        queue=SimpleNamespace(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
    )
    await scheduler._run_and_record(task)
    assert db.updated_tasks.get("task-1", {}).get("status") == "paused"
    assert len(db.logged_runs) == 1
    assert db.logged_runs[0].status == "error"


@pytest.mark.asyncio
async def test_run_and_record_group_not_found(monkeypatch) -> None:
    task = _make_task(group_folder="main")
    db = _FakeDB()

    monkeypatch.setattr(task_scheduler_module, "resolve_group_folder_path", lambda f: f"/tmp/{f}")

    scheduler = TaskScheduler(
        db=db,
        queue=SimpleNamespace(),
        registered_groups=lambda: {},  # no groups registered
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
    )
    await scheduler._run_and_record(task)
    assert len(db.logged_runs) == 1
    assert db.logged_runs[0].status == "error"
    assert "not found" in (db.logged_runs[0].error or "").lower()


@pytest.mark.asyncio
async def test_run_and_record_success(monkeypatch) -> None:
    task = _make_task(group_folder="main")
    db = _FakeDB()
    group = RegisteredGroup(
        name="Main", folder="main", trigger="@bot",
        added_at="2026-01-01T00:00:00Z", is_main=True,
    )

    monkeypatch.setattr(task_scheduler_module, "resolve_group_folder_path", lambda f: f"/tmp/{f}")

    async def fake_run(t, sessions):
        return "task result"

    scheduler = TaskScheduler(
        db=db,
        queue=SimpleNamespace(),
        registered_groups=lambda: {"jid": group},
        get_sessions=lambda: {},
        run_task_fn=fake_run,
    )
    await scheduler._run_and_record(task)
    assert len(db.logged_runs) == 1
    assert db.logged_runs[0].status == "success"
    assert db.logged_runs[0].result == "task result"


@pytest.mark.asyncio
async def test_run_and_record_task_fn_exception(monkeypatch) -> None:
    task = _make_task(group_folder="main")
    db = _FakeDB()
    group = RegisteredGroup(
        name="Main", folder="main", trigger="@bot",
        added_at="2026-01-01T00:00:00Z", is_main=True,
    )

    monkeypatch.setattr(task_scheduler_module, "resolve_group_folder_path", lambda f: f"/tmp/{f}")

    async def fail_run(t, sessions):
        raise RuntimeError("task failed")

    scheduler = TaskScheduler(
        db=db,
        queue=SimpleNamespace(),
        registered_groups=lambda: {"jid": group},
        get_sessions=lambda: {},
        run_task_fn=fail_run,
    )
    await scheduler._run_and_record(task)
    assert len(db.logged_runs) == 1
    assert db.logged_runs[0].status == "error"
    assert "task failed" in (db.logged_runs[0].error or "")


@pytest.mark.asyncio
async def test_stop_sets_flag_and_awaits() -> None:
    scheduler = TaskScheduler(
        db=SimpleNamespace(get_due_tasks=lambda: []),
        queue=SimpleNamespace(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
        poll_interval_ms=5,
    )

    scheduler.start()
    assert scheduler._runner is not None
    await asyncio.sleep(0.02)
    await scheduler.stop()
    assert scheduler._stopped is True


@pytest.mark.asyncio
async def test_stop_cancels_runner() -> None:
    scheduler = TaskScheduler(
        db=SimpleNamespace(get_due_tasks=lambda: []),
        queue=SimpleNamespace(),
        registered_groups=lambda: {},
        get_sessions=lambda: {},
        run_task_fn=lambda t, s: None,
        poll_interval_ms=1000,
    )

    scheduler.start()
    assert scheduler._runner is not None
    runner = scheduler._runner

    await asyncio.sleep(0)
    await scheduler.stop()

    assert runner.cancelled() or runner.done()
