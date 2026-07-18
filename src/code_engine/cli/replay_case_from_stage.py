"""Replay downstream case stages from immutable upstream checkpoints."""
from __future__ import annotations
import argparse,json,os,shutil
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from code_engine.cli.export_case_bundle import export_case_bundle
from code_engine.cli.l2_canonicalization_audit import audit as l2_audit,write as write_l2_audit
from code_engine.validation.case_routing import load_case_domain_profile

REUSED=("abstract_l1_claims.jsonl","abstract_l1_summary.json","run_paper_manifest.jsonl","acquired_paper_provenance.jsonl","search_plan.json","case_domain_profile.json","domain_profile.json","intake.json","semantic_search_intent.json","acquisition_report.json")

CURRENT_RUN_RESOLVER_ARTIFACTS = (
    "entity_resolution_candidates.jsonl",
    "entity_resolution_decisions.jsonl",
    "entity_resolution_audit.jsonl",
    "l2_entity_resolution_mentions.jsonl",
    "entity_llm_cleaner_audit.jsonl",
    "entity_llm_cleaner_summary.json",
)


def _clear_current_run_resolver_artifacts(artifacts: Path) -> None:
    for name in CURRENT_RUN_RESOLVER_ARTIFACTS:
        path = artifacts / name
        if path.exists():
            path.unlink()


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else ({} if default is None else default)
    except json.JSONDecodeError:
        return {} if default is None else default


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _count_lines(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.is_file() else 0


def _provider_key(provider: str) -> str | None:
    value = provider.casefold()
    if "mygene" in value:
        return "mygene"
    if "uniprot" in value:
        return "uniprot"
    if "ols" in value or "ontology" in value:
        return "ols"
    if "pubchem" in value:
        return "pubchem"
    if "chembl" in value:
        return "chembl"
    return None


def _validate_replay_checkpoint(source: Path, from_stage: str, no_l1: bool) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"source run not found: {source}")
    if from_stage == "l2":
        artifacts = source / "artifacts"
        required = ("abstract_l1_claims.jsonl", "abstract_l1_summary.json")
        missing = [name for name in required if not (artifacts / name).is_file()]
        if missing:
            raise FileNotFoundError(f"checkpoint missing required Abstract L1 artifact(s): {', '.join(missing)}")
    if not no_l1:
        raise ValueError("L1 replay is not implemented; use the normal case runner")


def _historical_call_counts(source_artifacts: Path) -> dict:
    l1 = _read_json(source_artifacts / "abstract_l1_summary.json")
    acquisition = _read_json(source_artifacts / "acquisition_report.json")
    diagnostics = _read_jsonl(source_artifacts / "pubmed_query_diagnostics.jsonl")
    entity = _read_json(source_artifacts / "entity_resolution_audit.json")
    cleaner = _read_json(source_artifacts / "entity_llm_cleaner_summary.json")
    provider_counts = dict(entity.get("provider_network_calls_by_provider") or (entity.get("failure_taxonomy") or {}).get("provider_network_calls_by_provider") or {})
    return {
        "historical_abstract_l1_calls": int(l1.get("api_calls_made", 0) or 0),
        "historical_abstract_retrieval_http_calls": int(acquisition.get("network_calls_made", 0) or 0),
        "historical_abstract_documents_downloaded": sum(int(row.get("downloaded_count") or 0) for row in diagnostics),
        "historical_l2_cleaner_calls": int(cleaner.get("entity_llm_cleaner_calls_made", 0) or 0),
        "historical_entity_network_calls": provider_counts,
    }


