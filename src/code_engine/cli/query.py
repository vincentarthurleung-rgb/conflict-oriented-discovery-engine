"""Run the offline query-driven discovery interface."""

from typing import Sequence

from code_engine.query.cli import main as query_main


def main(argv: Sequence[str] | None = None) -> int:
    return query_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())

