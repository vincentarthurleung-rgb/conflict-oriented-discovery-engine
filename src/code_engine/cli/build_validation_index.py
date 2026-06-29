"""Build a bounded, schema-bound local validation index."""

from __future__ import annotations

import argparse

from code_engine.validation.index_builders.chembl_builder import ChEMBLIndexBuilder
from code_engine.validation.index_builders.clinical_trials_builder import ClinicalTrialsIndexBuilder
from code_engine.validation.index_builders.curated_omics_builder import CuratedOmicsIndexBuilder
from code_engine.validation.index_builders.depmap_builder import DepMapIndexBuilder
from code_engine.validation.index_builders.lincs_builder import LINCSIndexBuilder
from code_engine.validation.index_builders.opentargets_builder import OpenTargetsIndexBuilder
from code_engine.validation.index_builders.reactome_builder import ReactomeIndexBuilder


BUILDERS = {
    "curated_omics": CuratedOmicsIndexBuilder, "reactome": ReactomeIndexBuilder,
    "chembl": ChEMBLIndexBuilder, "depmap": DepMapIndexBuilder,
    "lincs": LINCSIndexBuilder, "clinical_trials": ClinicalTrialsIndexBuilder,
    "opentargets": OpenTargetsIndexBuilder,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a local validation index from a bounded source fixture")
    parser.add_argument("--validator", choices=sorted(BUILDERS), required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--source-database-version")
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-large-source", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = BUILDERS[args.validator]().build_from_source(
        args.source, args.output_dir, source_database_version=args.source_database_version,
        max_records=args.max_records, dry_run=args.dry_run,
        allow_large_source=args.allow_large_source,
    )
    print(result.model_dump_json(indent=2))
    return 1 if result.status == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
