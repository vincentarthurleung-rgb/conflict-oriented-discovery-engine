from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from code_engine.extraction_assets.experimental_core.annotation_pilot import select_annotation_pilot
from code_engine.extraction_assets.experimental_core.annotation_targets import build_annotation_target
from code_engine.extraction_assets.experimental_core.comparator_triage import resolve_comparator
from code_engine.extraction_assets.experimental_core.factor_application_triage import resolve_factor_application
from code_engine.extraction_assets.experimental_core.method_source_audit import (
    exact_method_mentions, resolve_measurement_method,
)
from code_engine.extraction_assets.experimental_core.readiness_v3 import evaluate_readiness_v3_candidate
from code_engine.extraction_assets.experimental_core.reconciliation_v2 import reconcile_comparator_sets
from code_engine.extraction_assets.experimental_core.remediation_v3 import plan_remediation_v3
from code_engine.extraction_assets.experimental_core.source_authority import audit_source_scope
from code_engine.extraction_assets.experimental_core.source_envelope import build_resolution_envelope
from code_engine.extraction_assets.experimental_core.source_resolution_models import SourceResolutionEnvelope
from code_engine.extraction_assets.experimental_core.triage_policy import provider_candidate_audit

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260726_hif1a_source_grounded_linkage_resolution_annotation_triage_v1_offline"
ART = RUN / "artifacts"


def rows(name: str):
    return [json.loads(x) for x in (ART / name).read_text().splitlines() if x]


def value(name: str):
    return json.loads((ART / name).read_text())


@pytest.fixture
def provenance():
    return {
        "producer": "test", "producer_version": "v1", "source_artifact_refs": [],
        "deterministic_rule_refs": [], "limitations": [], "offline": True,
    }


def complete_scope(task="comparator"):
    kwargs = dict(
        task_type=task, result_context_present=True, factors_present=True,
        measurements_present=True, comparison_context_present=True,
        group_definition_present=True, methods_present=True,
        caption_scope_checked=True, source_anchor_verified=True,
    )
    return audit_source_scope(**kwargs)


def test_single_claim_is_not_complete_envelope(provenance):
    scope = complete_scope()
    envelope = build_resolution_envelope(
        task_type="comparator",
        observation={"identity": "obs", "experiment_scope_identity": "scope"},
        result={"identity": "result"}, measurements=[{"identity": "m"}],
        factors=[{"identity": "f"}],
        source_context={
            "primary_result_sentence": "A was lower than B.",
            "source_text_authority": "authoritative_current_fulltext",
            "historical_provider_input_authority": "incomplete",
        },
        scope_audit=scope, provenance=provenance,
    )
    with pytest.raises(ValueError, match="single claim"):
        SourceResolutionEnvelope.model_validate(envelope)


def test_current_fulltext_does_not_upgrade_historical_input(provenance):
    scope = complete_scope()
    envelope = build_resolution_envelope(
        task_type="comparator", observation={"identity": "o"}, result={"identity": "r"},
        measurements=[{"identity": "m"}], factors=[{"identity": "f"}],
        source_context={
            "primary_result_sentence": "A versus B", "following_sentence_refs": ["s2"],
            "source_text_authority": "authoritative_current_fulltext",
            "historical_provider_input_authority": "authoritative",
        }, scope_audit=scope, provenance=provenance,
    )
    with pytest.raises(ValueError, match="historical"):
        SourceResolutionEnvelope.model_validate(envelope)


def test_missing_methods_cannot_authorize_not_reported():
    scope = audit_source_scope(
        task_type="measurement_method", result_context_present=True,
        factors_present=True, measurements_present=True, methods_present=False,
        caption_scope_checked=False, source_anchor_verified=True,
    )
    assert scope["source_not_reported_authorized"] is False


def test_source_truncation_is_insufficient():
    scope = audit_source_scope(
        task_type="comparator", result_context_present=True, factors_present=True,
        measurements_present=True, comparison_context_present=True,
        group_definition_present=True, source_anchor_verified=True, truncation_detected=True,
    )
    assert scope["completeness"] == "insufficient"


