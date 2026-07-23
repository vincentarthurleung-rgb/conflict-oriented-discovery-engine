import copy
import json
from pathlib import Path

import pytest

from code_engine.cli.fulltext_l1_failed_block_recovery import main
from code_engine.extraction.deepseek_client import JSONExtractionResult
from code_engine.fulltext.failed_block_recovery import (
    ALLOWLIST, MAXIMUM_PROVIDER_CALLS, execute_recovery, write_recovery_plan,
)
from code_engine.schemas.fulltext_observation_draft import fulltext_l1_draft_prompt_examples


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in rows))


def _fixture(tmp_path: Path, monkeypatch):
    run=tmp_path/"source"; artifacts=run/"artifacts"; artifacts.mkdir(parents=True)
    _empty, example=fulltext_l1_draft_prompt_examples()
    first=copy.deepcopy(example); first["experimental_observations"][0]["observation"]["evidence"]["evidence_anchor_ids"]=[f"{ALLOWLIST[0]}:S9999"]
    second=copy.deepcopy(example); second["experimental_observations"][0]["observation"]["observed_result"]=None
    records=[]
    for block_id,payload in zip(ALLOWLIST,(first,second)):
        records.append({"block_id":block_id,"status":"parse_error","api_called":True,"cache_key":f"old-{block_id}",
                        "prompt_version":"v7","finish_reason":"stop","raw_response":payload,"usage":{}})
    records.extend(
        {"block_id":f"successful-{index:03d}","status":"completed_empty","api_called":True,
         "cache_key":f"success-{index:03d}"}
        for index in range(198)
    )
    _write_rows(artifacts/"fulltext_l1_v2_execution_records.jsonl",records)
    items={}
    for index,block_id in enumerate(ALLOWLIST):
        parent="PMC7767749_38_0" if index==0 else None
        block={"block_id":block_id,"parent_block_id":parent,"child_block_id":block_id if parent else None,
               "split_depth":1 if parent else 0,"chunk_hash":f"hash-{index}","text":"Observed result sentence.",
               "paper_metadata":{"pmcid":f"PMC{index}"},"context_sources":[]}
        items[block_id]={"block":block,"paper":{"paper_id":str(index),"pmcid":f"PMC{index}"},
                         "source_fulltext_hash":f"source-{index}","article_path":str(artifacts/f"article-{index}.json")}
    monkeypatch.setattr("code_engine.fulltext.failed_block_recovery._block_inventory",lambda *_a,**_k:items)
    monkeypatch.setattr("code_engine.fulltext.failed_block_recovery._historical_config",lambda *_a,**_k:{
        "max_sections":12,"max_chunks_per_paper":24,"max_chars":6000,"max_total_chunks":200,
        "max_tokens":32768,"observation_limit":40,"safe_input_tokens":6000,"max_split_depth":1,
        "split_version":"fulltext_block_split_v1","duplicate_rule_version":"v1",
        "cache_identity_version":"v5","thinking_mode":"disabled"})
    return run


