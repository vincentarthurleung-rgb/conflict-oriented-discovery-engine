"""Legacy Stage0 PMC path forwarding to dynamic acquisition."""

import sys

from code_engine.cli.ingest import main


if __name__ == "__main__":
    raise SystemExit(main([*sys.argv[1:], "--source", "pmc"]))
