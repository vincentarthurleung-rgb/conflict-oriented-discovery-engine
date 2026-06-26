"""Domain bootstrap agent.

This deterministic template agent writes a domain_spec config. It does not make
scientific truth claims and can run without an API key.
"""

from __future__ import annotations

import argparse
import json
import os
import time


OUTPUT_PATH = "config/schemas/domain_spec.json"


def build_domain_spec(topic: str) -> dict:
    topic_lower = topic.lower()
    core = ["KETAMINE", "ANTIDEPRESSANT RESPONSE", "GLUTAMATE", "NMDA", "AMPA", "MTOR", "BDNF"]
    if "ketamine" not in topic_lower:
        core = [topic.upper()]
    return {
        "domain_name": topic,
        "generation_mode": "template_fallback",
        "generated_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "core_entities": core,
        "relation_vocabulary": ["activates", "inhibits", "increases", "decreases", "promotes", "suppresses"],
        "context_axes": ["treatment_duration", "oxygen_condition", "species", "cell_type", "brain_region", "dose"],
        "suggested_search_queries": [topic, f"{topic} mechanism", f"{topic} validation"],
        "validation_resources": ["curated_omics_index", "LINCS", "GEO", "DrugBank", "ChEMBL"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate domain_spec.json from a topic.")
    parser.add_argument("topic", nargs="?", default="Ketamine antidepressant response")
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(build_domain_spec(args.topic), handle, ensure_ascii=False, indent=2)
    print(f"[DomainBootstrapAgent] Wrote {args.output}")


if __name__ == "__main__":
    main()
