"""Reparse the saved paid smoke responses without provider or network access."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.fulltext_l1_v2_draft_reparse import reparse_smoke_responses_offline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline Draft-to-Formal reparse of saved Fulltext L1 v2 smoke responses.")
    parser.add_argument("--run-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = reparse_smoke_responses_offline(args.run_dir)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
