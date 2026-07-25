from __future__ import annotations
import ast,json
from pathlib import Path
import pytest
from pydantic import ValidationError
from src.code_engine.context_attribution.observation_context.remediation.identities import remediation_identity
from src.code_engine.context_attribution.observation_context.remediation.models import *
from src.code_engine.context_attribution.observation_context.remediation.registry import assert_unique_active

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"runs/20260725_hif1a_context_remediation_scope_v1_offline/artifacts"
OLD=ROOT/"runs/20260725_hif1a_l4_context_readiness_gate_v1_offline/artifacts"
def jl(name):return [json.loads(x) for x in (RUN/name).read_text().splitlines() if x]
def j(name):return json.loads((RUN/name).read_text())

def test_need_is_observation_scoped_and_strict():
    row=jl("observation_context_remediation_needs.jsonl")[0]
    assert "candidate_id" not in row and row["source_candidate_ids"]
    with pytest.raises(ValidationError): ObservationContextRemediationNeedV1.model_validate({**row,"candidate_id":"forbidden"})

def test_candidate_and_role_do_not_affect_dedup_identity():
    row=jl("observation_context_remediation_needs.jsonl")[0]
    assert remediation_identity(row)==remediation_identity({**row,"source_candidate_ids":["different"],"endpoint_role":"b"})

def test_one_active_need_per_observation_and_multi_candidate_fanout():
    needs=[ObservationContextRemediationNeedV1.model_validate(x) for x in jl("observation_context_remediation_needs.jsonl")]
    assert_unique_active(needs)
    assert len(needs)==len({x.observation_id for x in needs})==6
    assert any(x.source_candidate_reference_count>1 for x in needs)
    with pytest.raises(ValueError):assert_unique_active(needs+[needs[0]])

def test_validated_contexts_have_no_need_and_missing_have_need():
    inv=jl("observation_context_inventory.jsonl"); needs={x["observation_id"] for x in jl("observation_context_remediation_needs.jsonl")}
    assert all(x["observation_id"] not in needs for x in inv if x["context_status"]=="validated")
    assert all(x["observation_id"] in needs for x in inv if x["context_status"] in {"unavailable","unvalidated"})

def test_need_safety_and_status_contracts():
    needs=[ObservationContextRemediationNeedV1.model_validate(x) for x in jl("observation_context_remediation_needs.jsonl")]
    for x in needs:
        assert not any((x.automatic_execution_authorized,x.provider_call_authorized,x.network_call_authorized,
                        x.download_authorized,x.historical_payload_mutation_authorized,
                        x.composition_rule_mutation_authorized,x.registry_mutation_authorized))
    row=needs[0].model_dump();row["remediation_status"]="resolved"
    with pytest.raises(ValidationError):ObservationContextRemediationNeedV1.model_validate(row)

def test_policy_reviews_are_unique_fail_closed_and_safe():
    rows=[ObservationContextPolicyCoverageReviewV1.model_validate(x) for x in jl("observation_context_policy_coverage_reviews.jsonl")]
    assert {x.observation_id for x in rows}=={"ftl1v3_17b7314297cabac677007b35","ftl1v3_41f0090d726e6e8591a58574"}
    assert len(rows)==2 and len({x.observation_id for x in rows})==2
    assert all(x.review_status=="fail_closed" and not x.candidate_policy_extension_eligible for x in rows)
    assert all(not x.automatic_rule_creation_authorized and not x.automatic_provider_retry_authorized and not x.automatic_payload_mutation_authorized for x in rows)
    assert all(x.independent_document_support_count==0 for x in rows)

def test_41f_is_one_need_one_review_with_two_references():
    a=j("41f_policy_coverage_review_audit.json")
    assert a["active_need_count"]==a["active_review_count"]==1 and a["candidate_reference_count"]==2

def test_only_qualified_context_block_creates_dependency():
    deps=[CandidateContextBlockingDependencyV1.model_validate(x) for x in jl("candidate_context_blocking_dependencies.jsonl")]
    assert len(deps)==1
    d=deps[0];assert d.candidate_id=="weak-256ac5981f2df16f7f33" and d.candidate_qualification_status=="qualified"
    assert d.endpoint_role=="b" and d.observation_id=="ftl1v3_f530298f2b2955bfe9988710"
    assert d.blocks_l4_entry and d.dependency_active and d.remediation_need_identity
    assert not d.automatic_recovery_authorized and not d.provider_recovery_authorized and not d.network_recovery_authorized

def test_key_pair_scopes_remain_correct():
    a,b,e=j("weak_3ca_remediation_scope_audit.json"),j("weak_256_remediation_scope_audit.json"),j("ebd5_remediation_scope_audit.json")
    assert a["active_remediation_need_count"]==a["active_dependency_count"]==0
    assert a["entry_status"]=="ready" and a["difference_authority_status"]=="ready_not_materialized"
    assert b["qualification_status"]=="qualified" and b["active_dependency_count"]==1
    assert b["entry_status"]=="blocked_context_b_unavailable" and b["difference_authority_status"]=="blocked_entry"
    assert e["qualification_status"]=="blocked_alignment" and e["active_dependency_count"]==0
    assert e["difference_authority_status"]=="diagnostic_only" and e["adjudication"]=="blocked_alignment_unvalidated"
    assert e["comparability"]==e["explanation"]=="pending_policy" and e["formal_status"]=="not_confirmed"

