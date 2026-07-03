"""Build a comparison-ready System B case card."""

from __future__ import annotations

from typing import Any


class CaseCardBuilder:
    def build(self, bundle: dict[str, Any]) -> dict[str, Any]:
        m = bundle["manifest"]
        p = bundle["pipeline"]
        ext = bundle["external_validation"]
        role = m.get("case_type", "unspecified")
        fulltext_status = m.get("fulltext_confirmation_status", "unknown")
        interpretation = self._interpretation(ext, bundle.get("lincs_validation", {}))
        reason = "positive-control whitebox case has no true graph conflict" if role == "positive_control_whitebox" and m.get("true_graph_conflict_count", 0) == 0 else p.get("l35_fulltext_confirmation", {}).get("message", "")
        return {
            "case_id": bundle["case_id"],
            "case_role": role,
            "system_b_status": "ingested",
            "pipeline_status": {
                "pipeline_complete": bool(m.get("pipeline_complete")),
                "abstract_mode_complete": bool(p.get("pipeline_complete_for_abstract_mode")),
                "external_validation_complete": bool(p.get("pipeline_complete_for_external_validation")),
                "fulltext_mode_complete": bool(p.get("pipeline_complete_for_fulltext_mode")),
            },
            "evidence_summary": {key: m.get(key, 0) for key in (
                "core_observation_count", "true_graph_conflict_count", "formal_hypothesis_count", "manual_review_followup_count"
            )},
            "validation_summary": {
                "executed_validators": m.get("executed_validators", []),
                "skipped_validators": m.get("skipped_validators", ext.get("skipped_validators", [])),
                "unavailable_validators": m.get("recommended_but_unavailable_validators", []),
                "external_validation_status": m.get("external_validation_status", ext.get("status", "unknown")),
                "lincs_interpretation": interpretation,
                "matched_signature_count": ext.get("matched_signature_count", m.get("matched_signature_count", 0)),
                "validation_target_count": ext.get("validation_target_count", m.get("validation_target_count", 0)),
                "overall_validation_score": ext.get("overall_validation_score", m.get("overall_validation_score")),
            },
            "fulltext_summary": {"status": fulltext_status, "reason": reason},
            "scientific_interpretation": self._scientific_interpretation(role),
        }

    @staticmethod
    def _interpretation(*summaries: dict[str, Any]) -> str:
        for summary in summaries:
            distribution = summary.get("interpretation_distribution", {})
            if distribution.get("mixed", 0) > 0:
                return "mixed"
            text = str(summary.get("biological_interpretation", "")).lower()
            for value in ("mixed", "supportive", "insufficient"):
                if value in text:
                    return value
        return "unavailable"

    @staticmethod
    def _scientific_interpretation(role: str) -> dict[str, list[str]]:
        if role == "positive_control_whitebox":
            return {
                "what_this_case_supports": [
                    "pipeline execution works", "domain-routed LINCS validation works", "System B bundle export works",
                    "positive-control evidence can be represented without false conflict inflation",
                ],
                "what_this_case_does_not_support": [
                    "true conflict discovery", "direct biochemical mechanism validation", "strong external validation support",
                    "production readiness of non-LINCS validators",
                ],
            }
        return {"what_this_case_supports": [], "what_this_case_does_not_support": []}
