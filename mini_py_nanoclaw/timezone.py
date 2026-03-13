from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def _parse_iso_timestamp(utc_iso: str) -> datetime:
    # Python does not parse trailing Z in fromisoformat directly.
    normalized = utc_iso.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_local_time(utc_iso: str, tz_name: str) -> str:
    """Convert a UTC ISO timestamp to a display string like `Jan 1, 2024, 1:30 PM`."""
    dt_utc = _parse_iso_timestamp(utc_iso)
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = datetime.now().astimezone().tzinfo or timezone.utc

    local = dt_utc.astimezone(tz)
    hour_12 = local.hour % 12 or 12
    am_pm = "AM" if local.hour < 12 else "PM"
    month = local.strftime("%b")
    return f"{month} {local.day}, {local.year}, {hour_12}:{local.minute:02d} {am_pm}"
