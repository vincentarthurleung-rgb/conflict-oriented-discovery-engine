"""
C.O.D.E. Core Pipeline - Stage 5: Layer 3 Shannon Gated Information Theory Court
Universal Release 4.1.0 (Production Core - Radar Self-Healing & Phase Compensation Edition)

[Release 4.1.0 Changes]:
1. Radar cardinality reset: uses sentence-level boolean detection to avoid denominator inflation.
2. Entropy compensation guard: tracks contested edge spaces with high entropy and unspecified temporal tags.
3. Maintains strict frequentist probability for information-theoretic limits.
"""

import os
import sys
import json
import math
import re
import time
from collections import defaultdict

# ==================== 1. Paths and Configuration Thresholds ====================
L2_INPUT_DIR = "./data/processed/l2_adapted"
L3_OUTPUT_DIR = "./data/processed/l3"
L3_REPORT_PATH = "./reports/shannon_reconciliation_report.json"

os.makedirs(L3_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(L3_REPORT_PATH), exist_ok=True)

# Frequency gate: causal pairs with total occurrences below this threshold are excluded
MIN_FREQUENCY_GATE = 2
# Mutual information significance threshold
MUTUAL_INFORMATION_GATE = 0.1
# Feedback radar threshold: if more than 20% of evidence sentences contain modal keywords, classify as feedback loop
FEEDBACK_SENTENCE_RATIO_GATE = 0.2

# Regular expression for temporal/feedback modal keywords
FEEDBACK_MODAL_KEYWORDS = re.compile(
    r"\b(transiently|transient|later stage|later stages|sustained|feedback|homeostatic|loop|adaptation|biphase|biphasic)\b", 
    re.IGNORECASE
)

def calculate_shannon_entropy(prob_list):
    """Calculate Shannon entropy: H(X) = -sum(p * log2(p))"""
    entropy = 0.0
    for p in prob_list:
        if p > 0:
            entropy -= p * math.log2(p)
    return round(entropy, 4)

# ==================== 2. Core Shannon Court Engine ====================

