"""Critic agent that reports risks without changing scores."""

from __future__ import annotations

import argparse
import json
import os


INPUT_PATH = "data/processed/l6/L6_final_ranked_output.json"
OUTPUT_PATH = "reports/hypothesis_critic_report.md"


def critique(input_path: str = INPUT_PATH) -> str:
    if not os.path.exists(input_path):
        return "# Hypothesis Critic Report\n\nNo L6 ranked output found.\n"
    with open(input_path, "r", encoding="utf-8") as handle:
        ranked = json.load(handle).get("ranked_hypotheses", [])
    lines = ["# Hypothesis Critic Report", "", "Critic notes are advisory and do not alter scores.", ""]
    for item in ranked:
        risks = []
        if item.get("independent_labs_count", 2) <= 1:
            risks.append("possible single-lab driver")
        if item.get("validation_status") == "Unresolved_No_Coverage":
            risks.append("validation coverage is unresolved")
        if item.get("registry_anchor_gene") or item.get("omics_anchor_gene"):
            risks.append("anchor gene comes from curated registry mapping, not automatic gene resolution")
        status_blob = json.dumps(item).lower()
        if "verified_by_hardened" in status_blob or "full lincs" in status_blob:
            risks.append("legacy wording may overstate validation strength")
        if not item.get("separating_contexts"):
            risks.append("structured separating contexts are absent")
        lines.append(f"## {item.get('hypothesis_id', 'UNKNOWN')}")
        lines.append(f"- Seed pair: `{item.get('seed_pair', '')}`")
        lines.append(f"- Risks: {', '.join(risks) if risks else 'No high-priority critic flags.'}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate hypothesis critic report.")
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(critique(args.input))
    print(f"[HypothesisCriticAgent] Wrote {args.output}")


if __name__ == "__main__":
    main()
