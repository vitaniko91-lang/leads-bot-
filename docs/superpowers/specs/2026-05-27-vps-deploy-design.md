# VPS Deploy — Bot as a System Service (design)

**Date:** 2026-05-27
**Context:** Бот сейчас работает на Mac в интерактивном терминале (PID-процесс умирает при закрытии терминала/сне ноута). Нужно перенести его на VPS так, чтобы он работал круглосуточно, независимо от Mac, и сам поднимался после ребута сервера.
**Scope:** Только сервис `bot`. Дашборд (dashboard-api / dashboard-ui / Caddy / домен / HTTPS) — вне объёма, отложено.

## Constraints

1. **Сессия Telethon эксклюзивна.** Один и тот же `leads_bot_session.session` нельзя использовать из двух мест одновременно — Telegram убивает ключ с `AuthKeyDuplicatedError`. Уже наступали на это (VPS-контейнер + Mac одновременно). Перенос файла сессии на другую машину допустим; одновременная работа — нет.
2. **Секреты и состояние не в git.** `.env`, `*.session`, `data/bot.db` — в `.gitignore`. `data/profile.json|sources.json|templates.json` — untracked (локальные). Всё это надо доставить на сервер вручную (scp), код — через git.
3. **15 реальных каналов живут только в `data/bot.db`.** Они добавлялись вживую через `add_dialog_sources.py` и отсутствуют в `sources.json` (там только 1 тестовый канал). Значит БД переносится как есть — пересев с json потеряет источники.
4. **У агента нет прямого доступа к серверу.** Деплой идёт по SSH, данные для подключения предоставляет владелец.

## Architecture

«Системный сервис» реализуется штатным механизмом репозитория — **Docker Compose**:

- Сервис `bot` в `docker-compose.yml` уже имеет `restart: always`.
- Docker daemon включается в автозапуск: `systemctl enable docker`.
- Итог: после `docker compose up -d bot` контейнер живёт постоянно и сам поднимается после перезагрузки сервера. Отдельный `systemd`-юнит не нужен (был бы дублированием поверх Docker restart-policy).

Контейнер `bot` собирается из `Dockerfile` (python:3.13-slim, uv), CMD = `alembic upgrade head && python -m leads_bot.main`. Тома монтируют `./data`, `./logs`, `./leads_bot_session.session` с хоста внутрь контейнера.

## Deploy flow

### Phase 0 — Mac (подготовка)
1. Запушить актуальный код в `origin/main` (2 коммита: test-isolation + discovery id-fix). Сервер берёт код из git.
2. **Остановить локального бота навсегда** (Ctrl+C в терминале / kill PID). С этого момента бот на Mac не запускается.

### Phase 1 — Server (provision)
3. Подключиться по SSH.
4. Проверить наличие Docker + compose-плагина; при отсутствии — установить (`get.docker.com` или пакетный менеджер дистрибутива).
5. `git clone` репозитория в рабочую папку (напр. `~/leads-bot`).

### Phase 2 — Transfer (scp Mac → server)
Доставить в папку репозитория на сервере файлы, которых нет в git:
- `.env`
- `leads_bot_session.session`
- `data/bot.db`
- `data/profile.json`, `data/sources.json`, `data/templates.json`

### Phase 3 — Launch
6. `systemctl enable docker` (автозапуск демона при загрузке).
7. `docker compose up -d --build bot` (поднимается только `bot`, без dashboard/caddy).

### Phase 4 — Verify
8. `docker compose logs -f bot` → дождаться `Bot is up. Listening …` и `Discovery scheduler started (tz=Europe/Kyiv)`.
9. Убедиться, что `AuthKeyDuplicatedError` НЕ появился (значит Mac-бот действительно погашен).
10. В Telegram отправить боту `/stats` → отвечает «Бот ▶ работает».
11. (Опц.) Проверить переживание ребута: `sudo reboot`, после старта `docker ps` показывает `leads-bot` снова `Up`.

## Verification criteria
- `docker ps`: контейнер `leads-bot` в статусе `Up` (healthy).
- В логах есть `Bot is up`, нет `AuthKeyDuplicatedError`.
- `/stats` в Telegram отвечает.
- После `reboot` контейнер поднимается сам.

## Rollback
Если бот на сервере не стартует:
1. `docker compose down` на сервере.
2. scp `leads_bot_session.session` обратно на Mac (или заново залогиниться на Mac, удалив session).
3. Запустить бота на Mac как раньше.
Состояние (`bot.db`) при этом не теряется — оно есть в обеих копиях; источник правды берём с того места, где бот работал последним.

## Open questions (нужны для исполнения)
- SSH: host/IP, пользователь, способ аутентификации (ключ).
- ОС и дистрибутив сервера (Ubuntu/Debian?) — влияет на команду установки Docker.
- Установлен ли уже Docker + compose-плагин.
- Ресурсы сервера (RAM): сборка образа python+uv требует ~1–2 ГБ; на маленьком инстансе лучше собрать образ заранее или увеличить swap.
- Часовой пояс самого сервера — на логику не влияет (бот читает `TIMEZONE` из `.env`), но удобнее `Europe/Kyiv` и для системного времени.
