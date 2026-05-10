"""Telethon TelegramClient setup."""
from telethon import TelegramClient

from leads_bot.config import get_settings


def build_client() -> TelegramClient:
    settings = get_settings()
    return TelegramClient(
        settings.telegram_session_name,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
