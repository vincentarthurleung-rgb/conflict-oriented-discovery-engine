"""
C.O.D.E. Master Input Script - Stage 6: Layer 4 Topologic Inference Orchestrator
Standard Release 5.0.0 (Zero-Token-Cost Causal Graph Runner)
"""

import os
import sys
import time

# Add project root to system path for cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage6_causal_graph_inference import execute_l4_topology_inference, L4_OUTPUT_DIR
except ImportError:
    print("[C.O.D.E. Fatal] Stage 6 topology inference chassis missing.", file=sys.stderr)
    sys.exit(1)

def main():
    """
    Main entry point for Layer 4 graph topology and discovery pipeline.
    Executes local causal graph inference without consuming external API tokens.
    """
    print("[Orchestrator] Starting Layer 4 Graph Topology & AI4S Discovery Pipeline...")
    start_time = time.time()

    # Local matrix and multi‑directed graph computation – zero API cost
    execute_l4_topology_inference()

    elapsed = round(time.time() - start_time, 2)
    print(f"Topological inference completed in {elapsed} seconds.")
    print(f"Master network knowledge flow stored at: {L4_OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()