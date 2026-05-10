"""Background asyncio loops: morning digest, healthcheck, rate-limit rotation.

Why no APScheduler: the three loops are simple wall-clock waits that don't need
a scheduler library. Each loop lives in its own task and respects KeyboardInterrupt.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.config import get_settings
from leads_bot.db.models import BotState
from leads_bot.health.monitor import HealthMonitor
from leads_bot.notifier.digest import run_morning_digest
from leads_bot.sender.rate_limiter import RateLimiter


async def digest_loop(factory: async_sessionmaker, bot, owner_tg_id: int) -> None:
    """Fire `run_morning_digest` once at quiet-end every day."""
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    while True:
        try:
            dh, dm = settings.digest_time_hm
            now = datetime.now(tz)
            target = now.replace(hour=dh, minute=dm, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info(f"Next digest at {target.isoformat()} (in {int(wait)}s)")
            await asyncio.sleep(wait)
            if settings.quiet_hours_enabled:
                await run_morning_digest(factory, bot=bot, owner_tg_id=owner_tg_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Digest loop iteration failed: {e}")
            await asyncio.sleep(60)


async def rotation_loop(factory: async_sessionmaker) -> None:
    """Hourly rate_limits cleanup."""
    rl = RateLimiter()
    while True:
        try:
            async with factory() as session:
                deleted = await rl.rotate_old_records(session)
                bs = (await session.execute(
                    select(BotState).where(BotState.id == 1)
                )).scalar_one()
                bs.last_rate_limit_rotation_at = datetime.utcnow()
                await session.commit()
            if deleted:
                logger.info(f"Rotation deleted {deleted} rate_limits rows")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Rotation loop iteration failed: {e}")
        await asyncio.sleep(3600)


async def start_background_tasks(
    factory: async_sessionmaker,
    user_client,
    bot,
    owner_tg_id: int,
) -> list[asyncio.Task]:
    """Spawn digest + health + rotation tasks. Returns the task handles."""
    monitor = HealthMonitor(user_client, bot, owner_tg_id, factory)
    tasks = [
        asyncio.create_task(digest_loop(factory, bot, owner_tg_id), name="digest"),
        asyncio.create_task(monitor.run_forever(), name="health"),
        asyncio.create_task(rotation_loop(factory), name="rotation"),
    ]
    logger.info(f"Started {len(tasks)} background tasks")
    return tasks