def test_exact_unique_comparator_resolves(provenance):
    result = {"identity": "r", "comparison_factor_refs": []}
    resolution = resolve_comparator(
        result=result,
        factors=[{"identity": "control", "raw_text": "vehicle control"}],
        source_texts=["response was lower compared with vehicle control."],
        scope_audit=complete_scope(),
        comparison_semantics={"identity": "s", "comparison_required": True},
        provenance=provenance,
    )
    assert resolution["resolution_status"] == "deterministically_resolved"
    assert resolution["exact_match_spans"]


def test_same_sentence_cooccurrence_is_not_comparator_authority(provenance):
    resolution = resolve_comparator(
        result={"identity": "r", "comparison_factor_refs": []},
        factors=[{"identity": "f", "raw_text": "vehicle"}],
        source_texts=["vehicle changed the response"], scope_audit=complete_scope(),
        comparison_semantics={"identity": "s", "comparison_required": True},
        provenance=provenance,
    )
    assert resolution["resolution_status"] == "source_not_reported"


def test_unique_control_without_comparison_is_not_authority(provenance):
    resolution = resolve_comparator(
        result={"identity": "r", "comparison_factor_refs": []},
        factors=[{"identity": "f", "raw_text": "control", "role": "control"}],
        source_texts=["control response"], scope_audit=complete_scope(),
        comparison_semantics={"identity": "s", "comparison_required": True},
        provenance=provenance,
    )
    assert not resolution["creates_scientific_link"]


def test_multiple_comparator_candidates_require_annotation(provenance):
    resolution = resolve_comparator(
        result={"identity": "r", "comparison_factor_refs": []},
        factors=[
            {"identity": "a", "raw_text": "control"},
            {"identity": "b", "raw_text": "baseline"},
        ],
        source_texts=["lower versus control and baseline"],
        scope_audit=complete_scope(),
        comparison_semantics={"identity": "s", "comparison_required": True},
        provenance=provenance,
    )
    assert resolution["resolution_status"] == "annotation_required"
    assert not resolution["annotation_candidate_has_authority"]


def test_single_measurement_does_not_create_factor_all_to_all(provenance):
    scope = audit_source_scope(
        task_type="factor_application", result_context_present=True,
        factors_present=True, measurements_present=True, source_anchor_verified=False,
    )
    resolution = resolve_factor_application(
        observation={"identity": "o", "observation_type": "interventional_experiment"},
        factors=[{"identity": "f"}], measurements=[{"identity": "m"}], results=[],
        existing_linkages=[], source_relation_refs=[], scope_audit=scope, provenance=provenance,
    )
    assert resolution["default_all_to_all_created"] is False
    assert resolution["resolution_status"] == "source_scope_insufficient"


def test_explicit_factor_application_resolves(provenance):
    resolution = resolve_factor_application(
        observation={"identity": "o", "observation_type": "interventional_experiment"},
        factors=[{"identity": "f"}], measurements=[{"identity": "m"}], results=[],
        existing_linkages=[{
            "relation_type": "factor_applies_to_measurement", "source_ref": "f",
            "target_ref": "m", "authority_status": "authoritative",
        }], source_relation_refs=[], scope_audit=complete_scope("factor_application"),
        provenance=provenance,
    )
    assert resolution["resolved_application_pairs"] == [{"factor_ref": "f", "measurement_ref": "m"}]


def test_specific_method_and_assay_family_are_distinct():
    mentions = exact_method_mentions([
        {"text": "Western blot and a protein assay were used.", "source_kind": "method"}
    ])
    assert {x["method_resolution_granularity"] for x in mentions} == {
        "specific_method", "assay_family"
    }


def test_semantic_level_and_endpoint_do_not_guess_method(provenance):
    resolution = resolve_measurement_method(
        measurement={
            "identity": "m", "measurement_semantic_level": "protein abundance",
            "property_or_endpoint_raw": "cell viability",
        },
        source_texts=[], context_method_refs=[], scope_audit=complete_scope("measurement_method"),
        core_reuse_blocked_without_method=False, provenance=provenance,
    )
    assert resolution["resolution_status"] == "optional_enrichment"
    assert resolution["semantic_level_used_as_method"] is False
    assert resolution["endpoint_used_to_infer_method"] is False


