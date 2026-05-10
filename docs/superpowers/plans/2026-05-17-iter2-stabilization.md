# Iteration 2 — Stabilization & UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the Iteration 1 MVP from "works, but needs babysitting" to "runs 24/7 without owner attention." Add quiet-hours logic with a morning digest, a full Telegram command surface (`/stats`, `/sources`, `/profile`, `/pause`, `/resume`, `/templates`, `/draft`, `/quiet`), persist sources as a CRUD-able DB table (with `/sources add @link` resolving via Telethon), implement the full edit-response state machine (replacing the Iter1 stub), add health monitoring with auto-alerts, set up automated SQLite backups via cron + script, and harden antiban with hourly `rate_limits` rotation.

**Architecture:** Same modular monolith as Iter1. New modules added: `notifier/commands.py` (FSM command router), `notifier/edit_flow.py` (FSM states for edit), `notifier/digest.py` (morning digest builder), `scheduler.py` (asyncio background loops for quiet-hours digest, healthcheck, rate-limit rotation), `sources/service.py` (CRUD + Telethon channel resolution). Backup is a standalone Python script invoked by host cron.

**Tech Stack:** Python 3.13, Telethon 1.36, aiogram 3.13 (with `aiogram.fsm.MemoryStorage`), SQLAlchemy 2.0 async, Alembic, pytest 8.3 / pytest-asyncio 0.24 / pytest-mock 3.14, loguru, Docker. **No new runtime deps** — APScheduler is intentionally NOT used; we use plain `asyncio.create_task` loops to keep the dependency surface small.

**Spec reference:** `docs/superpowers/specs/2026-05-10-telegram-leads-bot-design.md` — sections §6.4 (notifier), §9.2 (commands), §9.3 (morning digest), §11.1 (antiban), §11.2 (health monitoring), §8.8 (backup), §13 (Iter 2 scope).

---

## File Structure

**New files:**

```
.
├── scripts/
│   └── backup.py                                       # NEW — invoked by host cron
├── deploy/
│   └── crontab.example                                 # NEW — sample host crontab line
├── src/leads_bot/
│   ├── scheduler.py                                    # NEW — quiet/digest/health/rotation loops
│   ├── time_utils.py                                   # NEW — quiet-hours helpers (tz-aware)
│   ├── health/
│   │   ├── __init__.py                                 # NEW
│   │   └── monitor.py                                  # NEW — GetMe ping + alert
│   ├── sources/
│   │   ├── __init__.py                                 # NEW
│   │   └── service.py                                  # NEW — list/add/pause/resume + Telethon resolve
│   └── notifier/
│       ├── commands.py                                 # NEW — /stats, /sources, /profile, /pause, etc.
│       ├── digest.py                                   # NEW — morning digest builder + sender
│       ├── edit_flow.py                                # NEW — aiogram FSM for ✏️ edit
│       └── states.py                                   # NEW — FSM state classes
└── tests/
    ├── unit/
    │   ├── test_time_utils.py                          # NEW
    │   ├── test_sources_service.py                     # NEW
    │   ├── test_commands.py                            # NEW
    │   ├── test_digest.py                              # NEW
    │   ├── test_edit_flow.py                           # NEW
    │   ├── test_health_monitor.py                      # NEW
    │   ├── test_rate_limit_rotation.py                 # NEW
    │   └── test_backup_script.py                       # NEW
    └── integration/
        └── test_quiet_hours_flow.py                    # NEW
```

**Modified files (with what changes):**

| File | Change |
|---|---|
| `src/leads_bot/config.py` | Add `quiet_hours_enabled`, `digest_time`, `healthcheck_interval_sec`, `healthcheck_failure_threshold`, `rate_limit_retention_hours`. |
| `.env.example` | Document the new settings above. |
| `src/leads_bot/db/models.py` | Drop `seed.py`-based regions check, add nothing schema-wise (sources table already exists). Add `BotState` model for global pause + rate-limit rotation timestamps. |
| `src/leads_bot/db/migrations/versions/<new>_iter2.py` | New Alembic migration for `bot_state` table. |
| `src/leads_bot/notifier/handlers.py` | Replace the `edit` stub with a call into `edit_flow.start_edit(...)`; respect global pause from `BotState`. |
| `src/leads_bot/notifier/bot.py` | Build dispatcher with `MemoryStorage` for FSM; expose `send_lead_card` already exists. |
| `src/leads_bot/pipeline.py` | Before `send_lead_card`, check quiet-hours: if quiet, mark response as `pending_digest` instead of sending the card (still create the response row). |
| `src/leads_bot/db/seed.py` | Keep but make it OPTIONAL — sources are now CRUD-managed. Document that `data/sources.json` is bootstrap-only. |
| `src/leads_bot/main.py` | Wire `scheduler.start_background_tasks(...)`, register `commands` router, enable FSM, register edit-flow handler. |
| `src/leads_bot/sender/sender.py` | (Optional) make `_resolve_target` defensive when source row was unloaded — uses session re-fetch. |
| `Dockerfile` | Copy `scripts/` into image so cron can `docker exec` into it. |
| `README.md` | Document iter2 commands, backup setup, healthcheck config. |

---

## Task 1: Extend Config (quiet hours toggle + digest + health + rotation settings)

**Files:**
- Modify: `src/leads_bot/config.py`
- Modify: `.env.example`
- Test: `tests/unit/test_config.py` (extend existing)

- [ ] **Step 1: Add new failing tests to `tests/unit/test_config.py`**

Append to the existing file:

```python
def test_settings_quiet_hours_enabled_default(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x")]:
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.quiet_hours_enabled is True
    assert s.digest_time == "08:15"
    assert s.healthcheck_interval_sec == 600
    assert s.healthcheck_failure_threshold == 3
    assert s.rate_limit_retention_hours == 168


def test_settings_digest_time_parsed(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
                 ("DIGEST_TIME", "09:30")]:
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.digest_time_hm == (9, 30)


def test_settings_quiet_hours_disabled_when_set_false(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
                 ("QUIET_HOURS_ENABLED", "false")]:
        monkeypatch.setenv(k, v)
    s = Settings()
    assert s.quiet_hours_enabled is False
```

- [ ] **Step 2: Run tests, expect failure**

```bash
pytest tests/unit/test_config.py -v
```

Expected: `AttributeError: 'Settings' object has no attribute 'quiet_hours_enabled'` (or 3 failed).

- [ ] **Step 3: Update `src/leads_bot/config.py`**

Replace the file with:

```python
"""Loads environment configuration via pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Telegram userbot
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    telegram_session_name: str = "leads_bot_session"

    # Bot for owner
    bot_token: str
    owner_tg_id: int

    # Anthropic
    anthropic_api_key: str
    analyzer_model: str = "claude-haiku-4-5"
    drafter_model: str = "claude-sonnet-4-6"

    # DB
    database_url: str = "sqlite+aiosqlite:///data/bot.db"

    # Behavior
    min_budget_usd: int = 300
    min_relevance_score: int = 60
    quiet_hours: str = "23:00-08:00"
    quiet_hours_enabled: bool = True
    digest_time: str = "08:15"
    timezone: str = "Asia/Bangkok"

    # Rate limits
    max_responses_per_hour: int = 5
    max_responses_per_day: int = 30
    max_responses_per_week: int = 150
    max_dm_new_contacts_per_hour: int = 3

    # Antiban delays (sec)
    send_delay_min: int = 30
    send_delay_max: int = 90

    # Health monitoring (Iter 2)
    healthcheck_interval_sec: int = 600           # 10 min
    healthcheck_failure_threshold: int = 3        # consecutive fails -> alert

    # Rate-limit rotation (Iter 2): drop rate_limits rows older than this
    rate_limit_retention_hours: int = 168         # 7 days

    @property
    def quiet_hours_start(self) -> tuple[int, int]:
        h, m = self.quiet_hours.split("-")[0].split(":")
        return int(h), int(m)

    @property
    def quiet_hours_end(self) -> tuple[int, int]:
        h, m = self.quiet_hours.split("-")[1].split(":")
        return int(h), int(m)

    @property
    def digest_time_hm(self) -> tuple[int, int]:
        h, m = self.digest_time.split(":")
        return int(h), int(m)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

- [ ] **Step 4: Update `.env.example`**

Replace with:

```
# Telegram userbot credentials (from my.telegram.org)
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=
TELEGRAM_SESSION_NAME=leads_bot_session

# Telegram bot for owner notifications (from @BotFather)
BOT_TOKEN=
OWNER_TG_ID=

# Anthropic API
ANTHROPIC_API_KEY=

# Database
DATABASE_URL=sqlite+aiosqlite:///data/bot.db

# Behavior
MIN_BUDGET_USD=300
MIN_RELEVANCE_SCORE=60
QUIET_HOURS=23:00-08:00
QUIET_HOURS_ENABLED=true
DIGEST_TIME=08:15
TIMEZONE=Asia/Bangkok

# Rate limits
MAX_RESPONSES_PER_HOUR=5
MAX_RESPONSES_PER_DAY=30
MAX_RESPONSES_PER_WEEK=150
MAX_DM_NEW_CONTACTS_PER_HOUR=3

# Antiban delays (seconds)
SEND_DELAY_MIN=30
SEND_DELAY_MAX=90

# Health monitoring (Iteration 2)
HEALTHCHECK_INTERVAL_SEC=600
HEALTHCHECK_FAILURE_THRESHOLD=3

# rate_limits rotation (Iteration 2) — drop rows older than N hours
RATE_LIMIT_RETENTION_HOURS=168

# Claude models
ANALYZER_MODEL=claude-haiku-4-5
DRAFTER_MODEL=claude-sonnet-4-6
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_config.py -v
```

Expected: all PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add src/leads_bot/config.py .env.example tests/unit/test_config.py
git commit -m "feat(config): iter2 settings (quiet toggle, digest, healthcheck, rotation)"
```

---

## Task 2: Time Utils — quiet-hours helpers

**Files:**
- Create: `src/leads_bot/time_utils.py`
- Test: `tests/unit/test_time_utils.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_time_utils.py`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from leads_bot.time_utils import (
    is_in_quiet_window, next_quiet_end, parse_window, now_in_tz,
)


def test_parse_window_normal():
    start, end = parse_window("23:00-08:00")
    assert start == (23, 0)
    assert end == (8, 0)


def test_parse_window_same_day():
    start, end = parse_window("13:00-17:30")
    assert start == (13, 0)
    assert end == (17, 30)


@pytest.mark.parametrize("dt_str,expected", [
    ("2026-05-17 23:30", True),     # inside, after midnight crossing
    ("2026-05-17 02:00", True),     # inside, early morning
    ("2026-05-17 07:59", True),     # last minute of quiet
    ("2026-05-17 08:00", False),    # exact end -> not quiet
    ("2026-05-17 08:01", False),
    ("2026-05-17 12:00", False),
    ("2026-05-17 22:59", False),
    ("2026-05-17 23:00", True),     # exact start -> quiet
])
def test_is_in_quiet_window_overnight(dt_str, expected):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("UTC"))
    assert is_in_quiet_window(dt, (23, 0), (8, 0)) is expected


def test_is_in_quiet_window_same_day():
    # Lunch quiet: 12:00-13:00
    inside = datetime(2026, 5, 17, 12, 30, tzinfo=ZoneInfo("UTC"))
    outside = datetime(2026, 5, 17, 14, 0, tzinfo=ZoneInfo("UTC"))
    assert is_in_quiet_window(inside, (12, 0), (13, 0)) is True
    assert is_in_quiet_window(outside, (12, 0), (13, 0)) is False


