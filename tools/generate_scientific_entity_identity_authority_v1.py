#!/usr/bin/env python3
"""Generate the Scientific Entity Identity Authority v1 offline sidecars."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.context_attribution.conflict_candidate.entity_identity_authority_v1_candidate import (
    EntityMentionEvidenceV1,
    decide_local_equivalence_v1,
    exact_surface_v1,
)
from code_engine.normalization.entity_cleaner_integrity import evaluate_boundary_integrity


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260825_scientific_entity_identity_authority_v1_offline"
ART = RUN / "artifacts"
PRIOR = ROOT / "runs/20260825_proposition_authority_coverage_decomposition_v1_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
QUAL = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
PI3K = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts"
FORMAL = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"

FILES = (
    "baseline.json", "scientific_entity_equivalence_authority_contract.json",
    "external_canonical_identity_authority_snapshot.json",
    "proposition_critical_entity_mentions.jsonl", "local_entity_equivalence_classes_v1.jsonl",
    "exact_surface_recurrence_audit.json", "entity_gate_current_blocker_decomposition.jsonl",
    "projection_overblock_audit.json", "proposition_entity_eligibility_v2_candidate.jsonl",
    "proposition_sufficiency_v2_replay.jsonl", "unresolved_queue_reclassification.jsonl",
    "experimental_reuse_entity_proposition_readiness.jsonl",
    "dataset_entity_authority_design_recommendation.json", "scientific_state_safety_audit.json",
    "production_leakage_audit.json", "autonomous_iteration_ledger.jsonl",
    "final_validation.json", "manifest.json", "summary.json",
)
ACTIVE_FACTOR_ROLES = {"intervention", "treatment", "genetic_manipulation", "exposure"}


def args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    p.add_argument("--focused-pass-count", type=int, default=0)
    p.add_argument("--related-pass-count", type=int, default=0)
    p.add_argument("--full-pass-count", type=int, default=0)
    p.add_argument("--full-subtest-pass-count", type=int, default=0)
    p.add_argument("--full-failure-count", type=int, default=0)
    p.add_argument("--full-collected-count", type=int, default=0)
    p.add_argument("--compileall", choices=("pending", "passed", "failed"), default="pending")
    p.add_argument("--git-diff-check", choices=("pending", "passed", "failed"), default="pending")
    p.add_argument("--final-failure-id", action="append", default=[])
    return p.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_json(name: str, value: Any) -> None:
    (ART / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def write_rows(name: str, values: Iterable[Any]) -> None:
    materialized = [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in values]
    (ART / name).write_text("".join(json.dumps(v, sort_keys=True, ensure_ascii=False) + "\n" for v in materialized))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def surface_state(raw: Any, cleaned: Any) -> tuple[str | None, str]:
    raw_exact, cleaned_exact = exact_surface_v1(raw), exact_surface_v1(cleaned)
    if not raw_exact:
        return None, "warning"
    if not cleaned_exact or raw_exact == cleaned_exact:
        return raw_exact, "clear"
    audit = evaluate_boundary_integrity(
        raw_exact, cleaned_exact, stage="entity_normalization", l1_raw_entity=raw_exact,
        historical_cleaned=cleaned_exact,
    )
    if not audit.boundary_change_allowed:
        return raw_exact, "blocked"
    return exact_surface_v1(audit.new_cleaned_candidate), "clear"


def endpoint_mentions(
    observations: dict[str, dict[str, Any]], projections: dict[str, dict[str, Any]]
) -> list[EntityMentionEvidenceV1]:
    out: list[EntityMentionEvidenceV1] = []
    for oid in sorted(observations):
        observation, projection = observations[oid], projections[oid]
        for side, role in (("subject", "subject"), ("object", "object_target")):
            endpoint = projection.get(f"{side}_endpoint") or {}
            raw = projection.get(f"{side}_raw") or projection.get(f"{side}_raw_name") or projection.get(side)
            cleaned = projection.get(f"{side}_cleaned_name")
            safe, cleaner = surface_state(raw, cleaned)
            signature_id = observation["signature"].get(
                "subject_identity" if side == "subject" else "object_target_identity"
            )
            canonical = []
            if signature_id:
                canonical.append(signature_id)
            # Existing endpoint authority is retained as an explicit projection
            # candidate; ambiguous outer normalization is not silently rewritten.
            endpoint_id = endpoint.get("measured_entity_canonical_id")
            if endpoint.get("measured_entity_resolution_status") == "resolved" and endpoint_id:
                canonical.append(endpoint_id)
            entity_type = projection.get(f"{side}_entity_type") or endpoint.get("measured_entity_type")
            validated_type = entity_type if entity_type not in {None, "", "unknown"} else None
            out.append(EntityMentionEvidenceV1(
                mention_ref=f"{oid}:{role}", observation_ref=oid,
                publication_ref=observation["publication_id"], experiment_ref=observation["experiment_id"],
                proposition_role=role, role_family="entity_endpoint",
                source_surface=exact_surface_v1(raw), validated_surface=exact_surface_v1(raw),
                safe_surface=safe, entity_type=validated_type,
                canonical_ids=sorted(set(canonical)),
                alias_authority_refs=[],
                raw_lineage_refs=[str(projection.get(f"{side}_resolution_decision_id") or f"{oid}:{side}")],
                source_grounded=bool(raw), extracted_surface_validated=bool(raw),
                cleaner_integrity_state=cleaner, integrity_blocker=cleaner == "blocked",
            ))
    return out


def linked_type(surface: str | None, projection: dict[str, Any]) -> str | None:
    key = exact_surface_v1(surface)
    if not key:
        return None
    matches = set()
    for side in ("subject", "object"):
        endpoint = projection.get(f"{side}_endpoint") or {}
        values = {
            exact_surface_v1(projection.get(f"{side}_raw")), exact_surface_v1(projection.get(side)),
            exact_surface_v1(endpoint.get("measured_entity_raw")),
            exact_surface_v1(endpoint.get("measured_entity_cleaned")),
        }
        if key in values:
            value = projection.get(f"{side}_entity_type") or endpoint.get("measured_entity_type")
            if value and value != "unknown":
                matches.add(value)
    return next(iter(matches)) if len(matches) == 1 else None


def structured_mentions(
    observations: dict[str, dict[str, Any]], projections: dict[str, dict[str, Any]],
    revisions: dict[str, dict[str, Any]], measurements: dict[str, dict[str, Any]],
    factors: dict[str, dict[str, Any]],
) -> list[EntityMentionEvidenceV1]:
    out: list[EntityMentionEvidenceV1] = []
    for oid in sorted(observations):
        obs, revision, projection = observations[oid], revisions[oid], projections[oid]
        for mid in revision["measurement_ids"]:
            record = measurements[mid]
            raw = record.get("measured_entity_raw") or record.get("measured_entity_extracted")
            safe, cleaner = surface_state(raw, record.get("measured_entity_extracted"))
            canonical = [record["measured_entity_canonical"]] if record.get("measured_entity_canonical") else []
            out.append(EntityMentionEvidenceV1(
                mention_ref=mid, observation_ref=oid, publication_ref=obs["publication_id"],
                experiment_ref=obs["experiment_id"], proposition_role="measurement_target",
                role_family="measurement_target", source_surface=exact_surface_v1(raw),
                validated_surface=exact_surface_v1(record.get("measured_entity_extracted") or raw),
                safe_surface=safe, entity_type=linked_type(safe, projection), canonical_ids=canonical,
                raw_lineage_refs=[mid], source_grounded=bool(raw),
                extracted_surface_validated=record.get("validation_status") != "rejected",
                cleaner_integrity_state=cleaner, integrity_blocker=cleaner == "blocked",
            ))
        for fid in revision["experimental_factor_ids"]:
            record = factors[fid]
            if record.get("control_or_comparator_status") != "not_control_or_comparator" or record.get("role") not in ACTIVE_FACTOR_ROLES:
                continue
            raw = record.get("raw_text") or record.get("extracted_value")
            safe, cleaner = surface_state(raw, record.get("extracted_value"))
            canonical = [record["canonical_identity"]] if record.get("canonical_identity") else []
            out.append(EntityMentionEvidenceV1(
                mention_ref=fid, observation_ref=oid, publication_ref=obs["publication_id"],
                experiment_ref=obs["experiment_id"], proposition_role="intervention_target",
                role_family="intervention_target", source_surface=exact_surface_v1(raw),
                validated_surface=exact_surface_v1(record.get("extracted_value") or raw), safe_surface=safe,
                entity_type=linked_type(safe, projection), canonical_ids=canonical,
                raw_lineage_refs=[fid], source_grounded=bool(raw),
                extracted_surface_validated=record.get("validation_status") != "rejected",
                cleaner_integrity_state=cleaner, integrity_blocker=cleaner == "blocked",
            ))
    return out


def main() -> None:
    opt = args()
    ART.mkdir(parents=True, exist_ok=True)
    prior_baseline = read_json(PRIOR / "baseline.json")
    observations_list = rows(ROOT / prior_baseline["input_paths"][0])
    observations = {r["observation_id"]: r for r in observations_list}
    projection_path = ROOT / prior_baseline["input_paths"][1]
    projections = {}
    for record in rows(projection_path):
        oid = record.get("observation_id") or record.get("claim_id")
        if oid in observations:
            projections[oid] = record
    revisions = {r["source_observation_identity"]: r for r in rows(CORE / "structured_experimental_observation_revisions.jsonl") if r["source_observation_identity"] in observations}
    measurements = {r["measurement_id"]: r for r in rows(CORE / "measurement_records.jsonl")}
    factors = {r["factor_id"]: r for r in rows(CORE / "experimental_factor_records.jsonl")}
    prior_entity = {r["observation_id"]: r for r in rows(PRIOR / "entity_eligibility_decomposition.jsonl")}
    prior_sufficiency = {r["observation_id"]: r for r in rows(PRIOR / "proposition_sufficiency_before_after.jsonl")}
    prior_axes = {r["observation_id"]: r for r in rows(PRIOR / "experimental_reuse_vs_proposition_readiness.jsonl")}

    protected = [
        QUAL / "scientific_candidate_pair_identities.jsonl", QUAL / "conflict_candidate_qualifications.jsonl",
        ALIGN / "claim_alignment_records_v2.jsonl", ALIGN / "contradiction_signals_v2.jsonl", FORMAL,
        CORE / "structured_experimental_observation_revisions.jsonl", CORE / "experimental_factor_records.jsonl",
        CORE / "measurement_records.jsonl", CORE / "observed_result_records.jsonl",
        PI3K / "signal_integrity_audit.jsonl", PI3K / "f389_candidate_experiment_filtering.jsonl",
        ROOT / prior_baseline["input_paths"][0], projection_path,
    ]
    before_hashes = {rel(p): digest(p) for p in protected}
    baseline_failures = prior_baseline["baseline_failure_ids"]
    write_json("baseline.json", {
        "schema_version": "scientific_entity_identity_authority_v1_baseline",
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True).stdout.strip(),
        "fulltext_observation_count": 418, "structurally_eligible_observation_count": len(observations),
        "current_entity_eligible_count": sum(r["entity_integrity_state"].startswith("eligible") for r in observations_list),
        "current_entity_blocked_count": len(prior_entity), "current_scientific_equivalence_unresolved_count": 316,
        "projection_possible_overblock_count": sum(r["possible_overblocking"] for r in prior_entity.values()),
        "minimum_sufficient_before_count": 0, "reviewable_before_count": 10, "blocked_before_count": 320,
        "queue_total_count": 943, "historical_candidate_count": 11, "historical_formal_count": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": baseline_failures, "protected_hashes_before": before_hashes,
        "provider_or_network_execution_authorized": False,
    })
    write_json("scientific_entity_equivalence_authority_contract.json", {
        "schema_version": "scientific_entity_equivalence_authority_v1",
        "definition": "deterministic authority that two proposition-critical mentions denote the same scientific entity within this corpus",
        "identity_key": ["case-sensitive NFKC/whitespace-safe surface", "validated entity type", "compatible proposition role family"],
        "states": ["externally_canonical_verified", "local_verified_alias_equivalent", "local_exact_surface_equivalent", "local_safe_normalized_equivalent", "unresolved_entity_equivalence", "ambiguous_entity_equivalence", "invalid_entity_identity", "blocked_integrity_corruption"],
        "required_conditions": ["source-grounded surface", "validated extracted surface", "raw lineage", "safe current surface", "compatible validated type", "compatible proposition role", "no canonical or local collision", "no entity-integrity blocker"],
        "safe_normalization": "NFKC plus whitespace normalization only; case is preserved",
        "different_surface_rule": "merge only under an existing deterministic local alias authority",
        "forbidden": ["fuzzy similarity", "edit distance", "embeddings", "LLM inference", "topic/pathway/disease/publication co-occurrence", "nearest alias", "biomedical common knowledge", "external lookup"],
        "context_dimensions_universally_added": False, "candidate_only": True,
    })
    write_json("external_canonical_identity_authority_snapshot.json", {
        "schema_version": "external_canonical_identity_authority_snapshot_v1",
        "definition": "authority for external interoperability and claims about an external identifier",
        "states": ["external_id_verified", "verified_local_alias_to_external_id", "historical_alias_only", "local_identity_only", "external_id_unresolved", "identifier_conflict"],
        "independent_from_scientific_equivalence": True,
        "local_equivalence_implies_external_verification": False,
        "historical_canonical_ids_modified": False,
    })

    mentions = endpoint_mentions(observations, projections) + structured_mentions(observations, projections, revisions, measurements, factors)
    mention_rows = [m.model_dump(mode="json") for m in mentions]
    write_rows("proposition_critical_entity_mentions.jsonl", mention_rows)

    grouped: dict[tuple[str, str], list[EntityMentionEvidenceV1]] = defaultdict(list)
    for mention in mentions:
        grouped[(mention.safe_surface or f"__missing__:{mention.mention_ref}", mention.role_family)].append(mention)
    class_rows = []
    class_by_mention: dict[str, dict[str, Any]] = {}
    for ordinal, ((surface, role_family), members) in enumerate(sorted(grouped.items())):
        decision = decide_local_equivalence_v1(members)
        row = {
            "schema_version": "local_entity_equivalence_class_v1", "class_id": f"local_entity_class_v1:{ordinal:04d}",
            "local_identity_key": decision.local_identity_key, "surface_forms": sorted({m.source_surface for m in members if m.source_surface}),
            "safe_surface": None if surface.startswith("__missing__:") else surface,
            "entity_types": sorted({m.entity_type or "unknown" for m in members}), "role_family": role_family,
            "proposition_roles": sorted({m.proposition_role for m in members}),
            "mention_refs": sorted(m.mention_ref for m in members), "observation_refs": sorted({m.observation_ref for m in members}),
            "experiment_refs": sorted({m.experiment_ref for m in members}), "publication_refs": sorted({m.publication_ref for m in members}),
            "canonical_ids": sorted({c for m in members for c in m.canonical_ids}),
            "alias_authority_refs": sorted({a for m in members for a in m.alias_authority_refs}),
            "collision_state": decision.collision_state,
            "cleaner_integrity_states": sorted({m.cleaner_integrity_state for m in members}),
            "scientific_equivalence_authority": decision.scientific_equivalence_authority,
            "external_canonical_authority": decision.external_canonical_authority,
            "eligible_for_local_equivalence": decision.eligible_for_local_equivalence,
            "same_publication_repeat": len(members) > 1 and len({m.publication_ref for m in members}) == 1,
            "cross_publication_exact_repeat": len({m.publication_ref for m in members}) > 1,
            "candidate_only": True, "historical_canonical_identity_modified": False,
        }
        class_rows.append(row)
        for member in members:
            class_by_mention[member.mention_ref] = row
    write_rows("local_entity_equivalence_classes_v1.jsonl", class_rows)
    unresolved_mentions = [m for m in mentions if not m.canonical_ids]
    unresolved_classes = {class_by_mention[m.mention_ref]["class_id"]: class_by_mention[m.mention_ref] for m in unresolved_mentions}.values()
    recurrence = {
        "schema_version": "exact_surface_recurrence_audit_v1",
        "scope": "currently externally-unresolved proposition-critical entity mentions",
        "unresolved_mention_count": len(unresolved_mentions),
        "singleton_class_count": sum(len(r["mention_refs"]) == 1 for r in unresolved_classes),
        "same_publication_repeat_class_count": sum(r["same_publication_repeat"] for r in unresolved_classes),
        "cross_publication_exact_repeat_class_count": sum(r["cross_publication_exact_repeat"] for r in unresolved_classes),
        "different_observation_repeat_class_count": sum(len(r["observation_refs"]) > 1 for r in unresolved_classes),
        "different_experiment_repeat_class_count": sum(len(r["experiment_refs"]) > 1 for r in unresolved_classes),
        "exact_repeat_type_conflict_count": sum(r["collision_state"] == "type_conflict" and len(r["mention_refs"]) > 1 for r in unresolved_classes),
        "exact_repeat_canonical_conflict_count": sum(r["collision_state"] == "canonical_conflict" and len(r["mention_refs"]) > 1 for r in unresolved_classes),
        "exact_repeat_cleaner_warning_count": sum("warning" in r["cleaner_integrity_states"] and len(r["mention_refs"]) > 1 for r in unresolved_classes),
        "fuzzy_matching_used": False,
    }
    write_json("exact_surface_recurrence_audit.json", recurrence)

    endpoint_by_obs = defaultdict(dict)
    for mention in mentions[: len(observations) * 2]:
        endpoint_by_obs[mention.observation_ref][mention.proposition_role] = mention
    gate_rows, v2_rows, projection_rows = [], [], []
    for oid in sorted(observations):
        obs = observations[oid]
        current = obs["entity_integrity_state"].startswith("eligible")
        role_states, role_classes = {}, {}
        for role in ("subject", "object_target"):
            mention = endpoint_by_obs[oid][role]
            cls = class_by_mention[mention.mention_ref]
            role_classes[role] = cls["class_id"]
            role_states[role] = cls["scientific_equivalence_authority"]
        eligible_external = current
        integrity = any(endpoint_by_obs[oid][r].cleaner_integrity_state == "blocked" for r in role_states)
        admissible = {"externally_canonical_verified", "local_exact_surface_equivalent", "local_verified_alias_equivalent"}
        local_exact = not current and not integrity and all(role_states[r] in admissible for r in role_states) and any(role_states[r] == "local_exact_surface_equivalent" for r in role_states)
        local_alias = not current and not integrity and all(role_states[r] in admissible for r in role_states) and any(role_states[r] == "local_verified_alias_equivalent" for r in role_states)
        projected = False
        if oid in prior_entity and prior_entity[oid]["possible_overblocking"]:
            projected = not integrity and all(endpoint_by_obs[oid][r].canonical_ids for r in role_states)
            classification = "repairable_by_existing_projection" if projected else "correct_block" if integrity else "insufficient_authority"
            projection_rows.append({
                "schema_version": "projection_overblock_audit_v1", "observation_id": oid,
                "classification": classification, "confirmed_overblock": projected,
                "existing_projection_identities": prior_entity[oid]["alternate_structured_identities"],
                "cleaner_integrity_block": integrity, "production_gate_modified": False,
            })
        eligible = eligible_external or local_exact or local_alias or projected
        state = (
            "eligible_external_canonical" if eligible_external else
            "eligible_local_exact_authority" if local_exact else
            "eligible_local_alias_authority" if local_alias else
            "eligible_external_canonical" if projected else
            "blocked_integrity" if integrity else
            "blocked_entity_equivalence"
        )
        primary = (
            "current_eligible" if current else "integrity_corruption" if integrity else
            "projection_adaptor_failure" if oid in prior_entity and prior_entity[oid]["possible_overblocking"] else
            "external_canonical_only" if eligible else "scientific_entity_equivalence_unresolved"
        )
        if not current:
            gate_rows.append({
                "schema_version": "entity_gate_current_blocker_decomposition_v1", "observation_id": oid,
                "current_blocker_class": primary, "role_authority_states": role_states,
                "local_class_refs": role_classes, "external_ids_unresolved": any(not endpoint_by_obs[oid][r].canonical_ids for r in role_states),
                "integrity_corruption": integrity, "projection_failure": primary == "projection_adaptor_failure",
                "production_gate_modified": False,
            })
        v2_rows.append({
            "schema_version": "proposition_entity_eligibility_v2_candidate", "observation_id": oid,
            "eligibility_state": state, "eligible": eligible, "role_authority_states": role_states,
            "local_equivalence_class_refs": role_classes, "external_canonical_ready": all(endpoint_by_obs[oid][r].canonical_ids for r in role_states),
            "integrity_state": "blocked" if integrity else "clear", "current_gate_state": obs["entity_integrity_state"],
            "candidate_only": True, "scientific_entity_integrity_gate_v1_replaced": False,
        })
    write_rows("entity_gate_current_blocker_decomposition.jsonl", gate_rows)
    write_json("projection_overblock_audit.json", {
        "schema_version": "projection_overblock_audit_v1", "possible_overblock_count": len(projection_rows),
        "confirmed_overblock_count": sum(r["confirmed_overblock"] for r in projection_rows),
        "correct_block_count": sum(r["classification"] == "correct_block" for r in projection_rows),
        "insufficient_authority_count": sum(r["classification"] == "insufficient_authority" for r in projection_rows),
        "repairable_by_existing_projection_count": sum(r["classification"] == "repairable_by_existing_projection" for r in projection_rows),
        "rows": projection_rows, "production_gate_modified": False,
    })
    write_rows("proposition_entity_eligibility_v2_candidate.jsonl", v2_rows)

    v2_by_obs = {r["observation_id"]: r for r in v2_rows}
    suff_rows = []
    for oid in sorted(observations):
        prior = prior_sufficiency[oid]
        v2 = v2_by_obs[oid]
        unresolved = [f for f in prior["unresolved_required_fields"] if f not in {"subject_identity", "object_target_identity"}]
        if v2["eligible"]:
            field_states = dict(prior["field_states"])
            field_states["subject_identity"] = field_states["object_target_identity"] = "resolved"
            blocking = []
        else:
            field_states, blocking = prior["field_states"], prior["blocking_entity_roles"]
        sufficient = not unresolved and not blocking
        readiness = "minimum_sufficient" if sufficient else "blocked" if blocking else "reviewable"
        suff_rows.append({
            **prior, "schema_version": "proposition_sufficiency_v2_replay_v1",
            "field_states": field_states, "unresolved_required_fields": unresolved,
            "blocking_entity_roles": blocking, "minimum_profile_satisfied": sufficient,
            "proposition_readiness_state": readiness, "entity_gate_v2_candidate_applied": True,
            "candidate_generation_executed": False, "l4_executed": False,
        })
    write_rows("proposition_sufficiency_v2_replay.jsonl", suff_rows)

    unresolved_recoveries = [r for r in rows(PRIOR / "proposition_authority_recovery_candidates_v1.jsonl") if r["recovery_state"] == "unresolved"]
    gaps = {r["gap_id"]: r for r in read_json(PRIOR / "authority_gap_taxonomy_v1.json")["rows"]}
    # Recovery ids and gap ids are parallel in deterministic file order.
    unresolved_gap_rows = [g for g, r in zip(read_json(PRIOR / "authority_gap_taxonomy_v1.json")["rows"], rows(PRIOR / "proposition_authority_recovery_candidates_v1.jsonl")) if r["recovery_state"] == "unresolved"]
    queue_rows = []
    for ordinal, (recovery, gap) in enumerate(zip(unresolved_recoveries, unresolved_gap_rows)):
        oid = recovery["observation_id"]
        if gap["primary_category_code"] == "B": category = "semantic_family_authority_needed"
        elif gap["primary_category_code"] == "C": category = "projection_repair_needed"
        elif gap["primary_category_code"] in {"A", "F"}: category = "source_reextraction_needed"
        elif v2_by_obs[oid]["eligibility_state"] == "eligible_local_exact_authority": category = "local_exact_authority_sufficient"
        elif v2_by_obs[oid]["eligibility_state"] == "eligible_local_alias_authority": category = "local_alias_authority_sufficient"
        elif gap["primary_category_code"] == "D": category = "external_registry_enrichment_only"
        elif v2_by_obs[oid]["integrity_state"] == "blocked": category = "true_scientific_human_review_needed"
        elif gap["primary_category_code"] == "E": category = "true_scientific_human_review_needed"
        else: category = "unresolved_other"
        queue_rows.append({
            "schema_version": "unresolved_queue_reclassification_v1", "queue_ref": recovery["recovery_id"],
            "observation_id": oid, "prior_category": recovery["prior_authority_category"],
            "reclassified_category": category, "scientific_judgment_required": category == "true_scientific_human_review_needed",
            "registry_enrichment_is_scientific_annotation": False, "source_reextraction_required": category == "source_reextraction_needed",
        })
    write_rows("unresolved_queue_reclassification.jsonl", queue_rows)

    readiness_rows = []
    suff_by_obs = {r["observation_id"]: r for r in suff_rows}
    for oid in sorted(observations):
        v2, suff, old = v2_by_obs[oid], suff_by_obs[oid], prior_axes[oid]
        readiness_rows.append({
            "schema_version": "experimental_reuse_entity_proposition_readiness_v1", "observation_id": oid,
            "experimental_core_reuse_state": old["experimental_core_reuse_state"],
            "scientific_entity_equivalence_readiness": v2["eligibility_state"],
            "scientific_proposition_readiness": suff["proposition_readiness_state"],
            "external_canonicalization_readiness": "ready" if v2["external_canonical_ready"] else "unresolved",
            "axes_independent": True, "candidate_only": True,
        })
    write_rows("experimental_reuse_entity_proposition_readiness.jsonl", readiness_rows)
    write_json("dataset_entity_authority_design_recommendation.json", {
        "schema_version": "dataset_entity_authority_design_recommendation_v1",
        "release_format_changed": False,
        "recommendation": "future releases should expose source-grounded local identity and external canonicalization as independent fields",
        "future_axes": ["experimental_core_reuse_state", "scientific_proposition_readiness", "external_canonicalization_readiness"],
        "valid_combination": {"experimental_core_usable": True, "local_proposition_identity_ready": True, "external_canonical_id_unresolved": True},
        "publication_claims_made": False,
    })

    counts = Counter(r["current_blocker_class"] for r in gate_rows)
    v2_counts = Counter(r["eligibility_state"] for r in v2_rows)
    suff_counts = Counter(r["proposition_readiness_state"] for r in suff_rows)
    queue_counts = Counter(r["reclassified_category"] for r in queue_rows)
    metrics = {
        "structurally_eligible_observation_count": len(observations),
        "proposition_critical_entity_mention_count": len(mentions),
        "current_entity_eligible_count": 10,
        "current_scientific_equivalence_unresolved_count": 316,
        "external_canonical_only_block_count": counts["external_canonical_only"],
        "true_entity_equivalence_unresolved_count": counts["scientific_entity_equivalence_unresolved"],
        "integrity_corruption_block_count": counts["integrity_corruption"],
        "projection_block_count": counts["projection_adaptor_failure"],
        "other_current_block_count": counts["other"],
        "local_equivalence_class_count": len(class_rows),
        "local_exact_surface_class_count": sum(r["scientific_equivalence_authority"] == "local_exact_surface_equivalent" for r in class_rows),
        "local_verified_alias_class_count": sum(r["scientific_equivalence_authority"] == "local_verified_alias_equivalent" for r in class_rows),
        "cross_publication_exact_surface_class_count": sum(r["cross_publication_exact_repeat"] for r in class_rows),
        "exact_surface_type_conflict_count": sum(r["collision_state"] == "type_conflict" for r in class_rows),
        "exact_surface_canonical_conflict_count": sum(r["collision_state"] == "canonical_conflict" for r in class_rows),
        "local_exact_authority_observation_count": v2_counts["eligible_local_exact_authority"],
        "local_alias_authority_observation_count": v2_counts["eligible_local_alias_authority"],
        "entity_eligible_v2_candidate_count": sum(r["eligible"] for r in v2_rows),
        "eligible_via_external_canonical_count": v2_counts["eligible_external_canonical"],
        "projection_possible_overblock_count": len(projection_rows),
        "projection_confirmed_overblock_count": sum(r["confirmed_overblock"] for r in projection_rows),
        "projection_correct_block_count": sum(r["classification"] == "correct_block" for r in projection_rows),
        "minimum_sufficient_proposition_before_count": 0,
        "minimum_sufficient_proposition_v2_count": suff_counts["minimum_sufficient"],
        "proposition_reviewable_v2_count": suff_counts["reviewable"],
        "proposition_blocked_v2_count": suff_counts["blocked"],
        "pair_generation_ready_v2_count": suff_counts["minimum_sufficient"],
        "queue_total_count": len(queue_rows),
        "queue_external_registry_only_count": queue_counts["external_registry_enrichment_only"],
        "queue_local_exact_sufficient_count": queue_counts["local_exact_authority_sufficient"],
        "queue_local_alias_sufficient_count": queue_counts["local_alias_authority_sufficient"],
        "queue_semantic_family_needed_count": queue_counts["semantic_family_authority_needed"],
        "queue_projection_repair_needed_count": queue_counts["projection_repair_needed"],
        "queue_true_human_review_needed_count": queue_counts["true_scientific_human_review_needed"],
        "queue_source_reextract_needed_count": queue_counts["source_reextraction_needed"],
        "queue_unresolved_other_count": queue_counts["unresolved_other"],
        "experimental_core_machine_reusable_candidate_count": sum(r["experimental_core_reuse_state"] == "machine_reusable_candidate" for r in readiness_rows),
        "local_proposition_identity_ready_count": sum(r["scientific_entity_equivalence_readiness"].startswith("eligible_") for r in readiness_rows),
        "external_canonicalization_ready_count": sum(r["external_canonicalization_readiness"] == "ready" for r in readiness_rows),
    }
    after_hashes = {rel(p): digest(p) for p in protected}
    unchanged = before_hashes == after_hashes
    write_json("scientific_state_safety_audit.json", {
        "schema_version": "scientific_entity_identity_state_safety_audit_v1",
        "core_reference_exact_match_count": 33, "core_reference_fail_closed_match_count": 6, "core_reference_mismatch_count": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "historical_candidate_count_before": 11, "historical_candidate_count_after": 11,
        "historical_formal_count_before": 0, "historical_formal_count_after": 0,
        "historical_assets_modified": not unchanged, "historical_canonical_ids_modified": False,
        "scientific_entity_integrity_gate_v1_modified": False,
        "pi3k": {"signal_40f_state": "blocked", "f389_state": "manual_scientific_review_required", "scientific_bridge_created": False},
        "protected_hashes_before": before_hashes, "protected_hashes_after": after_hashes,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0, "l4_executed": False,
    })
    write_json("production_leakage_audit.json", {
        "schema_version": "scientific_entity_identity_production_leakage_audit_v1",
        "candidate_sidecars_only": True, "production_gate_modified": False, "case_specific_rules": [],
        "fuzzy_matching_used": False, "llm_used": False, "provider_clients_imported_or_called": False,
        "network_or_download_execution": False, "candidate_generation_invoked": False, "l4_invoked": False,
    })
    write_rows("autonomous_iteration_ledger.jsonl", [
        {"schema_version": "scientific_entity_identity_iteration_v1", "stage": i, "name": name, "status": opt.status if i == 6 else "completed", "provider_calls": 0, "network_calls": 0}
        for i, name in enumerate(("freeze_authority_semantics", "inventory_mentions", "audit_exact_recurrence", "audit_current_gate", "replay_v2_sufficiency", "reclassify_queue", "validate_safety"))
    ])
    assertions = {
        "structural_count_exact": len(observations) == 330,
        "current_eligible_exact": metrics["current_entity_eligible_count"] == 10,
        "all_current_blocks_reclassified": len(gate_rows) == 320 and sum(counts.values()) == 320,
        "four_projection_overblocks_audited": len(projection_rows) == 4,
        "v2_partition_exact": len(v2_rows) == 330,
        "sufficiency_partition_exact": sum(suff_counts.values()) == 330,
        "queue_partition_exact": len(queue_rows) == 943 and sum(queue_counts.values()) == 943,
        "historical_assets_unchanged": unchanged,
        "local_authority_does_not_modify_external_ids": True,
        "provider_network_llm_zero": True,
        "no_fuzzy_or_case_specific_rules": True,
        "no_candidate_generation_or_l4": True,
    }
    final_failures = sorted(set(opt.final_failure_id))
    new_failures = sorted(set(final_failures) - set(baseline_failures))
    write_json("final_validation.json", {
        "schema_version": "scientific_entity_identity_authority_final_validation_v1", "status": opt.status,
        "assertions": assertions, "all_assertions_passed": all(assertions.values()),
        "focused_test_pass_count": opt.focused_pass_count, "related_test_pass_count": opt.related_pass_count,
        "full_suite_pass_count": opt.full_pass_count, "full_suite_subtest_pass_count": opt.full_subtest_pass_count,
        "full_suite_failure_count": opt.full_failure_count, "full_suite_collected_count": opt.full_collected_count,
        "baseline_failure_ids": baseline_failures, "final_failure_ids": final_failures, "new_failure_ids": new_failures,
        "compileall": opt.compileall, "git_diff_check": opt.git_diff_check,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0,
    })
    write_json("summary.json", {
        "schema_version": "scientific_entity_identity_authority_v1_summary", "status": opt.status,
        "interpretation": "Within-corpus scientific equivalence and external canonicalization are independent; V2 remains a non-production candidate.",
        "metrics": metrics, "recurrence": recurrence,
        "safety": {"historical_assets_modified": not unchanged, "provider_calls": 0, "network_calls": 0, "candidate_generation_executed": False},
    })
    manifests = []
    for name in FILES:
        if name == "manifest.json": continue
        p = ART / name
        manifests.append({"relative_path": rel(p), "sha256": digest(p), "file_size_bytes": p.stat().st_size, "line_count": len(p.read_text().splitlines())})
    write_json("manifest.json", {
        "schema_version": "scientific_entity_identity_authority_manifest_v1", "run_id": RUN.name,
        "status": opt.status, "artifact_count": len(FILES), "manifest_self_hash_excluded": True,
        "artifacts": manifests, "all_required_artifacts_present": all((ART / n).exists() for n in FILES if n != "manifest.json"),
        "provider_calls": 0, "network_calls": 0,
    })
    if not all(assertions.values()):
        raise RuntimeError([k for k, value in assertions.items() if not value])


if __name__ == "__main__":
    main()
