from __future__ import annotations

import importlib

from nanoclaw.config import _as_bool, _as_int


def test_as_bool_true_values() -> None:
    for v in ["1", "true", "yes", "on", "True", "YES"]:
        assert _as_bool(v) is True


def test_as_bool_false_values() -> None:
    assert _as_bool(None) is False
    assert _as_bool("0") is False
    assert _as_bool("false") is False
    assert _as_bool("no") is False


def test_as_bool_default() -> None:
    assert _as_bool(None, default=True) is True


def test_as_int_valid() -> None:
    assert _as_int("42", 0) == 42
    assert _as_int("-1", 0) == -1


def test_as_int_invalid() -> None:
    assert _as_int("abc", 10) == 10
    assert _as_int(None, 5) == 5


def test_trigger_pattern_matches() -> None:
    from nanoclaw.config import TRIGGER_PATTERN
    assert TRIGGER_PATTERN.search("@Andy hello") is not None


def test_trigger_pattern_no_match() -> None:
    from nanoclaw.config import TRIGGER_PATTERN
    assert TRIGGER_PATTERN.search("hello @Bob") is None


def test_container_timeout_clamped_lower_bound(monkeypatch) -> None:
    import nanoclaw.config as config_module

    monkeypatch.setenv("CONTAINER_TIMEOUT", "-1")
    reloaded = importlib.reload(config_module)
    assert reloaded.CONTAINER_TIMEOUT == 1000


def test_container_timeout_clamped_upper_bound(monkeypatch) -> None:
    import nanoclaw.config as config_module

    monkeypatch.setenv("CONTAINER_TIMEOUT", "999999999")
    reloaded = importlib.reload(config_module)
    assert reloaded.CONTAINER_TIMEOUT == 3600000