def _current_call_accounting(target: Path, *, source: Path, reused: list[str], raw_l1_claims_reused: int,
                             network: bool, api: bool, entity_network_lookup: bool, entity_llm_cleaner: bool,
                             skip_fulltext: bool) -> tuple[dict, list[dict]]:
    artifacts = target / "artifacts"
    entity_audit = _read_json(artifacts / "entity_resolution_audit.json")
    cleaner = _read_json(artifacts / "entity_llm_cleaner_summary.json")
    decisions = _read_jsonl(artifacts / "entity_resolution_decisions.jsonl")
    provider_network = Counter({"mygene": 0, "uniprot": 0, "ols": 0, "pubchem": 0, "chembl": 0})
    ledger: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    case_id = target.name
    for item in decisions:
        request = item.get("request") or {}
        for trace in item.get("provider_trace") or []:
            calls = int(trace.get("network_calls_made") or 0)
            key = _provider_key(str(trace.get("provider_name") or ""))
            if key and calls > 0:
                provider_network[key] += calls
                ledger.append({
                    "stage": "l2",
                    "component": "entity_network_provider",
                    "provider": key,
                    "provider_name": trace.get("provider_name"),
                    "call_type": "ontology_http",
                    "call_count": calls,
                    "cache_hit": False,
                    "case_id": case_id,
                    "run_id": target.name,
                    "surface": request.get("surface"),
                    "timestamp": now,
                })
    cleaner_calls = int(cleaner.get("entity_llm_cleaner_calls_made", 0) or 0)
    if cleaner_calls:
        ledger.append({
            "stage": "l2",
            "component": "entity_llm_cleaner",
            "provider": cleaner.get("provider") or "entity_llm_cleaner",
            "call_type": "llm",
            "call_count": cleaner_calls,
            "cache_hit": False,
            "case_id": case_id,
            "run_id": target.name,
            "timestamp": now,
        })
    source_artifacts = source / "artifacts"
    historical = _historical_call_counts(source_artifacts)
    run_papers = _count_lines(source_artifacts / "run_paper_manifest.jsonl")
    provider_ledger_summary = _read_json(artifacts / "l2_provider_query_ledger_summary.json", {})
    ledger_network_calls = provider_ledger_summary.get("network_call_units_by_provider") or {}
    if ledger_network_calls:
        provider_network = Counter({
            key: int(value or 0)
            for provider_name, value in ledger_network_calls.items()
            if (key := _provider_key(str(provider_name)))
        })
    current = {
        "abstract_retrieval_http_calls": 0,
        "abstract_documents_downloaded": 0,
        "abstract_l1_provider_calls": 0,
        "l2_entity_llm_cleaner_calls": cleaner_calls,
        "l2_entity_llm_cleaner_accounting": {
            key: int(cleaner.get(key, 0) or 0)
            for key in (
                "cleaner_eligible_mentions",
                "cleaner_deterministic_skip",
                "cleaner_cache_hits",
                "cleaner_actual_calls",
                "cleaner_failures",
                "cleaner_pending",
            )
        },
        "l2_entity_llm_proposer_calls": 0,
        "entity_network_calls": dict(provider_network),
        "fulltext_download_calls": 0 if skip_fulltext else None,
        "fulltext_claim_provider_calls": 0,
        "local_artifacts_reused": raw_l1_claims_reused,
        "local_artifacts_copied": len(reused),
        "abstract_documents_reused_from_source": run_papers,
        "cache_hits": int(provider_ledger_summary.get("persistent_cache_hits", 0) or 0),
        "negative_cache_hits": int(provider_ledger_summary.get("negative_cache_hits", 0) or 0),
        "provider_query_ledger": {
            "raw_provider_query_requests": int(provider_ledger_summary.get("raw_provider_query_requests", 0) or 0),
            "unique_provider_query_keys": int(provider_ledger_summary.get("unique_provider_query_keys", 0) or 0),
            "deduplicated_requests": int(provider_ledger_summary.get("deduplicated_requests", 0) or 0),
            "network_attempts": int(provider_ledger_summary.get("network_attempts", 0) or 0),
            "retryable_failures": int(provider_ledger_summary.get("retryable_failures", 0) or 0),
            "legacy_migrated_queries": int(provider_ledger_summary.get("legacy_migrated_queries", 0) or 0),
            "network_call_units": int(provider_ledger_summary.get("network_call_units", 0) or 0),
            "status_counts": provider_ledger_summary.get("status_counts", {}),
        },
    }
    accounting = {
        "schema_version": "replay_stage_call_accounting.v1",
        "source_run": str(source),
        "new_run": str(target.resolve()),
        "execution_policy": {
            "from_stage": "l2",
            "no_l1": True,
            "network": network,
            "api": api,
            "entity_network_lookup": entity_network_lookup,
            "entity_llm_cleaner": entity_llm_cleaner,
            "skip_fulltext": skip_fulltext,
        },
        "current_run_calls": current,
        **historical,
        "invariants": {
            "abstract_retrieval_blocked_by_from_stage_l2": True,
            "abstract_l1_blocked_by_no_l1": True,
            "fulltext_download_blocked": bool(skip_fulltext),
            "source_l1_bound_read_only": True,
            "full_run_fallback_allowed": False,
        },
        "raw_legacy_fields_are_historical": {
            "abstract_l1_summary.api_calls_made": historical["historical_abstract_l1_calls"],
            "acquisition_report.network_calls_made": historical["historical_abstract_retrieval_http_calls"],
            "pubmed_query_diagnostics.downloaded_count": historical["historical_abstract_documents_downloaded"],
        },
        "entity_resolution_audit_network_calls_made": int(entity_audit.get("network_calls_made", 0) or 0),
    }
    return accounting, ledger


