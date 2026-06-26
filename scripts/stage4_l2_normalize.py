"""
C.O.D.E. Master Input Script - Stage 4: Layer 2 & Layer 3 Unified Realignment Orchestrator
Standard Release 4.5.0 (Zero-Token-Cost In-Memory EM Runner)
"""

import os
import sys
import time
import argparse

# Add project root to system path for cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.pipelines.stage5_shannon_matrix import execute_l2_l3_unified_pipeline
except ImportError:
    print("[C.O.D.E. Fatal] Stage 4 core unified matrix engine missing inside pipelines.", file=sys.stderr)
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Run Layer 2/3 unified realignment.")
    parser.add_argument("--config-path", default="config/schemas/l2_l3_ontology_rules.json")
    parser.add_argument("--allow-fallback", action="store_true")
    parser.add_argument("--strict-config", action="store_true", default=True)
    parser.add_argument("--no-strict-config", dest="strict_config", action="store_false")
    args = parser.parse_args()

    print("[Orchestrator] Starting Layer 2/3 Unified Realignment & Variational Attribution Matrix...")
    start_time = time.time()

    # Local in-memory streaming reconstruction – zero external token cost
    execute_l2_l3_unified_pipeline(
        config_path=args.config_path,
        allow_fallback=args.allow_fallback,
        strict_config=args.strict_config,
    )

    elapsed = round(time.time() - start_time, 2)
    print(f"Layer 2/3 alignment and attribution completed in {elapsed} seconds.")

if __name__ == "__main__":
    main()
