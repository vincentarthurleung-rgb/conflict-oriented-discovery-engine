from __future__ import annotations
import ast, json
from pathlib import Path
import pytest
from pydantic import ValidationError
from src.code_engine.context_attribution.conflict_candidate.qualification.models import (
    ConflictCandidateQualificationV1, QualifiedCandidateAuthoritySidecarV1)
from src.code_engine.context_attribution.context_difference.entry_gate.models import (
    ContextDifferenceAuthorityV1, ContextDifferenceEntryAuthorizationV1,
    ContextEndpointAuthority, ObservationContextRecoveryRequirementV1)
from src.code_engine.context_attribution.context_difference.entry_gate.service import authorize_entry

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/"runs/20260725_hif1a_l4_context_readiness_gate_v1_offline/artifacts"
Q=ROOT/"runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
def jl(base,name): return [json.loads(x) for x in (base/name).read_text().splitlines() if x]
def j(name): return json.loads((RUN/name).read_text())

def source(index=9):
    q=ConflictCandidateQualificationV1.model_validate(jl(Q,"conflict_candidate_qualifications.jsonl")[index])
    s=QualifiedCandidateAuthoritySidecarV1.model_validate(jl(Q,"qualified_candidate_authority_sidecars.jsonl")[index])
    rows=[x for x in jl(RUN,"observation_context_endpoint_authority_audit.jsonl") if x["candidate_id"]==q.candidate_id]
    return q,s,ContextEndpointAuthority.model_validate({k:v for k,v in rows[0].items() if k!="candidate_id"}),ContextEndpointAuthority.model_validate({k:v for k,v in rows[1].items() if k!="candidate_id"})

def test_qualified_two_authoritative_contexts_ready_but_no_difference():
    q,s,a,b=source(); e=authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b,policy_identity="p")
    assert e.entry_status=="ready" and e.ready_for_authoritative_context_difference
    assert not ({"comparability","explanation","formal_decision"} & e.model_dump().keys())
    audit=j("weak_3ca_l4_entry_audit.json")
    assert audit["difference_authority_status"]=="ready_not_materialized"
    assert audit["downstream_status"]=="blocked_difference_not_materialized"

@pytest.mark.parametrize("missing_a,missing_b,expected",[
    (True,False,"blocked_context_a_unavailable"),(False,True,"blocked_context_b_unavailable"),
    (True,True,"blocked_context_both_unavailable")])
def test_context_unavailable_states(missing_a,missing_b,expected):
    q,s,a,b=source()
    if missing_a: a=a.model_copy(update={"context_present":False})
    if missing_b: b=b.model_copy(update={"context_present":False})
    assert authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b,policy_identity="p").entry_status==expected

def test_candidate_unqualified_has_specific_secondary_block():
    q,s,a,b=source(0)
    e=authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b,policy_identity="p")
    assert e.entry_status=="blocked_candidate_unqualified"
    assert e.primary_block_reason=="alignment_unvalidated"
    assert "candidate_qualification_blocked_alignment" in e.secondary_block_reasons

def test_unvalidated_identity_and_binding_states():
    q,s,a,b=source()
    assert authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b.model_copy(update={"context_validator_valid":False}),policy_identity="p").entry_status=="blocked_context_b_unvalidated"
    assert authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b.model_copy(update={"context_identity_valid":False}),policy_identity="p").entry_status=="blocked_context_identity_mismatch"
    assert authorize_entry(qualification=q,authority=s,endpoint_a=a,endpoint_b=b.model_copy(update={"endpoint_binding_valid":False}),policy_identity="p").entry_status=="blocked_endpoint_context_binding_mismatch"

def test_only_validated_status_is_not_context_authority():
    _,_,a,_=source()
    weak=a.model_copy(update={"context_provenance_complete":False,"context_authority_valid":False})
    assert weak.observation_context_status=="validated" and not weak.context_authority_valid

def test_entry_and_difference_strict_schemas():
    e=jl(RUN,"context_difference_entry_authorizations.jsonl")[0]; e["comparability"]="forbidden"
    with pytest.raises(ValidationError): ContextDifferenceEntryAuthorizationV1.model_validate(e)
    a=jl(RUN,"context_difference_authorities.jsonl")[0]; a["formal_use_allowed"]=True
    with pytest.raises(ValidationError): ContextDifferenceAuthorityV1.model_validate(a)

def test_recovery_requirements_are_non_executable_and_classified():
    rows=[ObservationContextRecoveryRequirementV1.model_validate(x) for x in jl(RUN,"observation_context_recovery_requirements.jsonl")]
    assert rows and all(not x.provider_call_authorized and not x.network_call_authorized and not x.automatic_execution_authorized and not x.historical_payload_mutation_authorized for x in rows)
    policy=[x for x in rows if x.recovery_scope=="policy_coverage_failure"]
    assert policy and all(x.requires_policy_extension_review and not x.automatic_retry_recommended for x in policy)
    assert any(x.candidate_id=="weak-256ac5981f2df16f7f33" and x.endpoint_role=="b" for x in rows)

