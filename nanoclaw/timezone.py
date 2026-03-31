from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("nanoclaw")

_VALID_TZ_RE = re.compile(r"^[A-Za-z0-9/_+\-]{1,64}$")


def _parse_iso_timestamp(utc_iso: str) -> datetime:
    # Python does not parse trailing Z in fromisoformat directly.
    normalized = utc_iso.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@lru_cache(maxsize=64)
def _safe_zone_info(tz_name: str) -> ZoneInfo | None:
    """Validate tz_name format before constructing ZoneInfo to prevent path traversal."""
    if not _VALID_TZ_RE.match(tz_name) or ".." in tz_name:
        return None
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return None


def format_local_time(utc_iso: str, tz_name: str) -> str:
    """Convert a UTC ISO timestamp to a display string like `Jan 1, 2024, 1:30 PM`."""
    dt_utc = _parse_iso_timestamp(utc_iso)
    tz = _safe_zone_info(tz_name)
    if tz is None:
        logger.warning("timezone: invalid or unknown TZ '%s', using local timezone", tz_name)
        tz = datetime.now().astimezone().tzinfo or timezone.utc

    local = dt_utc.astimezone(tz)
    hour_12 = local.hour % 12 or 12
    am_pm = "AM" if local.hour < 12 else "PM"
    month = local.strftime("%b")
    return f"{month} {local.day}, {local.year}, {hour_12}:{local.minute:02d} {am_pm}"
