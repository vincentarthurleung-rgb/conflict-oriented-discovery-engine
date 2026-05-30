"""
C.O.D.E. Core Pipeline - Stage 4: Layer 2 Context Normalization & Structural Adapter
Universal Release 3.6.0 (Production Core - Absolute Precision Sealed Edition)

[Release 3.6.0 Changes]:
1. Dynamic Levenshtein Barrier: Ties edit distance thresholds to token length ratios to prevent drift.
2. Density-Weighted Confidence: Smooths belief_weight via localized frequency consensus.
3. Lineage Filter: Maintains pure 'unspecified' literal tracking for upstream compatibility.
"""

import os
import sys
import json
import re
from collections import defaultdict

L1_5_INPUT_DIR = "./data/processed/l1_5_refined"
L2_OUTPUT_DIR = "./data/processed/l2_adapted"
CONFIG_SCHEMA_PATH = "config/schemas/l2_normalization.json"

os.makedirs(L2_OUTPUT_DIR, exist_ok=True)

def load_universal_l2_contract():
    if not os.path.exists(CONFIG_SCHEMA_PATH):
        raise FileNotFoundError(f"[C.O.D.E. Fatal] Configuration missing at: {CONFIG_SCHEMA_PATH}")
    with open(CONFIG_SCHEMA_PATH, "r", encoding="utf-8") as f:
        contract = json.load(f)
    return (
        contract.get("synonym_map", {}),
        contract.get("forbidden_object_keywords", []),
        contract.get("weak_ontology_projection", {}),
        contract.get("composite_variable_mapping", {})
    )

try:
    SYNONYM_MAP, FORBIDDEN_OBJECT_KEYWORDS, ONTOLOGY_PROJECTION, COMPOSITE_MAP = load_universal_l2_contract()
except Exception as err:
    print(f"[L2 Config Init Crash] {str(err)}", file=sys.stderr)
    sys.exit(1)


def calculate_levenshtein_distance(s1, s2):
    if len(s1) < len(s2):
        return calculate_levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            curr_row.append(min(prev_row[j+1] + 1, curr_row[j] + 1, prev_row[j] + (c1 != c2)))
        prev_row = curr_row
    return prev_row[-1]


def normalize_semantic_token(raw_str):
    """
    Normalize a raw string to a standard semantic token.
    - Removes placeholder values like 'failed_unspecified' and 'unspecified'.
    - Applies synonym mapping.
    - Uses Levenshtein distance with length‑ratio threshold for fuzzy matching.
    """
    if not raw_str:
        return "unspecified"

    clean_str = str(raw_str).strip()

    # Remove LLM debugging leftovers and placeholder values
    if "failed_" in clean_str.lower() or clean_str.lower() in ["unspecified", "default_macro_env", ""]:
        return "unspecified"

    clean_str = clean_str.lower()
    clean_str = re.sub(r'[\s_\-]+', ' ', clean_str)

    if clean_str in SYNONYM_MAP:
        return SYNONYM_MAP[clean_str]

    # Fuzzy matching with dynamic threshold (edit distance ≤ 2 and ≤ 25% of token length)
    for target_key, std_name in SYNONYM_MAP.items():
        if abs(len(clean_str) - len(target_key)) <= 2:
            lev_dist = calculate_levenshtein_distance(clean_str, target_key)
            dynamic_threshold = min(2, max(1, int(len(clean_str) * 0.25)))
            if lev_dist <= dynamic_threshold:
                return std_name

    return clean_str.upper().strip()


def apply_weak_ontology_projection(ctx):
    cell_rule = ONTOLOGY_PROJECTION.get("cell_line_or_type", {})
    current_cell = ctx.get("cell_line_or_type", "unspecified").upper().strip()
    current_loc = ctx.get("localization", "unspecified").upper().strip()

    if current_cell in cell_rule:
        target_condition = cell_rule[current_cell].get("if_localization_is", "unspecified").upper()
        if current_loc == target_condition or current_loc == "UNSPECIFIED":
            ctx["localization"] = cell_rule[current_cell].get("then_project_localization_to", "CNS").upper()
    return ctx


def apply_composite_variable_mapping(ctx):
    cascade_rule = COMPOSITE_MAP.get("treatment_time_cascade", {})
    if not cascade_rule:
        return ctx

    p_axis = cascade_rule.get("primary_axis", "treatment")
    s_axis = cascade_rule.get("secondary_axis", "time")
    fusion_rules = cascade_rule.get("fusion_rules", {})
    fallback = cascade_rule.get("fallback_strategy", "UPPER_JOIN")

    p_val = ctx.get(p_axis, "unspecified").upper().strip()
    s_val = ctx.get(s_axis, "unspecified").upper().strip()

    if p_val != "UNSPECIFIED" and s_val != "UNSPECIFIED":
        joint_token = f"{p_val}_{s_val}"
        if joint_token in fusion_rules:
            ctx["composite_condition_axis"] = fusion_rules[joint_token]
        else:
            ctx["composite_condition_axis"] = joint_token if fallback == "UPPER_JOIN" else p_val
    else:
        ctx["composite_condition_axis"] = p_val if p_val != "UNSPECIFIED" else "UNSPECIFIED"

    return ctx


