"""Seeds `sources` table from a JSON file. Idempotent: skips existing tg_ids."""
import json
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Source

ALLOWED_REGIONS = {"ua", "cis_ex_ru", "eu", "en_global"}


async def seed_sources_from_json(path: Path, factory: async_sessionmaker) -> int:
    """Load sources from JSON. Returns number of NEW sources added."""
    data = json.loads(Path(path).read_text())
    added = 0
    async with factory() as session:
        for item in data:
            if item["region"] not in ALLOWED_REGIONS:
                logger.warning(f"Skipping source with disallowed region: {item}")
                continue
            existing = (await session.execute(
                select(Source).where(Source.tg_id == item["tg_id"])
            )).scalar_one_or_none()
            if existing:
                continue
            session.add(Source(
                tg_id=item["tg_id"],
                title=item["title"],
                type=item["type"],
                language=item["language"],
                region=item["region"],
                status="active",
            ))
            added += 1
        await session.commit()
    logger.info(f"Seeded {added} new sources from {path}")
    return added
