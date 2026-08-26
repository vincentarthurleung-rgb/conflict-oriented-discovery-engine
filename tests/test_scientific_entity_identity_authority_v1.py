import copy
import json
from pathlib import Path

import pytest

from code_engine.context_attribution.conflict_candidate.entity_identity_authority_v1_candidate import (
    EntityMentionEvidenceV1,
    LocalEntityEquivalenceDecisionV1,
    decide_local_equivalence_v1,
    exact_surface_v1,
)


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/20260825_scientific_entity_identity_authority_v1_offline/artifacts"


def mention(ref="m1", surface="CSN8", entity_type="gene", **changes):
    values = dict(
        mention_ref=ref, observation_ref=f"o:{ref}", publication_ref=f"p:{ref}",
        experiment_ref=f"e:{ref}", proposition_role="subject", role_family="entity_endpoint",
        source_surface=surface, validated_surface=surface, safe_surface=surface,
        entity_type=entity_type, source_grounded=True, extracted_surface_validated=True,
        cleaner_integrity_state="clear", raw_lineage_refs=[f"raw:{ref}"],
    )
    values.update(changes)
    return EntityMentionEvidenceV1(**values)


def test_same_exact_safe_surface_type_and_role_create_local_authority():
    result = decide_local_equivalence_v1([mention(), mention("m2")])
    assert result.scientific_equivalence_authority == "local_exact_surface_equivalent"
    assert result.eligible_for_local_equivalence


def test_local_equivalence_does_not_imply_external_canonical_id():
    result = decide_local_equivalence_v1([mention()])
    assert result.external_canonical_authority == "local_identity_only"
    assert result.external_identity_asserted_from_local_authority is False


def test_different_surfaces_without_alias_authority_do_not_merge():
    result = decide_local_equivalence_v1([mention(), mention("m2", "COPS8")])
    assert result.scientific_equivalence_authority == "unresolved_entity_equivalence"


def test_different_surfaces_with_existing_alias_authority_can_merge():
    result = decide_local_equivalence_v1([
        mention(alias_authority_refs=["alias:1"]),
        mention("m2", "COPS8", alias_authority_refs=["alias:1"]),
    ])
    assert result.scientific_equivalence_authority == "local_verified_alias_equivalent"


def test_exact_surface_type_conflict_fails_closed():
    result = decide_local_equivalence_v1([mention(), mention("m2", entity_type="drug")])
    assert result.collision_state == "type_conflict"
    assert not result.eligible_for_local_equivalence


def test_exact_surface_canonical_conflict_fails_closed():
    result = decide_local_equivalence_v1([
        mention(canonical_ids=["Entrez:1"]), mention("m2", canonical_ids=["Entrez:2"])
    ])
    assert result.collision_state == "canonical_conflict"
    assert result.external_canonical_authority == "identifier_conflict"


def test_cleaner_corrupted_lineage_cannot_authorize_equivalence():
    result = decide_local_equivalence_v1([
        mention(cleaner_integrity_state="blocked", integrity_blocker=True)
    ])
    assert result.scientific_equivalence_authority == "blocked_integrity_corruption"


def test_safe_normalization_requires_explicit_contract_switch():
    ordinary = decide_local_equivalence_v1([mention(surface="CSN8")])
    explicit = decide_local_equivalence_v1([mention(surface="CSN8")], allow_safe_normalized=True)
    assert ordinary.scientific_equivalence_authority == "local_exact_surface_equivalent"
    assert explicit.scientific_equivalence_authority == "local_safe_normalized_equivalent"
    assert exact_surface_v1("  CSN8\t") == "CSN8"


def test_external_id_unresolved_alone_does_not_block_local_equivalence():
    result = decide_local_equivalence_v1([mention(canonical_ids=[])])
    assert result.eligible_for_local_equivalence


def test_missing_validated_type_still_blocks():
    result = decide_local_equivalence_v1([mention(entity_type=None)])
    assert result.scientific_equivalence_authority == "unresolved_entity_equivalence"


def test_incompatible_role_families_do_not_merge():
    result = decide_local_equivalence_v1([
        mention(), mention("m2", role_family="measurement_target")
    ])
    assert result.scientific_equivalence_authority == "ambiguous_entity_equivalence"


def test_model_rejects_local_authority_claiming_external_verification():
    with pytest.raises(ValueError, match="local_equivalence_cannot_assert_external_verification"):
        LocalEntityEquivalenceDecisionV1(
            local_identity_key="CSN8|gene|entity_endpoint",
            scientific_equivalence_authority="local_exact_surface_equivalent",
            external_canonical_authority="external_id_verified",
            eligible_for_local_equivalence=True,
            basis=["test"],
        )


def test_decision_never_mutates_historical_input():
    source = mention()
    before = copy.deepcopy(source.model_dump())
    decide_local_equivalence_v1([source])
    assert source.model_dump() == before


def test_completed_projection_audit_covers_four_generically():
    path = ART / "projection_overblock_audit.json"
    if not path.exists():
        return
    audit = json.loads(path.read_text())
    assert audit["possible_overblock_count"] == 4
    assert len(audit["rows"]) == 4
    assert all(row["production_gate_modified"] is False for row in audit["rows"])


def test_completed_artifacts_keep_readiness_axes_independent():
    path = ART / "experimental_reuse_entity_proposition_readiness.jsonl"
    if not path.exists():
        return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 330
    assert all(row["axes_independent"] for row in rows)
    assert all("external_canonicalization_readiness" in row for row in rows)


def test_completed_run_is_offline_non_fuzzy_and_historically_immutable():
    path = ART / "scientific_state_safety_audit.json"
    if not path.exists():
        return
    safety = json.loads(path.read_text())
    leakage = json.loads((ART / "production_leakage_audit.json").read_text())
    assert safety["historical_assets_modified"] is False
    assert safety["historical_canonical_ids_modified"] is False
    assert safety["provider_calls"] == safety["network_calls"] == safety["llm_calls"] == 0
    assert leakage["fuzzy_matching_used"] is False
    assert leakage["case_specific_rules"] == []


def test_completed_run_preserves_historical_entity_integrity_and_pi3k_states():
    path = ART / "scientific_state_safety_audit.json"
    if not path.exists():
        return
    safety = json.loads(path.read_text())
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2
    assert safety["pi3k"]["signal_40f_state"] == "blocked"
    assert safety["pi3k"]["f389_state"] == "manual_scientific_review_required"


def test_completed_queue_reclassification_partitions_943():
    path = ART / "unresolved_queue_reclassification.jsonl"
    if not path.exists():
        return
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 943
    assert all(row["reclassified_category"] for row in rows)
    assert all(not row["registry_enrichment_is_scientific_annotation"] for row in rows)
