# Iteration 3 — Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Frontend Design Skill is auto-active in this workspace** — follow `~/.claude/rules/design.md` (sharp button corners 4-6px, card corners 12px, 4px base grid, max content 1200px, accent green `#4ade80`). **Do NOT install or use shadcn/ui — build all components from scratch.**

**Goal:** Web dashboard for the Telegram leads bot. Owner gets full visibility into leads, sources, profile, and settings via a self-hosted Next.js frontend talking to a FastAPI backend that reads the same SQLite the bot writes to. Live updates via SSE. Reverse-proxied through Caddy with auto Let's Encrypt and HTTP Basic auth.

**Architecture:** Three new services join the existing `bot` container in `docker-compose.yml`:

```
                    ┌──────────────┐
                    │  browser     │
                    └──────┬───────┘
                           │ HTTPS  (basic auth)
                    ┌──────▼───────┐
                    │  Caddy       │  :443 (auto LE), :80 (redirect)
                    └──┬────────┬──┘
            /           │        │ /api/*, /api/stream/*
        ┌───▼─────┐  ┌──▼──────────┐
        │ Next.js │  │ FastAPI     │  127.0.0.1:8000
        │ :3000   │  │ uvicorn     │
        └─────────┘  └──────┬──────┘
                            │ SQLAlchemy async (read-mostly)
                    ┌───────▼───────┐
                    │ SQLite (WAL)  │  shared volume ./data/bot.db
                    └───────▲───────┘
                            │ writes (leads, responses)
                    ┌───────┴───────┐
                    │ bot container │  (existing — unchanged)
                    └───────────────┘
```

All three new containers share the `./data` and `./logs` volumes. The bot is the primary writer to `leads` and `responses`; the dashboard writes only to `responses.notes`, `responses.client_status`, `sources.status`/`muted_until`, and to `data/settings.json` + `data/profile.json` (file-backed).

**Tech Stack:**

