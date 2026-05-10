"""Aggregates leads by (weekday, hour) in the owner's timezone."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.db.models import Lead

WEEKDAY_NAMES_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass
class HotHoursGrid:
    matrix: list[list[int]]   # 7 rows (Mon..Sun) × 24 cols (0..23)
    owner_tz: str

    def total(self) -> int:
        return sum(sum(row) for row in self.matrix)


async def compute_hot_hours(
    session: AsyncSession,
    days: int = 30,
    owner_tz: str = "Asia/Bangkok",
) -> HotHoursGrid:
    """Build a 7×24 matrix of lead counts in the owner's timezone."""
    cutoff_utc = datetime.utcnow() - timedelta(days=days)

    stmt = select(Lead.posted_at).where(Lead.posted_at >= cutoff_utc)
    rows = (await session.execute(stmt)).scalars().all()

    tz = ZoneInfo(owner_tz)
    matrix = [[0] * 24 for _ in range(7)]
    for posted_utc in rows:
        if posted_utc is None:
            continue
        if posted_utc.tzinfo is None:
            aware_utc = posted_utc.replace(tzinfo=timezone.utc)
        else:
            aware_utc = posted_utc.astimezone(timezone.utc)
        local = aware_utc.astimezone(tz)
        weekday = local.weekday()
        matrix[weekday][local.hour] += 1

    return HotHoursGrid(matrix=matrix, owner_tz=owner_tz)


def build_insight(grid: HotHoursGrid) -> str:
    """One-sentence summary of the hottest 3-hour band."""
    if grid.total() == 0:
        return "Hot-hours: no data yet — пока нет лидов для анализа."

    best_day, best_hour, best_score = 0, 0, -1
    for d in range(7):
        for h in range(24):
            window = grid.matrix[d][max(0, h - 1): h + 2]
            score = sum(window)
            if score > best_score:
                best_day, best_hour, best_score = d, h, score

    day_name = WEEKDAY_NAMES_EN[best_day]
    h_lo = max(0, best_hour - 1)
    h_hi = min(23, best_hour + 1)
    return (
        f"Most leads arrive {day_name} {h_lo:02d}:00–{h_hi:02d}:00 "
        f"({grid.owner_tz}). Total in last 30d: {grid.total()}."
    )
