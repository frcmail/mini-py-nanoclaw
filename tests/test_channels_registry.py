from nanoclaw.channels.registry import (
    get_channel_factory,
    get_registered_channel_names,
    register_channel,
)


def _cleanup_registry(monkeypatch):
    monkeypatch.setattr("nanoclaw.channels.registry._registry", {})


def test_register_and_get_channel_factory(monkeypatch) -> None:
    _cleanup_registry(monkeypatch)

    def factory(opts):
        return None

    register_channel("test-ch", factory)
    assert get_channel_factory("test-ch") is factory


def test_get_channel_factory_missing_returns_none(monkeypatch) -> None:
    _cleanup_registry(monkeypatch)
    assert get_channel_factory("nonexistent") is None


def test_get_registered_channel_names_sorted(monkeypatch) -> None:
    _cleanup_registry(monkeypatch)
    register_channel("zebra", lambda opts: None)
    register_channel("alpha", lambda opts: None)
    register_channel("mid", lambda opts: None)
    assert get_registered_channel_names() == ["alpha", "mid", "zebra"]


def test_register_overwrites_existing(monkeypatch) -> None:
    _cleanup_registry(monkeypatch)

    def first(opts):
        return "first"

    def second(opts):
        return "second"

    register_channel("ch", first)
    register_channel("ch", second)
    assert get_channel_factory("ch") is second


def test_get_registered_channel_names_empty(monkeypatch) -> None:
    _cleanup_registry(monkeypatch)
    assert get_registered_channel_names() == []