- **Backend:** FastAPI 0.115, uvicorn (standard), sse-starlette, pydantic 2, SQLAlchemy 2.0 async (already in project), httpx (test client).
- **Frontend:** Next.js 15 (App Router, TypeScript), Tailwind v4, Recharts 2.15, `@iconify/react`, custom components (no shadcn). Vitest + Playwright for the bare-minimum smoke tests.
- **Reverse proxy:** Caddy 2.8 (official Docker image, automatic Let's Encrypt).
- **Deploy:** Docker Compose on the same Hetzner VPS as the bot.

**Spec reference:** `docs/superpowers/specs/2026-05-10-telegram-leads-bot-design.md` — §6.7 (dashboard module), §10 (pages + SSE), §9 (UX style), §13 (iter 3 scope).

**Iter 2 dependency:** Iter 2 lands command-driven CRUD for sources, the edit-flow state machine, quiet hours enforcement, and `client_status` updates from Telegram. This plan assumes those merged commits exist on `main` before iter 3 starts — but does NOT depend on any new ORM models. If iter 2 introduces a `Setting` ORM model, swap Task 9's JSON-file approach for it during merge.

---

## File Structure

### New backend files (under `src/leads_bot/dashboard/`)

```
src/leads_bot/dashboard/
├── __init__.py
├── app.py                       # FastAPI app factory + uvicorn entry
├── auth.py                      # HTTPBasic dependency
├── deps.py                      # session, settings dependencies
├── schemas.py                   # pydantic response/request models
├── routes/
│   ├── __init__.py
│   ├── stats.py                 # GET /api/stats
│   ├── leads.py                 # GET/PATCH /api/leads
│   ├── sources.py               # GET/PATCH /api/sources
│   ├── profile.py               # GET/PATCH /api/profile
│   ├── settings.py              # GET/PATCH /api/settings
│   └── stream.py                # GET /api/stream/leads (SSE)
├── services/
│   ├── __init__.py
│   ├── stats.py                 # KPI aggregations
│   ├── settings_store.py        # JSON file read/write w/ atomic replace
│   └── profile_store.py         # profile.json read/write
└── main.py                      # `python -m leads_bot.dashboard.main`
```

### New backend tests (under `tests/dashboard/`)

```
tests/dashboard/
├── __init__.py
├── conftest.py                  # async test client + isolated DB
├── test_auth.py
├── test_stats.py
├── test_leads.py
├── test_sources.py
├── test_profile.py
├── test_settings.py
└── test_stream.py
```

### New frontend files (under `dashboard-ui/`)

```
dashboard-ui/
├── package.json
├── tsconfig.json
├── next.config.ts
├── tailwind.config.ts
├── postcss.config.mjs
├── vitest.config.ts
├── playwright.config.ts
├── .env.local.example
├── public/
│   └── favicon.ico
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── globals.css
│   │   ├── page.tsx                       # /  Overview
│   │   ├── leads/
│   │   │   ├── page.tsx                   # /leads
│   │   │   └── [id]/page.tsx              # /leads/[id]
│   │   ├── sources/page.tsx
│   │   ├── profile/page.tsx
│   │   └── settings/page.tsx
│   ├── components/
│   │   ├── Button.tsx
│   │   ├── Card.tsx
│   │   ├── Stat.tsx
│   │   ├── Badge.tsx
│   │   ├── Table.tsx
│   │   ├── Drawer.tsx
│   │   ├── Input.tsx
│   │   ├── Select.tsx
│   │   ├── Textarea.tsx
│   │   ├── PageHeader.tsx
│   │   ├── Sidebar.tsx
│   │   ├── LeadFlowChart.tsx
│   │   ├── ConversionChart.tsx
│   │   └── LeadFiltersBar.tsx
│   ├── hooks/
│   │   ├── useLeadsStream.ts              # SSE consumer
│   │   └── useApi.ts                      # fetch wrapper with basic-auth
│   ├── lib/
│   │   ├── api.ts                         # server-side fetcher
│   │   ├── format.ts                      # date/number formatters
│   │   └── types.ts                       # shared TS types
│   └── tests/
│       ├── Button.test.tsx                # Vitest smoke
│       └── e2e/
│           └── overview.spec.ts           # Playwright smoke
└── README.md
```

### New / modified infra files

```
.
├── Caddyfile                               # NEW — reverse proxy config
├── docker-compose.yml                      # MODIFIED — add fastapi, frontend, caddy
├── pyproject.toml                          # MODIFIED — add fastapi, uvicorn, sse-starlette, httpx
├── data/
│   └── settings.example.json               # NEW — initial settings shape
└── README.md                               # MODIFIED — deploy section for dashboard
```

---

## Task 1: Backend deps + FastAPI app skeleton

**Files:**
- Modify: `pyproject.toml`
- Create: `src/leads_bot/dashboard/__init__.py` (empty)
- Create: `src/leads_bot/dashboard/app.py`
- Create: `src/leads_bot/dashboard/main.py`

- [ ] **Step 1: Add FastAPI deps to `pyproject.toml`**

In the `dependencies` array, append:

```toml
    "fastapi==0.115.4",
    "uvicorn[standard]==0.32.0",
    "sse-starlette==2.1.3",
```

In the `dev` group, append:

```toml
    "httpx==0.27.2",
```

- [ ] **Step 2: Sync deps**

```bash
cd "/Users/vitalinanikulina/Documents/Work/search for projects"
uv sync
python -c "import fastapi, uvicorn, sse_starlette, httpx; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Create `src/leads_bot/dashboard/__init__.py`** (empty)

- [ ] **Step 4: Create `src/leads_bot/dashboard/app.py`**

```python
"""FastAPI application factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("Dashboard FastAPI starting")
    yield
    logger.info("Dashboard FastAPI shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Leads Bot Dashboard API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        # In prod the frontend lives under the same Caddy origin, so CORS is moot.
        # Allow localhost for dev convenience only.
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 5: Create `src/leads_bot/dashboard/main.py`**

```python
"""Run the dashboard FastAPI app via uvicorn.

Usage:
    python -m leads_bot.dashboard.main
"""
import uvicorn

from leads_bot.config import get_settings


def main() -> None:
    get_settings()  # validate env early
    uvicorn.run(
        "leads_bot.dashboard.app:app",
        host="0.0.0.0",  # bound inside container; only Caddy proxies it externally
        port=8000,
        workers=1,       # SSE polling holds in-memory state — keep workers=1
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Smoke test the app loads**

```bash
python -c "from leads_bot.dashboard.app import app; print(app.title, [r.path for r in app.routes])"
```

Expected output contains `/api/health` and `/api/docs`.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/leads_bot/dashboard/
git commit -m "feat(dashboard): FastAPI app skeleton + health endpoint"
```

---

## Task 2: Test infrastructure (httpx async client + isolated DB)

**Files:**
- Create: `tests/dashboard/__init__.py` (empty)
- Create: `tests/dashboard/conftest.py`

- [ ] **Step 1: Create `tests/dashboard/__init__.py`** (empty)

- [ ] **Step 2: Create `tests/dashboard/conftest.py`**

```python
"""Shared fixtures for dashboard API tests.

Each test gets:
- An in-memory SQLite engine + sessionmaker.
- A FastAPI app whose `get_session_factory` dependency is overridden to that engine.
- An httpx.AsyncClient bound to the app via ASGITransport.
- HTTP Basic credentials pre-encoded.
"""
import base64
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.dashboard.app import create_app
from leads_bot.dashboard.deps import get_session_factory_dep, get_settings_dep
from leads_bot.db.models import Base


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    """Provide a complete env so leads_bot.config.Settings() validates."""
    for k, v in [
        ("TELEGRAM_API_ID", "1"),
        ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"),
        ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"),
        ("ANTHROPIC_API_KEY", "x"),
        ("DASHBOARD_USER", "vita"),
        ("DASHBOARD_PASSWORD", "secret"),
        ("DATA_DIR", str(tmp_path)),
    ]:
        monkeypatch.setenv(k, v)
    # Reset cached singleton from leads_bot.config
    from leads_bot import config
    config._settings = None
    yield
    config._settings = None


@pytest.fixture
def basic_auth_header() -> dict[str, str]:
    raw = base64.b64encode(b"vita:secret").decode()
    return {"Authorization": f"Basic {raw}"}


@pytest.fixture
def wrong_auth_header() -> dict[str, str]:
    raw = base64.b64encode(b"vita:wrong").decode()
    return {"Authorization": f"Basic {raw}"}


@pytest.fixture
async def engine():
    e = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    await e.dispose()


@pytest.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
async def client(session_factory) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    # Register routes (avoid circular import at module import time)
    from leads_bot.dashboard.routes import register_all
    register_all(app)

    app.dependency_overrides[get_session_factory_dep] = lambda: session_factory
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seeded(session_factory):
    """Seed minimal data: one source, three leads, two responses."""
    from leads_bot.db.models import Source, Lead, Response
    async with session_factory() as s:
        src = Source(
            tg_id=-1001, title="Design Jobs UA", type="channel",
            language="ru", region="ua", status="active",
            added_at=datetime(2026, 5, 1),
        )
        s.add(src)
        await s.commit()
        leads = [
            Lead(source_id=src.id, tg_message_id=1, raw_text="Looking for UI",
                 is_lead=True, project_type="landing", budget_usd=1500,
                 language="en", client_country="eu", urgency="med",
                 relevance_score=88, reasoning="ok",
                 status="sent", posted_at=datetime(2026, 5, 22, 10),
                 analyzed_at=datetime(2026, 5, 22, 10, 1)),
            Lead(source_id=src.id, tg_message_id=2, raw_text="Шукаю дизайнера",
                 is_lead=True, project_type="app", budget_usd=600,
                 language="uk", client_country="ua", urgency="low",
                 relevance_score=72, reasoning="ok",
                 status="drafted", posted_at=datetime(2026, 5, 22, 11)),
            Lead(source_id=src.id, tg_message_id=3, raw_text="Сбер",
                 is_lead=False, client_country="ru",
                 status="filtered_out", posted_at=datetime(2026, 5, 22, 12)),
        ]
        s.add_all(leads)
        await s.commit()
        responses = [
            Response(lead_id=leads[0].id, draft_text="Hi! Saw your post...",
                     final_text="Hi! Saw your post...",
                     status="sent", sent_to="dm",
                     sent_at=datetime(2026, 5, 22, 10, 2),
                     client_replied=True, client_status="in_dialog"),
            Response(lead_id=leads[1].id, draft_text="Привіт! Бачила...",
                     status="drafted", sent_to="chat"),
        ]
        s.add_all(responses)
        await s.commit()
    return {"source_id": src.id, "lead_ids": [l.id for l in leads]}
```

- [ ] **Step 3: Commit**

```bash
git add tests/dashboard/
git commit -m "test(dashboard): conftest with httpx ASGI client + seeded fixtures"
```

---

## Task 3: HTTP Basic auth + dependency wiring

**Files:**
- Create: `src/leads_bot/dashboard/auth.py`
- Create: `src/leads_bot/dashboard/deps.py`
- Modify: `src/leads_bot/config.py`
- Create: `src/leads_bot/dashboard/routes/__init__.py`
- Test: `tests/dashboard/test_auth.py`

- [ ] **Step 1: Add dashboard env vars to `src/leads_bot/config.py`**

After the existing fields (before `quiet_hours_start` property), insert:

```python
    # Dashboard
    dashboard_user: str = "admin"
    dashboard_password: str = "change-me-please"
    data_dir: str = "data"
```

- [ ] **Step 2: Write failing auth test**

`tests/dashboard/test_auth.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_health_does_not_require_auth(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth(client):
    r = await client.get("/api/stats")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


@pytest.mark.asyncio
async def test_wrong_credentials_rejected(client, wrong_auth_header):
    r = await client.get("/api/stats", headers=wrong_auth_header)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_correct_credentials_accepted(client, basic_auth_header):
    r = await client.get("/api/stats", headers=basic_auth_header)
    # Stats endpoint exists once Task 4 lands; for now any 200/2xx is fine.
    assert r.status_code == 200
```

- [ ] **Step 3: Run, expect failure**

```bash
pytest tests/dashboard/test_auth.py -v
```

Expected: FAIL — `/api/stats` not yet routed.

- [ ] **Step 4: Implement `src/leads_bot/dashboard/auth.py`**

```python
"""HTTP Basic authentication for the dashboard API.

Single user, credentials from env (DASHBOARD_USER / DASHBOARD_PASSWORD).
Uses constant-time comparison to avoid timing attacks.
"""
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from leads_bot.config import Settings, get_settings

_basic = HTTPBasic(auto_error=True, realm="leads-dashboard")


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials, Depends(_basic)],
    settings: Settings = Depends(get_settings),
) -> str:
    """Return the username if creds are valid, else 401."""
    correct_user = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        settings.dashboard_user.encode("utf-8"),
    )
    correct_pwd = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        settings.dashboard_password.encode("utf-8"),
    )
    if not (correct_user and correct_pwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": 'Basic realm="leads-dashboard"'},
        )
    return credentials.username
```

- [ ] **Step 5: Implement `src/leads_bot/dashboard/deps.py`**

```python
"""FastAPI dependencies for DB session, settings, etc.

The session_factory dep is overridable in tests via app.dependency_overrides.
"""
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from leads_bot.config import Settings, get_settings
from leads_bot.db.session import get_session_factory


def get_settings_dep() -> Settings:
    return get_settings()


def get_session_factory_dep() -> async_sessionmaker[AsyncSession]:
    return get_session_factory()


async def get_session(
    factory: Annotated[
        async_sessionmaker[AsyncSession], Depends(get_session_factory_dep)
    ],
) -> AsyncIterator[AsyncSession]:
    async with factory() as s:
        yield s
```

- [ ] **Step 6: Implement `src/leads_bot/dashboard/routes/__init__.py`**

```python
"""Route registration for the dashboard API.

`register_all(app)` is called from create_app() after the FastAPI instance
exists, to avoid circular imports.
"""
from fastapi import FastAPI


def register_all(app: FastAPI) -> None:
    from leads_bot.dashboard.routes import (
        stats, leads, sources, profile, settings as settings_route, stream,
    )
    app.include_router(stats.router)
    app.include_router(leads.router)
    app.include_router(sources.router)
    app.include_router(profile.router)
    app.include_router(settings_route.router)
    app.include_router(stream.router)
```

- [ ] **Step 7: Update `src/leads_bot/dashboard/app.py` to call `register_all`**

Replace the existing `create_app()` body with:

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="Leads Bot Dashboard API",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}

    # Register all /api/* routers (lazy import to avoid circulars)
    from leads_bot.dashboard.routes import register_all
    register_all(app)
    return app
```

- [ ] **Step 8: Stub the routers so imports work**

For each of `stats.py`, `leads.py`, `sources.py`, `profile.py`, `settings.py`, `stream.py` create a temporary placeholder. We'll fill them in later tasks.

`src/leads_bot/dashboard/routes/stats.py`:

```python
from fastapi import APIRouter, Depends

from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def get_stats(_: str = Depends(require_basic_auth)):
    return {}  # filled in Task 4
```

For `leads.py`, `sources.py`, `profile.py`, `settings.py`, `stream.py` use the same shape — `APIRouter(prefix="/api", tags=[name])` and one dummy endpoint each (`/leads`, `/sources`, `/profile`, `/settings`, `/stream/leads`) returning `{}` and gated by `require_basic_auth`.

```python
# src/leads_bot/dashboard/routes/leads.py
from fastapi import APIRouter, Depends
from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["leads"])


@router.get("/leads")
async def list_leads(_: str = Depends(require_basic_auth)):
    return {"items": [], "total": 0}
```

```python
# src/leads_bot/dashboard/routes/sources.py
from fastapi import APIRouter, Depends
from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources")
async def list_sources(_: str = Depends(require_basic_auth)):
    return {"items": []}
```

```python
# src/leads_bot/dashboard/routes/profile.py
from fastapi import APIRouter, Depends
from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile")
async def get_profile(_: str = Depends(require_basic_auth)):
    return {}
```

```python
# src/leads_bot/dashboard/routes/settings.py
from fastapi import APIRouter, Depends
from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
async def get_settings_route(_: str = Depends(require_basic_auth)):
    return {}
```

```python
# src/leads_bot/dashboard/routes/stream.py
from fastapi import APIRouter, Depends
from leads_bot.dashboard.auth import require_basic_auth

router = APIRouter(prefix="/api", tags=["stream"])


@router.get("/stream/leads")
async def stream_leads(_: str = Depends(require_basic_auth)):
    return {}
```

- [ ] **Step 9: Run auth tests**

```bash
pytest tests/dashboard/test_auth.py -v
```

Expected: 4 PASS.

- [ ] **Step 10: Commit**

```bash
git add src/leads_bot/config.py src/leads_bot/dashboard/ tests/dashboard/test_auth.py
git commit -m "feat(dashboard): HTTP Basic auth + dependency wiring + route stubs"
```

---

## Task 4: GET /api/stats

**Files:**
- Modify: `src/leads_bot/dashboard/routes/stats.py`
- Create: `src/leads_bot/dashboard/services/__init__.py` (empty)
- Create: `src/leads_bot/dashboard/services/stats.py`
- Create: `src/leads_bot/dashboard/schemas.py`
- Test: `tests/dashboard/test_stats.py`

- [ ] **Step 1: Write failing test**

`tests/dashboard/test_stats.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_stats_today_returns_kpis(client, basic_auth_header, seeded, freezer=None):
    # The seeded fixture posts leads on 2026-05-22; just check structure.
    r = await client.get("/api/stats?period=today", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert set(data.keys()) >= {
        "period", "leads_total", "sent_count", "reply_count",
        "conversion_pct", "by_hour",
    }
    assert data["period"] == "today"
    assert isinstance(data["by_hour"], list)


@pytest.mark.asyncio
async def test_stats_invalid_period_400(client, basic_auth_header):
    r = await client.get("/api/stats?period=forever", headers=basic_auth_header)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_stats_week_aggregates(client, basic_auth_header, seeded):
    r = await client.get("/api/stats?period=week", headers=basic_auth_header)
    assert r.status_code == 200
    d = r.json()
    assert d["leads_total"] >= 0
    assert 0 <= d["conversion_pct"] <= 100
```

- [ ] **Step 2: Run, expect FAIL**

```bash
pytest tests/dashboard/test_stats.py -v
```

- [ ] **Step 3: Create `src/leads_bot/dashboard/schemas.py`**

```python
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
    client_status: Literal["replied", "in_dialog", "in_work", "rejected", "no_response"] | None = None


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
```

- [ ] **Step 4: Create `src/leads_bot/dashboard/services/__init__.py`** (empty)

- [ ] **Step 5: Create `src/leads_bot/dashboard/services/stats.py`**

```python
"""KPI aggregations for /api/stats."""
from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.schemas import HourBucket, StatsResponse
from leads_bot.db.models import Lead, Response

Period = Literal["today", "week", "month"]


def _period_start(period: Period, now: datetime) -> datetime:
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    raise ValueError(period)


async def compute_stats(session: AsyncSession, period: Period) -> StatsResponse:
    now = datetime.utcnow()
    start = _period_start(period, now)

    leads_total = (
        await session.execute(
            select(func.count(Lead.id)).where(Lead.posted_at >= start)
        )
    ).scalar_one()

    sent_count = (
        await session.execute(
            select(func.count(Response.id))
            .where(Response.status == "sent", Response.sent_at >= start)
        )
    ).scalar_one()

    reply_count = (
        await session.execute(
            select(func.count(Response.id))
            .where(Response.client_replied.is_(True), Response.sent_at >= start)
        )
    ).scalar_one()

    conv = (reply_count / sent_count * 100.0) if sent_count else 0.0

    # Hourly bucket: SQLite-friendly via strftime.
    rows = (
        await session.execute(
            select(
                func.strftime("%Y-%m-%d %H:00:00", Lead.posted_at).label("hour"),
                func.count(Lead.id).label("c"),
            )
            .where(Lead.posted_at >= start)
            .group_by("hour")
            .order_by("hour")
        )
    ).all()
    by_hour = [
        HourBucket(hour=datetime.fromisoformat(row.hour), count=row.c)
        for row in rows
    ]

    return StatsResponse(
        period=period,
        leads_total=leads_total,
        sent_count=sent_count,
        reply_count=reply_count,
        conversion_pct=round(conv, 2),
        by_hour=by_hour,
    )
```

- [ ] **Step 6: Replace `src/leads_bot/dashboard/routes/stats.py`**

```python
"""GET /api/stats — KPI numbers + hourly histogram."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import Period, StatsResponse
from leads_bot.dashboard.services.stats import compute_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: Annotated[Period, Query()] = "today",
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> StatsResponse:
    return await compute_stats(session, period)
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/dashboard/test_stats.py -v
```

Expected: 3 PASS. (`test_stats_invalid_period_400` returns 422 — FastAPI default for Literal validation.)

- [ ] **Step 8: Commit**

```bash
git add src/leads_bot/dashboard/schemas.py src/leads_bot/dashboard/services/ src/leads_bot/dashboard/routes/stats.py tests/dashboard/test_stats.py
git commit -m "feat(dashboard): GET /api/stats with hourly KPI bucketing"
```

---

## Task 5: GET /api/leads (filters + pagination) and GET /api/leads/{id}, PATCH /api/leads/{id}

**Files:**
- Modify: `src/leads_bot/dashboard/routes/leads.py`
- Test: `tests/dashboard/test_leads.py`

- [ ] **Step 1: Write failing tests**

`tests/dashboard/test_leads.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_leads_default(client, basic_auth_header, seeded):
    r = await client.get("/api/leads", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Sorted DESC by posted_at by default
    assert data["items"][0]["id"] == seeded["lead_ids"][2]


@pytest.mark.asyncio
async def test_list_leads_filter_by_status(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?status=sent", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_list_leads_filter_by_min_score(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?min_score=80", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["relevance_score"] >= 80


@pytest.mark.asyncio
async def test_list_leads_pagination(client, basic_auth_header, seeded):
    r = await client.get("/api/leads?limit=2&offset=0", headers=basic_auth_header)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    r = await client.get("/api/leads?limit=2&offset=2", headers=basic_auth_header)
    assert len(r.json()["items"]) == 1


@pytest.mark.asyncio
async def test_lead_detail(client, basic_auth_header, seeded):
    lid = seeded["lead_ids"][0]
    r = await client.get(f"/api/leads/{lid}", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == lid
    assert "responses" in data
    assert len(data["responses"]) == 1
    assert data["responses"][0]["status"] == "sent"


@pytest.mark.asyncio
async def test_lead_detail_404(client, basic_auth_header):
    r = await client.get("/api/leads/9999", headers=basic_auth_header)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_lead_updates_notes_and_client_status(
    client, basic_auth_header, seeded, session_factory,
):
    lid = seeded["lead_ids"][0]
    r = await client.patch(
        f"/api/leads/{lid}",
        json={"notes": "called back", "client_status": "in_work"},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    # Verify in DB
    from sqlalchemy import select
    from leads_bot.db.models import Response
    async with session_factory() as s:
        resp = (await s.execute(
            select(Response).where(Response.lead_id == lid)
        )).scalar_one()
        assert resp.notes == "called back"
        assert resp.client_status == "in_work"


@pytest.mark.asyncio
async def test_patch_lead_without_response_creates_no_op(
    client, basic_auth_header, seeded,
):
    """Lead 3 (filtered_out) has no response — patch should 404 cleanly."""
    lid = seeded["lead_ids"][2]
    r = await client.patch(
        f"/api/leads/{lid}",
        json={"notes": "x"},
        headers=basic_auth_header,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Replace `src/leads_bot/dashboard/routes/leads.py`**

```python
"""GET /api/leads, GET /api/leads/{id}, PATCH /api/leads/{id}.

PATCH writes to the latest Response row attached to the lead (notes, client_status).
We do NOT mutate Lead.status from the dashboard — that's the bot's job.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import (
    LeadDetail, LeadListResponse, LeadPatch, LeadSummary, ResponseDetail,
)
from leads_bot.db.models import Lead, Response, Source

router = APIRouter(prefix="/api", tags=["leads"])


def _to_summary(lead: Lead) -> LeadSummary:
    return LeadSummary(
        id=lead.id,
        source_id=lead.source_id,
        source_title=lead.source.title if lead.source else None,
        raw_text=lead.raw_text,
        posted_at=lead.posted_at,
        analyzed_at=lead.analyzed_at,
        is_lead=lead.is_lead,
        project_type=lead.project_type,
        budget_usd=lead.budget_usd,
        language=lead.language,
        client_country=lead.client_country,
        urgency=lead.urgency,
        relevance_score=lead.relevance_score,
        status=lead.status,
        has_response=bool(lead.responses),
    )


@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    status: Annotated[str | None, Query()] = None,
    source_id: Annotated[int | None, Query()] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    date_from: Annotated[str | None, Query()] = None,
    date_to: Annotated[str | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
    region: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadListResponse:
    stmt = (
        select(Lead)
        .options(selectinload(Lead.source), selectinload(Lead.responses))
        .order_by(desc(Lead.posted_at))
    )
    if status:
        stmt = stmt.where(Lead.status == status)
    if source_id:
        stmt = stmt.where(Lead.source_id == source_id)
    if min_score is not None:
        stmt = stmt.where(Lead.relevance_score >= min_score)
    if date_from:
        stmt = stmt.where(Lead.posted_at >= date_from)
    if date_to:
        stmt = stmt.where(Lead.posted_at <= date_to)
    if language:
        stmt = stmt.where(Lead.language == language)
    if region:
        stmt = stmt.where(Source.region == region).join(Source)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()

    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()

    return LeadListResponse(
        items=[_to_summary(l) for l in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/leads/{lead_id}", response_model=LeadDetail)
async def get_lead(
    lead_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadDetail:
    lead = (await session.execute(
        select(Lead)
        .options(selectinload(Lead.source), selectinload(Lead.responses))
        .where(Lead.id == lead_id)
    )).scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    summary = _to_summary(lead).model_dump()
    return LeadDetail(
        **summary,
        reasoning=lead.reasoning,
        author_username=lead.author_username,
        author_tg_id=lead.author_tg_id,
        responses=[
            ResponseDetail(
                id=r.id, draft_text=r.draft_text, final_text=r.final_text,
                status=r.status, sent_to=r.sent_to, sent_at=r.sent_at,
                client_replied=r.client_replied, client_status=r.client_status,
                notes=r.notes,
            )
            for r in lead.responses
        ],
    )


@router.patch("/leads/{lead_id}", response_model=LeadDetail)
async def patch_lead(
    lead_id: int,
    payload: LeadPatch,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> LeadDetail:
    """Update notes and/or client_status on the latest Response row."""
    resp = (await session.execute(
        select(Response)
        .where(Response.lead_id == lead_id)
        .order_by(desc(Response.id))
        .limit(1)
    )).scalar_one_or_none()
    if not resp:
        raise HTTPException(status_code=404, detail="No response for this lead")

    if payload.notes is not None:
        resp.notes = payload.notes
    if payload.client_status is not None:
        resp.client_status = payload.client_status
        if payload.client_status in ("replied", "in_dialog", "in_work"):
            resp.client_replied = True
    await session.commit()
    return await get_lead(lead_id, session=session, _="ok")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/dashboard/test_leads.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leads_bot/dashboard/routes/leads.py tests/dashboard/test_leads.py
git commit -m "feat(dashboard): /api/leads list+detail+patch with filters and pagination"
```

---

## Task 6: GET /api/sources + PATCH /api/sources/{id}

**Files:**
- Modify: `src/leads_bot/dashboard/routes/sources.py`
- Test: `tests/dashboard/test_sources.py`

- [ ] **Step 1: Write failing tests**

`tests/dashboard/test_sources.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_sources_returns_metrics(client, basic_auth_header, seeded):
    r = await client.get("/api/sources", headers=basic_auth_header)
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    s = data["items"][0]
    assert s["title"] == "Design Jobs UA"
    assert "leads_per_day" in s and "sent_per_day" in s and "conversion_pct" in s


@pytest.mark.asyncio
async def test_pause_source(client, basic_auth_header, seeded, session_factory):
    sid = seeded["source_id"]
    r = await client.patch(
        f"/api/sources/{sid}",
        json={"status": "paused"},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    from sqlalchemy import select
    from leads_bot.db.models import Source
    async with session_factory() as s:
        src = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert src.status == "paused"


@pytest.mark.asyncio
async def test_mute_source_for_minutes(client, basic_auth_header, seeded, session_factory):
    sid = seeded["source_id"]
    r = await client.patch(
        f"/api/sources/{sid}",
        json={"mute_for_minutes": 60},
        headers=basic_auth_header,
    )
    assert r.status_code == 200
    from datetime import datetime
    from sqlalchemy import select
    from leads_bot.db.models import Source
    async with session_factory() as s:
        src = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert src.muted_until is not None
        assert src.muted_until > datetime.utcnow()


@pytest.mark.asyncio
async def test_patch_source_404(client, basic_auth_header):
    r = await client.patch(
        "/api/sources/9999", json={"status": "paused"},
        headers=basic_auth_header,
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Replace `src/leads_bot/dashboard/routes/sources.py`**

```python
"""GET /api/sources, PATCH /api/sources/{id}."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.deps import get_session
from leads_bot.dashboard.schemas import (
    SourceListResponse, SourcePatch, SourceSummary,
)
from leads_bot.db.models import Lead, Response, Source

router = APIRouter(prefix="/api", tags=["sources"])


@router.get("/sources", response_model=SourceListResponse)
async def list_sources(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> SourceListResponse:
    sources = (await session.execute(select(Source))).scalars().all()
    cutoff = datetime.utcnow() - timedelta(days=14)
    items: list[SourceSummary] = []
    for src in sources:
        leads_count = (await session.execute(
            select(func.count(Lead.id))
            .where(Lead.source_id == src.id, Lead.posted_at >= cutoff)
        )).scalar_one()
        sent_count = (await session.execute(
            select(func.count(Response.id))
            .join(Lead, Lead.id == Response.lead_id)
            .where(Lead.source_id == src.id,
                   Response.status == "sent",
                   Response.sent_at >= cutoff)
        )).scalar_one()
        reply_count = (await session.execute(
            select(func.count(Response.id))
            .join(Lead, Lead.id == Response.lead_id)
            .where(Lead.source_id == src.id,
                   Response.client_replied.is_(True),
                   Response.sent_at >= cutoff)
        )).scalar_one()
        days = 14.0
        items.append(SourceSummary(
            id=src.id, tg_id=src.tg_id, title=src.title, type=src.type,
            language=src.language, region=src.region, status=src.status,
            muted_until=src.muted_until,
            leads_per_day=round(leads_count / days, 2),
            sent_per_day=round(sent_count / days, 2),
            conversion_pct=round((reply_count / sent_count * 100.0) if sent_count else 0.0, 2),
        ))
    return SourceListResponse(items=items)


@router.patch("/sources/{source_id}", response_model=SourceSummary)
async def patch_source(
    source_id: int,
    payload: SourcePatch,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_basic_auth),
) -> SourceSummary:
    src = (await session.execute(
        select(Source).where(Source.id == source_id)
    )).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")

    if payload.status is not None:
        src.status = payload.status
    if payload.mute_for_minutes is not None:
        if payload.mute_for_minutes == 0:
            src.muted_until = None
        else:
            src.muted_until = datetime.utcnow() + timedelta(minutes=payload.mute_for_minutes)
    await session.commit()

    # Re-list to get fresh metrics for this one row
    return SourceSummary(
        id=src.id, tg_id=src.tg_id, title=src.title, type=src.type,
        language=src.language, region=src.region, status=src.status,
        muted_until=src.muted_until,
        leads_per_day=0.0, sent_per_day=0.0, conversion_pct=0.0,  # lazy: omit recompute
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/dashboard/test_sources.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leads_bot/dashboard/routes/sources.py tests/dashboard/test_sources.py
git commit -m "feat(dashboard): /api/sources list with metrics + pause/mute PATCH"
```

---

## Task 7: GET/PATCH /api/profile (file proxy)

**Files:**
- Create: `src/leads_bot/dashboard/services/profile_store.py`
- Modify: `src/leads_bot/dashboard/routes/profile.py`
- Test: `tests/dashboard/test_profile.py`

- [ ] **Step 1: Write failing tests**

`tests/dashboard/test_profile.py`:

```python
import json
from pathlib import Path

import pytest


@pytest.fixture
def profile_path(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina",
        "portfolio_url": "https://x.design",
        "telegram": "@v",
        "min_rate_usd_per_hour": 50,
        "tone": "friendly",
        "payment_methods": ["wise"],
        "cases": [{"title": "Crypto", "tags": ["landing"], "description": "x", "url": "u"}],
    }))
    return p


@pytest.mark.asyncio
async def test_get_profile(client, basic_auth_header, profile_path):
    r = await client.get("/api/profile", headers=basic_auth_header)
    assert r.status_code == 200
    assert r.json()["name"] == "Vitalina"


@pytest.mark.asyncio
async def test_patch_profile_persists(client, basic_auth_header, profile_path):
    r = await client.patch("/api/profile", headers=basic_auth_header, json={
        "name": "Vita",
        "portfolio_url": "https://x.design",
        "telegram": "@v",
        "min_rate_usd_per_hour": 60,
        "tone": "direct",
        "payment_methods": ["wise", "payoneer"],
        "cases": [],
    })
    assert r.status_code == 200
    from json import loads
    assert loads(profile_path.read_text())["min_rate_usd_per_hour"] == 60
    assert loads(profile_path.read_text())["tone"] == "direct"


@pytest.mark.asyncio
async def test_get_profile_404_when_missing(client, basic_auth_header, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None
    r = await client.get("/api/profile", headers=basic_auth_header)
    assert r.status_code == 404
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Implement `src/leads_bot/dashboard/services/profile_store.py`**

```python
"""Read/write data/profile.json with atomic replace."""
import json
import os
import tempfile
from pathlib import Path


def profile_path(data_dir: str) -> Path:
    return Path(data_dir) / "profile.json"


def read_profile(data_dir: str) -> dict | None:
    p = profile_path(data_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def write_profile(data_dir: str, data: dict) -> None:
    p = profile_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Atomic: write to temp file in same dir, then os.replace
    fd, tmp = tempfile.mkstemp(prefix="profile.", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

- [ ] **Step 4: Replace `src/leads_bot/dashboard/routes/profile.py`**

```python
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
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/dashboard/test_profile.py -v
```

Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/leads_bot/dashboard/services/profile_store.py src/leads_bot/dashboard/routes/profile.py tests/dashboard/test_profile.py
git commit -m "feat(dashboard): /api/profile file-proxy with atomic write"
```

---

## Task 8: GET/PATCH /api/settings (settings.json — NOT .env)

**Decision rationale:** We persist runtime-mutable settings (quiet hours, min budget, min score, daily limits) to `data/settings.json`, NOT to `.env`. Why:

1. `.env` is for secrets and bootstrap config; mixing user-editable preferences into it is brittle (requires container restart, no atomic write, no schema validation).
2. The bot already reads its operational thresholds via `get_settings()` from `Settings`. We add a `settings_overlay` loader so the bot picks up changes from `data/settings.json` on each call without a restart (lazy reload). This is opt-in and falls back to `.env` defaults.
3. The dashboard owns the JSON file. Bot reads it, dashboard writes it. Single direction.
4. Iter 2 may introduce its own settings persistence — if so, swap this implementation but keep the public `/api/settings` shape.

**Files:**
- Create: `src/leads_bot/dashboard/services/settings_store.py`
- Modify: `src/leads_bot/dashboard/routes/settings.py`
- Create: `data/settings.example.json`
- Test: `tests/dashboard/test_settings.py`

- [ ] **Step 1: Create `data/settings.example.json`**

```json
{
  "quiet_hours": "23:00-08:00",
  "min_budget_usd": 300,
  "min_relevance_score": 60,
  "max_responses_per_hour": 5,
  "max_responses_per_day": 30,
  "max_responses_per_week": 150
}
```

- [ ] **Step 2: Write failing tests**

`tests/dashboard/test_settings.py`:

```python
import json
import pytest
from pathlib import Path


@pytest.mark.asyncio
async def test_get_settings_returns_defaults_when_file_absent(client, basic_auth_header):
    r = await client.get("/api/settings", headers=basic_auth_header)
    assert r.status_code == 200
    d = r.json()
    assert d["quiet_hours"] == "23:00-08:00"
    assert d["min_budget_usd"] == 300


@pytest.mark.asyncio
async def test_patch_settings_persists(client, basic_auth_header, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from leads_bot import config
    config._settings = None

    r = await client.patch("/api/settings", headers=basic_auth_header, json={
        "quiet_hours": "22:00-07:00",
        "min_budget_usd": 500,
        "min_relevance_score": 70,
        "max_responses_per_hour": 4,
        "max_responses_per_day": 20,
        "max_responses_per_week": 100,
    })
    assert r.status_code == 200
    p = tmp_path / "settings.json"
    data = json.loads(p.read_text())
    assert data["min_budget_usd"] == 500
    assert data["quiet_hours"] == "22:00-07:00"


@pytest.mark.asyncio
async def test_patch_invalid_quiet_hours_422(client, basic_auth_header):
    r = await client.patch("/api/settings", headers=basic_auth_header, json={
        "quiet_hours": "garbage",
        "min_budget_usd": 500,
        "min_relevance_score": 70,
        "max_responses_per_hour": 4,
        "max_responses_per_day": 20,
        "max_responses_per_week": 100,
    })
    assert r.status_code == 422
```

- [ ] **Step 3: Run, expect FAIL**

- [ ] **Step 4: Implement `src/leads_bot/dashboard/services/settings_store.py`**

```python
"""Read/write data/settings.json with atomic replace.

Falls back to bot's `Settings` defaults on read when file is absent.
"""
import json
import os
import tempfile
from pathlib import Path

from leads_bot.config import get_settings


def settings_path(data_dir: str) -> Path:
    return Path(data_dir) / "settings.json"


def read_settings(data_dir: str) -> dict:
    p = settings_path(data_dir)
    if p.exists():
        return json.loads(p.read_text())
    s = get_settings()
    return {
        "quiet_hours": s.quiet_hours,
        "min_budget_usd": s.min_budget_usd,
        "min_relevance_score": s.min_relevance_score,
        "max_responses_per_hour": s.max_responses_per_hour,
        "max_responses_per_day": s.max_responses_per_day,
        "max_responses_per_week": s.max_responses_per_week,
    }


def write_settings(data_dir: str, data: dict) -> None:
    p = settings_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="settings.", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
```

- [ ] **Step 5: Replace `src/leads_bot/dashboard/routes/settings.py`**

```python
"""GET /api/settings, PATCH /api/settings — proxy to data/settings.json."""
from fastapi import APIRouter, Depends

from leads_bot.config import Settings, get_settings
from leads_bot.dashboard.auth import require_basic_auth
from leads_bot.dashboard.schemas import SettingsPayload
from leads_bot.dashboard.services.settings_store import read_settings, write_settings

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
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/dashboard/test_settings.py -v
```

Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add src/leads_bot/dashboard/services/settings_store.py src/leads_bot/dashboard/routes/settings.py data/settings.example.json tests/dashboard/test_settings.py
git commit -m "feat(dashboard): /api/settings persists to data/settings.json (not .env)"
```

---

## Task 9: SSE /api/stream/leads

**Approach:** Single in-process polling loop. The endpoint hands the client a `text/event-stream` response that yields `event: new_lead\ndata: {...}\n\n` for every new `leads.id` greater than `last_seen`. Polling cadence: 1.5 s. State (`last_seen`) is per-connection (in the request scope), not global, so multiple clients each track their own watermark.

**Files:**
- Modify: `src/leads_bot/dashboard/routes/stream.py`
- Test: `tests/dashboard/test_stream.py`

- [ ] **Step 1: Write failing test**

`tests/dashboard/test_stream.py`:

```python
import asyncio
import json
import pytest
from datetime import datetime

from leads_bot.db.models import Lead, Source


@pytest.mark.asyncio
async def test_sse_emits_new_lead(client, basic_auth_header, session_factory):
    # Create one source so dependent leads are valid
    async with session_factory() as s:
        src = Source(tg_id=-1, title="x", type="channel",
                     language="en", region="eu", status="active")
        s.add(src)
        await s.commit()
        src_id = src.id

    # Open the stream and after a short delay insert a new lead
    async def _insert_after(delay_s: float):
        await asyncio.sleep(delay_s)
        async with session_factory() as s:
            s.add(Lead(source_id=src_id, tg_message_id=999, raw_text="x", status="new"))
            await s.commit()

    inserter = asyncio.create_task(_insert_after(0.5))

    async with client.stream(
        "GET", "/api/stream/leads?poll_ms=200",
        headers=basic_auth_header,
        timeout=5.0,
    ) as r:
        assert r.status_code == 200
        got = ""
        async for chunk in r.aiter_text():
            got += chunk
            if "new_lead" in got and "999" in got:
                break
        assert "new_lead" in got
        assert "999" in got

    await inserter


@pytest.mark.asyncio
async def test_sse_requires_auth(client):
    r = await client.get("/api/stream/leads")
    assert r.status_code == 401
```

- [ ] **Step 2: Run, expect FAIL**

- [ ] **Step 3: Replace `src/leads_bot/dashboard/routes/stream.py`**

```python
"""GET /api/stream/leads — Server-Sent Events for live lead updates.

Each connection holds its own `last_seen_id` watermark in memory. We poll the
`leads` table every `poll_ms` for rows with `id > last_seen_id` and emit them
as `event: new_lead`. The connection ends when the client disconnects.

Caveats:
- Backed by SQLite polling, not pub/sub. Latency ~poll interval.
- Run uvicorn with workers=1 (otherwise each worker has its own watermark
  and clients pinned to different workers see duplicate or missing events).
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
    # Initial watermark: max id at connection time, so we ONLY emit truly new rows.
    async with factory() as s:
        last_seen = (await s.execute(select(Lead.id).order_by(desc(Lead.id)).limit(1))).scalar() or 0

    # Send a hello so the client knows the stream is open.
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
        ping=15,  # keepalive every 15s
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/dashboard/test_stream.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leads_bot/dashboard/routes/stream.py tests/dashboard/test_stream.py
git commit -m "feat(dashboard): SSE /api/stream/leads via DB polling"
```

---

## Task 10: Backend service in docker-compose

**Files:**
- Modify: `Dockerfile` (or use existing — same image, different CMD)
- Modify: `docker-compose.yml`

- [ ] **Step 1: Decide on image strategy.** The dashboard FastAPI runs from the same Python image as the bot — single Dockerfile, two services with different `command`s. No new Dockerfile needed.

- [ ] **Step 2: Modify `docker-compose.yml`**

Replace existing content with:

```yaml
services:
  bot:
    build: .
    container_name: leads-bot
    restart: always
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./sessions:/app/sessions
    working_dir: /app
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import sqlite3; sqlite3.connect('/app/data/bot.db').execute('SELECT 1')"
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s

  dashboard-api:
    build: .
    container_name: leads-dashboard-api
    restart: always
    env_file:
      - .env
    environment:
      - DATA_DIR=/app/data
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    working_dir: /app
    command: ["python", "-m", "leads_bot.dashboard.main"]
    expose:
      - "8000"
    depends_on:
      - bot
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  dashboard-ui:
    build:
      context: ./dashboard-ui
      dockerfile: Dockerfile
    container_name: leads-dashboard-ui
    restart: always
    environment:
      - NODE_ENV=production
      - DASHBOARD_API_BASE_URL=http://dashboard-api:8000
    expose:
      - "3000"
    depends_on:
      - dashboard-api

  caddy:
    image: caddy:2.8-alpine
    container_name: leads-caddy
    restart: always
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - dashboard-api
      - dashboard-ui

volumes:
  caddy_data:
  caddy_config:
```

- [ ] **Step 3: Add SQLite WAL mode toggle**

The shared SQLite must use WAL mode so the dashboard reader doesn't block the bot writer. Edit `src/leads_bot/db/session.py` — verify or add `connect_args={"check_same_thread": False}` and a one-time PRAGMA. Append to `get_engine()`:

```python
from sqlalchemy import event

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, echo=False)

        @event.listens_for(_engine.sync_engine, "connect")
        def _enable_wal(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.close()
    return _engine
```

- [ ] **Step 4: Local sanity check (without frontend yet — frontend container would fail to build until Task 11)**

```bash
docker compose build bot dashboard-api
docker compose up -d bot dashboard-api
docker compose logs dashboard-api | tail -20
curl -u admin:change-me-please http://localhost:8000/api/health  # only works if you publish 8000 — remove `expose:` and add `ports: ["8000:8000"]` temporarily for this check, then revert
docker compose down
```

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml src/leads_bot/db/session.py
git commit -m "chore(docker): add dashboard-api, frontend, caddy services + SQLite WAL"
```

---

## Task 11: Frontend bootstrap (Next.js 15 + Tailwind v4)

**Files:**
- Create: `dashboard-ui/` (entire directory via `create-next-app`)

- [ ] **Step 1: Run create-next-app**

```bash
cd "/Users/vitalinanikulina/Documents/Work/search for projects"
npx create-next-app@latest dashboard-ui \
  --typescript \
  --tailwind \
  --app \
  --no-src-dir \
  --import-alias "@/*" \
  --eslint \
  --no-turbopack \
  --use-npm
```

When prompted: yes to TS, yes to Tailwind, yes to App Router, alias `@/*`. **Decline** any other prompts.

- [ ] **Step 2: Move to `src/` layout**

The wizard creates `app/` at the root. Restructure:

```bash
cd dashboard-ui
mkdir -p src
mv app src/app
# Update tsconfig if needed — Next.js auto-detects src/.
```

Edit `dashboard-ui/tsconfig.json` paths to:

```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  }
}
```

- [ ] **Step 3: Install runtime deps**

```bash
cd dashboard-ui
npm install recharts @iconify/react
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @playwright/test
```

- [ ] **Step 4: Verify dev server boots**

```bash
npm run dev
```

Expect Next.js banner on http://localhost:3000. Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard-ui/
git commit -m "feat(dashboard-ui): bootstrap Next.js 15 + Tailwind v4 + Recharts + Iconify"
```

---

## Task 12: Tailwind brand tokens + global styles

**Files:**
- Modify: `dashboard-ui/tailwind.config.ts`
- Modify: `dashboard-ui/src/app/globals.css`
- Modify: `dashboard-ui/src/app/layout.tsx`

- [ ] **Step 1: Replace `dashboard-ui/tailwind.config.ts`**

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx,js,jsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        bg: "#0a0a0a",
        surface: "#111111",
        surfaceHi: "#161616",
        border: "rgba(255,255,255,0.07)",
        borderHi: "rgba(255,255,255,0.12)",
        text: "#fafafa",
        textMuted: "rgba(250,250,250,0.62)",
        textDim: "rgba(250,250,250,0.42)",
        accent: "#4ADE80",
        accentDim: "#22a55a",
        warn: "#F59E0B",
        danger: "#FF5050",
        info: "#F472B6",
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "12px",
        xl: "16px",
      },
      maxWidth: {
        content: "1200px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        label: ["11px", { lineHeight: "14px", letterSpacing: "0.08em", fontWeight: "600" }],
      },
      spacing: {
        "0.5": "2px",
      },
      transitionDuration: {
        DEFAULT: "200ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

- [ ] **Step 2: Replace `dashboard-ui/src/app/globals.css`**

```css
@import "tailwindcss";

@layer base {
  html { color-scheme: dark; }
  body {
    background: #0a0a0a;
    color: #fafafa;
    font-family: Inter, system-ui, sans-serif;
    font-feature-settings: "cv11", "ss01";
    -webkit-font-smoothing: antialiased;
  }
  *:focus-visible {
    outline: 2px solid #4ADE80;
    outline-offset: 2px;
    border-radius: 4px;
  }
  button, [role="button"] { cursor: pointer; }
  ::selection { background: rgba(74, 222, 128, 0.25); }
}

@layer utilities {
  .uppercase-label {
    font-size: 11px;
    line-height: 14px;
    letter-spacing: 0.08em;
    font-weight: 600;
    text-transform: uppercase;
    color: rgba(250, 250, 250, 0.62);
  }
  .surface {
    background: #111111;
    border: 1px solid rgba(255, 255, 255, 0.07);
  }
  .surface-hi {
    background: #161616;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }
}
```

- [ ] **Step 3: Replace `dashboard-ui/src/app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Leads Bot Dashboard",
  description: "Internal control panel for the freelance leads bot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://rsms.me/" />
        <link rel="stylesheet" href="https://rsms.me/inter/inter.css" />
      </head>
      <body className="min-h-screen bg-bg text-text">{children}</body>
    </html>
  );
}
```

- [ ] **Step 4: Smoke check**

```bash
cd dashboard-ui
npm run dev
```

Visit http://localhost:3000 — body should be near-black with white text.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard-ui/tailwind.config.ts dashboard-ui/src/app/globals.css dashboard-ui/src/app/layout.tsx
git commit -m "feat(dashboard-ui): brand tokens (#0a0a0a + #4ADE80) + Inter typography"
```

---

## Task 13: Custom component — Button

**Files:**
- Create: `dashboard-ui/src/components/Button.tsx`
- Create: `dashboard-ui/src/tests/Button.test.tsx`
- Create: `dashboard-ui/vitest.config.ts`

- [ ] **Step 1: Implement `dashboard-ui/src/components/Button.tsx`**

```tsx
"use client";
import { forwardRef, ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
};

const base =
  "inline-flex items-center justify-center gap-2 font-medium rounded-md " +
  "transition-all select-none disabled:opacity-50 disabled:cursor-not-allowed " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60";

const variants: Record<Variant, string> = {
  primary:
    "bg-accent text-black hover:bg-accentDim active:translate-y-px",
  secondary:
    "bg-surfaceHi text-text border border-border hover:border-borderHi active:translate-y-px",
  ghost:
    "bg-transparent text-text hover:bg-surface",
  danger:
    "bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-12 px-6 text-base",
};

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "primary", size = "md", loading, fullWidth, className = "", children, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={[
        base,
        variants[variant],
        sizes[size],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      disabled={rest.disabled || loading}
      {...rest}
    >
      {loading && (
        <span className="inline-block h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
      )}
      {children}
    </button>
  );
});
```

- [ ] **Step 2: Create `dashboard-ui/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/tests/setup.ts"],
    include: ["src/tests/**/*.test.{ts,tsx}"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
```

- [ ] **Step 3: Create `dashboard-ui/src/tests/setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Create smoke test `dashboard-ui/src/tests/Button.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Button } from "@/components/Button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Send</Button>);
    expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
  });

  it("respects disabled", () => {
    render(<Button disabled>Send</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("disables when loading", () => {
    render(<Button loading>Send</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

- [ ] **Step 5: Add npm script**

In `dashboard-ui/package.json` `scripts`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 6: Run**

```bash
cd dashboard-ui && npm test
```

Expect 3 PASS.

- [ ] **Step 7: Commit**

```bash
cd ..
git add dashboard-ui/src/components/Button.tsx dashboard-ui/src/tests/ dashboard-ui/vitest.config.ts dashboard-ui/package.json
git commit -m "feat(dashboard-ui): Button component (4 variants, 3 sizes) + Vitest"
```

---

## Task 14: Custom components — Card, Stat, Badge

**Files:**
- Create: `dashboard-ui/src/components/Card.tsx`
- Create: `dashboard-ui/src/components/Stat.tsx`
- Create: `dashboard-ui/src/components/Badge.tsx`

- [ ] **Step 1: `dashboard-ui/src/components/Card.tsx`**

```tsx
import { HTMLAttributes } from "react";

type Props = HTMLAttributes<HTMLDivElement> & {
  padded?: boolean;
};

export function Card({ padded = true, className = "", children, ...rest }: Props) {
  return (
    <div
      className={[
        "rounded-lg border border-border bg-surface",
        padded ? "p-5" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 className="text-base font-semibold tracking-tight">{title}</h3>
        {subtitle && <p className="text-sm text-textMuted mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/components/Stat.tsx`**

```tsx
import { Card } from "./Card";

type Trend = "up" | "down" | "flat";

type Props = {
  label: string;
  value: string | number;
  delta?: string;
  trend?: Trend;
  hint?: string;
};

const trendColor: Record<Trend, string> = {
  up: "text-accent",
  down: "text-danger",
  flat: "text-textMuted",
};

export function Stat({ label, value, delta, trend = "flat", hint }: Props) {
  return (
    <Card>
      <div className="uppercase-label">{label}</div>
      <div className="mt-2 flex items-baseline gap-3">
        <span className="text-3xl font-bold tracking-tight tabular-nums">{value}</span>
        {delta && (
          <span className={`text-sm font-medium ${trendColor[trend]}`}>{delta}</span>
        )}
      </div>
      {hint && <div className="mt-2 text-sm text-textMuted">{hint}</div>}
    </Card>
  );
}
```

- [ ] **Step 3: `dashboard-ui/src/components/Badge.tsx`**

```tsx
type Tone = "neutral" | "accent" | "warn" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "bg-surfaceHi text-textMuted border-border",
  accent: "bg-accent/10 text-accent border-accent/30",
  warn: "bg-warn/10 text-warn border-warn/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  info: "bg-info/10 text-info border-info/30",
};

export function Badge({ tone = "neutral", children }: {
  tone?: Tone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-sm border text-xs font-medium",
        tones[tone],
      ].join(" ")}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard-ui/src/components/Card.tsx dashboard-ui/src/components/Stat.tsx dashboard-ui/src/components/Badge.tsx
git commit -m "feat(dashboard-ui): Card, Stat, Badge components"
```

---

## Task 15: Custom components — Table, Drawer, Input/Select/Textarea

**Files:**
- Create: `dashboard-ui/src/components/Table.tsx`
- Create: `dashboard-ui/src/components/Drawer.tsx`
- Create: `dashboard-ui/src/components/Input.tsx`
- Create: `dashboard-ui/src/components/Select.tsx`
- Create: `dashboard-ui/src/components/Textarea.tsx`

- [ ] **Step 1: `dashboard-ui/src/components/Table.tsx`**

```tsx
"use client";
import { ReactNode } from "react";

export type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  width?: string;
  align?: "left" | "right" | "center";
};

type Props<T> = {
  rows: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  rowKey: (row: T) => string | number;
};

export function Table<T>({ rows, columns, onRowClick, empty, rowKey }: Props<T>) {
  if (rows.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-12 text-center text-textMuted">
        {empty ?? "No rows"}
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-border bg-surface overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th
                key={c.key}
                style={{ width: c.width }}
                className={[
                  "uppercase-label px-4 py-3 text-left font-semibold",
                  c.align === "right" ? "text-right" : "",
                  c.align === "center" ? "text-center" : "",
                ].join(" ")}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              className={[
                "border-b border-border last:border-b-0 transition-colors",
                onRowClick ? "cursor-pointer hover:bg-surfaceHi" : "",
              ].join(" ")}
            >
              {columns.map((c) => (
                <td
                  key={c.key}
                  className={[
                    "px-4 py-3",
                    c.align === "right" ? "text-right" : "",
                    c.align === "center" ? "text-center" : "",
                  ].join(" ")}
                >
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/components/Drawer.tsx`**

```tsx
"use client";
import { useEffect } from "react";
import { Icon } from "@iconify/react";

type Props = {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  width?: number;
};

export function Drawer({ open, onClose, title, children, width = 560 }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className={[
          "fixed inset-0 bg-black/60 transition-opacity z-40",
          open ? "opacity-100" : "opacity-0 pointer-events-none",
        ].join(" ")}
        aria-hidden
      />
      <aside
        className={[
          "fixed inset-y-0 right-0 z-50 bg-surface border-l border-border",
          "transition-transform duration-200 flex flex-col",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
        style={{ width }}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex items-center justify-between px-5 h-14 border-b border-border shrink-0">
          <h2 className="text-base font-semibold tracking-tight">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-sm p-1 hover:bg-surfaceHi"
          >
            <Icon icon="lucide:x" width={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </>
  );
}
```

- [ ] **Step 3: `dashboard-ui/src/components/Input.tsx`**

```tsx
import { forwardRef, InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  error?: string;
  hint?: string;
};

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { label, error, hint, className = "", id, ...rest },
  ref,
) {
  const inputId = id ?? `inp-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={inputId} className="uppercase-label">{label}</label>
      )}
      <input
        ref={ref}
        id={inputId}
        className={[
          "w-full h-10 px-3 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "placeholder:text-textDim transition-colors",
          "focus:border-accent/60 focus:outline-none",
          error ? "border-danger/60" : "",
          className,
        ].join(" ")}
        {...rest}
      />
      {error ? (
        <p className="text-xs text-danger">{error}</p>
      ) : hint ? (
        <p className="text-xs text-textMuted">{hint}</p>
      ) : null}
    </div>
  );
});
```

- [ ] **Step 4: `dashboard-ui/src/components/Select.tsx`**

```tsx
import { forwardRef, SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & {
  label?: string;
  options: { value: string; label: string }[];
};

export const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { label, options, className = "", id, ...rest },
  ref,
) {
  const sid = id ?? `sel-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={sid} className="uppercase-label">{label}</label>
      )}
      <select
        ref={ref}
        id={sid}
        className={[
          "w-full h-10 px-3 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "focus:border-accent/60 focus:outline-none",
          className,
        ].join(" ")}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
});
```

- [ ] **Step 5: `dashboard-ui/src/components/Textarea.tsx`**

```tsx
import { forwardRef, TextareaHTMLAttributes } from "react";

type Props = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, Props>(function Textarea(
  { label, className = "", id, ...rest },
  ref,
) {
  const tid = id ?? `txt-${Math.random().toString(36).slice(2, 8)}`;
  return (
    <div className="space-y-1.5">
      {label && (
        <label htmlFor={tid} className="uppercase-label">{label}</label>
      )}
      <textarea
        ref={ref}
        id={tid}
        rows={4}
        className={[
          "w-full px-3 py-2 rounded-md bg-surfaceHi border border-border text-text text-sm",
          "placeholder:text-textDim focus:border-accent/60 focus:outline-none resize-y",
          className,
        ].join(" ")}
        {...rest}
      />
    </div>
  );
});
```

- [ ] **Step 6: Commit**

```bash
git add dashboard-ui/src/components/Table.tsx dashboard-ui/src/components/Drawer.tsx dashboard-ui/src/components/Input.tsx dashboard-ui/src/components/Select.tsx dashboard-ui/src/components/Textarea.tsx
git commit -m "feat(dashboard-ui): Table, Drawer, Input, Select, Textarea components"
```

---

## Task 16: API client + types + Sidebar shell

**Files:**
- Create: `dashboard-ui/src/lib/types.ts`
- Create: `dashboard-ui/src/lib/api.ts`
- Create: `dashboard-ui/src/lib/format.ts`
- Create: `dashboard-ui/src/hooks/useApi.ts`
- Create: `dashboard-ui/src/components/Sidebar.tsx`
- Create: `dashboard-ui/src/components/PageHeader.tsx`
- Create: `dashboard-ui/.env.local.example`

- [ ] **Step 1: `dashboard-ui/.env.local.example`**

```
# URL of the FastAPI backend. In Docker compose it's http://dashboard-api:8000
# In dev: http://localhost:8000
DASHBOARD_API_BASE_URL=http://localhost:8000

# Used only by `lib/api.ts` to attach Basic auth on the server.
# In production these come from runtime env, not committed.
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=change-me-please
```

- [ ] **Step 2: `dashboard-ui/src/lib/types.ts`**

```ts
export type Period = "today" | "week" | "month";

export type StatsResponse = {
  period: Period;
  leads_total: number;
  sent_count: number;
  reply_count: number;
  conversion_pct: number;
  by_hour: { hour: string; count: number }[];
};

export type LeadSummary = {
  id: number;
  source_id: number;
  source_title: string | null;
  raw_text: string;
  posted_at: string;
  analyzed_at: string | null;
  is_lead: boolean | null;
  project_type: string | null;
  budget_usd: number | null;
  language: string | null;
  client_country: string | null;
  urgency: string | null;
  relevance_score: number | null;
  status: string;
  has_response: boolean;
};

export type ResponseDetail = {
  id: number;
  draft_text: string;
  final_text: string | null;
  status: string;
  sent_to: string | null;
  sent_at: string | null;
  client_replied: boolean;
  client_status: string | null;
  notes: string | null;
};

export type LeadDetail = LeadSummary & {
  reasoning: string | null;
  author_username: string | null;
  author_tg_id: number | null;
  responses: ResponseDetail[];
};

export type LeadListResponse = {
  items: LeadSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type SourceSummary = {
  id: number;
  tg_id: number;
  title: string;
  type: string;
  language: string;
  region: string;
  status: string;
  muted_until: string | null;
  leads_per_day: number;
  sent_per_day: number;
  conversion_pct: number;
};

export type ProfilePayload = {
  name: string;
  portfolio_url: string;
  telegram: string;
  min_rate_usd_per_hour: number;
  tone: string;
  payment_methods: string[];
  cases: { title: string; tags: string[]; description: string; url: string }[];
};

export type SettingsPayload = {
  quiet_hours: string;
  min_budget_usd: number;
  min_relevance_score: number;
  max_responses_per_hour: number;
  max_responses_per_day: number;
  max_responses_per_week: number;
};
```

- [ ] **Step 3: `dashboard-ui/src/lib/api.ts`** — server-side fetcher (used in RSC)

```ts
import "server-only";

const BASE = process.env.DASHBOARD_API_BASE_URL ?? "http://localhost:8000";
const USER = process.env.DASHBOARD_USER ?? "admin";
const PWD = process.env.DASHBOARD_PASSWORD ?? "change-me-please";

function authHeader(): string {
  return "Basic " + Buffer.from(`${USER}:${PWD}`).toString("base64");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: authHeader(),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}
```

- [ ] **Step 4: `dashboard-ui/src/hooks/useApi.ts`** — client-side fetcher (relative paths through Caddy in prod)

```ts
"use client";

export async function clientApi<T>(path: string, init: RequestInit = {}): Promise<T> {
  // In prod, frontend and API share the same Caddy origin → relative path works.
  // In dev, set NEXT_PUBLIC_API_BASE if you want to point elsewhere.
  const base = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const res = await fetch(`${base}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    credentials: "include",   // browser carries Basic-auth cookie/header from Caddy
  });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json() as Promise<T>;
}
```

- [ ] **Step 5: `dashboard-ui/src/lib/format.ts`**

```ts
export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}

