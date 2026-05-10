"""Async entry point — boots Telethon + aiogram + pipeline + background loops."""
import asyncio
import sys
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.seed import seed_sources_from_json
from leads_bot.db.session import ensure_bot_state, get_engine, get_session_factory
from leads_bot.drafter.drafter import Drafter
from leads_bot.drafter.profile import load_profile
from leads_bot.listener.client import build_client
from leads_bot.listener.handler import register_listener
from leads_bot.notifier.bot import build_bot, build_dispatcher
from leads_bot.notifier.commands import (
    cmd_draft_retry,
    cmd_pause,
    cmd_profile,
    cmd_quiet,
    cmd_resume,
    cmd_sources,
    cmd_sources_add,
    cmd_sources_pause,
    cmd_sources_resume,
    cmd_stats,
    cmd_templates,
)
from leads_bot.notifier.edit_flow import (
    cancel_edit,
    confirm_edit,
    receive_edit_text,
    start_edit,
)
from leads_bot.notifier.handlers import handle_callback
from leads_bot.notifier.states import EditStates
from leads_bot.pipeline import Pipeline
from leads_bot.scheduler import start_background_tasks
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


def _build_router(
    factory, user_client, pipeline, sender, profile_path: Path,
) -> Router:
    """Wire commands + edit FSM into a single router."""
    r = Router()

    @r.message(Command("stats"))
    async def _stats(m: Message):
        await cmd_stats(m, factory)

    @r.message(Command("sources"))
    async def _sources(m: Message):
        text = (m.text or "").strip()
        parts = text.split()
        if len(parts) == 1:
            await cmd_sources(m, factory)
        elif len(parts) >= 2 and parts[1] == "add":
            await cmd_sources_add(m, factory, user_client)
        elif len(parts) >= 2 and parts[1] == "pause":
            await cmd_sources_pause(m, factory)
        elif len(parts) >= 2 and parts[1] == "resume":
            await cmd_sources_resume(m, factory)
        else:
            await m.answer(
                "Usage:\n/sources\n/sources add <link> <region> <lang>\n"
                "/sources pause <id>\n/sources resume <id>"
            )

    @r.message(Command("pause"))
    async def _pause(m: Message):
        await cmd_pause(m, factory)

    @r.message(Command("resume"))
    async def _resume(m: Message):
        await cmd_resume(m, factory)

    @r.message(Command("quiet"))
    async def _quiet(m: Message):
        await cmd_quiet(m, factory)

    @r.message(Command("profile"))
    async def _profile(m: Message):
        await cmd_profile(m, factory, profile_path)

    @r.message(Command("templates"))
    async def _templates(m: Message):
        await cmd_templates(m, factory)

    @r.message(Command("draft"))
    async def _draft(m: Message):
        await cmd_draft_retry(m, factory, pipeline)

    @r.message(
        Command("cancel"),
        StateFilter(EditStates.awaiting_text, EditStates.confirming),
    )
    async def _cancel(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("Отменено.")

    # Edit FSM
    @r.callback_query(F.data.startswith("edit:"))
    async def _start_edit(cq: CallbackQuery, state: FSMContext):
        await start_edit(cq, state)

    @r.message(StateFilter(EditStates.awaiting_text), F.text)
    async def _receive_edit(m: Message, state: FSMContext):
        await receive_edit_text(m, state)

    @r.callback_query(F.data.startswith("confirm_edit:"))
    async def _confirm(cq: CallbackQuery, state: FSMContext):
        await confirm_edit(cq, state, factory, sender)

    @r.callback_query(F.data.startswith("cancel_edit:"))
    async def _cancel_edit(cq: CallbackQuery, state: FSMContext):
        await cancel_edit(cq, state, factory, sender)

    # Approve / skip / mute (Iter1 callbacks)
    @r.callback_query(F.data.regexp(r"^(approve|skip|mute):\d+$"))
    async def _legacy(cq: CallbackQuery):
        await handle_callback(cq, factory, sender)

    return r


async def main():
    _setup_logging()
    settings = get_settings()
    logger.info("Starting leads-bot (iter2)")

    factory = get_session_factory()
    await ensure_bot_state(factory)

    sources_path = Path("data/sources.json")
    if sources_path.exists():
        await seed_sources_from_json(sources_path, factory)
    else:
        logger.info(
            "data/sources.json not found — sources will be managed via /sources commands."
        )

    profile_path = Path("data/profile.json")
    if not profile_path.exists():
        logger.error(
            "data/profile.json missing — copy from data/profile.example.json"
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
        factory=factory,
    )

    register_listener(user_client, factory, on_new_lead=pipeline.process_new_lead)

    dp = build_dispatcher()

    @dp.update.outer_middleware()
    async def owner_only(handler, event, data):
        msg = (
            getattr(event, "message", None)
            or getattr(event, "callback_query", None)
        )
        if msg is None:
            return await handler(event, data)
        from_user = getattr(msg, "from_user", None)
        if from_user is not None and from_user.id != settings.owner_tg_id:
            if hasattr(msg, "answer"):
                try:
                    await msg.answer("Не для тебя.")
                except Exception:
                    pass
            return None
        return await handler(event, data)

    router = _build_router(factory, user_client, pipeline, sender, profile_path)
    dp.include_router(router)

    bg_tasks = await start_background_tasks(
        factory, user_client, notif_bot, settings.owner_tg_id,
    )

    polling_task = asyncio.create_task(dp.start_polling(notif_bot))
    telethon_task = asyncio.create_task(user_client.run_until_disconnected())

    logger.info("Bot is up. Listening for new messages.")
    try:
        await asyncio.gather(polling_task, telethon_task, *bg_tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        for t in bg_tasks:
            t.cancel()
        await notif_bot.session.close()
        await user_client.disconnect()
        engine = get_engine()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
