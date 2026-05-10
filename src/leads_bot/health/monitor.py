"""Periodic GetMe health-check with consecutive-failure alerting. See spec §11.2."""
from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.config import get_settings
from leads_bot.db.models import BotState


class HealthMonitor:
    def __init__(
        self, user_client, bot, owner_tg_id: int,
        factory: async_sessionmaker,
    ):
        self._client = user_client
        self._bot = bot
        self._owner = owner_tg_id
        self._factory = factory
        self._settings = get_settings()

    async def check_once(self) -> bool:
        """Run a single GetMe ping, update DB, return True if ok."""
        ok = False
        try:
            await self._client.get_me()
            ok = True
        except Exception as e:
            logger.warning(f"Healthcheck failed: {type(e).__name__}: {e}")

        async with self._factory() as session:
            bs = (await session.execute(
                select(BotState).where(BotState.id == 1)
            )).scalar_one()
            if ok:
                bs.consecutive_health_fails = 0
                bs.last_health_ok_at = datetime.utcnow()
                await session.commit()
                return True
            bs.consecutive_health_fails += 1
            fails = bs.consecutive_health_fails
            threshold = self._settings.healthcheck_failure_threshold
            await session.commit()

        if fails >= threshold:
            try:
                await self._bot.send_message(
                    self._owner,
                    f"⚠️ Healthcheck: {fails} consecutive failures.\n"
                    f"Userbot may be disconnected — check VPS/logs.",
                )
            except Exception as e:
                logger.exception(f"Failed to alert owner: {e}")
            async with self._factory() as s2:
                bs2 = (await s2.execute(
                    select(BotState).where(BotState.id == 1)
                )).scalar_one()
                bs2.consecutive_health_fails = 0
                await s2.commit()
        return False

    async def run_forever(self) -> None:
        interval = self._settings.healthcheck_interval_sec
        logger.info(f"Health monitor started (interval={interval}s)")
        while True:
            try:
                await self.check_once()
            except Exception as e:
                logger.exception(f"Healthcheck loop iteration failed: {e}")
            await asyncio.sleep(interval)