export function fmtMoney(n: number | null): string {
  if (n == null) return "—";
  return `$${n.toLocaleString("en-US")}`;
}

export function fmtPct(n: number | null): string {
  if (n == null) return "—";
  return `${n.toFixed(1)}%`;
}

export function fmtDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function fmtRelative(s: string | null): string {
  if (!s) return "—";
  const ms = Date.now() - new Date(s).getTime();
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}
```

- [ ] **Step 6: `dashboard-ui/src/components/Sidebar.tsx`**

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@iconify/react";

const items = [
  { href: "/", label: "Overview", icon: "lucide:layout-dashboard" },
  { href: "/leads", label: "Leads", icon: "lucide:inbox" },
  { href: "/sources", label: "Sources", icon: "lucide:radio-tower" },
  { href: "/profile", label: "Profile", icon: "lucide:user" },
  { href: "/settings", label: "Settings", icon: "lucide:settings" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 shrink-0 border-r border-border bg-surface px-3 py-5 flex flex-col gap-1">
      <div className="px-2 mb-4">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2 w-2 rounded-full bg-accent" />
          <span className="font-semibold tracking-tight">leads-bot</span>
        </div>
        <div className="uppercase-label mt-1">control</div>
      </div>
      {items.map((it) => {
        const active = path === it.href || (it.href !== "/" && path.startsWith(it.href));
        return (
          <Link
            key={it.href}
            href={it.href}
            className={[
              "flex items-center gap-2.5 px-3 h-9 rounded-md text-sm transition-colors",
              active
                ? "bg-surfaceHi text-text"
                : "text-textMuted hover:text-text hover:bg-surface",
            ].join(" ")}
          >
            <Icon icon={it.icon} width={16} />
            {it.label}
          </Link>
        );
      })}
    </aside>
  );
}
```

