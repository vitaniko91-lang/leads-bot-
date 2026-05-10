from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from leads_bot.time_utils import (
    is_in_quiet_window,
    next_quiet_end,
    now_in_tz,
    parse_window,
)


def test_parse_window_normal():
    start, end = parse_window("23:00-08:00")
    assert start == (23, 0)
    assert end == (8, 0)


def test_parse_window_same_day():
    start, end = parse_window("13:00-17:30")
    assert start == (13, 0)
    assert end == (17, 30)


@pytest.mark.parametrize("dt_str,expected", [
    ("2026-05-17 23:30", True),
    ("2026-05-17 02:00", True),
    ("2026-05-17 07:59", True),
    ("2026-05-17 08:00", False),
    ("2026-05-17 08:01", False),
    ("2026-05-17 12:00", False),
    ("2026-05-17 22:59", False),
    ("2026-05-17 23:00", True),
])
def test_is_in_quiet_window_overnight(dt_str, expected):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("UTC"))
    assert is_in_quiet_window(dt, (23, 0), (8, 0)) is expected


def test_is_in_quiet_window_same_day():
    inside = datetime(2026, 5, 17, 12, 30, tzinfo=ZoneInfo("UTC"))
    outside = datetime(2026, 5, 17, 14, 0, tzinfo=ZoneInfo("UTC"))
    assert is_in_quiet_window(inside, (12, 0), (13, 0)) is True
    assert is_in_quiet_window(outside, (12, 0), (13, 0)) is False


def test_next_quiet_end_overnight_before_midnight():
    now = datetime(2026, 5, 17, 23, 30, tzinfo=ZoneInfo("UTC"))
    end = next_quiet_end(now, (23, 0), (8, 0))
    assert end == datetime(2026, 5, 18, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_next_quiet_end_overnight_after_midnight():
    now = datetime(2026, 5, 18, 2, 0, tzinfo=ZoneInfo("UTC"))
    end = next_quiet_end(now, (23, 0), (8, 0))
    assert end == datetime(2026, 5, 18, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_now_in_tz_returns_aware():
    n = now_in_tz("Asia/Bangkok")
    assert n.tzinfo is not None
    assert str(n.tzinfo) == "Asia/Bangkok"
