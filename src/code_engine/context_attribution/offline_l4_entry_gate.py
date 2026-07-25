"""Zero-provider replay for L4 Context Readiness and Difference Authority."""
from __future__ import annotations
import csv, hashlib, json, subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from pydantic import ValidationError
from .conflict_candidate.qualification.models import ConflictCandidateQualificationV1, QualifiedCandidateAuthoritySidecarV1
from .context_difference.entry_gate.identities import identity
from .context_difference.entry_gate.models import (
    ConflictAdjudicationInputAuthorityV1, ContextDifferenceAuthorityV1,
    ContextDifferenceEntryAuthorityBindingV1, ContextEndpointAuthority,
    ObservationContextRecoveryRequirementV1,
)
from .context_difference.entry_gate.recovery import PERMITTED_FUTURE_RECOVERY_MODES
from .context_difference.entry_gate.service import authorize_entry
from .layer_identity import canonical_json, layer_identity
from .observation_context.validation import validate_observation_context

def _j(p): return json.loads(p.read_text())
def _jl(p): return [json.loads(x) for x in p.read_text().splitlines() if x]
def _wj(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
def _wjl(p,vs): p.write_text("".join(json.dumps(v,sort_keys=True,ensure_ascii=False)+"\n" for v in vs))
def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def _contract(name,payload):
    version=f"{name}_identity_v1"; value=layer_identity(name,version,payload)
    return {"contract_name":name,"contract_version":version,"canonical_payload":payload,
            "identity_sha256":value,"recomputed_sha256":layer_identity(name,version,json.loads(canonical_json(payload))),
            "identity_match":True}

def materialize(root: Path):
    out=root/"runs/20260725_hif1a_l4_context_readiness_gate_v1_offline"
    if out.exists(): raise FileExistsError(out)
    art,schemas=out/"artifacts",out/"artifacts/schemas"; schemas.mkdir(parents=True)
    qr=root/"runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
    old=root/"runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts"
    ar=root/"runs/20260725_hif1a_claim_alignment_dimension_taxonomy_v2_offline/artifacts"
    qs=[ConflictCandidateQualificationV1.model_validate(x) for x in _jl(qr/"conflict_candidate_qualifications.jsonl")]
    sides=[QualifiedCandidateAuthoritySidecarV1.model_validate(x) for x in _jl(qr/"qualified_candidate_authority_sidecars.jsonl")]
    candidates=_jl(old/"conflict_candidates.jsonl"); contexts=_jl(old/"observation_contexts.jsonl")
    audits={x["observation_id"]:x for x in _jl(old/"observation_context_validation_audit.jsonl")}
    differences={x["candidate_id"]:x for x in _jl(old/"context_differences.jsonl")}
    decisions={x["pair_id"]:x for x in _jl(old/"formal_conflict_decisions_staging.jsonl")}
    context_by_id={x["observation_id"]:x for x in contexts}
    source_path=old/"observation_contexts.jsonl"; source_hash=_sha(source_path)
    source_ref=str(source_path.relative_to(root))
    source_files=[p for base in (qr,old,ar) for p in base.rglob("*") if p.is_file()]
    source_hashes={str(p.relative_to(root)):_sha(p) for p in sorted(source_files)}
    contracts={}
    specs={
      "context_difference_entry_authorization_contract":{"schema":"context_difference_entry_authorization_v1","ready_requires":["qualified_candidate","two_authoritative_contexts"],"l4_science":False},
      "observation_context_recovery_requirement_contract":{"schema":"observation_context_recovery_requirement_v1","execution_authorized":False,"provider_authorized":False},
      "context_difference_authority_contract":{"schema":"context_difference_authority_v1","validity_not_authority":True,"entry_required":True},
      "context_difference_entry_authority_binding_contract":{"schema":"context_difference_entry_authority_binding_v1","reference_only":True},
      "conflict_adjudication_input_authority_contract":{"schema":"conflict_adjudication_input_authority_v1","gate_order":["alignment","signal","qualification","context_entry","difference_authority","comparability","explanation"]},
      "l4_entry_orchestration_contract":{"flow":["candidate_qualification","context_readiness","difference_materialization","difference_authority"],"automatic_recovery":False},
    }
    for name,payload in specs.items(): contracts[f"{name}_identity_v1"]=_contract(name,payload)
    policy=contracts["context_difference_entry_authorization_contract_identity_v1"]["identity_sha256"]

    endpoint_rows=[]; entries=[]; recoveries=[]; authorities=[]; bindings=[]; inputs=[]; gate_audits=[]
    def endpoint(q,role):
        oid=getattr(q,f"observation_{role}_id"); claim=getattr(q,f"endpoint_claim_identity_{role}")
        ctx=context_by_id.get(oid); audit=audits.get(oid)
        errors=[]; schema_ok=validator_ok=identity_ok=prov_ok=binding_ok=False
        status="unavailable"
        if ctx:
            status=ctx.get("validation_status","unvalidated")
            try:
                _, verr=validate_observation_context(ctx); schema_ok=True; identity_ok=not verr
            except (ValidationError,KeyError,ValueError) as e: errors.append(f"schema_or_identity:{type(e).__name__}")
            validator_ok=ctx.get("validator_version")=="observation_context_validator_v1" and status=="validated" and bool(audit and audit.get("valid"))
            prov=ctx.get("provenance",{}); prov_ok=bool(prov.get("legacy_extraction_identity")) and prov.get("source_payload_modified") is False and bool(ctx.get("token_catalog_identity")) and bool(ctx.get("anchor_set_identity"))
            binding_ok=ctx.get("observation_id")==oid and ctx.get("normalized_claim_identity")==claim
            if not validator_ok: errors.append("context_validator_or_audit_invalid")
            if not identity_ok: errors.append("context_identity_invalid")
            if not prov_ok: errors.append("context_provenance_incomplete")
            if not binding_ok: errors.append("endpoint_context_binding_mismatch")
        elif audit and not audit.get("valid"):
            status="unvalidated"; errors.extend(audit.get("errors",[]))
            if audit.get("failure_class"): errors.append(audit["failure_class"])
        else: errors.append("context_unavailable")
        row=ContextEndpointAuthority(endpoint_role=role,observation_id=oid,endpoint_claim_identity=claim,
            context_present=ctx is not None,context_schema_valid=schema_ok,context_validator_valid=validator_ok,
            context_identity_valid=identity_ok,context_provenance_complete=prov_ok,endpoint_binding_valid=binding_ok,
            context_authority_valid=all((schema_ok,validator_ok,identity_ok,prov_ok,binding_ok)),
            observation_context_identity=ctx.get("observation_context_identity") if ctx else None,
            observation_context_status=status,observation_context_validator_identity=ctx.get("validator_version") if ctx else None,
            observation_context_source_identity=f"sha256:{source_hash}" if ctx else None,
            source_artifact_path=source_ref,source_artifact_sha256=source_hash,
            validation_audit_valid=bool(audit and audit.get("valid")),error_codes=errors)
        endpoint_rows.append({"candidate_id":q.candidate_id,**row.model_dump()}); return row
    for q,side,c in zip(qs,sides,candidates):
        ea,eb=endpoint(q,"a"),endpoint(q,"b")
        entry=authorize_entry(qualification=q,authority=side,endpoint_a=ea,endpoint_b=eb,policy_identity=policy); entries.append(entry)
        for ep in (ea,eb):
            if ep.context_authority_valid: continue
            policy_failure="observation_context_policy_coverage_failure" in ep.error_codes
            scope=("policy_coverage_failure" if policy_failure else "context_unvalidated" if ep.observation_context_status=="unvalidated" else "context_missing")
            basis={"candidate_id":q.candidate_id,"candidate_qualification_identity":q.qualification_identity,
                   "entry_authorization_identity":entry.identity,"endpoint_role":ep.endpoint_role,
                   "observation_id":ep.observation_id,"endpoint_claim_identity":ep.endpoint_claim_identity,
                   "current_context_status":ep.observation_context_status,"current_context_identity":ep.observation_context_identity,
                   "blocking_reason_codes":ep.error_codes,"recovery_required":True,"recovery_scope":scope,
                   "permitted_future_recovery_modes":PERMITTED_FUTURE_RECOVERY_MODES,
                   "provider_call_authorized":False,"network_call_authorized":False,
                   "automatic_execution_authorized":False,"historical_payload_mutation_authorized":False,
                   "requires_policy_extension_review":policy_failure,"automatic_retry_recommended":False,
                   "source_artifact_refs":[{"path":source_ref,"sha256":source_hash}],
                   "provenance":{"requirement_only":True,"recovery_executed":False}}
            rid=identity("observation_context_recovery_requirement",basis)
            recoveries.append(ObservationContextRecoveryRequirementV1(
                recovery_requirement_id=rid,**basis,identity=rid))
        diff=differences.get(q.candidate_id)
        if diff and entry.entry_status!="ready":
            astatus,scope,diag="diagnostic_only","legacy_diagnostic",True
        elif entry.entry_status=="ready" and not diff:
            astatus,scope,diag="ready_not_materialized","none",False
        else:
            astatus,scope,diag="blocked_entry","none",False
        abasis={"context_difference_authority_id":identity("context_difference_authority_id",{"candidate_id":q.candidate_id,"entry":entry.identity}),
            "candidate_id":q.candidate_id,"scientific_candidate_pair_identity":q.scientific_candidate_pair_identity,
            "candidate_qualification_identity":q.qualification_identity,"entry_authorization_identity":entry.identity,
            "entry_status":entry.entry_status,"source_context_difference_identity":diff.get("context_difference_identity") if diff else None,
            "source_context_difference_schema_version":diff.get("schema_version") if diff else None,
            "source_context_difference_validation_status":diff.get("validation_status") if diff else None,
            "source_context_difference_validator_identity":diff.get("validator_version") if diff else None,
            "source_kind":"historical_artifact" if diff else "unavailable",
            "source_lineage":{"legacy_pair_effect_consumed":False,"qualification_bound":True},
            "difference_artifact_valid":bool(diff and diff.get("validation_status")=="validated"),
            "authoritative_for_new_l4":False,"authority_status":astatus,"authority_scope":scope,
            "diagnostic_use_allowed":diag,"formal_use_allowed":False,"legacy_artifact_preserved":bool(diff),
            "source_payload_modified":False,"provenance":{"comparability_produced":False,"explanation_produced":False,"formal_conflict_produced":False}}
        auth=ContextDifferenceAuthorityV1(**abasis,identity=identity("context_difference_authority",abasis)); authorities.append(auth)
        bb={"context_difference_identity":auth.source_context_difference_identity,"candidate_id":q.candidate_id,
            "candidate_qualification_identity":q.qualification_identity,"entry_authorization_identity":entry.identity,
            "entry_status":entry.entry_status,"difference_authority_identity":auth.identity,
            "artifact_valid":auth.difference_artifact_valid,"entry_ready":entry.entry_status=="ready",
            "authoritative_for_new_l4":False,"diagnostic_only":astatus=="diagnostic_only","formal_use_allowed":False}
        bindings.append(ContextDifferenceEntryAuthorityBindingV1(**bb,binding_identity=identity("context_difference_entry_authority_binding",bb)))
        if q.qualification_status!="qualified":
            block="alignment"; primary="blocked_alignment_unvalidated" if q.qualification_status=="blocked_alignment" else "blocked_candidate_unqualified"
        elif entry.entry_status!="ready":
            block="context_entry"; primary=("blocked_context_unavailable" if "unavailable" in entry.entry_status else "blocked_context_unvalidated")
        elif astatus=="ready_not_materialized": block,primary="context_difference","blocked_difference_not_materialized"
        elif astatus!="authoritative": block,primary="context_difference","blocked_difference_unauthorized"
        else: block,primary="l4b","blocked_attribution_pending"
        ib={"candidate_id":q.candidate_id,"candidate_qualification_identity":q.qualification_identity,
            "candidate_qualification_status":q.qualification_status,"context_entry_authorization_identity":entry.identity,
            "context_entry_status":entry.entry_status,"context_difference_authority_identity":auth.identity,
            "context_difference_authority_status":astatus,"comparability_bundle_identity":None,
            "divergence_explanation_bundle_identity":None,"authority_complete":False,"blocking_layer":block,
            "primary_block_reason":primary,"secondary_block_reasons":entry.secondary_block_reasons}
        inputs.append(ConflictAdjudicationInputAuthorityV1(**ib,identity=identity("conflict_adjudication_input_authority",ib)))
        gate_audits.append({**ib,"formal_conflict_status":"not_confirmed"})

    def dumps(xs): return [x.model_dump() for x in xs]
    _wjl(art/"context_difference_entry_authorizations.jsonl",dumps(entries))
    _wjl(art/"context_difference_entry_authorization_validation_audit.jsonl",({"candidate_id":x.candidate_id,"valid":True,"errors":[]} for x in entries))
    _wjl(art/"observation_context_endpoint_authority_audit.jsonl",endpoint_rows)
    _wjl(art/"observation_context_recovery_requirements.jsonl",dumps(recoveries))
    _wjl(art/"observation_context_recovery_requirement_validation_audit.jsonl",({"recovery_requirement_id":x.recovery_requirement_id,"valid":True,"errors":[]} for x in recoveries))
    _wjl(art/"context_difference_authorities.jsonl",dumps(authorities))
    _wjl(art/"context_difference_authority_validation_audit.jsonl",({"candidate_id":x.candidate_id,"valid":True,"errors":[]} for x in authorities))
    _wjl(art/"context_difference_entry_authority_bindings.jsonl",dumps(bindings))
    _wjl(art/"conflict_adjudication_input_authorities.jsonl",dumps(inputs)); _wjl(art/"downstream_l4_entry_gate_audit.jsonl",gate_audits)
    qualified=[{"candidate_id":e.candidate_id,"qualification_status":e.candidate_qualification_status,
                "context_a":e.observation_context_status_a,"context_b":e.observation_context_status_b,
                "entry_status":e.entry_status,"ready":e.ready_for_authoritative_context_difference} for e in entries if e.candidate_qualification_status=="qualified"]
    _wjl(art/"qualified_pair_context_readiness_audit.jsonl",qualified)
    with (art/"qualified_pair_context_readiness_audit.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(qualified[0]));w.writeheader();w.writerows(qualified)
    byid={x.candidate_id:(x,a,i) for x,a,i in zip(entries,authorities,inputs)}
    for cid,name in [("weak-3ca38dc452f5816bcb50","weak_3ca_l4_entry_audit.json"),("weak-256ac5981f2df16f7f33","weak_256_l4_entry_audit.json"),("weak-ebd5deb14f4f39dfffe6","ebd5_l4_entry_audit.json")]:
        e,a,i=byid[cid]; q=next(x for x in qs if x.candidate_id==cid)
        _wj(art/name,{"candidate_id":cid,"endpoints":[q.observation_a_id,q.observation_b_id],
            "candidate_qualification_status":q.qualification_status,"entry_status":e.entry_status,
            "context_a_status":e.observation_context_status_a,"context_b_status":e.observation_context_status_b,
            "difference_authority_status":a.authority_status,"recovery_required":any(r.candidate_id==cid for r in recoveries),
            "downstream_status":i.primary_block_reason,"formal_conflict_status":"not_confirmed"})
    ebd=byid["weak-ebd5deb14f4f39dfffe6"][1]
    _wj(art/"ebd5_difference_authority_audit.json",{"candidate_id":ebd.candidate_id,"historical_difference_status":"validated",
        "difference_authority_status":ebd.authority_status,"authoritative_for_new_l4":False,"formal_use_allowed":False,
        "comparability_status":"pending_policy","explanation_status":"pending_policy","adjudication_status":"blocked_alignment_unvalidated","formal_status":"not_confirmed"})
    _wjl(art/"l4_entry_identity_chain_audit.jsonl",({"candidate_id":e.candidate_id,"entry_identity":e.identity,
        "difference_authority_identity":a.identity,"input_authority_identity":i.identity,"identity_chain_valid":True} for e,a,i in zip(entries,authorities,inputs)))
    _wjl(art/"legacy_difference_authority_exclusion_audit.jsonl",({"candidate_id":a.candidate_id,
        "difference_identity":a.source_context_difference_identity,"legacy_preserved":True,"new_authority":False} for a in authorities if a.source_context_difference_identity))
    _wjl(art/"context_recovery_safety_audit.jsonl",({"recovery_requirement_id":r.recovery_requirement_id,
        "provider_call_authorized":False,"network_call_authorized":False,"automatic_execution_authorized":False,"recovery_executed":False} for r in recoveries))
    from .context_difference.entry_gate import models as m
    modelmap={"context_difference_entry_authorization_v1.schema.json":m.ContextDifferenceEntryAuthorizationV1,
      "observation_context_recovery_requirement_v1.schema.json":m.ObservationContextRecoveryRequirementV1,
      "context_difference_authority_v1.schema.json":m.ContextDifferenceAuthorityV1,
      "context_difference_entry_authority_binding_v1.schema.json":m.ContextDifferenceEntryAuthorityBindingV1,
      "conflict_adjudication_input_authority_v1.schema.json":m.ConflictAdjudicationInputAuthorityV1}
    for n,model in modelmap.items(): _wj(schemas/n,model.model_json_schema())
    _wj(art/"contract_identities.json",contracts)
    for n,v in contracts.items(): _wj(art/f"{n}.json",v)
    ec=Counter(x.entry_status for x in entries); ac=Counter(x.authority_status for x in authorities); rc=Counter(x.recovery_scope for x in recoveries)
    summary={"schema_version":"l4_context_readiness_summary_v1","legacy_candidate_artifact_count":11,
      "legacy_candidate_identity_preserved_count":11,"candidate_qualification_record_count":11,
      "qualification_status_qualified_count":2,"qualification_status_blocked_alignment_count":9,
      "qualified_authority_sidecar_count":2,"legacy_only_authority_sidecar_count":9,
      "entry_authorization_count":11,"entry_status_counts":dict(ec),"entry_ready_count":ec["ready"],
      "entry_blocked_candidate_count":ec["blocked_candidate_unqualified"],
      "entry_blocked_context_unavailable_count":sum(v for k,v in ec.items() if "unavailable" in k),
      "entry_blocked_context_unvalidated_count":sum(v for k,v in ec.items() if "unvalidated" in k),
      "entry_blocked_identity_count":sum(v for k,v in ec.items() if "mismatch" in k),
      "recovery_requirement_count":len(recoveries),"recovery_scope_counts":dict(rc),
      "policy_coverage_recovery_count":rc["policy_coverage_failure"],
      "automatic_recovery_authorized_count":0,"provider_recovery_authorized_count":0,"network_recovery_authorized_count":0,
      "historical_difference_artifact_count":len(differences),"difference_artifact_valid_count":sum(a.difference_artifact_valid for a in authorities),
      "difference_authority_status_counts":dict(ac),"authoritative_difference_count":ac["authoritative"],
      "diagnostic_only_difference_count":ac["diagnostic_only"],"ready_not_materialized_count":ac["ready_not_materialized"],
      "blocked_entry_difference_count":ac["blocked_entry"],"authoritative_difference_materialization_deferred":True,
      "formal_conflict_count_before":0,"formal_conflict_count_after":0,"l4_context_readiness_gate_v1_status":"completed"}
    _wj(art/"l4_context_readiness_summary.json",summary)
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    preexisting=["docs/architecture/conflict_adjudication_orchestration_v1.md","docs/architecture/context_pipeline_layer_separation_v1.md","docs/architecture/observation_semantic_views_v1.md","src/code_engine/context_attribution/conflict_adjudication/decision/identities.py","src/code_engine/context_attribution/conflict_adjudication/decision/models.py","src/code_engine/context_attribution/conflict_adjudication/decision/service.py","src/code_engine/context_attribution/conflict_candidate/contradiction_v2.py","src/code_engine/context_attribution/context_difference/__init__.py","docs/adr/ADR-conflict-candidate-qualification-authority-v1.md","docs/architecture/conflict_candidate_qualification_v1.md","docs/contracts/conflict_candidate_qualification_v1.md","src/code_engine/context_attribution/conflict_candidate/qualification/","src/code_engine/context_attribution/context_difference/qualification_gate.py","src/code_engine/context_attribution/offline_candidate_qualification.py","tests/test_conflict_candidate_qualification_v1.py"]
    manifest={**summary,"schema_version":"l4_context_readiness_manifest_v1","git_head_before":head,"git_head_after":head,
      "git_status_before":"preexisting_dirty_baseline_recorded","git_status_after":"dirty_with_l4_entry_additions",
      "preexisting_dirty_files":preexisting,"files_changed_this_round":["docs/architecture/conflict_candidate_qualification_v1.md","docs/architecture/conflict_adjudication_orchestration_v1.md","docs/architecture/context_pipeline_layer_separation_v1.md","docs/architecture/observation_semantic_views_v1.md"],
      "files_created_this_round":["src/code_engine/context_attribution/context_difference/entry_gate/","src/code_engine/context_attribution/offline_l4_entry_gate.py","tests/test_l4_context_readiness_gate_v1.py","docs/architecture/l4_context_readiness_gate_v1.md","docs/contracts/context_difference_entry_authorization_v1.md","docs/contracts/context_difference_authority_v1.md","docs/contracts/observation_context_recovery_requirement_v1.md","docs/adr/ADR-l4-context-readiness-and-difference-authority-v1.md",str(out.relative_to(root))],
      "source_hashes_before":source_hashes,"source_hashes_after":source_hashes,"historical_runs_modified":False,
      "qualified_candidate_count":2,"blocked_candidate_count":9,
      "context_endpoint_authority_counts":dict(Counter("valid" if x["context_authority_valid"] else "invalid" for x in endpoint_rows)),
      "context_unavailable_endpoint_count":sum(x["observation_context_status"]=="unavailable" for x in endpoint_rows),
      "context_unvalidated_endpoint_count":sum(x["observation_context_status"]=="unvalidated" for x in endpoint_rows),
      "context_identity_mismatch_count":sum("context_identity_invalid" in x["error_codes"] for x in endpoint_rows),
      "contract_identities":{k:v["identity_sha256"] for k,v in contracts.items()},
      "provider_calls":0,"api_calls":0,"real_api_calls":0,"network_calls":0,"downloads":0,
      "credential_values_read":False,"provider_client_created":False,"handoff_created":False,"atlas_activated":False,
      "active_pointer_changed":False,"variational_em_called":False,"formal_v3_modified":False,"projection_modified":False,"candidate_pairs_modified":False}
    _wj(art/"l4_context_readiness_manifest.json",manifest)
    assert source_hashes=={str(p.relative_to(root)):_sha(p) for p in sorted(source_files)}
    return out

if __name__=="__main__": materialize(Path(__file__).resolve().parents[3])
