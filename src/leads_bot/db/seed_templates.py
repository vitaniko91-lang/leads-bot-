"""Seeds `templates` table from JSON. Idempotent on (name)."""
import json
from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Template


async def seed_templates_from_json(path: Path, factory: async_sessionmaker) -> int:
    """Load templates from JSON. Returns number of NEW templates inserted.

    Raises ValueError if active templates' traffic_share doesn't sum to 100.
    """
    data = json.loads(Path(path).read_text())

    active = [t for t in data if t.get("active", True)]
    total = sum(t.get("traffic_share", 0) for t in active)
    if total != 100:
        raise ValueError(
            f"Active templates' traffic_share must sum to 100, got {total}"
        )

    added = 0
    async with factory() as session:
        existing_names = {
            r[0] for r in (await session.execute(select(Template.name))).all()
        }
        for item in data:
            if item["name"] in existing_names:
                continue
            session.add(Template(
                name=item["name"],
                variant=item["variant"],
                active=bool(item.get("active", True)),
                traffic_share=int(item["traffic_share"]),
                prompt=item["prompt"],
            ))
            added += 1
        await session.commit()

    logger.info(f"Seeded {added} new templates from {path}")
    return added
