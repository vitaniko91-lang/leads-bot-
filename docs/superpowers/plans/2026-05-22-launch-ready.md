# Launch-Ready Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Довести бота до боевой работы локально — от текущего состояния «не запущен, нет реальных источников» до состояния «слушает 5-15 реальных каналов, ловит лиды, шлёт драфты владельцу».

**Architecture:** Без изменений кода. Только: правка `.env`, один новый одноразовый ops-скрипт (`scripts/run_discovery_once.py`, по образцу `scripts/backup.py`), и серия ручных проверок/действий. Discovery-модуль уже встроен в код (iter4) — нужна только точка ad-hoc запуска.

**Tech Stack:** Python 3.13, asyncio, Telethon (userbot), aiogram (notifier bot), SQLAlchemy 2.0 async, loguru. Все зависимости уже в `pyproject.toml`.

**Spec reference:** `docs/superpowers/specs/2026-05-22-launch-ready-design.md`

---

## File Structure

```
.
├── .env                                  ~  TIMEZONE: Asia/Bangkok → Europe/Kiev
├── data/
│   ├── profile.json                      [done in brainstorm session]
│   └── templates.json                    [done in brainstorm session]
└── scripts/
    └── run_discovery_once.py             +  one-shot discovery scan + digest
```

**Note:** все остальные изменения — ops (запуск процессов, нажатия кнопок в Telegram, наблюдение). Кода менять не нужно.

---

## Task 1: Fix TIMEZONE in .env

**Files:**
- Modify: `.env:23`

**Why:** `Asia/Bangkok` — артефакт прошлой настройки. `DIGEST_TIME=08:15` и `QUIET_HOURS=23:00-08:00` должны жить в часовом поясе Одессы. Иначе утренний дайджест придёт в 04:15 ночи.

- [ ] **Step 1: Read current `.env` line 23**

```bash
grep '^TIMEZONE=' .env
```
Expected: `TIMEZONE=Asia/Bangkok`

- [ ] **Step 2: Replace value**

```bash
sed -i '' 's|^TIMEZONE=Asia/Bangkok$|TIMEZONE=Europe/Kiev|' .env
```

- [ ] **Step 3: Verify**

```bash
grep '^TIMEZONE=' .env
```
Expected: `TIMEZONE=Europe/Kiev`

- [ ] **Step 4: Verify config loads correctly**

```bash
uv run python -c "from leads_bot.config import get_settings; print(get_settings().timezone)"
```
Expected: `Europe/Kiev` (no errors)

- [ ] **Step 5: Commit**

```bash
git add .env
git commit -m "config: timezone to Europe/Kiev for Odesa-based owner"
```

Note: если `.env` в `.gitignore`, шаг коммита пропускается; вместо него короткая запись в личных заметках.

---

## Task 2: Cold-Start Smoke

**Files:** none (verification only)

**Why:** убедиться что после изменений в `.env` и `profile.json` бот стартует без ошибок, Telethon коннектится, aiogram отвечает.

- [ ] **Step 1: Verify dependencies are in sync**

```bash
cd "/Users/vitalinanikulina/Documents/Work/search for projects"
uv sync
```
Expected: no errors, "Resolved N packages"

- [ ] **Step 2: Apply pending DB migrations (safe — should be no-op)**

```bash
uv run alembic upgrade head
```
Expected: `Running upgrade ... -> 2026_05_29_iter4_smart` OR `Already at head`

- [ ] **Step 3: Start the bot in a dedicated terminal**

```bash
uv run python -m leads_bot.main
```

Keep this terminal visible — bot logs live here.

- [ ] **Step 4: Verify startup logs (within 30 seconds)**

You should see these lines in order:

```
INFO ... Starting leads-bot (iter4 smart)
INFO ... Seeded N new sources from data/sources.json
INFO ... Seeded N new templates from data/templates.json   ← no "not found" warning now
INFO ... Userbot started for <phone>
INFO ... Discovery scheduler started (tz=Europe/Kiev)
INFO ... Started 3 background tasks
INFO ... Bot is up. Listening for new messages, DMs, and weekly discovery.
INFO ... Next digest at <timestamp>+03:00 ...                ← +03:00 confirms Kiev TZ
```

- [ ] **Step 5: From Telegram, send `/start` to `@vita_leads_bot`**

Expected: bot answers with greeting / acknowledgement (existing iter1 handler).

