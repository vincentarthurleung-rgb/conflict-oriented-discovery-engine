"""Offline semantics-only reprojection for existing L2 artifacts."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from code_engine.corpus.io import atomic_write_json
from code_engine.normalization.core_eligibility import core_graph_eligibility
from code_engine.normalization.intervention_semantics import apply_evidence_semantics


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _relation_for_layer(row: dict[str, Any]) -> str:
    layer = row.get("scientific_edge_layer")
    sign = row.get("derived_causal_sign")
    direction = "increase" if sign == 1 else "decrease" if sign == -1 else "unknown"
    if layer == "differential_expression":
        return "higher_expression_in" if row.get("observed_outcome_sign") == 1 else "lower_expression_in" if row.get("observed_outcome_sign") == -1 else "differentially_expressed_in"
    if layer == "association":
        return "associated_with"
    if layer == "intervention_observation":
        return "observed_increase_after" if row.get("observed_outcome_sign") == 1 else "observed_decrease_after"
    if layer == "rescue_supported":
        return "rescues"
    if layer in {"strict_causal_core", "causal_reviewable"}:
        return "increases" if direction == "increase" else "decreases" if direction == "decrease" else "unknown"
    return str(row.get("relation_family") or row.get("relation_raw") or "unknown")


def _endpoint_pair(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "subject": row.get("subject_canonical_name") or row.get("subject") or row.get("subject_raw"),
        "subject_id": row.get("subject_canonical_id"),
        "object": row.get("object_canonical_name") or row.get("object") or row.get("object_raw"),
        "object_id": row.get("object_canonical_id"),
        "measured_entity": row.get("measured_entity"),
        "measurement_dimension": row.get("measurement_dimension"),
        "sample_context": row.get("sample_context"),
        "intervention_target": row.get("intervention_target"),
        "intervention_type": row.get("intervention_type"),
    }


def _lineage(old_row: dict[str, Any]) -> dict[str, Any]:
    new_row = apply_evidence_semantics(dict(old_row))
    gate = core_graph_eligibility(new_row)
    return {
        "observation_id": old_row.get("observation_id"),
        "paper_id": old_row.get("paper_id"),
        "evidence_sentence": old_row.get("evidence_sentence") or old_row.get("evidence_text"),
        "old_layer": old_row.get("scientific_edge_layer") or old_row.get("graph_layer"),
        "new_layer": new_row.get("scientific_edge_layer"),
        "old_relation": old_row.get("formal_relation") or old_row.get("relation_family") or old_row.get("relation_raw"),
        "old_sign": old_row.get("relation_sign") or old_row.get("direct_relation_sign") or old_row.get("direction"),
        "new_relation": gate.get("formal_relation") if gate.get("eligible") else _relation_for_layer(new_row),
        "new_sign": new_row.get("derived_causal_sign"),
        "new_direction": new_row.get("causal_direction"),
        "old_endpoints": {
            "subject": old_row.get("subject") or old_row.get("subject_raw"),
            "subject_id": old_row.get("subject_canonical_id"),
            "object": old_row.get("object") or old_row.get("object_raw"),
            "object_id": old_row.get("object_canonical_id"),
        },
        "new_endpoints": _endpoint_pair(new_row),
        "evidence_design": new_row.get("evidence_design"),
        "inference_type": new_row.get("inference_type"),
        "derivation_provenance": new_row.get("causal_direction_provenance"),
        "core_status": "strict_core" if gate.get("eligible") else "non_core_retained",
        "core_reason": gate.get("reason"),
        "core_exclusion_reasons": gate.get("reasons", []),
    }


def _safety_metrics(lineages: list[dict[str, Any]]) -> dict[str, int]:
    core = [row for row in lineages if row["core_status"] == "strict_core"]
    def count(reason: str) -> int:
        return sum(reason in (row.get("core_exclusion_reasons") or []) for row in core)
    return {
        "unresolved_fallback_in_core_count": count("endpoint_unresolved_fallback"),
        "sample_context_in_core_count": count("sample_context_endpoint"),
        "association_in_causal_core_count": count("association_projected_as_regulation") + count("non_causal_evidence_design"),
        "measurement_missing_in_core_count": count("measurement_projection_missing"),
        "direction_conflict_in_core_count": count("direction_provenance_inconsistent"),
        "unresolved_intervention_in_core_count": count("intervention_semantics_unresolved") + count("rescue_semantics_unresolved"),
        "unsupported_isoform_projection_in_core_count": count("unsupported_isoform_projection"),
    }


def _write_markdown(path: Path, lineages: list[dict[str, Any]], counts: Counter[str]) -> None:
    lines = [
        "# EMT v6 Intervention Semantics Reprojection",
        "",
        "| Observation | Old edge | New representation | Layer | Direction | Core status | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in lineages:
        old = f"{row['old_endpoints']['subject']} {row['old_relation']} {row['old_endpoints']['object']} ({row['old_sign']})"
        new = f"{row['new_endpoints']['subject']} {row['new_relation']} {row['new_endpoints']['object']}"
        if row["new_endpoints"].get("measurement_dimension"):
            new += f" [{row['new_endpoints']['measurement_dimension']}]"
        lines.append(
            "| {obs} | {old} | {new} | {layer} | {direction} | {status} | {reason} |".format(
                obs=row.get("observation_id"),
                old=str(old).replace("|", "/"),
                new=str(new).replace("|", "/"),
                layer=row.get("new_layer"),
                direction=row.get("new_direction"),
                status=row.get("core_status"),
                reason=", ".join(row.get("core_exclusion_reasons") or [row.get("core_reason") or ""]),
            )
        )
    lines.extend(["", "## Useful Non-Core Evidence", ""])
    for layer in ("causal_reviewable", "intervention_observation", "rescue_supported", "association", "differential_expression"):
        lines.append(f"- {layer}: {counts[layer]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_contract_reports(reports_dir: Path) -> None:
    (reports_dir / "intervention_semantics_design.md").write_text(
        "# Intervention Semantics Design\n\n"
        "Lexical polarity is treated as observed outcome direction. Intervention semantics derives natural-state causal direction from intervention sign and observed outcome sign. Rescue and association evidence are retained in explicit non-core layers by default.\n",
        encoding="utf-8",
    )
    (reports_dir / "multilayer_evidence_graph_contract.md").write_text(
        "# Multi-Layer Evidence Graph Contract\n\n"
        "Layers: strict_causal_core, causal_reviewable, intervention_observation, rescue_supported, association, differential_expression, context_only, audit_rejected. Only strict_causal_core is formal conflict and formal hypothesis eligible. Non-core layers remain display/review evidence and carry core exclusion reasons.\n",
        encoding="utf-8",
    )


def reproject_run(run_dir: str | Path, *, reports_dir: str | Path = "reports") -> dict[str, Any]:
    run = Path(run_dir)
    reports = Path(reports_dir)
    reports.mkdir(parents=True, exist_ok=True)
    artifacts = run / "artifacts"
    old_core = _jsonl(artifacts / "l2_core_graph_observations.jsonl")
    lineages = [_lineage(row) for row in old_core]
    counts = Counter(row["new_layer"] for row in lineages)
    safety = _safety_metrics(lineages)
    direction_report = {
        "direction_provenance_consistency": {
            "checked_count": len(lineages),
            "conflict_count": sum("direction_provenance_inconsistent" in row["core_exclusion_reasons"] for row in lineages),
            "explained_inversion_count": sum(row["derivation_provenance"] in {"loss_of_function_sign_inversion", "rescue_restoration_inference"} for row in lineages),
        },
        "lineages": lineages,
    }
    result = {
        "schema_version": "intervention_semantics_reprojection_v1",
        "run_dir": str(run),
        "offline_call_accounting": {
            "abstract_l1_calls": 0,
            "retrieval_calls": 0,
            "download_calls": 0,
            "llm_cleaner_calls": 0,
            "provider_network_calls": 0,
        },
        "layer_counts": dict(counts),
        "safety_metrics": safety,
        "lineages": lineages,
    }
    atomic_write_json(reports / "emt_v6_semantics_reprojection.json", result)
    atomic_write_json(reports / "core_semantics_safety_metrics.json", safety)
    atomic_write_json(reports / "direction_provenance_consistency.json", direction_report)
    _write_markdown(reports / "emt_v6_core_before_after.md", lineages, counts)
    _write_contract_reports(reports)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args(argv)
    result = reproject_run(args.run_dir, reports_dir=args.reports_dir)
    print(json.dumps({k: result[k] for k in ("offline_call_accounting", "layer_counts", "safety_metrics")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
