"""Async entry point — boots Telethon + aiogram + pipeline + scheduler."""
import asyncio
import sys
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger
from sqlalchemy import select

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.models import Lead, Response
from leads_bot.db.seed import seed_sources_from_json
from leads_bot.db.seed_templates import seed_templates_from_json
from leads_bot.db.session import ensure_bot_state, get_engine, get_session_factory
from leads_bot.discovery.scheduler import DiscoveryScheduler
from leads_bot.discovery.searcher import DiscoverySearcher
from leads_bot.drafter.drafter import Drafter
from leads_bot.drafter.profile import load_profile
from leads_bot.listener.client import build_client
from leads_bot.listener.client_reply_notifier import ClientReplyNotifier
from leads_bot.listener.dm_handler import register_dm_listener
from leads_bot.listener.handler import register_listener
from leads_bot.notifier.bot import build_bot, build_dispatcher, send_lead_card
from leads_bot.notifier.card import build_keyboard, format_lead_card
from leads_bot.notifier.commands import (
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
from leads_bot.templates.repo import TemplateRepo


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
    factory, user_client, owner_tg_id, profile, notif_bot, sender, profile_path: Path,
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
        # iter4: rebuild drafter+pipeline per-call to bind a fresh TemplateRepo
        parts = (m.text or "").split()
        if len(parts) != 3 or not parts[1].isdigit() or parts[2] != "retry":
            await m.answer("Usage: /draft <lead_id> retry")
            return
        lead_id = int(parts[1])
        async with factory() as session:
            lead = (await session.execute(
                select(Lead).where(Lead.id == lead_id)
            )).scalar_one_or_none()
            if lead is None:
                await m.answer(f"❌ Lead {lead_id} not found")
                return
            await session.refresh(lead, attribute_names=["source"])

            repo = TemplateRepo(session)
            drafter = Drafter(profile, repo)
            try:
                draft = await drafter.draft(
                    lead_text=lead.raw_text,
                    project_type=lead.project_type or "other",
                    client_language=lead.language or "en",
                )
            except Exception as e:
                logger.exception(f"Drafter retry failed for lead {lead_id}: {e}")
                await m.answer(f"❌ Failed to regenerate: {e}")
                return

            response = Response(
                lead_id=lead.id, template_id=draft.template_id,
                author_tg_id_cached=lead.author_tg_id,
                draft_text=draft.text, status="drafted",
                sent_to="dm",
            )
            session.add(response)
            await session.commit()

            card = format_lead_card(lead, response)
            kb = build_keyboard(response_id=response.id, source_id=lead.source.id)
            await send_lead_card(notif_bot, owner_tg_id, card, kb)
        await m.answer(f"🔄 Регенерирован драфт для лида #{lead_id}")

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

    # Approve / skip / mute / discover_* / reply_* (iter1 + iter4 callbacks)
    @r.callback_query(F.data)
    async def _legacy(cq: CallbackQuery):
        await handle_callback(cq, factory, sender)

    return r


async def main():
    _setup_logging()
    settings = get_settings()
    logger.info("Starting leads-bot (iter4 smart)")

    factory = get_session_factory()
    await ensure_bot_state(factory)

    sources_path = Path("data/sources.json")
    if sources_path.exists():
        await seed_sources_from_json(sources_path, factory)
    else:
        logger.info(
            "data/sources.json not found — sources will be managed via /sources commands."
        )

    templates_path = Path("data/templates.json")
    if not templates_path.exists():
        templates_path = Path("data/templates.example.json")
        logger.warning("data/templates.json not found — using example seed")
    if templates_path.exists():
        await seed_templates_from_json(templates_path, factory)

    profile_path = Path("data/profile.json")
    if not profile_path.exists():
        logger.error("data/profile.json missing — copy from data/profile.example.json")
        return
    profile = load_profile(profile_path)

    notif_bot = build_bot()

    user_client = build_client()
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot started for {settings.telegram_phone}")

    sender = Sender(telethon_client=user_client)
    analyzer = Analyzer()

    # iter4: build drafter+pipeline per-incoming-lead so TemplateRepo is bound to a fresh session
    async def _on_new_lead(session, lead, source):
        repo = TemplateRepo(session)
        drafter = Drafter(profile, repo)
        pipeline = Pipeline(
            analyzer=analyzer, drafter=drafter, bot=notif_bot,
            owner_tg_id=settings.owner_tg_id, factory=factory, templates=repo,
        )
        await pipeline.process_new_lead(session, lead, source)

    register_listener(user_client, factory, on_new_lead=_on_new_lead)

    # iter4: DM reply detection
    reply_notifier = ClientReplyNotifier(bot=notif_bot, owner_tg_id=settings.owner_tg_id)
    register_dm_listener(user_client, factory, notifier=reply_notifier)

    # iter4: discovery scheduler (Wed scan + Sun digest)
    discovery_searcher = DiscoverySearcher(
        user_client, sleep_seconds=2, limit_per_query=20,
    )
    discovery = DiscoveryScheduler(
        searcher=discovery_searcher, factory=factory, bot=notif_bot,
        owner_tg_id=settings.owner_tg_id, timezone=settings.timezone,
    )
    discovery.start()

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

    router = _build_router(
        factory, user_client, settings.owner_tg_id, profile, notif_bot, sender,
        profile_path,
    )
    dp.include_router(router)

    bg_tasks = await start_background_tasks(
        factory, user_client, notif_bot, settings.owner_tg_id,
    )

    polling_task = asyncio.create_task(dp.start_polling(notif_bot))
    telethon_task = asyncio.create_task(user_client.run_until_disconnected())

    logger.info("Bot is up. Listening for new messages, DMs, and weekly discovery.")
    try:
        await asyncio.gather(polling_task, telethon_task, *bg_tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        discovery.stop()
        for t in bg_tasks:
            t.cancel()
        await notif_bot.session.close()
        await user_client.disconnect()
        engine = get_engine()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
