"""Read/write data/profile.json with atomic replace."""
import json
import os
import tempfile
from pathlib import Path


def profile_path(data_dir: str) -> Path:
    return Path(data_dir) / "profile.json"


def read_profile(data_dir: str) -> dict | None:
    p = profile_path(data_dir)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def write_profile(data_dir: str, data: dict) -> None:
    p = profile_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="profile.", suffix=".json", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
