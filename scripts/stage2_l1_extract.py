"""Legacy Stage2 command forwarding to :mod:`code_engine.cli.extract`."""

from code_engine.cli.extract import main


if __name__ == "__main__":
    raise SystemExit(main())
