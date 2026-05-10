"""KPI aggregations for /api/stats."""
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.schemas import HourBucket, StatsResponse
from leads_bot.db.models import Lead, Response

Period = Literal["today", "week", "month"]


def _period_start(period: Period, now: datetime) -> datetime:
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    raise ValueError(period)


async def compute_stats(session: AsyncSession, period: Period) -> StatsResponse:
    now = datetime.utcnow()
    start = _period_start(period, now)

    leads_total = (
        await session.execute(
            select(func.count(Lead.id)).where(Lead.posted_at >= start)
        )
    ).scalar_one()

    sent_count = (
        await session.execute(
            select(func.count(Response.id))
            .where(Response.status == "sent", Response.sent_at >= start)
        )
    ).scalar_one()

    reply_count = (
        await session.execute(
            select(func.count(Response.id))
            .where(Response.client_replied.is_(True), Response.sent_at >= start)
        )
    ).scalar_one()

    conv = (reply_count / sent_count * 100.0) if sent_count else 0.0

    rows = (
        await session.execute(
            select(
                func.strftime("%Y-%m-%d %H:00:00", Lead.posted_at).label("hour"),
                func.count(Lead.id).label("c"),
            )
            .where(Lead.posted_at >= start)
            .group_by("hour")
            .order_by("hour")
        )
    ).all()
    by_hour = [
        HourBucket(hour=datetime.fromisoformat(row.hour), count=row.c)
        for row in rows
    ]

    return StatsResponse(
        period=period,
        leads_total=leads_total,
        sent_count=sent_count,
        reply_count=reply_count,
        conversion_pct=round(conv, 2),
        by_hour=by_hour,
    )
