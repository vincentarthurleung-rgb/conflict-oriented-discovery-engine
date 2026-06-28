"""Rule-based context mining for C.O.D.E. v4.0.

This layer converts L1.5 refined tuples into span-grounded ContextMention
records. It is deterministic and rejects spans that cannot be located in the
source evidence sentence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from typing import Any, Dict, List, Tuple

from code_engine.config.loader import load_json_config
from code_engine.schemas import ContextMention


L1_5_INPUT_DIR = "./data/processed/l1_5_refined"
CONTEXT_AXIS_MAP_PATH = "configs/normalization/context_axis_map.json"
CONTEXT_MENTIONS_PATH = "data/processed/l4/context_mentions.json"
CONTEXT_AUDIT_PATH = "reports/context_mining_audit.md"


DEFAULT_AXIS_MAP = {
    "treatment_duration": {
        "acute": ["acute", "acutely", "short-term", "24 h", "24 hours"],
        "chronic": ["chronic", "chronically", "long-term", "weeks", "repeated"],
    },
    "oxygen_condition": {
        "hypoxia": ["hypoxia", "hypoxic", "oxygen deprivation"],
        "normoxia": ["normoxia", "normoxic"],
    },
    "species": {
        "mouse": ["mouse", "mice", "murine"],
        "rat": ["rat", "rats"],
        "human": ["human", "humans", "patient", "patients", "subjects"],
    },
    "cell_type": {
        "neuron": ["neuron", "neurons", "neuronal", "primary neuron"],
        "astrocyte": ["astrocyte", "astrocytes"],
        "microglia": ["microglia", "microglial"],
        "pc12": ["PC12"],
    },
    "brain_region": {
        "pfc": ["PFC", "prefrontal cortex", "prefrontal cortical"],
        "hippocampus": ["hippocampus", "hippocampal"],
    },
    "dose": {
        "low_dose": ["low dose", "subanesthetic", "subanaesthetic"],
        "high_dose": ["high dose", "anesthetic", "anaesthetic"],
    },
}


def load_axis_map(path: str = CONTEXT_AXIS_MAP_PATH) -> Dict[str, Dict[str, List[str]]]:
    if not os.path.exists(path):
        return DEFAULT_AXIS_MAP
    payload, _ = load_json_config(
        path,
        config_type="context_axis_map",
        allow_fallback=False,
        strict_config=True,
        fallback_data={"axes": DEFAULT_AXIS_MAP},
        required_modules=["context_mining"],
    )
    return payload.get("axes", DEFAULT_AXIS_MAP)


def _stable_id(*parts: Any) -> str:
    return hashlib.md5("_".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:12]


def _find_span(sentence: str, phrase: str) -> Tuple[str, bool]:
    pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    match = pattern.search(sentence or "")
    if not match:
        return "", False
    return sentence[match.start() : match.end()], True


def mine_context_mentions(
    input_dir: str = L1_5_INPUT_DIR,
    axis_map_path: str = CONTEXT_AXIS_MAP_PATH,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    axis_map = load_axis_map(axis_map_path)
    mentions: List[ContextMention] = []
    rejected = 0

    for fname in sorted(os.listdir(input_dir)):
        if not fname.endswith("_refined.json"):
            continue
        with open(os.path.join(input_dir, fname), "r", encoding="utf-8") as handle:
            l1_data = json.load(handle)
        paper_id = l1_data.get("asset_id", fname.replace("_refined.json", ""))

        for chunk in l1_data.get("chunks_extracted", []):
            chunk_id = str(chunk.get("chunk_index", "unknown"))
            for sample_idx, sample in enumerate(chunk.get("raw_samples", [])):
                for node_idx, node in enumerate(sample.get("causal_tuples", [])):
                    sentence = str(node.get("evidence_sentence", ""))
                    triple_id = _stable_id(paper_id, chunk_id, sample_idx, node_idx, sentence)
                    seen = set()

                    for axis, value_map in axis_map.items():
                        for value, phrases in value_map.items():
                            for phrase in phrases:
                                span, ok = _find_span(sentence, phrase)
                                if not ok:
                                    continue
                                key = (triple_id, axis, value, span.lower())
                                if key in seen:
                                    continue
                                seen.add(key)
                                mentions.append(
                                    ContextMention(
                                        context_id=_stable_id(*key),
                                        paper_id=paper_id,
                                        triple_id=triple_id,
                                        axis=axis,
                                        value=value,
                                        span=span,
                                        source_sentence=sentence,
                                        extraction_mode="rule_span",
                                        confidence=0.95,
                                    )
                                )

                    for axis, raw_value in node.get("context", {}).items():
                        clean = str(raw_value or "").strip()
                        if not clean or clean.lower() == "unspecified":
                            continue
                        span, ok = _find_span(sentence, clean)
                        if not ok:
                            rejected += 1
                            continue
                        mentions.append(
                            ContextMention(
                                context_id=_stable_id(triple_id, axis, clean, span.lower()),
                                paper_id=paper_id,
                                triple_id=triple_id,
                                axis=axis,
                                value=clean.lower(),
                                span=span,
                                source_sentence=sentence,
                                extraction_mode="l1_5_context_span",
                                confidence=0.8,
                            )
                        )

    audit = {
        "generated_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mentions_written": len(mentions),
        "rejected_missing_span": rejected,
        "axis_map_path": axis_map_path if os.path.exists(axis_map_path) else "default_axis_map",
    }
    return [m.model_dump() for m in mentions], audit


def write_context_outputs(mentions: List[Dict[str, Any]], audit: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(CONTEXT_MENTIONS_PATH), exist_ok=True)
    with open(CONTEXT_MENTIONS_PATH, "w", encoding="utf-8") as handle:
        json.dump({"context_mentions": mentions}, handle, ensure_ascii=False, indent=2)

    os.makedirs(os.path.dirname(CONTEXT_AUDIT_PATH), exist_ok=True)
    with open(CONTEXT_AUDIT_PATH, "w", encoding="utf-8") as handle:
        handle.write("# Context Mining Audit\n\n")
        for key, value in audit.items():
            handle.write(f"- {key}: {value}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine span-grounded context mentions from L1.5 refined tuples.")
    parser.add_argument("--input-dir", default=L1_5_INPUT_DIR)
    parser.add_argument("--axis-map", default=CONTEXT_AXIS_MAP_PATH)
    args = parser.parse_args()
    mentions, audit = mine_context_mentions(args.input_dir, args.axis_map)
    write_context_outputs(mentions, audit)
    print(f"[Context Mining] Wrote {len(mentions)} mentions to {CONTEXT_MENTIONS_PATH}")


if __name__ == "__main__":
    main()
