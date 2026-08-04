"""Wall-clock formatting for forms and UI.

Contract and phase times are *on-site* wall times (what's written on the contract sheet),
not travel-planning across zones. Storage may be UTC-aware under the hood; these helpers
always present and accept values in the app default timezone so a save without edits is a
no-op and validation compares the same wall clock the planner sees.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def app_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().default_timezone)


def as_wall_clock(value: datetime) -> datetime:
    """Interpret an aware (or naive) datetime as wall clock in the app default timezone."""
    if value.tzinfo is None:
        return value.replace(tzinfo=app_timezone())
    return value.astimezone(app_timezone())


def wall_clock_input(value: datetime | None) -> str:
    """Value for HTML datetime-local inputs (yyyy-mm-ddThh:mm)."""
    if value is None:
        return ""
    return as_wall_clock(value).strftime("%Y-%m-%dT%H:%M")


def wall_clock_display(value: datetime | None, fmt: str = "%d %b %H:%M") -> str:
    """Human-readable wall clock for tables and messages."""
    if value is None:
        return "—"
    return as_wall_clock(value).strftime(fmt)
