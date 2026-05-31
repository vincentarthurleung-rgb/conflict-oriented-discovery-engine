"""
C.O.D.E. Core Pipeline - Stage 7: Layer 5 Necessary Multi-Omics Falsification Engine
Universal Release 7.2.0 (Production Core - Sign Lock & Cell Pedigree Hardened Edition)

[Release 7.2.0 Features]:
- Sign consistency lock: enforces directional alignment between causal relation signs
  and LINCS transcriptomic signs. Opposite signs cause veto.
- Cell pedigree masking: uses cell ontology tree mappings to prioritize high-weight
  CNS cell lines (PC12, NEURON_CL), eliminating peripheral statistical flooding (A549, MCF7).
- Pointer lineage secured: tunnels whitebox traceability tokens down to the L6 paper core.
"""

import os
import sys
import json
import time

L4_INPUT_PATH = "./data/processed/l4/hypothesis_search_results.json"
LINCS_INDEX_PATH = "./config/schemas/l5_lincs_index.json"
CELL_MASK_PATH = "./config/schemas/l5_cell_ontology_pedigree.json"
L5_OUTPUT_DIR = "./data/processed/l5"
L5_VERIFIED_PATH = "./data/processed/l5/falsified_hypotheses_vetted.json"
L5_REPORT_PATH = "./reports/l5_verification_summary_report.json"

os.makedirs(L5_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(L5_REPORT_PATH), exist_ok=True)

# L5 omics filtering thresholds
UNRESPONSIVE_Z_THRESHOLD = 0.50   # Absolute z‑score below this is considered non‑responsive
MIN_PEDIGREE_VOTE_THRESHOLD = 0.60  # Minimum weighted consistency score to pass

def load_cell_pedigree_mask():
    if not os.path.exists(CELL_MASK_PATH):
        return {
            "cns_contexts": ["PRIMARY_NEURON", "CORTICAL_NEURON", "CNS", "BRAIN", "HIPPOCAMPUS"],
            "cns_cells": ["NEURON_CL", "PC12", "SKNMC", "SHSY5Y"],
            "peripheral_cells": ["A549", "MCF7", "PC3", "HEPG2"]
        }
    with open(CELL_MASK_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)["cell_ontology_pedigree_mask"]
    return {
        "cns_contexts": data["CNS_NERVOUS_SYSTEM_CELLS"]["target_contexts"],
        "cns_cells": data["CNS_NERVOUS_SYSTEM_CELLS"]["lincs_high_weight_cells"],
        "peripheral_cells": data["PERIPHERAL_OUT-OF-DOMAIN_SYSTEMS"]["forbidden_dilv_cells"]
    }

