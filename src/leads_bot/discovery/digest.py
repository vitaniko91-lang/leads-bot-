"""Renders the Sunday digest of pending discovery candidates."""
from typing import TypedDict

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.db.models import DiscoveryCandidate
from leads_bot.discovery.repo import DiscoveryRepo

REGION_FLAGS = {
    "ua": "🇺🇦", "cis_ex_ru": "🌍", "eu": "🇪🇺", "en_global": "🌐",
}


def _humanize(n: int | None) -> str:
    if not n:
        return "?"
    if n >= 1000:
        return f"{n / 1000:.1f}K"
    return str(n)


def format_candidate_line(c: DiscoveryCandidate) -> str:
    flag = REGION_FLAGS.get(c.predicted_region or "", "🌐")
    members = _humanize(c.member_count)
    desc_short = (c.description or "").strip().replace("\n", " ")
    if len(desc_short) > 120:
        desc_short = desc_short[:117] + "..."

    return (
        f"{flag} <b>{c.title}</b>\n"
        f"👥 {members} · {c.predicted_region or '?'} · {c.language or '?'}\n"
        f"🔎 query: {c.matched_query or '?'}\n"
        f"{desc_short}"
    )


def build_discovery_keyboard(candidate_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Add", callback_data=f"discover_add:{candidate_id}"),
        InlineKeyboardButton(text="❌ Reject", callback_data=f"discover_reject:{candidate_id}"),
    ]])


class DigestMessage(TypedDict):
    text: str
    keyboard: InlineKeyboardMarkup | None


class DigestRenderer:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def render(self, limit: int = 10) -> list[DigestMessage]:
        candidates = await DiscoveryRepo(self._s).pending(limit=limit)
        if not candidates:
            return [{
                "text": "🔍 Discovery: нет новых каналов на этой неделе.",
                "keyboard": None,
            }]

        header: DigestMessage = {
            "text": (
                f"🔍 Discovery: найдено {len(candidates)} новых каналов.\n"
                "Жми Add, чтобы подключить, или Reject — больше не предлагать."
            ),
            "keyboard": None,
        }
        items: list[DigestMessage] = [
            {
                "text": format_candidate_line(c),
                "keyboard": build_discovery_keyboard(c.id),
            }
            for c in candidates
        ]
        return [header, *items]
