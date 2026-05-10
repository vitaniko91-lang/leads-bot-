"""GET /api/settings, PATCH /api/settings — proxy to data/settings.json."""
from fastapi import APIRouter, Depends

from leads_bot.config import Settings, get_settings
from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.schemas import SettingsPayload
from leads_bot.dashboard.services.settings_store import (
    read_settings,
    write_settings,
)

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=SettingsPayload)
async def get_settings_route(
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> SettingsPayload:
    return SettingsPayload(**read_settings(settings.data_dir))


@router.patch("/settings", response_model=SettingsPayload)
async def patch_settings(
    payload: SettingsPayload,
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> SettingsPayload:
    write_settings(settings.data_dir, payload.model_dump())
    return payload
