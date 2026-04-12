from __future__ import annotations

from datetime import datetime, timezone


AGENT_COLORS = {
    "grok": "#FF6B35",
    "deepseek": "#4ECDC4",
    "qwen": "#7B68EE",
    "llama": "#45B7D1",
}

PNL_POSITIVE = "#00C853"
PNL_NEGATIVE = "#FF1744"
THRESHOLD_COLOR = "#FF1744"
STARTING_LINE_COLOR = "#888888"
DISCLAIMER = "This is an experimental AI simulation. No trades are financial advice. For entertainment purposes only."
REFRESH_INTERVAL_MS = 60_000
DEFAULT_INTERVAL_SECONDS = 1800

AGENT_META = {
    "grok": {"display_name": "Grok", "archetype": "The Instigator"},
    "deepseek": {"display_name": "DeepSeek", "archetype": "The Purist"},
    "qwen": {"display_name": "Qwen", "archetype": "The Operator"},
    "llama": {"display_name": "Llama", "archetype": "The Crowd Favorite"},
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ordinal(value: int) -> str:
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def derive_phase(active_count: int, elimination_count: int, configured_phase: str | None = None) -> str:
    if configured_phase:
        return configured_phase
    if active_count <= 1:
        return "Competition Complete"
    if active_count == 2:
        return "Endgame"
    if active_count == 3:
        return "Triangle Game"
    if elimination_count >= 1:
        return "First Blood"
    return "Opening Chaos"


def derive_status(last_loop_completed_at: str | None, interval_seconds: int = DEFAULT_INTERVAL_SECONDS) -> str:
    if not last_loop_completed_at:
        return "PAUSED"
    try:
        last_time = datetime.fromisoformat(last_loop_completed_at.replace("Z", "+00:00"))
    except ValueError:
        return "PAUSED"
    delta = utc_now() - last_time.astimezone(timezone.utc)
    if delta.total_seconds() <= interval_seconds * 2:
        return "LIVE"
    return "PAUSED"
