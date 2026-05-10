"""SQLAlchemy ORM models. See spec §8 for schema."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(10))
    region: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="active")
    muted_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_msg_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    leads: Mapped[list["Lead"]] = relationship(back_populates="source")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("source_id", "tg_message_id", name="uq_lead_source_msg"),
        Index("ix_leads_status_posted", "status", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    tg_message_id: Mapped[int] = mapped_column(BigInteger)
    author_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    author_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    is_lead: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    project_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    budget_usd: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    client_country: Mapped[str | None] = mapped_column(String(20), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="new")

    source: Mapped["Source"] = relationship(back_populates="leads")
    responses: Mapped[list["Response"]] = relationship(back_populates="lead")


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        Index("ix_responses_status_sent", "status", "sent_at"),
        Index(
            "ix_responses_author_status_sent",
            "author_tg_id_cached", "status", "sent_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("templates.id"), nullable=True,
    )
    author_tg_id_cached: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    draft_text: Mapped[str] = mapped_column(Text)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="drafted")
    sent_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_replied: Mapped[bool] = mapped_column(Boolean, default=False)
    client_replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="responses")
    template: Mapped["Template | None"] = relationship()


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    window: Mapped[str] = mapped_column(String(10))
    window_start: Mapped[datetime] = mapped_column(DateTime)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)


class BotState(Base):
    """Single-row table (id=1) holding mutable runtime flags."""
    __tablename__ = "bot_state"

    id: Mapped[int] = mapped_column(primary_key=True)  # always 1
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    last_digest_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_health_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_health_fails: Mapped[int] = mapped_column(Integer, default=0)
    last_rate_limit_rotation_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    quiet_hours_override: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text)
    variant: Mapped[str] = mapped_column(String(20))            # A | B | control
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    traffic_share: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow,
    )


class DiscoveryCandidate(Base):
    __tablename__ = "discovery_candidates"
    __table_args__ = (
        UniqueConstraint("tg_id", name="uq_discovery_tg_id"),
        Index("ix_discovery_status_discovered", "status", "discovered_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    predicted_region: Mapped[str | None] = mapped_column(String(20), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    matched_query: Mapped[str | None] = mapped_column(String(255), nullable=True)