def test_next_quiet_end_overnight_before_midnight():
    now = datetime(2026, 5, 17, 23, 30, tzinfo=ZoneInfo("UTC"))
    end = next_quiet_end(now, (23, 0), (8, 0))
    # End is 08:00 next day
    assert end == datetime(2026, 5, 18, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_next_quiet_end_overnight_after_midnight():
    now = datetime(2026, 5, 18, 2, 0, tzinfo=ZoneInfo("UTC"))
    end = next_quiet_end(now, (23, 0), (8, 0))
    # End is 08:00 same day
    assert end == datetime(2026, 5, 18, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_now_in_tz_returns_aware():
    n = now_in_tz("Asia/Bangkok")
    assert n.tzinfo is not None
    assert str(n.tzinfo) == "Asia/Bangkok"
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_time_utils.py -v
```

Expected: `ModuleNotFoundError: No module named 'leads_bot.time_utils'`.

- [ ] **Step 3: Implement `src/leads_bot/time_utils.py`**

```python
"""Quiet-hours and timezone helpers. Pure functions — no I/O, no DB."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def parse_window(spec: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Parse 'HH:MM-HH:MM' into ((sh, sm), (eh, em))."""
    a, b = spec.split("-")
    sh, sm = a.split(":")
    eh, em = b.split(":")
    return (int(sh), int(sm)), (int(eh), int(em))


def _hm_to_minutes(h: int, m: int) -> int:
    return h * 60 + m


def is_in_quiet_window(
    now: datetime, start: tuple[int, int], end: tuple[int, int]
) -> bool:
    """Return True if `now` is inside the quiet window.

    Window is half-open [start, end). Supports overnight windows where end < start
    (e.g. 23:00-08:00).
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    cur = _hm_to_minutes(now.hour, now.minute)
    s = _hm_to_minutes(*start)
    e = _hm_to_minutes(*end)
    if s == e:
        return False
    if s < e:
        # same-day window
        return s <= cur < e
    # overnight: quiet if cur >= s OR cur < e
    return cur >= s or cur < e


def next_quiet_end(
    now: datetime, start: tuple[int, int], end: tuple[int, int]
) -> datetime:
    """Return the next datetime when quiet hours end (i.e. when digest fires).

    If currently NOT in quiet window, returns the end of the next quiet window.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    candidate = now.replace(hour=end[0], minute=end[1], second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def now_in_tz(tz_name: str) -> datetime:
    """Return current time as an aware datetime in the given IANA tz."""
    return datetime.now(ZoneInfo(tz_name))
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_time_utils.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leads_bot/time_utils.py tests/unit/test_time_utils.py
git commit -m "feat(time_utils): quiet-hours window helpers (overnight + tz-aware)"
```

---

## Task 3: BotState model + Alembic migration

**Files:**
- Modify: `src/leads_bot/db/models.py` (add `BotState`)
- Create: `src/leads_bot/db/migrations/versions/<auto>_iter2_botstate.py` (autogen via Alembic)
- Test: `tests/unit/test_db_models.py` (extend)

`BotState` is a single-row table holding mutable runtime flags that `/pause` /`/resume` and other commands need to persist across restarts: `paused`, `last_digest_at`, `last_health_ok_at`, `consecutive_health_fails`, `last_rate_limit_rotation_at`.

- [ ] **Step 1: Append failing test to `tests/unit/test_db_models.py`**

```python
async def test_botstate_singleton_row(session):
    from leads_bot.db.models import BotState
    s = BotState(id=1, paused=False, consecutive_health_fails=0)
    session.add(s)
    await session.commit()
    assert s.id == 1
    assert s.paused is False
    assert s.consecutive_health_fails == 0
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_db_models.py::test_botstate_singleton_row -v
```

Expected: `ImportError: cannot import name 'BotState'`.

- [ ] **Step 3: Add `BotState` to `src/leads_bot/db/models.py`**

Append at the end of the file:

```python
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
```

Also extend the `Response.status` valid values informally — add `pending_digest` to the docstring of `Response`:

```python
class Response(Base):
    """status: drafted | approved | sent | failed | skipped | pending_digest (Iter2)."""
    __tablename__ = "responses"
    # ... rest unchanged
```

- [ ] **Step 4: Generate migration**

```bash
cd "/Users/vitalinanikulina/Documents/Work/search for projects"
alembic revision --autogenerate -m "iter2 bot_state table"
```

Verify the generated file in `src/leads_bot/db/migrations/versions/` only contains `op.create_table('bot_state', ...)` and matching `op.drop_table` in `downgrade()`.

- [ ] **Step 5: Apply migration**

```bash
alembic upgrade head
```

- [ ] **Step 6: Bootstrap row 1 — add helper to session.py**

Append to `src/leads_bot/db/session.py`:

```python
async def ensure_bot_state(factory: async_sessionmaker[AsyncSession]) -> None:
    """Insert the singleton BotState(id=1) row if missing. Idempotent."""
    from sqlalchemy import select
    from leads_bot.db.models import BotState
    async with factory() as session:
        existing = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        if existing is None:
            session.add(BotState(id=1, paused=False, consecutive_health_fails=0))
            await session.commit()
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/unit/test_db_models.py -v
```

Expected: all PASS (4 tests now).

- [ ] **Step 8: Commit**

```bash
git add src/leads_bot/db/models.py src/leads_bot/db/session.py src/leads_bot/db/migrations/versions/ tests/unit/test_db_models.py
git commit -m "feat(db): add BotState singleton + Alembic migration for iter2"
```

---

## Task 4: Sources Service (CRUD + Telethon resolve)

**Files:**
- Create: `src/leads_bot/sources/__init__.py` (empty)
- Create: `src/leads_bot/sources/service.py`
- Test: `tests/unit/test_sources_service.py`

The service exposes pure-async functions that the `/sources` commands call. `resolve_link_via_telethon` accepts an injected client to keep tests offline.

- [ ] **Step 1: Write failing test**

`tests/unit/test_sources_service.py`:

```python
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Source
from leads_bot.sources.service import (
    list_sources, add_source_from_link, pause_source, resume_source,
    SourceAlreadyExists, SourceNotFound, InvalidRegion,
)


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    yield f
    await engine.dispose()


def _fake_client(tg_id: int, title: str, megagroup: bool = False):
    """Return a MagicMock that mimics Telethon get_entity returning a Channel."""
    entity = MagicMock()
    entity.id = abs(tg_id) - 1_000_000_000_000  # raw id
    entity.title = title
    entity.megagroup = megagroup
    entity.broadcast = not megagroup
    client = MagicMock()
    client.get_entity = AsyncMock(return_value=entity)
    # Telethon's utils.get_peer_id-style normalized id is what we store
    return client, entity


async def test_list_sources_empty(factory):
    rows = await list_sources(factory)
    assert rows == []


async def test_add_source_from_username(factory):
    client, _ = _fake_client(-1001234567890, "Design Jobs UA")
    src = await add_source_from_link(
        factory, client=client, link="@design_jobs_ua",
        region="ua", language="uk",
    )
    assert src.title == "Design Jobs UA"
    assert src.region == "ua"
    assert src.status == "active"
    client.get_entity.assert_awaited_once_with("design_jobs_ua")


async def test_add_source_from_t_me_link(factory):
    client, _ = _fake_client(-1001234567890, "X")
    await add_source_from_link(
        factory, client=client, link="https://t.me/design_jobs_ua",
        region="eu", language="en",
    )
    client.get_entity.assert_awaited_once_with("design_jobs_ua")


async def test_add_source_rejects_ru_region(factory):
    client, _ = _fake_client(-100, "X")
    with pytest.raises(InvalidRegion):
        await add_source_from_link(
            factory, client=client, link="@x", region="ru", language="ru",
        )


async def test_add_source_dedup(factory):
    client, _ = _fake_client(-1001234567890, "X")
    await add_source_from_link(factory, client=client, link="@x", region="ua", language="uk")
    with pytest.raises(SourceAlreadyExists):
        await add_source_from_link(factory, client=client, link="@x", region="ua", language="uk")


async def test_pause_and_resume(factory):
    client, _ = _fake_client(-1001234567890, "X")
    src = await add_source_from_link(factory, client=client, link="@x", region="ua", language="uk")
    await pause_source(factory, src.id)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == src.id))).scalar_one()
        assert row.status == "paused"
    await resume_source(factory, src.id)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == src.id))).scalar_one()
        assert row.status == "active"


