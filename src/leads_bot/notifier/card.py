"""Formats a lead card for Telegram + builds inline keyboard. See spec §9.1."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from leads_bot.db.models import Lead, Response

TG_MSG_LIMIT = 4096
ORIGINAL_TEXT_BUDGET = 800
DRAFT_TEXT_BUDGET = 1500

COUNTRY_FLAGS = {
    "ua": "🇺🇦", "by": "🇧🇾", "kz": "🇰🇿", "ge": "🇬🇪", "am": "🇦🇲",
    "eu": "🇪🇺", "us": "🇺🇸", "uk_country": "🇬🇧",
    "ru": "🇷🇺", "unclear": "🌐",
}


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit - 1].rstrip() + "…"


def format_lead_card(lead: Lead, response: Response) -> str:
    flag = COUNTRY_FLAGS.get(lead.client_country or "unclear", "🌐")
    budget = f"~${lead.budget_usd}" if lead.budget_usd else "?"
    lang = (lead.language or "?").upper()
    urgency = lead.urgency or "?"
    project_type = lead.project_type or "?"
    score = lead.relevance_score or 0
    src_title = lead.source.title if lead.source else "?"
    country_label = (lead.client_country or "?").upper()

    original = _truncate(lead.raw_text, ORIGINAL_TEXT_BUDGET)
    draft = _truncate(response.draft_text, DRAFT_TEXT_BUDGET)

    warn = ""
    if lead.client_country == "unclear":
        warn = "\n⚠️ Страна не ясна — уточни в первом сообщении"

    text = f"""🎯 Лид #{lead.id} · score {score}
━━━━━━━━━━━━━━━━━━━━━━
📍 {src_title}
💰 {budget} · 🌐 {lang} · {flag} {country_label} · ⏰ {urgency}
📋 {project_type}{warn}

▎ОРИГИНАЛ
{original}

▎ДРАФТ ОТВЕТА
{draft}"""

    if len(text) > TG_MSG_LIMIT:
        excess = len(text) - TG_MSG_LIMIT + 50
        original = _truncate(lead.raw_text, max(100, ORIGINAL_TEXT_BUDGET - excess))
        text = f"""🎯 Лид #{lead.id} · score {score}
━━━━━━━━━━━━━━━━━━━━━━
📍 {src_title}
💰 {budget} · 🌐 {lang} · {flag} · ⏰ {urgency}
📋 {project_type}{warn}

▎ОРИГИНАЛ
{original}

▎ДРАФТ ОТВЕТА
{draft}"""
    return text


def build_keyboard(response_id: int, source_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data=f"approve:{response_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{response_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Скип", callback_data=f"skip:{response_id}"),
            InlineKeyboardButton(text="🔇 Молчать в канале час", callback_data=f"mute:{source_id}"),
        ],
    ])
