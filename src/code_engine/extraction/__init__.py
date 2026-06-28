"""L1/L1.5 extraction boundaries and cache metadata."""

from code_engine.extraction.llm_cache import compute_chunk_hash, compute_llm_cache_key, load_llm_cache_index
from code_engine.extraction.policy import DEFAULT_L1_TEMPERATURE, DEFAULT_L1_TOP_P, get_l1_sampling_config
from code_engine.extraction.converters import (
    l1_claim_to_evidence_record, l1_claim_to_legacy_tuple, legacy_tuple_to_l1_claim,
)

__all__ = [
    "compute_chunk_hash", "compute_llm_cache_key", "load_llm_cache_index",
    "DEFAULT_L1_TEMPERATURE", "DEFAULT_L1_TOP_P", "get_l1_sampling_config",
    "l1_claim_to_evidence_record", "l1_claim_to_legacy_tuple", "legacy_tuple_to_l1_claim",
]
