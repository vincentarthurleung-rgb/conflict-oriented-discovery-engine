"""
C.O.D.E. Master Input Script - Stage 4: Layer 2 & Layer 3 Unified Realignment Orchestrator
Standard Release 4.5.0 (Zero-Token-Cost In-Memory EM Runner)
"""

import os
import sys
import time

# Add project root to system path for cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage5_shannon_matrix import execute_l2_l3_unified_pipeline
except ImportError:
    print("[C.O.D.E. Fatal] Stage 4 core unified matrix engine missing inside pipelines.", file=sys.stderr)
    sys.exit(1)

def main():
    print("[Orchestrator] Starting Layer 2/3 Unified Realignment & Variational Attribution Matrix...")
    start_time = time.time()

    # Local in-memory streaming reconstruction – zero external token cost
    execute_l2_l3_unified_pipeline()

    elapsed = round(time.time() - start_time, 2)
    print(f"Layer 2/3 alignment and attribution completed in {elapsed} seconds.")

if __name__ == "__main__":
    main()