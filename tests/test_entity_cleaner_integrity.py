import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from code_engine.normalization.entity_cleaner_integrity import (
    EntityCleanerBoundaryIntegrityV1,
    EntityCleanerCorruptionAuditV1,
    LocalExactIdentityAuthority,
    classify_surface_lineage,
    deterministic_rule_supports,
    evaluate_boundary_integrity,
)


def test_unsupported_leading_character_loss_fails_closed():
    result = classify_surface_lineage(
        l1_raw_entity="PAR1",
        cleaner_input_entity="AR1",
        cleaner_output_entity="AR1",
        historical_canonical_entity="TCF20",
        historical_canonical_aliases=["AR1"],
        downstream_object_ids=["signal-1"],
    )
    assert result["classifications"] == [
        "potentially_lossy_cleaning",
        "canonical_identity_changed",
        "downstream_scientific_object_affected",
    ]
    assert result["leading_character_changed"] is True
    assert result["canonical_identity_changed_due_lossy_cleaning"] is True


def test_explicit_phosphorylation_and_deterministic_modifiers_remain_valid():
    assert deterministic_rule_supports("P-AKT", "AKT")[0] is True
    assert deterministic_rule_supports("pAKT", "AKT")[0] is True
    assert deterministic_rule_supports("PAR1", "AR1")[0] is False
    assert deterministic_rule_supports("expression of EGFR", "EGFR")[0] is True


def test_formatting_only_change_is_not_lossy():
    result = classify_surface_lineage(
        l1_raw_entity="Doxycycline", cleaner_input_entity="Doxycycline",
        cleaner_output_entity="doxycycline", historical_canonical_entity="Doxycycline",
    )
    assert result["classifications"] == ["formatting_only"]
    assert result["potentially_lossy"] is False


def test_unexplained_non_boundary_rewrite_is_unresolved_not_validated():
    result = classify_surface_lineage(
        l1_raw_entity="Entity A", cleaner_input_entity="Entity A",
        cleaner_output_entity="Entity B", historical_canonical_entity="Entity B",
    )
    assert result["classifications"] == ["unresolved"]
    assert result["canonical_identity_changed_due_lossy_cleaning"] is False


def test_audit_contract_retains_raw_and_historical_values():
    audit = EntityCleanerCorruptionAuditV1(
        source_run_ref="runs/example",
        claim_id="claim-1",
        observation_id="claim-1",
        mention_role="object",
        l1_raw_entity="PAR1",
        historical_cleaner_input_entity="AR1",
        historical_cleaner_output_entities=["AR1"],
        historical_normalized_canonical_entity="TCF20",
        historical_normalized_canonical_aliases=["AR1"],
        classifications=["potentially_lossy_cleaning", "canonical_identity_changed"],
        transformation_stages=["endpoint_preclean"],
        leading_character_changed=True,
        trailing_character_changed=False,
        potentially_lossy=True,
        canonical_identity_changed_due_lossy_cleaning=True,
        downstream_scientific_object_affected=False,
    )
    assert audit.raw_value_retained is True
    assert audit.historical_value_retained is True
    assert audit.historical_object_modified is False


# Entity Cleaner Integrity Repair v1 generic contract and regression controls.
def test_valid_entity_is_unchanged():
    decision = evaluate_boundary_integrity("EGFR", "EGFR", stage="entity_cleaner")
    assert decision.new_cleaned_candidate == "EGFR"
    assert decision.boundary_change_allowed is True


def test_unsupported_leading_character_removal_is_rejected_generically():
    decision = evaluate_boundary_integrity("XYZ1", "YZ1", stage="endpoint_preclean")
    assert decision.primary_class == "unsupported_boundary_change"
    assert decision.new_cleaned_candidate == "XYZ1"


def test_unsupported_trailing_character_removal_is_rejected_generically():
    decision = evaluate_boundary_integrity("XYZ1", "XYZ", stage="entity_cleaner")
    assert decision.primary_class == "ambiguous_rule_authority"
    assert decision.new_cleaned_candidate == "XYZ1"


def test_supported_punctuation_normalization_is_retained():
    decision = evaluate_boundary_integrity("EGFR.", "EGFR", stage="generic_text_cleanup")
    assert decision.primary_class == "validated_formatting_normalization"
    assert decision.new_cleaned_candidate == "EGFR"


def test_supported_formatting_normalization_does_not_discard_unicode_letters():
    punctuation = evaluate_boundary_integrity("NF-κB.", "NF-κB", stage="generic_text_cleanup")
    meaningful_loss = evaluate_boundary_integrity("SOD2Δ", "SOD2", stage="generic_text_cleanup")
    assert punctuation.primary_class == "validated_formatting_normalization"
    assert meaningful_loss.primary_class == "unsupported_boundary_change"


def test_raw_entity_is_never_mutated():
    decision = evaluate_boundary_integrity(
        "XYZ1", "YZ1", stage="endpoint_preclean", l1_raw_entity="XYZ1",
    )
    assert decision.raw_before == decision.raw_after == "XYZ1"


def test_historical_cleaned_value_is_preserved_separately():
    decision = evaluate_boundary_integrity(
        "XYZ1", "YZ1", stage="endpoint_preclean", historical_cleaned="YZ1",
    )
    assert decision.historical_cleaned_value == "YZ1"
    assert decision.new_cleaned_candidate == "XYZ1"
    assert decision.historical_cleaned_retained is True


def test_historical_normalized_value_is_preserved_separately():
    decision = evaluate_boundary_integrity(
        "XYZ1", "YZ1", stage="endpoint_preclean", historical_normalized="Historical identity",
    )
    assert decision.historical_normalized_value == "Historical identity"
    assert decision.historical_normalized_retained is True


