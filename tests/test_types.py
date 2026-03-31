from nanoclaw.types import (
    AdditionalMount,
    ContainerConfig,
    NewMessage,
    RegisteredGroup,
    ScheduledTask,
    TaskRunLog,
)


def test_new_message_defaults() -> None:
    msg = NewMessage(
        id="m1",
        chat_jid="jid@g.us",
        sender="user1",
        sender_name="User",
        content="hello",
        timestamp="2026-01-01T00:00:00Z",
    )
    assert msg.is_from_me is False
    assert msg.is_bot_message is False


def test_registered_group_optional_fields() -> None:
    group = RegisteredGroup(
        name="Test",
        folder="test",
        trigger="@bot",
        added_at="2026-01-01T00:00:00Z",
    )
    assert group.container_config is None
    assert group.requires_trigger is None
    assert group.is_main is None


def test_additional_mount_readonly_default() -> None:
    mount = AdditionalMount(host_path="/data")
    assert mount.readonly is True
    assert mount.container_path is None


def test_container_config_defaults() -> None:
    cfg = ContainerConfig()
    assert cfg.additional_mounts is None
    assert cfg.timeout is None


def test_scheduled_task_all_fields() -> None:
    task = ScheduledTask(
        id="t1",
        group_folder="main",
        chat_jid="jid@g.us",
        prompt="run daily",
        schedule_type="cron",
        schedule_value="0 8 * * *",
        context_mode="group",
        next_run="2026-01-02T08:00:00Z",
        last_run=None,
        last_result=None,
        status="active",
        created_at="2026-01-01T00:00:00Z",
    )
    assert task.schedule_type == "cron"
    assert task.status == "active"


def test_task_run_log_creation() -> None:
    log = TaskRunLog(
        task_id="t1",
        run_at="2026-01-01T08:00:00Z",
        duration_ms=150,
        status="success",
        result="done",
        error=None,
    )
    assert log.duration_ms == 150
    assert log.error is None
