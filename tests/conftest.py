"""Shared pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _isolate_env_file(monkeypatch):
    """Tests must be hermetic: never read the developer's local .env.

    Settings.model_config sets env_file=".env"; without this, a populated
    .env in the repo root leaks real values (e.g. MIN_BUDGET_USD=500) into
    tests that assert on code defaults. monkeypatch.setitem auto-restores.
    """
    from leads_bot.config import Settings
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """Reset the cached settings between tests."""
    from leads_bot import config
    config._settings = None
    yield
    config._settings = None
