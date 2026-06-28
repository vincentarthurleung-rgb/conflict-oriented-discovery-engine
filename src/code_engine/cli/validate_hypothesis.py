"""Dry-run CLI for domain-adaptive hypothesis validation planning."""

import argparse
import json
from pathlib import Path

from code_engine.domain.router import default_domain_router
from code_engine.validation.registry import ValidatorRegistry
from code_engine.validation.router import DomainAdaptiveValidationRouter


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hypothesis-file", required=True)
    parser.add_argument("--domain", default="general_biomedical")
    parser.add_argument("--relation-type", default="unknown")
    parser.add_argument("--dry-run", action="store_true", default=True)
    args = parser.parse_args(argv)
    payload = json.loads(Path(args.hypothesis_file).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        hypotheses = (
            payload.get("hypotheses")
            or payload.get("ranked_hypotheses")
            or ([payload["hypothesis"]] if isinstance(payload.get("hypothesis"), dict) else None)
            or [payload]
        )
    else:
        hypotheses = payload
    profile = default_domain_router().resolve(args.domain)
    if profile is None:
        parser.error(f"Unknown domain: {args.domain}")
    registry = ValidatorRegistry().register_defaults()
    outputs = []
    for hypothesis in hypotheses:
        plan = DomainAdaptiveValidationRouter().create_plan(hypothesis, profile, relation_type=args.relation_type)
        previews = [registry.validate(name, plan.questions[0]).model_dump() for name in plan.selected_validators]
        outputs.append({"validation_plan": plan.model_dump(), "coverage_preview": previews, "external_calls_made": 0})
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
