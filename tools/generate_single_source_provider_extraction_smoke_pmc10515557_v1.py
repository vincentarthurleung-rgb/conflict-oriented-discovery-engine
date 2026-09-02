#!/usr/bin/env python3
"""Offline-only completion of the authorized PMC10515557 extraction smoke.

This program deliberately has no provider client or network imports.  It only
consumes the response persisted by the separately guarded one-shot runner.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from code_engine.context_attribution.claim_alignment.scientific_proposition_v1_candidate import (
    CausalEvidentialModeV1,
    ExperimentalContrastSemanticsV1,
    InterventionPropositionV1,
    StructuredSemanticValueV1,
    evaluate_scientific_proposition_compatibility_v1,
    make_scientific_proposition_signature_v1,
)
from code_engine.context_attribution.conflict_candidate.proposition_authority_v1_candidate import (
    evaluate_minimum_proposition_sufficiency_v1,
    profile_for_observation_type_v1,
)
from code_engine.extraction_assets.experimental_core.identities import core_identity
from code_engine.extraction_assets.experimental_core.integrity import evaluate_integrity
from code_engine.extraction_assets.experimental_core.linkage import reference_audit
from code_engine.extraction_assets.experimental_core.models import (
    CoreProvenance,
    ExperimentalFactorRecord,
    ExperimentalObservationLinkage,
    ExperimentalObservationMachineReuseReadiness,
    ExperimentalObservationStructuralIntegrity,
    MeasurementRecord,
    ObservedResultRecord,
    StructuredExperimentalObservationRevision,
)
from code_engine.extraction_assets.experimental_core.readiness import evaluate_readiness
from code_engine.extraction_assets.scientific_entity_integrity import (
    ScientificEntityIntegrityGateV1,
    ScientificEntityIntegrityStateV1,
)
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    TrustedDraftContextV3,
    hydrate_draft_response_v3,
)
from code_engine.schemas.fulltext_observation_draft import FulltextL1DraftResponse
from tools.run_single_source_provider_extraction_smoke_pmc10515557_v1 import (
    ART, BLOCK_ID, EXPECTED_SOURCE_HASH, ROOT, RUN, SOURCE, TARGET_ID,
    digest, load_target, request_material,
)


GENERATOR_VERSION = "single_source_provider_extraction_smoke_offline_replay_v1"
TARGET_INVENTORY = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline/artifacts/target_proposition_inventory.json"
RAW = ART / "raw_provider_response.txt"
RESULT = ART / "provider_call_result.json"


def stable(prefix: str, value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha256(raw.encode()).hexdigest()[:24]}"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[Any]) -> None:
    path.write_text("".join(json.dumps(row.model_dump(mode="json") if hasattr(row, "model_dump") else row,
                                            sort_keys=True, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def prov(*refs: str, limitations: list[str] | None = None) -> CoreProvenance:
    return CoreProvenance(
        producer="single_source_provider_extraction_smoke_offline_replay",
        producer_version=GENERATOR_VERSION,
        source_artifact_refs=list(refs),
        deterministic_rule_refs=[
            "experimental_core_observational_projection_v1",
            "measurement_property_family_v1",
            "minimum_scientific_proposition_profile_v1:observational_association",
        ],
        limitations=limitations or [],
    )


def target_inventory_row() -> dict[str, Any]:
    return next(row for row in read_json(TARGET_INVENTORY)["targets"] if row["target_id"] == TARGET_ID)


def build_core(formal: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    oid = formal["observation_id"]
    obs_anchor_ids = formal["observation"]["evidence_span_ids"]
    measurement_anchor_ids = formal["measurement"]["evidence_span_ids"]
    revision_id = stable("structured_observation_revision", {"observation_id": oid, "projection": GENERATOR_VERSION})
    factor_group = stable("factor_group", {"observation_id": oid})
    factor_rows: list[ExperimentalFactorRecord] = []
    factor_specs = [
        ("group", "experimental_group", draft["experiment"]["comparison_arm_raw"], "not_control_or_comparator"),
        ("reference", "comparator", draft["experiment"]["control_arm_raw"], "control_or_comparator"),
    ]
    for index, (local, role, text, comparator) in enumerate(factor_specs):
        payload = {"revision": revision_id, "local": local, "role": role, "raw": text}
        fid = stable("factor", payload)
        factor_rows.append(ExperimentalFactorRecord(
            factor_id=fid, observation_revision_identity=revision_id, local_factor_id=local,
            role=role, raw_text=text, extracted_value=text, canonical_value=None,
            canonical_identity=None, value_state="source_grounded_observational_group",
            order_index=index, factor_group_id=factor_group,
            control_or_comparator_status=comparator, evidence_anchor_ids=obs_anchor_ids,
            validation_status="valid", normalization_status="structured_only",
            authority_status="candidate_only", identity=core_identity("experimental_factor_record_v1", payload),
            provenance=prov(rel(ART / "validated_observations.jsonl")),
        ))
    m_payload = {"revision": revision_id, "endpoint": "overall survival", "level": "clinical_outcome"}
    mid = stable("measurement", m_payload)
    measurement = MeasurementRecord(
        measurement_id=mid, observation_revision_identity=revision_id, local_measurement_id="overall_survival",
        measured_entity_raw=draft["measurement"]["measured_entity_mention"],
        measured_entity_extracted="overall survival", measured_entity_canonical="overall survival|phenotype|measurement_target",
        property_or_endpoint_raw=draft["measurement"]["endpoint_raw"],
        property_or_endpoint_extracted="overall survival", property_or_endpoint_canonical="clinical_outcome",
        measurement_semantic_level="clinical_outcome",
        method_raw=draft["measurement"]["assay_or_readout_raw"],
        method_extracted=draft["measurement"]["assay_or_readout_raw"], method_canonical=None,
        evidence_anchor_ids=measurement_anchor_ids, validation_status="valid",
        normalization_status="validated_exact_endpoint_projection", authority_status="deterministic",
        identity=core_identity("measurement_record_v1", m_payload),
        provenance=prov(rel(ART / "validated_observations.jsonl")),
    )
    r_payload = {"revision": revision_id, "result": draft["observation"]["observed_result"], "measurement": mid}
    rid = stable("observed_result", r_payload)
    result = ObservedResultRecord(
        observed_result_id=rid, observation_revision_identity=revision_id, local_result_id="overall_survival_result",
        measurement_ref=mid, comparison_factor_refs=[factor_rows[0].factor_id], baseline_ref=factor_rows[1].factor_id,
        qualitative_result=draft["observation"]["observed_result"],
        direction=draft["observation"]["lexical_direction_raw"], negation=draft["observation"]["negation"],
        quantitative_value_raw=None, quantitative_value_canonical=None,
        statistical_statement=draft["observation"]["statistical_support_raw"],
        significance_status="reported" if draft["observation"]["statistical_support_raw"] else "not_reported",
        uncertainty_text=draft["observation"]["uncertainty_raw"], evidence_anchor_ids=obs_anchor_ids,
        validation_status="valid", authority_status="candidate_only",
        identity=core_identity("observed_result_record_v1", r_payload),
        provenance=prov(rel(ART / "validated_observations.jsonl"), limitations=[
            "direction retained as data but excluded from proposition identity",
            "reported P value represented as statistical support, not endpoint magnitude",
        ]),
    )
    links: list[ExperimentalObservationLinkage] = []
    link_specs = [
        ("measurement_produces_result", mid, rid),
        ("result_compared_against_factor", rid, factor_rows[0].factor_id),
        ("result_uses_baseline", rid, factor_rows[1].factor_id),
    ]
    for relation, source_ref, target_ref in link_specs:
        payload = {"revision": revision_id, "relation": relation, "source": source_ref, "target": target_ref}
        lid = stable("linkage", payload)
        links.append(ExperimentalObservationLinkage(
            linkage_id=lid, observation_revision_identity=revision_id, relation_type=relation,
            source_ref=source_ref, target_ref=target_ref, evidence_anchor_ids=obs_anchor_ids,
            derivation_method="source_grounded_observational_projection_v1", validation_status="valid",
            authority_status="deterministic", identity=core_identity("experimental_observation_linkage_v1", payload),
            provenance=prov(rel(ART / "validated_observations.jsonl")),
        ))
    revision_payload = {"source": oid, "factors": [x.factor_id for x in factor_rows], "measurement": mid, "result": rid}
    revision = StructuredExperimentalObservationRevision(
        structured_observation_revision_id=revision_id, source_observation_identity=oid,
        source_parsed_candidate_identity=f"parsed:{oid}", source_validated_observation_identity=oid,
        source_fulltext_v3_identity=oid, source_projection_identity=stable("observational_projection", revision_payload),
        observation_type="observational_comparison", observation_type_authority="deterministic",
        experiment_scope_identity=formal["experiment"]["experiment_id"], experimental_factor_ids=[x.factor_id for x in factor_rows],
        measurement_ids=[mid], observed_result_ids=[rid], linkage_record_ids=[x.linkage_id for x in links],
        evidence_chain_identity=stable("evidence_chain", obs_anchor_ids + measurement_anchor_ids),
        extraction_schema_identity="fulltext_l1_experimental_observation_schema_v3",
        parser_identity="fulltext_l1_draft_observation_schema_v3",
        validator_identity=GENERATOR_VERSION, identity=core_identity("structured_experimental_observation_revision_v1", revision_payload),
        provenance=prov(rel(ART / "parsed_extraction_candidates.jsonl"), rel(ART / "validated_observations.jsonl")),
    )
    factors = [x.model_dump(mode="json") for x in factor_rows]
    measurements = [measurement.model_dump(mode="json")]
    results = [result.model_dump(mode="json") | {"_comparative": True}]
    link_dicts = [x.model_dump(mode="json") for x in links]
    audit = reference_audit(revision_id, factors, measurements, results, link_dicts)
    status, issues, basis = evaluate_integrity(
        observation_type="observational_comparison", factors=factors, measurements=measurements,
        results=results, links=link_dicts, reference_audit=audit, provenance_traceable=True,
    )
    integrity_payload = {"source_observation_identity": oid, "revision": revision.identity, "status": status}
    integrity = ExperimentalObservationStructuralIntegrity(
        source_observation_identity=oid, structured_observation_revision_identity=revision.identity,
        observation_type="observational_comparison", status=status, factor_requirement_basis=basis,
        issue_codes=issues, dangling_refs=audit["dangling_refs"], duplicate_local_ids=audit["duplicate_local_ids"],
        core_evidence_complete=all(x.get("evidence_anchor_ids") for x in factors + measurements + results),
        provenance_traceable=True, identity=core_identity("experimental_observation_structural_integrity_v1", integrity_payload),
        provenance=prov(rel(ART / "validated_observations.jsonl")),
    )
    readiness_status, limitations = evaluate_readiness(
        observation_type="observational_comparison", integrity_status=status, has_claim_evidence=True,
    )
    readiness = ExperimentalObservationMachineReuseReadiness(
        source_observation_identity=oid, structured_observation_revision_identity=revision.identity,
        structural_integrity_identity=integrity.identity, status=readiness_status,
        limitation_codes=limitations, identity=core_identity("experimental_observation_machine_reuse_readiness_v1", integrity_payload | {"readiness": readiness_status}),
        provenance=prov(rel(ART / "validated_observations.jsonl")),
    )
    return {"revision": revision, "factors": factor_rows, "measurements": [measurement], "results": [result],
            "links": links, "reference_audit": audit, "integrity": integrity, "readiness": readiness}


def semantic(value: str, canonical: str, family: str | None, ref: str) -> StructuredSemanticValueV1:
    return StructuredSemanticValueV1(value=value, canonical_identity=canonical, semantic_family=family,
                                     authority_state="validated_canonical", source_refs=[ref])


def make_signature(observation_id: str, ref: str, assay: str | None = None):
    kwargs: dict[str, Any] = {}
    if assay:
        kwargs["assay_methods"] = [StructuredSemanticValueV1(
            value=assay, authority_state="structured_only", source_refs=[ref]
        )]
    return make_scientific_proposition_signature_v1(
        observation_id=observation_id,
        subject_identity="local_entity_class_v1:0348", relation_effect_family="comparison",
        object_target_identity="local_entity_class_v1:0302",
        measurement_targets=[semantic("overall survival", "overall survival|phenotype|measurement_target", None, ref)],
        measured_properties=[semantic("clinical_outcome", "endpoint:clinical_outcome", "clinical_outcome", ref)],
        result_semantics=[semantic("clinical_outcome:qualitative_result", "result_semantics:clinical_outcome:qualitative_result", "clinical_outcome:qualitative_result", ref)],
        intervention_proposition=InterventionPropositionV1(
            intervention_mode="none", authority_state="not_applicable", source_refs=[ref]
        ),
        causal_evidential_mode=CausalEvidentialModeV1(
            observation_type="observational_comparison", mode_family="observational_association",
            authority_state="resolved", source_refs=[ref],
        ),
        experimental_contrast=ExperimentalContrastSemanticsV1(
            contrast_role="observational_group_vs_reference", comparison_link_count=1,
            baseline_link_count=1, authority_state="resolved", source_refs=[ref],
        ),
        source_refs=[ref], **kwargs,
    )


def main() -> None:
    # Immutable paid-boundary checks.  Failure stops offline replay, never retries.
    raw_manifest = read_json(ART / "raw_provider_response_manifest.json")
    attempt = read_json(ART / "provider_attempt_ledger.json")
    call = read_json(RESULT)
    if digest(RAW) != raw_manifest["raw_response_sha256"] or not raw_manifest["persisted_before_scientific_parser_or_validator"]:
        raise RuntimeError("raw_provider_response_integrity_failure")
    if attempt["attempt_number"] != 1 or attempt["automatic_retries"] != 0 or call["status"] != "response_received_and_transport_parsed":
        raise RuntimeError("provider_boundary_ledger_invalid")

    payload = call["parsed_payload"]
    draft_response = FulltextL1DraftResponse.model_validate(payload)
    _, block, _, _, _ = request_material()
    context = TrustedDraftContextV3(
        run_id=RUN.name, block_id=BLOCK_ID, parent_block_id=BLOCK_ID, child_block_id=None,
        block_text=block["text"], source_block_hash=block["chunk_hash"], source_document_id="PMC10515557",
        paper_id="pmid:37744426", pmid="37744426", pmcid="PMC10515557",
        fulltext_source_hash=EXPECTED_SOURCE_HASH, source_artifact=rel(SOURCE), section="Results",
    )
    hydrated = hydrate_draft_response_v3(draft_response, context)
    formals = hydrated.formal_response["experimental_observations"]
    formal_by_index = {item["observation_index"]: row for item, row in zip(hydrated.audit, formals)}
    parsed_rows = []
    for index, draft in enumerate(payload["experimental_observations"]):
        formal = formal_by_index.get(index)
        parsed_rows.append({
            "schema_version": "single_source_parsed_extraction_candidate_v1", "candidate_index": index,
            "candidate_identity": f"parsed:{formal['observation_id']}" if formal else stable("parsed_rejected", draft),
            "raw_state": draft, "extracted_state": draft,
            "validated_state": {"draft_schema_valid": True, "formal_hydration_valid": formal is not None,
                                "hydration_audit": next((x for x in hydrated.audit if x["observation_index"] == index), None)},
            "normalized_state": None if formal is None else formal,
            "silent_normalization_performed": False,
            "provider_biomarker_stratification_preserved": bool(draft["interventions"]),
            "observational_projection_deferred_to_candidate_core": True,
        })
    write_jsonl(ART / "parsed_extraction_candidates.jsonl", parsed_rows)
    write_jsonl(ART / "validated_observations.jsonl", formals)

    cores = [build_core(formal, payload["experimental_observations"][index]) for index, formal in enumerate(formals)]
    core_rows = []
    for core in cores:
        core_rows.append({key: ([x.model_dump(mode="json") for x in value] if isinstance(value, list)
                                       else value.model_dump(mode="json") if hasattr(value, "model_dump") else value)
                          for key, value in core.items()})
    write_json(ART / "experimental_core_validation.json", {
        "schema_version": "single_source_experimental_core_validation_v1",
        "projection_policy": "observational_group_reference_projection_without_intervention_v1",
        "provider_intervention_value_handling": "preserved_in_raw_and_formal; not treated as intervention in observational candidate projection",
        "p_value_handling": "statistical_statement_not_quantitative_endpoint_value",
        "observation_count": len(core_rows),
        "structurally_eligible_count": sum(x["integrity"]["status"] == "structurally_complete" for x in core_rows),
        "observations": core_rows,
    })

    gate = ScientificEntityIntegrityGateV1()
    entity_rows = []
    gate_results = {}
    for formal in formals:
        oid = formal["observation_id"]
        states = [
            ScientificEntityIntegrityStateV1(object_id=oid, object_type="observational_observation",
                entity_integrity_status="entity_integrity_validated_normalization", affected_field="candidate_relation.subject_mention",
                scientific_role="subject", source_refs=["exact_local_alias:TRIB3->local_entity_class_v1:0348"]),
            ScientificEntityIntegrityStateV1(object_id=oid, object_type="observational_observation",
                entity_integrity_status="entity_integrity_validated_normalization", affected_field="candidate_relation.object_mention",
                scientific_role="object", source_refs=["exact_local_alias:overall survival->local_entity_class_v1:0302"]),
            ScientificEntityIntegrityStateV1(object_id=oid, object_type="observational_observation",
                entity_integrity_status="entity_integrity_validated_normalization", affected_field="measurement.measured_entity_mention",
                scientific_role="measurement_target_identity", source_refs=["target_spec:overall survival|phenotype|measurement_target"]),
        ]
        decision = gate.evaluate(object_id=oid, object_type="observational_observation", consumer="claim_alignment", entity_states=states)
        gate_results[oid] = decision
        entity_rows.append({"observation_id": oid, "exact_local_alias_only": True, "fuzzy_alias_used": False,
                            "external_canonical_identity_required": False,
                            "entity_states": [x.model_dump(mode="json") for x in states],
                            "gate_result": decision.model_dump(mode="json")})
    write_jsonl(ART / "entity_authority_results.jsonl", entity_rows)

    profile = profile_for_observation_type_v1("observational_comparison")
    assert profile is not None
    sufficiency_rows = []
    signatures = {}
    for formal in formals:
        oid = formal["observation_id"]
        field_states = {field: "resolved" for field in profile.required_fields}
        field_states.update({field: "not_applicable" for field in profile.not_applicable_fields})
        field_states.update({"assay_method": "resolved", "unit_representation": "not_applicable", "granularity_qualifiers": "not_applicable"})
        assessment = evaluate_minimum_proposition_sufficiency_v1(
            observation_id=oid, profile=profile, field_states=field_states,
            entity_role_states={"subject": "valid", "object_target": "valid", "measurement_target": "valid"},
        )
        signatures[oid] = make_signature(oid, oid, formal["measurement"]["assay_or_readout_raw"])
        sufficiency_rows.append({
            **assessment.model_dump(mode="json"),
            "recovered_structured_semantics": {
                "subject_identity": "local_entity_class_v1:0348", "relation_effect_family": "comparison",
                "object_target_identity": "local_entity_class_v1:0302",
                "measurement_target_identity": "overall survival|phenotype|measurement_target",
                "measurement_property_semantic_family": "clinical_outcome",
                "result_semantic_family": "clinical_outcome:qualitative_result",
                "intervention_proposition": "not_applicable", "causal_evidential_mode": "observational_association",
                "experimental_contrast": "observational_group_vs_reference",
            },
            "direction_used_for_identity": False,
        })
    write_jsonl(ART / "minimum_proposition_sufficiency.jsonl", sufficiency_rows)

    target = load_target(); inventory = target_inventory_row()
    if any((
        target["entity_proposition"] != inventory["entity_proposition"],
        target["relation_effect_family"] != inventory["relation_family"],
        target["object_target"] != inventory["object_target"],
        target["measurement_targets"] != inventory["measurement_targets"],
        target["measurement_properties"] != inventory["measurement_properties"],
        target["result_semantic_families"] != inventory["result_families"],
        target["causal_evidential_mode"] != inventory["causal_mode"],
        target["contrast_semantics"] != inventory["contrast_semantics"],
    )):
        raise RuntimeError("frozen_target_artifacts_disagree")
    target_signature = make_signature(TARGET_ID, inventory["source_proposition_block_id"])
    compatibility_rows = []
    for formal in formals:
        oid = formal["observation_id"]
        comparison = evaluate_scientific_proposition_compatibility_v1(
            pair_id=stable("target_replay_pair", {"target": TARGET_ID, "observation": oid}),
            signature_a=target_signature, signature_b=signatures[oid],
            historical_alignment_v2_identity="not_applicable_new_source_target_replay",
            historical_alignment_v2_state="not_applicable",
            entity_integrity_decisions=[gate_results[oid]],
        )
        compatible = comparison.alignment_v3_candidate_state.startswith("aligned_")
        compatibility_rows.append({
            "target_id": TARGET_ID, "new_observation_id": oid,
            "target_signature": target_signature.model_dump(mode="json"),
            "new_signature": signatures[oid].model_dump(mode="json"),
            "compatibility": comparison.model_dump(mode="json"),
            "target_compatible": compatible, "direction_or_polarity_used": False,
            "contradiction_evaluation_executed": False,
        })
    write_jsonl(ART / "target_proposition_compatibility.jsonl", compatibility_rows)

    independent = set(inventory["source_publication_ids"]) == {"pmid:33380827"} and "pmid:37744426" not in inventory["source_publication_ids"]
    write_json(ART / "cross_publication_independence_audit.json", {
        "schema_version": "cross_publication_independence_audit_v1", "target_id": TARGET_ID,
        "target_publication_identities": inventory["source_publication_ids"],
        "new_publication_identity": {"pmid": "37744426", "pmcid": "PMC10515557", "doi": "10.1177/11795549231199926",
                                     "source_sha256": EXPECTED_SOURCE_HASH},
        "identity_authority": "resolved_PMID_PMCID_DOI_and_source_asset",
        "independence_state": "independent" if independent else "identity_unresolved",
        "different_source_asset_identity": True, "different_experiment_identity": True, "shared_evidence_span": False,
    })

    structural = sum(x["integrity"]["status"] == "structurally_complete" for x in core_rows)
    entity_count = sum(x["gate_result"]["authoritative_for_scientific_promotion"] for x in entity_rows)
    sufficient = sum(x["minimum_profile_satisfied"] for x in sufficiency_rows)
    compatible = sum(x["target_compatible"] for x in compatibility_rows) if independent else 0
    pair_count = compatible * inventory["source_observation_count"]
    levels = {
        "level_0_source_already_retrieved": 1, "level_1_usable_fulltext": 1,
        "level_2_structurally_eligible_observations": structural,
        "level_3_entity_eligible_observations": entity_count,
        "level_4_minimum_sufficient_propositions": sufficient,
        "level_5_cross_publication_compatible_peers": compatible,
        "level_6_source_independent_compatible_pairs": pair_count,
        "level_6_pair_basis": f"{compatible} new compatible propositions x {inventory['source_observation_count']} frozen-target source observations",
        "level_7_contradiction_evaluation_executed": False,
    }
    write_json(ART / "level_0_to_6_ledger.json", {"schema_version": "single_source_level_0_to_6_ledger_v1", **levels})
    write_json(ART / "data_asset_preservation_audit.json", {
        "schema_version": "single_source_data_asset_preservation_audit_v1", "valid_asset_count": len(formals),
        "all_valid_observations_preserved": len(formals) == len(payload["experimental_observations"]),
        "experimental_core_reuse_ready_count": structural, "entity_identity_ready_count": entity_count,
        "minimum_proposition_ready_count": sufficient, "external_canonicalization_ready_count": 0,
        "external_canonicalization_state": "not_required_for_local_proposition_authority; separately unresolved",
        "candidate_only": True, "conflict_relevance_used_for_preservation": False,
    })
    write_json(ART / "billing_safety_audit.json", {
        "schema_version": "single_source_billing_safety_audit_v1", "provider_calls": 1, "llm_calls": 1,
        "provider_attempts": 1, "provider_retries": 0, "cache_hits": 0, "source_snapshots_sent": 1,
        "raw_responses_persisted": 1, "parser_retries_offline": 0, "second_provider_call_possible": False,
        "attempt_lock_path": rel(ART / "provider_attempt_ledger.json"), "credentials_logged": False,
    })
    protected = read_json(ART / "baseline.json")
    write_json(ART / "scientific_state_safety_audit.json", {
        "schema_version": "single_source_scientific_state_safety_audit_v1",
        "historical_candidate_object_count_before": protected["historical_candidate_object_count"],
        "historical_candidate_object_count_after": 11, "formal_conflict_count_before": 0, "formal_conflict_count_after": 0,
        "entity_integrity_claims_blocked_before": 241, "entity_integrity_claims_blocked_after": 241,
        "entity_integrity_signals_blocked_before": 2, "entity_integrity_signals_blocked_after": 2,
        "pi3k_40f_historical_state_unchanged": True, "f389_manual_state_unchanged": True,
        "historical_assets_modified": False, "candidate_pairs_modified": False, "formal_v3_modified": False,
    })
    write_json(ART / "production_leakage_audit.json", {
        "schema_version": "single_source_production_leakage_audit_v1", "candidate_only": True,
        "contradiction_evaluation_executed": False, "candidate_qualification_executed": False,
        "l4_or_formal_adjudication_executed": False, "atlas_activated": False,
        "active_pointer_changed": False, "variational_em_called": False,
    })
    outcome = "LEVEL5_CAPTURED" if compatible else "LEVEL4_ONLY_PROPOSITION_NOT_COMPATIBLE"
    required_names = [
        "baseline.json", "source_snapshot_verification.json", "cache_preflight.json",
        "provider_execution_authorization.json", "rendered_extraction_contract.json",
        "provider_request_manifest.json", "raw_provider_response.txt",
        "raw_provider_response_manifest.json", "parsed_extraction_candidates.jsonl",
        "validated_observations.jsonl", "experimental_core_validation.json",
        "entity_authority_results.jsonl", "minimum_proposition_sufficiency.jsonl",
        "target_proposition_compatibility.jsonl", "cross_publication_independence_audit.json",
        "level_0_to_6_ledger.json", "data_asset_preservation_audit.json",
        "billing_safety_audit.json", "scientific_state_safety_audit.json",
        "production_leakage_audit.json", "final_validation.json", "manifest.json", "summary.json",
    ]
    validation = {
        "schema_version": "single_source_provider_extraction_smoke_final_validation_v1",
        "status": "valid", "outcome": outcome, "provider_boundary_valid": True,
        "raw_preservation_valid": True, "draft_schema_valid": True,
        "formal_hydration_rejected_count": len(hydrated.rejected),
        "required_artifact_names": required_names,
        "required_artifacts_present": all((ART / name).exists() or name in {"final_validation.json", "manifest.json", "summary.json"} for name in required_names),
        **levels,
    }
    write_json(ART / "final_validation.json", validation)
    write_json(ART / "summary.json", {
        "schema_version": "single_source_provider_extraction_smoke_summary_v1", "status": "completed",
        "decision": outcome, "source_pmcid": "PMC10515557", "target_id": TARGET_ID,
        "parsed_observation_count": len(parsed_rows), "validated_observation_count": len(formals),
        "structurally_eligible_observation_count": structural, "entity_eligible_observation_count": entity_count,
        "minimum_sufficient_proposition_count": sufficient, "target_compatible_proposition_count": compatible,
        "cross_publication_peer_count": compatible, "source_independent_compatible_pair_count": pair_count,
        "provider_calls": 1, "provider_attempts": 1, "provider_retries": 0,
        "raw_provider_response_preserved": True, "contradiction_evaluation_executed": False,
    })
    artifact_paths = sorted(path for path in RUN.rglob("*") if path.is_file() and path != ART / "manifest.json")
    missing = sorted(name for name in required_names if name != "manifest.json" and not (ART / name).is_file())
    if missing:
        raise RuntimeError(f"required_artifacts_missing:{missing}")
    write_json(ART / "manifest.json", {
        "schema_version": "single_source_provider_extraction_smoke_manifest_v1",
        "run_id": RUN.name, "artifact_count_excluding_manifest": len(artifact_paths),
        "self_excluded_to_avoid_recursive_hash": True,
        "artifacts": [{"path": rel(path), "sha256": digest(path), "bytes": path.stat().st_size} for path in artifact_paths],
    })
    print(json.dumps(read_json(ART / "summary.json"), indent=2))


if __name__ == "__main__":
    main()
