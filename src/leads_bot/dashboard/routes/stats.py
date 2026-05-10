"""GET /api/stats — KPI numbers + hourly histogram + hot-hours grid."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.analytics.hot_hours import build_insight, compute_hot_hours
from leads_bot.config import Settings, get_settings
from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import Period, StatsResponse
from leads_bot.dashboard.services.stats import compute_stats

router = APIRouter(prefix="/api", tags=["stats"])


class HotHoursOut(BaseModel):
    matrix: list[list[int]]
    owner_tz: str
    total: int
    insight: str
    weekday_labels: list[str]
    hour_labels: list[str]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: Annotated[Period, Query()] = "today",
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> StatsResponse:
    return await compute_stats(session, period)


@router.get("/stats/hot-hours", response_model=HotHoursOut)
async def hot_hours(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> HotHoursOut:
    grid = await compute_hot_hours(session, days=days, owner_tz=settings.timezone)
    return HotHoursOut(
        matrix=grid.matrix,
        owner_tz=grid.owner_tz,
        total=grid.total(),
        insight=build_insight(grid),
        weekday_labels=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        hour_labels=[f"{h:02d}" for h in range(24)],
    )