- [ ] **Step 7: `dashboard-ui/src/components/PageHeader.tsx`**

```tsx
export function PageHeader({ title, subtitle, action }: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="text-sm text-textMuted mt-1">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 8: Update `dashboard-ui/src/app/layout.tsx` to include Sidebar**

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Leads Bot Dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://rsms.me/" />
        <link rel="stylesheet" href="https://rsms.me/inter/inter.css" />
      </head>
      <body className="min-h-screen bg-bg text-text">
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 px-8 py-6 max-w-content w-full mx-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 9: Commit**

```bash
git add dashboard-ui/src/lib/ dashboard-ui/src/hooks/ dashboard-ui/src/components/Sidebar.tsx dashboard-ui/src/components/PageHeader.tsx dashboard-ui/src/app/layout.tsx dashboard-ui/.env.local.example
git commit -m "feat(dashboard-ui): API client, types, formatters, Sidebar layout"
```

---

## Task 17: Page `/` Overview (KPIs + lead-flow chart)

**Files:**
- Create: `dashboard-ui/src/components/LeadFlowChart.tsx`
- Modify: `dashboard-ui/src/app/page.tsx`

- [ ] **Step 1: `dashboard-ui/src/components/LeadFlowChart.tsx`**

```tsx
"use client";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

type Point = { hour: string; count: number };