def is_valid_microscopic_entity(entity_name):
    name_lower = entity_name.lower()
    for keyword in FORBIDDEN_OBJECT_KEYWORDS:
        if keyword in name_lower:
            return False
    return True


def execute_l2_adaptation():
    print("[C.O.D.E. Layer 2] Starting context normalization and structural adaptation...")

    if not os.path.exists(L1_5_INPUT_DIR):
        print(f"[ERROR] Source L1.5 directory empty at: {L1_5_INPUT_DIR}")
        return

    l1_5_files = [f for f in os.listdir(L1_5_INPUT_DIR) if f.endswith("_refined.json")]
    total_tuples_saved = 0
    total_tuples_dropped = 0

    for fname in l1_5_files:
        with open(os.path.join(L1_5_INPUT_DIR, fname), "r", encoding="utf-8") as f:
            l1_data = json.load(f)

        asset_id = l1_data["asset_id"]
        belief_weight = l1_data.get("belief_weight", 0.6)
        raw_tuples = []

        # Count frequency of each unique causal fingerprint within this asset
        local_pair_counts = defaultdict(int)

        for chunk in l1_data.get("chunks_extracted", []):
            for sample in chunk.get("raw_samples", []):
                if "causal_tuples" not in sample:
                    continue

                for tuple_node in sample["causal_tuples"]:
                    sub_raw = tuple_node.get("subject", "")
                    obj_raw = tuple_node.get("object", "")
                    sign = tuple_node.get("relation_sign", 1)
                    negated = tuple_node.get("negated", False)
                    ctx = tuple_node.get("context", {})
                    evidence = tuple_node.get("evidence_sentence", "")

                    # Filter out invalid entities
                    if not is_valid_microscopic_entity(obj_raw) or not is_valid_microscopic_entity(sub_raw):
                        total_tuples_dropped += 1
                        continue

                    sub_std = normalize_semantic_token(sub_raw)
                    obj_std = normalize_semantic_token(obj_raw)

                    if sub_std in ["UNSPECIFIED", ""] or obj_std in ["UNSPECIFIED", ""]:
                        continue

                    # Normalize context fields
                    norm_ctx = {k: normalize_semantic_token(v) for k, v in ctx.items()}
                    norm_ctx = apply_weak_ontology_projection(norm_ctx)
                    norm_ctx = apply_composite_variable_mapping(norm_ctx)

                    pair_fingerprint = (sub_std, obj_std, sign)
                    local_pair_counts[pair_fingerprint] += 1

                    raw_tuples.append({
                        "subject": sub_std,
                        "relation_sign": sign,
                        "object": obj_std,
                        "negated": negated,
                        "context": norm_ctx,
                        "fingerprint": pair_fingerprint,
                        "evidence": evidence
                    })

        if not raw_tuples:
            continue

        max_local_freq = max(local_pair_counts.values()) if local_pair_counts else 1
        adapted_tuples = []

        for t in raw_tuples:
            # Combine journal belief weight with local consensus frequency
            local_consensus = local_pair_counts[t["fingerprint"]] / max_local_freq
            fused_confidence = round(belief_weight * (0.7 + 0.3 * local_consensus), 4)

            adapted_tuples.append({
                "subject": t["subject"],
                "relation_sign": t["relation_sign"],
                "object": t["object"],
                "negated": t["negated"],
                "context": t["context"],
                "confidence": fused_confidence,
                "source_asset": asset_id,
                "evidence": t["evidence"]
            })
            total_tuples_saved += 1

        if adapted_tuples:
            output_path = os.path.join(L2_OUTPUT_DIR, f"{asset_id}_l2_adapted.json")
            with open(output_path, "w", encoding="utf-8") as out_f:
                json.dump({
                    "asset_id": asset_id,
                    "adapted_tuples_count": len(adapted_tuples),
                    "tuples": adapted_tuples
                }, out_f, ensure_ascii=False, indent=2)

    print(f"\n[L2 Adaptation Complete] Processed {len(l1_5_files)} assets.")
    print(f"Valid causal contracts exported: {total_tuples_saved}")
    print(f"Filtered outcome artifacts removed: {total_tuples_dropped}")
    print(f"Output directory: {L2_OUTPUT_DIR}/")


if __name__ == "__main__":
    execute_l2_adaptation()