"""Generate a validation plan from candidate hypotheses using deterministic rules."""

from __future__ import annotations

import argparse
import json
import os


INPUT_PATH = "data/processed/l4/hypothesis_search_results.json"
OUTPUT_PATH = "configs/generated/validation_plan.generated.json"


def classify_hypothesis(hypothesis: dict) -> str:
    relation = str(hypothesis.get("relation_family") or hypothesis.get("hypothesis_type") or "").casefold()
    if relation in {"gene_expression", "drug_gene_expression", "expression_direction"}:
        return "drug-gene expression"
    if "pathway" in relation:
        return "pathway"
    return "unknown"


def build_validation_plan(input_path: str = INPUT_PATH) -> dict:
    if not os.path.exists(input_path):
        return {"generation_mode": "no_hypotheses", "plan": []}
    with open(input_path, "r", encoding="utf-8") as handle:
        hypotheses = json.load(handle).get("hypotheses", [])
    plan = []
    for hyp in hypotheses:
        htype = classify_hypothesis(hyp)
        validators = ["NullValidator"]
        if htype == "drug-gene expression":
            validators = ["CuratedOmicsValidator", "LINCSValidator", "GEOValidator"]
        elif htype == "pathway":
            validators = ["ReactomeSkeleton", "NullValidator"]
        plan.append({"hypothesis_id": hyp.get("hypothesis_id"), "hypothesis_type": htype, "validators": validators})
    return {"generation_mode": "deterministic_rules", "plan": plan}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate validation plan from L4 hypotheses.")
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(build_validation_plan(args.input), handle, ensure_ascii=False, indent=2)
    print(f"[ValidationPlannerAgent] Wrote {args.output}")


if __name__ == "__main__":
    main()