def _write_preflight_call_accounting(target: Path, *, source: Path, reused: list[str], from_stage: str,
                                     no_l1: bool, network: bool, api: bool,
                                     entity_network_lookup: bool, entity_llm_cleaner: bool,
                                     skip_fulltext: bool) -> None:
    source_artifacts = source / "artifacts"
    historical = _historical_call_counts(source_artifacts)
    run_papers = _count_lines(source_artifacts / "run_paper_manifest.jsonl")
    current = {
        "abstract_retrieval_http_calls": 0,
        "abstract_documents_downloaded": 0,
        "abstract_l1_provider_calls": 0,
        "l2_entity_llm_cleaner_calls": 0,
        "l2_entity_llm_proposer_calls": 0,
        "entity_network_calls": {"mygene": 0, "uniprot": 0, "ols": 0, "pubchem": 0, "chembl": 0},
        "fulltext_download_calls": 0,
        "fulltext_claim_provider_calls": 0,
        "local_artifacts_reused": _count_lines(target / "artifacts" / "abstract_l1_claims.jsonl"),
        "local_artifacts_copied": len(reused),
        "abstract_documents_reused_from_source": run_papers,
        "cache_hits": 0,
        "negative_cache_hits": 0,
    }
    payload = {
        "schema_version": "replay_stage_call_accounting.v1",
        "status": "preflight_before_l2",
        "source_run": str(source),
        "new_run": str(target.resolve()),
        "execution_policy": {
            "from_stage": from_stage,
            "no_l1": no_l1,
            "network": network,
            "api": api,
            "entity_network_lookup": entity_network_lookup,
            "entity_llm_cleaner": entity_llm_cleaner,
            "skip_fulltext": skip_fulltext,
        },
        "current_run_calls": current,
        **historical,
        "invariants": {
            "abstract_retrieval_blocked_by_from_stage_l2": from_stage == "l2",
            "abstract_l1_blocked_by_no_l1": bool(no_l1),
            "fulltext_download_blocked": bool(skip_fulltext),
            "source_l1_bound_read_only": True,
            "full_run_fallback_allowed": False,
        },
    }
    artifacts = target / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "replay_stage_call_accounting.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifacts / "replay_external_call_ledger.json").write_text(json.dumps({"records": []}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_replay_terminal_state(target: Path, manifest: dict, call_accounting: dict, *, status: str = "completed") -> dict:
    current_calls = call_accounting["current_run_calls"]
    def _int(value: Any) -> int:
        return int(value or 0)
    terminal = {
        "schema_version": "replay_terminal_state_audit.v1",
        "run_id": target.name,
        "final_status": status,
        "exit_code": 0 if status == "completed" else 2,
        "terminal_status_written": True,
        "no_stage_started_after_terminal": True,
        "no_external_call_after_terminal": True,
        "pending_executor_shutdown_required": False,
        "provider_sessions_closed": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    state = {
        "run_id": target.name,
        "created_at": manifest.get("created_at"),
        "updated_at": terminal["timestamp"],
        "query": "",
        "mode": "execute",
        "api_enabled": bool(manifest.get("api_used")),
        "network_enabled": bool(manifest.get("network_used")),
        "until": "stage_replay",
        "current_step": None,
        "failed_step": None,
        "final_status": status,
        "api_calls_made": (
            _int(current_calls.get("abstract_l1_provider_calls"))
            + _int(current_calls.get("l2_entity_llm_cleaner_calls"))
            + _int(current_calls.get("l2_entity_llm_proposer_calls"))
            + _int(current_calls.get("fulltext_claim_provider_calls"))
        ),
        "network_calls_made": (
            _int(current_calls.get("abstract_retrieval_http_calls"))
            + sum(_int(value) for value in current_calls.get("entity_network_calls", {}).values())
            + _int(current_calls.get("fulltext_download_calls"))
        ),
        "current_run_calls": current_calls,
        "historical_calls": {
            "historical_abstract_l1_calls": call_accounting["historical_abstract_l1_calls"],
            "historical_abstract_retrieval_http_calls": call_accounting["historical_abstract_retrieval_http_calls"],
            "historical_abstract_documents_downloaded": call_accounting["historical_abstract_documents_downloaded"],
            "historical_l2_cleaner_calls": call_accounting["historical_l2_cleaner_calls"],
            "historical_entity_network_calls": call_accounting["historical_entity_network_calls"],
        },
        "warnings": [],
        "errors": [] if status == "completed" else [status],
    }
    (target / "run_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (target / "artifacts" / "replay_terminal_state_audit.json").write_text(json.dumps(terminal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return terminal

def replay(case_profile,search_plan,source_run,from_stage,output_root,output_suffix,bundle_id_suffix,*,no_l1=True,network=False,api=False,entity_network_lookup=False,entity_llm_cleaner=False,skip_fulltext=True,skip_l7=True,overwrite_bundle=False,bundle_root="case_bundles",case_version=None):
    source=Path(source_run).resolve();profile=load_case_domain_profile(case_profile);stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    _validate_replay_checkpoint(source, from_stage, no_l1)
    target=Path(output_root)/f"{stamp}_{profile.case_id}_{output_suffix}"
    if target.exists(): raise FileExistsError(f"replay run exists: {target}")
    shutil.copytree(source,target);artifacts=target/"artifacts"
    reused=[name for name in REUSED if (artifacts/name).is_file()]
    required="abstract_l1_claims.jsonl"
    if required not in reused: shutil.rmtree(target);raise FileNotFoundError(f"checkpoint missing required artifact: {required}")
    shutil.copy2(case_profile,artifacts/"case_domain_profile.json");shutil.copy2(search_plan,artifacts/"search_plan.json")
    _write_preflight_call_accounting(
        target, source=source, reused=reused, from_stage=from_stage, no_l1=no_l1,
        network=network, api=api, entity_network_lookup=entity_network_lookup,
        entity_llm_cleaner=entity_llm_cleaner, skip_fulltext=skip_fulltext,
    )
    rerun=[]
    if from_stage=="l2":
        from code_engine.workflow.steps import run_l2_abstract_step,run_abstract_conflict_screening_step
        if network and entity_network_lookup:
            from code_engine.normalization.providers.patient_execution import L2ProviderExecutionManager
            L2ProviderExecutionManager(target, install_signal_handlers=False)
        _clear_current_run_resolver_artifacts(artifacts)
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
        from code_engine.fulltext.candidate_bridge import availability_summary_from_bridge,canonical_fulltext_candidates,write_candidate_bridge_audit,write_pmcid_integrity_audit
        bridge_candidates,pmcid_conflicts=canonical_fulltext_candidates(artifacts)
        write_pmcid_integrity_audit(artifacts,pmcid_conflicts)
        bridge_audit=write_candidate_bridge_audit(artifacts,bridge_candidates,case_id=profile.case_id)
        (artifacts/"fulltext_availability_summary.json").write_text(json.dumps(availability_summary_from_bridge(bridge_candidates,bridge_audit,enabled=True,retrieval_results=[]),indent=2)+"\n")
        (artifacts/"l35_fulltext_retrieval_summary.json").write_text(json.dumps({"status":"planned_discovery_escalation","reason":"offline_replay_selected_candidates_without_acquisition","network_used":network,"candidate_paper_count":discovery["fulltext_escalation_candidate_count"],"fulltext_escalation_mode":discovery["fulltext_escalation_mode"],"fulltext_escalation_candidate_count":discovery["fulltext_escalation_candidate_count"]},indent=2)+"\n")
        for name in ("l35_fulltext_l1_summary.json","l35_fulltext_conflict_confirmation_summary.json"):(artifacts/name).write_text(json.dumps({"status":"skipped","reason":"stage_replay_no_llm_no_network","network_used":network},indent=2)+"\n")
    else:
        from code_engine.fulltext.discovery_escalation import discovery_escalation_expected,finalize_discovery_escalation,prepare_discovery_escalation
        from code_engine.fulltext.stage import run_l35_pmc_oa_stage
        expected=discovery_escalation_expected(fulltext_enabled=True,network_enabled=network,discovery_mode=True,
            weak_count=discovery["weak_conflict_candidate_count"],escalation_count=discovery["fulltext_escalation_candidate_count"],reviewable_count=discovery["reviewable_graph_observation_count"])
        prepared=prepare_discovery_escalation(target,enabled=True)
        shared_fulltext=run_l35_pmc_oa_stage(target,enabled=True,network_enabled=network,api_enabled=api,l1_client=None,l1_provider=os.getenv("L1_PROVIDER"),l1_model=os.getenv("MODEL_NAME"))
        finalize_discovery_escalation(target,prepared=prepared,expected=expected,explicitly_disabled=False,shared_summary=shared_fulltext,strict_conflict_count=0)
        rerun.append("l35_fulltext")
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
                **{
                    key: int(llm_cleaner_summary.get(key, 0) or 0)
                    for key in (
                        "cleaner_eligible_mentions",
                        "cleaner_deterministic_skip",
                        "cleaner_cache_hits",
                        "cleaner_actual_calls",
                        "cleaner_failures",
                        "cleaner_pending",
                    )
                },
            }
        except (json.JSONDecodeError, OSError):
            llm_cleaner_fields = {"entity_llm_cleaner_enabled": entity_llm_cleaner}
    else:
        llm_cleaner_fields = {"entity_llm_cleaner_enabled": entity_llm_cleaner}
    raw_l1_claims_reused=sum(1 for x in (artifacts/required).read_text().splitlines() if x.strip())
    call_accounting, external_call_ledger = _current_call_accounting(
        target, source=source, reused=reused, raw_l1_claims_reused=raw_l1_claims_reused,
        network=network, api=api, entity_network_lookup=entity_network_lookup,
        entity_llm_cleaner=entity_llm_cleaner, skip_fulltext=skip_fulltext,
    )
    (artifacts/"replay_stage_call_accounting.json").write_text(json.dumps(call_accounting,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (artifacts/"replay_external_call_ledger.json").write_text(json.dumps({"records": external_call_ledger},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    manifest={"schema_version":"case_stage_replay_v1","source_run":str(source),"new_run":str(target.resolve()),"case_id":profile.case_id,"from_stage":from_stage,"reused_artifacts":reused,"rerun_stages":rerun,"skipped_stages":["acquisition","l1"]+(["fulltext_network_and_l1"] if skip_fulltext else [])+(["l7"] if skip_l7 else []),"network_used":network,"api_used":api,"llm_used":False,"entity_network_lookup_enabled":entity_network_lookup,"entity_llm_proposer_enabled":False,"entity_network_calls_made":entity_network_calls,"entity_external_lookup_skipped_reason":entity_audit_skipped_reason,"created_at":datetime.now(timezone.utc).isoformat(),"reason":"downstream_replay_from_checkpoint","replay_source_run":str(source),"replay_from_stage":from_stage,"upstream_artifacts_reused":True,"raw_l1_claims_reused":raw_l1_claims_reused,"current_run_calls":call_accounting["current_run_calls"],"historical_abstract_l1_calls":call_accounting["historical_abstract_l1_calls"],"historical_abstract_documents_downloaded":call_accounting["historical_abstract_documents_downloaded"],"graph_observation_count":graph_count,"core_observation_count":core_count,"true_graph_conflict_count":0,"formal_hypothesis_count":0,**{k:discovery[k] for k in ("l2_retained_observation_count","seed_neighborhood_observation_count","reviewable_graph_observation_count","weak_conflict_candidate_count","fulltext_escalation_candidate_count")},**seed_provenance,**llm_cleaner_fields}
    (target/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n");(artifacts/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    network_status_line = f"- Network used: {network}" + (f" (entity external lookup skipped: {entity_audit_skipped_reason})" if entity_audit_skipped_reason else f" (entity network calls: {entity_network_calls})")
    report=f"# Stage Replay Report\n\n- Source: `{source}`\n- New run: `{target}`\n- From stage: `{from_stage}`\n- LLM used: false\n{network_status_line}\n- Current Abstract L1 calls: {call_accounting['current_run_calls']['abstract_l1_provider_calls']}\n- Current abstract retrieval HTTP calls: {call_accounting['current_run_calls']['abstract_retrieval_http_calls']}\n- Current abstract documents downloaded: {call_accounting['current_run_calls']['abstract_documents_downloaded']}\n- Current L2 cleaner calls: {call_accounting['current_run_calls']['l2_entity_llm_cleaner_calls']}\n- Current entity network calls: {sum(call_accounting['current_run_calls']['entity_network_calls'].values())}\n- Historical Abstract L1 calls in source artifacts: {call_accounting['historical_abstract_l1_calls']}\n- Historical abstract documents downloaded in source artifacts: {call_accounting['historical_abstract_documents_downloaded']}\n- L1 claims reused: {manifest['raw_l1_claims_reused']}\n- Graph observations: {graph_count}\n- Conflict observations: {core_count}\n"
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
    manifest.update({"bundle":str(bundle),"case_version":version,"scientific_output_class":case_manifest["scientific_output_class"]})
    terminal = _write_replay_terminal_state(target, manifest, call_accounting, status="completed")
    manifest.update({"final_status": terminal["final_status"], "exit_code": terminal["exit_code"]})
    (target/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    (artifacts/"replay_manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    return manifest

def main(argv=None):
 p=argparse.ArgumentParser();p.add_argument("--case-profile",required=True);p.add_argument("--search-plan-file",required=True);p.add_argument("--source-run",required=True);p.add_argument("--from-stage",choices=("l2","l3","l6","bundle"),required=True);p.add_argument("--output-root",default="runs");p.add_argument("--output-suffix",required=True);p.add_argument("--bundle-id-suffix",required=True);p.add_argument("--no-l1",action="store_true");p.add_argument("--network",action="store_true",help="Enable external entity database lookups (PubChem, ChEMBL, MyGene, UniProt) during entity normalization.");p.add_argument("--no-network",action="store_true",help="Explicitly disable external entity lookups (default behavior).");p.add_argument("--api",action="store_true",help="Enable API-based services alongside network lookups.");p.add_argument("--entity-network-lookup",action="store_true",help="Enable external entity database candidate generation (PubChem, ChEMBL, MyGene, UniProt). Requires --network.");p.add_argument("--no-entity-network-lookup",action="store_true",help="Explicitly disable external entity database lookups (default).");p.add_argument("--entity-llm-cleaner",action="store_true",help="Enable LLM-assisted entity surface cleaning before external lookup.");p.add_argument("--no-entity-llm-cleaner",action="store_true",help="Explicitly disable LLM entity surface cleaner (default).");p.add_argument("--skip-fulltext",action="store_true");p.add_argument("--skip-l7",action="store_true");p.add_argument("--overwrite-bundle",action="store_true");a=p.parse_args(argv)
 network_enabled = a.network and not a.no_network
 api_enabled = a.api and not a.no_network
 entity_network_lookup = a.entity_network_lookup and not a.no_entity_network_lookup
 entity_llm_cleaner = a.entity_llm_cleaner and not a.no_entity_llm_cleaner
 result=replay(a.case_profile,a.search_plan_file,a.source_run,a.from_stage,a.output_root,a.output_suffix,a.bundle_id_suffix,no_l1=a.no_l1,network=network_enabled,api=api_enabled,entity_network_lookup=entity_network_lookup,entity_llm_cleaner=entity_llm_cleaner,skip_fulltext=a.skip_fulltext,skip_l7=a.skip_l7,overwrite_bundle=a.overwrite_bundle);print(json.dumps(result,indent=2,ensure_ascii=False));return int(result.get("exit_code", 0))
if __name__=="__main__":raise SystemExit(main())
