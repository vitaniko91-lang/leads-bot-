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
