from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["stream"])


@router.get("/stream/leads")
async def stream_leads(_: str = Depends(require_basic_auth)):
    return {}
