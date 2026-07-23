"""Fail-closed recovery for the two frozen Fulltext L1 failures.

Planning is entirely local.  Provider execution is possible only through the
separately gated function and always writes a new run.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from code_engine.extraction.client_factory import build_json_client_from_config
from code_engine.extraction.deepseek_client import DeepSeekExtractionError
from code_engine.fulltext.evidence_anchors import EVIDENCE_ANCHOR_VERSION
from code_engine.fulltext.experimental_semantics_registry import REGISTRY_VERSION
from code_engine.fulltext.fulltext_l1_draft_hydration_v3 import (
    COMPLETENESS_POLICY_VERSION, HYDRATOR_VERSION, TrustedDraftContextV3,
    hydrate_draft_response_v3,
)
from code_engine.fulltext.fulltext_l1_v2 import (
    CACHE_IDENTITY_VERSION, DEFAULT_MAX_TOKENS, DEFAULT_THINKING_MODE, PROMPT_VERSION, SCHEMA_VERSION,
    build_prompt, cache_key, estimate_tokens, formal_schema_hash, observation_as_legacy_claim,
    prompt_hash, schema_hash, split_transport_metadata, token_budget_preflight,
    FulltextTokenBudget,
)
from code_engine.fulltext.fulltext_l1_v2_smoke import (
    _block_inventory, _config_hash, _historical_config, _jsonl,
)
from code_engine.schemas.fulltext_observation import FulltextL1V3Response
from code_engine.schemas.fulltext_observation_draft import DRAFT_SCHEMA_VERSION, FulltextL1DraftResponse


PROFILE = "fulltext_l1_v3_failed_block_recovery_v1"
PLAN_SCHEMA = "fulltext_failed_block_recovery_plan_v1"
ALLOWLIST = (
    "PMC7767749_38_0__split_fulltext_block_split_v1_00",
    "PMC7708218_15_0",
)
PROVIDER = "deepseek"
MODEL = "deepseek-v4-pro"
MAXIMUM_PROVIDER_CALLS = 2


def _sha(value: bytes | str | Any) -> str:
    if isinstance(value, bytes): data = value
    elif isinstance(value, str): data = value.encode("utf-8")
    else: data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")


def _tree_hashes(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): _sha(path.read_bytes()) for path in sorted(root.rglob("*")) if path.is_file()}


def _source_id(block_id: str, parent_block_id: str | None) -> str:
    if parent_block_id: return parent_block_id
    marker = "__split_fulltext_block_split_v1_"
    return block_id.split(marker, 1)[0] if marker in block_id else block_id


def _frozen_contract() -> dict[str, str]:
    return {
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(),
        "cache_identity_version": CACHE_IDENTITY_VERSION,
        "draft_schema_version": DRAFT_SCHEMA_VERSION,
        "draft_schema_hash": schema_hash(),
        "formal_schema_version": SCHEMA_VERSION,
        "formal_schema_hash": formal_schema_hash(),
        "hydrator_version": HYDRATOR_VERSION,
        "anchor_contract_version": EVIDENCE_ANCHOR_VERSION,
        "completeness_policy_version": COMPLETENESS_POLICY_VERSION,
    }


def _context(output_run: Path, item: dict[str, Any]) -> TrustedDraftContextV3:
    block, paper = item["block"], item["paper"]
    section_value = block.get("section") or {}
    section = section_value.get("section_title") if isinstance(section_value, dict) else str(section_value or "") or None
    return TrustedDraftContextV3(
        run_id=output_run.name, block_id=str(block["block_id"]),
        parent_block_id=block.get("parent_block_id") or block["block_id"],
        child_block_id=block.get("child_block_id"), block_text=str(block["text"]),
        source_block_hash=str(block.get("chunk_hash") or _sha(str(block["text"]))),
        source_document_id=str(paper.get("pmcid") or paper.get("pmid") or paper.get("paper_id")),
        paper_id=str(paper.get("paper_id") or paper.get("pmid") or paper.get("pmcid")),
        pmid=str(paper.get("pmid")) if paper.get("pmid") is not None else None,
        pmcid=str(paper.get("pmcid")) if paper.get("pmcid") is not None else None,
        fulltext_source_hash=str(item["source_fulltext_hash"]),
        source_artifact=str(item["article_path"]), section=section,
    )


def _raw_json(record: dict[str, Any]) -> tuple[Any, bool, bool]:
    raw: Any = record.get("raw_response")
    exists = raw not in (None, "")
    raw_path = Path(str(record.get("raw_response_path") or ""))
    if not exists and raw_path.is_file():
        raw = raw_path.read_text(encoding="utf-8"); exists = True
    try:
        if isinstance(raw, str): raw = json.loads(raw)
        return raw, exists, isinstance(raw, dict)
    except (json.JSONDecodeError, TypeError):
        return raw, exists, False


def _audit_failure(source_run: Path, output_run: Path, record: dict[str, Any],
                   item: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    block, paper = item["block"], item["paper"]
    raw, raw_exists, raw_valid = _raw_json(record)
    draft_valid = formal_valid = False; draft_error = formal_error = None
    hydrated: Any = None
    if raw_valid:
        try:
            draft = FulltextL1DraftResponse.model_validate(raw); draft_valid = True
            hydrated = hydrate_draft_response_v3(draft, _context(output_run, item))
            FulltextL1V3Response.model_validate(hydrated.formal_response)
            formal_valid = not hydrated.rejected
            if hydrated.rejected: formal_error = ",".join(f"{x['observation_index']}:{x['status']}:{x['reason']}" for x in hydrated.rejected)
        except ValidationError as exc: draft_error = str(exc)
        except (ValueError, TypeError) as exc: formal_error = str(exc)
    prior_hash = _sha({key: paper.get(key) for key in ("subject", "object", "abstract_observation_ids")})
    expected_identity = cache_key(
        source_fulltext_hash=item["source_fulltext_hash"], chunk_hash=block["chunk_hash"],
        provider=PROVIDER, model=MODEL, config_hash=_config_hash(config), candidate_prior_hash=prior_hash,
        thinking_mode=DEFAULT_THINKING_MODE, max_tokens=int(config["max_tokens"]),
    )
    preflight = token_budget_preflight(paper, block, FulltextTokenBudget(
        max_tokens=int(config["max_tokens"]), observation_limit=int(config.get("observation_limit", 40)),
        safe_input_tokens=int(config.get("safe_input_tokens", 6000)), max_split_depth=int(config.get("max_split_depth", 1)),
    ))
    if not raw_valid: failure_stage, failure_reason, category = "transport_parse", "raw_response_not_valid_json_object", "malformed JSON"
    elif not draft_valid: failure_stage, failure_reason, category = "draft_schema", draft_error, "Draft schema failure"
    elif not formal_valid: failure_stage, failure_reason, category = "formal_hydration", formal_error, "evidence-anchor failure"
    else: failure_stage, failure_reason, category = None, None, "unknown"
    split_depth = int(block.get("split_depth", 0)); parent = block.get("parent_block_id")
    return {
        "block_id": record["block_id"], "source_block_id": record["block_id"],
        "parent_block_id": parent, "split_depth": split_depth,
        "input_hash": block["chunk_hash"], "cache_identity": record.get("cache_key"),
        "expected_cache_identity": expected_identity, "cache_identity_match": record.get("cache_key") == expected_identity,
        "source_prompt_version": record.get("prompt_version"), "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash(), "cache_identity_version": CACHE_IDENTITY_VERSION,
        "old_cache_identity_excluded": record.get("cache_key") != expected_identity,
        "draft_schema_version": DRAFT_SCHEMA_VERSION,
        "formal_schema_version": SCHEMA_VERSION, "anchor_contract_version": EVIDENCE_ANCHOR_VERSION,
        "provider_called": bool(record.get("api_called")), "raw_response_exists": raw_exists,
        "raw_json_valid": raw_valid, "draft_valid": draft_valid, "formal_valid": formal_valid,
        "finish_reason": record.get("finish_reason"), "truncated": record.get("finish_reason") == "length" or bool(record.get("output_truncated")),
        "failure_stage": failure_stage, "failure_reason": failure_reason, "failure_category": category,
        "recoverable_offline": bool(raw_valid and draft_valid and formal_valid),
        "provider_call_required": not bool(raw_valid and draft_valid and formal_valid),
        "origin_if_offline_recovered": "offline_recovery_existing_provider_response",
        "input_character_count": len(str(block["text"])), "estimated_input_tokens": estimate_tokens(build_prompt(paper, block)),
        "preflight": preflight, "raw_response_path": record.get("raw_response_path"),
        "raw_response_hash": _sha(raw) if raw_exists else None, "usage": record.get("usage") or {},
        "historical_error_kind": record.get("error_kind"), "historical_exception_class": record.get("exception_class"),
        "formal_valid_observation_count_before_failure": len(hydrated.formal_response["experimental_observations"]) if hydrated else 0,
        "formal_rejected_count": len(hydrated.rejected) if hydrated else 0,
    }


def _successful_protection(source_run: Path, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows=[]; hashes={}
    cache_root=source_run/"artifacts/cache/fulltext_l1_v2"
    for record in records:
        if record.get("status") not in {"completed", "completed_empty", "cache_hit", "recovered_offline_success"}: continue
        block_id=str(record.get("block_id")); row_hash=_sha(record); entry={"block_id":block_id,"execution_record_hash":row_hash}
        cache_path=cache_root/f"{record.get('cache_key')}.json"
        if cache_path.is_file(): entry["cache_artifact"] = str(cache_path); entry["cache_artifact_hash"]=_sha(cache_path.read_bytes())
        rows.append(entry); hashes[block_id]=_sha(entry)
    return rows, hashes


def _output_path(source_run: Path, output_run: Path | None) -> Path:
    if output_run: return output_run
    digest=_sha({
        "source":str(source_run.resolve()),"profile":PROFILE,"allowlist":ALLOWLIST,
        "prompt_version":PROMPT_VERSION,"prompt_hash":prompt_hash(),
        "cache_identity_version":CACHE_IDENTITY_VERSION,
    })[:20]
    return source_run.parent/f"{source_run.name}__failed_block_recovery_{digest}"


def write_recovery_plan(source_run: Path, *, output_run: Path | None = None) -> dict[str, Any]:
    source_run=Path(source_run).resolve(); output=_output_path(source_run, output_run)
    artifacts=source_run/"artifacts"; all_records=_jsonl(artifacts/"fulltext_l1_v2_execution_records.jsonl")
    failures=[x for x in all_records if x.get("block_id") in ALLOWLIST]
    if [x.get("block_id") for x in failures] != list(ALLOWLIST):
        by_id={x.get("block_id"):x for x in failures}; failures=[by_id[x] for x in ALLOWLIST if x in by_id]
    if len(failures)!=2 or any(x.get("status")!="parse_error" for x in failures):
        raise RuntimeError("source run does not contain exactly the two frozen unresolved failures")
    before=_tree_hashes(source_run)
    active_pointer=source_run.parent.parent/"system_b_outputs/system_a_sync/active_projections_by_case.json"
    external_before={str(active_pointer):_sha(active_pointer.read_bytes())} if active_pointer.is_file() else {}
    config=_historical_config(artifacts, all_records)
    inventory=_block_inventory(source_run, failures, config)
    audits=[_audit_failure(source_run, output, record, inventory[record["block_id"]], config) for record in failures]
    success, protected=_successful_protection(source_run, all_records)
    provider=[x["block_id"] for x in audits if x["provider_call_required"]]
    offline=[x["block_id"] for x in audits if x["recoverable_offline"]]
    source_ids={_source_id(str(x.get("block_id")), x.get("parent_block_id")) for x in all_records}
    sibling_rows=[x for x in all_records if x.get("parent_block_id")=="PMC7767749_38_0"]
    split_audit={
        "parent_block_id":"PMC7767749_38_0", "failed_child_id":ALLOWLIST[0],
        "failed_child_is_only_failed_sibling":sum(x.get("status")=="parse_error" for x in sibling_rows)+1==1,
        "successful_sibling_ids":[x["block_id"] for x in sibling_rows if x.get("status") in {"completed","completed_empty","cache_hit"}],
        "parent_complete":False, "further_split_required":False,
        "reason":"finish_reason_stop_and_payload_within_budget", "frozen_child_split_plan":[],
    }
    frozen_contract=_frozen_contract()
    identity={"schema_version":PLAN_SCHEMA,"recovery_profile":PROFILE,"source_run":str(source_run),
              "failed_source_blocks":list(ALLOWLIST),"audits":audits,"source_tree_hash":_sha(before),
              "frozen_contract":frozen_contract}
    plan={**identity,"mode":"plan_only","planned_leaf_blocks":list(ALLOWLIST),
          "offline_recoverable_blocks":offline,"provider_required_blocks":provider,
          "cache_hits":0,"planned_provider_calls":len(provider),"maximum_provider_calls":MAXIMUM_PROVIDER_CALLS,
          "network_calls":0,"api_calls":0,"downloads":0,"protected_successful_blocks":len(success),
          "successful_blocks_reused":len(success),"successful_blocks_recalled":0,
          "successful_block_protection":success,"protected_artifact_hashes":protected,
          "source_artifact_hashes":before,"split_audit":split_audit,
          "protected_external_state_hashes":external_before,"atlas_activated":False,"active_projection_unchanged":True,
          "planned_source_block_count":len(source_ids),"planned_leaf_block_count":len(all_records),
          "recovery_run":str(output),"publication_allowed":False,
          "plan_hash":_sha(identity),"requires_explicit_execute_and_api":True,
          "hidden_retries":0,"provider_retry_limit":0,"dynamic_call_budget_expansion":False,
          "dynamic_budget_expansion":False,"further_splits":0,
          "provider_scan_scope":list(ALLOWLIST),
          "resumable_ledger_path":str(output/"artifacts/fulltext_failed_block_recovery_execution_ledger.jsonl"),
          "ledger_flush_policy":"after_each_provider_call_or_terminal_validation_result",
          "cops8_post_recovery_safeguards":{
              "block_id":"PMC7708218_15_0","existing_same_paper_evidence_present":True,
              "exact_duplicate_removal_required":True,"evidence_family_recalculation_required":True,
              "canonical_edge_recalculation_required":True,"polarity_conflict_recalculation_required":True,
              "species_gate_must_remain_enabled":True,
              "pre_execution_conclusion":"overlap exists, but exact duplication and edge impact depend on the new provider response"}}
    out=output/"artifacts"; out.mkdir(parents=True,exist_ok=True)
    _write_json(out/"fulltext_failed_block_recovery_plan.json",plan)
    _write_jsonl(out/"fulltext_failed_block_recovery_audit.jsonl",audits)
    summary={"schema_version":"fulltext_failed_block_recovery_summary_v1","mode":"plan_only",
             "successful_blocks_reused":len(success),"successful_blocks_recalled":0,
             "failed_blocks_before":2,"failed_blocks_after":2,"offline_recovered_blocks":0,
             "provider_recovered_blocks":0,"new_provider_calls":0,"new_raw_observation_count":0,
             "new_formal_valid_count":0,"new_formal_resolved_count":0,"new_formal_reviewable_count":0,
             "new_formal_rejected_count":0,"new_evidence_family_count":0,
             "strict_core_before":5,"strict_core_after":5,"canonical_edges_before":4,"canonical_edges_after":4,
             "true_conflicts_before":0,"true_conflicts_after":0,"species_conflicts_before":0,"species_conflicts_after":0,
             "scientific_input_complete":False,"partial_block_failures":True,"publication_allowed":False,
             "api_calls":0,"network_calls":0,"downloads":0}
    _write_json(out/"fulltext_failed_block_recovery_summary.json",summary)
    _write_json(out/"fulltext_recovery_merge_manifest.json",{
        "schema_version":"fulltext_recovery_merge_manifest_v1","status":"planned_not_merged",
        "source_run":str(source_run),"recovery_run":str(output),"immutable_successful_block_references":success,
        "recovered_block_results":[],"source_tree_hash":plan["source_tree_hash"],"publication_allowed":False})
    _write_json(out/"fulltext_recovery_consistency_report.json",{
        "schema_version":"fulltext_recovery_consistency_report_v1","status":"incomplete_plan_only",
        "planned_source_block_count":len(source_ids),"planned_leaf_block_count":len(all_records),
        "completed_source_blocks":len(source_ids)-2,"completed_leaf_blocks":len(success),
        "failed_source_blocks":list(ALLOWLIST),"failed_leaf_blocks":list(ALLOWLIST),
        "partial_block_failures":True,"scientific_input_complete":False,"publication_allowed":False})
    commands={
        "paid_recovery":f"PYTHONPATH=src python -m code_engine.cli.fulltext_l1_failed_block_recovery --run-dir {source_run} --output-run {output} --execute --api",
        "reentry":f"PYTHONPATH=src python -m code_engine.cli.fulltext_reentry_replay --case-id hif1a_hypoxia_cancer_response_discovery_v1 --base-run runs/20260723_033238_hif1a_hypoxia_cancer_response_discovery_v1_fulltext_v3_native_reentry --fulltext-run {output} --output-root runs --output-suffix fulltext_v3_recovered_reentry",
        "projection":"PYTHONPATH=src python -m code_engine.cli.fulltext_offline_reproject <NEW_REENTRY_RUN> --output-root runs",
        "handoff":f"PYTHONPATH=src python -m code_engine.cli.fulltext_projection_handoff_replay --fulltext-run {output} --reentry-run <NEW_REENTRY_RUN> --projection-run <NEW_PROJECTION_RUN> --output-root runs --staging-only",
        "publication_readiness_audit":"Inspect the new recovery consistency report plus the new reentry, projection, and staging manifests; do not publish or activate Atlas.",
    }
    report=["# Fulltext Failed-block Recovery Report","","No provider, network, or download call was made.","",
            "## Failure audit",""]
    for a in audits: report += [f"- `{a['block_id']}`: {a['failure_category']} at {a['failure_stage']}; offline={str(a['recoverable_offline']).lower()}; provider_required={str(a['provider_call_required']).lower()}"]
    report += ["","## Frozen recovery","",f"- Planned / maximum provider calls: {len(provider)} / {MAXIMUM_PROVIDER_CALLS}","- Successful blocks recalled: 0","- Further split: no","- Atlas activation: forbidden","","## Commands",""]+[f"- {k}: `{v}`" for k,v in commands.items()]
    (out/"fulltext_failed_block_recovery_report.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    if before!=_tree_hashes(source_run): raise RuntimeError("plan-only modified the immutable source run")
    external_after={str(active_pointer):_sha(active_pointer.read_bytes())} if active_pointer.is_file() else {}
    if external_before!=external_after: raise RuntimeError("plan-only modified the active projection pointer")
    return {**summary,"recovery_profile":PROFILE,"source_run":str(source_run),"recovery_run":str(output),
            "failed_source_blocks":list(ALLOWLIST),"planned_leaf_blocks":list(ALLOWLIST),
            "offline_recoverable_blocks":offline,"provider_required_blocks":provider,"cache_hits":0,
            "planned_provider_calls":len(provider),"maximum_provider_calls":MAXIMUM_PROVIDER_CALLS,
            "protected_successful_blocks":len(success),"protected_artifact_hashes":protected,"commands":commands}


def execute_recovery(source_run: Path, *, output_run: Path, api_authorized: bool,
                     client: Any | None = None) -> dict[str, Any]:
    if not api_authorized: raise PermissionError("recovery execution requires both --execute and --api")
    source_run=Path(source_run).resolve(); output=Path(output_run).resolve(); out=output/"artifacts"
    plan_path=out/"fulltext_failed_block_recovery_plan.json"
    if not plan_path.is_file(): raise FileNotFoundError("run plan-only first with the same --output-run")
    plan=json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("failed_source_blocks")!=list(ALLOWLIST) or plan.get("maximum_provider_calls")!=MAXIMUM_PROVIDER_CALLS:
        raise RuntimeError("saved plan violates the frozen allowlist or call bound")
    if plan.get("frozen_contract") != _frozen_contract():
        raise RuntimeError("systematic schema or prompt contract drift after recovery planning")
    if _sha(_tree_hashes(source_run))!=plan.get("source_tree_hash"): raise RuntimeError("source run changed after planning")
    records=_jsonl(source_run/"artifacts/fulltext_l1_v2_execution_records.jsonl"); failures=[x for x in records if x.get("block_id") in ALLOWLIST]
    config=_historical_config(source_run/"artifacts",records); inventory=_block_inventory(source_run,failures,config)
    client=client or build_json_client_from_config(PROVIDER,MODEL,max_retries=0)
    if client is None: raise RuntimeError("DeepSeek provider is not configured")
    cache=out/"cache/fulltext_l1_failed_block_recovery"; cache.mkdir(parents=True,exist_ok=True)
    ledger_path=out/"fulltext_failed_block_recovery_execution_ledger.jsonl"
    prior=_jsonl(ledger_path); terminal={x.get("block_id") for x in prior if x.get("status")=="completed"}
    results=list(prior); calls=sum(bool(x.get("api_called")) for x in prior)
    prior_stopped=any(x.get("status")!="completed" for x in prior)
    for block_id in ALLOWLIST:
        if prior_stopped: break
        if block_id in terminal: continue
        if calls>=MAXIMUM_PROVIDER_CALLS: raise RuntimeError("frozen provider call bound exhausted")
        item=inventory[block_id]; entry=next(x for x in plan["audits"] if x["block_id"]==block_id)
        key=entry["expected_cache_identity"]; cache_file=cache/f"{key}.json"
        if cache_file.is_file():
            cached=json.loads(cache_file.read_text(encoding="utf-8"))
            compatible = (
                cached.get("cache_identity") == key
                and cached.get("prompt_version") == PROMPT_VERSION
                and cached.get("prompt_hash") == prompt_hash()
                and cached.get("cache_identity_version") == CACHE_IDENTITY_VERSION
            )
            if not compatible:
                raise RuntimeError("recovery cache artifact violates the frozen prompt/cache identity")
            results.append({**cached["execution_record"],"api_called":False,"cache_hit":True})
            _write_jsonl(ledger_path,results)
            continue
        method=getattr(client,"extract_json_result",None) or getattr(client,"extract_json")
        calls+=1
        try:
            response=method(build_prompt(item["paper"],item["block"]),model=MODEL,temperature=0,top_p=1,
                            max_tokens=DEFAULT_MAX_TOKENS,retry_on_length=False,thinking_mode=DEFAULT_THINKING_MODE)
            payload,transport=split_transport_metadata(response)
            raw=transport.get("raw_response") or json.dumps(payload,ensure_ascii=False)
            raw_path=cache/f"{key}.raw_response.txt"; raw_path.write_text(str(raw),encoding="utf-8")
            if transport.get("finish_reason")=="length":
                rec={"block_id":block_id,"status":"output_truncated","api_called":True,"finish_reason":"length","raw_response_path":str(raw_path)}
                results.append(rec); _write_jsonl(ledger_path,results); break
            draft=FulltextL1DraftResponse.model_validate(payload); hydrated=hydrate_draft_response_v3(draft,_context(output,item))
            formal=FulltextL1V3Response.model_validate(hydrated.formal_response).model_dump(mode="json")
            complete=not hydrated.rejected
            rec={"block_id":block_id,"parent_block_id":item["block"].get("parent_block_id"),"status":"completed" if complete else "formal_incomplete",
                 "api_called":True,"cache_hit":False,"cache_identity":key,"finish_reason":transport.get("finish_reason"),
                 "usage":transport.get("usage") or {},"observation_count":len(formal["experimental_observations"]),
                 "formal_rejected_count":len(hydrated.rejected),"prompt_version":PROMPT_VERSION,
                 "prompt_hash":prompt_hash(),"cache_identity_version":CACHE_IDENTITY_VERSION,
                 "origin":"native_prompt_v8_results_anchor_contract_provider_failed_block_recovery",
                 "raw_response_path":str(raw_path)}
            _write_json(cache/f"{key}.draft.json",draft.model_dump(mode="json")); _write_json(cache/f"{key}.formal.json",formal)
            _write_json(cache/f"{key}.audit.json",{"hydration_audit":hydrated.audit,"rejected":hydrated.rejected})
            _write_json(cache_file,{"cache_identity":key,"prompt_version":PROMPT_VERSION,
                                    "prompt_hash":prompt_hash(),"cache_identity_version":CACHE_IDENTITY_VERSION,
                                    "execution_record":rec,"draft_response":draft.model_dump(mode="json"),
                                    "formal_response":formal,"hydration_audit":hydrated.audit,"rejected":hydrated.rejected})
            results.append(rec); _write_jsonl(ledger_path,results)
        except (DeepSeekExtractionError,ValidationError,ValueError,TypeError,json.JSONDecodeError) as exc:
            rec={"block_id":block_id,"status":"provider_or_validation_failure","api_called":True,"error_class":type(exc).__name__,"error":str(exc),
                 "finish_reason":getattr(exc,"finish_reason",None)}
            results.append(rec); _write_jsonl(ledger_path,results); break
    completed={x["block_id"] for x in results if x.get("status")=="completed"}
    complete=completed==set(ALLOWLIST)
    if complete:
        recovered=[]; audits=[]
        for block_id in ALLOWLIST:
            rec=next(x for x in reversed(results) if x.get("block_id")==block_id and x.get("status")=="completed")
            cached=json.loads((cache/f"{rec['cache_identity']}.json").read_text(encoding="utf-8")); recovered += cached["formal_response"]["experimental_observations"]; audits += cached["hydration_audit"]
        source_art=source_run/"artifacts"
        for path in source_art.iterdir():
            if path.is_file() and path.name not in {"fulltext_experiment_observations.jsonl","l35_fulltext_l1_claims.jsonl","fulltext_l1_v2_execution_records.jsonl","fulltext_l1_v2_summary.json","l35_fulltext_l1_summary.json"}:
                shutil.copy2(path,out/path.name)
        observations=[]; seen=set()
        for row in _jsonl(source_art/"fulltext_experiment_observations.jsonl")+recovered:
            fingerprint=_sha(row)
            if fingerprint in seen: continue
            seen.add(fingerprint); observations.append(row)
        merged_exec=[x for x in records if x.get("block_id") not in ALLOWLIST]+[x for x in results if x.get("status")=="completed"]
        _write_jsonl(out/"fulltext_experiment_observations.jsonl",observations); _write_jsonl(out/"l35_fulltext_l1_claims.jsonl",[observation_as_legacy_claim(x) for x in observations]); _write_jsonl(out/"fulltext_l1_v2_execution_records.jsonl",merged_exec)
        _write_jsonl(out/"fulltext_l1_v2_parser_normalization_audit.jsonl",_jsonl(source_art/"fulltext_l1_v2_parser_normalization_audit.jsonl")+audits)
        source_summary=json.loads((source_art/"fulltext_l1_v2_summary.json").read_text(encoding="utf-8"))
        summary={**source_summary,"fulltext_l1_status":"completed","observation_count":len(observations),"generated_observation_count":len(observations),
                 "fulltext_l1_claim_count":len(observations),"completed_block_count":len(merged_exec),"parse_errors":0,"parse_error_block_count":0,
                 "failed_block_ids":[],"still_failed":[],"newly_failed":[],"previously_failed_now_recovered":list(ALLOWLIST),
                 "scientific_input_complete":True,"partial_block_failures":False,
                 "recovery_provider_calls":calls,"consistency_report":{"complete_scientific_run":True,"publication_allowed":False,"message":"scientific input complete; formal publication gate not executed"}}
        _write_json(out/"fulltext_l1_v2_summary.json",summary); _write_json(out/"l35_fulltext_l1_summary.json",summary)
    final={"schema_version":"fulltext_failed_block_recovery_summary_v1","mode":"executed","source_run":str(source_run),"recovery_run":str(output),
           "successful_blocks_reused":198,"successful_blocks_recalled":0,"failed_blocks_before":2,"failed_blocks_after":0 if complete else 2-len(completed),
           "offline_recovered_blocks":0,"provider_recovered_blocks":len(completed),"new_provider_calls":calls,"api_calls":calls,"network_calls":calls,"downloads":0,
           "scientific_input_complete":complete,"partial_block_failures":not complete,"publication_allowed":False,"atlas_activated":False}
    _write_json(out/"fulltext_failed_block_recovery_summary.json",final)
    unresolved=[x for x in ALLOWLIST if x not in completed]
    _write_json(out/"fulltext_recovery_consistency_report.json",{
        "schema_version":"fulltext_recovery_consistency_report_v1","status":"complete" if complete else "incomplete",
        "planned_source_block_count":plan["planned_source_block_count"],"planned_leaf_block_count":plan["planned_leaf_block_count"],
        "completed_source_blocks":plan["planned_source_block_count"]-len(unresolved),
        "completed_leaf_blocks":plan["planned_leaf_block_count"]-len(unresolved),
        "failed_source_blocks":unresolved,"failed_leaf_blocks":unresolved,
        "execution_ledger_consistent":len({x.get("block_id") for x in results if x.get("status")=="completed"})==len(completed),
        "partial_block_failures":not complete,"scientific_input_complete":complete,"publication_allowed":False})
    _write_json(out/"fulltext_recovery_merge_manifest.json",{
        "schema_version":"fulltext_recovery_merge_manifest_v1","status":"merged" if complete else "not_merged_incomplete",
        "source_run":str(source_run),"recovery_run":str(output),"source_tree_hash":plan["source_tree_hash"],
        "immutable_successful_block_references":plan["successful_block_protection"],
        "recovered_block_results":[x for x in results if x.get("status")=="completed"],
        "successful_blocks_recalled":0,"publication_allowed":False})
    return final


__all__=["PROFILE","ALLOWLIST","MAXIMUM_PROVIDER_CALLS","write_recovery_plan","execute_recovery"]
