import json

from nanoclaw.sender_allowlist import (
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
