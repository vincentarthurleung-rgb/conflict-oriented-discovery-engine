"""Legacy CLI wrapper; prefer ``python -m code_engine.cli.query``."""

from code_engine.query.cli import *  # noqa: F401,F403
from code_engine.query.cli import main


if __name__ == "__main__":
    raise SystemExit(main())

