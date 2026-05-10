from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads")
async def list_leads(_: str = Depends(require_basic_auth)):
    return {"items": [], "total": 0}
