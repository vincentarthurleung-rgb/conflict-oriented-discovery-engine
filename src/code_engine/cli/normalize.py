"""Offline CLI for auditable biomedical entity normalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from code_engine.normalization.registry import DEFAULT_REGISTRY_PATH, LocalBiomedicalRegistry
from code_engine.normalization.resolver import ResolverCascade


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve one term using the local curated biomedical registry.")
    parser.add_argument("--term", required=True)
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--show-candidates", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON; JSON is also the default machine-readable output.")
    parser.add_argument("--registry-path", default=str(DEFAULT_REGISTRY_PATH))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = LocalBiomedicalRegistry(Path(args.registry_path), allow_fallback=args.allow_fallback)
    decision = ResolverCascade(registry).resolve_entity(args.term)
    payload = decision.model_dump()
    if not args.show_candidates:
        payload.pop("candidates", None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
