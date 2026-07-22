"""Build a projection-authoritative handoff and non-activating Atlas staging."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_engine.fulltext.projection_handoff import stage_projection_handoff


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fulltext-run", type=Path, required=True)
    parser.add_argument("--reentry-run", type=Path, required=True)
    parser.add_argument("--projection-run", type=Path, required=True)
    parser.add_argument("--base-abstract-run", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--staging-only", action="store_true", help="Required safety declaration; activation is never implemented here.")
    args = parser.parse_args(argv)
    if not args.staging_only:
        parser.error("--staging-only is required; this command never activates Atlas")
    result = stage_projection_handoff(
        fulltext_run=args.fulltext_run, reentry_run=args.reentry_run,
        projection_run=args.projection_run, base_abstract_run=args.base_abstract_run,
        output_root=args.output_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
