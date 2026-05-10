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
    healthcheck_interval_sec: int = 600
    healthcheck_failure_threshold: int = 3

    # Rate-limit rotation (Iter 2): drop rate_limits rows older than this
    rate_limit_retention_hours: int = 168

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
