"""GET /api/profile, PATCH /api/profile — proxy to data/profile.json."""
from fastapi import APIRouter, Depends, HTTPException

from leads_bot.config import Settings, get_settings
from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.schemas import ProfilePayload
from leads_bot.dashboard.services.profile_store import read_profile, write_profile

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=ProfilePayload)
async def get_profile(
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> ProfilePayload:
    data = read_profile(settings.data_dir)
    if data is None:
        raise HTTPException(status_code=404, detail="profile.json not found")
    return ProfilePayload(**data)


@router.patch("/profile", response_model=ProfilePayload)
async def patch_profile(
    payload: ProfilePayload,
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> ProfilePayload:
    write_profile(settings.data_dir, payload.model_dump())
    return payload
