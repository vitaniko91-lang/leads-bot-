from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources")
async def list_sources(_: str = Depends(require_basic_auth)):
    return {"items": []}
