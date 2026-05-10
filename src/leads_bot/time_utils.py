"""Quiet-hours and timezone helpers. Pure functions — no I/O, no DB."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def parse_window(spec: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Parse 'HH:MM-HH:MM' into ((sh, sm), (eh, em))."""
    a, b = spec.split("-")
    sh, sm = a.split(":")
    eh, em = b.split(":")
    return (int(sh), int(sm)), (int(eh), int(em))


def _hm_to_minutes(h: int, m: int) -> int:
    return h * 60 + m


def is_in_quiet_window(
    now: datetime, start: tuple[int, int], end: tuple[int, int]
) -> bool:
    """Return True if `now` is inside the quiet window.

    Window is half-open [start, end). Supports overnight windows where end < start
    (e.g. 23:00-08:00).
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    cur = _hm_to_minutes(now.hour, now.minute)
    s = _hm_to_minutes(*start)
    e = _hm_to_minutes(*end)
    if s == e:
        return False
    if s < e:
        return s <= cur < e
    return cur >= s or cur < e


def next_quiet_end(
    now: datetime, start: tuple[int, int], end: tuple[int, int]
) -> datetime:
    """Return the next datetime when quiet hours end (i.e. when digest fires)."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    candidate = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def now_in_tz(tz_name: str) -> datetime:
    """Return current time as an aware datetime in the given IANA tz."""
    return datetime.now(ZoneInfo(tz_name))
