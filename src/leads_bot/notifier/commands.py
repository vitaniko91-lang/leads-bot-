"""Owner-only command handlers. See spec §9.2.

All commands receive the message object first, then dependencies (factory,
client, pipeline, profile_path) injected by main.py via partials.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import BotState, Lead, Response
from leads_bot.drafter.profile import load_profile
from leads_bot.sources.service import (
    InvalidLink,
    InvalidRegion,
    SourceAlreadyExists,
    SourceNotFound,
    add_source_from_link,
    list_sources,
    pause_source,
    resume_source,
)

_QUIET_RE = re.compile(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$")


# ──────────────────────────── /stats ────────────────────────────

async def cmd_stats(message, factory: async_sessionmaker) -> None:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with factory() as session:
        leads_today = (await session.execute(
            select(func.count(Lead.id)).where(Lead.posted_at >= today)
        )).scalar_one()
        sent_today = (await session.execute(
            select(func.count(Response.id)).where(
                Response.status == "sent", Response.sent_at >= today,
            )
        )).scalar_one()
        replied_today = (await session.execute(
            select(func.count(Response.id)).where(
                Response.client_replied.is_(True), Response.sent_at >= today,
            )
        )).scalar_one()
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        paused = bs.paused if bs else False

    text = (
        f"📊 За сегодня\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Лидов получено: {leads_today}\n"
        f"Отправлено: {sent_today}\n"
        f"Ответов клиентов: {replied_today}\n"
        f"Бот: {'⏸ на паузе' if paused else '▶ работает'}"
    )
    await message.answer(text)


# ──────────────────────────── /sources ────────────────────────────

async def cmd_sources(message, factory: async_sessionmaker) -> None:
    rows = await list_sources(factory)
    if not rows:
        await message.answer(
            "Нет источников. Добавь: /sources add @username <region> <lang>"
        )
        return
    lines = ["📡 Источники:"]
    for r in rows:
        marker = "▶" if r.status == "active" else "⏸"
        lines.append(
            f"{marker} #{r.id} · {r.title} · {r.region}/{r.language} · {r.status}"
        )
    await message.answer("\n".join(lines))


async def cmd_sources_add(message, factory: async_sessionmaker, client) -> None:
    """Format: /sources add <link> <region> <language>"""
    parts = (message.text or "").split()
    if len(parts) != 5 or parts[1] != "add":
        await message.answer(
            "Usage: /sources add <link> <region> <language>\n"
            "Example: /sources add @design_jobs_ua ua uk\n"
            "Allowed regions: ua | cis_ex_ru | eu | en_global"
        )
        return
    _, _, link, region, language = parts
    try:
        src = await add_source_from_link(
            factory, client=client, link=link, region=region, language=language,
        )
    except InvalidRegion as e:
        await message.answer(f"❌ {e}")
        return
    except InvalidLink as e:
        await message.answer(f"❌ {e}")
        return
    except SourceAlreadyExists as e:
        await message.answer(f"⚠️ {e}")
        return
    except Exception as e:
        logger.exception(f"Failed to resolve link {link}: {e}")
        await message.answer(f"❌ Не удалось добавить: {e}")
        return
    await message.answer(
        f"✅ Добавлен #{src.id}: {src.title} ({src.region}/{src.language})"
    )


async def cmd_sources_pause(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] != "pause" or not parts[2].isdigit():
        await message.answer("Usage: /sources pause <id>")
        return
    try:
        await pause_source(factory, int(parts[2]))
    except SourceNotFound as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(f"⏸ Источник {parts[2]} на паузе")


async def cmd_sources_resume(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] != "resume" or not parts[2].isdigit():
        await message.answer("Usage: /sources resume <id>")
        return
    try:
        await resume_source(factory, int(parts[2]))
    except SourceNotFound as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(f"▶ Источник {parts[2]} запущен")


# ──────────────────────────── /pause /resume (global) ────────────────────────────

async def cmd_pause(message, factory: async_sessionmaker) -> None:
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.paused = True
        await session.commit()
    await message.answer(
        "⏸ Бот на паузе. Новые лиды не будут обрабатываться. /resume чтобы вернуть."
    )


async def cmd_resume(message, factory: async_sessionmaker) -> None:
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.paused = False
        await session.commit()
    await message.answer("▶ Бот снова работает.")


# ──────────────────────────── /quiet ────────────────────────────

async def cmd_quiet(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not _QUIET_RE.match(parts[1]):
        await message.answer("Usage: /quiet HH:MM-HH:MM\nExample: /quiet 22:00-09:00")
        return
    spec = parts[1]
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.quiet_hours_override = spec
        await session.commit()
    await message.answer(f"🔕 Quiet hours: {spec}")


# ──────────────────────────── /profile ────────────────────────────

async def cmd_profile(
    message, factory: async_sessionmaker, profile_path: Path
) -> None:
    if not profile_path.exists():
        await message.answer("❌ profile.json missing — see data/profile.example.json")
        return
    p = load_profile(profile_path)
    case_lines = "\n".join(
        f"  • {c.title} ({', '.join(c.tags)})" for c in p.cases[:5]
    )
    text = (
        f"👤 Profile\n"
        f"━━━━━━━━━━━━━\n"
        f"Name: {p.name}\n"
        f"Portfolio: {p.portfolio_url}\n"
        f"Telegram: {p.telegram}\n"
        f"Rate: ${p.min_rate_usd_per_hour}/hr\n"
        f"Tone: {p.tone}\n"
        f"Payment: {', '.join(p.payment_methods)}\n"
        f"Cases ({len(p.cases)}):\n{case_lines}"
    )
    await message.answer(text)


# ──────────────────────────── /templates (stub) ────────────────────────────

async def cmd_templates(message, factory: async_sessionmaker) -> None:
    await message.answer(
        "📝 Шаблоны появятся в Iter 4 (A/B testing).\n"
        "Сейчас используется один Sonnet-промпт из drafter/prompts.py."
    )


# ──────────────────────────── /draft <id> retry ────────────────────────────

async def cmd_draft_retry(message, factory: async_sessionmaker, pipeline) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or parts[2] != "retry":
        await message.answer("Usage: /draft <lead_id> retry")
        return
    lead_id = int(parts[1])
    try:
        await pipeline.regenerate_draft(lead_id)
    except Exception as e:
        await message.answer(f"❌ Failed to regenerate: {e}")
        return
    await message.answer(f"🔄 Регенерирую драфт для лида #{lead_id}...")
