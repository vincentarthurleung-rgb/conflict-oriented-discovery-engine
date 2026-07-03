"""Export machine-readable and human-readable System B reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReportExporter:
    def export(self, output_root: str | Path, card: dict[str, Any], quality: dict[str, Any], validation: dict[str, Any], limitations: list[str], case_label: str | None = None) -> Path:
        output = Path(output_root) / (case_label or card["case_id"])
        output.mkdir(parents=True, exist_ok=True)
        quality_report = {**quality, "schema_validation": validation, "limitations": limitations}
        summary = {
            "case_id": card["case_id"], "output_case_label": case_label or card["case_id"],
            "system_b_status": card["system_b_status"], "quality_class": quality["quality_class"],
            "comparison_readiness": quality["comparison_readiness"], "schema_valid": validation["schema_valid"],
            "bundle_consistent": validation["bundle_consistent"], "ready_for_system_b": validation["ready_for_system_b"],
        }
        self._json(output / "system_b_case_card.json", card)
        self._json(output / "system_b_quality_report.json", quality_report)
        self._json(output / "system_b_ingestion_summary.json", summary)
        (output / "system_b_case_card.md").write_text(self._case_markdown(card, quality, limitations), encoding="utf-8")
        (output / "system_b_quality_report.md").write_text(self._quality_markdown(card, quality, validation, limitations), encoding="utf-8")
        return output

    @staticmethod
    def _json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    @staticmethod
    def _case_markdown(card: dict[str, Any], quality: dict[str, Any], limitations: list[str]) -> str:
        e, v, f = card["evidence_summary"], card["validation_summary"], card["fulltext_summary"]
        role = "Positive-control white-box case." if card["case_role"] == "positive_control_whitebox" else card["case_role"]
        limit_lines = "\n".join(f"- {item}" for item in limitations)
        return f"""# System B Case Report: {card['case_id']}

## Executive Decision

{quality['quality_class']}

## Case Role

{role}

## Evidence Summary

- Core observations: {e['core_observation_count']}
- True graph conflicts: {e['true_graph_conflict_count']}
- Formal hypotheses: {e['formal_hypothesis_count']}
- Manual-review follow-ups: {e['manual_review_followup_count']}

## Validation Summary

- Executed validators: {', '.join(v['executed_validators']) or 'none'}
- LINCS interpretation: {v['lincs_interpretation']}
- Matched signatures: {v['matched_signature_count']}
- Overall validation score: {v['overall_validation_score']}

## Full-Text Status

{f['status']}: {f['reason']}

## Limitations

{limit_lines}

## Recommended Next Step

Proceed to first conflict-enriched case.
"""

    @staticmethod
    def _quality_markdown(card: dict[str, Any], quality: dict[str, Any], validation: dict[str, Any], limitations: list[str]) -> str:
        return f"""# System B Quality Report: {card['case_id']}

## Quality Class

{quality['quality_class']}

## Comparison Readiness

{quality['comparison_readiness']}

## Bundle Validation

- Schema valid: {str(validation['schema_valid']).lower()}
- Bundle consistent: {str(validation['bundle_consistent']).lower()}
- Ready for System B: {str(validation['ready_for_system_b']).lower()}

## Limitations

{chr(10).join(f'- {item}' for item in limitations)}
"""
