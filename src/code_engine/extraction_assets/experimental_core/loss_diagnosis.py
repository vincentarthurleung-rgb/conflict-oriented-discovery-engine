"""Find the first observed structural loss without blaming unavailable raw data."""
from __future__ import annotations

from typing import Any


def first_loss(traces: list[dict[str, Any]], component: str) -> tuple[int | None, str | None, str]:
    count_key = {
        "experimental_factors": "factor_count", "interventions": "intervention_count",
        "measurements": "measurement_count", "observed_results": "observed_result_count",
        "linkages": "linkage_count",
    }[component]
    available = [row for row in sorted(traces, key=lambda x: x["stage_number"])
                 if row["field_status"].get(component) != "unavailable"]
    if not available:
        return None, None, "legacy_lineage_unavailable"
    previous: dict[str, Any] | None = None
    for row in available:
        if previous and previous[count_key] > 0 and row[count_key] == 0:
            stage = row["stage_number"]
            origin = {
                1: "parser_dropped", 2: "response_schema_could_not_represent",
                3: "scientific_validation_rejected", 4: "fulltext_v3_projection_loss",
                5: "evidence_projection_loss", 6: "asset_migration_omission",
                7: "adapter_dropped",
            }.get(stage, "unknown")
            return stage, row["stage_name"], origin
        previous = row
    first_positive = next((index for index, row in enumerate(available) if row[count_key] > 0), None)
    if first_positive is not None and first_positive > 0:
        return (
            available[0]["stage_number"], available[0]["stage_name"],
            "legacy_lineage_unavailable",
        )
    if all(row[count_key] == 0 for row in available):
        if available[0]["stage_number"] == 0:
            return 0, available[0]["stage_name"], "absent_from_provider_output"
        if available[0]["stage_number"] == 1:
            return 1, available[0]["stage_name"], "raw_unavailable"
        return available[0]["stage_number"], available[0]["stage_name"], "legacy_lineage_unavailable"
    return None, None, "present_all_stages"
