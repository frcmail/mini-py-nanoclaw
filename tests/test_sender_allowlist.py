import json

import nanoclaw.sender_allowlist as allowlist_module
from nanoclaw.sender_allowlist import (
    SenderAllowlistConfig,
    is_sender_allowed,
    is_trigger_allowed,
    load_sender_allowlist,
    should_drop_message,
)


def test_sender_allowlist_defaults(tmp_path) -> None:
    cfg = load_sender_allowlist(tmp_path / "missing.json")
    assert cfg.default.allow == "*"
    assert cfg.default.mode == "trigger"


def test_sender_allowlist_custom_rules(tmp_path) -> None:
    path = tmp_path / "sender-allowlist.json"
    path.write_text(
        json.dumps(
            {
                "default": {"allow": ["alice"], "mode": "drop"},
                "chats": {"g1": {"allow": ["bob"], "mode": "trigger"}},
                "logDenied": False,
            }
        ),
        encoding="utf-8",
    )

    cfg = load_sender_allowlist(path)

    assert should_drop_message("unknown", cfg) is True
    assert is_sender_allowed("unknown", "alice", cfg) is True
    assert is_sender_allowed("unknown", "eve", cfg) is False

    assert should_drop_message("g1", cfg) is False
    assert is_trigger_allowed("g1", "bob", cfg) is True
    assert is_trigger_allowed("g1", "eve", cfg) is False


# ── Error paths ──


def test_load_invalid_json_returns_default(tmp_path, monkeypatch) -> None:
    _reset_cache(monkeypatch)
    path = tmp_path / "bad.json"
    path.write_text("NOT JSON {{{", encoding="utf-8")
    warnings: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "warning", lambda msg, *a: warnings.append(msg % a))
    cfg = load_sender_allowlist(path)
    assert cfg.default.allow == "*"
    assert any("invalid JSON" in w for w in warnings)


def test_load_invalid_default_entry_returns_default(tmp_path, monkeypatch) -> None:
    _reset_cache(monkeypatch)
    path = tmp_path / "bad_default.json"
    path.write_text(json.dumps({"default": {"allow": 123, "mode": "trigger"}}), encoding="utf-8")
    warnings: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "warning", lambda msg, *a: warnings.append(msg % a))
    cfg = load_sender_allowlist(path)
    assert cfg.default.allow == "*"
    assert any("invalid default" in w for w in warnings)


def test_load_invalid_chat_entry_skipped(tmp_path, monkeypatch) -> None:
    _reset_cache(monkeypatch)
    path = tmp_path / "bad_chat.json"
    path.write_text(
        json.dumps({
            "default": {"allow": "*", "mode": "trigger"},
            "chats": {
                "good": {"allow": ["alice"], "mode": "trigger"},
                "bad": {"allow": 42, "mode": "invalid"},
            },
        }),
        encoding="utf-8",
    )
    warnings: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "warning", lambda msg, *a: warnings.append(msg % a))
    cfg = load_sender_allowlist(path)
    assert "good" in cfg.chats
    assert "bad" not in cfg.chats
    assert any("skipping invalid" in w for w in warnings)


def test_load_oserror_on_read_returns_default(tmp_path, monkeypatch) -> None:
    _reset_cache(monkeypatch)
    path = tmp_path / "readonly.json"
    path.mkdir()  # directory, not file → OSError on read_text
    warnings: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "warning", lambda msg, *a: warnings.append(msg % a))
    cfg = load_sender_allowlist(path)
    assert cfg.default.allow == "*"
    assert any("cannot read" in w for w in warnings)


# ── Cache behavior ──


def test_cache_hit_returns_same_result(tmp_path, monkeypatch) -> None:
    _reset_cache(monkeypatch)
    # Use the global cache path
    path = tmp_path / "allowlist.json"
    path.write_text(
        json.dumps({"default": {"allow": ["user1"], "mode": "trigger"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(allowlist_module, "SENDER_ALLOWLIST_PATH", path)

    cfg1 = load_sender_allowlist()
    cfg2 = load_sender_allowlist()
    assert cfg1 is cfg2  # exact same object from cache
    assert cfg1.default.allow == ["user1"]


# ── is_trigger_allowed logging ──


def test_is_trigger_allowed_denied_logs_debug(monkeypatch) -> None:
    cfg = SenderAllowlistConfig()
    cfg.default.allow = ["alice"]
    cfg.log_denied = True

    debug_msgs: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "debug", lambda msg, *a: debug_msgs.append(msg % a))

    result = is_trigger_allowed("chat1", "bob", cfg)
    assert result is False
    assert any("trigger denied" in m for m in debug_msgs)


def test_is_trigger_allowed_no_log_when_log_denied_false(monkeypatch) -> None:
    cfg = SenderAllowlistConfig()
    cfg.default.allow = ["alice"]
    cfg.log_denied = False

    debug_msgs: list[str] = []
    monkeypatch.setattr(allowlist_module.logger, "debug", lambda msg, *a: debug_msgs.append(msg % a))

    result = is_trigger_allowed("chat1", "bob", cfg)
    assert result is False
    assert len(debug_msgs) == 0


# ── should_drop_message ──


def test_should_drop_message_drop_mode() -> None:
    from nanoclaw.sender_allowlist import ChatAllowlistEntry

    cfg = SenderAllowlistConfig()
    cfg.chats["dropme"] = ChatAllowlistEntry(allow="*", mode="drop")
    assert should_drop_message("dropme", cfg) is True
    assert should_drop_message("other", cfg) is False  # default is "trigger"


def _reset_cache(monkeypatch):
    monkeypatch.setattr(allowlist_module, "_allowlist_cache", None)
    monkeypatch.setattr(allowlist_module, "_allowlist_mtime", 0.0)
