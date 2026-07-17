"""Offline CLI for auditable biomedical entity normalization."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from code_engine.normalization.registry import LocalBiomedicalRegistry
from code_engine.normalization.resolver import ResolverCascade


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resolve one term through the auditable EntityResolutionHub.")
    parser.add_argument("--term", required=True)
    parser.add_argument("--expected-entity-type", help="Optional type hint for provider routing, e.g. biological_process or disease.")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--show-candidates", action="store_true")
    parser.add_argument("--json", action="store_true", help="Emit JSON; JSON is also the default machine-readable output.")
    parser.add_argument("--registry-path", help="Explicit curated anchor source; pilot fixtures are never loaded implicitly.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--entity-network-lookup", action="store_true")
    parser.add_argument("--entity-llm-proposer", action="store_true")
    parser.add_argument("--entity-resolution-policy")
    parser.add_argument("--run-dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry = LocalBiomedicalRegistry(Path(args.registry_path), allow_fallback=args.allow_fallback) if args.registry_path else None
    policy = json.loads(Path(args.entity_resolution_policy).read_text(encoding="utf-8")) if args.entity_resolution_policy and Path(args.entity_resolution_policy).exists() else None
    context = {"expected_entity_type": args.expected_entity_type} if args.expected_entity_type else None
    decision = ResolverCascade(registry, run_dir=args.run_dir, execute=args.execute, network_enabled=args.execute and args.network, api_enabled=args.execute and args.api, entity_network_lookup=args.entity_network_lookup, entity_llm_proposer=args.entity_llm_proposer, adjudicator_policy=policy).resolve_entity(args.term, context=context)
    payload = decision.model_dump()
    if not args.show_candidates:
        payload.pop("candidates", None)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
