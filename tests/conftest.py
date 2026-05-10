"""Shared pytest fixtures."""
import pytest


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """Reset the cached settings between tests."""
    from leads_bot import config
    config._settings = None
    yield
    config._settings = None