def test_results_exact_method_resolves(provenance):
    resolution = resolve_measurement_method(
        measurement={"identity": "m"},
        source_texts=[{"text": "Measured by flow cytometry.", "source_kind": "result"}],
        context_method_refs=[], scope_audit=complete_scope("measurement_method"),
        core_reuse_blocked_without_method=False, provenance=provenance,
    )
    assert resolution["resolution_status"] == "deterministically_resolved"
    assert resolution["method_resolution_granularity"] == "specific_method"


def test_provider_candidate_never_authorizes_execution(provenance):
    row = provider_candidate_audit(
        "x", source_text_exists=True, envelope_sufficient=True,
        information_likely_present=True, deterministic_resolution_failed=True,
        joint_prompt_suitable=True, annotation_cost_exceeds_batch_extraction=True,
        prompt_v2_expressible=True, provenance=provenance,
    )
    assert row["provider_candidate"] is True
    for field in (
        "provider_reextraction_required", "automatic_execution_authorized",
        "provider_call_authorized", "network_call_authorized", "budget_authorization_present",
    ):
        assert row[field] is False


def test_reconciliation_emits_exact_ids():
    payload, membership = reconcile_comparator_sets(
        recovery_unresolved_ids={"a"}, comparative_reference_unresolved_ids={"a", "b"},
        readiness_blocked_comparator_ids={"a"},
        result_to_observation={"a": "oa", "b": "ob"},
        comparison_semantics={"b": {"comparison_semantics": "unresolved"}},
        other_linkage_blockers={},
    )
    assert payload["comparative_only_ids"] == ["b"]
    assert membership[1]["difference_reason"] == "added_by_result_level_comparison_semantics_unresolved"


def test_annotation_target_abstains_and_has_no_authority(provenance):
    envelope = {
        "identity": "e", "primary_result_sentence": "A versus B",
        "preceding_sentence_refs": [], "following_sentence_refs": [],
        "methods_text_refs": [], "figure_caption_refs": [], "table_caption_refs": [],
        "evidence_chain_refs": ["anchor"], "context_field_evidence_refs": [],
    }
    target = build_annotation_target(
        task_type="comparator", observation_identity="o", result_identity="r",
        measurement_identity="m", factor_candidate_ids=["f"],
        experiment_scope_identity="s", envelope=envelope, candidate_answers=["f"],
        ambiguity_reason="test", provenance=provenance,
    )
    assert target["abstain_allowed"] is True
    assert target["candidate_answers_authoritative"] is False
    assert target["scientific_link_created"] is False
    assert "Conflict" not in target["question_text"]


def test_pilot_selection_is_deterministic():
    targets = [
        {"task_type": "comparator", "expected_difficulty": "easy",
         "observation_identity": f"o{i}", "identity": f"t{i}"}
        for i in range(4)
    ]
    assert select_annotation_pilot(targets) == select_annotation_pilot(list(reversed(targets)))


def test_annotation_pending_is_not_text_only(provenance):
    row = evaluate_readiness_v3_candidate(
        observation_identity="o", structured_revision_identity="r",
        comparator_status="annotation_required", factor_application_status=None,
        method_status="optional_enrichment", context_available=True,
        v2_readiness_identity="v2", provenance=provenance,
    )
    assert row["status"] == "machine_reusable_with_annotation_pending"
    assert "text" not in row["status"]


def test_method_gap_need_not_block_core_reuse(provenance):
    row = evaluate_readiness_v3_candidate(
        observation_identity="o", structured_revision_identity="r",
        comparator_status=None, factor_application_status=None,
        method_status="source_not_reported", context_available=True,
        v2_readiness_identity="v2", provenance=provenance,
    )
    assert row["status"] == "machine_reusable_with_method_limitations"


def test_remediation_v3_is_planning_only(provenance):
    row = plan_remediation_v3(
        target_type="comparator", target_identity="t", observation_identity="o",
        source_block_identity="b", resolution_status="annotation_required",
        provenance=provenance,
    )
    assert row["requirement_classification"] == "annotation_required"
    assert row["provider_reextraction_required"] is False


