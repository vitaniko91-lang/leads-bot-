from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile")
async def get_profile(_: str = Depends(require_basic_auth)):
    return {}
