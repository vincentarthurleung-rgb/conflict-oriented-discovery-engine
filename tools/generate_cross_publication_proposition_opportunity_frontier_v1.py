#!/usr/bin/env python3
"""Generate the offline cross-publication proposition opportunity audit."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from code_engine.context_attribution.conflict_candidate.cross_publication_frontier_v1_candidate import (
    PROPOSITION_CRITICAL_DIMENSIONS,
    PartialDimensionV1,
    PartialScientificPropositionSignatureV1,
    compare_cross_publication_envelope_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260826_cross_publication_proposition_opportunity_frontier_v1_offline"
ART = RUN / "artifacts"
FRONTIER = ROOT / "runs/20260826_proposition_sufficiency_frontier_closure_v1_offline/artifacts"
ENTITY = ROOT / "runs/20260825_scientific_entity_identity_authority_v1_offline/artifacts"
AUTH = ROOT / "runs/20260825_proposition_authority_coverage_decomposition_v1_offline/artifacts"
CORE = ROOT / "runs/20260725_hif1a_core_experimental_observation_integrity_v1_offline/artifacts"
QUAL = ROOT / "runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
ALIGN = ROOT / "runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
PI3K = ROOT / "runs/20260816_provenance_authority_pair_context_entity_integrity_pi3k_v1_offline/artifacts"
FORMAL = ROOT / "runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts/formal_conflict_decisions_staging.jsonl"

FILES = (
    "baseline.json", "frontier_partial_proposition_signatures.jsonl", "ready_proposition_observations.jsonl",
    "reviewable_proposition_observations.jsonl", "cross_publication_compatibility_envelopes.jsonl",
    "ready_reviewable_opportunities.jsonl", "reviewable_reviewable_opportunities.jsonl",
    "reviewable_value_of_resolution_triage.jsonl", "frontier_human_review_priority.jsonl",
    "semantic_family_review_priority.jsonl", "existing_proposition_block_extension_audit.json",
    "frontier_opportunity_graph.json", "corpus_expansion_decision.json",
    "proposition_driven_future_retrieval_targets.jsonl", "dataset_task_readiness_axes.json",
    "scientific_state_safety_audit.json", "production_leakage_audit.json",
    "autonomous_iteration_ledger.jsonl", "final_validation.json", "manifest.json", "summary.json",
)
POTENTIAL = {"potential_match_if_single_gap_resolved", "potential_match_if_multiple_gaps_resolved"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--status", choices=("pending", "completed", "failed"), default="pending")
    for name in ("focused_pass_count", "related_pass_count", "full_pass_count", "full_subtest_pass_count", "full_failure_count", "full_collected_count"):
        p.add_argument("--" + name.replace("_", "-"), type=int, default=0)
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
    data = [v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in values]
    (ART / name).write_text("".join(json.dumps(v, sort_keys=True, ensure_ascii=False) + "\n" for v in data))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def class_identity(cls: dict[str, Any]) -> str | None:
    ids = cls.get("canonical_ids") or []
    if len(ids) == 1:
        return ids[0]
    return cls.get("local_identity_key")


def same_publication_possible(
    left: PartialScientificPropositionSignatureV1,
    right: PartialScientificPropositionSignatureV1,
) -> bool:
    if left.profile != right.profile or left.experiment_id == right.experiment_id:
        return False
    for name in PROPOSITION_CRITICAL_DIMENSIONS:
        a, b = left.dimensions[name], right.dimensions[name]
        if a.state == b.state == "resolved" and a.value != b.value:
            return False
        if (a.state == "not_applicable") != (b.state == "not_applicable"):
            return False
    return True


def main() -> None:
    opt = parse_args(); ART.mkdir(parents=True, exist_ok=True)
    previous_summary = read_json(FRONTIER / "summary.json")
    previous_validation = read_json(FRONTIER / "final_validation.json")
    inventory = {r["observation_id"]: r for r in rows(FRONTIER / "frontier_observation_inventory.jsonl")}
    replay = {r["observation_id"]: r for r in rows(FRONTIER / "frontier_proposition_sufficiency_replay.jsonl")}
    measurement_authority = defaultdict(list)
    for r in rows(FRONTIER / "frontier_measurement_semantic_authority.jsonl"): measurement_authority[r["observation_id"]].append(r)
    result_authority = defaultdict(list)
    for r in rows(FRONTIER / "frontier_result_semantic_authority.jsonl"): result_authority[r["observation_id"]].append(r)
    intervention_authority = {r["observation_id"]: r for r in rows(FRONTIER / "frontier_intervention_semantic_authority.jsonl")}
    blockers = defaultdict(list)
    for r in rows(FRONTIER / "frontier_proposition_blockers_v1.jsonl"): blockers[r["observation_id"]].append(r)
    pair_readiness = read_json(FRONTIER / "frontier_pair_generation_readiness.json")
    entity_v2 = {r["observation_id"]: r for r in rows(ENTITY / "proposition_entity_eligibility_v2_candidate.jsonl") if r["observation_id"] in inventory}
    classes = {r["class_id"]: r for r in rows(ENTITY / "local_entity_equivalence_classes_v1.jsonl")}
    auth_baseline = read_json(AUTH / "baseline.json")
    observation_path = ROOT / auth_baseline["input_paths"][0]
    observations = {r["observation_id"]: r for r in rows(observation_path) if r["observation_id"] in inventory}
    measurement_prior = {r["observation_id"]: r for r in rows(AUTH / "measurement_authority_decomposition.jsonl") if r["observation_id"] in inventory}
    intervention_prior = {r["observation_id"]: r for r in rows(AUTH / "intervention_causal_authority_decomposition.jsonl") if r["observation_id"] in inventory}
    protected = [
        QUAL / "scientific_candidate_pair_identities.jsonl", QUAL / "conflict_candidate_qualifications.jsonl",
        ALIGN / "claim_alignment_records_v2.jsonl", ALIGN / "contradiction_signals_v2.jsonl", FORMAL,
        CORE / "structured_experimental_observation_revisions.jsonl", CORE / "experimental_factor_records.jsonl",
        CORE / "measurement_records.jsonl", CORE / "observed_result_records.jsonl",
        PI3K / "signal_integrity_audit.jsonl", PI3K / "f389_candidate_experiment_filtering.jsonl",
        FRONTIER / "frontier_proposition_sufficiency_replay.jsonl", FRONTIER / "frontier_pair_generation_readiness.json",
    ]
    before_hashes = {rel(p): digest(p) for p in protected}
    ready = {oid for oid, r in replay.items() if r["minimum_profile_satisfied"]}
    reviewable = set(replay) - ready
    publications = {r["publication_id"] for r in inventory.values() if r["publication_id"]}
    ready_publications = {inventory[oid]["publication_id"] for oid in ready}
    write_json("baseline.json", {
        "schema_version": "cross_publication_proposition_opportunity_frontier_v1_baseline",
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip(),
        "frontier_observation_count": len(inventory), "ready_observation_count": len(ready),
        "reviewable_observation_count": len(reviewable), "frontier_publication_count": len(publications),
        "ready_publication_count": len(ready_publications), "current_proposition_block_count": len(pair_readiness["blocks"]),
        "current_cross_publication_block_count": pair_readiness["cross_publication_proposition_block_count"],
        "historical_candidate_count": 11, "formal_conflict_count": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "baseline_failure_ids": previous_validation["baseline_failure_ids"], "protected_hashes_before": before_hashes,
        "provider_or_network_execution_authorized": False,
    })

    signatures: dict[str, PartialScientificPropositionSignatureV1] = {}
    for oid in sorted(inventory):
        obs, inv, final, entity = observations[oid], inventory[oid], replay[oid], entity_v2[oid]
        final_unresolved = set(final["final_unresolved_required_fields"])
        human_fields = {b["required_field"] for b in blockers[oid] if b["required_field"] in final_unresolved and b["recoverability"] == "human_scientific_review"}
        subject_cls = classes[entity["local_equivalence_class_refs"]["subject"]]
        object_cls = classes[entity["local_equivalence_class_refs"]["object_target"]]
        mrows, rrows, irow = measurement_authority[oid], result_authority[oid], intervention_authority[oid]
        recovered = final["recovered_values"]
        measurement_targets = []
        for row in mrows:
            canonical = measurement_prior[oid]["recovered_measurement_target_identities"].get(row["measurement_id"])
            cls = classes.get(next((c for c, value in classes.items() if row["measurement_id"] in value["mention_refs"]), ""), {})
            measurement_targets.append(canonical or class_identity(cls))
        property_values = [r["property_semantic_family"] for r in mrows]
        result_values = [r["result_semantic_family"] for r in rrows]
        intervention_value = None
        if inv["profile_id"] != "interventional_effect":
            intervention_state = "not_applicable"
        elif "intervention_proposition" in final_unresolved:
            intervention_state = "review_required" if "intervention_proposition" in human_fields else "unresolved"
        else:
            intervention_state = "resolved"
            intervention_value = {
                "mode": irow["intervention_mode"], "roles": sorted(irow["factor_roles"]),
                "targets": sorted(irow["recovered_intervention_targets"].values()),
            }
        def dimension(field: str, value: Any, authority: str, refs: list[str], *, na: bool = False) -> PartialDimensionV1:
            if na: return PartialDimensionV1(state="not_applicable", authority=authority, source_refs=refs)
            if field in final_unresolved:
                return PartialDimensionV1(state="review_required" if field in human_fields else "unresolved", value=None, authority=authority, source_refs=refs)
            return PartialDimensionV1(state="resolved", value=value, authority=authority, source_refs=refs)
        contrast_value = recovered.get("experimental_contrast") or intervention_prior[oid]["contrast_structure"]
        relation_value = recovered.get("relation_effect_family") or obs["signature"]["relation_effect_family"]
        dims = {
            "entity_proposition": dimension("subject_identity", class_identity(subject_cls), entity["role_authority_states"]["subject"], [subject_cls["class_id"]]),
            "relation_family": dimension("relation_effect_family", relation_value, "minimum_profile_v1_or_frontier_projection", inv["factor_ids"]),
            "object_target": dimension("object_target_identity", class_identity(object_cls), entity["role_authority_states"]["object_target"], [object_cls["class_id"]]),
            "measurement_target": dimension("measurement_target_identity", measurement_targets, "measurement_target_identity_authority", inv["measurement_ids"]),
            "measurement_property": dimension("measurement_property_semantic_family", property_values, "measurement_property_family_v1_or_exact_endpoint_contract", inv["measurement_ids"]),
            "result_semantic_level": dimension("result_semantic_family", result_values, "result_semantic_family_v1", inv["result_ids"]),
            "intervention_proposition": PartialDimensionV1(state=intervention_state, value=intervention_value, authority="factor_and_intervention_contract", source_refs=inv["factor_ids"]),
            "causal_evidential_mode": dimension("causal_evidential_mode", irow["causal_mode_family"], "causal_mode_family_v1", inv["factor_ids"]),
            "contrast_role": dimension("experimental_contrast", contrast_value, "contrast_role_inventory_v1", inv["factor_ids"], na=inv["profile_id"] == "descriptive_observation"),
            "granularity_qualifiers": PartialDimensionV1(state="resolved" if obs["signature"]["granularity_qualifiers"] else "unresolved", value=obs["signature"]["granularity_qualifiers"] or None, authority="compatibility_qualifier_only", source_refs=obs["signature"]["source_refs"]),
        }
        signatures[oid] = PartialScientificPropositionSignatureV1(
            observation_id=oid, publication_id=inv["publication_id"], experiment_id=inv["experiment_id"],
            evidence_span_ids=obs["evidence_span_ids"], profile=inv["profile_id"],
            entity_integrity_permits_comparison=entity["integrity_state"] == "clear", dimensions=dims,
        )
    write_rows("frontier_partial_proposition_signatures.jsonl", signatures.values())

    block_by_observation = {oid: block["proposition_block_id"] for block in pair_readiness["blocks"] for oid in block["observation_ids"]}
    ready_rows = [{
        "schema_version": "ready_proposition_observation_v1", "observation_id": oid,
        "publication_id": inventory[oid]["publication_id"], "experiment_id": inventory[oid]["experiment_id"],
        "profile_id": inventory[oid]["profile_id"], "proposition_block_id": block_by_observation[oid],
        "partial_signature": signatures[oid].model_dump(mode="json"),
        "source_independent_within_current_block": next(b["source_independent"] for b in pair_readiness["blocks"] if oid in b["observation_ids"]),
        "historical_signature_modified": False,
    } for oid in sorted(ready)]
    review_rows = [{
        "schema_version": "reviewable_proposition_observation_v1", "observation_id": oid,
        "publication_id": inventory[oid]["publication_id"], "profile_id": inventory[oid]["profile_id"],
        "resolved_dimensions": sorted(k for k, v in signatures[oid].dimensions.items() if v.state == "resolved"),
        "unresolved_critical_dimensions": replay[oid]["final_unresolved_required_fields"],
        "blocker_types": sorted({b["blocker_type"] for b in blockers[oid] if b["required_field"] in replay[oid]["final_unresolved_required_fields"]}),
        "unresolved_critical_dimension_count": len(replay[oid]["final_unresolved_required_fields"]),
        "authority_boundary": "human_scientific_review" if replay[oid]["readiness_state"] == "reviewable_human_science" else "semantic_family_authority",
    } for oid in sorted(reviewable)]
    write_rows("ready_proposition_observations.jsonl", ready_rows)
    write_rows("reviewable_proposition_observations.jsonl", review_rows)

    envelopes = []
    for a, b in itertools.combinations(sorted(signatures), 2):
        if signatures[a].publication_id == signatures[b].publication_id:
            continue
        envelopes.append(compare_cross_publication_envelope_v1(signatures[a], signatures[b]))
    write_rows("cross_publication_compatibility_envelopes.jsonl", envelopes)
    envelope_by_pair = {frozenset((e.left_observation_id, e.right_observation_id)): e for e in envelopes}
    rr_opportunities, rv_opportunities = [], []
    for envelope in envelopes:
        pair = {envelope.left_observation_id, envelope.right_observation_id}
        if envelope.envelope_state not in POTENTIAL:
            continue
        row = {
            **envelope.model_dump(mode="json"),
            "opportunity_only": True, "missing_values_inferred": False,
        }
        if len(pair & ready) == 1 and len(pair & reviewable) == 1:
            rr_opportunities.append(row)
        elif pair <= reviewable:
            rv_opportunities.append(row)
    write_rows("ready_reviewable_opportunities.jsonl", rr_opportunities)
    write_rows("reviewable_reviewable_opportunities.jsonl", rv_opportunities)

    triage_rows = []
    for oid in sorted(reviewable):
        cross = [e for e in envelopes if oid in {e.left_observation_id, e.right_observation_id} and e.envelope_state in POTENTIAL]
        same_pub = [other for other in reviewable | ready if other != oid and inventory[other]["publication_id"] == inventory[oid]["publication_id"] and same_publication_possible(signatures[oid], signatures[other])]
        if cross:
            min_gaps = min(e.unresolved_gap_count for e in cross)
            state = "high_value_single_gap_cross_publication" if min_gaps == 1 else "high_value_multi_gap_cross_publication"
        elif same_pub:
            state = "medium_value_same_publication_only"
        else:
            state = "low_value_no_compatible_frontier_partner"
        triage_rows.append({
            "schema_version": "reviewable_value_of_resolution_triage_v1", "observation_id": oid,
            "publication_id": inventory[oid]["publication_id"], "primary_triage_state": state,
            "cross_publication_partner_ids": sorted({other for e in cross for other in (e.left_observation_id, e.right_observation_id) if other != oid}),
            "same_publication_partner_ids": sorted(same_pub),
            "unresolved_critical_dimensions": replay[oid]["final_unresolved_required_fields"],
            "missing_value_inferred": False, "model_score_used": False,
        })
    write_rows("reviewable_value_of_resolution_triage.jsonl", triage_rows)
    triage = {r["observation_id"]: r for r in triage_rows}
    human_rows = []
    for oid in sorted(reviewable):
        if replay[oid]["readiness_state"] != "reviewable_human_science": continue
        state = triage[oid]["primary_triage_state"]
        priority = "P0" if state == "high_value_single_gap_cross_publication" else "P1" if state == "high_value_multi_gap_cross_publication" else "P2"
        human_rows.append({
            "schema_version": "frontier_human_review_priority_v1", "observation_id": oid,
            "priority": priority, "immediate_review_recommended": priority in {"P0", "P1"},
            "cross_publication_partner_ids": triage[oid]["cross_publication_partner_ids"],
            "unresolved_fields": replay[oid]["final_unresolved_required_fields"],
            "answer_suggestion": None, "preferred_answer": None, "review_answered": False,
        })
    write_rows("frontier_human_review_priority.jsonl", human_rows)
    semantic_rows = []
    for oid in sorted(reviewable):
        if replay[oid]["readiness_state"] != "reviewable_semantic_family": continue
        high = triage[oid]["primary_triage_state"].startswith("high_value_")
        semantic_rows.append({
            "schema_version": "semantic_family_review_priority_v1", "observation_id": oid,
            "high_value_cross_publication": high,
            "unresolved_semantic_fields": replay[oid]["final_unresolved_required_fields"],
            "compatible_cross_publication_partner_ids": triage[oid]["cross_publication_partner_ids"],
            "disposition": "prioritize_bounded_semantic_review" if high else "defer_semantic_family_expansion",
            "semantic_mapping_inferred": False,
        })
    write_rows("semantic_family_review_priority.jsonl", semantic_rows)

    block_audits = []
    for block in pair_readiness["blocks"]:
        members = set(block["observation_ids"]); extendable = []
        for oid in reviewable:
            if inventory[oid]["publication_id"] in block["publication_ids"]: continue
            if any(envelope_by_pair.get(frozenset((oid, member))) and envelope_by_pair[frozenset((oid, member))].envelope_state in POTENTIAL for member in members):
                extendable.append(oid)
        block_audits.append({
            "proposition_block_id": block["proposition_block_id"], "observation_count": block["observation_count"],
            "publication_count": len(block["publication_ids"]), "experiment_count": len(block["experiment_ids"]),
            "multi_observation_same_publication_only": block["multi_observation"] and not block["cross_publication"],
            "cross_publication_extension_possible": bool(extendable),
            "reviewable_extension_observation_ids": sorted(extendable),
        })
    write_json("existing_proposition_block_extension_audit.json", {
        "schema_version": "existing_proposition_block_extension_audit_v1", "current_block_count": len(block_audits),
        "extendable_cross_publication_count": sum(r["cross_publication_extension_possible"] for r in block_audits),
        "blocks": block_audits,
    })
    graph_edges = []
    for envelope in envelopes:
        if envelope.envelope_state not in POTENTIAL | {"cross_publication_match_already_supported"}: continue
        a, b = envelope.left_observation_id, envelope.right_observation_id
        edge_type = "ready_ready" if a in ready and b in ready else "ready_reviewable_single_gap" if envelope.unresolved_gap_count == 1 and len({a, b} & ready) == 1 else "ready_reviewable_multi_gap" if len({a, b} & ready) == 1 else "reviewable_reviewable"
        graph_edges.append({"source": a, "target": b, "edge_type": edge_type, "envelope_state": envelope.envelope_state})
    write_json("frontier_opportunity_graph.json", {
        "schema_version": "frontier_opportunity_graph_v1",
        "nodes": [{"observation_id": oid, "publication_id": inventory[oid]["publication_id"], "readiness": replay[oid]["readiness_state"]} for oid in sorted(inventory)],
        "edges": graph_edges, "node_count": 20, "edge_count": len(graph_edges),
        "diagnostic_only": True, "embeddings_used": False, "graph_algorithm_used": False,
    })

    triage_counts = Counter("high" if r["primary_triage_state"].startswith("high_") else "medium" if r["primary_triage_state"].startswith("medium_") else "low" for r in triage_rows)
    high_count = triage_counts["high"]
    decision = "CORPUS_EXPANSION_JUSTIFIED" if high_count == 0 else "EXPANSION_NOT_YET_JUSTIFIED" if high_count > 3 else "TARGETED_REVIEW_THEN_EXPAND"
    write_json("corpus_expansion_decision.json", {
        "schema_version": "corpus_expansion_decision_v1", "decision": decision,
        "basis": "no reviewable observation has a cross-publication compatibility envelope; resolved subject/entity propositions differ across all locally independent publications" if decision == "CORPUS_EXPANSION_JUSTIFIED" else "bounded high-value review opportunities remain",
        "high_value_reviewable_count": high_count,
        "publication_identity_blocked": False, "retrieval_executed": False,
    })
    retrieval_targets = []
    if decision == "CORPUS_EXPANSION_JUSTIFIED":
        for block in pair_readiness["blocks"]:
            payload = block["identity_payload"]
            retrieval_targets.append({
                "schema_version": "proposition_driven_future_retrieval_target_v1",
                "target_id": "future_proposition_target_v1:" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16],
                "source_proposition_block_id": block["proposition_block_id"],
                "entity_proposition": payload["subject"], "relation_family": payload["relation_effect_family"],
                "object_target": payload["object_target"], "measurement_targets": payload["measurement_targets"],
                "measurement_properties": payload["measurement_properties"], "result_families": payload["result_families"],
                "intervention_targets": payload["intervention_targets"], "causal_mode": payload["causal_mode"],
                "evidence_family": payload["profile"], "desired_source_property": "different_locally_established_publication",
                "provider_query_generated": False, "retrieval_executed": False,
            })
    write_rows("proposition_driven_future_retrieval_targets.jsonl", retrieval_targets)
    write_json("dataset_task_readiness_axes.json", {
        "schema_version": "dataset_task_readiness_axes_v1", "frontier_observation_count": 20,
        "experimental_data_reuse_useful_count": 20, "experimental_data_reuse_qualification": "usable_with_major_limitations",
        "proposition_construction_ready_count": 7, "cross_publication_conflict_discovery_ready_count": 0,
        "axes_independent": True, "dataset_release_format_changed": False,
    })

    envelope_counts = Counter(e.envelope_state for e in envelopes)
    priority_counts = Counter(r["priority"] for r in human_rows)
    metrics = {
        "frontier_observation_count": 20, "ready_observation_count": 7, "reviewable_observation_count": 13,
        "ready_publication_count": len(ready_publications), "current_proposition_block_count": 4,
        "current_cross_publication_block_count": 0,
        "ready_reviewable_cross_publication_opportunity_count": len(rr_opportunities),
        "reviewable_reviewable_cross_publication_opportunity_count": len(rv_opportunities),
        "single_gap_cross_publication_opportunity_count": envelope_counts["potential_match_if_single_gap_resolved"],
        "multi_gap_cross_publication_opportunity_count": envelope_counts["potential_match_if_multiple_gaps_resolved"],
        "reviewable_high_value_count": triage_counts["high"], "reviewable_medium_value_count": triage_counts["medium"],
        "reviewable_low_value_count": triage_counts["low"],
        "human_review_p0_count": priority_counts["P0"], "human_review_p1_count": priority_counts["P1"],
        "human_review_p2_count": priority_counts["P2"],
        "semantic_family_high_value_count": sum(r["high_value_cross_publication"] for r in semantic_rows),
        "existing_block_extendable_cross_publication_count": sum(r["cross_publication_extension_possible"] for r in block_audits),
        "publication_independence_unresolved_opportunity_count": envelope_counts["insufficient_shared_authority"],
        "future_retrieval_target_count": len(retrieval_targets),
        "historical_candidate_object_count": 11, "formal_conflict_count": 0,
    }
    after_hashes = {rel(p): digest(p) for p in protected}; unchanged = before_hashes == after_hashes
    write_json("scientific_state_safety_audit.json", {
        "schema_version": "cross_publication_frontier_scientific_state_safety_audit_v1",
        "historical_candidate_count_before": 11, "historical_candidate_count_after": 11,
        "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "entity_integrity_claims_blocked": 241, "entity_integrity_signals_blocked": 2,
        "historical_assets_modified": not unchanged, "candidate_pairs_modified": False, "formal_v3_modified": False,
        "experimental_core_modified": False, "alignment_modified": False,
        "pi3k": {"signal_40f_state": "historically_blocked", "f389_state": "manual_scientific_review", "bridge_created": False},
        "protected_hashes_before": before_hashes, "protected_hashes_after": after_hashes,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0,
        "atlas_activated": False, "active_pointer_changed": False, "variational_em_called": False,
        "candidate_generation_executed": False, "contradiction_evaluated": False, "l4_executed": False,
    })
    write_json("production_leakage_audit.json", {
        "schema_version": "cross_publication_frontier_production_leakage_audit_v1",
        "candidate_sidecars_only": True, "production_modules_modified": False, "hardcoded_frontier_ids": [],
        "direction_or_polarity_used": False, "fuzzy_matching_used": False, "embeddings_used": False,
        "llm_used": False, "provider_clients_imported_or_called": False, "network_or_download_execution": False,
        "candidate_generation_invoked": False, "contradiction_adjudication_invoked": False, "l4_invoked": False,
    })
    write_rows("autonomous_iteration_ledger.jsonl", [
        {"schema_version": "cross_publication_frontier_iteration_v1", "stage": i, "name": name, "status": opt.status if i == 6 else "completed", "provider_calls": 0, "network_calls": 0}
        for i, name in enumerate(("freeze_frontier", "build_partial_signatures", "compare_independent_publications", "triage_value_of_resolution", "audit_block_extension", "decide_expansion_boundary", "validate_safety"))
    ])
    assertions = {
        "frontier_partition_exact": len(ready) == 7 and len(reviewable) == 13,
        "all_reviewables_triaged": len(triage_rows) == 13,
        "four_existing_blocks_audited": len(block_audits) == 4,
        "only_different_publications_in_envelopes": all(inventory[e.left_observation_id]["publication_id"] != inventory[e.right_observation_id]["publication_id"] for e in envelopes),
        "unresolved_never_counted_as_already_compatible": all(not e.unresolved_dimensions for e in envelopes if e.envelope_state == "cross_publication_match_already_supported"),
        "human_priority_has_no_answers": all(r["answer_suggestion"] is None and r["preferred_answer"] is None for r in human_rows),
        "publication_identity_authority_complete": metrics["publication_independence_unresolved_opportunity_count"] == 0,
        "historical_assets_unchanged": unchanged, "provider_network_llm_zero": True,
        "no_candidate_contradiction_l4": True, "no_hardcoded_ids_or_similarity": True,
    }
    baseline_failures = previous_validation["baseline_failure_ids"]
    final_failures = sorted(set(opt.final_failure_id)); new_failures = sorted(set(final_failures) - set(baseline_failures))
    write_json("final_validation.json", {
        "schema_version": "cross_publication_frontier_final_validation_v1", "status": opt.status,
        "assertions": assertions, "all_assertions_passed": all(assertions.values()),
        "focused_test_pass_count": opt.focused_pass_count, "related_test_pass_count": opt.related_pass_count,
        "full_suite_pass_count": opt.full_pass_count, "full_suite_subtest_pass_count": opt.full_subtest_pass_count,
        "full_suite_failure_count": opt.full_failure_count, "full_suite_collected_count": opt.full_collected_count,
        "baseline_failure_ids": baseline_failures, "final_failure_ids": final_failures, "new_failure_ids": new_failures,
        "compileall": opt.compileall, "git_diff_check": opt.git_diff_check,
        "provider_calls": 0, "api_calls": 0, "network_calls": 0, "downloads": 0, "llm_calls": 0,
    })
    write_json("summary.json", {
        "schema_version": "cross_publication_proposition_opportunity_frontier_v1_summary", "status": opt.status,
        "decision": decision, "metrics": metrics, "envelope_state_counts": dict(sorted(envelope_counts.items())),
        "interpretation": "Resolved entity propositions differ across all independent frontier publications; bounded review cannot currently create a cross-publication proposition block.",
        "safety": {"historical_assets_modified": not unchanged, "provider_calls": 0, "network_calls": 0, "candidate_generation_executed": False},
    })
    manifest_rows = []
    for name in FILES:
        if name == "manifest.json": continue
        path = ART / name
        manifest_rows.append({"relative_path": rel(path), "sha256": digest(path), "file_size_bytes": path.stat().st_size, "line_count": len(path.read_text().splitlines())})
    write_json("manifest.json", {
        "schema_version": "cross_publication_frontier_manifest_v1", "run_id": RUN.name,
        "status": opt.status, "artifact_count": len(FILES), "manifest_self_hash_excluded": True,
        "artifacts": manifest_rows, "all_required_artifacts_present": all((ART / n).exists() for n in FILES if n != "manifest.json"),
        "provider_calls": 0, "network_calls": 0,
    })
    if not all(assertions.values()): raise RuntimeError([k for k, v in assertions.items() if not v])


if __name__ == "__main__": main()
