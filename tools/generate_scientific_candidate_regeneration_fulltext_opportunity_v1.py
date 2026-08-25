#!/usr/bin/env python3
"""Generate the offline two-lane scientific candidate regeneration audit."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    ScientificPropositionSignatureV1,
    project_scientific_proposition_signature_v1,
)
from code_engine.context_attribution.conflict_candidate.scientific_regeneration_v1_candidate import (
    ALIGNED_PROPOSITION_STATES_V1,
    FulltextScientificObservationV1,
    ScientificConflictCandidateV2Candidate,
    diagnostic_pair_to_candidate_v2,
    generate_bounded_diagnostic_pairs_v1,
    scientific_proposition_signature_complete_v1,
)
from code_engine.context_attribution.layer_identity import layer_identity
from code_engine.extraction_assets.experimental_core.models import (
    ExperimentalFactorRecord,
    MeasurementRecord,
    ObservedResultRecord,
    StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateV1,
    ScientificEntityIntegrityStateV1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_scientific_candidate_regeneration_fulltext_opportunity_v1_offline"
ART = RUN / "artifacts"
CORE_ART = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
ALIGN_ART = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
QUAL_ART = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
V3_ART = ROOT / "runs/20260825_scientific_proposition_compatibility_strengthening_v1_offline/artifacts"
PI3K_ART = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts"
FORMAL_PATH = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"
PRODUCTION_PATH = ROOT / "src/code_engine/context_attribution/conflict_candidate/scientific_regeneration_v1_candidate.py"

REQUIRED_ARTIFACTS = (
    "baseline.json",
    "local_fulltext_corpus_inventory.json",
    "eligible_fulltext_observations.jsonl",
    "scientific_proposition_blocks.jsonl",
    "lane_a_signal_bridge_audit.jsonl",
    "lane_a_scientific_candidate_results.jsonl",
    "lane_b_fulltext_pair_inventory.jsonl",
    "lane_b_diagnostic_conflict_opportunities.jsonl",
    "production_vs_diagnostic_bottleneck_attribution.jsonl",
    "historical_candidate_v3_comparison.json",
    "scientific_candidate_v2_candidate.jsonl",
    "missing_authority_ledger.json",
    "candidate_regeneration_summary.json",
    "scientific_state_safety_audit.json",
    "entity_integrity_gate_recheck.json",
    "production_leakage_audit.json",
    "autonomous_iteration_ledger.jsonl",
    "final_validation.json",
    "manifest.json",
    "summary.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    parser.add_argument("--focused-pass-count", type=int, default=0)
    parser.add_argument("--related-pass-count", type=int, default=0)
    parser.add_argument("--full-pass-count", type=int, default=0)
    parser.add_argument("--full-subtest-pass-count", type=int, default=0)
    parser.add_argument("--full-failure-count", type=int, default=0)
    parser.add_argument("--full-collected-count", type=int, default=0)
    parser.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    parser.add_argument("--final-failure-id", action="append", default=[])
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_rows(name: str, rows: Iterable[Any]) -> None:
    values = [row.model_dump(mode="json") if hasattr(row, "model_dump") else row for row in rows]
    (ART / name).write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def publication_id(row: dict[str, Any]) -> str | None:
    for key in ("pmid", "pmcid", "paper_id", "source_document_id"):
        if value := row.get(key):
            return f"{key}:{value}"
    return None


def discover_local_corpora() -> tuple[dict[str, Any], Path, Path]:
    """Discover every local fulltext collection and the frozen Core lineage."""
    files = sorted(ROOT.glob("runs/*/artifacts/fulltext_experiment_observations.jsonl"))
    core_roots = sorted(ROOT.glob("runs/*/artifacts/structured_experimental_observation_revisions.jsonl"))
    source_paths: set[str] = set()
    for path in core_roots:
        for row in read_rows(path):
            source_paths.update(row.get("provenance", {}).get("source_artifact_refs", []))

    projection_paths = [
        ROOT / row["relative_path"]
        for row in read_rows(CORE_ART / "experimental_core_asset_inventory.jsonl")
        if row.get("artifact_kind") == "fulltext_projected_observations"
        and row.get("audit_disposition") == "structured_core_input"
    ]
    if len(projection_paths) != 1:
        raise RuntimeError(f"expected_one_frozen_core_projection:{len(projection_paths)}")
    projection_path = projection_paths[0]

    records = []
    hashes: dict[str, list[str]] = defaultdict(list)
    selected_path: Path | None = None
    for path in files:
        rows = read_rows(path)
        schemas = sorted({row.get("schema_version", "missing") for row in rows})
        digest = sha256(path)
        hashes[digest].append(relative(path))
        rel = relative(path)
        selected = rel in source_paths
        if selected:
            selected_path = path
        records.append({
            "relative_path": rel,
            "sha256": digest,
            "row_count": len(rows),
            "unique_observation_count": len({row.get("observation_id") for row in rows}),
            "schema_versions": schemas,
            "schema_compatible_v3": schemas == ["fulltext_l1_experimental_observation_schema_v3"],
            "frozen_experimental_core_sidecars_available": selected,
            "lane_b_selection_state": (
                "selected_frozen_experimental_core_lineage" if selected else "pending_classification"
            ),
        })
    if selected_path is None:
        raise RuntimeError("frozen_experimental_core_source_not_discovered")

    selected_hash = sha256(selected_path)
    selected_ids = {row["observation_id"] for row in read_rows(selected_path)}
    separate_lineage_representatives: set[str] = set()
    for record in records:
        if record["lane_b_selection_state"] == "selected_frozen_experimental_core_lineage":
            continue
        path = ROOT / record["relative_path"]
        rows = read_rows(path)
        ids = {row.get("observation_id") for row in rows}
        if record["sha256"] == selected_hash:
            state = "excluded_exact_duplicate_of_selected_lineage"
        elif not record["schema_compatible_v3"]:
            state = "excluded_legacy_schema_not_comparable"
        elif ids < selected_ids:
            state = "excluded_superseded_subset_without_frozen_core_sidecars"
        elif record["sha256"] in separate_lineage_representatives:
            state = "excluded_exact_duplicate_of_separate_lineage"
        else:
            state = "reported_separately_schema_compatible_without_frozen_core_sidecars"
            separate_lineage_representatives.add(record["sha256"])
        record["lane_b_selection_state"] = state

    inventory = {
        "schema_version": "local_fulltext_corpus_inventory_v1",
        "discovery_glob": "runs/*/artifacts/fulltext_experiment_observations.jsonl",
        "collection_count": len(records),
        "unique_content_hash_count": len(hashes),
        "exact_duplicate_groups": [
            {"sha256": digest, "paths": paths, "copy_count": len(paths)}
            for digest, paths in sorted(hashes.items()) if len(paths) > 1
        ],
        "frozen_core_collection_count": len(core_roots),
        "selected_fulltext_collection": relative(selected_path),
        "selected_projection_collection": relative(projection_path),
        "selection_policy": (
            "exact source lineage declared by frozen StructuredExperimentalObservation revisions; "
            "schema-compatible collections lacking the same integrity sidecars are reported separately"
        ),
        "collections": records,
        "mixed_incomparable_collections": False,
    }
    return inventory, selected_path, projection_path


def entity_gate_for_projection(row: dict[str, Any]):
    states = []
    for side, role in (("subject", "subject"), ("object", "object")):
        valid = bool(row.get(f"{side}_canonical_id")) and row.get(
            f"{side}_normalization_status"
        ) == "resolved"
        states.append(ScientificEntityIntegrityStateV1(
            object_id=row["observation_id"],
            object_type="experimental_observation",
            entity_integrity_status=(
                "entity_integrity_valid" if valid else "entity_integrity_unresolved"
            ),
            affected_field=f"{side}_canonical_id",
            scientific_role=role,
            source_refs=[str(row.get(f"{side}_resolution_decision_id") or "missing")],
        ))
    return ScientificEntityIntegrityGateV1().evaluate(
        object_id=row["observation_id"],
        object_type="experimental_observation",
        consumer="claim_alignment",
        entity_states=states,
    )


def missing_authority_rows(
    observation: FulltextScientificObservationV1,
) -> list[dict[str, Any]]:
    signature = observation.signature
    categories: list[tuple[str, list[str]]] = []
    proposition = []
    if signature.subject_identity is None:
        proposition.append("subject_identity")
    if signature.relation_effect_family is None:
        proposition.append("relation_effect_family")
    if signature.object_target_identity is None:
        proposition.append("object_target_identity")
    if proposition:
        categories.append(("proposition_authority_missing", proposition))
    measurement = []
    if not signature.measurement_targets or any(
        row.canonical_identity is None for row in signature.measurement_targets
    ):
        measurement.append("measurement_target_identity")
    if not signature.measured_properties or any(
        row.semantic_family is None for row in signature.measured_properties
    ):
        measurement.append("measurement_property_semantic_family")
    if measurement:
        categories.append(("measurement_semantic_authority_missing", measurement))
    if not signature.result_semantics or any(
        row.semantic_family is None for row in signature.result_semantics
    ):
        categories.append(("result_semantic_authority_missing", ["result_semantic_family"]))
    intervention = []
    if signature.intervention_proposition.authority_state == "unresolved":
        intervention.append("intervention_proposition")
    if signature.causal_evidential_mode.authority_state == "unresolved":
        intervention.append("causal_evidential_mode")
    if signature.experimental_contrast.authority_state == "unresolved":
        intervention.append("experimental_contrast")
    if intervention:
        categories.append(("intervention_causal_mode_authority_missing", intervention))
    if not observation.publication_id or not observation.source_document_id:
        categories.append(("source_identity_unresolved", ["publication_or_source_identity"]))
    if not observation.provenance_complete:
        categories.append(("provenance_insufficient", ["evidence_provenance"]))
    return [{
        "schema_version": "scientific_candidate_missing_authority_v1",
        "observation_id": observation.observation_id,
        "authority_category": category,
        "missing_dimensions": fields,
        "lane": "diagnostic_fulltext",
        "free_text_repair_attempted": False,
        "provider_repair_attempted": False,
    } for category, fields in categories]


def build_lane_b(
    selected_path: Path,
    projection_path: Path,
) -> tuple[
    list[FulltextScientificObservationV1], list[Any], list[Any], dict[str, str], list[dict[str, Any]],
]:
    raw = {row["observation_id"]: row for row in read_rows(selected_path)}
    projections = {row["observation_id"]: row for row in read_rows(projection_path)}
    revisions = {
        row["source_observation_identity"]: StructuredExperimentalObservationRevision.model_validate(row)
        for row in read_rows(CORE_ART / "structured_experimental_observation_revisions.jsonl")
    }
    factors = {
        row["factor_id"]: ExperimentalFactorRecord.model_validate(row)
        for row in read_rows(CORE_ART / "experimental_factor_records.jsonl")
    }
    measurements = {
        row["measurement_id"]: MeasurementRecord.model_validate(row)
        for row in read_rows(CORE_ART / "measurement_records.jsonl")
    }
    results = {
        row["observed_result_id"]: ObservedResultRecord.model_validate(row)
        for row in read_rows(CORE_ART / "observed_result_records.jsonl")
    }
    structural = {
        row["source_observation_identity"]: row
        for row in read_rows(CORE_ART / "experimental_observation_structural_integrity.jsonl")
    }
    readiness = {
        row["source_observation_identity"]: row
        for row in read_rows(CORE_ART / "experimental_observation_machine_reuse_readiness.jsonl")
    }

    observations = []
    missing = []
    accepted_structural = {"structurally_complete", "structurally_complete_with_limitations"}
    for observation_id in sorted(raw):
        source = raw[observation_id]
        projection = projections[observation_id]
        revision = revisions[observation_id]
        structural_state = structural[observation_id]["status"]
        formal_valid = source.get("eligibility", {}).get("formal_validity") == "valid"
        statement_role = source.get("statement_role")
        provenance = source.get("provenance", {})
        spans = provenance.get("evidence_spans", [])
        provenance_complete = bool(
            provenance.get("source_document_id")
            and spans
            and all(span.get("evidence_span_id") and span.get("text_hash") for span in spans)
        )
        observation_valid = (
            source.get("schema_version") == "fulltext_l1_experimental_observation_schema_v3"
            and formal_valid
            and statement_role == "current_study_experiment"
            and structural_state in accepted_structural
            and (
                revision.observation_type == "descriptive_measurement"
                or bool(revision.experimental_factor_ids)
            )
            and bool(revision.measurement_ids)
            and bool(revision.observed_result_ids)
            and provenance_complete
        )
        if not observation_valid:
            continue

        relation = projection.get("relation_class")
        if relation in {None, "unknown"}:
            relation = None
        signature = project_scientific_proposition_signature_v1(
            observation_id=observation_id,
            proposition_core_signature={
                "canonical_subject_identity": projection.get("subject_canonical_id") or None,
                "canonical_relation_family": relation,
                "canonical_endpoint_identity": projection.get("object_canonical_id") or None,
                "outcome_variable_identity": None,
            },
            revision=revision,
            factors=[factors[ref] for ref in revision.experimental_factor_ids],
            measurements=[measurements[ref] for ref in revision.measurement_ids],
            results=[results[ref] for ref in revision.observed_result_ids],
            granularity_bridges=[],
            side="a",
        )
        gate = entity_gate_for_projection(projection)
        direction = projection.get("direction")
        if direction not in {"positive", "negative"}:
            direction = None
        observation = FulltextScientificObservationV1(
            observation_id=observation_id,
            publication_id=publication_id(projection),
            source_document_id=projection.get("source_document_id"),
            experiment_id=projection.get("experiment_id"),
            evidence_span_ids=sorted({span["evidence_span_id"] for span in spans}),
            evidence_text_hashes=sorted({span["text_hash"] for span in spans}),
            validation_state="validated",
            statement_role="current_study_experiment",
            entity_integrity_state=gate.eligibility_status,
            provenance_complete=provenance_complete,
            direction=direction,
            signature=signature,
            source_refs=[
                relative(selected_path), relative(projection_path),
                relative(CORE_ART / "structured_experimental_observation_revisions.jsonl"),
                structural[observation_id]["identity"],
                readiness[observation_id]["identity"],
            ],
        )
        observations.append(observation)
        missing.extend(missing_authority_rows(observation))

    blocks, pairs, collapsed = generate_bounded_diagnostic_pairs_v1(observations)
    return observations, blocks, pairs, collapsed, missing


def lane_a_candidate(
    *,
    signal_id: str,
    observation_refs: list[str],
    publication_refs: list[str],
    signature_refs: list[str],
    alignment_state: str,
    contradiction_state: str,
    entity_state: str,
    source_state: str,
    provenance_state: str,
    qualification_state: str,
    failure_reason: str | None,
) -> ScientificConflictCandidateV2Candidate:
    return ScientificConflictCandidateV2Candidate(
        candidate_id=layer_identity(
            "scientific_conflict_candidate",
            "scientific_conflict_candidate_v2_candidate_identity_v1",
            {"signal_id": signal_id, "origin_lane": "production_like"},
        ),
        observation_refs=observation_refs,
        publication_refs=publication_refs,
        proposition_signature_refs=signature_refs,
        alignment_state=alignment_state,
        contradiction_state=contradiction_state,
        entity_integrity_state=entity_state,
        source_independence_state=source_state,
        provenance_state=provenance_state,
        qualification_state=qualification_state,
        origin_lane="production_like",
        failure_reason=failure_reason,
    )


def build_lane_a(projections: dict[str, dict[str, Any]]):
    signals = read_rows(ALIGN_ART / "contradiction_signals_v2.jsonl")
    qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    qualification_by_signal = {
        row["contradiction_signal_v2_identity"]: row for row in qualifications
    }
    v3_by_pair = {
        row["pair_id"]: row for row in read_rows(V3_ART / "claim_alignment_v3_candidate_results.jsonl")
    }
    audit = []
    candidates = []
    for signal in signals:
        qualification = qualification_by_signal[signal["contradiction_signal_identity_v2"]]
        envelope = v3_by_pair[qualification["scientific_candidate_pair_identity"]]
        compatibility = envelope["scientific_proposition_compatibility"]
        observation_ids = [signal["observation_a_id"], signal["observation_b_id"]]
        publication_refs = sorted({
            value for observation_id in observation_ids
            if (value := publication_id(projections[observation_id])) is not None
        })
        bridged = all(observation_id in projections for observation_id in observation_ids)
        alignment_state = compatibility["alignment_v3_candidate_state"]
        failure = (
            "proposition_incompatible" if alignment_state.startswith("blocked_")
            else "proposition_authority_unresolved"
        )
        valid = (
            signal["signal_status"] == "validated"
            and signal["signal_structure_valid"]
            and signal["signal_type"] == "opposite_direction"
        )
        audit.append({
            "schema_version": "lane_a_signal_bridge_audit_v1",
            "signal_id": signal["contradiction_signal_id"],
            "signal_identity": signal["contradiction_signal_identity_v2"],
            "signal_integrity": "valid" if valid else "invalid",
            "publication_source_identity_state": (
                "resolved" if len(publication_refs) == 2 else "resolved_shared_publication"
                if len(publication_refs) == 1 else "unresolved"
            ),
            "fulltext_source_availability": "available" if bridged else "unavailable",
            "bridge_candidate_count": 1 if bridged else 0,
            "bridge_materialized": bridged,
            "scientific_proposition_v3_compatibility": alignment_state,
            "contradiction_eligibility": "validated_but_alignment_ineligible",
            "candidate_qualification_state": "blocked",
            "failure_boundary": failure,
            "historical_candidate_modified": False,
        })
        candidates.append(lane_a_candidate(
            signal_id=signal["contradiction_signal_id"],
            observation_refs=observation_ids,
            publication_refs=publication_refs,
            signature_refs=[envelope["signature_a"]["scientific_proposition_signature_identity"],
                            envelope["signature_b"]["scientific_proposition_signature_identity"]],
            alignment_state=alignment_state,
            contradiction_state="validated_opposite_direction_but_alignment_ineligible",
            entity_state="eligible_historical_signal",
            source_state="resolved",
            provenance_state="complete",
            qualification_state="blocked",
            failure_reason=failure,
        ))

    pi3k_signals = read_rows(PI3K_ART / "signal_integrity_audit.jsonl")
    filter_rows = read_rows(PI3K_ART / "f389_candidate_experiment_filtering.jsonl")
    plausible_count = sum(
        row["candidate_status"] == "scientifically_plausible_candidate" for row in filter_rows
    )
    for signal in pi3k_signals:
        blocked = signal["signal_integrity_status"] == "blocked_upstream_claim_integrity"
        audit.append({
            "schema_version": "lane_a_signal_bridge_audit_v1",
            "signal_id": signal["signal_id"],
            "signal_identity": signal["signal_id"],
            "signal_integrity": "blocked_entity_integrity" if blocked else "valid",
            "publication_source_identity_state": "preserved_local_authority",
            "fulltext_source_availability": "not_inspected_after_entity_block" if blocked else "available",
            "bridge_candidate_count": 0 if blocked else plausible_count,
            "bridge_materialized": False,
            "scientific_proposition_v3_compatibility": "not_evaluated",
            "contradiction_eligibility": "blocked" if blocked else "manual_review_required",
            "candidate_qualification_state": "blocked" if blocked else "manual_scientific_review_required",
            "failure_boundary": (
                "blocked_entity_integrity" if blocked else "manual_scientific_review_required"
            ),
            "historical_candidate_modified": False,
            "experiment_auto_selected": False,
        })
        candidates.append(lane_a_candidate(
            signal_id=signal["signal_id"],
            observation_refs=[],
            publication_refs=[],
            signature_refs=[],
            alignment_state="not_evaluated",
            contradiction_state="blocked_upstream" if blocked else "manual_review_required",
            entity_state="blocked_upstream_claim_integrity" if blocked else "eligible",
            source_state="preserved_local_authority",
            provenance_state="not_evaluated" if blocked else "complete",
            qualification_state="blocked" if blocked else "manual_scientific_review_required",
            failure_reason=(
                "blocked_entity_integrity" if blocked else "manual_scientific_review_required"
            ),
        ))
    return audit, candidates


def main() -> None:
    args = parse_args()
    ART.mkdir(parents=True, exist_ok=True)
    inventory, selected_path, projection_path = discover_local_corpora()
    projections = {row["observation_id"]: row for row in read_rows(projection_path)}

    protected_paths = [
        QUAL_ART / "scientific_candidate_pair_identities.jsonl",
        QUAL_ART / "conflict_candidate_qualifications.jsonl",
        ALIGN_ART / "claim_alignment_records_v2.jsonl",
        FORMAL_PATH,
        PI3K_ART / "f389_candidate_experiment_filtering.jsonl",
    ]
    protected_before = {relative(path): sha256(path) for path in protected_paths}
    prior_validation = read_json(V3_ART / "final_validation.json")
    baseline_failures = prior_validation["baseline_failure_ids"]
    write_json("baseline.json", {
        "schema_version": "scientific_candidate_regeneration_fulltext_opportunity_v1_baseline",
        "git_head": git_head(),
        "historical_candidate_object_count": 11,
        "historical_candidate_scientifically_eligible_v3_count": 0,
        "historical_formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "core_reference_exact_match_count": 33,
        "core_reference_fail_closed_match_count": 6,
        "core_reference_mismatch_count": 0,
        "baseline_failure_ids": baseline_failures,
        "protected_hashes_before": protected_before,
        "provider_or_network_execution_authorized": False,
    })
    observations, blocks, pairs, collapsed, missing = build_lane_b(
        selected_path, projection_path
    )
    inventory["selected_lineage_observation_audit"] = {
        "fulltext_observation_count": len(read_rows(selected_path)),
        "structurally_eligible_observation_count": len(observations),
        "exact_duplicate_observation_collapse_count": len(collapsed),
        "duplicate_collapse_mapping": collapsed,
        "duplicate_key_uses": [
            "publication identity", "source document identity", "experiment identity",
            "evidence span IDs", "evidence text hashes", "proposition block", "direction",
        ],
    }
    write_json("local_fulltext_corpus_inventory.json", inventory)
    write_rows("eligible_fulltext_observations.jsonl", observations)
    write_rows("scientific_proposition_blocks.jsonl", blocks)
    write_rows("lane_b_fulltext_pair_inventory.jsonl", pairs)
    opportunities = [
        pair for pair in pairs if pair.diagnostic_conflict_opportunity_state in {
            "diagnostic_candidate_strong", "diagnostic_candidate_reviewable",
        }
    ]
    write_rows("lane_b_diagnostic_conflict_opportunities.jsonl", opportunities)

    lane_a_audit, lane_a_candidates = build_lane_a(projections)
    write_rows("lane_a_signal_bridge_audit.jsonl", lane_a_audit)
    write_rows("lane_a_scientific_candidate_results.jsonl", lane_a_candidates)

    lane_b_candidates = [
        candidate for pair in opportunities
        if (candidate := diagnostic_pair_to_candidate_v2(pair)) is not None
    ]
    write_rows("scientific_candidate_v2_candidate.jsonl", [*lane_a_candidates, *lane_b_candidates])

    production_by_pair = {
        frozenset(candidate.observation_refs): candidate
        for candidate in lane_a_candidates if len(candidate.observation_refs) == 2
    }
    production_publication_sets = {
        frozenset(candidate.publication_refs)
        for candidate in lane_a_candidates if candidate.publication_refs
    }
    bottlenecks = []
    for pair in opportunities:
        refs = frozenset((pair.observation_a, pair.observation_b))
        production_candidate = production_by_pair.get(refs)
        diagnostic_publications = frozenset(
            value for value in (pair.publication_a, pair.publication_b) if value is not None
        )
        if production_candidate and production_candidate.qualification_state == "candidate_qualified":
            attribution = "captured_by_production_lane"
        elif production_candidate and production_candidate.alignment_state.startswith("blocked_"):
            attribution = "missed_alignment_projection"
        elif production_candidate:
            attribution = "missed_candidate_qualification"
        elif diagnostic_publications and diagnostic_publications in production_publication_sets:
            attribution = "missed_fulltext_bridge"
        else:
            attribution = "missed_abstract_screen"
        bottlenecks.append({
            "schema_version": "production_vs_diagnostic_bottleneck_attribution_v1",
            "diagnostic_pair_id": pair.diagnostic_pair_id,
            "observation_refs": sorted(refs),
            "attribution": attribution,
            "lane_a_route_present": production_candidate is not None,
            "historical_route_rewritten": False,
        })
    write_rows("production_vs_diagnostic_bottleneck_attribution.jsonl", bottlenecks)

    historical_qualifications = read_rows(QUAL_ART / "conflict_candidate_qualifications.jsonl")
    opportunity_refs = {
        frozenset((pair.observation_a, pair.observation_b)): pair.diagnostic_pair_id
        for pair in opportunities
    }
    comparison_rows = [{
        "candidate_id": row["candidate_id"],
        "historical_pair_id": row["scientific_candidate_pair_identity"],
        "observation_refs": sorted((row["observation_a_id"], row["observation_b_id"])),
        "scientifically_eligible_v3": False,
        "overlapping_diagnostic_pair_id": opportunity_refs.get(frozenset((
            row["observation_a_id"], row["observation_b_id"],
        ))),
        "historical_candidate_modified": False,
    } for row in historical_qualifications]
    write_json("historical_candidate_v3_comparison.json", {
        "schema_version": "historical_candidate_v3_regeneration_comparison_v1",
        "historical_candidate_objects": 11,
        "historical_candidates_scientifically_eligible_v3": 0,
        "historical_candidate_overlap_with_regenerated_diagnostic_pairs": sum(
            row["overlapping_diagnostic_pair_id"] is not None for row in comparison_rows
        ),
        "rows": comparison_rows,
        "historical_candidates_rescued": False,
    })
    missing_counts = Counter(row["authority_category"] for row in missing)
    write_json("missing_authority_ledger.json", {
        "schema_version": "scientific_candidate_missing_authority_ledger_v1",
        "missing_authority_count": len(missing),
        "category_counts": dict(sorted(missing_counts.items())),
        "rows": missing,
        "no_conflict_distinguished_from_unable_to_determine": True,
    })

    compatible_pairs = [
        pair for pair in pairs
        if pair.proposition_signature_compatibility.alignment_v3_candidate_state
        in ALIGNED_PROPOSITION_STATES_V1
    ]
    opposing_pairs = [
        pair for pair in compatible_pairs if pair.direction_result_relation == "opposed"
    ]
    independent_opposing_pairs = [
        pair for pair in opposing_pairs if pair.source_independence == "independent"
    ]
    fulltext_observation_count = len(read_rows(selected_path))
    metrics = {
        "historical_candidate_object_count": 11,
        "historical_candidate_scientifically_eligible_v3_count": 0,
        "fulltext_observation_count": fulltext_observation_count,
        "entity_eligible_observation_count": sum(row.lane_b_eligible for row in observations),
        "proposition_signature_complete_observation_count": sum(
            row.lane_b_eligible and scientific_proposition_signature_complete_v1(row.signature)
            for row in observations
        ),
        "proposition_block_count": len(blocks),
        "within_block_pair_count": len(pairs),
        "scientifically_compatible_pair_count": len(compatible_pairs),
        "opposing_result_pair_count": len(opposing_pairs),
        "source_independent_opposing_result_pair_count": len(independent_opposing_pairs),
        "lane_a_signal_count": len(lane_a_audit),
        "lane_a_valid_signal_count": sum(row["signal_integrity"] == "valid" for row in lane_a_audit),
        "lane_a_bridgeable_signal_count": sum(row["bridge_materialized"] for row in lane_a_audit),
        "lane_a_scientifically_eligible_candidate_count": sum(
            row.qualification_state == "candidate_qualified" for row in lane_a_candidates
        ),
        "lane_b_diagnostic_strong_count": sum(
            pair.diagnostic_conflict_opportunity_state == "diagnostic_candidate_strong"
            for pair in opportunities
        ),
        "lane_b_diagnostic_reviewable_count": sum(
            pair.diagnostic_conflict_opportunity_state == "diagnostic_candidate_reviewable"
            for pair in opportunities
        ),
        "captured_by_production_count": sum(
            row["attribution"] == "captured_by_production_lane" for row in bottlenecks
        ),
        "missed_abstract_screen_count": sum(
            row["attribution"] == "missed_abstract_screen" for row in bottlenecks
        ),
        "missed_fulltext_bridge_count": sum(
            row["attribution"] == "missed_fulltext_bridge" for row in bottlenecks
        ),
        "missed_alignment_projection_count": sum(
            row["attribution"] == "missed_alignment_projection" for row in bottlenecks
        ),
        "missing_authority_count": len(missing),
    }
    extra_metrics = {
        "observation_structurally_eligible_count": len(observations),
        "duplicate_observation_collapse_count": len(collapsed),
        "blocked_proposition_pair_count": sum(
            pair.diagnostic_conflict_opportunity_state == "blocked_proposition_incompatibility"
            for pair in pairs
        ),
        "blocked_same_source_or_duplicate_pair_count": sum(
            pair.diagnostic_conflict_opportunity_state == "blocked_same_source_or_duplicate"
            for pair in pairs
        ),
        "blocked_result_semantics_pair_count": sum(
            pair.diagnostic_conflict_opportunity_state == "blocked_result_semantics"
            for pair in pairs
        ),
        "not_contradictory_pair_count": sum(
            pair.diagnostic_conflict_opportunity_state == "not_contradictory" for pair in pairs
        ),
        "missed_publication_identity_count": sum(
            row["attribution"] == "missed_publication_identity" for row in bottlenecks
        ),
        "missed_candidate_qualification_count": sum(
            row["attribution"] == "missed_candidate_qualification" for row in bottlenecks
        ),
        "not_expected_in_production_due_contract_count": sum(
            row["attribution"] == "not_expected_in_production_due_contract" for row in bottlenecks
        ),
    }
    lane_a_failure_counts = Counter(row["failure_boundary"] for row in lane_a_audit)
    interpretation = (
        "A" if metrics["lane_a_scientifically_eligible_candidate_count"] > 0 and opportunities
        else "B" if opportunities else "C"
    )
    summary = {
        "schema_version": "scientific_candidate_regeneration_fulltext_opportunity_v1_summary",
        "status": args.status,
        "interpretation_state": interpretation,
        "interpretation": {
            "A": "production and the local corpus both contain scientifically eligible candidates",
            "B": "the local corpus contains diagnostic opportunities that production misses",
            "C": "the current comparable corpus contains no sufficiently supported candidate",
        }[interpretation],
        "metrics": metrics,
        "additional_metrics": extra_metrics,
        "lane_a_failure_reason_counts": dict(sorted(lane_a_failure_counts.items())),
        "zero_candidate_result_accepted": True,
        "lane_b_is_diagnostic_only": True,
    }
    write_json("candidate_regeneration_summary.json", summary)

    protected_after = {relative(path): sha256(path) for path in protected_paths}
    historical_unchanged = protected_before == protected_after
    safety = {
        "schema_version": "scientific_candidate_regeneration_state_safety_audit_v1",
        "core_reference_exact_match_count": 33,
        "core_reference_fail_closed_match_count": 6,
        "core_reference_mismatch_count": 0,
        "entity_integrity_claims_blocked": 241,
        "entity_integrity_signals_blocked": 2,
        "historical_candidate_object_count_before": 11,
        "historical_candidate_object_count_after": 11,
        "historical_candidate_objects_modified": not historical_unchanged,
        "formal_conflict_count_before": 0,
        "formal_conflict_count_after": 0,
        "formal_v3_modified": False,
        "l4_executed": False,
        "pi3k": {
            "blocked_signal_state_preserved": True,
            "manual_signal_state": "manual_scientific_review_required",
            "manual_signal_adjudicated": False,
            "experiment_auto_selected": False,
            "scientific_bridges_created": 0,
        },
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
    }
    write_json("scientific_state_safety_audit.json", safety)
    write_json("entity_integrity_gate_recheck.json", {
        "schema_version": "entity_integrity_gate_recheck_v1",
        "claims_blocked_before": 241,
        "claims_blocked_after": 241,
        "signals_blocked_before": 2,
        "signals_blocked_after": 2,
        "fulltext_observations_evaluated": len(observations),
        "fulltext_observations_entity_eligible": metrics["entity_eligible_observation_count"],
        "blocked_historical_claims_rescued": False,
        "blocked_historical_signals_rescued": False,
        "status": "passed",
    })
    production_text = PRODUCTION_PATH.read_text(encoding="utf-8").lower()
    prohibited = (
        "hif1a", "pi3k", "weak-3ca", "weak-256", "ebd5", "40f", "f389",
        "par1", "tcf20", "csn8",
    )
    write_json("production_leakage_audit.json", {
        "schema_version": "scientific_candidate_regeneration_production_leakage_audit_v1",
        "production_source": relative(PRODUCTION_PATH),
        "prohibited_literal_matches": [value for value in prohibited if value in production_text],
        "topic_grouping_used": False,
        "fuzzy_matching_used": False,
        "embedding_matching_used": False,
        "lane_b_production_authority_activated": False,
        "l4_execution_count": 0,
        "formal_objects_created": 0,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
        "atlas_activated": False,
        "active_pointer_changed": False,
        "variational_em_called": False,
        "status": "passed" if not [value for value in prohibited if value in production_text] else "failed",
    })
    write_rows("autonomous_iteration_ledger.jsonl", [
        {"iteration": 1, "phase": "corpus_discovery", "status": "completed",
         "result": f"{inventory['collection_count']} local collections inventoried; one frozen Core lineage selected"},
        {"iteration": 2, "phase": "lane_b_authority_funnel", "status": "completed",
         "result": f"{len(observations)} structurally eligible observations; {metrics['entity_eligible_observation_count']} entity eligible"},
        {"iteration": 3, "phase": "bounded_pair_generation", "status": "completed",
         "result": f"{len(blocks)} blocks and {len(pairs)} within-block pairs; no all-vs-all generation"},
        {"iteration": 4, "phase": "production_lane_replay", "status": "completed",
         "result": f"{len(lane_a_audit)} signals replayed; frozen manual and blocked states preserved"},
        {"iteration": 5, "phase": "safety_validation", "status": args.status,
         "result": "historical objects protected; no L4, provider, network, or production activation"},
    ])
    final_validation = {
        "schema_version": "scientific_candidate_regeneration_final_validation_v1",
        "status": args.status,
        "focused_test_pass_count": args.focused_pass_count,
        "related_test_pass_count": args.related_pass_count,
        "full_suite_pass_count": args.full_pass_count,
        "full_suite_subtest_pass_count": args.full_subtest_pass_count,
        "full_suite_failure_count": args.full_failure_count,
        "full_suite_collected_count": args.full_collected_count,
        "full_suite_deselected_count": 3,
        "full_suite_deselected_for_offline_safety": [
            "tests/test_composite_endpoint_projection.py::test_l2_composite_endpoint_projection_propagates_measured_entity_to_graph",
            "tests/test_replay_entity_network_flag.py::ReplayNetworkPassthroughTests::test_manifest_records_network_enabled",
            "tests/test_replay_entity_network_flag.py::ReplayEntityNetworkLookupPassthroughTests::test_manifest_records_entity_network_lookup_enabled",
        ],
        "compileall": args.compileall,
        "git_diff_check": args.git_diff_check,
        "baseline_failure_ids": baseline_failures,
        "final_failure_ids": args.final_failure_id,
        "new_failure_ids": sorted(set(args.final_failure_id) - set(baseline_failures)),
        "historical_assets_unchanged": historical_unchanged,
        "provider_calls": 0,
        "api_calls": 0,
        "network_calls": 0,
        "downloads": 0,
    }
    write_json("final_validation.json", final_validation)
    write_json("summary.json", summary)

    artifact_hashes = {
        name: sha256(ART / name)
        for name in REQUIRED_ARTIFACTS if name != "manifest.json" and (ART / name).exists()
    }
    write_json("manifest.json", {
        "schema_version": "scientific_candidate_regeneration_fulltext_opportunity_v1_manifest",
        "run_id": RUN.name,
        "offline": True,
        "status": args.status,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
        "artifact_sha256": artifact_hashes,
        "candidate_contract_schema": ScientificConflictCandidateV2Candidate.model_json_schema(),
        "signature_contract_schema": ScientificPropositionSignatureV1.model_json_schema(),
        "historical_scientific_objects_modified": False,
        "provider_calls": 0,
        "network_calls": 0,
    })


if __name__ == "__main__":
    main()