def _valid_response(block_id: str):
    _empty, response=fulltext_l1_draft_prompt_examples(); response=copy.deepcopy(response)
    def rewrite(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=="evidence_anchor_ids": value[key]=[f"{block_id}:S0001"]
                else: rewrite(item)
        elif isinstance(value,list):
            for item in value: rewrite(item)
    rewrite(response)
    return response


def test_plan_is_allowlisted_zero_call_and_preserves_source(tmp_path,monkeypatch):
    run=_fixture(tmp_path,monkeypatch); before={p.relative_to(run):p.read_bytes() for p in run.rglob("*") if p.is_file()}
    result=write_recovery_plan(run,output_run=tmp_path/"recovery")
    assert result["failed_source_blocks"]==list(ALLOWLIST)
    assert result["provider_required_blocks"]==list(ALLOWLIST)
    assert result["offline_recoverable_blocks"]==[]
    assert result["planned_provider_calls"]==result["maximum_provider_calls"]==MAXIMUM_PROVIDER_CALLS
    assert result["api_calls"]==result["network_calls"]==result["downloads"]==0
    assert result["successful_blocks_recalled"]==0
    assert result["protected_successful_blocks"]==198
    assert before=={p.relative_to(run):p.read_bytes() for p in run.rglob("*") if p.is_file()}
    plan=json.loads((tmp_path/"recovery/artifacts/fulltext_failed_block_recovery_plan.json").read_text())
    assert [x["failure_category"] for x in plan["audits"]]==["evidence-anchor failure","Draft schema failure"]
    assert plan["split_audit"]["further_split_required"] is False
    assert plan["dynamic_call_budget_expansion"] is False and plan["dynamic_budget_expansion"] is False
    assert plan["hidden_retries"]==0 and plan["further_splits"]==0
    assert plan["provider_scan_scope"]==list(ALLOWLIST)
    assert plan["successful_blocks_reused"]==198 and plan["successful_blocks_recalled"]==0
    assert all(x["old_cache_identity_excluded"] for x in plan["audits"])
    assert plan["frozen_contract"]["prompt_version"].endswith("v8_results_anchor_contract")
    assert plan["frozen_contract"]["cache_identity_version"].endswith("v6_results_anchor_contract")


def test_execution_and_cli_fail_closed_without_both_flags(tmp_path):
    with pytest.raises(PermissionError,match="both --execute and --api"):
        execute_recovery(tmp_path/"source",output_run=tmp_path/"out",api_authorized=False)
    with pytest.raises(SystemExit): main(["--run-dir",str(tmp_path),"--execute"])
    with pytest.raises(SystemExit): main(["--run-dir",str(tmp_path),"--api"])


def test_execution_stops_before_provider_on_frozen_contract_drift(tmp_path,monkeypatch):
    run=_fixture(tmp_path,monkeypatch); output=tmp_path/"recovery"
    write_recovery_plan(run,output_run=output)
    plan_path=output/"artifacts/fulltext_failed_block_recovery_plan.json"
    plan=json.loads(plan_path.read_text())
    plan["frozen_contract"]["draft_schema_hash"]="drifted"
    plan_path.write_text(json.dumps(plan))
    class NeverClient:
        def extract_json_result(self,*_args,**_kwargs):
            raise AssertionError("provider must not be called after contract drift")
    with pytest.raises(RuntimeError,match="systematic schema or prompt contract drift"):
        execute_recovery(run,output_run=output,api_authorized=True,client=NeverClient())


def test_unallowlisted_source_fails_closed(tmp_path):
    artifacts=tmp_path/"source/artifacts"; artifacts.mkdir(parents=True)
    _write_rows(artifacts/"fulltext_l1_v2_execution_records.jsonl",[
        {"block_id":"not-authorized","status":"parse_error"},
    ])
    with pytest.raises(RuntimeError,match="exactly the two frozen"):
        write_recovery_plan(tmp_path/"source",output_run=tmp_path/"out")


def test_fake_provider_recovers_only_two_and_completeness_is_recomputed(tmp_path,monkeypatch):
    run=_fixture(tmp_path,monkeypatch); artifacts=run/"artifacts"
    (artifacts/"fulltext_experiment_observations.jsonl").write_text("")
    (artifacts/"fulltext_l1_v2_parser_normalization_audit.jsonl").write_text("")
    (artifacts/"fulltext_l1_v2_summary.json").write_text(json.dumps({"planned_block_count":3,"observation_count":0}))
    output=tmp_path/"recovery"; write_recovery_plan(run,output_run=output)
    class Client:
        def __init__(self): self.calls=[]
        def extract_json_result(self,prompt,**kwargs):
            block_id=ALLOWLIST[len(self.calls)]; self.calls.append((block_id,kwargs))
            payload=_valid_response(block_id)
            return JSONExtractionResult(payload=payload,raw_response=json.dumps(payload),finish_reason="stop",usage={})
    client=Client(); result=execute_recovery(run,output_run=output,api_authorized=True,client=client)
    assert [x[0] for x in client.calls]==list(ALLOWLIST)
    assert all(x[1].get("retry_on_length") is False for x in client.calls)
    assert result["new_provider_calls"]==MAXIMUM_PROVIDER_CALLS
    assert result["scientific_input_complete"] is True and result["partial_block_failures"] is False
    assert result["publication_allowed"] is False
    consistency=json.loads((output/"artifacts/fulltext_recovery_consistency_report.json").read_text())
    assert consistency["failed_leaf_blocks"]==[] and consistency["execution_ledger_consistent"] is True
    before=len(client.calls); resumed=execute_recovery(run,output_run=output,api_authorized=True,client=client)
    assert len(client.calls)==before and resumed["scientific_input_complete"] is True
