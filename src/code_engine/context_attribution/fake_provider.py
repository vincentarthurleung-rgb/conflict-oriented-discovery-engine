from __future__ import annotations

from copy import deepcopy
from typing import Any

from .recovery import EXTRACTION_SCHEMA_VERSION_V6


class FakeRecoveryProvider:
    """Deterministic, injected test provider. It has no env or network code."""

    def __init__(self, extraction_scenarios: dict[str, str] | None = None,
                 comparison_scenarios: dict[str, str] | None = None):
        self.extraction_scenarios = extraction_scenarios or {}
        self.comparison_scenarios = comparison_scenarios or {}
        self.calls: list[dict[str, Any]] = []

    @staticmethod
    def _unknown_extraction(observation_id: str, prompt: str) -> dict[str, Any]:
        import json
        request = json.loads(prompt)
        factor_ids = list(request["factor_registry"])
        return {
            "schema_version": EXTRACTION_SCHEMA_VERSION_V6,
            "observation_id": observation_id,
            "domain_profiles": ["generic", "biomedical"],
            "input_mode": request["input"]["input_mode"],
            "context_factors": [
                {
                    "factor_id": factor_id, "status": "unknown",
                    "explicit_span": None, "source_chain_node_ids": [],
                    "inference_rule": None, "raw_components": [],
                    "normalized_candidate": None, "confidence": 0,
                }
                for factor_id in factor_ids
            ],
            "missing_critical_information": factor_ids, "warnings": [],
        }

    @staticmethod
    def _comparison(pair_id: str, prompt: str) -> dict[str, Any]:
        import json
        request = json.loads(prompt)["input"]
        return {
            "schema_version": "context_pair_attribution_v2", "pair_id": pair_id,
            "claim_a_observation_id": request["claim_a"]["observation_id"],
            "claim_b_observation_id": request["claim_b"]["observation_id"],
            "comparability": "insufficient_information", "factor_comparisons": [],
            "primary_explanatory_factors": [], "missing_critical_information": [],
            "reasoning_summary": "Deterministic fake test response.", "confidence": 0,
        }

    def call(self, *, call_type: str, record_id: str, request_identity: str,
             prompt: str, attempt_number: int) -> dict[str, Any]:
        self.calls.append({
            "call_type": call_type, "record_id": record_id,
            "request_identity": request_identity, "call_order": len(self.calls) + 1,
            "attempt_number": attempt_number,
        })
        scenarios = (self.extraction_scenarios if call_type == "extraction"
                     else self.comparison_scenarios)
        scenario = scenarios.get(record_id, "valid")
        if scenario == "provider_failure":
            raise RuntimeError(f"fake_provider_failure:{record_id}")
        payload = (self._unknown_extraction(record_id, prompt)
                   if call_type == "extraction" else self._comparison(record_id, prompt))
        if scenario == "schema_invalid":
            payload["unexpected_field"] = True
        elif scenario == "deterministic_invalid" and call_type == "extraction":
            payload["observation_id"] = "wrong-observation"
        return deepcopy(payload)


__all__ = ["FakeRecoveryProvider"]