async def test_pause_missing_raises(factory):
    with pytest.raises(SourceNotFound):
        await pause_source(factory, 999)
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_sources_service.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/leads_bot/sources/__init__.py`**

```python
```

(empty)

- [ ] **Step 4: Implement `src/leads_bot/sources/service.py`**

```python
"""CRUD service for `sources` table.

Telethon is used only to RESOLVE a link/username into a tg_id + title; all DB
work is plain SQLAlchemy and is fully testable with a mocked client.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon.utils import get_peer_id

from leads_bot.db.models import Source

ALLOWED_REGIONS = {"ua", "cis_ex_ru", "eu", "en_global"}
_LINK_RE = re.compile(r"^(?:https?://)?(?:t\.me/|telegram\.me/)?@?(?P<u>[A-Za-z0-9_]{4,})/?$")


class SourceAlreadyExists(Exception): pass
class SourceNotFound(Exception): pass
class InvalidRegion(Exception): pass
class InvalidLink(Exception): pass


@dataclass(frozen=True)
class SourceView:
    """Read-only DTO returned by `list_sources` (avoids leaking ORM rows)."""
    id: int
    tg_id: int
    title: str
    type: str
    language: str
    region: str
    status: str


def _parse_link(link: str) -> str:
    """Extract bare username from a t.me URL, @handle, or plain username."""
    link = link.strip()
    m = _LINK_RE.match(link)
    if not m:
        raise InvalidLink(f"Cannot parse link: {link!r}")
    return m.group("u")


async def list_sources(factory: async_sessionmaker) -> list[SourceView]:
    async with factory() as session:
        rows = (await session.execute(
            select(Source).order_by(Source.id)
        )).scalars().all()
        return [
            SourceView(
                id=r.id, tg_id=r.tg_id, title=r.title, type=r.type,
                language=r.language, region=r.region, status=r.status,
            )
            for r in rows
        ]


async def add_source_from_link(
    factory: async_sessionmaker,
    client,
    link: str,
    region: str,
    language: str,
) -> SourceView:
    """Resolve `link` via Telethon, then INSERT into sources.

    Raises InvalidRegion / InvalidLink / SourceAlreadyExists.
    """
    if region not in ALLOWED_REGIONS:
        raise InvalidRegion(f"region must be one of {sorted(ALLOWED_REGIONS)}, got {region!r}")

    username = _parse_link(link)
    entity = await client.get_entity(username)
    tg_id = get_peer_id(entity)  # canonical -100... form for channels
    title = getattr(entity, "title", None) or username
    type_ = "group" if getattr(entity, "megagroup", False) else "channel"

    async with factory() as session:
        existing = (await session.execute(
            select(Source).where(Source.tg_id == tg_id)
        )).scalar_one_or_none()
        if existing:
            raise SourceAlreadyExists(f"Source with tg_id={tg_id} already exists (id={existing.id})")
        row = Source(
            tg_id=tg_id, title=title, type=type_,
            language=language, region=region, status="active",
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        logger.info(f"Added source {row.id}: {title} ({tg_id})")
        return SourceView(
            id=row.id, tg_id=row.tg_id, title=row.title, type=row.type,
            language=row.language, region=row.region, status=row.status,
        )


async def pause_source(factory: async_sessionmaker, source_id: int) -> None:
    async with factory() as session:
        row = (await session.execute(
            select(Source).where(Source.id == source_id)
        )).scalar_one_or_none()
        if not row:
            raise SourceNotFound(f"No source with id={source_id}")
        row.status = "paused"
        await session.commit()


async def resume_source(factory: async_sessionmaker, source_id: int) -> None:
    async with factory() as session:
        row = (await session.execute(
            select(Source).where(Source.id == source_id)
        )).scalar_one_or_none()
        if not row:
            raise SourceNotFound(f"No source with id={source_id}")
        row.status = "active"
        await session.commit()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_sources_service.py -v
```

Expected: all PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add src/leads_bot/sources/ tests/unit/test_sources_service.py
git commit -m "feat(sources): CRUD service with Telethon link resolution"
```

---

## Task 5: Bot Commands (`/stats`, `/sources`, `/pause`, etc.)

**Files:**
- Create: `src/leads_bot/notifier/commands.py`
- Modify: `src/leads_bot/notifier/bot.py` (use `MemoryStorage`)
- Test: `tests/unit/test_commands.py`

Commands are routed by an aiogram `Router`. We restrict every command to the owner via a custom filter.

- [ ] **Step 1: Write failing test**

`tests/unit/test_commands.py`:

```python
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.commands import (
    cmd_stats, cmd_sources, cmd_sources_add, cmd_sources_pause,
    cmd_pause, cmd_resume, cmd_quiet, cmd_profile, cmd_templates,
    cmd_draft_retry,
)


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


def _msg(text: str):
    m = MagicMock()
    m.text = text
    m.answer = AsyncMock()
    return m


async def test_stats_with_empty_db(factory):
    msg = _msg("/stats")
    await cmd_stats(msg, factory)
    msg.answer.assert_awaited_once()
    out = msg.answer.call_args.args[0]
    assert "0" in out
    assert "лидов" in out.lower() or "leads" in out.lower()


async def test_stats_counts_today(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel", language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        # Today
        s.add(Lead(source_id=src.id, tg_message_id=1, raw_text="x", status="drafted"))
        s.add(Lead(source_id=src.id, tg_message_id=2, raw_text="x", status="filtered_out"))
        s.add(Lead(source_id=src.id, tg_message_id=3, raw_text="x", status="sent"))
        await s.commit()
        # Sent response today
        lead = (await s.execute(select(Lead).limit(1))).scalar_one()
        s.add(Response(lead_id=lead.id, draft_text="x", final_text="x",
                       status="sent", sent_at=datetime.utcnow()))
        await s.commit()

    msg = _msg("/stats")
    await cmd_stats(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "3" in out  # 3 leads
    assert "1" in out  # 1 sent


async def test_sources_lists_all(factory):
    async with factory() as s:
        s.add(Source(tg_id=-100, title="Design Jobs UA", type="channel",
                     language="uk", region="ua", status="active"))
        s.add(Source(tg_id=-101, title="UX Berlin", type="channel",
                     language="en", region="eu", status="paused"))
        await s.commit()

    msg = _msg("/sources")
    await cmd_sources(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "Design Jobs UA" in out
    assert "UX Berlin" in out
    assert "active" in out
    assert "paused" in out


async def test_sources_add_calls_service(factory):
    msg = _msg("/sources add @design_jobs_ua ua uk")
    fake_client = MagicMock()
    entity = MagicMock(); entity.title = "Design Jobs UA"; entity.megagroup = False
    fake_client.get_entity = AsyncMock(return_value=entity)

    await cmd_sources_add(msg, factory, fake_client)
    out = msg.answer.call_args.args[0]
    assert "Design Jobs UA" in out or "added" in out.lower()


async def test_sources_add_bad_args(factory):
    msg = _msg("/sources add only_one_arg")
    fake_client = MagicMock()
    await cmd_sources_add(msg, factory, fake_client)
    out = msg.answer.call_args.args[0]
    assert "usage" in out.lower() or "формат" in out.lower()


async def test_sources_pause_changes_status(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        sid = src.id

    msg = _msg(f"/sources pause {sid}")
    await cmd_sources_pause(msg, factory)
    async with factory() as s:
        row = (await s.execute(select(Source).where(Source.id == sid))).scalar_one()
        assert row.status == "paused"


async def test_pause_resume_toggle_botstate(factory):
    msg_p = _msg("/pause")
    await cmd_pause(msg_p, factory)
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.paused is True

    msg_r = _msg("/resume")
    await cmd_resume(msg_r, factory)
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.paused is False


async def test_quiet_command_updates_runtime_settings(factory):
    msg = _msg("/quiet 22:00-09:00")
    await cmd_quiet(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "22:00-09:00" in out
    # The setting is persisted into BotState.notes? No — we keep it in env.
    # cmd_quiet writes to BotState.last_rate_limit_rotation_at? No.
    # Per spec we just confirm it was parsed; runtime apply is via settings.quiet_hours
    # (overridden by the new bot_state column added below in Task 5b).


async def test_profile_shows_loaded_profile(tmp_path, monkeypatch, factory):
    import json
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({
        "name": "Vitalina", "portfolio_url": "https://x.design",
        "telegram": "@v", "min_rate_usd_per_hour": 60, "tone": "friendly",
        "payment_methods": ["wise"],
        "cases": [{"title": "C", "tags": ["landing"], "description": "d", "url": "u"}],
    }))
    msg = _msg("/profile")
    await cmd_profile(msg, factory, profile_path=p)
    out = msg.answer.call_args.args[0]
    assert "Vitalina" in out
    assert "60" in out


async def test_templates_stub_replies(factory):
    msg = _msg("/templates")
    await cmd_templates(msg, factory)
    out = msg.answer.call_args.args[0]
    assert "iter" in out.lower() or "итер" in out.lower()


async def test_draft_retry_calls_pipeline(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        lead = Lead(source_id=src.id, tg_message_id=1, raw_text="hi",
                    project_type="landing", language="en",
                    relevance_score=80, status="drafted")
        s.add(lead); await s.commit()
        lid = lead.id

    msg = _msg(f"/draft {lid} retry")
    pipeline = MagicMock()
    pipeline.regenerate_draft = AsyncMock()
    await cmd_draft_retry(msg, factory, pipeline)
    pipeline.regenerate_draft.assert_awaited_once()
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_commands.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Add `quiet_hours_override` column to `BotState` to support `/quiet`**

Append to `src/leads_bot/db/models.py` `BotState` class:

```python
    quiet_hours_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

Generate a follow-up migration:

```bash
alembic revision --autogenerate -m "iter2 botstate quiet_hours_override"
alembic upgrade head
```

- [ ] **Step 4: Implement `src/leads_bot/notifier/commands.py`**

```python
"""Owner-only command handlers. See spec §9.2.

All commands receive the message object first, then dependencies (factory,
client, pipeline, profile_path) injected by main.py via partials.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import BotState, Lead, Response, Source
from leads_bot.drafter.profile import load_profile
from leads_bot.sources.service import (
    InvalidLink, InvalidRegion, SourceAlreadyExists, SourceNotFound,
    add_source_from_link, list_sources, pause_source, resume_source,
)


_QUIET_RE = re.compile(r"^\d{1,2}:\d{2}-\d{1,2}:\d{2}$")


# ──────────────────────────── /stats ────────────────────────────

async def cmd_stats(message, factory: async_sessionmaker) -> None:
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    async with factory() as session:
        leads_today = (await session.execute(
            select(func.count(Lead.id)).where(Lead.posted_at >= today)
        )).scalar_one()
        sent_today = (await session.execute(
            select(func.count(Response.id)).where(
                Response.status == "sent", Response.sent_at >= today,
            )
        )).scalar_one()
        replied_today = (await session.execute(
            select(func.count(Response.id)).where(
                Response.client_replied.is_(True), Response.sent_at >= today,
            )
        )).scalar_one()
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        paused = bs.paused if bs else False

    text = (
        f"📊 За сегодня\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Лидов получено: {leads_today}\n"
        f"Отправлено: {sent_today}\n"
        f"Ответов клиентов: {replied_today}\n"
        f"Бот: {'⏸ на паузе' if paused else '▶ работает'}"
    )
    await message.answer(text)


# ──────────────────────────── /sources ────────────────────────────

async def cmd_sources(message, factory: async_sessionmaker) -> None:
    rows = await list_sources(factory)
    if not rows:
        await message.answer("Нет источников. Добавь: /sources add @username <region> <lang>")
        return
    lines = ["📡 Источники:"]
    for r in rows:
        marker = "▶" if r.status == "active" else "⏸"
        lines.append(f"{marker} #{r.id} · {r.title} · {r.region}/{r.language} · {r.status}")
    await message.answer("\n".join(lines))


async def cmd_sources_add(message, factory: async_sessionmaker, client) -> None:
    """Format: /sources add <link> <region> <language>"""
    parts = (message.text or "").split()
    # Accept "/sources add @x ua uk" → parts = ["/sources", "add", "@x", "ua", "uk"]
    if len(parts) != 5 or parts[1] != "add":
        await message.answer(
            "Usage: /sources add <link> <region> <language>\n"
            "Example: /sources add @design_jobs_ua ua uk\n"
            "Allowed regions: ua | cis_ex_ru | eu | en_global"
        )
        return
    _, _, link, region, language = parts
    try:
        src = await add_source_from_link(
            factory, client=client, link=link, region=region, language=language,
        )
    except InvalidRegion as e:
        await message.answer(f"❌ {e}")
        return
    except InvalidLink as e:
        await message.answer(f"❌ {e}")
        return
    except SourceAlreadyExists as e:
        await message.answer(f"⚠️ {e}")
        return
    except Exception as e:
        logger.exception(f"Failed to resolve link {link}: {e}")
        await message.answer(f"❌ Не удалось добавить: {e}")
        return
    await message.answer(f"✅ Добавлен #{src.id}: {src.title} ({src.region}/{src.language})")


async def cmd_sources_pause(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] != "pause" or not parts[2].isdigit():
        await message.answer("Usage: /sources pause <id>")
        return
    try:
        await pause_source(factory, int(parts[2]))
    except SourceNotFound as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(f"⏸ Источник {parts[2]} на паузе")


async def cmd_sources_resume(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or parts[1] != "resume" or not parts[2].isdigit():
        await message.answer("Usage: /sources resume <id>")
        return
    try:
        await resume_source(factory, int(parts[2]))
    except SourceNotFound as e:
        await message.answer(f"❌ {e}")
        return
    await message.answer(f"▶ Источник {parts[2]} запущен")


# ──────────────────────────── /pause /resume (global) ────────────────────────────

async def cmd_pause(message, factory: async_sessionmaker) -> None:
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.paused = True
        await session.commit()
    await message.answer("⏸ Бот на паузе. Новые лиды не будут обрабатываться. /resume чтобы вернуть.")


async def cmd_resume(message, factory: async_sessionmaker) -> None:
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.paused = False
        await session.commit()
    await message.answer("▶ Бот снова работает.")


# ──────────────────────────── /quiet ────────────────────────────

async def cmd_quiet(message, factory: async_sessionmaker) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not _QUIET_RE.match(parts[1]):
        await message.answer("Usage: /quiet HH:MM-HH:MM\nExample: /quiet 22:00-09:00")
        return
    spec = parts[1]
    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.quiet_hours_override = spec
        await session.commit()
    await message.answer(f"🔕 Quiet hours: {spec}")


# ──────────────────────────── /profile ────────────────────────────

async def cmd_profile(message, factory: async_sessionmaker, profile_path: Path) -> None:
    if not profile_path.exists():
        await message.answer("❌ profile.json missing — see data/profile.example.json")
        return
    p = load_profile(profile_path)
    case_lines = "\n".join(f"  • {c.title} ({', '.join(c.tags)})" for c in p.cases[:5])
    text = (
        f"👤 Profile\n"
        f"━━━━━━━━━━━━━\n"
        f"Name: {p.name}\n"
        f"Portfolio: {p.portfolio_url}\n"
        f"Telegram: {p.telegram}\n"
        f"Rate: ${p.min_rate_usd_per_hour}/hr\n"
        f"Tone: {p.tone}\n"
        f"Payment: {', '.join(p.payment_methods)}\n"
        f"Cases ({len(p.cases)}):\n{case_lines}"
    )
    await message.answer(text)


# ──────────────────────────── /templates (stub) ────────────────────────────

async def cmd_templates(message, factory: async_sessionmaker) -> None:
    await message.answer(
        "📝 Шаблоны появятся в Iter 4 (A/B testing).\n"
        "Сейчас используется один Sonnet-промпт из drafter/prompts.py."
    )


# ──────────────────────────── /draft <id> retry ────────────────────────────

async def cmd_draft_retry(message, factory: async_sessionmaker, pipeline) -> None:
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[1].isdigit() or parts[2] != "retry":
        await message.answer("Usage: /draft <lead_id> retry")
        return
    lead_id = int(parts[1])
    try:
        await pipeline.regenerate_draft(lead_id)
    except Exception as e:
        await message.answer(f"❌ Failed to regenerate: {e}")
        return
    await message.answer(f"🔄 Регенерирую драфт для лида #{lead_id}...")
```

- [ ] **Step 5: Add `Pipeline.regenerate_draft` (referenced by `/draft retry`)**

Append to `src/leads_bot/pipeline.py`:

```python
    async def regenerate_draft(self, lead_id: int) -> None:
        """Regenerate the draft for an existing lead and resend the card to owner."""
        from sqlalchemy import select
        from leads_bot.db.session import get_session_factory
        from leads_bot.notifier.bot import send_lead_card
        from leads_bot.notifier.card import build_keyboard, format_lead_card

        factory = get_session_factory()
        async with factory() as session:
            lead = (await session.execute(
                select(Lead).where(Lead.id == lead_id)
            )).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} not found")

            await session.refresh(lead, attribute_names=["source"])
            try:
                draft_text = await self._drafter.draft(
                    lead_text=lead.raw_text,
                    project_type=lead.project_type or "other",
                    client_language=lead.language or "en",
                )
            except Exception as e:
                logger.exception(f"Drafter retry failed for lead {lead_id}: {e}")
                raise

            response = Response(
                lead_id=lead.id, draft_text=draft_text,
                status="drafted",
                sent_to="dm" if self._wants_dm(lead.raw_text) else "chat",
            )
            session.add(response)
            await session.commit()

            card = format_lead_card(lead, response)
            kb = build_keyboard(response_id=response.id, source_id=lead.source.id)
            await send_lead_card(self._bot, self._owner, card, kb)
