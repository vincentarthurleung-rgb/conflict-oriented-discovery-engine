"""Offline config, manifest, and payload audit entrypoint."""

import argparse
from typing import Sequence

from code_engine.config.loader import load_json_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run local C.O.D.E. validation audits. Manifest and payload audits "
            "are legacy compatibility operations."
        )
    )
    parser.add_argument("--config")
    parser.add_argument("--config-type", choices=("l2_l3_ontology_rules", "context_axis_map", "domain_spec", "validation_plan", "entity_registry"))
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--payloads", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.config:
        if not args.config_type:
            raise SystemExit("--config-type is required with --config")
        load_json_config(args.config, config_type=args.config_type)
        print(f"Config valid: {args.config}")
        return 0
    if args.manifest or args.payloads:
        # Legacy compatibility only. Not used by the main System A workflow.
        from src.pipelines.manifest_validation import (
            PAYLOAD_DIR,
            validate_manifest,
            validate_payload_dir,
            write_validation_audits,
        )

        manifest_audit = validate_manifest(strict=args.strict)
        payload_audit = validate_payload_dir(PAYLOAD_DIR, strict=args.strict)
        write_validation_audits(manifest_audit, payload_audit)
        print("Local artifact audit complete.")
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