def test_full_run_reconciles_88_89_85_by_real_sets():
    summary = value("source_grounded_linkage_resolution_annotation_triage_summary.json")
    reconciliation = value("comparator_unresolved_set_reconciliation.json")
    assert summary["comparator_recovery_unresolved_count"] == len(reconciliation["recovery_unresolved_ids"])
    assert summary["comparative_reference_unresolved_count"] == len(reconciliation["comparative_reference_unresolved_ids"])
    assert summary["readiness_blocked_comparator_count"] == len(reconciliation["readiness_blocked_comparator_ids"])
    assert len(reconciliation["comparative_reference_unresolved_ids"]) == len(reconciliation["recovery_unresolved_ids"]) + 1


def test_full_run_core_upper_bound_is_not_provider_required():
    summary = value("source_grounded_linkage_resolution_annotation_triage_summary.json")
    routed = sum(summary[f"core_{x}_count"] for x in (
        "resolved_offline", "annotation_required", "source_not_reported",
        "source_reingestion_required", "provider_candidate", "unresolved",
    ))
    assert routed == summary["pre_triage_core_linkage_unresolved_upper_bound"]
    assert summary["provider_reextraction_required_count"] == 0


def test_full_run_method_gap_is_fully_routed():
    summary = value("source_grounded_linkage_resolution_annotation_triage_summary.json")
    routed = sum(summary[f"method_{x}_count"] for x in (
        "resolved_offline", "annotation_required", "source_not_reported",
        "source_reingestion_required", "optional_enrichment", "provider_candidate", "unresolved",
    ))
    assert routed == summary["pre_triage_method_gap_upper_bound"]


def test_every_envelope_has_real_source_anchor_or_incomplete_authority():
    for envelope in rows("source_resolution_envelopes.jsonl"):
        assert envelope["primary_result_sentence"]
        assert (
            envelope["source_text_authority"] == "incomplete_source"
            or envelope["source_document_identity"]
        )


def test_contract_identities_recompute():
    for row in value("contract_identities.json"):
        digest = hashlib.sha256(json.dumps(
            row["canonical_payload"], ensure_ascii=False, sort_keys=True,
            separators=(",", ":"),
        ).encode()).hexdigest()
        assert row["identity_sha256"] == digest == row["recomputed_sha256"]
        assert row["identity_match"] is True


def test_all_schema_snapshots_are_strict_and_parse():
    for path in (RUN / "schemas").glob("*.schema.json"):
        schema = json.loads(path.read_text())
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "field,expected",
    [
        ("provider_calls", 0), ("api_calls", 0), ("real_api_calls", 0),
        ("network_calls", 0), ("downloads", 0), ("credential_values_read", False),
        ("provider_client_created", False), ("human_annotations_executed", 0),
        ("human_gold_created", False), ("historical_runs_modified", False),
        ("historical_projection_content_modified", False), ("historical_raw_files_modified", False),
        ("historical_parsed_payloads_modified", False),
        ("historical_validated_observations_modified", False), ("formal_v3_modified", False),
        ("candidate_pairs_modified", False), ("dataset_release_pipeline_created", False),
        ("method_paper_narrative_changed", False), ("handoff_created", False),
        ("atlas_activated", False), ("active_pointer_changed", False),
        ("variational_em_called", False), ("composition_rules_modified", False),
        ("difference_comparability_explanation_implemented", False),
    ],
)
def test_execution_and_scientific_safety(field, expected):
    assert value("source_resolution_safety_audit.json")[field] == expected


@pytest.mark.parametrize(
    "name,key,expected",
    [
        ("weak_3ca_source_resolution_audit.json", "difference_authority_status", "ready_not_materialized"),
        ("weak_256_source_resolution_audit.json", "context_entry_status", "blocked_context_b_unavailable"),
        ("ebd5_source_resolution_audit.json", "candidate_qualification_status", "blocked_alignment"),
        ("ebd5_source_resolution_audit.json", "difference_authority_status", "diagnostic_only"),
        ("ebd5_source_resolution_audit.json", "formal_conflict_status", "not_confirmed"),
        ("context_17b_source_resolution_audit.json", "status", "fail_closed_policy_coverage_failure"),
        ("context_41f_source_resolution_audit.json", "status", "fail_closed_policy_coverage_failure"),
    ],
)
def test_existing_scientific_state_is_unchanged(name, key, expected):
    assert value(name)[key] == expected


