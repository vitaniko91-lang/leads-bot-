"""Pydantic models for API requests/responses."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Period = Literal["today", "week", "month"]


class HourBucket(BaseModel):
    hour: datetime
    count: int


class StatsResponse(BaseModel):
    period: Period
    leads_total: int
    sent_count: int
    reply_count: int
    conversion_pct: float
    by_hour: list[HourBucket]


class LeadSummary(BaseModel):
    id: int
    source_id: int
    source_title: str | None = None
    raw_text: str
    posted_at: datetime
    analyzed_at: datetime | None
    is_lead: bool | None
    project_type: str | None
    budget_usd: int | None
    language: str | None
    client_country: str | None
    urgency: str | None
    relevance_score: int | None
    status: str
    has_response: bool


class ResponseDetail(BaseModel):
    id: int
    draft_text: str
    final_text: str | None
    status: str
    sent_to: str | None
    sent_at: datetime | None
    client_replied: bool
    client_status: str | None
    notes: str | None


class LeadDetail(LeadSummary):
    reasoning: str | None
    author_username: str | None
    author_tg_id: int | None
    responses: list[ResponseDetail]


class LeadListResponse(BaseModel):
    items: list[LeadSummary]
    total: int
    limit: int
    offset: int


class LeadPatch(BaseModel):
    notes: str | None = None
    client_status: Literal[
        "replied", "in_dialog", "in_work", "rejected", "no_response"
    ] | None = None


class SourceSummary(BaseModel):
    id: int
    tg_id: int
    title: str
    type: str
    language: str
    region: str
    status: str
    muted_until: datetime | None
    leads_per_day: float
    sent_per_day: float
    conversion_pct: float


class SourceListResponse(BaseModel):
    items: list[SourceSummary]


class SourcePatch(BaseModel):
    status: Literal["active", "paused", "banned"] | None = None
    mute_for_minutes: int | None = Field(None, ge=0, le=10080)


class ProfilePayload(BaseModel):
    """Loose passthrough; full schema defined in data/profile.example.json."""
    name: str
    portfolio_url: str
    telegram: str
    min_rate_usd_per_hour: int
    tone: str
    payment_methods: list[str]
    cases: list[dict]


class SettingsPayload(BaseModel):
    quiet_hours: str = Field(..., pattern=r"^\d{2}:\d{2}-\d{2}:\d{2}$")
    min_budget_usd: int = Field(..., ge=0, le=100000)
    min_relevance_score: int = Field(..., ge=0, le=100)
    max_responses_per_hour: int = Field(..., ge=1, le=100)
    max_responses_per_day: int = Field(..., ge=1, le=1000)
    max_responses_per_week: int = Field(..., ge=1, le=10000)
