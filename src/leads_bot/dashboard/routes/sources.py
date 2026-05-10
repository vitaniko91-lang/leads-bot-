"""GET /api/sources, PATCH /api/sources/{id}."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import (
    SourceListResponse,
    SourcePatch,
    SourceSummary,
)
from leads_bot.db.models import Lead, Response, Source

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> SourceListResponse:
    sources = (await session.execute(select(Source))).scalars().all()
    cutoff = datetime.utcnow() - timedelta(days=14)
    items: list[SourceSummary] = []
    for src in sources:
        leads_count = (await session.execute(
            select(func.count(Lead.id))
            .where(Lead.source_id == src.id, Lead.posted_at >= cutoff)
        )).scalar_one()
        sent_count = (await session.execute(
            select(func.count(Response.id))
            .join(Lead, Lead.id == Response.lead_id)
            .where(Lead.source_id == src.id,
                   Response.status == "sent",
                   Response.sent_at >= cutoff)
        )).scalar_one()
        reply_count = (await session.execute(
            select(func.count(Response.id))
            .join(Lead, Lead.id == Response.lead_id)
            .where(Lead.source_id == src.id,
                   Response.client_replied.is_(True),
                   Response.sent_at >= cutoff)
        )).scalar_one()
        days = 14.0
        items.append(SourceSummary(
            id=src.id, tg_id=src.tg_id, title=src.title, type=src.type,
            language=src.language, region=src.region, status=src.status,
            muted_until=src.muted_until,
            leads_per_day=round(leads_count / days, 2),
            sent_per_day=round(sent_count / days, 2),
            conversion_pct=round(
                (reply_count / sent_count * 100.0) if sent_count else 0.0, 2
            ),
        ))
    return SourceListResponse(items=items)


@router.patch("/sources/{source_id}", response_model=SourceSummary)
async def patch_source(
    source_id: int,
    payload: SourcePatch,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> SourceSummary:
    src = (await session.execute(
        select(Source).where(Source.id == source_id)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")

    if payload.status is not None:
        src.status = payload.status
    if payload.mute_for_minutes is not None:
        if payload.mute_for_minutes == 0:
            src.muted_until = None
        else:
            src.muted_until = (
                datetime.utcnow() + timedelta(minutes=payload.mute_for_minutes)
            )
    await session.commit()

    return SourceSummary(
        id=src.id, tg_id=src.tg_id, title=src.title, type=src.type,
        language=src.language, region=src.region, status=src.status,
        muted_until=src.muted_until,
        leads_per_day=0.0, sent_per_day=0.0, conversion_pct=0.0,
    )