def _accepted_cache(tmp_path: Path) -> Path:
    path = tmp_path / "accepted.jsonl"
    path.write_text(json.dumps({
        "surface": "EGFR", "normalized_surface": "egfr",
        "canonical_id": "GENE:1", "canonical_name": "EGFR", "aliases": ["ERBB1"],
    }) + "\n", encoding="utf-8")
    return path


def test_repaired_normalized_value_requires_exact_local_authority(tmp_path):
    authority = LocalExactIdentityAuthority(_accepted_cache(tmp_path))
    identity, status, _ = authority.lookup("ERBB1")
    assert status == "resolved_exact_local_authority"
    assert identity and identity.canonical_id == "GENE:1"


def test_no_exact_authority_is_unresolved_not_guessed(tmp_path):
    authority = LocalExactIdentityAuthority(_accepted_cache(tmp_path))
    identity, status, candidates = authority.lookup("ERBB2")
    assert identity is None
    assert candidates == []
    assert status == "unresolved_exact_local_authority"


@pytest.mark.parametrize(
    "forbidden_field",
    ["fuzzy_authority_used", "fulltext_authority_used", "same_publication_authority_used"],
)
def test_forbidden_authorities_cannot_authorize_repair(forbidden_field):
    payload = evaluate_boundary_integrity("XYZ1", "YZ1", stage="endpoint_preclean").model_dump()
    payload[forbidden_field] = True
    with pytest.raises(ValidationError, match="forbidden_entity_repair_authority"):
        EntityCleanerBoundaryIntegrityV1(**payload)


def test_canonical_identity_change_triggers_integrity_audit():
    result = classify_surface_lineage(
        l1_raw_entity="XYZ1", cleaner_input_entity="YZ1", cleaner_output_entity="YZ1",
        historical_canonical_entity="Different entity", historical_canonical_aliases=["YZ1"],
    )
    assert "canonical_identity_changed" in result["classifications"]


def test_canonical_unchanged_formatting_does_not_overblock():
    result = classify_surface_lineage(
        l1_raw_entity="EGFR", cleaner_input_entity="EGFR",
        cleaner_output_entity="egfr", historical_canonical_entity="EGFR",
    )
    assert result["classifications"] == ["formatting_only"]
    assert result["potentially_lossy"] is False


def _impact(claim_id, signal_id, *, primary="unsupported_boundary_change", changed=True, effect="canonical_identity_became_unresolved"):
    return {
        "cleaner_input_id": f"input-{claim_id}-{signal_id}",
        "source_run_ref": "runs/fixture",
        "claim_id": claim_id,
        "mention_role": "object",
        "historical_canonical_identity": "Historical",
        "historical_canonical_identity_changed": changed,
        "semantic_effect": effect,
        "primary_boundary_class": primary,
        "downstream_signal_ids": [signal_id] if signal_id else [],
        "identity_transition_state": "historical_identity_suspect_but_unresolved",
        "source_raw_entity": "XYZ1",
        "l1_raw_extracted_entity": "XYZ1",
        "historical_cleaned_entity": "YZ1",
        "repaired_cleaned_entity_candidate": "XYZ1",
        "repaired_normalized_entity_candidate": None,
        "repaired_normalization_status": "unresolved_exact_local_authority",
        "entity_integrity_status": "canonical_identity_unresolved",
    }


def test_affected_claim_is_identified_from_lineage():
    from scripts.run_entity_cleaner_integrity_repair_v1 import claim_and_signal_replay
    claims, _signals, _revisions, metrics = claim_and_signal_replay([_impact("claim-1", "signal-1")])
    assert claims[0]["claim_id"] == "claim-1"
    assert metrics["potentially_affected_claim_count"] == 1


def test_unaffected_claim_remains_valid_and_absent_from_affected_sidecar():
    from scripts.run_entity_cleaner_integrity_repair_v1 import claim_and_signal_replay
    claims, signals, _revisions, metrics = claim_and_signal_replay([
        _impact("claim-1", "signal-1", primary="validated_semantic_normalization", changed=False),
    ])
    assert claims == [] and signals == []
    assert metrics["claim_integrity_blocked_count"] == 0


def test_corrupted_claim_cannot_authorize_contradiction_signal():
    from scripts.run_entity_cleaner_integrity_repair_v1 import claim_and_signal_replay
    _claims, signals, _revisions, _metrics = claim_and_signal_replay([_impact("claim-1", "signal-1")])
    assert signals[0]["signal_scientific_eligibility"] == "blocked_upstream_claim_integrity"
    assert signals[0]["new_contradiction_signal_created"] is False


def test_second_affected_signal_is_discovered_generically():
    from scripts.run_entity_cleaner_integrity_repair_v1 import claim_and_signal_replay
    impacts = [_impact("claim-1", "signal-1"), _impact("claim-2", "signal-2", changed=False)]
    _claims, signals, _revisions, metrics = claim_and_signal_replay(impacts)
    assert {item["signal_id"] for item in signals} == {"signal-1", "signal-2"}
    assert metrics["affected_signal_count"] == 2


def test_no_case_specific_production_rule_and_legitimate_rules_regress():
    source = Path("src/code_engine/normalization/entity_cleaner_integrity.py").read_text(encoding="utf-8")
    assert "PI3K" not in source
    assert deterministic_rule_supports("P-AKT", "AKT")[0] is True
    assert deterministic_rule_supports("expression of EGFR", "EGFR")[0] is True
    assert deterministic_rule_supports("JNKs", "JNK")[0] is True
