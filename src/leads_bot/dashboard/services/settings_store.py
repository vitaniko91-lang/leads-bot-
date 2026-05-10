"""Read/write data/settings.json with atomic replace.

Falls back to bot's `Settings` defaults on read when file is absent.
"""
import json
import os
import tempfile
from pathlib import Path

from leads_bot.config import get_settings


def settings_path(data_dir: str) -> Path:
    return Path(data_dir) / "settings.json"


def read_settings(data_dir: str) -> dict:
    p = settings_path(data_dir)
    if p.exists():
        return json.loads(p.read_text())
    s = get_settings()
    return {
        "quiet_hours": s.quiet_hours,
        "min_budget_usd": s.min_budget_usd,
        "min_relevance_score": s.min_relevance_score,
        "max_responses_per_hour": s.max_responses_per_hour,
        "max_responses_per_day": s.max_responses_per_day,
        "max_responses_per_week": s.max_responses_per_week,
    }


def write_settings(data_dir: str, data: dict) -> None:
    p = settings_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="settings.", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
