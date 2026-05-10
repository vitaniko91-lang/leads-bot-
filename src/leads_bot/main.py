"""Async entry point — boots Telethon + aiogram + pipeline together."""
import asyncio
import sys
from pathlib import Path

from aiogram import F
from aiogram.types import CallbackQuery
from loguru import logger

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.seed import seed_sources_from_json
from leads_bot.db.session import get_engine, get_session_factory
from leads_bot.drafter.drafter import Drafter
from leads_bot.drafter.profile import load_profile
from leads_bot.listener.client import build_client
from leads_bot.listener.handler import register_listener
from leads_bot.notifier.bot import build_bot, build_dispatcher
from leads_bot.notifier.handlers import handle_callback
from leads_bot.pipeline import Pipeline
from leads_bot.sender.sender import Sender


def _setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/bot.log", rotation="100 MB", retention="7 days", level="INFO")


async def main():
    _setup_logging()
    settings = get_settings()
    logger.info("Starting leads-bot")

    factory = get_session_factory()

    sources_path = Path("data/sources.json")
    if sources_path.exists():
        await seed_sources_from_json(sources_path, factory)
    else:
        logger.warning(
            "data/sources.json not found — only example file present. "
            "Bot will not listen to anything."
        )

    profile_path = Path("data/profile.json")
    if not profile_path.exists():
        logger.error(
            "data/profile.json missing — copy from data/profile.example.json and fill in"
        )
        return
    profile = load_profile(profile_path)

    analyzer = Analyzer()
    drafter = Drafter(profile)
    notif_bot = build_bot()

    user_client = build_client()
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot started for {settings.telegram_phone}")

    sender = Sender(telethon_client=user_client)

    pipeline = Pipeline(
        analyzer=analyzer, drafter=drafter,
        bot=notif_bot, owner_tg_id=settings.owner_tg_id,
    )

    register_listener(user_client, factory, on_new_lead=pipeline.process_new_lead)

    dp = build_dispatcher()

    @dp.callback_query(F.data)
    async def _on_callback(cq: CallbackQuery):
        if cq.from_user.id != settings.owner_tg_id:
            await cq.answer("Не для тебя", show_alert=True)
            return
        await handle_callback(cq, factory, sender)

    polling_task = asyncio.create_task(dp.start_polling(notif_bot))
    telethon_task = asyncio.create_task(user_client.run_until_disconnected())

    logger.info("Bot is up. Listening for new messages.")
    try:
        await asyncio.gather(polling_task, telethon_task)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        await notif_bot.session.close()
        await user_client.disconnect()
        engine = get_engine()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
