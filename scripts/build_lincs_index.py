"""
C.O.D.E. Tooling Script - Curated/Demo Omics Registry Builder
Universal Release 7.0.0 (Data Engineering - Memory Protection Edition)

[Release 7.0.0 Principles]:
1. Memory defense: uses chunked iterator streaming when a large matrix is available.
2. Targeted orthogonal filtering uses only targets explicitly supplied through
   the CODE_OMICS_TARGETS environment variable.

This script does not certify full LINCS validation. If the raw matrix is absent,
it writes a curated/demo registry that must be reported as limited coverage.
"""

import os
import sys
import json
import pandas as pd
from collections import defaultdict

# Paths
RAW_LINCS_CSV_PATH = "./data/external/GSE92742_Broad_LINCS_Level5_COMPZ_sub_matrix.txt"
OUTPUT_INDEX_PATH = "./configs/validators/curated_omics_registry.json"

os.makedirs(os.path.dirname(OUTPUT_INDEX_PATH), exist_ok=True)

# Explicit target genes supplied by the caller; the default is domain-neutral.
TARGET_GENE_FLIGHT_LOG = [item.strip().upper() for item in os.getenv("CODE_OMICS_TARGETS", "").split(",") if item.strip()]

def _registry_entry(anchor_gene, cell_lines):
    return {
        "registry_anchor_gene": anchor_gene,
        "omics_anchor_gene": anchor_gene,
        "target_gene": anchor_gene,
        "legacy_fields": {
            "target_gene": "retained for backward compatibility; use registry_anchor_gene"
        },
        "cell_lines": cell_lines,
    }


def build_production_lincs_index():
    print("[Omics Registry Builder] Starting curated/partial omics registry build...")
    
    # Generate a fallback high-fidelity index if the raw file is not yet available
    if not os.path.exists(RAW_LINCS_CSV_PATH):
        print("[Parser Notice] Raw data file not found on disk.")
        print("Writing curated/demo registry because the raw matrix is absent.")
        
        simulated_registry = {"perturbation_registry": {}}
        with open(OUTPUT_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump(simulated_registry, f, ensure_ascii=False, indent=2)
        print(f"Index compiled and saved to: {OUTPUT_INDEX_PATH}\n")
        return

    # Stream the large file in chunks to prevent memory overflow
    perturbation_registry = {}
    
    try:
        # chunksize=5000 keeps memory footprint low
        chunk_iterator = pd.read_csv(RAW_LINCS_CSV_PATH, sep="\t", chunksize=5000, low_memory=False)
        
        for chunk_idx, chunk in enumerate(chunk_iterator):
            for _, row in chunk.iterrows():
                pert = str(row.get("pert_iname", row.get("pert_id", ""))).upper().strip()
                gene = str(row.get("gene_symbol", "")).upper().strip()
                cell = str(row.get("cell_id", "UNKNOWN_CL")).upper().strip()
                z_val = float(row.get("zscore", 0.0))
                
                if gene in TARGET_GENE_FLIGHT_LOG:
                    key_entity = gene
                    
                    if key_entity not in perturbation_registry:
                        perturbation_registry[key_entity] = {
                            "registry_anchor_gene": gene,
                            "omics_anchor_gene": gene,
                            "target_gene": gene,
                            "legacy_fields": {
                                "target_gene": "retained for backward compatibility; use registry_anchor_gene"
                            },
                            "cell_lines": {}
                        }
                    perturbation_registry[key_entity]["cell_lines"][cell] = {"z_score": round(z_val, 4)}
                    
        with open(OUTPUT_INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"perturbation_registry": perturbation_registry}, f, ensure_ascii=False, indent=2)
            
        print(f"[Parser Success] Stream parsing completed. Index saved to: {OUTPUT_INDEX_PATH}")
    except Exception as e:
        print(f"[Parser Crash] Failed to stream data: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    build_production_lincs_index()
