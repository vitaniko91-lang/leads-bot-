# Telegram Leads Bot — Design Spec

**Date:** 2026-05-10
**Owner:** Vitalina Harkusha (@Vita_webdesigner)
**Status:** Draft → pending user review
**Implementation lead:** TBD

---

## 1. Цель

Автоматизировать поиск платящих клиентов на веб-дизайн через Telegram-каналы и чаты для фриланса.

Бот мониторит каналы 24/7, через Claude API анализирует посты на релевантность, генерирует персонализированные драфты откликов, и присылает их Vitalina на апрув. После одобрения отправляет от её имени с антибан-задержками.

**Метрика успеха:** ≥1 реальный платящий клиент через бота в первые 2 недели прода. ≥80% карточек лидов релевантны. 0 банов.

## 2. Профиль владельца (для фильтра и драфтов)

- **Услуги:** кастомный веб-дизайн, UI/UX, лендинги (НЕ Tilda/Webflow), мобильные приложения, брендинг, дизайн-системы. В Figma.
- **Минимальный бюджет:** $300
- **Языки клиентов:** RU, EN
- **Гео-констрейнт:** Vitalina из Украины. Российские клиенты исключены полностью (нет канала оплаты). Целевые регионы: UA, СНГ кроме РФ (Казахстан, Грузия, Армения и др.), EU, EN-global.
- **Способы оплаты:** Wise, Payoneer, crypto, IBAN EU, украинская карта.

## 3. Решения и обоснования

### 3.1 Уровень автономности — драфт + апрув

Бот готовит драфт ответа, шлёт владельцу с кнопками `[✅ Отправить] [✏️ Редактировать] [❌ Скип]`. После апрува отправляет от имени владельца.

**Why:** полная автоматизация рискует баном в фриланс-каналах за один неудачный авто-ответ → потеря источника лидов навсегда. Драфт-апрув даёт скорость без потери качества и тона.

### 3.2 Стек Telegram доступа — Telethon (userbot) + aiogram (bot API)

- **Telethon (userbot)** работает с аккаунта `@Vita_webdesigner` — читает каналы, отправляет отклики.
- **Aiogram (bot API)** — отдельный `@vita_leads_bot`, общается ТОЛЬКО с владельцем (карточки, кнопки).

**Why:** Bot API не может читать произвольные каналы. TDLib функционально эквивалентен Telethon, но сложнее в разработке. Telethon — стандарт для таких ботов.

### 3.3 LLM — Claude

- **Claude Haiku 4.5** для классификации лидов (быстро, дёшево, structured JSON output).
- **Claude Sonnet 4.6** для генерации драфтов откликов (качество письма).

### 3.4 Хостинг — VPS Hetzner CX22 (~€4/мес)

**Why:** userbot требует постоянного коннекта к Telegram. Локальный ноут не годится (выключение = потеря лидов). Cloud-функции усложняют persistent connection. VPS — стандартное решение.

### 3.5 Архитектура — модульный монолит

Один Python-процесс на asyncio, чётко разделённый на модули с явными интерфейсами. Один Docker-контейнер.

**Why:** микросервисы overkill для одного юзера. "Всё в одном файле" превращается в кашу через 2 недели. Модульный монолит — простой деплой + чёткие границы для тестирования и upgrade-пути.

### 3.6 Scope — расширенный (не MVP-only)

Финальная версия включает: дашборд, A/B шаблонов, авто-discovery каналов, mini-CRM. Релиз итерациями (4 итерации, 3-4 недели), чтобы первые лиды ловить уже через ~неделю.

## 4. Архитектура

```
                    ┌─────────────────────────┐
                    │   Telegram (твои чаты)  │
                    └─────────────────────────┘
                         ↑                ↓
                   Telethon (userbot, @Vita_webdesigner)
                         ↑                ↑
                    ┌─────────────────────────┐
   Anthropic API ←→ │   Бот (один процесс)    │ ←→ SQLite
                    │  ┌──────────────────┐   │
                    │  │ listener         │   │
                    │  │ analyzer         │   │
                    │  │ sender_drafter   │   │
                    │  │ notifier ────────┼──── Bot API ───→ владелец в личке
                    │  │ sender           │   │                (драфты + кнопки)
                    │  │ discovery        │   │
                    │  │ dashboard ───────┼──── HTTPS ──────→ браузер
                    │  └──────────────────┘   │                (Next.js dashboard)
                    └─────────────────────────┘
                              ↑
                         Docker Compose
                              ↑
                    VPS Hetzner CX22 (€4/мес)
```

