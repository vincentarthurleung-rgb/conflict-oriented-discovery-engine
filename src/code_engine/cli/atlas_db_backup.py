"""Create an online-consistent SQLite backup for Atlas."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from code_engine.system_b.persistence.database import database_url, sqlite_path_from_url


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--output-dir", default="data/backups")
    args = parser.parse_args(argv)
    url = database_url(args.database_url)
    source_path = sqlite_path_from_url(url)
    if not source_path or not source_path.exists():
        raise FileNotFoundError("SQLite database file not found")
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = out / f"code_atlas_{stamp}.db"
    with sqlite3.connect(source_path) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    manifest = {"backup_path": str(backup), "source_path": str(source_path), "created_at": stamp, "sha256": digest}
    (backup.with_suffix(".json")).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