def test_f530_one_need_multiple_refs_one_active_dependency():
    a=j("f530_remediation_need_audit.json")
    assert a["active_need_count"]==1 and a["candidate_reference_count"]==3 and a["active_dependency_count"]==1

def test_legacy_nine_are_read_only_migrated_and_deduplicated():
    old=jl("legacy_recovery_requirement_migration_audit.jsonl")
    assert len(old)==9 and len({x["legacy_requirement_id"] for x in old})==9
    assert all(x["new_remediation_need_identity"] and "legacy artifact preserved" in x["migration_notes"] for x in old)
    assert sum(x["duplicate_target"] for x in old)==3
    summary=j("legacy_recovery_requirement_migration_summary.json")
    assert summary["migrated_count"]==9 and not summary["legacy_artifacts_modified"]

def test_registry_is_unique_nonexecuting_index():
    r=ObservationContextRemediationRegistryV1.model_validate(j("observation_context_remediation_registry.json"))
    assert len(r.observation_to_active_need)==6 and len(r.active_need_identities)==6
    assert not r.execution_queue and not r.execution_authorized
    assert "credential" not in r.model_dump_json() and "provider" not in r.model_dump_json().lower()

def test_metrics_are_separated_and_safety_zero():
    s=j("context_remediation_scope_summary.json")
    assert s["observation_context_inventory_count"]==11
    assert s["observation_remediation_need_count"]==s["active_observation_remediation_need_count"]==s["unique_remediation_target_count"]==6
    assert s["duplicate_remediation_target_count"]==0 and s["policy_coverage_review_count"]==2
    assert s["active_l4_blocking_dependency_count"]==1 and s["unqualified_candidate_dependency_count"]==0
    assert s["observations_referenced_by_multiple_candidates_count"]==2
    assert s["deprecated_ambiguous_metric"] and s["deprecated_recovery_requirement_count"]==9
    for k in ("automatic_recovery_authorized_count","provider_recovery_authorized_count","network_recovery_authorized_count",
              "download_recovery_authorized_count","payload_mutation_authorized_count",
              "composition_mutation_authorized_count","registry_mutation_authorized_count"):assert s[k]==0

def test_contracts_candidate_safety_and_historical_hashes():
    m=j("context_remediation_scope_manifest.json");contracts=j("contract_identities.json")
    assert len(contracts)==7 and all(x["identity_match"] and x["identity_sha256"]==x["recomputed_sha256"] for x in contracts.values())
    assert m["candidate_count_before"]==m["candidate_count_after"]==11
    assert m["candidate_ids_before"]==m["candidate_ids_after"] and not m["candidate_order_changed"]
    assert m["source_hashes_before"]==m["source_hashes_after"] and not m["historical_runs_modified"]

def test_dependency_boundaries():
    base=ROOT/"src/code_engine/context_attribution/observation_context/remediation"
    for p in base.glob("*.py"):
        imports=[ast.unparse(x) for x in ast.walk(ast.parse(p.read_text())) if isinstance(x,(ast.Import,ast.ImportFrom))]
        assert all(not any(word in i for word in ("conflict_candidate","entry_gate","provider","recovery_execution","network","download")) for i in imports)

def test_external_effects_zero():
    m=j("context_remediation_scope_manifest.json")
    for k in ("provider_calls","api_calls","real_api_calls","network_calls","downloads"):assert m[k]==0
    for k in ("credential_values_read","provider_client_created","handoff_created","atlas_activated","active_pointer_changed","variational_em_called"):assert m[k] is False

@pytest.mark.parametrize("name",["observation_context_inventory.jsonl","observation_context_remediation_needs.jsonl",
"observation_context_remediation_need_validation_audit.jsonl","observation_context_policy_coverage_reviews.jsonl",
"observation_context_policy_coverage_review_validation_audit.jsonl","observation_context_remediation_registry.json",
"observation_context_remediation_registry_validation_audit.json","candidate_context_blocking_dependencies.jsonl",
"candidate_context_blocking_dependency_validation_audit.jsonl","context_entry_remediation_dependency_bindings.jsonl",
"legacy_recovery_requirement_migration_audit.jsonl","legacy_recovery_requirement_migration_summary.json",
"remediation_target_deduplication_audit.jsonl","candidate_reference_fanout_audit.jsonl",
"policy_coverage_review_deduplication_audit.jsonl","weak_3ca_remediation_scope_audit.json",
"weak_256_remediation_scope_audit.json","ebd5_remediation_scope_audit.json","f530_remediation_need_audit.json",
"17b_policy_coverage_review_audit.json","41f_policy_coverage_review_audit.json",
"context_remediation_identity_chain_audit.jsonl","context_remediation_safety_audit.json",
"context_remediation_scope_summary.json","context_remediation_scope_manifest.json"])
def test_required_artifact(name):
    assert (RUN/name).is_file()
