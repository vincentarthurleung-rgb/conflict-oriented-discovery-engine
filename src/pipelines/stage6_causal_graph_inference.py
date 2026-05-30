"""
C.O.D.E. Core Pipeline - Stage 6: Layer 4 Context-Masked Causal Topology Inference Engine
Universal Release 5.1.0 (Production Core - Anatomical Relaxation & Non-Asymmetric Hub Edition)

[Release 5.1.0 Changes]:
1. Anatomical adjacency relaxation: injects a biological transition graph for localization
   (SYNAPSE -> CYTOPLASM -> NUCLEUS) to prevent orthogonal vector cancellation over cellular paths.
2. Differentiated hypothesis filter: bans mid-node penalty aggregation; preserves long-range paths
   when the terminal node targets an innovative long-tail causal entity.
3. Maintains full structural compatibility with standard L3 input contracts.
"""

import os
import sys
import json
import math
import time
import numpy as np
from collections import defaultdict

L3_INPUT_PATH = "./data/processed/l3/integrated_shannon_graph.json"
L4_OUTPUT_DIR = "./data/processed/l4"
L4_GRAPH_PATH = "./data/processed/l4/final_topology_graph.json"
L4_DISCOVERY_REPORT = "./reports/ai4s_discovery_whitepaper.json"

os.makedirs(L4_OUTPUT_DIR, exist_ok=True)

# Cosine similarity threshold (reduced to rely more on anatomical relaxation)
CONTEXT_COSINE_SIMILARITY_GATE = 0.3
# Exponential penalty coefficient for high-frequency (common) nodes
CENTRALITY_ALPHA_PENALTY = 0.04

# Anatomical transition graph: defines permissible cellular compartment transitions
ANATOMICAL_TRANSFER_MAP = {
    ("SYNAPSE", "CYTOPLASM"): 0.85,
    ("CYTOPLASM", "SYNAPSE"): 0.85,
    ("CYTOPLASM", "NUCLEUS"): 0.85,
    ("NUCLEUS", "CYTOPLASM"): 0.85,
    ("SYNAPSE", "NUCLEUS"): 0.70,
    ("NUCLEUS", "SYNAPSE"): 0.70,
    ("CNS", "BRAIN"): 0.90,
    ("BRAIN", "CNS"): 0.90,
    ("PFC", "CNS"): 0.80,
    ("HIPPOCAMPUS", "CNS"): 0.80,
    ("mPFC", "PFC"): 0.95,
    ("SUBICULUM", "HIPPOCAMPUS"): 0.90
}

def build_orthogonal_context_vector(ctx_dict):
    """
    Convert a context dictionary into a normalized feature vector.

    Args:
        ctx_dict (dict): Context fields such as treatment, time, species, etc.

    Returns:
        np.ndarray: Normalized vector representation.
    """
    vector = []
    for axis in ["treatment", "time", "species", "localization", "cell_line_or_type", "genotype"]:
        val = ctx_dict.get(axis, "UNSPECIFIED").upper().strip()
        if val in ["UNSPECIFIED", ""]:
            vector.append(0.0)
        else:
            # Hash-based mapping to a positive integer
            vector.append(float(abs(hash(val)) % 1000 + 1))
    arr = np.array(vector, dtype=float)
    norm = np.linalg.norm(arr)
    return arr / norm if norm > 0 else arr

def calculate_cosine_similarity(v1, v2):
    """
    Compute cosine similarity between two vectors.

    Args:
        v1, v2 (np.ndarray): Input vectors.

    Returns:
        float: Cosine similarity.
    """
    if len(v1) == 0 or len(v2) == 0:
        return 0.0
    return float(np.dot(v1, v2))

def get_anatomical_relaxation_weight(ctx1, ctx2):
    """
    Retrieve the anatomical transition weight between two localizations.

    Args:
        ctx1, ctx2 (dict): Context dictionaries containing "localization" fields.

    Returns:
        float: Transition weight (1.0 if same or unspecified, 0.0 if no rule).
    """
    loc1 = ctx1.get("localization", "UNSPECIFIED").upper().strip()
    loc2 = ctx2.get("localization", "UNSPECIFIED").upper().strip()
    
    if loc1 == "UNSPECIFIED" or loc2 == "UNSPECIFIED" or loc1 == loc2:
        return 1.0
        
    if (loc1, loc2) in ANATOMICAL_TRANSFER_MAP:
        return ANATOMICAL_TRANSFER_MAP[(loc1, loc2)]
    return 0.0

