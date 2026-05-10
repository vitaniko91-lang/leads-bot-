"""FastAPI router for /api/discovery — pending candidates + add/reject."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.discovery.repo import DiscoveryRepo

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


class CandidateOut(BaseModel):
    id: int
    tg_id: int
    title: str
    description: str | None
    member_count: int | None
    language: str | None
    predicted_region: str | None
    matched_query: str | None
    status: str


@router.get("/pending", response_model=list[CandidateOut])
async def list_pending(
    limit: int = 20,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> list[CandidateOut]:
    repo = DiscoveryRepo(s)
    return [
        CandidateOut(
            id=c.id, tg_id=c.tg_id, title=c.title,
            description=c.description, member_count=c.member_count,
            language=c.language, predicted_region=c.predicted_region,
            matched_query=c.matched_query, status=c.status,
        )
        for c in await repo.pending(limit=limit)
    ]


@router.post("/{candidate_id}/approve", status_code=201)
async def approve(
    candidate_id: int,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
):
    try:
        src = await DiscoveryRepo(s).approve(candidate_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"source_id": src.id, "tg_id": src.tg_id, "title": src.title}


@router.post("/{candidate_id}/reject", status_code=204)
async def reject(
    candidate_id: int,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
):
    await DiscoveryRepo(s).reject(candidate_id)
