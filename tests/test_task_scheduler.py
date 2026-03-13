from datetime import datetime, timedelta, timezone

from nanoclaw.task_scheduler import compute_next_run
from nanoclaw.types import ScheduledTask


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
