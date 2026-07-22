"""Recover paid Fulltext L1 v2 raw responses without API or network access."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.fulltext_l1_v2 import recover_fulltext_l1_v2_offline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--max-tokens", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = recover_fulltext_l1_v2_offline(args.run_dir, max_tokens=args.max_tokens)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
