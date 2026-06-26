"""
C.O.D.E. Universal Input Script - Stage 3: Layer 1.5 Truth Matrix Orchestrator
Standard Release 3.0.1 (Production Async Dispatcher)

[Release 3.0.1 Changes]:
- Removed unused walrus operator for cleaner code.
- Used gather(return_exceptions=True) to isolate runtime crashes.
- Added active asset verification to prevent downstream artifacts.
"""

import os
import sys
import json
import asyncio
import time
from traceback import format_exc

# Add project root to system path for cross-module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import aiohttp
except ImportError:
    print("[C.O.D.E. Fatal] Missing 'aiohttp' library. Run 'pip install aiohttp'.", file=sys.stderr)
    sys.exit(1)

try:
    from src.pipelines.stage3_l1_5_refiner import refine_single_file, L1_INPUT_DIR, CONFIG_RULES_PATH, L1_5_OUTPUT_DIR
except ImportError:
    print("[C.O.D.E. Fatal] Unable to import refiner module. Ensure src/pipelines/stage3_l1_5_refiner.py exists.", file=sys.stderr)
    sys.exit(1)


def audit_preflight_check():
    """Run preflight checks to validate input paths and API credentials."""
    if not os.path.exists(CONFIG_RULES_PATH):
        return False
    if not os.path.exists(L1_INPUT_DIR):
        return False
    if not os.getenv("DEEPSEEK_API_KEY"):
        return False
    return True


async def orchestrate_mass_refinement():
    """Orchestrate concurrent refinement of all Layer 1 assets and generate an active manifest."""
    if not audit_preflight_check():
        print("[Preflight Error] Configuration file, input directory, or API key missing.", file=sys.stderr)
        sys.exit(1)

    # Gather all L1 extraction files
    all_l1_files = [f for f in os.listdir(L1_INPUT_DIR) if f.endswith("_extracted.json")]
    total_files = len(all_l1_files)

    if total_files == 0:
        print(f"[Orchestrator] No files found in {L1_INPUT_DIR}. Exiting.")
        return

    print(f"[Orchestrator] Found {total_files} L1 assets. Starting refinement...")
    start_time = time.time()

    # Concurrency control to avoid API rate limiting
    semaphore = asyncio.BoundedSemaphore(3)
    connector = aiohttp.TCPConnector(limit=32)

    active_manifest_registry = []

    async with aiohttp.ClientSession(connector=connector) as session:
        file_keys = []
        tasks = []
        for fname in all_l1_files:
            asset_id = fname.replace("_extracted.json", "")
            file_keys.append(asset_id)
            tasks.append(refine_single_file(session, semaphore, fname))

        print("[Orchestrator] Launching refinement tasks...")
        # Use return_exceptions to prevent a single failure from crashing all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Audit each asset's output after refinement
        print("[Orchestrator] Performing post-refinement validation...")
        for asset_id, res in zip(file_keys, results):
            expected_path = os.path.join(L1_5_OUTPUT_DIR, f"{asset_id}_refined.json")

            if isinstance(res, Exception) or not os.path.exists(expected_path):
                print(f"[Error] Asset '{asset_id}' failed during refinement.", file=sys.stderr)
                if isinstance(res, Exception):
                    print(f"  Exception: {str(res)}", file=sys.stderr)
                print(f"  Excluding '{asset_id}' from active registry.", file=sys.stderr)
                continue

            active_manifest_registry.append(f"{asset_id}_refined.json")

    elapsed = round(time.time() - start_time, 2)

    # Generate manifest of successfully refined assets for downstream consumption
    manifest_payload = {
        "generation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "active_assets_count": len(active_manifest_registry),
        "total_source_assets": total_files,
        "registered_refined_files": active_manifest_registry
    }

    with open(os.path.join(L1_5_OUTPUT_DIR, "l1_5_active_manifest.json"), "w", encoding="utf-8") as m_f:
        json.dump(manifest_payload, m_f, ensure_ascii=False, indent=2)

    print(f"[Orchestrator] Refinement completed.")
    print(f"Active assets: {len(active_manifest_registry)} / {total_files}")
    print(f"Duration: {elapsed} seconds.")
    print(f"Manifest saved to: {L1_5_OUTPUT_DIR}/l1_5_active_manifest.json")


if __name__ == "__main__":
    # Windows event loop compatibility
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(orchestrate_mass_refinement())
    except Exception as e:
        print(f"\n[Orchestrator Fatal] Unhandled exception:\n{format_exc()}", file=sys.stderr)
        sys.exit(1)