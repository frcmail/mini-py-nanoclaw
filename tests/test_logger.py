import logging

from nanoclaw.logger import _resolve_level, get_logger


def test_resolve_level_defaults_to_info(monkeypatch) -> None:
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert _resolve_level() == logging.INFO


def test_resolve_level_case_insensitive(monkeypatch) -> None:
    for val in ("debug", "DEBUG", "Debug"):
        monkeypatch.setenv("LOG_LEVEL", val)
        assert _resolve_level() == logging.DEBUG


def test_resolve_level_invalid_falls_back_to_info(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "NONSENSE")
    assert _resolve_level() == logging.INFO


def test_resolve_level_warn_maps_to_warning(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "WARN")
    assert _resolve_level() == logging.WARNING


def test_resolve_level_fatal_maps_to_critical(monkeypatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "FATAL")
    assert _resolve_level() == logging.CRITICAL


def test_get_logger_returns_logger_instance() -> None:
    lg = get_logger("test-nanoclaw-logger")
    assert isinstance(lg, logging.Logger)
    assert lg.name == "test-nanoclaw-logger"


def test_get_logger_no_duplicate_handlers() -> None:
    name = "test-nanoclaw-dup-check"
    lg1 = get_logger(name)
    count1 = len(lg1.handlers)
    lg2 = get_logger(name)
    assert lg2 is lg1
    assert len(lg2.handlers) == count1


def test_get_logger_disables_propagation() -> None:
    lg = get_logger("test-no-propagate")
    assert lg.propagate is False
