"""Callback handlers for inline keyboard. See spec §6.4."""
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Response, Source


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
        await callback.answer(
            "✏️ Редактирование появится в Итерации 2. Пока — скип или апрув.",
            show_alert=True,
        )

    else:
        await callback.answer("Unknown action")
