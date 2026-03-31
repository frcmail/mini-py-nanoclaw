from __future__ import annotations

import nanoclaw.timezone as tz_module
from nanoclaw.timezone import _parse_iso_timestamp, _safe_zone_info, format_local_time


def test_parse_iso_timestamp_z_suffix() -> None:
    dt = _parse_iso_timestamp("2024-01-15T12:30:00.000Z")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.hour == 12


def test_parse_iso_timestamp_offset() -> None:
    dt = _parse_iso_timestamp("2024-01-15T12:30:00+05:00")
    assert dt.hour == 7  # converted to UTC


def test_safe_zone_info_valid() -> None:
    tz = _safe_zone_info("UTC")
    assert tz is not None


def test_safe_zone_info_rejects_path_traversal() -> None:
    assert _safe_zone_info("../../etc/passwd") is None
    assert _safe_zone_info("../foo") is None


def test_safe_zone_info_rejects_invalid_chars() -> None:
    assert _safe_zone_info("US;drop table") is None


def test_format_local_time_utc() -> None:
    result = format_local_time("2024-06-15T14:30:00.000Z", "UTC")
    assert "Jun" in result
    assert "2024" in result
    assert "2:30 PM" in result


def test_format_local_time_invalid_tz_falls_back() -> None:
    result = format_local_time("2024-01-15T12:00:00.000Z", "Invalid/Fake")
    # Should not raise, should fall back to local tz
    assert "2024" in result


def test_format_local_time_invalid_tz_logs_warning(monkeypatch) -> None:
    warnings = []
    monkeypatch.setattr(tz_module.logger, "warning", lambda fmt, *args: warnings.append(fmt % args))
    # Clear any cached zone info for this invalid name
    _safe_zone_info.cache_clear()
    format_local_time("2024-01-15T12:00:00.000Z", "Bogus/Nowhere")
    assert any("Bogus/Nowhere" in w for w in warnings)