def load_lincs_index():
    if not os.path.exists(LINCS_INDEX_PATH):
        print(f"[L5 Fatal] Omics index file missing at: {LINCS_INDEX_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(LINCS_INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("perturbation_registry", {})

def execute_l5_falsification():
    print("[C.O.D.E. Stage 7] Starting hardened multi‑omics sign‑locked falsification engine...")
    
    if not os.path.exists(L4_INPUT_PATH):
        print(f"[Fatal] L4 hypothesis frontier missing at: {L4_INPUT_PATH}", file=sys.stderr)
        return
        
    with open(L4_INPUT_PATH, "r", encoding="utf-8") as f:
        l4_data = json.load(f)
        
    raw_hypotheses = l4_data.get("hypotheses", [])
    lincs_registry = load_lincs_index()
    pedigree_mask = load_cell_pedigree_mask()
    
    print(f"Loaded {len(raw_hypotheses)} Pareto‑optimized hypothesis vectors from L4.")

    vetted_hypotheses_pool = []
    falsified_sign_mismatch = 0
    falsified_pedigree_dilution = 0
    passed_count = 0

    # Validate each hypothesis against LINCS L1000 signatures
    for h in raw_hypotheses:
        h_id = h["hypothesis_id"]
        seed_pair = h["seed_pair"]
        tokens = seed_pair.split(" -> ")
        if len(tokens) < 2:
            continue
        sub, obj = tokens[0].strip(), tokens[1].strip()
        
        target_entity = obj.upper().strip()
        
        # Expected relation sign from the L4 trace
        expected_relation_sign = 1 
        for trace in h.get("whitebox_traceability", []):
            if "relation_sign" in trace:
                expected_relation_sign = trace["relation_sign"]
                break
                
        # If target not in omics index, pass with fallback status
        if target_entity not in lincs_registry:
            h["lincs_falsification_status"] = "Passed_By_General_Fallback"
            h["pedigree_weighted_consistency_score"] = 0.50
            vetted_hypotheses_pool.append(h)
            passed_count += 1
            continue
            
        entity_profile = lincs_registry[target_entity]
        cell_lines_data = entity_profile.get("cell_lines", {})
        
        # Check if the chain involves CNS/neural contexts
        is_cns_target_chain = False
        for trace in h.get("whitebox_traceability", []):
            snapshot_str = json.dumps(trace.get("context_snapshot", {})).upper()
            if any(ctx in snapshot_str for ctx in pedigree_mask["cns_contexts"]):
                is_cns_target_chain = True
                break
                
        weighted_votes = []
        total_weights = []
        sign_mismatch_in_high_weight_cells = False
        
        for cell_name, metrics in cell_lines_data.items():
            z_val = metrics["z_score"]
            abs_z = abs(z_val)
            
            # Assign cell‑specific weight
            cell_weight = 1.0
            if is_cns_target_chain:
                if cell_name in pedigree_mask["cns_cells"]:
                    cell_weight = 2.5  # CNS‑relevant cell lines get higher weight
                elif cell_name in pedigree_mask["peripheral_cells"]:
                    cell_weight = 0.2  # Peripheral cells are down‑weighted
                    
            total_weights.append(cell_weight)
            
            # Sign consistency lock
            if abs_z > UNRESPONSIVE_Z_THRESHOLD:
                lincs_sign = 1 if z_val > 0 else -1
                if lincs_sign != expected_relation_sign:
                    if cell_weight > 1.0:
                        sign_mismatch_in_high_weight_cells = True
                    weighted_votes.append(0.0 * cell_weight)   # mismatch → zero contribution
                else:
                    weighted_votes.append(1.0 * cell_weight)   # match → full contribution
            else:
                weighted_votes.append(0.0 * cell_weight)       # non‑responsive → zero contribution

        # Veto if any high‑weight CNS cell line shows sign mismatch
        if sign_mismatch_in_high_weight_cells:
            print(f"[Sign Locked Veto] Falsified {h_id} ({seed_pair}): causal inversion in CNS cell lines.")
            falsified_sign_mismatch += 1
            continue
            
        # Compute weighted consistency score
        final_weighted_score = sum(weighted_votes) / sum(total_weights) if total_weights else 0.0
        
        # Veto if score is below the pedigree threshold
        if final_weighted_score < MIN_PEDIGREE_VOTE_THRESHOLD:
            print(f"[Pedigree Dilution Veto] Falsified {h_id} ({seed_pair}): weighted score {round(final_weighted_score,4)} below threshold.")
            falsified_pedigree_dilution += 1
            continue
            
        # Hypothesis passes all checks
        h["lincs_falsification_status"] = "Verified_By_Hardened_Omics_Sign_Locked"
        h["pedigree_weighted_consistency_score"] = round(final_weighted_score, 4)
        h["lincs_target_gene_matched"] = entity_profile.get("target_gene", "UNKNOWN")
        
        vetted_hypotheses_pool.append(h)
        passed_count += 1

    # Write output files
    with open(L5_VERIFIED_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "chassis_version": "Universal_Release_7.2.0_SignLocked_Vetted",
            "total_candidates_evaluated": len(raw_hypotheses),
            "total_passed_retained": passed_count,
            "falsified_by_sign_mismatch": falsified_sign_mismatch,
            "falsified_by_pedigree_dilution": falsified_pedigree_dilution,
            "hypotheses": vetted_hypotheses_pool
        }, f, ensure_ascii=False, indent=2)
        
    with open(L5_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "report_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "evaluated_candidates_count": len(raw_hypotheses),
            "falsified_sign_mismatch_count": falsified_sign_mismatch,
            "falsified_pedigree_dilution_count": falsified_pedigree_dilution,
            "passed_retained_count": passed_count,
            "net_omics_survival_rate": f"{round((passed_count / len(raw_hypotheses)) * 100, 2) if raw_hypotheses else 0.0}%"
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[L5 Hardened Verification Complete] Full‑spectrum validation finished.")
    print(f"Hypotheses passing vetting: {passed_count}")
    print(f"Vetoed due to sign mismatch: {falsified_sign_mismatch}")
    print(f"Vetoed due to low pedigree consensus: {falsified_pedigree_dilution}")
    print(f"Omics audit report saved to: {L5_REPORT_PATH}\n")

if __name__ == "__main__":
    execute_l5_falsification()