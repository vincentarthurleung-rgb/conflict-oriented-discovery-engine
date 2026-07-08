"""Replay downstream case stages from immutable upstream checkpoints."""
from __future__ import annotations
import argparse,json,shutil
from datetime import datetime,timezone
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle
from code_engine.cli.l2_canonicalization_audit import audit as l2_audit,write as write_l2_audit
from code_engine.validation.case_routing import load_case_domain_profile

REUSED=("abstract_l1_claims.jsonl","abstract_l1_summary.json","run_paper_manifest.jsonl","acquired_paper_provenance.jsonl","search_plan.json","case_domain_profile.json","domain_profile.json","intake.json","semantic_search_intent.json","acquisition_report.json")

def replay(case_profile,search_plan,source_run,from_stage,output_root,output_suffix,bundle_id_suffix,*,no_l1=True,network=False,api=False,entity_network_lookup=False,entity_llm_cleaner=False,skip_fulltext=True,skip_l7=True,overwrite_bundle=False,bundle_root="case_bundles",case_version=None):
    if not no_l1: raise ValueError("L1 replay is not implemented; use the normal case runner")
    source=Path(source_run).resolve();profile=load_case_domain_profile(case_profile);stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    target=Path(output_root)/f"{stamp}_{profile.case_id}_{output_suffix}"
    if target.exists(): raise FileExistsError(f"replay run exists: {target}")
    shutil.copytree(source,target);artifacts=target/"artifacts"
    reused=[name for name in REUSED if (artifacts/name).is_file()]
    required="abstract_l1_claims.jsonl"
    if required not in reused: shutil.rmtree(target);raise FileNotFoundError(f"checkpoint missing required artifact: {required}")
    shutil.copy2(case_profile,artifacts/"case_domain_profile.json");shutil.copy2(search_plan,artifacts/"search_plan.json")
    rerun=[]
    if from_stage=="l2":
        from code_engine.workflow.steps import run_l2_abstract_step,run_abstract_conflict_screening_step
        run_l2_abstract_step(run_dir=target,l1_mode="abstract_screening",execute=True,network=network,api=api,entity_network_lookup=entity_network_lookup,entity_llm_cleaner=entity_llm_cleaner)
        rerun.append("l2")
        run_abstract_conflict_screening_step(run_dir=target,l1_mode="abstract_screening");rerun.append("l3")
    if from_stage in {"l2","l3"}:
        from code_engine.reporting.full_abstract_pipeline import build_l4_context_mining,build_l5_context_attribution
        build_l4_context_mining(target);build_l5_context_attribution(target);rerun.extend(["l4","l5"])
    if from_stage in {"l2","l3","l6"}:
        from code_engine.reporting.full_abstract_pipeline import build_l6_mechanism_graph
        build_l6_mechanism_graph(target);rerun.append("l6")
    graph_count=sum(1 for x in (artifacts/"l2_graph_observations.jsonl").read_text().splitlines() if x.strip()) if (artifacts/"l2_graph_observations.jsonl").is_file() else 0
    core_count=sum(1 for x in (artifacts/"l2_core_graph_observations.jsonl").read_text().splitlines() if x.strip()) if (artifacts/"l2_core_graph_observations.jsonl").is_file() else 0
    conflict_summary={"status":"completed","true_graph_conflict_count":0,"source":"stage_replay","conflict_reasoning_observation_count":core_count};(artifacts/"graph_conflict_summary.json").write_text(json.dumps(conflict_summary,indent=2)+"\n")
    (artifacts/"hypothesis_summary.json").write_text(json.dumps({"status":"no_input","formal_hypothesis_count":0,"reason":"no_replay_conflict_inputs"},indent=2)+"\n")
    from code_engine.discovery.lanes import build_discovery_lanes,synchronize_seed_metadata
    discovery=build_discovery_lanes(target)["summary"]
    seed_provenance=synchronize_seed_metadata(target)
    if skip_l7:(artifacts/"l7_external_validation_summary.json").write_text(json.dumps({"status":"skipped","executed_validators":[],"skipped_validators":["all"],"reason":"stage_replay_skip_l7","network_used":network},indent=2)+"\n")
    if skip_fulltext:
        (artifacts/"l35_fulltext_retrieval_summary.json").write_text(json.dumps({"status":"planned_discovery_escalation","reason":"offline_replay_selected_candidates_without_acquisition","network_used":network,"candidate_paper_count":discovery["fulltext_escalation_candidate_count"],"fulltext_escalation_mode":discovery["fulltext_escalation_mode"],"fulltext_escalation_candidate_count":discovery["fulltext_escalation_candidate_count"]},indent=2)+"\n")
        for name in ("l35_fulltext_l1_summary.json","l35_fulltext_conflict_confirmation_summary.json"):(artifacts/name).write_text(json.dumps({"status":"skipped","reason":"stage_replay_no_llm_no_network","network_used":network},indent=2)+"\n")
    audit_result=l2_audit(target);write_l2_audit(audit_result,artifacts)
    # --- read entity resolution audit to capture actual network call counts ---
    entity_audit_path = artifacts / "entity_resolution_audit.json"
    entity_network_calls = 0
    entity_audit_skipped_reason = None
    if entity_audit_path.is_file():
        try:
            entity_audit = json.loads(entity_audit_path.read_text(encoding="utf-8"))
            entity_network_calls = int(entity_audit.get("network_calls_made", 0))
        except (json.JSONDecodeError, OSError):
            pass
    # Determine skip reason based on flag configuration (not just network alone)
    if not network:
        entity_audit_skipped_reason = "entity_external_lookup_skipped_because_network_disabled"
    elif not entity_network_lookup:
        entity_audit_skipped_reason = "entity_external_lookup_skipped_because_entity_network_lookup_disabled"
    # --- read entity llm cleaner audit to capture actual call counts ---
    llm_cleaner_audit_path = artifacts / "entity_llm_cleaner_summary.json"
    llm_cleaner_fields: dict = {}
    if llm_cleaner_audit_path.is_file():
        try:
            llm_cleaner_summary = json.loads(llm_cleaner_audit_path.read_text(encoding="utf-8"))
            llm_cleaner_fields = {
                "entity_llm_cleaner_enabled": entity_llm_cleaner,
                "entity_llm_cleaner_calls_made": int(llm_cleaner_summary.get("entity_llm_cleaner_calls_made", 0)),
                "entity_llm_cleaner_cleaned_count": int(llm_cleaner_summary.get("entity_llm_cleaner_cleaned_count", 0)),
                "entity_llm_cleaner_failed_count": int(llm_cleaner_summary.get("entity_llm_cleaner_failed_count", 0)),
                "entity_llm_suggested_unverified_count": int(llm_cleaner_summary.get("entity_llm_suggested_unverified_count", 0)),
                "entity_external_verified_after_llm_cleaning_count": int(llm_cleaner_summary.get("entity_external_verified_after_llm_cleaning_count", 0)),
                "entity_external_lookup_after_cleaning_calls_made": int(llm_cleaner_summary.get("entity_external_lookup_after_cleaning_calls_made", 0)),
            }
        except (json.JSONDecodeError, OSError):
            llm_cleaner_fields = {"entity_llm_cleaner_enabled": entity_llm_cleaner}
    else:
        llm_cleaner_fields = {"entity_llm_cleaner_enabled": entity_llm_cleaner}
    manifest={"schema_version":"case_stage_replay_v1","source_run":str(source),"new_run":str(target.resolve()),"case_id":profile.case_id,"from_stage":from_stage,"reused_artifacts":reused,"rerun_stages":rerun,"skipped_stages":["acquisition","l1"]+(["fulltext_network_and_l1"] if skip_fulltext else [])+(["l7"] if skip_l7 else []),"network_used":network,"api_used":api,"llm_used":False,"entity_network_lookup_enabled":entity_network_lookup,"entity_llm_proposer_enabled":False,"entity_network_calls_made":entity_network_calls,"entity_external_lookup_skipped_reason":entity_audit_skipped_reason,"created_at":datetime.now(timezone.utc).isoformat(),"reason":"downstream_replay_from_checkpoint","replay_source_run":str(source),"replay_from_stage":from_stage,"upstream_artifacts_reused":True,"raw_l1_claims_reused":sum(1 for x in (artifacts/required).read_text().splitlines() if x.strip()),"graph_observation_count":graph_count,"core_observation_count":core_count,"true_graph_conflict_count":0,"formal_hypothesis_count":0,**{k:discovery[k] for k in ("l2_retained_observation_count","seed_neighborhood_observation_count","reviewable_graph_observation_count","weak_conflict_candidate_count","fulltext_escalation_candidate_count")},**seed_provenance,**llm_cleaner_fields}
    (target/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n");(artifacts/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    network_status_line = f"- Network used: {network}" + (f" (entity external lookup skipped: {entity_audit_skipped_reason})" if entity_audit_skipped_reason else f" (entity network calls: {entity_network_calls})")
    report=f"# Stage Replay Report\n\n- Source: `{source}`\n- New run: `{target}`\n- From stage: `{from_stage}`\n- LLM used: false\n{network_status_line}\n- L1 claims reused: {manifest['raw_l1_claims_reused']}\n- Graph observations: {graph_count}\n- Conflict observations: {core_count}\n"
    (target/"replay_report.md").write_text(report);(artifacts/"replay_report.md").write_text(report)
    pipeline={"case_id":profile.case_id,"status":"completed","is_replay_run":True,"replay_from_stage":from_stage,"stage_counts":{"raw_l1_claims_reused":manifest["raw_l1_claims_reused"],"graph_observations":graph_count,"core_observations":core_count,"conflicts":0,"hypotheses":0},"warnings":[]};(artifacts/"pipeline_stage_summary.json").write_text(json.dumps(pipeline,indent=2)+"\n")
    provenance={"replay_source_run":str(source),"replay_from_stage":from_stage,"upstream_artifacts_reused":True}
    for name in ("l2_abstract_summary.json","l2_canonicalization_audit_summary.json","graph_conflict_summary.json","l4_context_mining_summary.json","l5_context_attribution_summary.json","l6_mechanism_graph_summary.json","hypothesis_summary.json","pipeline_stage_summary.json"):
        path=artifacts/name
        if path.is_file():
            try:value=json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:continue
            if isinstance(value,dict):value.update(provenance);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    version=case_version or f"v2_replay_{from_stage}";bundle,case_manifest=export_case_bundle(target,case_profile,bundle_root,bundle_id_suffix=bundle_id_suffix,overwrite_bundle=overwrite_bundle,manifest_overrides={"case_version":version,"is_replay_run":True,"is_replay":True,"replay_from_stage":from_stage,"source_run":str(source),"source_case_version":"v1_zero_claim","llm_used":False,"network_used":network,"api_used":api,"entity_network_lookup_enabled":entity_network_lookup,"entity_llm_proposer_enabled":False,"entity_llm_cleaner_enabled":entity_llm_cleaner,"entity_network_calls_made":entity_network_calls,"entity_external_lookup_skipped_reason":entity_audit_skipped_reason,"replay_source_run":str(source)})
    manifest.update({"bundle":str(bundle),"case_version":version,"scientific_output_class":case_manifest["scientific_output_class"]});(target/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n");return manifest

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--case-profile",required=True);p.add_argument("--search-plan-file",required=True);p.add_argument("--source-run",required=True);p.add_argument("--from-stage",choices=("l2","l3","l6","bundle"),required=True);p.add_argument("--output-root",default="runs");p.add_argument("--output-suffix",required=True);p.add_argument("--bundle-id-suffix",required=True);p.add_argument("--no-l1",action="store_true");p.add_argument("--network",action="store_true",help="Enable external entity database lookups (PubChem, ChEMBL, MyGene, UniProt) during entity normalization.");p.add_argument("--no-network",action="store_true",help="Explicitly disable external entity lookups (default behavior).");p.add_argument("--api",action="store_true",help="Enable API-based services alongside network lookups.");p.add_argument("--entity-network-lookup",action="store_true",help="Enable external entity database candidate generation (PubChem, ChEMBL, MyGene, UniProt). Requires --network.");p.add_argument("--no-entity-network-lookup",action="store_true",help="Explicitly disable external entity database lookups (default).");p.add_argument("--entity-llm-cleaner",action="store_true",help="Enable LLM-assisted entity surface cleaning before external lookup.");p.add_argument("--no-entity-llm-cleaner",action="store_true",help="Explicitly disable LLM entity surface cleaner (default).");p.add_argument("--skip-fulltext",action="store_true");p.add_argument("--skip-l7",action="store_true");p.add_argument("--overwrite-bundle",action="store_true");a=p.parse_args(argv)
 network_enabled = a.network and not a.no_network
 api_enabled = a.api and not a.no_network
 entity_network_lookup = a.entity_network_lookup and not a.no_entity_network_lookup
 entity_llm_cleaner = a.entity_llm_cleaner and not a.no_entity_llm_cleaner
 result=replay(a.case_profile,a.search_plan_file,a.source_run,a.from_stage,a.output_root,a.output_suffix,a.bundle_id_suffix,no_l1=a.no_l1,network=network_enabled,api=api_enabled,entity_network_lookup=entity_network_lookup,entity_llm_cleaner=entity_llm_cleaner,skip_fulltext=a.skip_fulltext,skip_l7=a.skip_l7,overwrite_bundle=a.overwrite_bundle);print(json.dumps(result,indent=2,ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
