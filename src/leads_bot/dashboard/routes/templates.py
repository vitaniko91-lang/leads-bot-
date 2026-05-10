"""FastAPI router for /api/templates."""
from anthropic import AsyncAnthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.config import Settings, get_settings
from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.drafter.prompts import build_drafter_prompt
from leads_bot.templates.repo import TemplateRepo
from leads_bot.templates.winner import find_winner

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateOut(BaseModel):
    id: int
    name: str
    variant: str
    prompt: str
    active: bool
    traffic_share: int
    sent_count: int
    reply_count: int
    conversion_rate: float
    is_winner: bool


class TemplateUpdateIn(BaseModel):
    name: str | None = None
    prompt: str | None = None
    traffic_share: int | None = Field(None, ge=0, le=100)
    active: bool | None = None


class TemplateCreateIn(BaseModel):
    name: str
    variant: str
    prompt: str
    traffic_share: int = Field(0, ge=0, le=100)
    active: bool = True


class PreviewIn(BaseModel):
    prompt: str
    sample_lead_text: str = "Looking for UI designer for crypto landing, $1500"
    sample_project_type: str = "landing"
    sample_language: str = "en"


class PreviewOut(BaseModel):
    draft: str


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> list[TemplateOut]:
    repo = TemplateRepo(s)
    rows = await repo.all()
    winner = find_winner(rows)
    winner_id = winner.id if winner else None

    out = []
    for t in rows:
        rate = (t.reply_count / t.sent_count) if t.sent_count else 0.0
        out.append(TemplateOut(
            id=t.id, name=t.name, variant=t.variant, prompt=t.prompt,
            active=t.active, traffic_share=t.traffic_share,
            sent_count=t.sent_count, reply_count=t.reply_count,
            conversion_rate=rate,
            is_winner=(t.id == winner_id),
        ))
    return out


@router.post("", response_model=TemplateOut)
async def create_template(
    body: TemplateCreateIn,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> TemplateOut:
    repo = TemplateRepo(s)
    t = await repo.create(**body.model_dump())
    return TemplateOut(
        id=t.id, name=t.name, variant=t.variant, prompt=t.prompt,
        active=t.active, traffic_share=t.traffic_share,
        sent_count=0, reply_count=0, conversion_rate=0.0, is_winner=False,
    )


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: int, body: TemplateUpdateIn,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> TemplateOut:
    repo = TemplateRepo(s)
    if (await repo.get(template_id)) is None:
        raise HTTPException(404, "Template not found")
    t = await repo.update(template_id, **body.model_dump(exclude_none=True))
    rate = (t.reply_count / t.sent_count) if t.sent_count else 0.0
    return TemplateOut(
        id=t.id, name=t.name, variant=t.variant, prompt=t.prompt,
        active=t.active, traffic_share=t.traffic_share,
        sent_count=t.sent_count, reply_count=t.reply_count,
        conversion_rate=rate, is_winner=False,
    )


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    s: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
):
    await TemplateRepo(s).delete(template_id)


@router.post("/preview", response_model=PreviewOut)
async def preview_prompt(
    body: PreviewIn,
    settings: Settings = Depends(get_settings),
    _: str = Depends(require_basic_auth),
) -> PreviewOut:
    """Run Claude with the candidate prompt against a sample lead."""
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    from leads_bot.drafter.profile import Case, Profile
    sample_profile = Profile(
        name="Vitalina", portfolio_url="https://vitalina.design",
        telegram="@v", min_rate_usd_per_hour=50, tone="friendly",
        payment_methods=["wise", "payoneer"],
        cases=[Case(
            title="Crypto landing", tags=["landing"],
            description="3x conversion uplift", url="https://x/case",
        )],
    )
    user = build_drafter_prompt(
        profile=sample_profile,
        lead_text=body.sample_lead_text,
        project_type=body.sample_project_type,
        client_language=body.sample_language,
    )
    msg = await client.messages.create(
        model=settings.drafter_model,
        max_tokens=400,
        system=body.prompt,
        messages=[{"role": "user", "content": user}],
    )
    return PreviewOut(draft=msg.content[0].text.strip())