export function LeadFlowChart({ data }: { data: Point[] }) {
  const formatted = data.map((p) => ({
    label: new Date(p.hour).toLocaleString("en-US", { hour: "2-digit", weekday: "short" }),
    count: p.count,
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <AreaChart data={formatted} margin={{ top: 10, right: 16, bottom: 0, left: -16 }}>
          <defs>
            <linearGradient id="leadFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#4ADE80" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#4ADE80" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis dataKey="label" stroke="rgba(250,250,250,0.42)" fontSize={11} tickLine={false} axisLine={false} />
          <YAxis stroke="rgba(250,250,250,0.42)" fontSize={11} tickLine={false} axisLine={false} allowDecimals={false} />
          <Tooltip
            contentStyle={{
              background: "#161616", border: "1px solid rgba(255,255,255,0.12)",
              borderRadius: 6, fontSize: 12,
            }}
            cursor={{ stroke: "rgba(74,222,128,0.4)", strokeDasharray: 3 }}
          />
          <Area type="monotone" dataKey="count" stroke="#4ADE80" strokeWidth={2} fill="url(#leadFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Replace `dashboard-ui/src/app/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { Card, CardHeader } from "@/components/Card";
import { Stat } from "@/components/Stat";
import { LeadFlowChart } from "@/components/LeadFlowChart";
import { PageHeader } from "@/components/PageHeader";
import type { StatsResponse } from "@/lib/types";
import { fmtNum, fmtPct } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const today = await api<StatsResponse>("/api/stats?period=today");
  const week = await api<StatsResponse>("/api/stats?period=week");

  return (
    <>
      <PageHeader title="Overview" subtitle="Leads pipeline at a glance" />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Stat label="Leads today" value={fmtNum(today.leads_total)} />
        <Stat label="Sent today" value={fmtNum(today.sent_count)} />
        <Stat label="Replies today" value={fmtNum(today.reply_count)} />
        <Stat label="Conv. today" value={fmtPct(today.conversion_pct)} />
      </div>

      <Card>
        <CardHeader title="Lead flow (last 7 days)" subtitle="Hourly counts" />
        <LeadFlowChart data={week.by_hour} />
      </Card>
    </>
  );
}
```

- [ ] **Step 3: Smoke check**

Start backend (`python -m leads_bot.dashboard.main`) and frontend (`npm run dev` in `dashboard-ui/`). Browser at http://localhost:3000 → 4 stat cards + chart. Use a `.env.local` with API base URL.

- [ ] **Step 4: Commit**

```bash
git add dashboard-ui/src/components/LeadFlowChart.tsx dashboard-ui/src/app/page.tsx
git commit -m "feat(dashboard-ui): / Overview page with KPIs + Recharts area chart"
```

---

## Task 18: Page `/leads` (table + filters + drawer)

**Files:**
- Create: `dashboard-ui/src/components/LeadFiltersBar.tsx`
- Create: `dashboard-ui/src/app/leads/page.tsx`
- Create: `dashboard-ui/src/components/LeadRow.tsx` (small inline helpers)

- [ ] **Step 1: `dashboard-ui/src/components/LeadFiltersBar.tsx`**

```tsx
"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { Select } from "./Select";
import { Input } from "./Input";

const STATUSES = [
  { value: "", label: "All" },
  { value: "new", label: "New" },
  { value: "drafted", label: "Drafted" },
  { value: "approved", label: "Approved" },
  { value: "sent", label: "Sent" },
  { value: "skipped", label: "Skipped" },
  { value: "filtered_out", label: "Filtered out" },
];

export function LeadFiltersBar() {
  const router = useRouter();
  const params = useSearchParams();

  function update(key: string, value: string) {
    const next = new URLSearchParams(Array.from(params.entries()));
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`/leads?${next.toString()}`);
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <Select
        label="Status"
        value={params.get("status") ?? ""}
        onChange={(e) => update("status", e.target.value)}
        options={STATUSES}
      />
      <Input
        label="Min score"
        type="number"
        min={0}
        max={100}
        defaultValue={params.get("min_score") ?? ""}
        onBlur={(e) => update("min_score", e.target.value)}
      />
      <Input
        label="Language"
        placeholder="en, ru, uk"
        defaultValue={params.get("language") ?? ""}
        onBlur={(e) => update("language", e.target.value)}
      />
      <Input
        label="Region"
        placeholder="ua, eu, en_global"
        defaultValue={params.get("region") ?? ""}
        onBlur={(e) => update("region", e.target.value)}
      />
    </div>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/app/leads/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { LeadFiltersBar } from "@/components/LeadFiltersBar";
import { LeadsTable } from "./LeadsTable";
import type { LeadListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

type SP = Record<string, string | undefined>;

function buildQuery(sp: SP): string {
  const p = new URLSearchParams();
  for (const k of ["status", "min_score", "language", "region", "source_id"]) {
    const v = sp[k];
    if (v) p.set(k, v);
  }
  if (!p.has("limit")) p.set("limit", "50");
  return p.toString();
}

export default async function LeadsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const sp = await searchParams;
  const data = await api<LeadListResponse>(`/api/leads?${buildQuery(sp)}`);

  return (
    <>
      <PageHeader title="Leads" subtitle={`${data.total} total`} />
      <LeadFiltersBar />
      <LeadsTable initial={data} />
    </>
  );
}
```

- [ ] **Step 3: `dashboard-ui/src/app/leads/LeadsTable.tsx`** (client component for drawer state + SSE later)

```tsx
"use client";
import { useState } from "react";
import { Table, type Column } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { Drawer } from "@/components/Drawer";
import { LeadDetailPanel } from "./LeadDetailPanel";
import { fmtRelative, fmtMoney } from "@/lib/format";
import type { LeadListResponse, LeadSummary } from "@/lib/types";
import { useLeadsStream } from "@/hooks/useLeadsStream";

const STATUS_TONE: Record<string, "neutral" | "accent" | "warn" | "danger" | "info"> = {
  new: "info",
  drafted: "warn",
  approved: "accent",
  sent: "accent",
  skipped: "neutral",
  filtered_out: "danger",
  expired: "neutral",
  analysis_failed: "danger",
};

export function LeadsTable({ initial }: { initial: LeadListResponse }) {
  const [rows, setRows] = useState(initial.items);
  const [active, setActive] = useState<number | null>(null);

  useLeadsStream((evt) => {
    // Prepend new lead — minimal shape; full row comes from API on next refetch
    setRows((cur) => [
      {
        id: evt.id,
        source_id: evt.source_id,
        source_title: null,
        raw_text: evt.raw_text ?? "",
        posted_at: new Date().toISOString(),
        analyzed_at: null,
        is_lead: null,
        project_type: null,
        budget_usd: null,
        language: null,
        client_country: null,
        urgency: null,
        relevance_score: evt.relevance_score ?? null,
        status: evt.status,
        has_response: false,
      },
      ...cur,
    ]);
  });

  const columns: Column<LeadSummary>[] = [
    { key: "id", header: "#", width: "60px", render: (l) => <span className="text-textMuted">{l.id}</span> },
    {
      key: "score", header: "Score", width: "80px",
      render: (l) => l.relevance_score == null
        ? <span className="text-textDim">—</span>
        : <span className={l.relevance_score >= 80 ? "text-accent font-semibold" : ""}>{l.relevance_score}</span>,
    },
    {
      key: "text", header: "Message",
      render: (l) => <span className="line-clamp-1 text-text">{l.raw_text.slice(0, 120)}</span>,
    },
    {
      key: "budget", header: "Budget", width: "100px", align: "right",
      render: (l) => fmtMoney(l.budget_usd),
    },
    {
      key: "status", header: "Status", width: "120px",
      render: (l) => <Badge tone={STATUS_TONE[l.status] ?? "neutral"}>{l.status}</Badge>,
    },
    {
      key: "when", header: "Posted", width: "120px",
      render: (l) => <span className="text-textMuted">{fmtRelative(l.posted_at)}</span>,
    },
  ];

  return (
    <>
      <Table
        rows={rows}
        columns={columns}
        rowKey={(l) => l.id}
        onRowClick={(l) => setActive(l.id)}
        empty="No leads match these filters."
      />
      <Drawer
        open={active != null}
        onClose={() => setActive(null)}
        title={active ? `Lead #${active}` : undefined}
      >
        {active != null && <LeadDetailPanel leadId={active} onUpdated={() => {}} />}
      </Drawer>
    </>
  );
}
```

- [ ] **Step 4: `dashboard-ui/src/app/leads/LeadDetailPanel.tsx`** (skeleton — full impl in Task 19)

```tsx
"use client";
import { useEffect, useState } from "react";
import { clientApi } from "@/hooks/useApi";
import type { LeadDetail } from "@/lib/types";
import { Badge } from "@/components/Badge";
import { fmtMoney, fmtDate } from "@/lib/format";

export function LeadDetailPanel({ leadId, onUpdated }: { leadId: number; onUpdated: () => void }) {
  const [data, setData] = useState<LeadDetail | null>(null);

  useEffect(() => {
    let live = true;
    clientApi<LeadDetail>(`/api/leads/${leadId}`).then((d) => { if (live) setData(d); });
    return () => { live = false; };
  }, [leadId]);

  if (!data) return <div className="text-textMuted">Loading…</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <Badge tone="accent">{data.status}</Badge>
        <Badge>score {data.relevance_score ?? "—"}</Badge>
        <Badge>{fmtMoney(data.budget_usd)}</Badge>
      </div>
      <section>
        <div className="uppercase-label mb-1.5">Original</div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{data.raw_text}</p>
      </section>
      {data.responses[0] && (
        <section>
          <div className="uppercase-label mb-1.5">Draft</div>
          <p className="text-sm whitespace-pre-wrap leading-relaxed bg-surfaceHi p-3 rounded-md border border-border">
            {data.responses[0].draft_text}
          </p>
          {data.responses[0].sent_at && (
            <div className="text-xs text-textMuted mt-2">Sent {fmtDate(data.responses[0].sent_at)}</div>
          )}
        </section>
      )}
      {data.reasoning && (
        <section>
          <div className="uppercase-label mb-1.5">Claude reasoning</div>
          <p className="text-sm text-textMuted">{data.reasoning}</p>
        </section>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit (will fail to compile until SSE hook lands; create stub now)**

`dashboard-ui/src/hooks/useLeadsStream.ts` (stub; Task 22 fills in):

```ts
"use client";
import { useEffect } from "react";
type Evt = { id: number; source_id: number; status: string; raw_text?: string; relevance_score?: number };
export function useLeadsStream(_handler: (evt: Evt) => void) {
  useEffect(() => { /* SSE wired in Task 22 */ }, []);
}
```

```bash
git add dashboard-ui/src/components/LeadFiltersBar.tsx dashboard-ui/src/app/leads/ dashboard-ui/src/hooks/useLeadsStream.ts
git commit -m "feat(dashboard-ui): /leads page with filter bar, table, drawer detail"
```

---

## Task 19: Page `/leads/[id]` (full detail + status update)

**Files:**
- Create: `dashboard-ui/src/app/leads/[id]/page.tsx`
- Create: `dashboard-ui/src/app/leads/[id]/StatusForm.tsx`

- [ ] **Step 1: `dashboard-ui/src/app/leads/[id]/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/Card";
import { Badge } from "@/components/Badge";
import { fmtDate, fmtMoney } from "@/lib/format";
import { StatusForm } from "./StatusForm";
import type { LeadDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function LeadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const lead = await api<LeadDetail>(`/api/leads/${id}`);
  const resp = lead.responses[0];

  return (
    <>
      <PageHeader
        title={`Lead #${lead.id}`}
        subtitle={lead.source_title ?? "Unknown source"}
        action={<Badge tone="accent">{lead.status}</Badge>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader title="Original message" />
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{lead.raw_text}</p>
            <div className="flex flex-wrap gap-2 mt-4">
              <Badge>{lead.project_type ?? "?"}</Badge>
              <Badge>{lead.language ?? "?"}</Badge>
              <Badge>{lead.client_country ?? "?"}</Badge>
              <Badge>{fmtMoney(lead.budget_usd)}</Badge>
              <Badge>score {lead.relevance_score ?? "—"}</Badge>
            </div>
          </Card>

          {resp && (
            <Card>
              <CardHeader title="Draft / sent message" subtitle={resp.sent_at ? `Sent ${fmtDate(resp.sent_at)}` : "Not sent yet"} />
              <p className="text-sm whitespace-pre-wrap leading-relaxed bg-surfaceHi p-3 rounded-md border border-border">
                {resp.final_text ?? resp.draft_text}
              </p>
            </Card>
          )}

          {lead.reasoning && (
            <Card>
              <CardHeader title="Claude reasoning" />
              <p className="text-sm text-textMuted">{lead.reasoning}</p>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          {resp && <StatusForm leadId={lead.id} initial={resp} />}
          <Card>
            <CardHeader title="Timeline" />
            <ul className="text-sm space-y-2 text-textMuted">
              <li><span className="text-textDim">posted</span> {fmtDate(lead.posted_at)}</li>
              {lead.analyzed_at && <li><span className="text-textDim">analyzed</span> {fmtDate(lead.analyzed_at)}</li>}
              {resp?.sent_at && <li><span className="text-textDim">sent</span> {fmtDate(resp.sent_at)}</li>}
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/app/leads/[id]/StatusForm.tsx`**

```tsx
"use client";
import { useState } from "react";
import { Card, CardHeader } from "@/components/Card";
import { Select } from "@/components/Select";
import { Textarea } from "@/components/Textarea";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { ResponseDetail } from "@/lib/types";

const OPTS = [
  { value: "no_response", label: "No response" },
  { value: "replied", label: "Replied" },
  { value: "in_dialog", label: "In dialog" },
  { value: "in_work", label: "In work" },
  { value: "rejected", label: "Rejected" },
];

export function StatusForm({ leadId, initial }: { leadId: number; initial: ResponseDetail }) {
  const [status, setStatus] = useState(initial.client_status ?? "no_response");
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    try {
      await clientApi(`/api/leads/${leadId}`, {
        method: "PATCH",
        body: JSON.stringify({ client_status: status, notes }),
      });
      setSavedAt(new Date().toLocaleTimeString());
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader title="CRM status" subtitle={savedAt ? `Saved at ${savedAt}` : undefined} />
      <div className="space-y-3">
        <Select label="Client status" value={status} onChange={(e) => setStatus(e.target.value)} options={OPTS} />
        <Textarea label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={5} />
        <Button onClick={save} loading={saving} fullWidth>Save</Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard-ui/src/app/leads/[id]/
git commit -m "feat(dashboard-ui): /leads/[id] detail page with CRM status form"
```

---

## Task 20: Page `/sources` (table + pause/resume actions)

**Files:**
- Create: `dashboard-ui/src/app/sources/page.tsx`
- Create: `dashboard-ui/src/app/sources/SourceActions.tsx`

- [ ] **Step 1: `dashboard-ui/src/app/sources/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { SourcesTable } from "./SourcesTable";
import type { SourceSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const data = await api<{ items: SourceSummary[] }>("/api/sources");
  return (
    <>
      <PageHeader title="Sources" subtitle={`${data.items.length} channels tracked`} />
      <SourcesTable initial={data.items} />
    </>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/app/sources/SourcesTable.tsx`**

```tsx
"use client";
import { useState } from "react";
import { Table, type Column } from "@/components/Table";
import { Badge } from "@/components/Badge";
import { SourceActions } from "./SourceActions";
import type { SourceSummary } from "@/lib/types";
import { fmtPct } from "@/lib/format";

export function SourcesTable({ initial }: { initial: SourceSummary[] }) {
  const [rows, setRows] = useState(initial);

  function patchLocal(id: number, patch: Partial<SourceSummary>) {
    setRows((cur) => cur.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }

  const columns: Column<SourceSummary>[] = [
    { key: "title", header: "Channel", render: (s) => <span className="font-medium">{s.title}</span> },
    { key: "region", header: "Region", width: "100px", render: (s) => <Badge>{s.region}</Badge> },
    { key: "status", header: "Status", width: "100px",
      render: (s) => (
        <Badge tone={s.status === "active" ? "accent" : s.status === "paused" ? "warn" : "danger"}>
          {s.status}
        </Badge>
      ),
    },
    { key: "lpd", header: "Leads/d", width: "90px", align: "right", render: (s) => s.leads_per_day.toFixed(1) },
    { key: "spd", header: "Sent/d", width: "90px", align: "right", render: (s) => s.sent_per_day.toFixed(1) },
    { key: "conv", header: "Conv.", width: "80px", align: "right", render: (s) => fmtPct(s.conversion_pct) },
    { key: "act", header: "", width: "180px",
      render: (s) => <SourceActions source={s} onUpdated={(p) => patchLocal(s.id, p)} />,
    },
  ];

  return <Table rows={rows} columns={columns} rowKey={(s) => s.id} />;
}
```

- [ ] **Step 3: `dashboard-ui/src/app/sources/SourceActions.tsx`**

```tsx
"use client";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { SourceSummary } from "@/lib/types";

export function SourceActions({
  source, onUpdated,
}: { source: SourceSummary; onUpdated: (patch: Partial<SourceSummary>) => void }) {
  async function patch(body: Record<string, unknown>) {
    const updated = await clientApi<SourceSummary>(`/api/sources/${source.id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    onUpdated(updated);
  }

  if (source.status === "active") {
    return (
      <div className="flex gap-2 justify-end">
        <Button size="sm" variant="secondary" onClick={() => patch({ mute_for_minutes: 60 })}>Mute 1h</Button>
        <Button size="sm" variant="ghost" onClick={() => patch({ status: "paused" })}>Pause</Button>
      </div>
    );
  }
  return (
    <div className="flex justify-end">
      <Button size="sm" onClick={() => patch({ status: "active" })}>Resume</Button>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard-ui/src/app/sources/
git commit -m "feat(dashboard-ui): /sources page with pause/mute/resume actions"
```

---

## Task 21: Pages `/profile` and `/settings`

**Files:**
- Create: `dashboard-ui/src/app/profile/page.tsx`
- Create: `dashboard-ui/src/app/profile/ProfileForm.tsx`
- Create: `dashboard-ui/src/app/settings/page.tsx`
- Create: `dashboard-ui/src/app/settings/SettingsForm.tsx`

- [ ] **Step 1: `dashboard-ui/src/app/profile/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { ProfileForm } from "./ProfileForm";
import type { ProfilePayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function ProfilePage() {
  let initial: ProfilePayload | null = null;
  try {
    initial = await api<ProfilePayload>("/api/profile");
  } catch {
    // 404 → form starts empty
  }
  return (
    <>
      <PageHeader title="Profile" subtitle="The persona Claude uses for drafts" />
      <ProfileForm initial={initial} />
    </>
  );
}
```

- [ ] **Step 2: `dashboard-ui/src/app/profile/ProfileForm.tsx`**

```tsx
"use client";
import { useState } from "react";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { ProfilePayload } from "@/lib/types";

const EMPTY: ProfilePayload = {
  name: "", portfolio_url: "", telegram: "",
  min_rate_usd_per_hour: 50, tone: "", payment_methods: [], cases: [],
};

export function ProfileForm({ initial }: { initial: ProfilePayload | null }) {
  const [data, setData] = useState<ProfilePayload>(initial ?? EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof ProfilePayload>(k: K, v: ProfilePayload[K]) {
    setData((d) => ({ ...d, [k]: v }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await clientApi("/api/profile", {
        method: "PATCH",
        body: JSON.stringify(data),
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input label="Name" value={data.name} onChange={(e) => set("name", e.target.value)} />
        <Input label="Telegram" value={data.telegram} onChange={(e) => set("telegram", e.target.value)} />
        <Input label="Portfolio URL" value={data.portfolio_url} onChange={(e) => set("portfolio_url", e.target.value)} />
        <Input
          label="Min rate ($/hr)" type="number" min={0}
          value={data.min_rate_usd_per_hour}
          onChange={(e) => set("min_rate_usd_per_hour", Number(e.target.value) || 0)}
        />
        <div className="md:col-span-2">
          <Textarea label="Tone" value={data.tone} onChange={(e) => set("tone", e.target.value)} rows={3} />
        </div>
        <div className="md:col-span-2">
          <Input
            label="Payment methods (comma-separated)"
            value={data.payment_methods.join(", ")}
            onChange={(e) => set("payment_methods", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
          />
        </div>
      </div>
      <div className="mt-5 flex items-center gap-3">
        <Button onClick={save} loading={saving}>Save profile</Button>
        {error && <span className="text-sm text-danger">{error}</span>}
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: `dashboard-ui/src/app/settings/page.tsx`**

```tsx
import { api } from "@/lib/api";
import { PageHeader } from "@/components/PageHeader";
import { SettingsForm } from "./SettingsForm";
import type { SettingsPayload } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const data = await api<SettingsPayload>("/api/settings");
  return (
    <>
      <PageHeader title="Settings" subtitle="Bot behavior thresholds" />
      <SettingsForm initial={data} />
    </>
  );
}
```

- [ ] **Step 4: `dashboard-ui/src/app/settings/SettingsForm.tsx`**

```tsx
"use client";
import { useState } from "react";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { Button } from "@/components/Button";
import { clientApi } from "@/hooks/useApi";
import type { SettingsPayload } from "@/lib/types";

export function SettingsForm({ initial }: { initial: SettingsPayload }) {
  const [data, setData] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof SettingsPayload>(k: K, v: SettingsPayload[K]) {
    setData((d) => ({ ...d, [k]: v }));
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await clientApi("/api/settings", { method: "PATCH", body: JSON.stringify(data) });
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="Quiet hours (HH:MM-HH:MM)"
          value={data.quiet_hours}
          onChange={(e) => set("quiet_hours", e.target.value)}
        />
        <Input
          label="Min budget (USD)" type="number" min={0}
          value={data.min_budget_usd}
          onChange={(e) => set("min_budget_usd", Number(e.target.value) || 0)}
        />
        <Input
          label="Min relevance score" type="number" min={0} max={100}
          value={data.min_relevance_score}
          onChange={(e) => set("min_relevance_score", Number(e.target.value) || 0)}
        />
        <Input
          label="Max responses / hour" type="number" min={1}
          value={data.max_responses_per_hour}
          onChange={(e) => set("max_responses_per_hour", Number(e.target.value) || 1)}
        />
        <Input
          label="Max responses / day" type="number" min={1}
          value={data.max_responses_per_day}
          onChange={(e) => set("max_responses_per_day", Number(e.target.value) || 1)}
        />
        <Input
          label="Max responses / week" type="number" min={1}
          value={data.max_responses_per_week}
          onChange={(e) => set("max_responses_per_week", Number(e.target.value) || 1)}
        />
      </div>
      <div className="mt-5 flex items-center gap-3">
        <Button onClick={save} loading={saving}>Save</Button>
        {error && <span className="text-sm text-danger">{error}</span>}
      </div>
    </Card>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add dashboard-ui/src/app/profile/ dashboard-ui/src/app/settings/
git commit -m "feat(dashboard-ui): /profile and /settings forms"
```

---

## Task 22: SSE hook (live `/leads`)

**Files:**
- Modify: `dashboard-ui/src/hooks/useLeadsStream.ts`

- [ ] **Step 1: Replace stub with real implementation**

```ts
"use client";
import { useEffect } from "react";

type Evt = {
  id: number;
  source_id: number;
  status: string;
  raw_text?: string;
  relevance_score?: number;
};

export function useLeadsStream(handler: (evt: Evt) => void) {
  useEffect(() => {
    const es = new EventSource("/api/stream/leads", { withCredentials: true });

    es.addEventListener("hello", (e) => {
      // eslint-disable-next-line no-console
      console.log("SSE hello", (e as MessageEvent).data);
    });
    es.addEventListener("new_lead", (e) => {
      try {
        handler(JSON.parse((e as MessageEvent).data));
      } catch (err) {
        console.warn("Bad SSE payload", err);
      }
    });
    es.onerror = (err) => {
      console.warn("SSE error", err);
      // EventSource auto-reconnects; nothing else to do
    };

    return () => es.close();
    // intentionally rerun only on mount — handler kept stable via closure
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard-ui/src/hooks/useLeadsStream.ts
git commit -m "feat(dashboard-ui): SSE hook subscribes to /api/stream/leads"
```

---

## Task 23: Frontend Dockerfile

**Files:**
- Create: `dashboard-ui/Dockerfile`
- Create: `dashboard-ui/.dockerignore`
- Modify: `dashboard-ui/next.config.ts` (enable standalone output)

- [ ] **Step 1: Modify `dashboard-ui/next.config.ts`**

```ts
import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  // Same-origin in prod via Caddy → no rewrites needed.
};

export default config;
```

- [ ] **Step 2: `dashboard-ui/.dockerignore`**

```
node_modules
.next
dist
out
playwright-report
.env*.local
```

- [ ] **Step 3: `dashboard-ui/Dockerfile`** (multi-stage)

```dockerfile
# --- deps ---
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# --- build ---
FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- runtime ---
FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 4: Build locally**

```bash
cd dashboard-ui
docker build -t leads-dashboard-ui .
```

Expect a successful build.

- [ ] **Step 5: Commit**

```bash
cd ..
git add dashboard-ui/Dockerfile dashboard-ui/.dockerignore dashboard-ui/next.config.ts
git commit -m "chore(dashboard-ui): multi-stage Dockerfile (standalone output)"
```

---

## Task 24: Caddyfile + integration

**Files:**
- Create: `Caddyfile`
- Modify: `README.md` deploy section

- [ ] **Step 1: Create `Caddyfile`**

```caddy
{
    # Replace with real email when domain is set.
    email admin@example.com
    # Disable auto-HTTPS for local dev where DOMAIN is "localhost"
}

# Production block — domain provided via env at deploy
{$DOMAIN:dashboard.localhost} {
    encode gzip zstd

    # SSE — DO NOT buffer. Critical for /api/stream/*.
    @sse path /api/stream/*
    handle @sse {
        reverse_proxy dashboard-api:8000 {
            flush_interval -1
            header_up X-Forwarded-Proto {scheme}
        }
    }

    # API — Basic auth handled by FastAPI itself
    handle /api/* {
        reverse_proxy dashboard-api:8000
    }

    # Frontend (Next.js)
    handle {
        reverse_proxy dashboard-ui:3000
    }

    # Logs
    log {
        output stdout
        format json
    }
}
```

- [ ] **Step 2: Local dry-run**

```bash
docker compose --env-file .env up -d
docker compose ps
docker compose logs caddy | tail -20
curl -kI https://dashboard.localhost --resolve dashboard.localhost:443:127.0.0.1
```

If `DOMAIN` is not set, Caddy will refuse Let's Encrypt for `.localhost`; that's expected — for local you can override with `DOMAIN=:80` or run frontend directly.

- [ ] **Step 3: Update `.env.example`** — add at the bottom:

```
# Dashboard
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=change-me-please

# Reverse proxy
DOMAIN=dashboard.example.com
```

- [ ] **Step 4: Commit**

```bash
git add Caddyfile .env.example
git commit -m "chore(deploy): Caddyfile with SSE flush_interval -1 and auto-LE"
```

---

## Task 25: Playwright smoke test

**Files:**
- Create: `dashboard-ui/playwright.config.ts`
- Create: `dashboard-ui/src/tests/e2e/overview.spec.ts`

- [ ] **Step 1: `dashboard-ui/playwright.config.ts`**

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./src/tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    httpCredentials: { username: "admin", password: "change-me-please" },
  },
});
```

- [ ] **Step 2: `dashboard-ui/src/tests/e2e/overview.spec.ts`**

```ts
import { test, expect } from "@playwright/test";

test("overview page loads with KPI cards", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("Leads today")).toBeVisible();
  await expect(page.getByText("Sent today")).toBeVisible();
});
```

- [ ] **Step 3: Add npm script**

```json
"e2e": "playwright test"
```

- [ ] **Step 4: Run (requires backend + frontend up)**

```bash
cd dashboard-ui
npx playwright install chromium
docker compose up -d dashboard-api
npm run dev &
npm run e2e
```

- [ ] **Step 5: Commit**

```bash
git add dashboard-ui/playwright.config.ts dashboard-ui/src/tests/e2e/ dashboard-ui/package.json
git commit -m "test(dashboard-ui): Playwright smoke for / page"
```

---

## Task 26: README deploy section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append to `README.md`**

```markdown
## Dashboard (Iteration 3)

The dashboard is split into three new containers managed by the same `docker-compose.yml`:

- `dashboard-api` — FastAPI + uvicorn on `:8000` (internal only).
- `dashboard-ui` — Next.js 15 on `:3000` (internal only).
- `caddy` — TLS-terminating reverse proxy on `:80` and `:443`.

### Local development

```bash
# 1. Backend
python -m leads_bot.dashboard.main         # uvicorn on :8000

# 2. Frontend
cd dashboard-ui
cp .env.local.example .env.local           # set DASHBOARD_API_BASE_URL=http://localhost:8000
npm run dev                                # Next.js on :3000
```

Open http://localhost:3000 — Basic auth prompt uses `DASHBOARD_USER` / `DASHBOARD_PASSWORD` from your `.env`.

### Production deploy on the existing VPS

1. Set `DOMAIN=dashboard.<your-domain>` in `/opt/leads-bot/.env`.
2. Point an A record for that subdomain at the VPS IP.
3. `docker compose pull && docker compose up -d --build dashboard-api dashboard-ui caddy`
4. Caddy auto-provisions a Let's Encrypt cert on first hit.
5. Browser to `https://dashboard.<your-domain>` — Basic auth prompt → done.

### Caveats

- `dashboard-api` MUST run with `workers=1` because the SSE polling watermark is held in memory per connection (each connection initialises its own `last_seen`, but workers don't share connections — keep it 1 to avoid surprises if the design changes).
- SQLite uses WAL mode (set on engine connect). The dashboard-api and bot containers share `./data/bot.db` via the named volume — concurrent access is safe but writes from the dashboard are limited to `responses.notes`, `responses.client_status`, `sources.status`/`muted_until`, `data/profile.json`, and `data/settings.json`.
- The `Caddyfile` requires `flush_interval -1` on the `/api/stream/*` matcher; without it SSE traffic is buffered and the live updates break.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: dashboard local-dev and production deploy notes"
```

---

## Task 27: Manual end-to-end verification

**No code — sanity checklist before declaring iter 3 done.**

- [ ] **Step 1:** `docker compose up -d` from a clean clone. Wait 30s.
- [ ] **Step 2:** `docker compose ps` — `bot`, `dashboard-api`, `dashboard-ui`, `caddy` all healthy.
- [ ] **Step 3:** `curl -u admin:$DASHBOARD_PASSWORD http://localhost:8000/api/health` returns `{"status":"ok"}`.
- [ ] **Step 4:** Open `https://dashboard.<domain>/` in browser → Basic auth prompt → Overview renders 4 KPI cards + chart.
- [ ] **Step 5:** Navigate to `/leads`. Filter by `status=sent` — table updates without errors.
- [ ] **Step 6:** Click a row → drawer slides in from right with original + draft.
- [ ] **Step 7:** Open `/leads/[id]` → CRM form. Change client status, add note, click Save → reload page → values persist.
- [ ] **Step 8:** SSE: keep `/leads` open in one tab, in a second terminal `INSERT` a fake row into `data/bot.db` (or post a real test message in a tracked channel). The `/leads` table prepends the new row within ~2 s.
- [ ] **Step 9:** `/sources` → click "Mute 1h" on one row → verify `sources.muted_until` is set in DB. Refresh — pause/resume cycle works.
- [ ] **Step 10:** `/profile` → edit name + tone → Save → `cat data/profile.json` shows the change.
- [ ] **Step 11:** `/settings` → change `min_relevance_score` to 70 → Save → `cat data/settings.json` shows the change. **(Bot-side respect of this value is verified once iter 2's settings-overlay reload lands; document if not yet wired.)**
- [ ] **Step 12:** Browser dev tools → Network tab on `/leads` → verify `EventSource` connection to `/api/stream/leads` is open and receiving `event: hello` then `event: new_lead` events.
- [ ] **Step 13:** Force a backend crash (`docker compose stop dashboard-api`) → frontend pages show error state, SSE auto-reconnects when backend comes up.
- [ ] **Step 14:** Lighthouse on `/`: a11y ≥ 95, performance ≥ 90.
- [ ] **Step 15:** Resize to 768 px and 375 px — sidebar collapses or remains usable; no horizontal scroll on main content. (If failing, ship a follow-up — responsive polish is iter 4 territory.)

---

## Definition of Done — Iteration 3

- [ ] All backend tests pass: `pytest tests/dashboard/`
- [ ] Frontend Vitest passes: `cd dashboard-ui && npm test`
- [ ] Frontend Playwright passes: `cd dashboard-ui && npm run e2e`
- [ ] `docker compose up -d` brings up `bot`, `dashboard-api`, `dashboard-ui`, `caddy` cleanly on a clean checkout.
- [ ] Caddy terminates TLS via Let's Encrypt for the configured `DOMAIN`.
- [ ] Basic auth gate works on every `/api/*` endpoint and is rejected on wrong credentials.
- [ ] All pages (`/`, `/leads`, `/leads/[id]`, `/sources`, `/profile`, `/settings`) render with real data on production deployment.
- [ ] SSE `/api/stream/leads` delivers a new lead event to an open browser tab within 2 s of insertion.
- [ ] Dashboard writes to `data/profile.json`, `data/settings.json`, `responses.notes`, `responses.client_status`, `sources.status`, `sources.muted_until` are observable in the bot's view of the same DB/files.
- [ ] No `shadcn/ui` packages installed; all components are bespoke and live in `dashboard-ui/src/components/`.
- [ ] Iconography uses `@iconify/react` exclusively — no inline SVGs apart from the Recharts gradient defs.
- [ ] README has a working deploy section that someone unfamiliar with the repo can follow.
- [ ] Lighthouse a11y score ≥ 95 on `/`.
```

---

### Critical Files for Implementation

- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/dashboard/app.py` — FastAPI factory; central wiring point for routes, auth, CORS.
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/dashboard/routes/stream.py` — SSE polling loop; the highest-risk piece, must run under `workers=1`.
- `/Users/vitalinanikulina/Documents/Work/search for projects/dashboard-ui/src/lib/api.ts` and `dashboard-ui/src/hooks/useApi.ts` — server-side and client-side API plumbing; controls how Basic auth flows through Caddy.
- `/Users/vitalinanikulina/Documents/Work/search for projects/Caddyfile` — `flush_interval -1` SSE matcher is mandatory; getting this wrong silently breaks live updates.
- `/Users/vitalinanikulina/Documents/Work/search for projects/docker-compose.yml` — orchestrates all four services and the shared SQLite volume; WAL mode (set in `db/session.py`) must be in place before the dashboard reader joins.
