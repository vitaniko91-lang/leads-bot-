"""Formats and sends the 'Лид #N ответил!' notification to owner."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from leads_bot.db.models import Lead, Response


def build_reply_keyboard(response_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💬 In dialog",
                callback_data=f"reply_in_dialog:{response_id}",
            ),
            InlineKeyboardButton(
                text="🛠 In work",
                callback_data=f"reply_in_work:{response_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Rejected",
                callback_data=f"reply_rejected:{response_id}",
            ),
        ],
    ])


def format_reply_notification(lead: Lead, response: Response) -> str:
    username = lead.author_username or "—"
    return (
        f"💬 Лид #{lead.id} ответил!\n"
        f"👤 @{username}\n"
        f"📋 {lead.project_type or '?'} · {lead.client_country or '?'} "
        f"· score {lead.relevance_score or '?'}\n\n"
        f"Что дальше?"
    )


class ClientReplyNotifier:
    def __init__(self, bot, owner_tg_id: int):
        self._bot = bot
        self._owner = owner_tg_id

    async def notify(self, lead: Lead, response: Response) -> None:
        text = format_reply_notification(lead, response)
        kb = build_reply_keyboard(response.id)
        await self._bot.send_message(
            self._owner, text,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
