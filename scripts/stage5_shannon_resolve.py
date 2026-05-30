"""
C.O.D.E. Master Input Script - Stage 4: Layer 3 Integrated Shannon Court Orchestrator
Standard Release 4.0.0 (Zero-Token-Cost Matrix Compute Runner)
"""

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage5_shannon_matrix import execute_l3_shannon_court, L3_OUTPUT_DIR
except ImportError:
    print("[C.O.D.E. Fatal] Stage 5 shannon court core infrastructure missing.", file=sys.stderr)
    sys.exit(1)

def main():
    print("[Orchestrator] Starting Layer 3 Shannon Gated Court Matrix computation...")
    start_time = time.time()

    # Local graph computation - no external API cost
    execute_l3_shannon_court()

    elapsed = round(time.time() - start_time, 2)
    print(f"Shannon convergence completed in {elapsed} seconds.")
    print(f"Integrated Shannon matrix stored at: {L3_OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()