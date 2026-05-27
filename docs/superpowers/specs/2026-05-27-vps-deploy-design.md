# VPS Deploy — Bot as a systemd Service (design)

**Date:** 2026-05-27
**Context:** Бот сейчас работает на Mac в интерактивном терминале (умирает при закрытии терминала/сне ноута). Нужно перенести его на VPS так, чтобы он работал круглосуточно, независимо от Mac, и сам поднимался после ребута сервера.
**Scope:** Только процесс бота (`python -m leads_bot.main`). Дашборд / Caddy / домен / HTTPS — вне объёма.

## Target server (осмотрено по SSH 2026-05-27)

- IP `206.189.230.129`, hostname `for-bot`, root-доступ по SSH-ключу с Mac (passwordless — агент ходит напрямую).
- Ubuntu 24.04.3 LTS, x86_64.
- **RAM 458 МБ, swap нет** — крошечный дроплет (DO 512MB). Диск 8.7 ГБ (свободно 6.8).
- Docker НЕ установлен. git установлен. Машина чистая (создана сегодня) — отключать нечего.

## Approach: native systemd (не Docker)

На 458 МБ Docker неудачен: демон ест 50–100 МБ, сборка образа (`uv pip install`) почти наверняка упадёт по OOM. Поэтому — **нативный запуск через systemd**:

- Легче (нет демона Docker, нет сборки образа → нет OOM на билде).
- Буквально «системный сервис»: `systemd` unit с `Restart=always`, `enable` при загрузке.
- Минус: расходится с `docker-compose.yml` в репо (он остаётся для будущего деплоя на большую машину).

**+1 ГБ swap** добавляем обязательно: `uv sync` на 458 МБ может упереться в память, плюс запас рантайму.

## Constraints

1. **Сессия Telethon эксклюзивна.** `leads_bot_session.session` нельзя использовать из двух мест одновременно (`AuthKeyDuplicatedError`). Перенос файла допустим; одновременная работа — нет. Порядок: сначала стоп Mac-бота → потом старт на сервере.
2. **Секреты и состояние не в git.** `.env`, `*.session`, `data/bot.db` — в `.gitignore`; `data/profile.json|sources.json|templates.json` — untracked. Всё доставляется на сервер через scp, код — через git.
3. **15 реальных каналов живут только в `data/bot.db`** (добавлены вживую, в `sources.json` их нет). БД переносится как есть.

## Deploy flow

### Phase 0 — Mac
1. Запушить актуальный код в `origin/main` (4 коммита: test-isolation, discovery id-fix, deploy spec, + обновление спеки).
2. Подготовить файлы для переноса (они уже на месте локально).

### Phase 1 — Server: окружение
3. Добавить swap 1 ГБ (`fallocate /swapfile`, `mkswap`, `swapon`, запись в `/etc/fstab`).
4. Поставить uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`), убедиться, что есть Python 3.13 (uv поставит при необходимости).
5. `git clone` репозитория в `/opt/leads-bot`.
6. `uv sync` (создать venv с зависимостями).

### Phase 2 — Transfer (scp Mac → server, в `/opt/leads-bot`)
- `.env`
- `leads_bot_session.session`
- `data/bot.db`
- `data/profile.json`, `data/sources.json`, `data/templates.json`

### Phase 3 — Service
7. `uv run alembic upgrade head` (на перенесённой БД — no-op, уже на head).
8. Создать `/etc/systemd/system/leads-bot.service`:
   - `WorkingDirectory=/opt/leads-bot`
   - `ExecStart=<uv path> run python -m leads_bot.main`
   - `Restart=always`, `RestartSec=5`
   - `After=network-online.target`, `Wants=network-online.target`
   - окружение часового пояса опц. (`TIMEZONE` всё равно берётся из `.env`)
9. **Остановить бота на Mac** (стоп процесса / Ctrl+C). С этого момента Mac-бот не запускается.
10. `systemctl daemon-reload && systemctl enable --now leads-bot`.

### Phase 4 — Verify
11. `journalctl -u leads-bot -f` → дождаться `Bot is up. Listening …` + `Discovery scheduler started (tz=Europe/Kyiv)`.
12. Убедиться, что `AuthKeyDuplicatedError` НЕ появился (Mac-бот точно погашен).
13. В Telegram `/stats` → «Бот ▶ работает».
14. Проверить переживание ребута: `reboot`, после старта `systemctl status leads-bot` → `active (running)`.

## Verification criteria
- `systemctl is-active leads-bot` → `active`.
- В `journalctl` есть `Bot is up`, нет `AuthKeyDuplicatedError`.
- `/stats` в Telegram отвечает.
- После `reboot` сервис поднимается сам.

## Rollback
Если на сервере не стартует:
1. `systemctl disable --now leads-bot` на сервере.
2. scp `leads_bot_session.session` обратно на Mac (или заново залогиниться на Mac, удалив session).
3. Запустить бота на Mac как раньше. `bot.db` есть в обеих копиях — источник правды берём с последней рабочей машины.

## Open questions / risks
- **RAM 458 МБ** — даже нативно тесновато; swap обязателен. Если бот будет OOM-иться под нагрузкой — апгрейд дроплета до 1 ГБ.
- Часовой пояс системного времени сервера — на логику не влияет (`TIMEZONE` из `.env`), но удобнее выставить `Europe/Kyiv`.
- uv ставит свой Python 3.13 — проверить, что сборка `uv sync` укладывается в RAM+swap.