```

- [ ] **Step 6: Update `src/leads_bot/notifier/bot.py` to use FSM-capable Dispatcher**

Replace `build_dispatcher`:

```python
"""aiogram Bot/Dispatcher setup. See spec §6.4."""
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from leads_bot.config import get_settings


def build_bot() -> Bot:
    settings = get_settings()
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


def build_dispatcher() -> Dispatcher:
    """Dispatcher with in-memory FSM storage (single-user bot, no need for Redis)."""
    return Dispatcher(storage=MemoryStorage())


async def send_lead_card(bot: Bot, owner_tg_id: int, text: str, keyboard) -> int:
    msg = await bot.send_message(
        owner_tg_id, text, reply_markup=keyboard, disable_web_page_preview=True,
    )
    return msg.message_id
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/unit/test_commands.py -v
```

Expected: all PASS (10 tests).

- [ ] **Step 8: Commit**

```bash
git add src/leads_bot/notifier/commands.py src/leads_bot/notifier/bot.py src/leads_bot/pipeline.py src/leads_bot/db/models.py src/leads_bot/db/migrations/versions/ tests/unit/test_commands.py
git commit -m "feat(notifier): full command surface (stats/sources/pause/resume/quiet/profile/templates/draft retry)"
```

---

## Task 6: Edit Response FSM Flow

**Files:**
- Create: `src/leads_bot/notifier/states.py`
- Create: `src/leads_bot/notifier/edit_flow.py`
- Modify: `src/leads_bot/notifier/handlers.py` (replace edit stub)
- Test: `tests/unit/test_edit_flow.py`

The flow:
1. Owner taps ✏️ on a lead card → callback `edit:<resp_id>` arrives.
2. Bot enters `EditStates.awaiting_text` for that user, stores `response_id` in FSM context, asks: "Send the new version of the reply (or /cancel)."
3. Owner sends a text message → handler reads from FSM, builds confirm card with two inline buttons: `[✅ Send this version]` (`confirm_edit:<resp_id>`) and `[↩ Back to draft]` (`cancel_edit:<resp_id>`).
4. On confirm: write `final_text`, status=`approved`, then call `sender.send`.
5. On cancel: revert FSM and answer "Returned to draft. Reply card is still above."

- [ ] **Step 1: Write failing test**

`tests/unit/test_edit_flow.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.edit_flow import (
    start_edit, receive_edit_text, confirm_edit, cancel_edit,
)
from leads_bot.notifier.states import EditStates


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


def _state(user_id=1, chat_id=1):
    storage = MemoryStorage()
    key = StorageKey(bot_id=42, user_id=user_id, chat_id=chat_id)
    return FSMContext(storage=storage, key=key)


async def _make_response(factory):
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        lead = Lead(source_id=src.id, tg_message_id=1,
                    raw_text="hi", status="drafted")
        s.add(lead); await s.commit()
        resp = Response(lead_id=lead.id, draft_text="original draft",
                        status="drafted", sent_to="dm")
        s.add(resp); await s.commit()
        return resp.id


async def test_start_edit_sets_state_and_prompts(factory):
    resp_id = await _make_response(factory)
    state = _state()
    callback = MagicMock()
    callback.data = f"edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    await start_edit(callback, state)

    cur = await state.get_state()
    assert cur == EditStates.awaiting_text.state
    data = await state.get_data()
    assert data["response_id"] == resp_id
    callback.message.answer.assert_awaited_once()
    msg = callback.message.answer.call_args.args[0]
    assert "новую версию" in msg.lower() or "new version" in msg.lower()


async def test_receive_edit_text_shows_confirm(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.awaiting_text)
    await state.update_data(response_id=resp_id)

    msg = MagicMock()
    msg.text = "edited reply with more detail"
    msg.answer = AsyncMock()

    await receive_edit_text(msg, state)

    cur = await state.get_state()
    assert cur == EditStates.confirming.state
    data = await state.get_data()
    assert data["edited_text"] == "edited reply with more detail"
    msg.answer.assert_awaited_once()
    call = msg.answer.call_args
    keyboard = call.kwargs["reply_markup"]
    flat = [b for row in keyboard.inline_keyboard for b in row]
    cbs = [b.callback_data for b in flat]
    assert any(c == f"confirm_edit:{resp_id}" for c in cbs)
    assert any(c == f"cancel_edit:{resp_id}" for c in cbs)


async def test_confirm_edit_persists_and_sends(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.confirming)
    await state.update_data(response_id=resp_id, edited_text="final edited text")

    callback = MagicMock()
    callback.data = f"confirm_edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()

    sender = MagicMock()
    sender.send = AsyncMock()

    await confirm_edit(callback, state, factory, sender)

    async with factory() as s:
        r = (await s.execute(select(Response).where(Response.id == resp_id))).scalar_one()
        assert r.final_text == "final edited text"
        assert r.status == "approved"

    sender.send.assert_awaited_once()
    cur = await state.get_state()
    assert cur is None  # cleared


async def test_cancel_edit_clears_state_no_send(factory):
    resp_id = await _make_response(factory)
    state = _state()
    await state.set_state(EditStates.confirming)
    await state.update_data(response_id=resp_id, edited_text="abandoned")

    callback = MagicMock()
    callback.data = f"cancel_edit:{resp_id}"
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.delete = AsyncMock()

    sender = MagicMock()
    sender.send = AsyncMock()

    await cancel_edit(callback, state, factory, sender)

    sender.send.assert_not_awaited()
    cur = await state.get_state()
    assert cur is None
    async with factory() as s:
        r = (await s.execute(select(Response).where(Response.id == resp_id))).scalar_one()
        assert r.final_text is None
        assert r.status == "drafted"


async def test_receive_edit_text_ignored_when_no_state(factory):
    resp_id = await _make_response(factory)
    state = _state()
    msg = MagicMock(); msg.text = "hi"; msg.answer = AsyncMock()
    # No state set -> handler should noop (this is enforced by aiogram's filter
    # at the dispatcher level; here we simulate by just not setting state)
    cur = await state.get_state()
    assert cur is None
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_edit_flow.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/leads_bot/notifier/states.py`**

```python
"""FSM states for owner interactions. See spec §6.4 (edit flow)."""
from aiogram.fsm.state import State, StatesGroup


class EditStates(StatesGroup):
    awaiting_text = State()    # bot asked owner for new text
    confirming = State()       # bot showed confirm card
```

- [ ] **Step 4: Implement `src/leads_bot/notifier/edit_flow.py`**

```python
"""Edit-response state machine. See spec §6.4 + iter2 brief.

Flow:
  ✏️ tap   → start_edit       (sets EditStates.awaiting_text)
  text msg → receive_edit_text (sets EditStates.confirming, shows preview)
  ✅ tap   → confirm_edit      (writes final_text, calls sender)
  ↩ tap   → cancel_edit        (clears state)
"""
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.db.models import Response
from leads_bot.notifier.states import EditStates


def _confirm_keyboard(response_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Send this version",
                callback_data=f"confirm_edit:{response_id}",
            ),
            InlineKeyboardButton(
                text="↩ Back to draft",
                callback_data=f"cancel_edit:{response_id}",
            ),
        ],
    ])


async def start_edit(callback, state: FSMContext) -> None:
    """Triggered by callback 'edit:<resp_id>'."""
    try:
        _, rid_s = (callback.data or "").split(":", 1)
        response_id = int(rid_s)
    except ValueError:
        await callback.answer("Bad callback")
        return

    await state.set_state(EditStates.awaiting_text)
    await state.update_data(response_id=response_id)
    await callback.answer()
    await callback.message.answer(
        "✏️ Пришли новую версию ответа одним сообщением.\n"
        "Чтобы отменить — /cancel"
    )


