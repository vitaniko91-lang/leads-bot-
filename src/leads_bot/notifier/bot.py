"""aiogram Bot/Dispatcher setup. See spec §6.4."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from leads_bot.config import get_settings


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),  # plain text карточка
    )


def build_dispatcher() -> Dispatcher:
    """Dispatcher with in-memory FSM storage (single-user bot, no need for Redis)."""
    return Dispatcher(storage=MemoryStorage())


async def send_lead_card(bot: Bot, owner_tg_id: int, text: str, keyboard) -> int:
    """Send a lead card to owner. Returns message_id."""
    msg = await bot.send_message(
        owner_tg_id, text, reply_markup=keyboard, disable_web_page_preview=True
    )
    return msg.message_id
