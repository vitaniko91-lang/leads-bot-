"""GET /api/leads, GET /api/leads/{id}, PATCH /api/leads/{id}.

PATCH writes to the latest Response row attached to the lead (notes, client_status).
We do NOT mutate Lead.status from the dashboard — that's the bot's job.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import (
    LeadDetail,
    LeadListResponse,
    LeadPatch,
    LeadSummary,
    ResponseDetail,
)
from leads_bot.db.models import Lead, Response, Source

router = APIRouter(prefix="/api", tags=["leads"])


def _to_summary(lead: Lead) -> LeadSummary:
    return LeadSummary(
        id=lead.id,
        source_id=lead.source_id,
        source_title=lead.source.title if lead.source else None,
        raw_text=lead.raw_text,
        posted_at=lead.posted_at,
        analyzed_at=lead.analyzed_at,
        is_lead=lead.is_lead,
        project_type=lead.project_type,
        budget_usd=lead.budget_usd,
        language=lead.language,
        client_country=lead.client_country,
        urgency=lead.urgency,
        relevance_score=lead.relevance_score,
        status=lead.status,
        has_response=bool(lead.responses),
    )


@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    status: Annotated[str | None, Query()] = None,
    source_id: Annotated[int | None, Query()] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
    region: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadListResponse:
    stmt = (
        select(Lead)
        .options(selectinload(Lead.source), selectinload(Lead.responses))
        .order_by(desc(Lead.posted_at))
    )
    if region:
        stmt = stmt.join(Source).where(Source.region == region)
    if status:
        stmt = stmt.where(Lead.status == status)
    if source_id:
        stmt = stmt.where(Lead.source_id == source_id)
    if min_score is not None:
        stmt = stmt.where(Lead.relevance_score >= min_score)
    if date_from:
        stmt = stmt.where(Lead.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(Lead.posted_at <= date_to)
    if language:
        stmt = stmt.where(Lead.language == language)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()

    return LeadListResponse(
        items=[_to_summary(lead) for lead in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadDetail:
    lead = (await session.execute(
        select(Lead)
        .options(selectinload(Lead.source), selectinload(Lead.responses))
        .where(Lead.id == lead_id)
    )).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    summary = _to_summary(lead).model_dump()
    return LeadDetail(
        **summary,
        reasoning=lead.reasoning,
        author_username=lead.author_username,
        author_tg_id=lead.author_tg_id,
        responses=[
            ResponseDetail(
                id=r.id, draft_text=r.draft_text, final_text=r.final_text,
                status=r.status, sent_to=r.sent_to, sent_at=r.sent_at,
                client_replied=r.client_replied, client_status=r.client_status,
                notes=r.notes,
            )
            for r in lead.responses
        ],
    )


@router.patch("/leads/{lead_id}", response_model=LeadDetail)
async def patch_lead(
    lead_id: int,
    payload: LeadPatch,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadDetail:
    """Update notes and/or client_status on the latest Response row."""
    resp = (await session.execute(
        select(Response)
        .where(Response.lead_id == lead_id)
        .order_by(desc(Response.id))
        .limit(1)
    )).scalar_one_or_none()
    if not resp:
        raise HTTPException(status_code=404, detail="No response for this lead")

    if payload.notes is not None:
        resp.notes = payload.notes
    if payload.client_status is not None:
        resp.client_status = payload.client_status
        if payload.client_status in ("replied", "in_dialog", "in_work"):
            resp.client_replied = True
    await session.commit()
    return await get_lead(lead_id, session=session, _="ok")