def test_dependency_boundaries_do_not_import_conflict_layers():
    modules = [
        "source_envelope.py", "comparator_triage.py", "factor_application_triage.py",
        "method_source_audit.py", "annotation_targets.py", "remediation_v3.py", "readiness_v3.py",
    ]
    base = ROOT / "src/code_engine/extraction_assets/experimental_core"
    for name in modules:
        imports = "\n".join(
            line for line in (base / name).read_text().lower().splitlines()
            if line.startswith(("import ", "from "))
        )
        assert "context_attribution" not in imports
        assert "provider" not in imports


@pytest.mark.parametrize("name", [
    "source_resolution_envelopes.jsonl",
    "source_resolution_envelope_summary.json",
    "source_scope_completeness_audit.jsonl",
    "comparator_unresolved_set_reconciliation.json",
    "comparator_unresolved_set_membership.jsonl",
    "source_grounded_comparator_resolutions.jsonl",
    "source_grounded_comparator_resolution_summary.json",
    "comparator_annotation_targets.jsonl",
    "source_grounded_factor_measurement_resolutions.jsonl",
    "source_grounded_factor_measurement_resolution_summary.json",
    "factor_measurement_annotation_targets.jsonl",
    "source_grounded_measurement_method_resolutions.jsonl",
    "source_grounded_measurement_method_resolution_summary.json",
    "measurement_method_annotation_targets.jsonl",
    "source_not_reported_audit.jsonl",
    "source_scope_insufficient_audit.jsonl",
    "source_reingestion_requirements.jsonl",
    "annotation_target_inventory.jsonl",
    "annotation_target_summary.json",
    "annotation_pilot_selection.json",
    "annotation_pilot_selection_summary.json",
    "annotation_gold_candidate_audit.jsonl",
    "experimental_core_remediation_requirements_v3.jsonl",
    "remediation_v2_v3_reconciliation.json",
    "provider_candidate_policy_audit.jsonl",
    "post_triage_requirement_summary.json",
    "machine_reuse_readiness_v3_candidates.jsonl",
    "machine_reuse_readiness_v2_v3_comparison.json",
    "source_resolution_identity_chain_audit.jsonl",
    "source_resolution_safety_audit.json",
    "source_grounded_linkage_resolution_annotation_triage_summary.json",
    "source_grounded_linkage_resolution_annotation_triage_manifest.json",
    "worktree_protection_audit.json",
])
def test_required_artifact_exists_and_is_json(name):
    path = ART / name
    assert path.is_file()
    if name.endswith(".jsonl"):
        for line in path.read_text().splitlines():
            json.loads(line)
    else:
        json.loads(path.read_text())


@pytest.mark.parametrize("name", [
    "source_grounded_resolution_envelope_contract_identity_v1.json",
    "source_resolution_scope_completeness_contract_identity_v1.json",
    "comparator_unresolved_set_reconciliation_contract_identity_v2.json",
    "source_grounded_comparator_resolution_contract_identity_v2.json",
    "source_grounded_factor_measurement_resolution_contract_identity_v1.json",
    "source_grounded_measurement_method_resolution_contract_identity_v2.json",
    "source_resolution_provider_candidate_policy_contract_identity_v1.json",
    "experimental_linkage_annotation_target_contract_identity_v1.json",
    "measurement_method_annotation_target_contract_identity_v1.json",
    "experimental_annotation_pilot_selection_contract_identity_v1.json",
    "experimental_annotation_gold_candidate_policy_contract_identity_v1.json",
    "source_reingestion_requirement_contract_identity_v1.json",
    "experimental_core_remediation_contract_identity_v3.json",
    "experimental_observation_machine_reuse_contract_identity_v3_candidate.json",
    "source_grounded_resolution_orchestration_contract_identity_v1.json",
])
def test_required_contract_identity_snapshot_exists(name):
    row = json.loads((RUN / "contract_identities" / name).read_text())
    assert row["identity_match"] is True
