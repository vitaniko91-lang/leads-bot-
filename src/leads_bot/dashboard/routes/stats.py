from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats(_: str = Depends(require_basic_auth)):
    return {}  # filled in Task 4
