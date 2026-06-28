"""Batch evaluation for automated scientific problem discovery."""

from code_engine.evaluation.batch_discovery.batch_runner import run_batch_discovery
from code_engine.evaluation.batch_discovery.prompt_bank import load_prompt_bank

__all__ = ["run_batch_discovery", "load_prompt_bank"]