# ==================== Main Inference Engine ====================

def execute_l4_topology_inference():
    """
    Execute Layer 4 context-masked causal topology inference.

    Builds a directed multi-graph from L3 entropy edges, splits resolved edges into parallel
    orthogonal virtual edges, computes discovery scores with MI-weighted penalty, and identifies
    long-range causal chains using anatomical relaxation.
    """
    print("[C.O.D.E. Stage 6] Starting Layer 4 Adaptive Causal Topology Inference Engine...")
    
    if not os.path.exists(L3_INPUT_PATH):
        print(f"[Fatal] Source L3 graph missing at: {L3_INPUT_PATH}", file=sys.stderr)
        return
        
    with open(L3_INPUT_PATH, "r", encoding="utf-8") as f:
        l3_data = json.load(f)
    print(f"Loaded {len(l3_data)} entropy edges from L3.")

    adj_matrix_cascaded = defaultdict(list)   # adjacency list with edge metadata
    node_degree_registry = defaultdict(int)   # out-degree per node
    node_frequency_weight = defaultdict(int)  # total evidence count per node
    node_accumulated_mi = defaultdict(float)  # sum of mutual information per node

    total_edges_bifurcated = 0

    # ==================== Step A: Adaptive splitting for resolved edges ====================
    for edge in l3_data:
        sub = edge["subject"]
        obj = edge["object"]
        mi = edge["mutual_information_I_R_C"]
        status = edge["resolution_status"]
        evidence_cnt = edge["evidence_count"]
        
        node_frequency_weight[sub] += evidence_cnt
        node_frequency_weight[obj] += evidence_cnt
        node_accumulated_mi[sub] += mi
        node_accumulated_mi[obj] += mi

        if status == "Resolved_By_Spatiotemporal_Manifold_Split" and "context_directed_rules" in edge:
            # Create parallel orthogonal virtual edges for each context manifold
            rules = edge["context_directed_rules"].get("joint_manifold", {})
            for joint_key, local_sign in rules.items():
                tokens = joint_key.split("_")
                reconstructed_ctx = {
                    "treatment": tokens[0] if len(tokens) > 0 else "UNSPECIFIED",
                    "time": tokens[1] if len(tokens) > 1 else "UNSPECIFIED",
                    "species": tokens[2] if len(tokens) > 2 else "UNSPECIFIED",
                    "localization": tokens[3] if len(tokens) > 3 else "UNSPECIFIED"
                }
                
                payload = {
                    "target": obj,
                    "relation_sign": local_sign,
                    "mutual_information": mi,
                    "context": reconstructed_ctx,
                    "context_vector": build_orthogonal_context_vector(reconstructed_ctx),
                    "status": "Orthogonal_Bifurcated"
                }
                adj_matrix_cascaded[sub].append(payload)
                node_degree_registry[sub] += 1
                node_degree_registry[obj] += 1
                total_edges_bifurcated += 1
        else:
            # Regular edge: derive sign from final reconciliation score
            recon_sign = int(1 if edge["final_reconciliation_score"] >= 0 else -1)
            # Basic fallback context (e.g., treatment for known drugs)
            fallback_ctx = {
                "treatment": sub if sub in ["KETAMINE", "MEMANTINE", "SCOPOLAMINE"] else "UNSPECIFIED"
            }
            payload = {
                "target": obj,
                "relation_sign": recon_sign,
                "mutual_information": mi,
                "context": fallback_ctx,
                "context_vector": build_orthogonal_context_vector(fallback_ctx),
                "status": status
            }
            adj_matrix_cascaded[sub].append(payload)
            node_degree_registry[sub] += 1
            node_degree_registry[obj] += 1

    print(f"Adaptive split complete. Created {total_edges_bifurcated} parallel virtual edges.")

    # ==================== Step B: MI-weighted discovery scores ====================
    advanced_discovery_scores = {}
    for node, raw_degree in node_degree_registry.items():
        freq = node_frequency_weight[node]
        accumulated_mi = node_accumulated_mi[node]
        
        # Exponential penalty for high-frequency (common) nodes
        penalty_factor = math.exp(-CENTRALITY_ALPHA_PENALTY * max(0, freq - 5))
        discovery_score = round(raw_degree * (1.0 + accumulated_mi) * penalty_factor, 4)
        
        advanced_discovery_scores[node] = {
            "raw_degree_centrality": raw_degree,
            "evidence_exposure_frequency": freq,
            "accumulated_mutual_information": round(accumulated_mi, 4),
            "ai4s_discovery_priority_score": discovery_score
        }

    # ==================== Step C: Long‑range chain discovery with anatomical relaxation ====================
    print("Activating context‑masked anatomical relaxation radar...")
    discovered_long_range_chains = []

    for start_node, outbound_edges in adj_matrix_cascaded.items():
        for edge_1 in outbound_edges:
            mid_node = edge_1["target"]
            ctx_1 = edge_1["context"]
            v1 = edge_1["context_vector"]
            sign_1 = edge_1["relation_sign"]
            mi_1 = edge_1["mutual_information"]
            
            if mid_node in adj_matrix_cascaded:
                for edge_2 in adj_matrix_cascaded[mid_node]:
                    end_node = edge_2["target"]
                    ctx_2 = edge_2["context"]
                    v2 = edge_2["context_vector"]
                    sign_2 = edge_2["relation_sign"]
                    mi_2 = edge_2["mutual_information"]
                    
                    if end_node == start_node:
                        continue  # skip self‑loops
                    
                    # Cosine similarity of context vectors
                    cosine_sim = calculate_cosine_similarity(v1, v2)
                    
                    # Anatomical transition weight
                    anatomical_relaxation = get_anatomical_relaxation_weight(ctx_1, ctx_2)
                    
                    # Path allowed if cosine similarity sufficient or anatomical relaxation strong
                    if cosine_sim >= CONTEXT_COSINE_SIMILARITY_GATE or anatomical_relaxation >= 0.8 or (len(v1) == 0 or len(v2) == 0):
                        
                        inferred_sign = sign_1 * sign_2
                        
                        # Rarity weight for the target node (long-tail entities are more valuable)
                        target_rarity_weight = 1.0
                        if end_node in advanced_discovery_scores:
                            target_freq = advanced_discovery_scores[end_node]["evidence_exposure_frequency"]
                            target_rarity_weight = 1.5 if target_freq <= 4 else 1.0
                            
                        path_score = round((mi_1 + mi_2 + 0.1) * max(cosine_sim, anatomical_relaxation) * target_rarity_weight, 4)
                        
                        if path_score > 0.01:
                            chain_payload = {
                                "source": start_node,
                                "intermediary": mid_node,
                                "target": end_node,
                                "inferred_sign": inferred_sign,
                                "algebraic_cosine_similarity": round(cosine_sim, 4),
                                "anatomical_relaxation_weight": round(anatomical_relaxation, 4),
                                "ai4s_hypothesis_discovery_score": path_score
                            }
                            discovered_long_range_chains.append(chain_payload)

    # Sort chains by discovery score (descending)
    discovered_long_range_chains.sort(key=lambda x: x["ai4s_hypothesis_discovery_score"], reverse=True)
    sorted_discovery_nodes = sorted(advanced_discovery_scores.items(), key=lambda x: x[1]["ai4s_discovery_priority_score"], reverse=True)

    # ==================== Step D: Export results ====================
    # Export full graph (omit context_vector fields for readability)
    graph_export = {
        "metadata": {
            "version": "Release_5.1.0_Flow_Closed",
            "total_nodes": len(node_degree_registry),
            "bifurcated_edge_count": total_edges_bifurcated
        },
        "adjacency_list": {k: [{ki: vi for ki, vi in edge.items() if ki != "context_vector"} for edge in v] for k, v in adj_matrix_cascaded.items()}
    }
    with open(L4_GRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(graph_export, f, ensure_ascii=False, indent=2)

    # Export discovery report
    report_export = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "top_ai4s_target_discovery_priority": dict(sorted_discovery_nodes[:15]),
        "discovered_long_range_causal_chains_count": len(discovered_long_range_chains),
        "top_inferred_hypotheses_chains": discovered_long_range_chains[:15]
    }
    with open(L4_DISCOVERY_REPORT, "w", encoding="utf-8") as f:
        json.dump(report_export, f, ensure_ascii=False, indent=2)

    print(f"\n[L4 Topology Inference Complete]")
    print(f"Graph saved to: {L4_GRAPH_PATH}")
    print(f"Long-range causal chains discovered: {len(discovered_long_range_chains)}")
    print(f"Discovery report saved to: {L4_DISCOVERY_REPORT}\n")

if __name__ == "__main__":
    execute_l4_topology_inference()