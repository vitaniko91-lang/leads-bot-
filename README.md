# Leads Bot

Telegram userbot for finding freelance design leads. See full design spec in `docs/superpowers/specs/2026-05-10-telegram-leads-bot-design.md`.

## Setup (local development)

1. Python 3.12+ installed
2. Get Telegram API credentials at https://my.telegram.org
3. Create bot at @BotFather, copy token
4. Get Anthropic API key at https://console.anthropic.com
5. Copy `.env.example` to `.env` and fill in credentials
6. Install: `uv sync` (or `pip install -e .`)
7. Init DB: `alembic upgrade head`
8. Run: `python -m leads_bot.main`

## Testing

`pytest`

## Deploy (VPS)

See `docker-compose.yml`. SSH to VPS, clone repo, copy `.env`, `docker compose up -d`.

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

### Edit-response flow

Tap ✏️ on a lead card → bot asks for the new text → reply with the rewritten message → confirm with `[✅ Send this version]` or back out with `[↩ Back to draft]`. Implemented as an aiogram FSM with in-memory storage.

### Quiet hours + morning digest

When `QUIET_HOURS_ENABLED=true`, leads that arrive inside the quiet window are analyzed and drafted, but the response card is **not** posted to the owner. Instead the response sits in `status='pending_digest'`. At `DIGEST_TIME` (default 08:15), the digest loop posts a single summary message and promotes all pending responses back to `status='drafted'`.

### Healthcheck

The userbot is pinged via `client.get_me()` every `HEALTHCHECK_INTERVAL_SEC` (default 600s). After `HEALTHCHECK_FAILURE_THRESHOLD` consecutive failures (default 3) the owner gets a Telegram alert and the counter resets to avoid spam.

### Backup

`scripts/backup.py` dumps the SQLite DB to a timestamped `.sql.gz` in `/app/data/` and prunes anything older than 30 days. Schedule it from the **host** crontab — the container does not run cron itself.

```bash
sudo crontab -e
# Paste the line from deploy/crontab.example
```

### Tests

```bash
pytest                                                  # all unit + integration
pytest tests/integration/test_quiet_hours_flow.py -v    # verify quiet behavior
```

## Dashboard (Iteration 3)

Dashboard adds three containers managed by the same `docker-compose.yml`:

- `dashboard-api` — FastAPI + uvicorn on `:8000` (internal only).
- `dashboard-ui` — Next.js 16 on `:3000` (internal only).
- `caddy` — TLS-terminating reverse proxy on `:80` and `:443`.

### Local development

```bash
# 1. Backend
python -m leads_bot.dashboard.main         # uvicorn on :8000

# 2. Frontend
cd dashboard-ui
cp .env.local.example .env.local           # set DASHBOARD_API_BASE_URL=http://localhost:8000
npm install                                # if not done
npm run dev                                # Next.js on :3000
```

Open http://localhost:3000 — Basic auth uses `DASHBOARD_USER` / `DASHBOARD_PASSWORD` from `.env`.

### Production deploy

1. Set `DOMAIN=dashboard.<your-domain>` and `DASHBOARD_PASSWORD=...` in `/opt/leads-bot/.env`.
2. Point an A record for that subdomain at the VPS IP.
3. `docker compose pull && docker compose up -d --build dashboard-api dashboard-ui caddy`
4. Caddy auto-provisions a Let's Encrypt cert on first hit.
5. Browser to `https://dashboard.<your-domain>` → Basic auth prompt → done.

### Caveats

- `dashboard-api` MUST run with `workers=1` (SSE polling watermark per connection).
- SQLite uses WAL mode. Bot + dashboard share `./data/bot.db`. Dashboard writes are limited to `responses.notes`, `responses.client_status`, `sources.status`/`muted_until`, `data/profile.json`, `data/settings.json`.
- `Caddyfile` requires `flush_interval -1` on `/api/stream/*`; without it SSE is buffered and live updates break.
