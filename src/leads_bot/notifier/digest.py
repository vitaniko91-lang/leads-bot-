"""Morning digest builder + sender. See spec §9.3."""
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from leads_bot.db.models import BotState, Response

TG_MSG_LIMIT = 4096
MAX_LINES = 30


def build_digest_text(rows) -> str:
    n = len(rows)
    if n == 0:
        return "🌅 Доброе утро. За ночь ничего нового."

    lines = [f"🌅 Доброе утро. За ночь: {n} лид{'' if n == 1 else 'ов'}"]
    sorted_rows = sorted(
        rows, key=lambda r: (r.lead.relevance_score or 0), reverse=True,
    )
    for r in sorted_rows[:MAX_LINES]:
        score = r.lead.relevance_score or 0
        ptype = r.lead.project_type or "?"
        budget = f"${r.lead.budget_usd}" if r.lead.budget_usd else "?"
        lines.append(f"• #{r.id} score {score} — {ptype}, {budget}")
    if n > MAX_LINES:
        lines.append(f"…и ещё {n - MAX_LINES}. Открой /stats для деталей.")
    text = "\n".join(lines)
    return text[:TG_MSG_LIMIT]


async def collect_pending_digest_responses(
    factory: async_sessionmaker,
) -> list[Response]:
    async with factory() as session:
        rows = (await session.execute(
            select(Response)
            .options(selectinload(Response.lead))
            .where(Response.status == "pending_digest")
            .order_by(Response.id)
        )).scalars().all()
        for r in rows:
            session.expunge(r)
        return list(rows)


async def run_morning_digest(
    factory: async_sessionmaker, bot, owner_tg_id: int,
) -> None:
    """Send digest to owner; promote each pending_digest → drafted."""
    rows = await collect_pending_digest_responses(factory)
    text = build_digest_text(rows)
    try:
        await bot.send_message(owner_tg_id, text, disable_web_page_preview=True)
    except Exception as e:
        logger.exception(f"Digest send failed: {e}")
        return

    if rows:
        async with factory() as session:
            ids = [r.id for r in rows]
            db_rows = (await session.execute(
                select(Response).where(Response.id.in_(ids))
            )).scalars().all()
            for r in db_rows:
                r.status = "drafted"
            await session.commit()

    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.last_digest_at = datetime.utcnow()
        await session.commit()

    logger.info(f"Digest sent ({len(rows)} leads)")
