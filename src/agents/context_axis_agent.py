"""Aggregate mined context mentions into a generated axis map."""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict


INPUT_PATH = "data/processed/l4/context_mentions.json"
OUTPUT_PATH = "config/schemas/context_axis_map.generated.json"


def generate_axis_map(input_path: str = INPUT_PATH) -> dict:
    if not os.path.exists(input_path):
        return {"generation_mode": "no_context_mentions", "axes": {}}
    with open(input_path, "r", encoding="utf-8") as handle:
        mentions = json.load(handle).get("context_mentions", [])
    axes = defaultdict(lambda: defaultdict(set))
    for mention in mentions:
        axes[mention["axis"]][mention["value"]].add(mention["span"])
    return {
        "generation_mode": "deterministic_grouping",
        "axes": {axis: {value: sorted(spans) for value, spans in values.items()} for axis, values in axes.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate context axis map from context mentions.")
    parser.add_argument("--input", default=INPUT_PATH)
    parser.add_argument("--output", default=OUTPUT_PATH)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(generate_axis_map(args.input), handle, ensure_ascii=False, indent=2)
    print(f"[ContextAxisAgent] Wrote {args.output}")


if __name__ == "__main__":
    main()
