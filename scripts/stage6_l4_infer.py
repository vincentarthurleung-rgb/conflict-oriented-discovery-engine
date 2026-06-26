"""
C.O.D.E. Master Input Script - Stage 6: Layer 4 Graph Regularized Hypothesis Search Orchestrator
Standard Release 6.6.0 (Zero-Token-Cost Bounded Search Graph Runner)
"""

import os
import sys
import time
import traceback

# Add project root to system path to enable cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage6_l4_beam_search import execute_l4_search_pipeline, L4_OUTPUT_DIR
except ImportError as e:
    print("[C.O.D.E. Fatal Error] Layer 4 import failed.", file=sys.stderr)
    print(f"Detailed error: {str(e)}", file=sys.stderr)
    print("----------------------------------------------------------------", file=sys.stderr)
    # Print full traceback for debugging
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

def main():
    print("[Orchestrator] Starting Layer 6 hypothesis search and ablation...")
    start_time = time.time()
    
    # Local NumPy / PyG matrix optimization – zero external token cost
    execute_l4_search_pipeline()
    
    elapsed = round(time.time() - start_time, 2)
    print(f"Layer 6 hypothesis search and ablation completed in {elapsed} seconds.")
    print(f"Output matrices stored in: {L4_OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()
