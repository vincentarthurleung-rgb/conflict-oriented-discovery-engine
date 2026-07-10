"""Run Atlas database migrations."""
from __future__ import annotations

import argparse
import os

from alembic import command
from alembic.config import Config

from code_engine.system_b.persistence.database import database_url, protect_database_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--revision", default="head")
    args = parser.parse_args(argv)
    url = database_url(args.database_url)
    os.environ["ATLAS_DATABASE_URL"] = url
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, args.revision)
    protect_database_file(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
