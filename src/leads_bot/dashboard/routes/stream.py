"""GET /api/stream/leads — Server-Sent Events for live lead updates.

Each connection holds its own `last_seen_id` watermark in memory. We poll the
`leads` table every `poll_ms` for rows with `id > last_seen_id` and emit them
as `event: new_lead`. The connection ends when the client disconnects.

Caveats:
- Backed by SQLite polling, not pub/sub. Latency ~poll interval.
- Run uvicorn with workers=1 (otherwise each worker has its own watermark).
"""
import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sse_starlette.sse import EventSourceResponse

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session_factory_dep
from leads_bot.db.models import Lead

router = APIRouter(prefix="/api", tags=["stream"])


async def _poll_and_emit(
    request: Request,
    factory: async_sessionmaker,
    poll_ms: int,
) -> AsyncIterator[dict]:
    async with factory() as s:
        last_seen = (
            await s.execute(select(Lead.id).order_by(desc(Lead.id)).limit(1))
        ).scalar() or 0

    yield {"event": "hello", "data": json.dumps({"last_seen_id": last_seen})}

    while True:
        if await request.is_disconnected():
            return
        async with factory() as s:
            rows = (await s.execute(
                select(Lead).where(Lead.id > last_seen).order_by(Lead.id).limit(50)
            )).scalars().all()
            for lead in rows:
                yield {
                    "event": "new_lead",
                    "data": json.dumps({
                        "id": lead.id,
                        "source_id": lead.source_id,
                        "raw_text": (lead.raw_text or "")[:200],
                        "status": lead.status,
                        "relevance_score": lead.relevance_score,
                    }),
                }
                last_seen = lead.id
        await asyncio.sleep(poll_ms / 1000.0)


@router.get("/stream/leads")
async def stream_leads(
    request: Request,
    poll_ms: int = Query(1500, ge=100, le=10000),
    factory: async_sessionmaker = Depends(get_session_factory_dep),
    _: str = Depends(require_basic_auth),
) -> EventSourceResponse:
    return EventSourceResponse(
        _poll_and_emit(request, factory, poll_ms),
        ping=15,
    )
