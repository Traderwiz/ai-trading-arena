from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


EASTERN_TZ = ZoneInfo("America/Toronto")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(EASTERN_TZ)


def format_timestamp_eastern(value: str | None, fallback: str = "") -> str:
    parsed = parse_timestamp(value)
    if parsed is None:
        return fallback
    return parsed.strftime("%Y-%m-%d %I:%M:%S %p %Z")
