import gzip
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from scripts.backup import dump_database, prune_old_backups


def test_dump_database_creates_gzip(tmp_path: Path):
    db_path = tmp_path / "bot.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE x (a INTEGER)")
    conn.execute("INSERT INTO x VALUES (1)")
    conn.commit(); conn.close()

    out = dump_database(db_path, tmp_path)
    assert out.exists()
    assert out.suffix == ".gz"
    with gzip.open(out, "rt") as f:
        content = f.read()
    assert "CREATE TABLE" in content
    assert "INSERT INTO" in content


def test_dump_filename_includes_date(tmp_path: Path):
    db_path = tmp_path / "bot.db"
    sqlite3.connect(db_path).close()
    out = dump_database(db_path, tmp_path)
    today = datetime.utcnow().strftime("%Y%m%d")
    assert today in out.name
    assert out.name.startswith("backup-")
    assert out.name.endswith(".sql.gz")


def test_prune_removes_old_backups(tmp_path: Path):
    for d in [40, 35, 31, 25, 1]:
        f = tmp_path / f"backup-{(datetime.utcnow() - timedelta(days=d)).strftime('%Y%m%d')}.sql.gz"
        f.write_bytes(b"x")
        ts = (datetime.utcnow() - timedelta(days=d)).timestamp()
        os.utime(f, (ts, ts))

    n = prune_old_backups(tmp_path, retention_days=30)
    assert n == 3
    remaining = sorted(p.name for p in tmp_path.glob("backup-*.sql.gz"))
    assert len(remaining) == 2