def test_17b_41f_remain_policy_failures_without_composition_changes():
    rows=jl(RUN,"observation_context_endpoint_authority_audit.jsonl")
    for fragment in ("17b731","41f009"):
        hits=[x for x in rows if fragment in x["observation_id"]]
        assert hits and all("observation_context_policy_coverage_failure" in x["error_codes"] for x in hits)
        assert all(not x["context_authority_valid"] for x in hits)

def test_difference_authority_separation_and_counts():
    rows=[ContextDifferenceAuthorityV1.model_validate(x) for x in jl(RUN,"context_difference_authorities.jsonl")]
    assert len(rows)==11
    assert sum(x.authority_status=="diagnostic_only" for x in rows)==1
    assert sum(x.authority_status=="ready_not_materialized" for x in rows)==1
    assert sum(x.authority_status=="blocked_entry" for x in rows)==9
    assert not any(x.authoritative_for_new_l4 for x in rows)
    assert all(not ({"comparability","explanation","formal_conflict"} & x.model_dump().keys()) for x in rows)

def test_key_pair_real_results():
    a,b,e=j("weak_3ca_l4_entry_audit.json"),j("weak_256_l4_entry_audit.json"),j("ebd5_l4_entry_audit.json")
    assert a["entry_status"]=="ready" and a["difference_authority_status"]=="ready_not_materialized"
    assert b["endpoints"][1]=="ftl1v3_f530298f2b2955bfe9988710"
    assert b["candidate_qualification_status"]=="qualified" and b["entry_status"]=="blocked_context_b_unavailable" and b["recovery_required"]
    assert e["endpoints"]==["ftl1v3_71023211dcfb3d430a918e17","ftl1v3_8a6dafe08d3c36201f191e09"]
    assert e["candidate_qualification_status"]=="blocked_alignment" and e["entry_status"]=="blocked_candidate_unqualified"
    assert e["difference_authority_status"]=="diagnostic_only" and e["formal_conflict_status"]=="not_confirmed"

def test_metrics_safety_identity_and_contracts():
    s,m=j("l4_context_readiness_summary.json"),j("l4_context_readiness_manifest.json")
    assert s["entry_ready_count"]+s["entry_blocked_candidate_count"]+s["entry_blocked_context_unavailable_count"]==11
    assert s["authoritative_difference_count"]==0 and s["formal_conflict_count_before"]==s["formal_conflict_count_after"]==0
    assert m["legacy_candidate_artifact_count"]==11 and not m["candidate_pairs_modified"]
    assert m["source_hashes_before"]==m["source_hashes_after"] and not m["historical_runs_modified"]
    contracts=j("contract_identities.json"); assert len(contracts)==6
    assert all(x["identity_match"] and x["identity_sha256"]==x["recomputed_sha256"] for x in contracts.values())

def test_dependency_and_external_effect_boundaries():
    for p in (ROOT/"src/code_engine/context_attribution/context_difference/entry_gate").glob("*.py"):
        tree=ast.parse(p.read_text()); imports=[ast.unparse(x) for x in ast.walk(tree) if isinstance(x,(ast.Import,ast.ImportFrom))]
        assert all(not any(w in i for w in ("comparability","divergence_explanation","provider","recovery_execution")) for i in imports)
    m=j("l4_context_readiness_manifest.json")
    for k in ("provider_calls","api_calls","real_api_calls","network_calls","downloads"): assert m[k]==0
    for k in ("credential_values_read","provider_client_created","handoff_created","atlas_activated","active_pointer_changed","variational_em_called"): assert m[k] is False

@pytest.mark.parametrize("name",[
"context_difference_entry_authorizations.jsonl","context_difference_entry_authorization_validation_audit.jsonl",
"observation_context_endpoint_authority_audit.jsonl","observation_context_recovery_requirements.jsonl",
"observation_context_recovery_requirement_validation_audit.jsonl","context_difference_authorities.jsonl",
"context_difference_authority_validation_audit.jsonl","context_difference_entry_authority_bindings.jsonl",
"conflict_adjudication_input_authorities.jsonl","downstream_l4_entry_gate_audit.jsonl",
"qualified_pair_context_readiness_audit.jsonl","qualified_pair_context_readiness_audit.csv",
"weak_3ca_l4_entry_audit.json","weak_256_l4_entry_audit.json","ebd5_l4_entry_audit.json",
"ebd5_difference_authority_audit.json","l4_entry_identity_chain_audit.jsonl",
"legacy_difference_authority_exclusion_audit.jsonl","context_recovery_safety_audit.jsonl",
"l4_context_readiness_summary.json","l4_context_readiness_manifest.json"])
def test_required_artifact(name): assert (RUN/name).is_file()
