"""
C.O.D.E. Input Script - Stage 3: Layer 2 Normalized Database Orchestrator
Standard Release 3.5.0 (Zero-Token-Cost Local Execution Runner)
"""

import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage4_l2_adapter import execute_l2_adaptation, L2_OUTPUT_DIR
except ImportError:
    print("[C.O.D.E. Fatal] Layer 2 adapter source core missing.", file=sys.stderr)
    sys.exit(1)

def main():
    print("[Orchestrator] Launching Layer 2 Space Normalization Wave...")
    start_time = time.time()

    execute_l2_adaptation()

    elapsed = round(time.time() - start_time, 2)
    print(f"Standardization complete in {elapsed} seconds.")
    print(f"Clean normalized assets permanently cached at: {L2_OUTPUT_DIR}/\n")

if __name__ == "__main__":
    main()