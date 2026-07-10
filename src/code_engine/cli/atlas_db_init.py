"""Initialize and migrate the Atlas SQLite database."""
from __future__ import annotations

import argparse
import os

from alembic import command
from alembic.config import Config

from code_engine.system_b.persistence.database import create_atlas_engine, database_url, protect_database_file, sqlite_health


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    url = database_url(args.database_url)
    os.environ["ATLAS_DATABASE_URL"] = url
    command.upgrade(_config(url), "head")
    protect_database_file(url)
    engine = create_atlas_engine(url)
    print(sqlite_health(engine))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