- [ ] **Step 6: Send `/stats`**

Expected: bot responds with today's stats (likely zeros). Confirms aiogram polling + commands work.

- [ ] **Step 7: Send `/profile`**

Expected: bot prints the freshly-saved profile JSON (AXON, GFIT, Gusto, Behance URL). Confirms `data/profile.json` is loaded correctly.

- [ ] **Step 8: Test reconnect (resilience check)**

Disable Wi-Fi for ~30 seconds, then re-enable.
Watch logs for either:
- `Healthcheck failed: ConnectionError ...` followed by `Healthcheck recovered` / next healthy ping — OK
- Continuous failures without recovery — flag as bug, do NOT proceed to Task 3

- [ ] **Step 9: Stop the bot** (Ctrl+C)

Expected: clean shutdown without traceback.

---

## Task 3: Write `scripts/run_discovery_once.py`

**Files:**
- Create: `scripts/run_discovery_once.py`

**Why:** discovery-модуль (iter4) умеет `scan_now()` + `send_digest_now()`, но эти методы вызываются APScheduler-ом только по cron (среда 03:00, воскресенье 10:00). Для первого запуска нужна одноразовая точка входа. Скрипт повторяет bootstrap из `main.py` (Telethon client, aiogram bot, DB factory), но вместо запуска listener/dispatcher просто дёргает scan + digest и выходит.

**Pattern:** следуем `scripts/backup.py` — самодостаточный CLI, без тестов (это ops-скрипт, не библиотека).

**Constraint:** во время запуска этого скрипта **основной бот должен быть остановлен**, потому что Telethon-сессия эксклюзивна (один процесс держит лок на `leads_bot_session.session`).

- [ ] **Step 1: Create the file with the content below**

```python
"""One-shot ad-hoc discovery: scan now + send digest to owner.

Usage (with the main bot stopped):
    uv run python scripts/run_discovery_once.py

The digest arrives in the owner's Telegram with [Add]/[Reject] buttons.
Callbacks are persisted in Telegram, so they will be handled correctly
after you restart the main bot.

Exit codes:
    0 — scan completed (regardless of insertion count)
    1 — bootstrap failure (config, DB, Telethon, or aiogram error)
"""
from __future__ import annotations

import asyncio
import sys

from loguru import logger

from leads_bot.config import get_settings
from leads_bot.db.session import get_engine, get_session_factory
from leads_bot.discovery.scheduler import DiscoveryScheduler
from leads_bot.discovery.searcher import DiscoverySearcher
from leads_bot.listener.client import build_client
from leads_bot.notifier.bot import build_bot


async def run() -> int:
    settings = get_settings()

    engine = get_engine(settings.database_url)
    factory = get_session_factory(engine)

    user_client = build_client(settings)
    await user_client.start(phone=settings.telegram_phone)
    logger.info(f"Userbot started for {settings.telegram_phone}")

    notif_bot = build_bot(settings.bot_token)

    searcher = DiscoverySearcher(
        user_client, sleep_seconds=2, limit_per_query=20,
    )
    scheduler = DiscoveryScheduler(
        searcher=searcher, factory=factory, bot=notif_bot,
        owner_tg_id=settings.owner_tg_id, timezone=settings.timezone,
    )

    try:
        inserted = await scheduler.scan_now()
        logger.info(f"scan_now inserted {inserted} candidates")
        await scheduler.send_digest_now()
        logger.info("digest sent")
    finally:
        await user_client.disconnect()
        await notif_bot.session.close()
        await engine.dispose()

    return inserted


def main() -> None:
    try:
        n = asyncio.run(run())
        print(f"OK: {n} new candidates persisted, digest sent.")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Discovery one-shot failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the file imports cleanly (no runtime execution)**

```bash
uv run python -c "import scripts.run_discovery_once; print('imports OK')"
```
Expected: `imports OK` and no traceback.

Note: this will pull in `leads_bot.*` modules but won't connect to Telegram (we didn't call `main()`).

- [ ] **Step 3: Commit**

```bash
git add scripts/run_discovery_once.py
git commit -m "scripts: ad-hoc discovery — scan_now + send_digest_now in one shot"
```

---

## Task 4: Run Discovery and Approve Channels

**Files:** none (manual ops + Telegram clicks)

**Why:** Task 3 produces the trigger. This task uses it to actually populate `sources`.

- [ ] **Step 1: Confirm main bot is stopped**

```bash
ps aux | grep "leads_bot.main" | grep -v grep
```
Expected: empty output (no process).

If something is running — `kill <pid>`.

- [ ] **Step 2: Run the discovery script**

```bash
uv run python scripts/run_discovery_once.py
```

Expected (within 1-3 minutes):

```
INFO ... Userbot started for <phone>
INFO ... Discovery: starting weekly scan
INFO ... Discovery: scan inserted N new candidates
INFO ... Discovery: sending weekly digest
INFO ... digest sent
OK: N new candidates persisted, digest sent.
```

If N = 0: see fallback below.

- [ ] **Step 3: Restart the main bot in a separate terminal**

```bash
uv run python -m leads_bot.main
```
Wait for `Bot is up. Listening ...`

- [ ] **Step 4: Open the digest in your Telegram**

The digest comes as multiple messages from `@vita_leads_bot`, each showing one candidate channel with `[✅ Add]` and `[❌ Reject]` buttons.

- [ ] **Step 5: Approve 5-15 channels**

Click `[✅ Add]` on the ones that look like real freelance/jobs channels for designers (UA/CIS-ex-RU/EU/EN-global).
Click `[❌ Reject]` on obvious noise (random communities, off-topic, RU-only despite the blocklist).

Goal: 5-15 channels accepted.

- [ ] **Step 6: Verify sources are in DB**

```bash
sqlite3 data/bot.db \
  "SELECT id, title, region, language, status FROM sources WHERE status='active';"
