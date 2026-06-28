"""Deterministic aggregation of per-validator coverage results."""

from code_engine.schemas.validation import ValidationCoverageReport, ValidationResult


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
