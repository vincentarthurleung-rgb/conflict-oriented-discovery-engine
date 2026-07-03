"""Structural and cross-artifact consistency checks for case bundles."""

from __future__ import annotations

from typing import Any


class BundleSchemaValidator:
    def validate(self, bundle: dict[str, Any]) -> dict[str, Any]:
        manifest = bundle.get("manifest", {})
        pipeline = bundle.get("pipeline", {})
        errors: list[str] = []
        warnings: list[str] = []
        for filename in bundle.get("missing_required_files", []):
            errors.append(f"missing_required_file: {filename}")

        ready = manifest.get("ready_for_system_b") is True
        if not ready:
            errors.append("ready_for_system_b_not_true")
        if manifest.get("pipeline_complete") is not True:
            errors.append("pipeline_complete_not_true")
        if "executed_validators" not in manifest:
            errors.append("executed_validators_missing")
        if not isinstance(pipeline.get("stages", {}).get("L7", {}).get("status"), str):
            errors.append("l7_status_missing")
        if not self._fulltext_status(bundle):
            errors.append("fulltext_status_missing")

        canonical = {
            "manual_review_followup_count": bundle.get("hypothesis", {}).get("manual_review_followup_count"),
            "formal_hypothesis_count": bundle.get("hypothesis", {}).get("formal_hypothesis_count"),
            "true_graph_conflict_count": bundle.get("graph_conflict", {}).get("true_graph_conflict_count"),
        }
        fulltext = self._fulltext_summary(bundle)
        canonical.update({
            "fulltext_candidate_paper_count": fulltext.get("candidate_paper_count"),
            "fulltext_available_count": fulltext.get("oa_available_count"),
            "fulltext_l1_claim_count": fulltext.get("fulltext_l1_claim_count"),
            "fulltext_confirmed_conflict_count": fulltext.get("fulltext_confirmed_conflict_count"),
        })
        for field, expected in canonical.items():
            if expected is not None and manifest.get(field) != expected:
                warnings.append(f"manifest_count_mismatch: {field}")

        selected = bundle.get("validator_selection", {}).get("validator_selection", {})
        selected_executed = selected.get("executed_validators")
        if selected_executed is not None and manifest.get("executed_validators") != selected_executed:
            warnings.append("manifest_validator_mismatch: executed_validators")
        schema_valid = not errors
        return {
            "schema_valid": schema_valid,
            "bundle_consistent": schema_valid and not warnings,
            "ready_for_system_b": ready,
            "errors": errors,
            "warnings": warnings,
        }

    @staticmethod
    def _fulltext_summary(bundle: dict[str, Any]) -> dict[str, Any]:
        summaries = bundle.get("fulltext", {})
        return summaries.get("l35_fulltext_retrieval_summary", {}) or bundle.get("pipeline", {}).get("l35_fulltext_confirmation", {})

    def _fulltext_status(self, bundle: dict[str, Any]) -> str | None:
        return self._fulltext_summary(bundle).get("status") or bundle.get("manifest", {}).get("fulltext_confirmation_status")
