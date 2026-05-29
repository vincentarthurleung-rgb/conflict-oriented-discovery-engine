"""
C.O.D.E. Pipeline CLI Entrance - Stage 2: Knowledge Extraction Launcher
Complete Release 1.8.2 (Standard Execution Wrapper)

Wrapper script that invokes the modular extraction pipeline from the src/ directory.
Executes the asynchronous extraction protocol with RPM safety limits.
"""

import os
import sys
import time
import asyncio

# Dynamically add the project root to sys.path to avoid import errors
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the core orchestration function and API key from the pipeline module
from src.pipelines.stage2_l1_extract import run_extraction_pipeline, API_KEY

if __name__ == "__main__":
    # Validate API credentials before starting the pipeline
    if API_KEY == "your_real_api_key_here" or not API_KEY:
        print("\n[C.O.D.E. Launcher Fatal] Missing valid DeepSeek API credentials.")
        print("Please set the environment variable DEEPSEEK_API_KEY with your API key:")
        print("export DEEPSEEK_API_KEY=\"your_api_key\"")
        sys.exit(1)

    print("[C.O.D.E. Stage 2 Launcher] CLI entrance activated.")
    print("API authentication verified. Starting extraction pipeline...")

    start_time = time.time()

    # Execute the asynchronous extraction pipeline
    asyncio.run(run_extraction_pipeline())

    elapsed = time.time() - start_time
    print("\n[Stage 2 Launcher] Pipeline execution completed.")
    print(f"Total execution time: {elapsed:.2f} seconds.")