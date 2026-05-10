from leads_bot.config import Settings


def test_settings_loads_required_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123")
    monkeypatch.setenv("TELEGRAM_API_HASH", "abc")
    monkeypatch.setenv("TELEGRAM_PHONE", "+380501234567")
    monkeypatch.setenv("BOT_TOKEN", "bot:token")
    monkeypatch.setenv("OWNER_TG_ID", "111")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-x")

    s = Settings()

    assert s.telegram_api_id == 123
    assert s.telegram_phone == "+380501234567"
    assert s.min_budget_usd == 300
    assert s.max_responses_per_hour == 5
    assert s.send_delay_min == 30
    assert s.analyzer_model == "claude-haiku-4-5"


def test_settings_quiet_hours_parsed(monkeypatch):
    for k, v in [
        ("TELEGRAM_API_ID", "1"), ("TELEGRAM_API_HASH", "x"),
        ("TELEGRAM_PHONE", "+1"), ("BOT_TOKEN", "x"),
        ("OWNER_TG_ID", "1"), ("ANTHROPIC_API_KEY", "x"),
        ("QUIET_HOURS", "22:00-07:30"),
    ]:
        monkeypatch.setenv(k, v)

    s = Settings()
    assert s.quiet_hours_start == (22, 0)
    assert s.quiet_hours_end == (7, 30)
