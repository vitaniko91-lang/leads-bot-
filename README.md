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
