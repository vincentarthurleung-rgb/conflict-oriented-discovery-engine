"""CLI for zero-call rehydration of the frozen Prompt-v6 smoke responses."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from code_engine.fulltext.fulltext_l1_v3_offline_rehydrate import offline_rehydrate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(offline_rehydrate(args.run_dir), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
