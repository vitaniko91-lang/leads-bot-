"""Persistence for DiscoveryCandidate. Skips dups by tg_id; respects sources."""
from typing import Sequence

from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.db.models import DiscoveryCandidate, Source
from leads_bot.discovery.searcher import RawCandidate


class DiscoveryRepo:
    def __init__(self, session: AsyncSession):
        self._s = session

    async def get(self, candidate_id: int) -> DiscoveryCandidate | None:
        return await self._s.get(DiscoveryCandidate, candidate_id)

    async def pending(self, limit: int = 10) -> Sequence[DiscoveryCandidate]:
        stmt = (
            select(DiscoveryCandidate)
            .where(DiscoveryCandidate.status == "pending")
            .order_by(DiscoveryCandidate.member_count.desc().nullslast())
            .limit(limit)
        )
        return list((await self._s.execute(stmt)).scalars().all())

    async def upsert_pending(self, raws: list[RawCandidate]) -> int:
        """Insert raw candidates as 'pending' rows. Returns count of NEW insertions.

        Skips:
        - Candidates whose tg_id already appears in `sources`.
        - Candidates whose tg_id already appears in `discovery_candidates`
          (any status — including 'rejected', so we don't re-suggest).
        """
        if not raws:
            return 0

        ids = [r.tg_id for r in raws]

        existing_sources = set((await self._s.execute(
            select(Source.tg_id).where(Source.tg_id.in_(ids))
        )).scalars().all())

        existing_candidates = set((await self._s.execute(
            select(DiscoveryCandidate.tg_id)
            .where(DiscoveryCandidate.tg_id.in_(ids))
        )).scalars().all())

        added = 0
        for raw in raws:
            if raw.tg_id in existing_sources or raw.tg_id in existing_candidates:
                continue
            self._s.add(DiscoveryCandidate(
                tg_id=raw.tg_id,
                title=raw.title,
                description=raw.description,
                member_count=raw.member_count,
                language=raw.predicted_language,
                predicted_region=raw.predicted_region,
                matched_query=raw.matched_query,
                status="pending",
            ))
            added += 1
        await self._s.commit()
        logger.info(f"Discovery: upserted {added} new candidates (of {len(raws)})")
        return added

    async def approve(self, candidate_id: int) -> Source:
        cand = await self.get(candidate_id)
        if cand is None:
            raise ValueError(f"DiscoveryCandidate #{candidate_id} not found")

        src = Source(
            tg_id=cand.tg_id,
            title=cand.title,
            type="channel",
            language=cand.language or "en",
            region=cand.predicted_region or "en_global",
            status="active",
        )
        self._s.add(src)
        cand.status = "approved"
        await self._s.commit()
        return src

    async def reject(self, candidate_id: int) -> None:
        await self._s.execute(
            update(DiscoveryCandidate)
            .where(DiscoveryCandidate.id == candidate_id)
            .values(status="rejected")
        )
        await self._s.commit()
