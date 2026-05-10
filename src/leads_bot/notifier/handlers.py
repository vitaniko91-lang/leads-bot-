"""Callback handlers for inline keyboard. See spec §6.4 + §6.6."""
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Response, Source
from leads_bot.discovery.repo import DiscoveryRepo

CLIENT_STATUS_MAP = {
    "reply_in_dialog": "in_dialog",
    "reply_in_work": "in_work",
    "reply_rejected": "rejected",
}


async def handle_callback(callback, session_factory: async_sessionmaker, sender) -> None:
    """Single dispatch for approve/skip/mute/edit callbacks.

    `edit` is a stub in Iteration 1 — full state machine in Iteration 2.
    """
    data = callback.data or ""
    try:
        action, target_id_s = data.split(":", 1)
        target_id = int(target_id_s)
    except ValueError:
        await callback.answer("Bad callback")
        return

    if action == "approve":
        async with session_factory() as session:
            resp = (await session.execute(
                select(Response).where(Response.id == target_id)
            )).scalar_one_or_none()
            if not resp:
                await callback.answer("Response not found")
                return
            resp.status = "approved"
            await session.commit()
            await callback.answer("✅ В очереди на отправку")
            try:
                await sender.send(session, target_id)
            except Exception as e:
                logger.exception(f"Sender failed for {target_id}: {e}")

    elif action == "skip":
        async with session_factory() as session:
            resp = (await session.execute(
                select(Response).where(Response.id == target_id)
            )).scalar_one()
            resp.status = "skipped"
            await session.commit()
        await callback.answer("❌ Скип")
        try:
            await callback.message.delete()
        except Exception:
            pass

    elif action == "mute":
        async with session_factory() as session:
            src = (await session.execute(
                select(Source).where(Source.id == target_id)
            )).scalar_one()
            src.muted_until = datetime.utcnow() + timedelta(hours=1)
            await session.commit()
        await callback.answer("🔇 Канал заглушён на 1 час")

    elif action == "edit":
        # Iter 2: this branch is unreachable — the FSM router (registered
        # earlier in main.py) catches `edit:*` before this fallback handler.
        # Kept as a no-op for safety.
        await callback.answer()

    elif action == "discover_add":
        async with session_factory() as session:
            try:
                src = await DiscoveryRepo(session).approve(target_id)
            except ValueError:
                await callback.answer("Кандидат не найден")
                return
        await callback.answer(f"✅ Добавлен: {src.title}")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif action == "discover_reject":
        async with session_factory() as session:
            await DiscoveryRepo(session).reject(target_id)
        await callback.answer("❌ Не предлагать снова")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    elif action in CLIENT_STATUS_MAP:
        new_status = CLIENT_STATUS_MAP[action]
        async with session_factory() as session:
            resp = (await session.execute(
                select(Response).where(Response.id == target_id)
            )).scalar_one_or_none()
            if not resp:
                await callback.answer("Response not found")
                return
            resp.client_status = new_status
            await session.commit()
        await callback.answer(f"Помечено: {new_status}")
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    else:
        await callback.answer("Unknown action")
