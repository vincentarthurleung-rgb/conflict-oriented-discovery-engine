"""Check Atlas database health and migration state."""
from __future__ import annotations

import argparse
import json

from code_engine.system_b.persistence.database import create_atlas_engine, database_url, sqlite_health


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args(argv)
    engine = create_atlas_engine(database_url(args.database_url))
    health = sqlite_health(engine)
    print(json.dumps(health, indent=2, ensure_ascii=False))
    return 0 if health["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
