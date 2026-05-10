"""One-off: list dialogs (chats/channels) with their tg_ids.

Run after first Telethon login: `python scripts/get_chat_id.py`
"""
import asyncio

from telethon import TelegramClient

from leads_bot.config import get_settings


async def main():
    s = get_settings()
    async with TelegramClient(
        s.telegram_session_name, s.telegram_api_id, s.telegram_api_hash
    ) as c:
        await c.start(phone=s.telegram_phone)
        print(f"{'tg_id':>20}  {'name'}")
        print("-" * 60)
        async for d in c.iter_dialogs():
            print(f"{d.id:>20}  {d.name}")


if __name__ == "__main__":
    asyncio.run(main())
