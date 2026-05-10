"""Hour/day/week limits + antiban delay. See spec §11.1."""
import random
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.config import get_settings
from leads_bot.db.models import RateLimit


class RateLimitExceeded(Exception):
    """Raised when sending would exceed configured limits."""


_WINDOW_DURATIONS = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(days=7),
}


class RateLimiter:
    def __init__(self):
        self._settings = get_settings()

    async def _count(self, session: AsyncSession, window: str) -> int:
        cutoff = datetime.utcnow() - _WINDOW_DURATIONS[window]
        stmt = select(RateLimit).where(
            and_(RateLimit.window == window, RateLimit.window_start >= cutoff)
        )
        rows = (await session.execute(stmt)).scalars().all()
        return sum(r.sent_count for r in rows)

    async def check_and_record(self, session: AsyncSession) -> None:
        """Verify all 3 windows allow one more send, then record it.

        Raises RateLimitExceeded with the window name.
        """
        limits = {
            "hour": self._settings.max_responses_per_hour,
            "day": self._settings.max_responses_per_day,
            "week": self._settings.max_responses_per_week,
        }
        for window, cap in limits.items():
            current = await self._count(session, window)
            if current >= cap:
                raise RateLimitExceeded(
                    f"Limit exceeded for window '{window}': {current}/{cap}"
                )

        now = datetime.utcnow()
        for window in limits:
            session.add(RateLimit(window=window, window_start=now, sent_count=1))
        await session.commit()

    def random_delay_seconds(self) -> int:
        return random.randint(self._settings.send_delay_min, self._settings.send_delay_max)

    async def rotate_old_records(self, session: AsyncSession) -> int:
        """Delete rate_limits rows older than RATE_LIMIT_RETENTION_HOURS.

        Returns number of deleted rows.
        """
        from sqlalchemy import delete
        from loguru import logger

        cutoff = datetime.utcnow() - timedelta(
            hours=self._settings.rate_limit_retention_hours
        )
        result = await session.execute(
            delete(RateLimit).where(RateLimit.window_start < cutoff)
        )
        await session.commit()
        n = result.rowcount or 0
        if n:
            logger.info(
                f"Rotated {n} old rate_limits rows (cutoff={cutoff.isoformat()})"
            )
        return n