async def receive_edit_text(message, state: FSMContext) -> None:
    """Triggered when owner sends a text while EditStates.awaiting_text."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Пустое сообщение. Пришли текст или /cancel.")
        return
    if text == "/cancel":
        await state.clear()
        await message.answer("Отменено. Карточка с драфтом всё ещё выше.")
        return

    await state.update_data(edited_text=text)
    await state.set_state(EditStates.confirming)
    data = await state.get_data()
    response_id = int(data["response_id"])

    preview = (
        f"▎НОВАЯ ВЕРСИЯ\n{text}\n\n"
        "Отправить эту версию?"
    )
    await message.answer(preview, reply_markup=_confirm_keyboard(response_id))


async def confirm_edit(
    callback, state: FSMContext,
    factory: async_sessionmaker, sender,
) -> None:
    """Triggered by callback 'confirm_edit:<resp_id>'."""
    data = await state.get_data()
    edited_text = data.get("edited_text")
    response_id = data.get("response_id")
    if not edited_text or not response_id:
        await callback.answer("Состояние утеряно. Нажми ✏️ заново.", show_alert=True)
        await state.clear()
        return

    async with factory() as session:
        resp = (await session.execute(
            select(Response).where(Response.id == int(response_id))
        )).scalar_one_or_none()
        if resp is None:
            await callback.answer("Response not found", show_alert=True)
            await state.clear()
            return
        resp.final_text = edited_text
        resp.status = "approved"
        await session.commit()

        try:
            await sender.send(session, int(response_id))
        except Exception as e:
            logger.exception(f"Sender failed for edited response {response_id}: {e}")

    await callback.answer("✅ Отправлено")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()


async def cancel_edit(
    callback, state: FSMContext,
    factory: async_sessionmaker, sender,
) -> None:
    """Triggered by callback 'cancel_edit:<resp_id>'.

    `factory` and `sender` are accepted for parity with confirm_edit (so the
    dispatcher can register both with the same signature).
    """
    await callback.answer("↩ Возврат к драфту")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await state.clear()
```

- [ ] **Step 5: Update `src/leads_bot/notifier/handlers.py` to remove edit stub and route to FSM**

Replace the `elif action == "edit":` branch with a no-op that's overridden by main.py registering the FSM handler at higher priority:

```python
    elif action == "edit":
        # Iter 2: this branch is unreachable — the FSM router (registered
        # earlier in main.py) catches `edit:*` before this fallback handler.
        # Kept for safety as a no-op.
        await callback.answer()
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_edit_flow.py tests/unit/test_handlers.py -v
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/leads_bot/notifier/states.py src/leads_bot/notifier/edit_flow.py src/leads_bot/notifier/handlers.py tests/unit/test_edit_flow.py
git commit -m "feat(notifier): full edit-response FSM flow (✏️ → text → confirm/cancel)"
```

---

## Task 7: Quiet Hours + Morning Digest

**Files:**
- Create: `src/leads_bot/notifier/digest.py`
- Modify: `src/leads_bot/pipeline.py` (skip card during quiet, mark `pending_digest`)
- Test: `tests/unit/test_digest.py`

- [ ] **Step 1: Write failing test for digest**

`tests/unit/test_digest.py`:

```python
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.digest import (
    build_digest_text, collect_pending_digest_responses, run_morning_digest,
)


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


async def _seed(factory, n: int) -> list[int]:
    async with factory() as s:
        src = Source(tg_id=-100, title="x", type="channel",
                     language="ru", region="ua", status="active")
        s.add(src); await s.commit()
        ids = []
        for i in range(n):
            lead = Lead(source_id=src.id, tg_message_id=i+1, raw_text="x",
                        project_type="landing", budget_usd=500 + i*100,
                        relevance_score=70 + i, status="drafted")
            s.add(lead); await s.commit()
            resp = Response(lead_id=lead.id, draft_text="d", status="pending_digest",
                            sent_to="dm")
            s.add(resp); await s.commit()
            ids.append(resp.id)
        return ids


def test_build_digest_text_with_three_leads():
    rows = [
        MagicMock(id=145, lead=MagicMock(relevance_score=92, project_type="ui_ux", budget_usd=3000)),
        MagicMock(id=144, lead=MagicMock(relevance_score=78, project_type="landing", budget_usd=500)),
        MagicMock(id=143, lead=MagicMock(relevance_score=65, project_type="app", budget_usd=1200)),
    ]
    text = build_digest_text(rows)
    assert "3 лид" in text
    assert "#145" in text
    assert "92" in text
    assert "$3000" in text or "3000" in text


def test_build_digest_text_empty():
    text = build_digest_text([])
    assert "0" in text or "Нет" in text or "ничего" in text.lower()


async def test_collect_pending_returns_only_pending_digest(factory):
    ids = await _seed(factory, 3)
    rows = await collect_pending_digest_responses(factory)
    assert len(rows) == 3
    assert {r.id for r in rows} == set(ids)


async def test_run_morning_digest_sends_and_promotes_to_drafted(factory):
    ids = await _seed(factory, 2)
    bot = MagicMock(); bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    await run_morning_digest(factory, bot=bot, owner_tg_id=999)

    bot.send_message.assert_awaited()
    # Each pending_digest response should be promoted back to "drafted" so the
    # owner can interact with the per-lead card flow if they want details.
    async with factory() as s:
        rows = (await s.execute(select(Response).where(Response.id.in_(ids)))).scalars().all()
        for r in rows:
            assert r.status == "drafted"
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.last_digest_at is not None


async def test_run_morning_digest_no_op_when_empty(factory):
    bot = MagicMock(); bot.send_message = AsyncMock()
    await run_morning_digest(factory, bot=bot, owner_tg_id=999)
    # When there's nothing accumulated, we still post a single "ничего за ночь"
    # so the owner knows the bot is alive.
    bot.send_message.assert_awaited_once()
```

- [ ] **Step 2: Write failing test for quiet-hours pipeline behavior**

`tests/integration/test_quiet_hours_flow.py`:

```python
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, Lead, Response, Source
from leads_bot.db.session import ensure_bot_state
from leads_bot.notifier.digest import run_morning_digest
from leads_bot.pipeline import Pipeline


@pytest.fixture
async def session_and_factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
                 ("QUIET_HOURS", "23:00-08:00"), ("QUIET_HOURS_ENABLED", "true"),
                 ("TIMEZONE", "UTC")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    async with f() as s:
        yield s, f
    await engine.dispose()


async def test_during_quiet_no_card_response_marked_pending(session_and_factory):
    session, factory = session_and_factory
    src = Source(tg_id=-100, title="x", type="channel",
                 language="ru", region="ua", status="active")
    session.add(src); await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1,
                raw_text="Looking for designer", status="new")
    session.add(lead); await session.commit()

    analyzer = MagicMock()
    async def _analyze(s, l, ct, cl):
        l.is_lead = True; l.project_type = "landing"; l.budget_usd = 1000
        l.language = "en"; l.client_country = "eu"; l.urgency = "med"
        l.relevance_score = 88; l.reasoning = "ok"; l.status = "drafted"
        await s.commit(); return l
    analyzer.analyze_and_persist = AsyncMock(side_effect=_analyze)
    drafter = MagicMock(); drafter.draft = AsyncMock(return_value="hi")
    bot = MagicMock(); bot.send_message = AsyncMock()

    pipeline = Pipeline(analyzer=analyzer, drafter=drafter, bot=bot,
                        owner_tg_id=999, factory=factory)

    # Force "now" inside quiet window
    fixed_now = datetime(2026, 5, 17, 2, 0)  # 02:00 UTC
    with patch("leads_bot.pipeline._utcnow_aware", return_value=fixed_now.replace(tzinfo=__import__("zoneinfo").ZoneInfo("UTC"))):
        await pipeline.process_new_lead(session, lead, src)

    # Card should NOT be sent during quiet
    bot.send_message.assert_not_awaited()
    resp = (await session.execute(select(Response).where(Response.lead_id == lead.id))).scalar_one()
    assert resp.status == "pending_digest"


async def test_morning_digest_after_quiet_releases_pending(session_and_factory):
    session, factory = session_and_factory
    src = Source(tg_id=-100, title="x", type="channel",
                 language="ru", region="ua", status="active")
    session.add(src); await session.commit()
    lead = Lead(source_id=src.id, tg_message_id=1, raw_text="x",
                project_type="landing", budget_usd=1500, relevance_score=88,
                status="drafted")
    session.add(lead); await session.commit()
    resp = Response(lead_id=lead.id, draft_text="d", status="pending_digest", sent_to="dm")
    session.add(resp); await session.commit()

    bot = MagicMock(); bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    await run_morning_digest(factory, bot=bot, owner_tg_id=999)

    await session.refresh(resp)
    assert resp.status == "drafted"
    bot.send_message.assert_awaited()
```

- [ ] **Step 3: Run, expect fail**

```bash
pytest tests/unit/test_digest.py tests/integration/test_quiet_hours_flow.py -v
```

Expected: `ModuleNotFoundError` on digest; integration test fails because `Pipeline.__init__` doesn't accept `factory` yet.

- [ ] **Step 4: Implement `src/leads_bot/notifier/digest.py`**

```python
"""Morning digest builder + sender. See spec §9.3."""
from datetime import datetime
from typing import Iterable

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import selectinload

from leads_bot.db.models import BotState, Response


TG_MSG_LIMIT = 4096
MAX_LINES = 30


def build_digest_text(rows) -> str:
    n = len(rows)
    if n == 0:
        return "🌅 Доброе утро. За ночь ничего нового."

    lines = [f"🌅 Доброе утро. За ночь: {n} лид{'' if n == 1 else 'ов'}"]
    sorted_rows = sorted(
        rows, key=lambda r: (r.lead.relevance_score or 0), reverse=True,
    )
    for r in sorted_rows[:MAX_LINES]:
        score = r.lead.relevance_score or 0
        ptype = r.lead.project_type or "?"
        budget = f"${r.lead.budget_usd}" if r.lead.budget_usd else "?"
        lines.append(f"• #{r.id} score {score} — {ptype}, {budget}")
    if n > MAX_LINES:
        lines.append(f"…и ещё {n - MAX_LINES}. Открой /stats для деталей.")
    text = "\n".join(lines)
    return text[:TG_MSG_LIMIT]


async def collect_pending_digest_responses(factory: async_sessionmaker) -> list[Response]:
    async with factory() as session:
        rows = (await session.execute(
            select(Response)
            .options(selectinload(Response.lead))
            .where(Response.status == "pending_digest")
            .order_by(Response.id)
        )).scalars().all()
        # Detach so caller can iterate without session
        for r in rows:
            session.expunge(r)
        return list(rows)


async def run_morning_digest(
    factory: async_sessionmaker, bot, owner_tg_id: int,
) -> None:
    """Send digest to owner; promote each pending_digest → drafted."""
    rows = await collect_pending_digest_responses(factory)
    text = build_digest_text(rows)
    try:
        await bot.send_message(owner_tg_id, text, disable_web_page_preview=True)
    except Exception as e:
        logger.exception(f"Digest send failed: {e}")
        return

    if rows:
        async with factory() as session:
            ids = [r.id for r in rows]
            db_rows = (await session.execute(
                select(Response).where(Response.id.in_(ids))
            )).scalars().all()
            for r in db_rows:
                r.status = "drafted"
            await session.commit()

    async with factory() as session:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one()
        bs.last_digest_at = datetime.utcnow()
        await session.commit()

    logger.info(f"Digest sent ({len(rows)} leads)")
```

- [ ] **Step 5: Update `src/leads_bot/pipeline.py` — quiet-hours check**

Replace the file with:

```python
"""Wires listener → analyzer → drafter → notifier. See spec §7."""
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.models import BotState, Lead, Response, Source
from leads_bot.drafter.drafter import Drafter
from leads_bot.notifier.bot import send_lead_card
from leads_bot.notifier.card import build_keyboard, format_lead_card
from leads_bot.time_utils import is_in_quiet_window, parse_window


def _utcnow_aware() -> datetime:
    """Wrappable for tests."""
    return datetime.now(ZoneInfo("UTC"))


class Pipeline:
    def __init__(
        self, analyzer: Analyzer, drafter: Drafter, bot,
        owner_tg_id: int, factory: async_sessionmaker | None = None,
    ):
        self._analyzer = analyzer
        self._drafter = drafter
        self._bot = bot
        self._owner = owner_tg_id
        self._factory = factory
        self._settings = get_settings()

    async def _is_paused(self, session: AsyncSession) -> bool:
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        return bool(bs and bs.paused)

    async def _quiet_window(self, session: AsyncSession) -> tuple[tuple[int, int], tuple[int, int]] | None:
        if not self._settings.quiet_hours_enabled:
            return None
        bs = (await session.execute(
            select(BotState).where(BotState.id == 1)
        )).scalar_one_or_none()
        spec = (bs.quiet_hours_override if bs and bs.quiet_hours_override
                else self._settings.quiet_hours)
        return parse_window(spec)

    async def process_new_lead(
        self, session: AsyncSession, lead: Lead, source: Source,
    ) -> None:
        # Global pause check
        if await self._is_paused(session):
            logger.info(f"Bot paused — ignoring lead {lead.id}")
            return

        analyzed = await self._analyzer.analyze_and_persist(
            session, lead, source.title, source.language,
        )
        if analyzed.status == "filtered_out":
            logger.info(f"Lead {lead.id} filtered out: {analyzed.reasoning}")
            return
        if analyzed.status == "analysis_failed":
            logger.warning(f"Lead {lead.id} analysis failed — manual retry needed")
            return

        sent_to = "dm" if self._wants_dm(analyzed.raw_text) else "chat"

        try:
            draft_text = await self._drafter.draft(
                lead_text=analyzed.raw_text,
                project_type=analyzed.project_type or "other",
                client_language=analyzed.language or "en",
            )
        except Exception as e:
            logger.exception(f"Drafter failed for lead {lead.id}: {e}")
            analyzed.status = "analysis_failed"
            await session.commit()
            return

        # Quiet-hours decision
        quiet = await self._quiet_window(session)
        in_quiet = quiet and is_in_quiet_window(_utcnow_aware(), *quiet)

        response = Response(
            lead_id=lead.id, draft_text=draft_text,
            status="pending_digest" if in_quiet else "drafted",
            sent_to=sent_to,
        )
        session.add(response)
        await session.commit()

        if in_quiet:
            logger.info(f"Lead {lead.id} queued for morning digest (quiet hours)")
            return

        await session.refresh(lead, attribute_names=["source"])
        card = format_lead_card(lead, response)
        kb = build_keyboard(response_id=response.id, source_id=source.id)
        await send_lead_card(self._bot, self._owner, card, kb)

    async def regenerate_draft(self, lead_id: int) -> None:
        """Regenerate the draft for an existing lead and resend the card to owner."""
        from leads_bot.db.session import get_session_factory
        factory = self._factory or get_session_factory()
        async with factory() as session:
            lead = (await session.execute(
                select(Lead).where(Lead.id == lead_id)
            )).scalar_one_or_none()
            if lead is None:
                raise ValueError(f"Lead {lead_id} not found")
            await session.refresh(lead, attribute_names=["source"])
            try:
                draft_text = await self._drafter.draft(
                    lead_text=lead.raw_text,
                    project_type=lead.project_type or "other",
                    client_language=lead.language or "en",
                )
            except Exception as e:
                logger.exception(f"Drafter retry failed for lead {lead_id}: {e}")
                raise
            response = Response(
                lead_id=lead.id, draft_text=draft_text,
                status="drafted",
                sent_to="dm" if self._wants_dm(lead.raw_text) else "chat",
            )
            session.add(response)
            await session.commit()
            card = format_lead_card(lead, response)
            kb = build_keyboard(response_id=response.id, source_id=lead.source.id)
            await send_lead_card(self._bot, self._owner, card, kb)

    @staticmethod
    def _wants_dm(text: str) -> bool:
        lower = text.lower()
        return any(s in lower for s in [
            "в лс", "пишите в", "write in dm", "dm me", "dms open", "in dm",
        ])
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_digest.py tests/integration/test_quiet_hours_flow.py tests/integration/test_pipeline.py -v
```

Expected: all PASS. (Existing `test_pipeline.py` may need a small fix — it constructs `Pipeline(...)` without `factory=`; the new param is optional so it should still pass.)

- [ ] **Step 7: Commit**

```bash
git add src/leads_bot/notifier/digest.py src/leads_bot/pipeline.py tests/unit/test_digest.py tests/integration/test_quiet_hours_flow.py
git commit -m "feat(quiet+digest): pipeline queues to pending_digest during quiet, morning digest releases them"
```

---

## Task 8: Health Monitor

**Files:**
- Create: `src/leads_bot/health/__init__.py` (empty)
- Create: `src/leads_bot/health/monitor.py`
- Test: `tests/unit/test_health_monitor.py`

The monitor calls `client.get_me()` periodically. On 3 consecutive failures it pings the owner via the aiogram bot and resets the counter (to avoid spam).

- [ ] **Step 1: Write failing test**

`tests/unit/test_health_monitor.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, BotState
from leads_bot.db.session import ensure_bot_state
from leads_bot.health.monitor import HealthMonitor


@pytest.fixture
async def factory(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "999"), ("ANTHROPIC_API_KEY", "x"),
                 ("HEALTHCHECK_FAILURE_THRESHOLD", "3")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    await ensure_bot_state(f)
    yield f
    await engine.dispose()


async def test_success_resets_counter(factory):
    user_client = MagicMock(); user_client.get_me = AsyncMock(return_value=MagicMock(id=1))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    # Pretend we already have 2 fails
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        bs.consecutive_health_fails = 2
        await s.commit()

    await monitor.check_once()

    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 0
        assert bs.last_health_ok_at is not None
    bot.send_message.assert_not_awaited()


async def test_failure_increments_counter(factory):
    user_client = MagicMock(); user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    await monitor.check_once()
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 1
    bot.send_message.assert_not_awaited()


async def test_threshold_reached_alerts_owner_and_resets(factory):
    user_client = MagicMock(); user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock(); bot.send_message = AsyncMock()
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)

    for _ in range(3):
        await monitor.check_once()

    bot.send_message.assert_awaited_once()
    msg = bot.send_message.call_args.args[1]
    assert "health" in msg.lower() or "связь" in msg.lower()
    async with factory() as s:
        bs = (await s.execute(select(BotState).where(BotState.id == 1))).scalar_one()
        assert bs.consecutive_health_fails == 0  # reset after alert


async def test_alert_send_failure_does_not_crash(factory):
    user_client = MagicMock(); user_client.get_me = AsyncMock(side_effect=ConnectionError("boom"))
    bot = MagicMock(); bot.send_message = AsyncMock(side_effect=RuntimeError("bot down too"))
    monitor = HealthMonitor(user_client, bot, owner_tg_id=999, factory=factory)
    for _ in range(3):
        await monitor.check_once()  # must not raise
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_health_monitor.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/leads_bot/health/__init__.py`** (empty)

- [ ] **Step 4: Implement `src/leads_bot/health/monitor.py`**

```python
"""Periodic GetMe health-check with consecutive-failure alerting. See spec §11.2."""
from __future__ import annotations

import asyncio
from datetime import datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.config import get_settings
from leads_bot.db.models import BotState


class HealthMonitor:
    def __init__(self, user_client, bot, owner_tg_id: int,
                 factory: async_sessionmaker):
        self._client = user_client
        self._bot = bot
        self._owner = owner_tg_id
        self._factory = factory
        self._settings = get_settings()

    async def check_once(self) -> bool:
        """Run a single GetMe ping, update DB, return True if ok."""
        ok = False
        try:
            await self._client.get_me()
            ok = True
        except Exception as e:
            logger.warning(f"Healthcheck failed: {type(e).__name__}: {e}")

        async with self._factory() as session:
            bs = (await session.execute(
                select(BotState).where(BotState.id == 1)
            )).scalar_one()
            if ok:
                bs.consecutive_health_fails = 0
                bs.last_health_ok_at = datetime.utcnow()
            else:
                bs.consecutive_health_fails += 1
                fails = bs.consecutive_health_fails
                threshold = self._settings.healthcheck_failure_threshold
                await session.commit()
                if fails >= threshold:
                    try:
                        await self._bot.send_message(
                            self._owner,
                            f"⚠️ Healthcheck: {fails} consecutive failures.\n"
                            f"Userbot may be disconnected — check VPS/logs.",
                        )
                    except Exception as e:
                        logger.exception(f"Failed to alert owner: {e}")
                    # Reset counter so we don't spam
                    async with self._factory() as s2:
                        bs2 = (await s2.execute(
                            select(BotState).where(BotState.id == 1)
                        )).scalar_one()
                        bs2.consecutive_health_fails = 0
                        await s2.commit()
                return False
            await session.commit()
        return ok

    async def run_forever(self) -> None:
        interval = self._settings.healthcheck_interval_sec
        logger.info(f"Health monitor started (interval={interval}s)")
        while True:
            try:
                await self.check_once()
            except Exception as e:
                logger.exception(f"Healthcheck loop iteration failed: {e}")
            await asyncio.sleep(interval)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_health_monitor.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/leads_bot/health/ tests/unit/test_health_monitor.py
git commit -m "feat(health): GetMe healthcheck with consecutive-failure alerting"
```

---

## Task 9: Rate-Limit Rotation

**Files:**
- Modify: `src/leads_bot/sender/rate_limiter.py` (add `rotate_old_records`)
- Test: `tests/unit/test_rate_limit_rotation.py`

The Iter 1 rate_limiter inserts a row per send and never cleans up. Over months that's ~10k+ rows. We add a `rotate_old_records(session, retention_hours)` method called hourly by the scheduler.

- [ ] **Step 1: Write failing test**

`tests/unit/test_rate_limit_rotation.py`:

```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from leads_bot.db.models import Base, RateLimit
from leads_bot.sender.rate_limiter import RateLimiter


@pytest.fixture
async def session(monkeypatch):
    for k, v in [("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
                 ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
                 ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
                 ("RATE_LIMIT_RETENTION_HOURS", "168")]:
        monkeypatch.setenv(k, v)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    f = async_sessionmaker(engine, expire_on_commit=False)
    async with f() as s:
        yield s
    await engine.dispose()


async def test_rotate_drops_old_records(session):
    now = datetime.utcnow()
    # 5 old (>168h), 3 fresh
    for d in [200, 180, 170, 169, 200]:
        session.add(RateLimit(window="hour", window_start=now - timedelta(hours=d), sent_count=1))
    for d in [10, 50, 167]:
        session.add(RateLimit(window="hour", window_start=now - timedelta(hours=d), sent_count=1))
    await session.commit()

    rl = RateLimiter()
    deleted = await rl.rotate_old_records(session)
    assert deleted == 5

    rows = (await session.execute(select(RateLimit))).scalars().all()
    assert len(rows) == 3


async def test_rotate_no_op_when_clean(session):
    rl = RateLimiter()
    deleted = await rl.rotate_old_records(session)
    assert deleted == 0
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_rate_limit_rotation.py -v
```

Expected: `AttributeError: 'RateLimiter' object has no attribute 'rotate_old_records'`.

- [ ] **Step 3: Add method to `src/leads_bot/sender/rate_limiter.py`**

Append inside the `RateLimiter` class:

```python
    async def rotate_old_records(self, session: AsyncSession) -> int:
        """Delete rate_limits rows older than RATE_LIMIT_RETENTION_HOURS.
        Returns number of deleted rows."""
        from sqlalchemy import delete
        cutoff = datetime.utcnow() - timedelta(
            hours=self._settings.rate_limit_retention_hours
        )
        result = await session.execute(
            delete(RateLimit).where(RateLimit.window_start < cutoff)
        )
        await session.commit()
        n = result.rowcount or 0
        if n:
            from loguru import logger
            logger.info(f"Rotated {n} old rate_limits rows (cutoff={cutoff.isoformat()})")
        return n
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_rate_limit_rotation.py tests/unit/test_rate_limiter.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/leads_bot/sender/rate_limiter.py tests/unit/test_rate_limit_rotation.py
git commit -m "feat(sender): rate_limits rotation to bound table growth"
```

---

## Task 10: Scheduler — background asyncio loops

**Files:**
- Create: `src/leads_bot/scheduler.py`

The scheduler runs three loops in parallel: digest (fires when current time crosses `quiet_end`), health (every `healthcheck_interval_sec`), rotation (every hour).

- [ ] **Step 1: Implement `src/leads_bot/scheduler.py`**

```python
"""Background asyncio loops: morning digest, healthcheck, rate-limit rotation.

