from __future__ import annotations

from code_engine.extraction_assets.context.models import AssetProvenance
from code_engine.extraction_assets.context.readiness_v3 import (
    ContextFieldRequirementAssignmentV1, build_readiness_v3, classify_unresolved,
)
from code_engine.extraction_assets.forensics.signal_fulltext_bridge import (
    BridgeForensicFactsV1, bridge_may_create_scientific_link, classify_bridge,
)


PROV = AssetProvenance(producer="test", producer_version="v1", offline=True)


def assignment(**updates):
    data = {
        "observation_identity": "obs:1", "profile_id": "profile:1", "field_name": "species",
        "requirement": "optional", "requirement_basis_refs": ["consumer.py:1"],
        "value_state": "unresolved", "authority": "unresolved", "inheritance_path": [],
        "source_scope_sufficient": None, "competing_source_supported_value_count": 0,
        "identity": "assignment:1", "provenance": PROV,
    }
    data.update(updates)
    return ContextFieldRequirementAssignmentV1.model_validate(data)


def facts(**updates):
    data = {
        "same_pmid": True, "source_identity_consistent": True, "local_fulltext_present": True,
        "target_experiment_locatable": True, "existing_validated_observation_count": 1,
        "exact_provenance_overlap": True, "compatible_proposition": True,
        "compatible_measurement_result": True, "compatible_experiment_scope": True,
        "competing_incompatible_observation_count": 0,
    }
    data.update(updates)
    return BridgeForensicFactsV1.model_validate(data)


def test_optional_unresolved_does_not_block():
    assert build_readiness_v3(observation_identity="obs:1", assignments=[assignment()], provenance=PROV).status == "ready_with_optional_unresolved"


def test_required_unresolved_blocks():
    record = build_readiness_v3(observation_identity="obs:1", assignments=[assignment(requirement="required")], provenance=PROV)
    assert record.status == "blocked_required_context_missing"


def test_unknown_requirement_is_not_automatically_ready():
    record = build_readiness_v3(observation_identity="obs:1", assignments=[assignment(requirement="unknown_requirement")], provenance=PROV)
    assert record.status == "requirement_profile_unresolved"


def test_inherited_field_requires_path():
    try:
        assignment(authority="scope_inherited")
    except ValueError as error:
        assert "requires_path" in str(error)
    else:
        raise AssertionError("missing inheritance path was accepted")


def test_derived_field_does_not_masquerade_as_direct():
    record = build_readiness_v3(
        observation_identity="obs:1",
        assignments=[assignment(value_state="present", authority="deterministically_derived")],
        provenance=PROV,
    )
    assert record.status == "ready_with_derived_context"


def test_insufficient_source_scope_is_not_source_not_reported():
    record = assignment(value_state="not_reported", source_scope_sufficient=False)
    assert classify_unresolved(record) == "source_scope_insufficient"


def test_single_candidate_is_not_ambiguous_source_evidence():
    record = assignment(value_state="ambiguous", competing_source_supported_value_count=1)
    assert classify_unresolved(record) != "ambiguous_competing_context"


def test_same_pmid_with_multiple_observations_is_ambiguous():
    assert classify_bridge(facts(existing_validated_observation_count=3,
                                 competing_incompatible_observation_count=2)) == "ambiguous_multiple_fulltext_experiments"


def test_same_gene_across_experiments_cannot_bridge():
    assert classify_bridge(facts(same_gene_only=True)) != "local_bridge_recoverable"


def test_same_polarity_cannot_bridge():
    assert classify_bridge(facts(same_polarity_only=True)) != "local_bridge_recoverable"


def test_same_sentence_wording_alone_cannot_bridge():
    assert classify_bridge(facts(wording_similarity_only=True)) != "local_bridge_recoverable"


def test_exact_provenance_and_compatible_scope_is_recoverable_candidate():
    assert classify_bridge(facts()) == "local_bridge_recoverable"


def test_missing_provenance_cannot_be_recoverable():
    assert classify_bridge(facts(exact_provenance_overlap=False)) != "local_bridge_recoverable"


def test_abstract_candidate_only_cannot_enter_l4():
    assert bridge_may_create_scientific_link(
        classification="local_bridge_recoverable", validated_by_scientific_authority=False
    ) is False


def test_local_source_does_not_mean_target_experiment_extracted():
    outcome = classify_bridge(facts(existing_validated_observation_count=0,
                                    exact_provenance_overlap=False, target_experiment_locatable=False))
    assert outcome == "local_source_scope_insufficient"


def test_provider_candidate_cannot_auto_execute():
    outcome = classify_bridge(facts(source_identity_consistent=False))
    assert outcome == "provenance_identity_mismatch"
    assert bridge_may_create_scientific_link(classification=outcome,
                                             validated_by_scientific_authority=False) is False
