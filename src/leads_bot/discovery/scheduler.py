"""APScheduler-driven weekly discovery scan + Sunday digest send."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.discovery.digest import DigestRenderer
from leads_bot.discovery.queries import all_queries
from leads_bot.discovery.repo import DiscoveryRepo
from leads_bot.discovery.searcher import DiscoverySearcher


class DiscoveryScheduler:
    """Runs:
    - `scan_now()` Wednesday 03:00 in `timezone` — uses Telethon to search.
    - `send_digest_now()` Sunday 10:00 in `timezone` — sends digest to owner.
    """

    def __init__(
        self,
        searcher: DiscoverySearcher,
        factory: async_sessionmaker,
        bot,
        owner_tg_id: int,
        timezone: str = "Asia/Bangkok",
    ):
        self._searcher = searcher
        self._factory = factory
        self._bot = bot
        self._owner = owner_tg_id
        self._tz = timezone
        self._scheduler = AsyncIOScheduler(timezone=timezone)

    async def scan_now(self) -> int:
        """Run all queries, persist new candidates. Returns insertion count."""
        logger.info("Discovery: starting weekly scan")
        raws = await self._searcher.run_all(list(all_queries()))
        async with self._factory() as session:
            inserted = await DiscoveryRepo(session).upsert_pending(raws)
        logger.info(f"Discovery: scan inserted {inserted} new candidates")
        return inserted

    async def send_digest_now(self) -> None:
        logger.info("Discovery: sending weekly digest")
        async with self._factory() as session:
            messages = await DigestRenderer(session).render(limit=10)
        for msg in messages:
            try:
                await self._bot.send_message(
                    self._owner, msg["text"],
                    reply_markup=msg["keyboard"],
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as e:
                logger.exception(f"Discovery: failed to send digest msg: {e}")

    def start(self) -> None:
        self._scheduler.add_job(
            self.scan_now,
            trigger=CronTrigger(day_of_week="wed", hour=3, minute=0, timezone=self._tz),
            id="discovery_scan_weekly",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self.send_digest_now,
            trigger=CronTrigger(day_of_week="sun", hour=10, minute=0, timezone=self._tz),
            id="discovery_digest_weekly",
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(f"Discovery scheduler started (tz={self._tz})")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