```
Expected: 5-15 rows (the test channel + your new approvals).

- [ ] **Step 7: Verify Telethon picked up new channels**

In the bot terminal, you should see (per added channel):

```
INFO ... Joined / resubscribed to <channel title>
```
or equivalent log from `register_listener`. If it doesn't auto-join: Telethon userbot needs the channel to be already accessible from `@Vita_webdesigner` account. Some discovery candidates may require manual `/join` from your Telegram client first.

**Fallback if Step 2 returned 0 candidates:**

- Manually google `freelance design jobs telegram channel Ukraine` (and `Europe`, `EN`)
- For each found channel, in your Telegram bot DM type:
  ```
  /sources add @channel_username ua uk
  ```
  (Regions allowed: `ua`, `cis_ex_ru`, `eu`, `en_global`. Languages: `uk`, `ru`, `en`.)
- Aim for 5+ manually-added sources.

---

## Task 5: 24-72h Observation + First-Lead Smoke E2E

**Files:** none (observation phase)

**Why:** код один раз стартовал и поймал тестовые лиды, но цикл «реальный пост → карточка → ✏️/✅ → отправка от твоего имени → антибан-задержка → проверка в исходном канале» никогда не прогонялся на боевых каналах.

- [ ] **Step 1: Leave the bot running in its terminal**

Don't close the terminal. If your laptop sleeps, leads from that period are lost — but bot resumes on wake (Telethon catches up on missed updates within the session retention window).

- [ ] **Step 2: Wait for the first real lead**

Expected within 1-6 hours depending on channel activity. Watch the bot terminal for:

```
INFO ... New message in <channel> ... matched filter
INFO ... Analyzer: relevance=N budget=$M lang=...
INFO ... Drafter: using template '<name>' (variant ...)
INFO ... Drafted reply (NNN chars) for <lang> lead
INFO ... Lead N queued (drafted)   ← if outside quiet hours
```

A lead card should arrive in your Telegram from `@vita_leads_bot`.

- [ ] **Step 3: Smoke-check the card content**

On the card, verify:
- Source link is clickable and points to the original post
- Relevance score is shown (e.g. 72/100)
- Budget signal (e.g. "$1,500" or "negotiable")
- Detected language (en / ru / uk)
- Draft text reads as plausible YOU (mentions AXON / Behance / payment options)

- [ ] **Step 4: Exercise the ✏️ edit flow**

Tap `✏️ Edit`. Bot prompts for new text. Send a revised version. Bot shows `[✅ Send this version]` / `[↩ Back to draft]`. Tap Back; verify the original draft re-appears. (This validates the edit FSM without committing.)

- [ ] **Step 5: Decide on send**

If the draft (or edited version) is genuinely something you'd send → tap `✅ Send`.
If not → tap `❌ Skip`, note in writing what felt off (for Task 6 calibration).

- [ ] **Step 6: If ✅ was tapped — verify send happened**

Within `SEND_DELAY_MIN..MAX` seconds (30-90s), check the original channel. Your message should appear posted from `@Vita_webdesigner`. The bot terminal should log:

```
INFO ... Sender: sent response NNN after Ms delay
```

Status in DB:

```bash
sqlite3 data/bot.db "SELECT id, status, sent_at FROM responses WHERE id=<N>;"
```
Expected: `status='sent'`, `sent_at` filled.

- [ ] **Step 7: Watch for client reply (next 24-72h)**

If the client replies to your sent message via DM to `@Vita_webdesigner`, the DM listener (iter4) should detect it and notify you:

```
INFO ... DM detector: client_replied=true for response NNN
```

In your Telegram you receive a notification from `@vita_leads_bot` with buttons `[Reply in dialog] [Mark as work] [Rejected]`.

- [ ] **Step 8: Log observations**

Open `docs/superpowers/specs/2026-05-22-launch-ready-design.md` Section 7 ("Открытые вопросы") in your editor. At the bottom, append a "## Observations 2026-05-22..2026-05-25" section with:
- # of leads received vs sent
- % of drafts you'd send without edits
- Channels giving signal vs noise
- Any healthcheck/reconnect events

This becomes the input for Task 6 (calibration) and for the VPS go/no-go decision in spec section 4 Phase 5.

---

## Task 6: Calibration Runbook (Reference)

**Files:** none (this task IS reference material — read, don't execute unless symptom)

**Why:** в Фазе 4 спеки описано «реагируем по симптомам». Этот таск — конкретные команды на каждый симптом.

| Symptom | Command / Action |
|---|---|
| **≥30% карточек нерелевантны** | Edit `.env`: `MIN_RELEVANCE_SCORE=70` (from 60). Restart bot. |
| **<1 лида в день при 10+ каналах** | Edit `.env`: `MIN_RELEVANCE_SCORE=50` and/or `MIN_BUDGET_USD=300`. Restart bot. |
| **Draft mentions wrong case** | Edit `data/profile.json`: refine `tags` of cases so they match incoming-lead vocabulary. Restart bot. |
| **Template A consistently underperforms B** | Via dashboard `/templates` (если поднят) — снижай `traffic_share` у A, повышай у B. Иначе: `sqlite3 data/bot.db "UPDATE templates SET traffic_share=20 WHERE name='Friendly + portfolio (A)';"` |
| **Channel gives only noise** | In bot DM: `/sources pause <id>` (id из `/sources` list). |
| **Healthcheck alerts > 1/day** | Edit `.env`: `HEALTHCHECK_FAILURE_THRESHOLD=5` (from 3). Restart bot. |
| **Quiet hours misfire** | Verify `TIMEZONE=Europe/Kiev` is loaded: `uv run python -c "from leads_bot.config import get_settings; print(get_settings().timezone)"` |

- [ ] **Step 1: Bookmark this table**

No action — keep this file accessible during the observation week.

- [ ] **Step 2: After 5-7 days of observation, decide on VPS migration**

Trigger criteria (from spec section 4, Phase 5):
- ≥3 real qualified leads in the week
- ≥1 client responded to a draft
- Healthcheck stable
- ≥70% drafts sent without manual edits

If all four hit → start a new spec for the VPS-deploy pipeline (Hetzner CX22 + Caddy + domain).
If not → loop: pick the weakest criterion, address via this table, observe another week.

---

## Self-Review Checklist (for plan author)

Spec coverage verified:
- ✅ Section 2.5 (TIMEZONE) → Task 1
- ✅ Phase 1 (cold start) → Task 2
- ✅ Phase 2 (ad-hoc discovery) → Tasks 3 + 4
- ✅ Phase 3 (smoke E2E) → Task 5
- ✅ Phase 4 (calibration) → Task 6
- ✅ Phase 5 (VPS decision) → Task 6 Step 2

Open questions from spec section 7:
- "Если discovery возвращает 0 кандидатов" → Task 4 fallback section
- "Дашборд /api/templates работает?" → not blocking — Task 5 doesn't require dashboard; verify later if calibration needs it
- "Телефон +84..." → not addressed in this plan; user must confirm before Task 2 Step 3 (userbot starts with whatever phone is configured)