def execute_l3_shannon_court():
    """Main entry point for Layer 3 entropy-based reconciliation."""
    print("[C.O.D.E. Stage 5] Layer 3 Shannon Court initializing...")
    
    if not os.path.exists(L2_INPUT_DIR):
        print(f"[Fatal] Source L2 storage missing at: {L2_INPUT_DIR}", file=sys.stderr)
        return
        
    l2_files = [f for f in os.listdir(L2_INPUT_DIR) if f.endswith("_l2_adapted.json")]
    if not l2_files:
        print("[Court Bypassed] No L2 adapted assets found.")
        return
        
    print(f"Loaded {len(l2_files)} L2 adapted assets.")

    # Build global causal universe from all assets
    global_causal_universe = defaultdict(list)

    for fname in l2_files:
        with open(os.path.join(L2_INPUT_DIR, fname), "r", encoding="utf-8") as f:
            l2_data = json.load(f)
        asset_id = l2_data["asset_id"]
        
        for t in l2_data.get("tuples", []):
            sub = t["subject"].upper().strip()
            obj = t["object"].upper().strip()
            sign = t["relation_sign"]
            ctx = t.get("context", {})
            evidence = t.get("evidence", "")
            confidence = t.get("confidence", 0.6)
            
            if sub in ["UNSPECIFIED", ""] or obj in ["UNSPECIFIED", ""]:
                continue
                
            global_causal_universe[(sub, obj)].append({
                "source_asset": asset_id,
                "relation_sign": sign,
                "context": ctx,
                "evidence": evidence,
                "confidence": confidence
            })

    print(f"Found {len(global_causal_universe)} distinct causal pairs.")

    reconciled_knowledge_graph = []
    feedback_loop_report = {}

    # Process each causal pair
    for pair_key, observations in global_causal_universe.items():
        sub, obj = pair_key
        total_obs = len(observations)
        
        if total_obs < MIN_FREQUENCY_GATE:
            continue

        # Count relation signs using raw frequencies (not confidence-weighted)
        sign_counts = defaultdict(int)
        total_confidence_sum = 0.0
        
        for obs in observations:
            sign_counts[obs["relation_sign"]] += 1
            total_confidence_sum += obs["confidence"]
            
        p_plus = sign_counts[1] / total_obs
        p_minus = sign_counts[-1] / total_obs
        
        # Marginal entropy H(R)
        h_r = calculate_shannon_entropy([p_plus, p_minus])
        mean_edge_confidence = round(total_confidence_sum / total_obs, 4)

        # Build joint context contingency table
        joint_context_contingency = defaultdict(list)
        unspecified_time_obs_count = 0  # Count observations with unspecified temporal axis
        
        for obs in observations:
            c = obs["context"]
            composite_axis = c.get("composite_condition_axis", "UNSPECIFIED").upper().strip()
            spec = c.get("species", "UNSPECIFIED").upper().strip()
            loc = c.get("localization", "UNSPECIFIED").upper().strip()
            
            if composite_axis == "UNSPECIFIED" or "UNSPECIFIED" in composite_axis:
                unspecified_time_obs_count += 1
                
            joint_key = f"{composite_axis}_{spec}_{loc}"
            joint_context_contingency[joint_key].append(obs)

        # Calculate conditional entropy H(R | Joint Context)
        h_r_given_c = 0.0
        total_joint_counts = sum(len(bucket) for bucket in joint_context_contingency.values())
        
        context_directed_rules = defaultdict(dict)
        
        for j_key, obs_list in joint_context_contingency.items():
            p_c = len(obs_list) / total_joint_counts
            
            local_sign_counts = defaultdict(int)
            local_total = len(obs_list)
            for obs in obs_list:
                local_sign_counts[obs["relation_sign"]] += 1
                
            lp_plus = local_sign_counts[1] / local_total
            lp_minus = local_sign_counts[-1] / local_total
            
            context_directed_rules["joint_manifold"][j_key] = 1 if lp_plus >= lp_minus else -1
            
            local_h = calculate_shannon_entropy([lp_plus, lp_minus])
            h_r_given_c += p_c * local_h

        # Mutual information I(R; Context)
        i_r_c = round(max(0.0, h_r - h_r_given_c), 4)
        h_r_given_c = round(h_r_given_c, 4)
        
        final_reconciliation_score = round(i_r_c * mean_edge_confidence, 4)

        # Conflict resolution and feedback radar detection
        is_conflicting = h_r > 0.1
        resolution_status = "Uncontested"
        primary_divergence_driver = "None"
        
        if is_conflicting:
            if i_r_c >= MUTUAL_INFORMATION_GATE:
                resolution_status = "Resolved_By_Spatiotemporal_Manifold_Split"
                primary_divergence_driver = "Spatiotemporal_Joint_Manifold"
            else:
                # Sentence-level feedback detection (avoid denominator inflation)
                feedback_hit_sentences_count = 0
                total_valid_sentences = 0
                matched_proofs = []
                
                for obs in observations:
                    ev_text = obs.get("evidence", "").strip()
                    if ev_text:
                        total_valid_sentences += 1
                        if FEEDBACK_MODAL_KEYWORDS.search(ev_text):
                            feedback_hit_sentences_count += 1
                            matched_proofs.append({
                                "source_asset": obs["source_asset"],
                                "sentence": ev_text,
                                "sign": obs["relation_sign"]
                            })
                            
                feedback_sentence_ratio = feedback_hit_sentences_count / total_valid_sentences if total_valid_sentences > 0 else 0.0
                
                if feedback_sentence_ratio >= FEEDBACK_SENTENCE_RATIO_GATE:
                    resolution_status = "Homeostatic_Feedback_Loop_Preserved"
                    primary_divergence_driver = "Temporal_Latency_Feedback_Arc"
                    
                    feedback_loop_report[f"{sub} -> {obj}"] = {
                        "marginal_entropy_H_R": h_r,
                        "mutual_information_I_R_C": i_r_c,
                        "feedback_sentence_ratio": f"{feedback_hit_sentences_count}/{total_valid_sentences} ({round(feedback_sentence_ratio*100, 2)}%)",
                        "whitebox_proofs": matched_proofs
                    }
                # Phase transition compensation for high entropy with unspecified time context
                elif (unspecified_time_obs_count / total_obs) >= 0.4 and h_r > 0.8:
                    resolution_status = "Potential_Continuous_Phase_Transition_Hidden"
                    primary_divergence_driver = "Unresolved_Continuous_Time_Manifold"
                else:
                    resolution_status = "Hard_Academic_Contradiction"

        # Append edge payload to the reconciled graph
        edge_payload = {
            "subject": sub,
            "object": obj,
            "marginal_entropy_H_R": h_r,
            "conditional_entropy_H_R_C": h_r_given_c,
            "mutual_information_I_R_C": i_r_c,
            "mean_edge_confidence": mean_edge_confidence,
            "final_reconciliation_score": final_reconciliation_score,
            "is_conflicting": is_conflicting,
            "resolution_status": resolution_status,
            "primary_divergence_driver": primary_divergence_driver,
            "evidence_count": total_obs,
            "context_directed_rules": dict(context_directed_rules) if resolution_status == "Resolved_By_Spatiotemporal_Manifold_Split" else {}
        }
        reconciled_knowledge_graph.append(edge_payload)

    # Write output files
    graph_path = os.path.join(L3_OUTPUT_DIR, "integrated_shannon_graph.json")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(reconciled_knowledge_graph, f, ensure_ascii=False, indent=2)
        
    with open(L3_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "report_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_pairs_evaluated": len(reconciled_knowledge_graph),
            "homeostatic_feedback_loops_saved": len(feedback_loop_report),
            "feedback_loop_matrix": feedback_loop_report
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[L3 Shannon Reconciliation Complete]")
    print(f"Shannon graph saved to: {graph_path}")
    print(f"Homeostatic loops preserved: {len(feedback_loop_report)}")
    print(f"Conflict report saved to: {L3_REPORT_PATH}\n")

if __name__ == "__main__":
    execute_l3_shannon_court()