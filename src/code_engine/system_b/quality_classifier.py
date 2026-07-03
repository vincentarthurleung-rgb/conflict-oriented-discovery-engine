"""Policy-based quality classification; no biological rescoring occurs here."""

from __future__ import annotations

from typing import Any


class QualityClassifier:
    def classify(self, bundle: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
        m = bundle.get("manifest", {})
        role = m.get("case_type")
        conflicts = m.get("true_graph_conflict_count", 0)
        validators = m.get("executed_validators", [])
        fulltext = m.get("fulltext_confirmation_status", "unknown")
        if not validation.get("schema_valid") or not validation.get("ready_for_system_b"):
            quality = "CASE_NOT_READY"
        elif conflicts > 0 and fulltext in {"not_enabled", "not_run", "unavailable", "unknown"}:
            quality = "CASE_NEEDS_FULLTEXT_CONFIRMATION"
        elif not validators:
            quality = "CASE_NEEDS_VALIDATOR_EXPANSION"
        elif role == "positive_control_whitebox":
            quality = "CASE_READY_FOR_ARCHIVE"
        else:
            quality = "CASE_READY_FOR_COMPARISON"
        return {
            "quality_class": quality,
            "comparison_readiness": "READY_AS_POSITIVE_CONTROL" if role == "positive_control_whitebox" and quality == "CASE_READY_FOR_ARCHIVE" else ("READY_FOR_COMPARISON" if quality == "CASE_READY_FOR_COMPARISON" else "NOT_READY"),
            "validator_expansion_needed": bool(m.get("recommended_but_unavailable_validators")) or not validators,
            "conflict_discovery_status": "NO_TRUE_CONFLICT_EXPECTED" if role == "positive_control_whitebox" and conflicts == 0 else ("TRUE_CONFLICT_PRESENT" if conflicts else "NO_TRUE_CONFLICT_FOUND"),
            "system_b_use": ["archive", "positive_control", "pipeline_regression_fixture", "bundle_schema_fixture"] if role == "positive_control_whitebox" else ["archive", "comparison"],
        }
