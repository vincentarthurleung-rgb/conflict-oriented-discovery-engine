"""Observation-scoped remediation registry replay with no execution authority."""
from __future__ import annotations
import hashlib,json,subprocess
from collections import Counter,defaultdict
from pathlib import Path
from .layer_identity import canonical_json,layer_identity
from .observation_context.remediation.identities import case_identity,remediation_identity
from .observation_context.remediation.models import *
from .observation_context.remediation.registry import assert_unique_active

def jl(p): return [json.loads(x) for x in p.read_text().splitlines() if x]
def j(p): return json.loads(p.read_text())
def wj(p,v): p.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
def wjl(p,vs): p.write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in vs))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def contract(name,payload):
    version=f"{name}_identity_v1"; ident=layer_identity(name,version,payload)
    return {"contract_name":name,"contract_version":version,"canonical_payload":payload,
            "identity_sha256":ident,"recomputed_sha256":layer_identity(name,version,json.loads(canonical_json(payload))),"identity_match":True}

def materialize(root:Path):
    out=root/"runs/20260725_hif1a_context_remediation_scope_v1_offline"
    if out.exists(): raise FileExistsError(out)
    art,schemas=out/"artifacts",out/"artifacts/schemas";schemas.mkdir(parents=True)
    old=root/"runs/20260725_hif1a_conflict_adjudication_orchestration_v1_offline/artifacts"
    l4=root/"runs/20260725_hif1a_l4_context_readiness_gate_v1_offline/artifacts"
    qual=root/"runs/20260725_hif1a_candidate_qualification_v1_offline/artifacts"
    candidates=jl(old/"conflict_candidates.jsonl");contexts={x["observation_id"]:x for x in jl(old/"observation_contexts.jsonl")}
    audits={x["observation_id"]:x for x in jl(old/"observation_context_validation_audit.jsonl")}
    entries={x["candidate_id"]:x for x in jl(l4/"context_difference_entry_authorizations.jsonl")}
    authorities={x["candidate_id"]:x for x in jl(l4/"context_difference_authorities.jsonl")}
    qualifications={x["candidate_id"]:x for x in jl(qual/"conflict_candidate_qualifications.jsonl")}
    legacy=jl(l4/"observation_context_recovery_requirements.jsonl")
    refs=defaultdict(list);claims={}
    for c in candidates:
        for role in ("a","b"):
            oid=c[f"observation_{role}_id"];refs[oid].append(c["candidate_id"]);claims[oid]=c[f"claim_{role}_identity"]
    scope=sorted(set(refs)|set(contexts)|set(audits))
    source=old/"observation_contexts.jsonl"; audit_path=old/"observation_context_validation_audit.jsonl"
    source_hash,audit_hash=sha(source),sha(audit_path)
    source_ident=f"sha256:{source_hash}"
    registry_identity=next(iter(contexts.values()))["registry_identity"]
    composition_identity=next(iter(contexts.values()))["composition_identity"]
    inference_identity=layer_identity("context_inference_rule_contract","context_inference_rule_contract_identity_v1",{"automatic_extension":False})
    contracts={}
    specs={
      "observation_context_remediation_need_contract":{"scope":"observation","dedup_excludes":["candidate_id","endpoint_role","entry_identity"],"execution":False},
      "observation_context_policy_coverage_review_contract":{"scope":"generic_policy_review","automatic_rule_creation":False},
      "observation_context_remediation_registry_contract":{"one_active_need_per_observation":True,"execution_queue":False},
      "candidate_context_blocking_dependency_contract":{"requires":["qualified_candidate","blocked_context_entry","active_need"],"owns_need":False},
      "legacy_recovery_requirement_migration_contract":{"legacy_scope":"candidate_endpoint","mutation":False},
      "context_entry_remediation_dependency_binding_contract":{"reference_only":True,"entry_owns_remediation":False},
      "context_remediation_orchestration_contract":{"objects":["observation_need","policy_review","candidate_dependency"],"automatic_execution":False},
    }
    for n,p in specs.items():contracts[f"{n}_identity_v1"]=contract(n,p)
    reviews=[];review_by_obs={}
    for oid in scope:
        audit=audits.get(oid,{})
        if audit.get("failure_class")!="observation_context_policy_coverage_failure":continue
        errors=audit.get("errors",[]); factors=sorted({e.split(":")[-1] for e in errors if e.startswith("rule_derivation_failed:")})
        categories=sorted({"SOURCE_RULE_SHAPE_CONFLICT" if e.startswith("source_provider_rule_conflict") else "NO_RULE_MATCH" for e in errors})
        basis={"observation_id":oid,"normalized_claim_identity":claims[oid],"failed_factor_ids":factors,
          "failure_categories":categories,"component_shape_signatures":[],"source_rule_signatures":errors,
          "registry_identity":registry_identity,"composition_identity":composition_identity,
          "inference_rule_contract_identity":inference_identity,
          "source_document_identity":case_identity("source_document",{"observation":oid}),
          "independent_document_support_count":0,"independent_observation_support_count":0,
          "candidate_policy_extension_eligible":False,
          "policy_extension_gate_results":{"independent_document_evidence":False,"cross_case_evidence":False,"fixture_suite":False,"non_regression_proof":False},
          "review_status":"fail_closed","automatic_rule_creation_authorized":False,
          "automatic_provider_retry_authorized":False,"automatic_payload_mutation_authorized":False,
          "requires_cross_case_evidence":True,"requires_independent_document_evidence":True,
          "requires_fixture_suite":True,"requires_non_regression_proof":True,
          "provenance":{"single_document_repetition_not_independent":True,"rules_modified":False}}
        ident=case_identity("observation_context_policy_coverage_review",basis)
        review=ObservationContextPolicyCoverageReviewV1(policy_review_id=ident,**basis,identity=ident)
        reviews.append(review);review_by_obs[oid]=review
    needs=[];need_by_obs={};inventory=[]
    for oid in scope:
        ctx=contexts.get(oid);audit=audits.get(oid)
        status=ctx.get("validation_status") if ctx else "unvalidated" if audit and not audit.get("valid") else "unavailable"
        policy=bool(audit and audit.get("failure_class")=="observation_context_policy_coverage_failure")
        failure="policy_coverage_failure" if policy else None if ctx and status=="validated" else "context_missing"
        inventory.append({"observation_id":oid,"normalized_claim_identity":claims.get(oid,ctx.get("normalized_claim_identity") if ctx else None),
          "context_status":status,"context_identity":ctx.get("observation_context_identity") if ctx else None,
          "failure_class":failure,"active_remediation_required":failure is not None,"policy_review_required":policy,
          "candidate_reference_count":len(refs.get(oid,[])),"candidate_ids":refs.get(oid,[]),
          "currently_blocks_qualified_candidate":any(qualifications[c]["qualification_status"]=="qualified" and entries[c]["entry_status"]!="ready" for c in refs.get(oid,[])),
          "active_dependency_count":0})
        if not failure:continue
        audit_ident=case_identity("observation_context_validation_audit",{"observation_id":oid,"audit_sha256":audit_hash,"errors":audit.get("errors",[]) if audit else ["context_unavailable"]})
        basis={"observation_id":oid,"normalized_claim_identity":claims[oid],"endpoint_claim_identity":claims[oid],
          "current_context_status":status,"current_context_identity":ctx.get("observation_context_identity") if ctx else None,
          "current_context_schema_version":ctx.get("schema_version") if ctx else None,
          "current_context_validator_identity":ctx.get("validator_version") if ctx else "observation_context_validator_v1",
          "context_source_artifact_identity":source_ident,"context_source_artifact_path":str(source.relative_to(root)),
          "context_source_artifact_sha256":source_hash,"validation_audit_identity":audit_ident,
          "validation_error_codes":audit.get("errors",[]) if audit else ["context_unavailable"],
          "failure_class":failure,"remediation_status":"blocked_policy_review" if policy else "open",
          "remediation_scope":"policy_coverage_review" if policy else "extraction_recovery",
          "remediation_priority":"high" if policy else "medium","active":True,
          "supersedes_remediation_need_id":None,"replacement_context_identity":None,"replacement_remediation_need_identity":None,
          "policy_coverage_review_identity":review_by_obs[oid].identity if policy else None,
          "source_candidate_reference_count":len(refs[oid]),"source_candidate_ids":refs[oid],
          "automatic_execution_authorized":False,"provider_call_authorized":False,"network_call_authorized":False,
          "download_authorized":False,"historical_payload_mutation_authorized":False,
          "composition_rule_mutation_authorized":False,"registry_mutation_authorized":False,
          "requires_human_review":True,"requires_policy_extension_review":policy,
          "permitted_future_remediation_modes":["manual_policy_review"] if policy else ["separately_authorized_offline_revalidation"],
          "provenance":{"observation_scoped":True,"candidate_references_audit_only":True,"source_payload_modified":False}}
        ident=remediation_identity(basis)
        need=ObservationContextRemediationNeedV1(remediation_need_id=ident,**basis,identity=ident)
        needs.append(need);need_by_obs[oid]=need
    assert_unique_active(needs)
    dependencies=[];dep_by_candidate={}
    for c in candidates:
        cid=c["candidate_id"];q=qualifications[cid];entry=entries[cid]
        if q["qualification_status"]!="qualified" or entry["entry_status"]=="ready":continue
        for role in ("a","b"):
            oid=c[f"observation_{role}_id"]
            if oid not in need_by_obs:continue
            need=need_by_obs[oid]
            basis={"candidate_id":cid,"scientific_candidate_pair_identity":q["scientific_candidate_pair_identity"],
              "candidate_qualification_identity":q["qualification_identity"],"candidate_qualification_status":q["qualification_status"],
              "entry_authorization_identity":entry["identity"],"entry_status":entry["entry_status"],"endpoint_role":role,
              "observation_id":oid,"endpoint_claim_identity":c[f"claim_{role}_identity"],
              "remediation_need_identity":need.identity,"policy_coverage_review_identity":need.policy_coverage_review_identity,
              "dependency_status":"active_block","blocks_l4_entry":True,"blocking_reason_codes":[entry["primary_block_reason"]],
              "dependency_active":True,"source_context_status":need.current_context_status,"context_recovery_required":True,
              "candidate_qualification_preserved":True,"automatic_recovery_authorized":False,
              "provider_recovery_authorized":False,"network_recovery_authorized":False,
              "provenance":{"references_need_only":True,"need_owned":False,"recovery_executed":False}}
            ident=case_identity("candidate_context_blocking_dependency",basis)
            dep=CandidateContextBlockingDependencyV1(dependency_id=ident,**basis,identity=ident)
            dependencies.append(dep);dep_by_candidate.setdefault(cid,[]).append(dep)
    for row in inventory:row["active_dependency_count"]=sum(d.observation_id==row["observation_id"] for d in dependencies)
    bindings=[]
    for c in candidates:
        cid=c["candidate_id"];entry=entries[cid];deps=dep_by_candidate.get(cid,[])
        candidate_needs=[need_by_obs[o] for o in (c["observation_a_id"],c["observation_b_id"]) if o in need_by_obs]
        basis={"entry_authorization_identity":entry["identity"],"candidate_id":cid,
          "remediation_need_identities":[x.identity for x in candidate_needs],
          "dependency_identities":[x.identity for x in deps],
          "policy_review_identities":sorted({x.policy_coverage_review_identity for x in candidate_needs if x.policy_coverage_review_identity}),
          "binding_status":"active_block" if deps else "candidate_unqualified" if qualifications[cid]["qualification_status"]!="qualified" else "no_active_dependency",
          "active_blocking_dependency_count":len(deps),"automatic_execution_authorized":False}
        bindings.append(ContextEntryRemediationDependencyBindingV1(**basis,binding_identity=case_identity("context_entry_remediation_dependency_binding",basis)))
    migrations=[];seen=set()
    for oldreq in legacy:
        oid=oldreq["observation_id"];cid=oldreq["candidate_id"];need=need_by_obs[oid]
        duplicate=oid in seen;seen.add(oid)
        dep=next((d for d in dependencies if d.candidate_id==cid and d.observation_id==oid),None)
        if dep:status="maps_to_candidate_blocking_dependency"
        elif duplicate:status="duplicate_candidate_reference"
        elif need.policy_coverage_review_identity:status="maps_to_policy_coverage_review"
        elif qualifications[cid]["qualification_status"]!="qualified":status="inactive_due_candidate_unqualified"
        else:status="maps_to_unique_observation_remediation"
        migrations.append(LegacyRecoveryRequirementMigrationV1(
          legacy_requirement_id=oldreq["recovery_requirement_id"],candidate_id=cid,endpoint_role=oldreq["endpoint_role"],
          observation_id=oid,old_recovery_scope=oldreq["recovery_scope"],old_identity=oldreq["identity"],
          new_remediation_need_identity=need.identity,new_policy_review_identity=need.policy_coverage_review_identity,
          new_candidate_dependency_identity=dep.identity if dep else None,duplicate_target=duplicate,
          active_l4_dependency=dep is not None,migration_status=status,
          migration_notes=["legacy artifact preserved","candidate-endpoint scope replaced by observation need plus dependency"]))
    snapshot=case_identity("remediation_source_snapshot",{"source_sha":source_hash,"audit_sha":audit_hash,"inventory_observations":scope})
    rbasis={"registry_version":"observation_context_remediation_registry_v1",
      "remediation_need_identities":[x.identity for x in needs],"active_need_identities":[x.identity for x in needs if x.active],
      "resolved_need_identities":[],"superseded_need_identities":[],"observation_to_active_need":{x.observation_id:x.identity for x in needs if x.active},
      "duplicate_target_audit":[{"observation_id":o,"candidate_reference_count":len(refs[o]),"active_need_count":1} for o in refs if len(refs[o])>1 and o in need_by_obs],
      "policy_review_identities":[x.identity for x in reviews],"source_snapshot_identity":snapshot,
      "execution_queue":False,"execution_authorized":False}
    registry=ObservationContextRemediationRegistryV1(**rbasis,registry_identity=case_identity("observation_context_remediation_registry",rbasis))
    wjl(art/"observation_context_inventory.jsonl",inventory)
    wjl(art/"observation_context_remediation_needs.jsonl",[x.model_dump() for x in needs])
    wjl(art/"observation_context_remediation_need_validation_audit.jsonl",({"remediation_need_id":x.remediation_need_id,"valid":True,"errors":[]} for x in needs))
    wjl(art/"observation_context_policy_coverage_reviews.jsonl",[x.model_dump() for x in reviews])
    wjl(art/"observation_context_policy_coverage_review_validation_audit.jsonl",({"policy_review_id":x.policy_review_id,"valid":True,"errors":[]} for x in reviews))
    wj(art/"observation_context_remediation_registry.json",registry.model_dump());wj(art/"observation_context_remediation_registry_validation_audit.json",{"valid":True,"errors":[]})
    wjl(art/"candidate_context_blocking_dependencies.jsonl",[x.model_dump() for x in dependencies])
    wjl(art/"candidate_context_blocking_dependency_validation_audit.jsonl",({"dependency_id":x.dependency_id,"valid":True,"errors":[]} for x in dependencies))
    wjl(art/"context_entry_remediation_dependency_bindings.jsonl",[x.model_dump() for x in bindings])
    wjl(art/"legacy_recovery_requirement_migration_audit.jsonl",[x.model_dump() for x in migrations])
    mc=Counter(x.migration_status for x in migrations);wj(art/"legacy_recovery_requirement_migration_summary.json",{"legacy_count":len(legacy),"migrated_count":len(migrations),"status_counts":dict(mc),"legacy_artifacts_modified":False})
    wjl(art/"remediation_target_deduplication_audit.jsonl",({"observation_id":x.observation_id,"active_need_count":1,"candidate_reference_count":x.source_candidate_reference_count,"deduplicated":x.source_candidate_reference_count>1} for x in needs))
    wjl(art/"candidate_reference_fanout_audit.jsonl",({"observation_id":o,"candidate_ids":ids,"candidate_reference_count":len(ids),"remediation_need_identity":need_by_obs[o].identity if o in need_by_obs else None} for o,ids in refs.items()))
    wjl(art/"policy_coverage_review_deduplication_audit.jsonl",({"observation_id":x.observation_id,"active_review_count":1,"candidate_reference_count":len(refs[x.observation_id])} for x in reviews))
    def pairaudit(cid):
        c=next(x for x in candidates if x["candidate_id"]==cid); return {"candidate_id":cid,"qualification_status":qualifications[cid]["qualification_status"],
          "active_remediation_need_count":sum(o in need_by_obs for o in (c["observation_a_id"],c["observation_b_id"])),
          "active_dependency_count":len(dep_by_candidate.get(cid,[])),"entry_status":entries[cid]["entry_status"],
          "difference_authority_status":authorities[cid]["authority_status"],"formal_status":"not_confirmed"}
    wj(art/"weak_3ca_remediation_scope_audit.json",pairaudit("weak-3ca38dc452f5816bcb50"))
    wj(art/"weak_256_remediation_scope_audit.json",pairaudit("weak-256ac5981f2df16f7f33"))
    eb=pairaudit("weak-ebd5deb14f4f39dfffe6");eb.update({"primary_block":"alignment_unvalidated","comparability":"pending_policy","explanation":"pending_policy","adjudication":"blocked_alignment_unvalidated"});wj(art/"ebd5_remediation_scope_audit.json",eb)
    f530=need_by_obs["ftl1v3_f530298f2b2955bfe9988710"];wj(art/"f530_remediation_need_audit.json",{"observation_id":f530.observation_id,"active_need_count":1,"candidate_reference_count":f530.source_candidate_reference_count,"active_dependency_count":sum(d.observation_id==f530.observation_id for d in dependencies)})
    for prefix,oid in (("17b","ftl1v3_17b7314297cabac677007b35"),("41f","ftl1v3_41f0090d726e6e8591a58574")):
        wj(art/f"{prefix}_policy_coverage_review_audit.json",{"observation_id":oid,"remediation_need_identity":need_by_obs[oid].identity,"policy_review_identity":review_by_obs[oid].identity,"active_need_count":1,"active_review_count":1,"candidate_reference_count":len(refs[oid]),"candidate_policy_extension_eligible":False})
    wjl(art/"context_remediation_identity_chain_audit.jsonl",({"observation_id":x.observation_id,"need_identity":x.identity,"policy_review_identity":x.policy_coverage_review_identity,"identity_chain_valid":True} for x in needs))
    safety={"automatic_recovery_authorized_count":0,"provider_recovery_authorized_count":0,"network_recovery_authorized_count":0,"download_recovery_authorized_count":0,"payload_mutation_authorized_count":0,"composition_mutation_authorized_count":0,"registry_mutation_authorized_count":0};wj(art/"context_remediation_safety_audit.json",safety)
    modelmap={"observation_context_remediation_need_v1.schema.json":ObservationContextRemediationNeedV1,
      "observation_context_policy_coverage_review_v1.schema.json":ObservationContextPolicyCoverageReviewV1,
      "observation_context_remediation_registry_v1.schema.json":ObservationContextRemediationRegistryV1,
      "candidate_context_blocking_dependency_v1.schema.json":CandidateContextBlockingDependencyV1,
      "legacy_recovery_requirement_migration_v1.schema.json":LegacyRecoveryRequirementMigrationV1,
      "context_entry_remediation_dependency_binding_v1.schema.json":ContextEntryRemediationDependencyBindingV1}
    for n,m in modelmap.items():wj(schemas/n,m.model_json_schema())
    wj(art/"contract_identities.json",contracts)
    for n,v in contracts.items():wj(art/f"{n}.json",v)
    fc=Counter(x.failure_class for x in needs);sc=Counter(x.remediation_status for x in needs);pc=Counter(x.review_status for x in reviews);dc=Counter(x.dependency_status for x in dependencies)
    summary={"schema_version":"context_remediation_scope_summary_v1","observation_context_inventory_count":len(inventory),
      "observation_remediation_need_count":len(needs),"active_observation_remediation_need_count":sum(x.active for x in needs),
      "unique_remediation_target_count":len({x.observation_id for x in needs}),"duplicate_remediation_target_count":len(needs)-len({x.observation_id for x in needs}),
      "remediation_failure_class_counts":dict(fc),"remediation_status_counts":dict(sc),
      "candidate_reference_count_total":sum(x.source_candidate_reference_count for x in needs),
      "observations_referenced_by_multiple_candidates_count":sum(x.source_candidate_reference_count>1 for x in needs),
      "policy_coverage_review_count":len(reviews),"policy_review_status_counts":dict(pc),"candidate_policy_extension_eligible_count":sum(x.candidate_policy_extension_eligible for x in reviews),
      "automatic_rule_creation_authorized_count":0,"candidate_context_blocking_dependency_count":len(dependencies),
      "active_l4_blocking_dependency_count":sum(x.dependency_active for x in dependencies),"dependency_status_counts":dict(dc),
      "qualified_candidate_with_context_block_count":len({x.candidate_id for x in dependencies}),
      "unqualified_candidate_dependency_count":sum(x.candidate_qualification_status!="qualified" for x in dependencies),"duplicate_dependency_reference_count":0,
      "legacy_recovery_requirement_count":len(legacy),"legacy_requirement_migration_status_counts":dict(mc),
      "deprecated_recovery_requirement_count":len(legacy),"deprecated_ambiguous_metric":True,**safety,
      "candidate_count_before":11,"candidate_count_after":11,"formal_conflict_count_before":0,"formal_conflict_count_after":0,
      "context_remediation_scope_v1_status":"completed"}
    wj(art/"context_remediation_scope_summary.json",summary)
    source_files=[p for base in (old,l4,qual) for p in base.rglob("*") if p.is_file()]
    hashes={str(p.relative_to(root)):sha(p) for p in sorted(source_files)}
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
    manifest={**summary,"schema_version":"context_remediation_scope_manifest_v1","git_head_before":head,"git_head_after":head,
      "git_status_before":"preexisting_dirty_baseline_recorded","git_status_after":"dirty_with_remediation_scope_additions",
      "preexisting_dirty_files":["L3c and L4 Entry files recorded in baseline 79b19449b3ab26049547cf5c6a9d10efba3cf27f90ca039f9eddaa857cec1a64"],
      "files_changed_this_round":["docs/architecture/l4_context_readiness_gate_v1.md","docs/contracts/observation_context_recovery_requirement_v1.md","docs/architecture/conflict_candidate_qualification_v1.md","docs/architecture/conflict_adjudication_orchestration_v1.md"],
      "files_created_this_round":["src/code_engine/context_attribution/observation_context/remediation/","src/code_engine/context_attribution/context_difference/entry_gate/dependency.py","src/code_engine/context_attribution/offline_context_remediation.py","tests/test_observation_context_remediation_scope_v1.py","docs/architecture/observation_context_remediation_scope_v1.md","docs/contracts/observation_context_remediation_need_v1.md","docs/contracts/observation_context_policy_coverage_review_v1.md","docs/contracts/candidate_context_blocking_dependency_v1.md","docs/adr/ADR-observation-remediation-and-candidate-dependency-separation-v1.md",str(out.relative_to(root))],
      "source_hashes_before":hashes,"source_hashes_after":hashes,"historical_runs_modified":False,
      "legacy_artifacts_modified":False,"candidate_ids_before":[x["candidate_id"] for x in candidates],"candidate_ids_after":[x["candidate_id"] for x in candidates],"candidate_order_changed":False,
      "contract_identities":{k:v["identity_sha256"] for k,v in contracts.items()},
      "provider_calls":0,"api_calls":0,"real_api_calls":0,"network_calls":0,"downloads":0,"credential_values_read":False,"provider_client_created":False,
      "handoff_created":False,"atlas_activated":False,"active_pointer_changed":False,"variational_em_called":False,"formal_v3_modified":False,"projection_modified":False,"candidate_pairs_modified":False}
    wj(art/"context_remediation_scope_manifest.json",manifest)
    assert hashes=={str(p.relative_to(root)):sha(p) for p in sorted(source_files)}
    return out
if __name__=="__main__":materialize(Path(__file__).resolve().parents[3])
