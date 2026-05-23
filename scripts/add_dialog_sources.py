"""Add Telethon dialogs as sources interactively.

Lists channels / megagroups the userbot is in but NOT yet in `sources`,
prompts for each one: add (with region + lang) or skip. Useful for private
invite-link channels that `/sources add @username` cannot handle.

Usage (works while the main bot is running — Telethon SQLite session is
shared in WAL mode, but if it fails with AuthKey conflict, stop the bot,
run this, then restart the bot):

    uv run python scripts/add_dialog_sources.py
"""
from __future__ import annotations

import asyncio
import sys

from loguru import logger
from sqlalchemy import select
from telethon.tl.types import Channel
from telethon.utils import get_peer_id

from leads_bot.config import get_settings
from leads_bot.db.models import Source
from leads_bot.db.session import get_engine, get_session_factory
from leads_bot.listener.client import build_client

ALLOWED_REGIONS = {"ua", "cis_ex_ru", "eu", "en_global"}
ALLOWED_LANGUAGES = {"ru", "uk", "en"}


async def _ask(prompt: str) -> str:
    return (await asyncio.to_thread(input, prompt)).strip().lower()


async def run() -> int:
    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        existing = set((await session.execute(select(Source.tg_id))).scalars().all())
    logger.info(f"Already tracked: {len(existing)} sources")

    user_client = build_client()
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot connected as {settings.telegram_phone}")

    candidates: list[tuple[int, str, Channel]] = []
    async for dialog in user_client.iter_dialogs():
        ent = dialog.entity
        if not isinstance(ent, Channel):
            continue
        marked_id = get_peer_id(ent)
        if marked_id in existing:
            continue
        candidates.append((marked_id, dialog.name or "(no title)", ent))

    print(f"\n=== Found {len(candidates)} channel(s) not yet in `sources` ===\n")

    if not candidates:
        await user_client.disconnect()
        return 0

    added = 0
    for marked_id, name, ent in candidates:
        members = getattr(ent, "participants_count", None) or "?"
        kind = "channel" if ent.broadcast else "megagroup"
        print(f"\n→ {name}")
        print(f"   id={marked_id}  type={kind}  members={members}")

        choice = await _ask("   Add? (y/N): ")
        if choice not in ("y", "yes"):
            continue

        region = await _ask("   Region [ua / cis_ex_ru / eu / en_global]: ")
        if region not in ALLOWED_REGIONS:
            print("   ✗ invalid region — skipped")
            continue

        lang = await _ask("   Language [ru / uk / en]: ")
        if lang not in ALLOWED_LANGUAGES:
            print("   ✗ invalid language — skipped")
            continue

        async with factory() as session:
            session.add(Source(
                tg_id=marked_id,
                title=name[:255],
                type=kind,
                language=lang,
                region=region,
            ))
            await session.commit()
        added += 1
        print(f"   ✓ added as source")

    print(f"\n=== Done. Added {added} source(s). ===")

    await user_client.disconnect()
    await get_engine().dispose()
    return added


def main() -> None:
    try:
        n = asyncio.run(run())
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"add_dialog_sources failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
