"""One-shot ad-hoc discovery: scan now + send digest to owner.

Usage (with the main bot stopped):
    uv run python scripts/run_discovery_once.py

The digest arrives in the owner's Telegram with [Add]/[Reject] buttons.
Callbacks are persisted in Telegram, so they will be handled correctly
after you restart the main bot.

Exit codes:
    0 — scan completed (regardless of insertion count)
    1 — bootstrap failure (config, DB, Telethon, or aiogram error)
"""
from __future__ import annotations

import asyncio
import sys

from loguru import logger

from leads_bot.config import get_settings
from leads_bot.db.session import get_engine, get_session_factory
from leads_bot.discovery.scheduler import DiscoveryScheduler
from leads_bot.discovery.searcher import DiscoverySearcher
from leads_bot.listener.client import build_client
from leads_bot.notifier.bot import build_bot


async def run() -> int:
    settings = get_settings()

    engine = get_engine()
    factory = get_session_factory()

    user_client = build_client()
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot started for {settings.telegram_phone}")

    notif_bot = build_bot()

    searcher = DiscoverySearcher(
        user_client, sleep_seconds=2, limit_per_query=20,
    )
    scheduler = DiscoveryScheduler(
        searcher=searcher, factory=factory, bot=notif_bot,
        owner_tg_id=settings.owner_tg_id, timezone=settings.timezone,
    )

    try:
        inserted = await scheduler.scan_now()
        logger.info(f"scan_now inserted {inserted} candidates")
        await scheduler.send_digest_now()
        logger.info("digest sent")
    finally:
        await user_client.disconnect()
        await notif_bot.session.close()
        await engine.dispose()

    return inserted


def main() -> None:
    try:
        n = asyncio.run(run())
        print(f"OK: {n} new candidates persisted, digest sent.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Discovery one-shot failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
