"""Deterministic aggregation of per-validator coverage results."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from code_engine.schemas.validation import (
    AggregatedValidationResult, ValidationAnchor, ValidationCoverageReport,
    ValidationQueryPlan, ValidationResourcePolicy, ValidationResult, ValidationSignal,
)


class ValidationResultAggregator:
    def aggregate(self, results: list[ValidationResult]) -> ValidationCoverageReport:
        hypothesis_id = results[0].hypothesis_id if results else "UNKNOWN"
        statuses = {item.validation_status for item in results}
        if "supported" in statuses and "contradicted" in statuses:
            overall = "mixed"
        elif "supported" in statuses:
            overall = "supported"
        elif "contradicted" in statuses:
            overall = "contradicted"
        elif statuses and statuses <= {"no_coverage", "not_applicable", "external_index_not_configured"}:
            overall = "no_coverage"
        elif statuses == {"insufficient_quality"}:
            overall = "insufficient_quality"
        elif not statuses:
            overall = "no_coverage"
        else:
            overall = "mixed"
        covered = [item.validator_name for item in results if item.validation_status in {"supported", "contradicted", "mixed"}]
        uncovered = [item.validator_name for item in results if item.validator_name not in covered]
        return ValidationCoverageReport(hypothesis_id=hypothesis_id, overall_status=overall, validator_results=results, covered_validators=covered, uncovered_validators=uncovered)


NON_PROOF_SIGNALS = {
    "binding_support", "target_prior", "pathway_membership_support",
    "pathway_bridge_hint", "trial_existence_signal", "clinical_context_signal",
    "cancer_dependency_context", "target_disease_association_signal",
    "identity_support", "protein_function_annotation",
}


def aggregate_validation_signals(
    signal_jsonl_path: Path, anchors: list[ValidationAnchor],
    query_plans: list[ValidationQueryPlan], resource_policy: ValidationResourcePolicy,
    *, output_dir: Path | None = None,
) -> AggregatedValidationResult:
    """Stream signal JSONL and conservatively aggregate bounded counters."""

    anchors_by_id = {item.anchor_id: item for item in anchors}
    plans_by_group: dict[tuple[str, str], list[ValidationQueryPlan]] = defaultdict(list)
    for plan in query_plans:
        plans_by_group[(plan.anchor_id, plan.validator_name)].append(plan)
    state: dict[tuple[str, str], Counter] = defaultdict(Counter)
    signal_ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    evidence_ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    if signal_jsonl_path.exists():
        with signal_jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                signal = ValidationSignal.model_validate_json(line)
                key = (signal.anchor_id, signal.validator_name)
                signal_ids[key].append(signal.signal_id)
                evidence_ids[key].extend(signal.linked_external_evidence_ids)
                if signal.signal_type == "error_signal":
                    state[key]["error"] += 1
                elif signal.signal_type == "external_index_not_configured_signal":
                    state[key]["external"] += 1
                elif signal.signal_type == "no_coverage_signal":
                    state[key]["no_coverage"] += 1
                elif signal.signal_type == "insufficient_quality_signal" or signal.quality < 0.6:
                    state[key]["low_quality"] += 1
                elif signal.signal_type in NON_PROOF_SIGNALS:
                    state[key]["limited_context"] += 1
                elif signal.supports_hypothesis is True:
                    state[key]["support"] += 1
                elif signal.contradicts_hypothesis is True:
                    state[key]["contradict"] += 1
                else:
                    state[key]["limited_context"] += 1
    results = []
    all_groups = set(plans_by_group) | set(state)
    for key in sorted(all_groups):
        anchor_id, validator_name = key
        counts = state[key]
        plans = plans_by_group.get(key, [])
        limits = ["External evidence is not proof.", "Validation signal is not proof."]
        if counts["support"] and counts["contradict"]:
            status, summary, confidence = "mixed", "High-quality support and contradiction signals coexist.", 0.8
        elif counts["support"] >= 2:
            status, summary, confidence = "supported", "Multiple high-quality support signals were observed.", 0.8
        elif counts["contradict"] >= 2:
            status, summary, confidence = "contradicted", "Multiple high-quality contradiction signals were observed.", 0.8
        elif counts["error"]:
            status, summary, confidence = "error", "Validator execution produced structured errors.", 0.0
        elif not resource_policy.execution_enabled and not signal_ids[key]:
            status, summary, confidence = "external_index_not_configured", "Validation query was planned but not executed; no coverage conclusion was made.", 0.0
            limits.append("Planned query is not executed evidence.")
        elif counts["external"] or any(
            item.status in {"no_index", "provider_not_configured", "blocked", "over_budget"}
            for item in plans
        ):
            status, summary, confidence = "external_index_not_configured", "Required external index or provider is not configured.", 0.0
        elif any(item.status == "no_cache" for item in plans):
            status, summary, confidence = "external_index_not_configured", "Cache miss left the validation question unevaluated.", 0.0
            limits.append("Cache miss is not no_coverage.")
        elif any(item.status == "too_broad" for item in plans):
            status, summary, confidence = "insufficient_quality", "Validation query was too broad for bounded execution.", 0.0
        elif counts["low_quality"] or counts["limited_context"] or counts["support"] or counts["contradict"]:
            status, summary, confidence = "insufficient_quality", "Signals are limited, low-quality, or non-proof context signals.", 0.4
        else:
            status, summary, confidence = "no_coverage", "Executed query produced no usable records; this is not contradiction.", 0.0
            limits.append("No record found is not contradiction.")
        anchor = anchors_by_id.get(anchor_id)
        hypothesis_ids = anchor.linked_hypothesis_ids if anchor else []
        results.append(ValidationResult(
            hypothesis_id=hypothesis_ids[0] if hypothesis_ids else "UNKNOWN",
            validator_name=validator_name, validation_status=status,
            confidence=confidence, quality=confidence,
            coverage_score=1.0 if signal_ids[key] else 0.0,
            anchor_ids=[anchor_id], query_plan_ids=[item.query_plan_id for item in plans],
            evidence_ids=list(dict.fromkeys(evidence_ids[key])),
            signal_ids=list(dict.fromkeys(signal_ids[key])), summary=summary,
            interpretation_limits=limits, limitations=limits,
        ))
    statuses = Counter(item.validation_status for item in results)
    if statuses["mixed"] or (statuses["supported"] and statuses["contradicted"]):
        overall = "mixed"
    elif statuses["supported"]:
        overall = "supported"
    elif statuses["contradicted"]:
        overall = "contradicted"
    elif statuses["error"]:
        overall = "error"
    elif statuses["insufficient_quality"]:
        overall = "insufficient_quality"
    elif statuses["no_coverage"]:
        overall = "no_coverage"
    else:
        overall = "external_index_not_configured"
    aggregate = AggregatedValidationResult(
        aggregate_status=overall, result_count=len(results),
        status_counts=dict(statuses), results=results,
        warnings=["external_evidence_and_signals_are_not_proof"],
    )
    if output_dir is not None:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        results_path = output / "external_validation_results.jsonl"
        summary_path = output / "external_validation_aggregate_summary.json"
        results_path.write_text("".join(item.model_dump_json() + "\n" for item in results), encoding="utf-8")
        summary_payload = aggregate.model_dump(mode="json", exclude={"results"})
        summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        aggregate.artifact_refs = {"results": str(results_path), "summary": str(summary_path)}
    return aggregate


__all__ = ["ValidationResultAggregator", "aggregate_validation_signals"]
