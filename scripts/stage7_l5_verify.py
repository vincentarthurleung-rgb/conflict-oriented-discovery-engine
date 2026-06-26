"""
C.O.D.E. Master Input Script - Stage 7: Layer 5 Necessary Multi-Omics Verification Orchestrator
Standard Release 7.1.0 (Zero-Token-Cost Omics Query Runner)
"""

import os
import sys
import time

# Add project root to system path to enable cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage7_l5_falsification import execute_l5_falsification, L5_OUTPUT_DIR
except ImportError:
    print("[C.O.D.E. Fatal] Stage 7 multi-omics falsification core matrix architecture missing inside pipelines.", file=sys.stderr)
    sys.exit(1)

def main():
    print("[Orchestrator] Starting Layer 5 curated/external validator pipeline...")
    start_time = time.time()
    
    # Local fast matrix filtering
    execute_l5_falsification()
    
    elapsed = round(time.time() - start_time, 2)
    print(f"Layer 5 validator orchestration completed in {elapsed} seconds.")
    print(f"Vetted true vectors permanently stored in: {L5_OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()