Why no APScheduler: the three loops are simple wall-clock waits that don't need
a scheduler library. Each loop lives in its own task and respects KeyboardInterrupt.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from leads_bot.config import get_settings
from leads_bot.db.models import BotState
from leads_bot.health.monitor import HealthMonitor
from leads_bot.notifier.digest import run_morning_digest
from leads_bot.sender.rate_limiter import RateLimiter
from leads_bot.time_utils import parse_window


async def _sleep_until(target: datetime) -> None:
    """Sleep until `target` (aware datetime). Wakes early if interrupted."""
    now = datetime.now(target.tzinfo)
    delta = (target - now).total_seconds()
    if delta > 0:
        await asyncio.sleep(delta)


async def digest_loop(factory: async_sessionmaker, bot, owner_tg_id: int) -> None:
    """Fire `run_morning_digest` once at quiet-end every day.

    We compute next quiet-end based on `BotState.quiet_hours_override` if set,
    else `settings.quiet_hours`, in `settings.timezone`.
    """
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    while True:
        try:
            async with factory() as session:
                bs = (await session.execute(
                    select(BotState).where(BotState.id == 1)
                )).scalar_one_or_none()
                spec = (bs.quiet_hours_override if bs and bs.quiet_hours_override
                        else settings.quiet_hours)
            _, end = parse_window(spec)
            # Use digest_time if explicitly set (slightly after quiet end is the spec default)
            dh, dm = settings.digest_time_hm
            now = datetime.now(tz)
            target = now.replace(hour=dh, minute=dm, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info(f"Next digest at {target.isoformat()} (in {int(wait)}s)")
            await asyncio.sleep(wait)
            if settings.quiet_hours_enabled:
                await run_morning_digest(factory, bot=bot, owner_tg_id=owner_tg_id)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Digest loop iteration failed: {e}")
            await asyncio.sleep(60)


async def rotation_loop(factory: async_sessionmaker) -> None:
    """Hourly rate_limits cleanup."""
    rl = RateLimiter()
    while True:
        try:
            async with factory() as session:
                deleted = await rl.rotate_old_records(session)
                bs = (await session.execute(
                    select(BotState).where(BotState.id == 1)
                )).scalar_one()
                bs.last_rate_limit_rotation_at = datetime.utcnow()
                await session.commit()
            if deleted:
                logger.info(f"Rotation deleted {deleted} rate_limits rows")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception(f"Rotation loop iteration failed: {e}")
        await asyncio.sleep(3600)


async def start_background_tasks(
    factory: async_sessionmaker,
    user_client,
    bot,
    owner_tg_id: int,
) -> list[asyncio.Task]:
    """Spawn digest + health + rotation tasks. Returns the task handles."""
    monitor = HealthMonitor(user_client, bot, owner_tg_id, factory)
    tasks = [
        asyncio.create_task(digest_loop(factory, bot, owner_tg_id), name="digest"),
        asyncio.create_task(monitor.run_forever(), name="health"),
        asyncio.create_task(rotation_loop(factory), name="rotation"),
    ]
    logger.info(f"Started {len(tasks)} background tasks")
    return tasks
```

- [ ] **Step 2: Smoke-import test**

```bash
python -c "from leads_bot.scheduler import start_background_tasks, digest_loop, rotation_loop; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/leads_bot/scheduler.py
git commit -m "feat(scheduler): asyncio background loops (digest, health, rotation)"
```

---

## Task 11: Backup Script + Cron

**Files:**
- Create: `scripts/backup.py`
- Create: `deploy/crontab.example`
- Modify: `Dockerfile` (copy `scripts/`)
- Test: `tests/unit/test_backup_script.py`

The script is meant to be invoked from the **host** via `docker exec leads-bot python /app/scripts/backup.py`. It dumps SQLite to `/app/data/backup-YYYYMMDD.sql.gz` and prunes anything older than 30 days.

- [ ] **Step 1: Write failing test**

`tests/unit/test_backup_script.py`:

```python
import gzip
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts.backup import dump_database, prune_old_backups


def test_dump_database_creates_gzip(tmp_path: Path):
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE x (a INTEGER)")
    conn.execute("INSERT INTO x VALUES (1)")
    conn.commit(); conn.close()

    out = dump_database(db_path, tmp_path)
    assert out.exists()
    assert out.suffix == ".gz"
    with gzip.open(out, "rt") as f:
        content = f.read()
    assert "CREATE TABLE" in content
    assert "INSERT INTO" in content


def test_dump_filename_includes_date(tmp_path: Path):
    db_path = tmp_path / "bot.db"
    sqlite3.connect(db_path).close()
    out = dump_database(db_path, tmp_path)
    today = datetime.utcnow().strftime("%Y%m%d")
    assert today in out.name
    assert out.name.startswith("backup-")
    assert out.name.endswith(".sql.gz")


def test_prune_removes_old_backups(tmp_path: Path):
    # Create 5 fake backup files with mtime in the past
    for d in [40, 35, 31, 25, 1]:
        f = tmp_path / f"backup-{(datetime.utcnow() - timedelta(days=d)).strftime('%Y%m%d')}.sql.gz"
        f.write_bytes(b"x")
        ts = (datetime.utcnow() - timedelta(days=d)).timestamp()
        import os
        os.utime(f, (ts, ts))

    n = prune_old_backups(tmp_path, retention_days=30)
    assert n == 3  # the ones at d=40, 35, 31
    remaining = sorted(p.name for p in tmp_path.glob("backup-*.sql.gz"))
    assert len(remaining) == 2
```

- [ ] **Step 2: Run, expect fail**

```bash
pytest tests/unit/test_backup_script.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.backup'`.

- [ ] **Step 3: Make `scripts/` a package + add an `__init__.py`**

Create empty `scripts/__init__.py`.

- [ ] **Step 4: Implement `scripts/backup.py`**

```python
"""Dump SQLite DB to a timestamped .sql.gz and prune old backups.

Usage (from host cron):
    docker exec leads-bot python /app/scripts/backup.py

Defaults work for the in-container layout:
    DB:      /app/data/bot.db
    OUT DIR: /app/data
    KEEP:    30 days
"""
from __future__ import annotations

import argparse
import gzip
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def dump_database(db_path: Path, out_dir: Path) -> Path:
    """Dump `db_path` to `out_dir/backup-YYYYMMDD.sql.gz`. Returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    out = out_dir / f"backup-{stamp}.sql.gz"
    conn = sqlite3.connect(str(db_path))
    try:
        with gzip.open(out, "wt", encoding="utf-8") as gz:
            for line in conn.iterdump():
                gz.write(line + "\n")
    finally:
        conn.close()
    return out


def prune_old_backups(out_dir: Path, retention_days: int) -> int:
    """Delete backup-*.sql.gz files older than `retention_days`. Returns count."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = 0
    for p in out_dir.glob("backup-*.sql.gz"):
        mtime = datetime.utcfromtimestamp(p.stat().st_mtime)
        if mtime < cutoff:
            p.unlink()
            deleted += 1
    return deleted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup SQLite DB and prune old dumps.")
    ap.add_argument("--db", default="/app/data/bot.db", type=Path)
    ap.add_argument("--out", default="/app/data", type=Path)
    ap.add_argument("--keep-days", default=30, type=int)
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 1

    out = dump_database(args.db, args.out)
    n = prune_old_backups(args.out, args.keep_days)
    size_kb = out.stat().st_size // 1024
    print(f"Backup written: {out} ({size_kb} KB), pruned {n} old files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create `deploy/crontab.example`**

```
# Host crontab for leads-bot daily backup.
# Install:  crontab -e   then paste the line below.
# Adjust the time (here: 04:15 UTC) to your preference.
15 4 * * * docker exec leads-bot python /app/scripts/backup.py >> /var/log/leads-bot-backup.log 2>&1
```

- [ ] **Step 6: Update `Dockerfile` to include `scripts/`**

Replace the `Dockerfile` with:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN uv pip install --system --no-cache .

COPY alembic.ini ./
COPY src/leads_bot/db/migrations ./src/leads_bot/db/migrations
COPY data/profile.example.json ./data/
COPY scripts/ ./scripts/

RUN mkdir -p /app/data /app/logs

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "alembic upgrade head && python -m leads_bot.main"]
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/unit/test_backup_script.py -v
```

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add scripts/__init__.py scripts/backup.py deploy/crontab.example Dockerfile tests/unit/test_backup_script.py
git commit -m "feat(backup): SQLite dump script + host crontab example, 30-day retention"
```

---

## Task 12: Wire Everything in `main.py`

**Files:**
- Modify: `src/leads_bot/main.py`

- [ ] **Step 1: Replace `src/leads_bot/main.py`**

```python
"""Async entry point — boots Telethon + aiogram + pipeline + background loops."""
import asyncio
import sys
from functools import partial
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from leads_bot.analyzer.analyzer import Analyzer
from leads_bot.config import get_settings
from leads_bot.db.seed import seed_sources_from_json
from leads_bot.db.session import ensure_bot_state, get_engine, get_session_factory
from leads_bot.drafter.drafter import Drafter
from leads_bot.drafter.profile import load_profile
from leads_bot.listener.client import build_client
from leads_bot.listener.handler import register_listener
from leads_bot.notifier.bot import build_bot, build_dispatcher
from leads_bot.notifier.commands import (
    cmd_draft_retry, cmd_pause, cmd_profile, cmd_quiet, cmd_resume,
    cmd_sources, cmd_sources_add, cmd_sources_pause, cmd_sources_resume,
    cmd_stats, cmd_templates,
)
from leads_bot.notifier.edit_flow import (
    cancel_edit, confirm_edit, receive_edit_text, start_edit,
)
from leads_bot.notifier.handlers import handle_callback
from leads_bot.notifier.states import EditStates
from leads_bot.pipeline import Pipeline
from leads_bot.scheduler import start_background_tasks
from leads_bot.sender.sender import Sender


def _setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level:<8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    Path("logs").mkdir(exist_ok=True)
    logger.add("logs/bot.log", rotation="100 MB", retention="7 days", level="INFO")


def _build_router(factory, user_client, pipeline, sender, profile_path: Path) -> Router:
    """Wire commands + edit FSM into a single router."""
    r = Router()

    # ─── Commands (owner-only, enforced upstream) ────────────────────────
    @r.message(Command("stats"))
    async def _stats(m: Message): await cmd_stats(m, factory)

    @r.message(Command("sources"))
    async def _sources(m: Message):
        text = (m.text or "").strip()
        parts = text.split()
        if len(parts) == 1:
            await cmd_sources(m, factory)
        elif len(parts) >= 2 and parts[1] == "add":
            await cmd_sources_add(m, factory, user_client)
        elif len(parts) >= 2 and parts[1] == "pause":
            await cmd_sources_pause(m, factory)
        elif len(parts) >= 2 and parts[1] == "resume":
            await cmd_sources_resume(m, factory)
        else:
            await m.answer("Usage:\n/sources\n/sources add <link> <region> <lang>\n"
                           "/sources pause <id>\n/sources resume <id>")

    @r.message(Command("pause"))
    async def _pause(m: Message): await cmd_pause(m, factory)

    @r.message(Command("resume"))
    async def _resume(m: Message): await cmd_resume(m, factory)

    @r.message(Command("quiet"))
    async def _quiet(m: Message): await cmd_quiet(m, factory)

    @r.message(Command("profile"))
    async def _profile(m: Message): await cmd_profile(m, factory, profile_path)

    @r.message(Command("templates"))
    async def _templates(m: Message): await cmd_templates(m, factory)

    @r.message(Command("draft"))
    async def _draft(m: Message): await cmd_draft_retry(m, factory, pipeline)

    @r.message(Command("cancel"), StateFilter(EditStates.awaiting_text, EditStates.confirming))
    async def _cancel(m: Message, state: FSMContext):
        await state.clear()
        await m.answer("Отменено.")

    # ─── Edit FSM ─────────────────────────────────────────────────────────
    @r.callback_query(F.data.startswith("edit:"))
    async def _start_edit(cq: CallbackQuery, state: FSMContext):
        await start_edit(cq, state)

    @r.message(StateFilter(EditStates.awaiting_text), F.text)
    async def _receive_edit(m: Message, state: FSMContext):
        await receive_edit_text(m, state)

    @r.callback_query(F.data.startswith("confirm_edit:"))
    async def _confirm(cq: CallbackQuery, state: FSMContext):
        await confirm_edit(cq, state, factory, sender)

    @r.callback_query(F.data.startswith("cancel_edit:"))
    async def _cancel_edit(cq: CallbackQuery, state: FSMContext):
        await cancel_edit(cq, state, factory, sender)

    # ─── Approve / skip / mute (legacy callbacks from Iter1) ─────────────
    @r.callback_query(F.data.regexp(r"^(approve|skip|mute):\d+$"))
    async def _legacy(cq: CallbackQuery):
        await handle_callback(cq, factory, sender)

    return r


async def main():
    _setup_logging()
    settings = get_settings()
    logger.info("Starting leads-bot (iter2)")

    factory = get_session_factory()
    await ensure_bot_state(factory)

    sources_path = Path("data/sources.json")
    if sources_path.exists():
        await seed_sources_from_json(sources_path, factory)
    else:
        logger.info(
            "data/sources.json not found — sources will be managed via /sources commands."
        )

    profile_path = Path("data/profile.json")
    if not profile_path.exists():
        logger.error(
            "data/profile.json missing — copy from data/profile.example.json and fill in"
        )
        return
    profile = load_profile(profile_path)

    analyzer = Analyzer()
    drafter = Drafter(profile)
    notif_bot = build_bot()

    user_client = build_client()
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot started for {settings.telegram_phone}")

    sender = Sender(telethon_client=user_client)
    pipeline = Pipeline(
        analyzer=analyzer, drafter=drafter,
        bot=notif_bot, owner_tg_id=settings.owner_tg_id,
        factory=factory,
    )

    register_listener(user_client, factory, on_new_lead=pipeline.process_new_lead)

    dp = build_dispatcher()

    # Owner-only filter applied via outer router
    @dp.update.outer_middleware()
    async def owner_only(handler, event, data):
        msg = (
            getattr(event, "message", None)
            or getattr(event, "callback_query", None)
        )
        if msg is None:
            return await handler(event, data)
        from_user = getattr(msg, "from_user", None)
        if from_user is not None and from_user.id != settings.owner_tg_id:
            if hasattr(msg, "answer"):
                try:
                    await msg.answer("Не для тебя.")
                except Exception:
                    pass
            return None
        return await handler(event, data)

    router = _build_router(factory, user_client, pipeline, sender, profile_path)
    dp.include_router(router)

    bg_tasks = await start_background_tasks(factory, user_client, notif_bot, settings.owner_tg_id)

    polling_task = asyncio.create_task(dp.start_polling(notif_bot))
    telethon_task = asyncio.create_task(user_client.run_until_disconnected())

    logger.info("Bot is up. Listening for new messages.")
    try:
        await asyncio.gather(polling_task, telethon_task, *bg_tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        for t in bg_tasks:
            t.cancel()
        await notif_bot.session.close()
        await user_client.disconnect()
        engine = get_engine()
        if engine is not None:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Smoke-import test**

```bash
python -c "from leads_bot.main import main, _build_router; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all passing (Iter1 67 + new Iter2 tests).

- [ ] **Step 4: Commit**

```bash
git add src/leads_bot/main.py
git commit -m "feat(main): wire commands router, edit FSM, owner-only middleware, background tasks"
```

---

## Task 13: README + deploy notes

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Append to `README.md`**

```markdown
## Iteration 2 features

### Commands

All commands are owner-only (checked against `OWNER_TG_ID`).

| Command | Effect |
|---|---|
| `/stats` | Today's lead count, sent count, replies, paused state |
| `/sources` | List all sources with id/title/region/language/status |
| `/sources add <link> <region> <lang>` | Resolve link via Telethon and add. Allowed regions: `ua`, `cis_ex_ru`, `eu`, `en_global` |
| `/sources pause <id>` | Set source status=paused |
| `/sources resume <id>` | Set source status=active |
| `/pause` | Global pause — listener still records leads, pipeline ignores them |
| `/resume` | Global resume |
| `/quiet HH:MM-HH:MM` | Override quiet-hours window (persisted in `bot_state.quiet_hours_override`) |
| `/profile` | Show currently-loaded `data/profile.json` |
| `/templates` | Stub — A/B templates land in Iteration 4 |
| `/draft <lead_id> retry` | Regenerate the draft for a lead and resend the card |

### Quiet hours + morning digest

When `QUIET_HOURS_ENABLED=true`, leads that arrive inside the quiet window are
analyzed and drafted, but the response card is **not** posted to the owner.
Instead the response sits in `status='pending_digest'`. At `DIGEST_TIME`
(default 08:15), the digest loop posts a single summary message and promotes
all pending responses back to `status='drafted'`.

### Healthcheck

The userbot is pinged via `client.get_me()` every `HEALTHCHECK_INTERVAL_SEC`
(default 600s). After `HEALTHCHECK_FAILURE_THRESHOLD` consecutive failures
(default 3) the owner gets a Telegram alert and the counter resets.

### Backup

The `scripts/backup.py` script dumps the SQLite DB to a timestamped `.sql.gz`
in `/app/data/` and prunes anything older than 30 days. Schedule it from the
**host** crontab — the container does not run cron itself.

```bash
sudo crontab -e
# Paste the line from deploy/crontab.example
```

### Tests

```bash
pytest                          # all unit + integration
pytest tests/integration/test_quiet_hours_flow.py -v   # verify quiet behavior
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: iter2 commands, quiet+digest, healthcheck, backup"
```

---

## Task 14: Manual E2E Verification

**No code — checklist.**

- [ ] **Step 1: Apply migrations**

```bash
alembic upgrade head
```

- [ ] **Step 2: Verify all unit + integration tests pass**

```bash
pytest -v
```

Expected: all green, no skips.

- [ ] **Step 3: Test commands flow locally**

Start bot:

```bash
docker compose up
```

In Telegram DM with `@vita_leads_bot`:

- Send `/stats` — verify formatted reply with today's counts.
- Send `/sources` — verify list (empty or seeded).
- Send `/sources add @<your_test_channel> ua uk` — verify it resolves and adds.
- Send `/sources pause 1` then `/sources resume 1` — verify status changes via `/sources`.
- Send `/profile` — verify profile dump.
- Send `/templates` — verify stub message.
- Send `/quiet 22:00-09:00` — verify confirmation.
- Send `/pause` — post a test lead in your channel; verify NO card arrives. Then `/resume`.
- Send `/draft <existing_lead_id> retry` — verify a fresh card with new draft arrives.

- [ ] **Step 4: Test edit flow**

- Wait for a real lead card.
- Tap ✏️ — verify bot asks for new text.
- Send `Replaced reply text`.
- Verify confirm card with `[✅ Send this version] [↩ Back to draft]`.
- Tap ✅ — verify Telethon sends `Replaced reply text` to target, DB row has `final_text` set, `status='approved'` then `'sent'`.
- Repeat with another lead and tap ↩ instead — verify no send happens, FSM clears.

- [ ] **Step 5: Test quiet-hours behavior**

- Temporarily set `QUIET_HOURS=00:00-23:59` and `QUIET_HOURS_ENABLED=true` in `.env`, restart.
- Post a lead-like message in your test channel.
- Verify NO card arrives in DM.
- Verify `Response.status='pending_digest'` in DB.
- Set `DIGEST_TIME` to 1-2 minutes ahead of current local time, restart.
- Wait for the configured time; verify a digest message arrives, response status flips back to `drafted`.

- [ ] **Step 6: Test healthcheck alert**

- Stop the userbot client by killing its session externally (e.g. log out via Telegram > Devices).
- Within 3 × `HEALTHCHECK_INTERVAL_SEC` (set to 30s for the test), verify owner receives `⚠️ Healthcheck...` alert.
- Verify alert is sent only once (counter reset).

- [ ] **Step 7: Test rate-limit rotation**

- Manually insert old rows: `sqlite3 data/bot.db "INSERT INTO rate_limits (window, window_start, sent_count) VALUES ('hour', datetime('now', '-200 hours'), 1)"`.
- Wait up to 1 hour (or trigger by restarting and watching logs).
- Verify the row is deleted; logs show `Rotated N old rate_limits rows`.

- [ ] **Step 8: Test backup script in-container**

```bash
docker exec leads-bot python /app/scripts/backup.py
ls -la data/backup-*.sql.gz
gzip -t data/backup-*.sql.gz   # verify integrity
```

Expected: a fresh `.sql.gz` file appears.

- [ ] **Step 9: Install host crontab**

```bash
sudo crontab -l > /tmp/cron_backup
cat deploy/crontab.example >> /tmp/cron_backup
sudo crontab /tmp/cron_backup
sudo crontab -l   # verify
```

- [ ] **Step 10: Document any issues found, fix, re-test, commit**

```bash
# After fixes:
git add <changed files>
git commit -m "fix(iter2): <specific issue from E2E>"
```

---

## Definition of Done — Iteration 2

- [ ] **All tests pass:** `pytest` returns 0 failures, with the new Iter2 test files included.
- [ ] **Commands surface complete:** owner can invoke `/stats`, `/sources`, `/sources add @x ua uk`, `/sources pause N`, `/sources resume N`, `/pause`, `/resume`, `/quiet 22:00-09:00`, `/profile`, `/templates`, `/draft N retry` — verified manually in DM with the bot, each returns a non-empty reply.
- [ ] **Edit flow works end-to-end:** owner can tap ✏️ on a real card, send a replacement message, see the confirm card, and tap ✅ to send the edited text via Telethon. Tapping ↩ clears state without sending.
- [ ] **Quiet hours obey config:** with `QUIET_HOURS_ENABLED=true`, leads arriving inside the window do NOT produce a card; their response rows are `status='pending_digest'`. Verified by `tests/integration/test_quiet_hours_flow.py`.
- [ ] **Morning digest fires once at `DIGEST_TIME`:** sends a summary message listing leads scored high-to-low; flips all `pending_digest` rows back to `drafted`; updates `BotState.last_digest_at`.
- [ ] **Sources are managed via DB + commands:** `/sources add` writes a row, `/sources pause` flips status. `data/sources.json` is now bootstrap-only and optional.
- [ ] **Healthcheck alerts owner on 3 consecutive failures:** triggered by simulated disconnect, verified single alert message, counter reset to 0 after.
- [ ] **Rate-limit rotation runs hourly:** `BotState.last_rate_limit_rotation_at` is updated; old rows (>168h by default) are deleted.
- [ ] **Backup script produces verifiable `.sql.gz`:** `gzip -t data/backup-YYYYMMDD.sql.gz` returns 0; `gunzip -c | head` shows valid `CREATE TABLE`/`INSERT` SQL; files older than 30 days are pruned on next run.
- [ ] **Host cron line installed:** `crontab -l` on VPS shows the `docker exec leads-bot python /app/scripts/backup.py` line; next-day check confirms a new dated backup file.
- [ ] **24-hour soak test:** bot left running on VPS overnight, no crash logs, healthcheck count stays at 0, morning digest delivered, no FloodWait alerts, response cards appear normally outside quiet hours.

---

### Critical Files for Implementation

- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/main.py` — central wiring point; everything new (router, FSM, middleware, background tasks) is registered here.
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/notifier/edit_flow.py` — new FSM flow for the ✏️ edit button (was a stub in Iter1).
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/notifier/commands.py` — full `/stats`, `/sources*`, `/pause`, `/resume`, `/quiet`, `/profile`, `/templates`, `/draft` surface.
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/scheduler.py` — asyncio loops for digest, healthcheck, rate-limit rotation.
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/pipeline.py` — modified to honor global pause + quiet-hours decision (`pending_digest` vs `drafted`).
- `/Users/vitalinanikulina/Documents/Work/search for projects/src/leads_bot/db/models.py` — new `BotState` singleton + `quiet_hours_override` column.

---

**Status:** DONE_WITH_CONCERNS
**Plan target file path:** `docs/superpowers/plans/2026-05-17-iter2-stabilization.md`

**Concerns:**

1. **Read-only mode prevented file write.** I am strictly forbidden from creating files (per the system prompt's READ-ONLY MODE block), so the plan is delivered inline as my assistant message rather than written to `docs/superpowers/plans/2026-05-17-iter2-stabilization.md`. The user will need to copy this output into that file (or invoke a non-read-only agent to materialize it).

2. **Aiogram outer-middleware signature.** The `owner_only` middleware in `main.py` Task 12 uses `@dp.update.outer_middleware()` — aiogram 3.13 expects a class-based middleware in some patterns. If the decorator-style fails at runtime, the fix is to subclass `BaseMiddleware`. Worth a quick smoke test on first boot.

3. **Telethon `get_peer_id` import.** `from telethon.utils import get_peer_id` — confirmed available in 1.36, but if the import surface ever shifts, the sources service add-from-link test will fail loudly (it's covered by `test_add_source_from_username`).

4. **Digest timing relies on `digest_time` not `quiet_hours_end`.** The spec says "morning digest" without naming a separate field; I introduced `DIGEST_TIME` (default 08:15) so quiet-hours and digest can be tuned independently. If the user wants strictly digest-at-quiet-end, simplify `digest_loop` to derive target from `parse_window(spec)[1]`.

5. **`Pipeline.regenerate_draft` and `pipeline._factory`.** The integration test for `test_pipeline.py` from Iter1 calls `Pipeline(...)` without `factory=`. I made it optional, so the existing test should keep passing — but worth verifying first run.

6. **Backup script tested with sqlite `iterdump`.** This produces text SQL (gzipped) rather than binary `.backup`. Easier to inspect/restore but slightly larger; acceptable trade-off for the small schema.
