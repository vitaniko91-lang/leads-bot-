from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
async def get_settings_route(_: str = Depends(require_basic_auth)):
    return {}
