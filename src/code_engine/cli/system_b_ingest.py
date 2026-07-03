"""CLI for offline System B case-bundle ingestion."""

from __future__ import annotations

import argparse

from code_engine.system_b import BundleSchemaValidator, CaseBundleLoader, CaseCardBuilder, LimitationReporter, QualityClassifier, ReportExporter


def ingest(case_bundle: str, output_root: str, case_label: str | None = None) -> tuple[dict, dict]:
    bundle = CaseBundleLoader(case_bundle).load()
    validation = BundleSchemaValidator().validate(bundle)
    card = CaseCardBuilder().build(bundle)
    quality = QualityClassifier().classify(bundle, validation)
    limitations = LimitationReporter().generate(bundle, card)
    ReportExporter().export(output_root, card, quality, validation, limitations, case_label)
    return card, quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest an exported case bundle into System B")
    parser.add_argument("--case-bundle", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--case-label")
    args = parser.parse_args()
    card, quality = ingest(args.case_bundle, args.output_root, args.case_label)
    passed = quality["quality_class"] != "CASE_NOT_READY"
    print("SYSTEM_B_INGEST_PASS" if passed else "SYSTEM_B_INGEST_FAIL")
    print(f"case_id = {card['case_id']}")
    print(f"quality_class = {quality['quality_class']}")
    print(f"comparison_readiness = {quality['comparison_readiness']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
