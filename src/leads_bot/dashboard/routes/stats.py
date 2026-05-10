"""GET /api/stats — KPI numbers + hourly histogram."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import Period, StatsResponse
from leads_bot.dashboard.services.stats import compute_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: Annotated[Period, Query()] = "today",
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> StatsResponse:
    return await compute_stats(session, period)
