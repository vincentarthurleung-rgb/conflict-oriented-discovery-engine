"""
C.O.D.E. v4.0 Stage 7: External Validation Orchestrator.

This replaces pass-by-fallback behavior with explicit validator coverage states.
The curated omics validator is intentionally named as curated/demo coverage, not
full LINCS validation.
"""

from __future__ import annotations

import json
import os
import time

from src.validators import CuratedOmicsValidator, NullValidator


L4_INPUT_PATH = "./data/processed/l4/hypothesis_search_results.json"
L5_OUTPUT_DIR = "./data/processed/l5"
L5_VALIDATED_CANDIDATES_PATH = "./data/processed/l5/validated_hypotheses.json"
L5_VERIFIED_PATH = "./data/processed/l5/falsified_hypotheses_vetted.json"
L5_VALIDATION_RESULTS_PATH = "./data/processed/l5/validation_results.json"
L5_REPORT_PATH = "./reports/l5_verification_summary_report.json"
L5_AUDIT_MD_PATH = "./reports/l5_validation_audit.md"


def _select_validator(hypothesis: dict, validators: list) -> object:
    for validator in validators:
        if validator.can_validate(hypothesis):
            return validator
    return NullValidator()


def _write_json(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def execute_l5_falsification() -> None:
    print("[C.O.D.E. v4.0 Stage 7] Starting external validator orchestrator...")
    if not os.path.exists(L4_INPUT_PATH):
        raise FileNotFoundError(f"L4 hypothesis frontier missing at: {L4_INPUT_PATH}")

    with open(L4_INPUT_PATH, "r", encoding="utf-8") as handle:
        l4_data = json.load(handle)

    raw_hypotheses = l4_data.get("hypotheses", [])
    validators = [CuratedOmicsValidator()]
    vetted_hypotheses = []
    validation_results = []

    for hypothesis in raw_hypotheses:
        validator = _select_validator(hypothesis, validators)
        result = validator.validate(hypothesis)
        validation_results.append(result)

        hypothesis["validation_result"] = result
        hypothesis["validation_status"] = result["status"]
        hypothesis["validation_score"] = result.get("score")
        # Legacy field retained for backward compatibility with older report exporters.
        hypothesis["lincs_falsification_status"] = result["status"]
        if result.get("omics_anchor_gene"):
            hypothesis["omics_anchor_gene"] = result["omics_anchor_gene"]
            hypothesis["registry_anchor_gene"] = result["registry_anchor_gene"]
            hypothesis["anchor_gene"] = result["omics_anchor_gene"]
            # Legacy field retained for backward compatibility with older reports.
            hypothesis["lincs_target_gene_matched"] = result["omics_anchor_gene"]

        if result["status"] == "Sign_Consistent_Under_Curated_Index":
            vetted_hypotheses.append(hypothesis)

    counts = {}
    for result in validation_results:
        counts[result["status"]] = counts.get(result["status"], 0) + 1

    _write_json(
        L5_VALIDATION_RESULTS_PATH,
        {
            "chassis_version": "CODE_v4.0_validator_orchestrator",
            "validation_results": validation_results,
        },
    )
    validated_payload = {
        "chassis_version": "CODE_v4.0_validation_orchestrator",
        "total_candidates_evaluated": len(raw_hypotheses),
        "total_retained_after_validation": len(vetted_hypotheses),
        "status_counts": counts,
        "hypotheses": vetted_hypotheses,
        "legacy_alias": L5_VERIFIED_PATH,
    }
    _write_json(L5_VALIDATED_CANDIDATES_PATH, validated_payload)
    # Legacy output retained for backward compatibility with scripts/stage8_l6_results.py.
    _write_json(L5_VERIFIED_PATH, {**validated_payload, "legacy_field_notice": "Use validated_hypotheses.json for new code."})
    _write_json(
        L5_REPORT_PATH,
        {
            "report_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "evaluated_candidates_count": len(raw_hypotheses),
            "status_counts": counts,
            "retained_after_validation_count": len(vetted_hypotheses),
            "validator_note": "Curated omics index only; unresolved coverage is not treated as passed.",
        },
    )

    os.makedirs(os.path.dirname(L5_AUDIT_MD_PATH), exist_ok=True)
    with open(L5_AUDIT_MD_PATH, "w", encoding="utf-8") as handle:
        handle.write("# L5 Validation Audit\n\n")
        handle.write("This run uses a curated/demo omics registry, not full LINCS validation.\n\n")
        for status, count in counts.items():
            handle.write(f"- {status}: {count}\n")
        handle.write("\nUncovered hypotheses are `Unresolved_No_Coverage` and are not retained as passed.\n")

    print(f"[L5] Evaluated candidates: {len(raw_hypotheses)}")
    print(f"[L5] Status counts: {counts}")
    print(f"[L5] Retained sign-consistent curated hypotheses: {len(vetted_hypotheses)}")


if __name__ == "__main__":
    execute_l5_falsification()
