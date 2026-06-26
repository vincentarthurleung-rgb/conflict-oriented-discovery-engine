"""
C.O.D.E. Pipeline Runner - Stage 8: Layer 6 Exporter Orchestrator
Description: Automated orchestration script responsible for managing filesystem persistence,
             environment self-healing initialization, and driving the Layer 6 engine
             to execute asynchronous pipeline parallelism with strict anti-drift auditing.
"""

import os
import sys
import json
import asyncio

# Dynamically add the project root to the Python path to enable seamless imports from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.pipelines.stage8_l6_Exporter_Orchestrator import CODEAsyncLayer6Engine

async def run_pipeline_orchestrator():
    print("=" * 70)
    print("[STAGE 8] INITIALIZING C.O.D.E. LAYER 8 REPORT EXPORT")
    print("=" * 70)

    # Path asset resolution
    DATA_DIR = "data/processed/l5"
    OUTPUT_DIR = "data/processed/l6"
    preferred_input_path = os.path.join(DATA_DIR, "validated_hypotheses.json")
    legacy_input_path = os.path.join(DATA_DIR, "falsified_hypotheses_vetted.json")
    L5_INPUT_PATH = preferred_input_path if os.path.exists(preferred_input_path) else legacy_input_path
    FINAL_JSON_OUTPUT = os.path.join(OUTPUT_DIR, "L6_final_ranked_output.json")

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Environment robustness self-healing
    if not os.path.exists(L5_INPUT_PATH):
        print(f"[ERROR] Upper pipeline asset missing at {L5_INPUT_PATH}. Pipeline aborted.")
        return

    # 1. Load final verified data assets from Layer 5
    with open(L5_INPUT_PATH, "r", encoding="utf-8") as f:
        vetted_data = json.load(f)

    # Anti-drift audit: correct semantic mismatches between L4 and L6
    print("[Compatibility Audit] Checking data stream desynchronization before L8 export...")
    for hyp in vetted_data.get("hypotheses", []):
        trace_blob = str(hyp.get("whitebox_traceability", "")).upper()
        # If the underlying literature indicates long-term adaptation, correct the context
        if "CHRONIC" in trace_blob or "LONG-TERM" in trace_blob:
            if "ACUTE_PHASE" in hyp["minimal_augmented_context_set"]:
                print(f" -> [Compatibility Adjustment] {hyp['hypothesis_id']}: replacing legacy 'ACUTE_PHASE' with 'CHRONIC_PHASE' based on trace text.")
                # Replace ACUTE_PHASE with CHRONIC_PHASE in the context set
                hyp["minimal_augmented_context_set"] = ["CHRONIC_PHASE" if x == "ACUTE_PHASE" else x for x in hyp["minimal_augmented_context_set"]]

    # 2. Instantiate the core decoupled asynchronous engine
    engine = CODEAsyncLayer6Engine(output_dir=OUTPUT_DIR)

    # 3. Launch parallel pipeline task scheduling
    print("[Pipeline] Spawning asynchronous Producer and Consumer tasks...")
    producer_task = asyncio.create_task(engine.stream_ingest_hypotheses(vetted_data.get("hypotheses", [])))
    consumer_task = asyncio.create_task(engine.consume_and_rank_processor())

    # 4. Wait synchronously for the parallel pipeline to finish
    await producer_task
    ranked_hypotheses = await consumer_task

    # 5. Trigger asynchronous streaming disk rendering
    print("[Pipeline] Flowing ranked matrix into disk renderer...")
    report_path = await engine.render_markdown_report(ranked_hypotheses)

    # 6. Persist the final L6 ranked JSON file conforming to front-end asset contracts
    with open(FINAL_JSON_OUTPUT, "w", encoding="utf-8") as f:
        json.dump({"ranked_hypotheses": ranked_hypotheses}, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("[SUCCESS] LAYER 8 REPORT EXPORT COMPLETED.")
    print(f" -> Markdown Report: {report_path}")
    print(f" -> Final Ranked JSON Asset: {FINAL_JSON_OUTPUT}")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_pipeline_orchestrator())
