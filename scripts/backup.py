"""Dump SQLite DB to a timestamped .sql.gz and prune old backups.

Usage (from host cron):
    docker exec leads-bot python /app/scripts/backup.py

Defaults work for the in-container layout:
    DB:      /app/data/bot.db
    OUT DIR: /app/data
    KEEP:    30 days
"""
from __future__ import annotations

import argparse
import gzip
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def dump_database(db_path: Path, out_dir: Path) -> Path:
    """Dump `db_path` to `out_dir/backup-YYYYMMDD.sql.gz`. Returns the path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    out = out_dir / f"backup-{stamp}.sql.gz"
    conn = sqlite3.connect(str(db_path))
    try:
        with gzip.open(out, "wt", encoding="utf-8") as gz:
            for line in conn.iterdump():
                gz.write(line + "\n")
    finally:
        conn.close()
    return out


def prune_old_backups(out_dir: Path, retention_days: int) -> int:
    """Delete backup-*.sql.gz files older than `retention_days`. Returns count."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    deleted = 0
    for p in out_dir.glob("backup-*.sql.gz"):
        mtime = datetime.utcfromtimestamp(p.stat().st_mtime)
        if mtime < cutoff:
            p.unlink()
            deleted += 1
    return deleted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup SQLite DB and prune old dumps.")
    ap.add_argument("--db", default="/app/data/bot.db", type=Path)
    ap.add_argument("--out", default="/app/data", type=Path)
    ap.add_argument("--keep-days", default=30, type=int)
    args = ap.parse_args(argv)

    if not args.db.exists():
        print(f"DB not found: {args.db}", file=sys.stderr)
        return 1

    out = dump_database(args.db, args.out)
    n = prune_old_backups(args.out, args.keep_days)
    size_kb = out.stat().st_size // 1024
    print(f"Backup written: {out} ({size_kb} KB), pruned {n} old files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