## 5. Стек

- **Backend:** Python 3.12, asyncio
- **Telegram:** Telethon (userbot), aiogram (bot API)
- **LLM:** Anthropic SDK (claude-haiku-4-5 + claude-sonnet-4-6)
- **DB:** SQLAlchemy ORM + SQLite (миграция на Postgres при необходимости)
- **Web API:** FastAPI
- **Web UI:** Next.js 15 (App Router, RSC), TypeScript, Tailwind v4, кастомные компоненты, Recharts
- **Reverse proxy:** Caddy (auto Let's Encrypt)
- **Deploy:** Docker Compose на Hetzner Cloud CX22
- **Backup:** Hetzner Storage Box (~€3/мес)
- **Logging:** loguru (структурированный JSON, 7-day rolling)
- **Testing:** pytest + pytest-vcr (для Claude API mock)

## 6. Модули

### 6.1 `listener/`
- Подписан на `NewMessage` event Telethon во всех `sources` со статусом `active`.
- Pre-filter по ключевикам ("ищу дизайнера", "looking for designer", "нужен UI" и т.д.) — отсекает 95% мусора.
- Прошедшее → `analyzer.analyze(message)`.
- **Не знает про:** Claude, БД, отправку.

### 6.2 `analyzer/`
- Получает сообщение + контекст канала.
- Вызывает Claude Haiku 4.5 со structured output:
  ```json
  {
    "is_lead": bool,
    "project_type": "landing"|"app"|"branding"|"design_system"|"ui_ux"|"other",
    "budget_usd": number|null,
    "language": "ru"|"en",
    "client_country": "ua"|"by"|"kz"|"ge"|"eu"|"us"|"unclear"|"ru",
    "urgency": "low"|"med"|"high",
    "relevance_score": 0-100,
    "reasoning": "..."
  }
  ```
- **Hard reject если:** `client_country = "ru"`, или текст содержит RU-маркеры (Сбер, Тинькофф, ИП РФ, +7, "оплата на карту Сбера").
- **Pass если:** `is_lead && budget_usd >= 300 && relevance_score >= 60 && client_country != "ru"`.
- Все результаты (включая отказы) пишутся в `leads` таблицу.

### 6.3 `sender_drafter/`
- Получает лид + `profile.json` (имя, портфолио-ссылка, кейсы по тегам, тон, ставки).
- Выбирает шаблон из активных `templates` (учитывая A/B распределение).
- Вызывает Claude Sonnet 4.6, передаёт системный промпт шаблона + контекст лида.
- Драфт длиной 4-6 предложений, тон по `profile.style`.
- Передаёт в `notifier`.

### 6.4 `notifier/` (aiogram)
- Шлёт владельцу карточку лида в личку (формат — Раздел 9.1).
- Inline-кнопки: ✅ / ✏️ / ❌ / 🔇 mute канала на час.
- Обработка callback'ов:
  - ✅ → `sender.send(response_id)`
  - ✏️ → ждёт следующее сообщение от владельца, потом `[✅ Отправить эту версию] [↩ Назад к драфту]`
  - ❌ → `responses.status = "skipped"`
  - 🔇 → `sources.muted_until = now() + 1h`
- Quiet hours: 23:00-08:00 (UTC+8 / Бали). Ночью лиды копятся, утром — сводка.
- Если владелец не реагирует 2ч → push-напоминание. Если 24ч → `expired`.

### 6.5 `sender/` (Telethon)
- Отправляет одобренный текст в исходный чат или в личку автору поста (зависит от `sent_to` в карточке).
- **Антибан задержка:** случайные 30-90 сек после ✅, плюс `SetTyping` 2-5 сек.
- **Лимиты (hard cap):** 5/час, 30/день, 150/неделю откликов. 3/час личных сообщений новым контактам.
- При `FloodWaitError` — спать столько, сколько просит API. Если >10 мин → alert владельцу.
- Обработка ошибок: `failed_user_blocked`, `failed_chat_archived` — без ретрая.

### 6.6 `discovery/`
- Раз в неделю — поиск новых каналов по гео-таргетированным ключевикам (`design Ukraine`, `UI/UX вакансії`, `freelance designer Berlin`).
- **Blocklist:** ключевики с РФ-маркерами (`дизайнер Москва`, `ИП дизайн`).
- Результаты → `discovery_candidates` со статусом `pending`.
- Еженедельная сводка владельцу с inline-кнопками `[Add] [Reject]`.

### 6.7 `dashboard/`
- FastAPI backend — REST API + SSE для live-обновлений.
- Слушает `127.0.0.1`, наружу через Caddy + basic auth.
- Next.js frontend — страницы Overview, Leads, Sources, Templates, Profile, Settings.
- Подробности — Раздел 10.

### 6.8 `db/`
- SQLAlchemy ORM, SQLite файл `data/bot.db` (chmod 600).
- Миграции через Alembic.
- Подробности — Раздел 8.

## 7. Поток данных (lifecycle лида)

```
T+0      Пост в канале
T+0.1s   listener: pre-filter ключевиками
T+1.5s   analyzer: Claude Haiku → JSON-вердикт → запись в leads
T+1.6s   sender_drafter: Claude Sonnet → драфт
T+2s     notifier: карточка владельцу в @vita_leads_bot
T+30s    Владелец жмёт ✅ (или ✏️, или ❌)
T+30-90s sender: антибан задержка + typing
T+90s    Telethon отправляет от владельца
T+24h    Если клиент написал в личку владельца → бот предлагает пометить "in_dialog"
```

## 8. Схема БД (SQLAlchemy + SQLite)

### 8.1 `sources`
- `id` PK
- `tg_id` BIGINT UNIQUE
- `title` TEXT
- `type` TEXT: `channel` | `group`
- `language` TEXT
- `region` TEXT: `ua` | `cis_ex_ru` | `eu` | `en_global` *(валидация: не `ru`)*
- `status` TEXT: `active` | `paused` | `banned`
- `muted_until` TIMESTAMP NULL
- `added_at` TIMESTAMP
- `last_msg_at` TIMESTAMP

### 8.2 `leads`
- `id` PK
- `source_id` FK
- `tg_message_id` BIGINT
- `author_tg_id` BIGINT
- `author_username` TEXT
- `raw_text` TEXT
- `posted_at` TIMESTAMP
- `analyzed_at` TIMESTAMP
- `is_lead` BOOL
- `project_type` TEXT
- `budget_usd` INTEGER NULL
- `language` TEXT
- `client_country` TEXT
- `urgency` TEXT
- `relevance_score` INTEGER (0-100)
- `reasoning` TEXT
- `status` TEXT: `new` | `drafted` | `approved` | `sent` | `skipped` | `expired` | `filtered_out`
- UNIQUE(`source_id`, `tg_message_id`)

### 8.3 `responses`
- `id` PK
- `lead_id` FK
- `template_id` FK NULL
- `draft_text` TEXT
- `final_text` TEXT
- `status` TEXT: `drafted` | `approved` | `sent` | `failed` | `skipped`
- `sent_to` TEXT: `chat` | `dm`
- `sent_at` TIMESTAMP NULL
- `client_replied` BOOL DEFAULT false
- `client_status` TEXT: `replied` | `in_dialog` | `in_work` | `rejected` | `no_response`
- `notes` TEXT

### 8.4 `templates`
- `id` PK
- `name` TEXT
- `prompt` TEXT
- `variant` TEXT: `A` | `B` | `control`
- `active` BOOL
- `traffic_share` INTEGER (0-100, сумма активных = 100)
- `sent_count` INTEGER DEFAULT 0
- `reply_count` INTEGER DEFAULT 0

### 8.5 `discovery_candidates`
- `id` PK
- `tg_id` BIGINT
- `title` TEXT
- `description` TEXT
- `member_count` INTEGER
- `language` TEXT
- `predicted_region` TEXT
- `discovered_at` TIMESTAMP
- `status` TEXT: `pending` | `approved` | `rejected`

### 8.6 `rate_limits`
- `id` PK
- `window` TEXT: `hour` | `day` | `week`
- `window_start` TIMESTAMP
- `sent_count` INTEGER

### 8.7 Индексы
- `leads(status, posted_at)`
- `responses(status, sent_at)`
- `sources(status)`

### 8.8 Backup
- Раз в день `sqlite3 .backup` → загрузка в Hetzner Storage Box.
- Хранение: 30 дней rolling.

## 9. Telegram UX (диалог с владельцем)

### 9.1 Карточка лида

```
🎯 Лид #128 · score 85
━━━━━━━━━━━━━━━━━━━━━━
📍 Design Jobs UA · 2 мин назад
💰 ~$1000 · 🌐 RU · 🇺🇦 UA · ⏰ medium
📋 landing + design system

▎ОРИГИНАЛ
Ищу дизайнера на лендинг для криптостартапа.
Бюджет 800-1200$, нужен Figma + дизайн-система.
Писать в ЛС @ivanov

[🔗 Открыть оригинал]

▎ДРАФТ ОТВЕТА
Привет! Видела ваш пост про лендинг для крипто-
стартапа. У меня есть 2 свежих кейса с дизайн-
системами для финтеха — могу скинуть. Ставлю
Figma + интерактивный прототип. Готова обсудить
созвон. Портфолио: vitalina.design

📤 Отправлено будет в: личку @ivanov
🤖 Шаблон: «Дружеский + портфолио» (A)

[ ✅ Отправить ] [ ✏️ Редактировать ]
[ ❌ Скип ]      [ 🔇 Молчать в канале час ]
```

Если `client_country = "unclear"` → дополнительно `⚠️ Страна не ясна — уточни в первом сообщении`.

### 9.2 Команды

- `/stats` — за сегодня: лидов, отправлено, ответов
- `/pause` / `/resume` — глобальная пауза
- `/sources` — список каналов
- `/sources add <link>` — добавить
- `/sources pause <id>` — заморозить
- `/profile` — посмотреть/обновить
- `/templates` — список с метриками
- `/draft <lead_id> retry` — перегенерить
- `/quiet 22:00-09:00` — настроить тишину

### 9.3 Утренняя сводка

```
🌅 Доброе утро. За ночь: 7 лидов
• #145 score 92 — Senior UX, $3000
• #144 score 78 — landing, $500
• #143 ...
[Смотреть все →]
```

### 9.4 Тон бота

Минималистичный, без эмодзи-спама и пресмыкательств. Никаких "Отличный лид!" / "Готов помочь!". Только факты.

## 10. Web Dashboard

**URL:** `dashboard.vita-leads.app` (поддомен), HTTPS via Caddy + Let's Encrypt, basic auth.

**Стек:** Next.js 15 (App Router, RSC) + TypeScript + Tailwind v4 + кастомные компоненты + Recharts.

**Стиль:** dark mode по умолчанию (`#0a0a0a` + accent `#4ade80`). Frontend Design Skill активен — никакого generic AI-look.

### 10.1 Страницы

1. **`/` Overview** — KPI-карточки (лидов, отправлено, ответов, конверсия), lead flow гистограмма по часам, топ каналов по конверсии.
2. **`/leads`** — таблица с фильтрами (status, source, score, date, language, region), drawer с деталями.
3. **`/leads/[id]`** — детальная страница лида: оригинал, анализ Claude, шаблон, драфт, отправленный текст, timeline, мини-CRM.
4. **`/sources`** — управление каналами + pending discovery candidates.
5. **`/templates`** — A/B шаблонов с метриками, редактор промпта, слайдер распределения.
6. **`/profile`** — имя, ссылки, ставка, стиль, кейсы (для драфтов).
7. **`/settings`** — quiet hours, лимиты, мин. score, ключи (маскированные), backup.

### 10.2 Real-time

SSE (Server-Sent Events) для live-обновлений `/leads`. WebSocket не нужен (односторонняя раздача).

## 11. Антибан и безопасность

### 11.1 Защита Telegram-аккаунта

- Случайные задержки между действиями (30-180 сек на отправку).
- `SetTyping` 2-5 сек перед отправкой длинных сообщений.
- Hard limits: **5 откликов/час, 30/день, 150/неделю**. **3 ЛС новым контактам/час**.
- Если за час >50 лидов — анализируем все, шлём драфты только на топ-10 по score.
- НЕ использовать основной номер `+84 36 2892 731`. Завести **отдельный SIM** (виртуальный $5 или второй UA-номер).
- 2FA на Telegram-аккаунте обязательно.
- Сессия Telethon только на VPS, encrypted at rest.

### 11.2 Health monitoring

- Каждые 10 мин — `GetMe` ping. При разрыве — реконнект с exp backoff.
- Каждый час — статистика в БД.
- 3 провала health-check подряд → alert владельцу.

### 11.3 Error handling по слоям

| Слой | Ошибка | Действие |
|---|---|---|
| listener | Disconnect, FloodWait | reconnect + backoff |
| analyzer | Claude timeout/429 | retry 3× exp backoff → mark `analysis_failed` |
| sender_drafter | Claude error | то же |
| notifier | Bot API down | очередь, отправка пачкой при восстановлении |
| sender | User blocked, chat archived | mark `failed_*`, без ретрая |
| db | SQLite locked | retry 5× с jitter → alert |
| dashboard | FastAPI crashed | Caddy 502, Docker restart |

### 11.4 Безопасность

- Секреты в `.env` (не коммитим), на VPS — `age`/`sops` шифрование.
- В дашборде ключи маскируются (`sk-ant-...***...xyz`).
- FastAPI слушает `127.0.0.1`, наружу через Caddy.
- SQLite файл `chmod 600`, owner = Docker user.
- Логи: hash + первые 50 символов сообщений (без PII клиентов в plaintext).

### 11.5 Disaster recovery (если бан случится)

1. Бэкап SQLite сохранён.
2. Новый Telegram аккаунт (новый SIM).
3. Подписка на каналы из `sources`.
4. Замена `TELEGRAM_*` в `.env`, рестарт контейнера.
5. Бот продолжает с того же места.

## 12. Тестирование

### 12.1 Unit-тесты (pytest)

- `analyzer.parse_claude_response` — JSON parsing edge cases.
- `analyzer.geo_filter` — корректно отсекает RU маркеры.
- `sender.rate_limiter` — лимиты соблюдаются, задержки в диапазоне.
- `notifier.format_lead_card` — длина < 4096 символов.
- `sender_drafter.build_prompt` — корректный контекст.
- `db` — миграции, дедуп `(source_id, tg_message_id)`.

### 12.2 Integration-тесты

- Полный pipeline на fixture-сообщениях, mock Telethon/aiogram.
- Claude API через `pytest-vcr` (replay записанных ответов).
- Geo-filter: 30 fixture-постов (10 RU / 10 UA / 10 EU) → корректная классификация.

### 12.3 E2E (вручную, чеклист)

- Запуск локально с тестовым каналом.
- Полный путь: пост → драфт → ✅ → отправка в test-аккаунт.
- ✏️, ❌, 🔇 mute.
- Дашборд: новый лид появляется в `/leads` без рефреша (SSE).

### 12.4 Не тестируем

- Telegram API (не наш код).
- UI компоненты дашборда детально (Playwright скриншоты).
- Discovery (внешний поиск, ручная проверка).

## 13. План релиза (4 итерации, 3-4 недели)

### Итерация 1 — MVP (1 неделя)
listener + analyzer + notifier + sender + БД (sources/leads/responses) + Telethon ✅/✏️/❌ + Geo-filter + 3-5 каналов вручную в `sources.json` + Docker на VPS.

**Done when:** ловит первых живых лидов, владелец понимает точность фильтра.

### Итерация 2 — Стабилизация и UX (3-5 дней)
Quiet hours + утренние сводки + полный набор команд + sources как таблица + `profile.json` подгружается + healthchecks + backup + все anti-ban механизмы.

**Done when:** бот работает 24/7 без внимания владельца.

### Итерация 3 — Дашборд (1 неделя)
Next.js + кастомные компоненты + страницы Overview/Leads/Sources/Profile/Settings + SSE + FastAPI + Caddy + HTTPS + Recharts + mini-CRM.

**Done when:** владелец видит полную картину.

### Итерация 4 — Smart features (5-7 дней)
A/B шаблонов + auto-discovery каналов + анализ горячих часов + auto-detection ответов клиентов.

**Done when:** все фичи расширенного варианта на месте.

## 14. Критерии успеха (после 2 недель в проде)

- ≥80% лидов в карточке релевантные.
- 0 ложных срабатываний на RU-клиентов.
- 0 банов аккаунта.
- ≥1 реальный платящий клиент пришёл через бота.

## 15. Открытые вопросы (на момент implementation)

- **Стартовый список каналов** — Vitalina скинет 3-5, остальные подберём через discovery.
- **Anthropic API key** — завести в первый день implementation на console.anthropic.com.
- **Отдельный SIM** для Telegram-аккаунта — закупить до Итерации 1.
- **Доменное имя** для дашборда — выбрать (по умолчанию `vita-leads.app`).
- **Профиль (`profile.json`)** — собрать кейсы Vitalina, тон, ставки до Итерации 2.
