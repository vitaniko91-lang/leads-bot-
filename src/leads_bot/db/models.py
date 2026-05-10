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
    __table_args__ = (Index("ix_responses_status_sent", "status", "sent_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"))
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    draft_text: Mapped[str] = mapped_column(Text)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="drafted")
    sent_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_replied: Mapped[bool] = mapped_column(Boolean, default=False)
    client_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    lead: Mapped["Lead"] = relationship(back_populates="responses")


class RateLimit(Base):
    __tablename__ = "rate_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    window: Mapped[str] = mapped_column(String(10))
    window_start: Mapped[datetime] = mapped_column(DateTime)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
