"""Reusable one-command System A -> Atlas orchestration service."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from code_engine.cli.fulltext_bridge_replay import replay_fulltext_bridge_from_run
from code_engine.cli.fulltext_reentry_replay import run_replay
from code_engine.cli.repair_fulltext_candidate_pmcids import repair_fulltext_candidate_pmcids
from code_engine.integration.atlas_handoff import publish_atlas_handoff, sha256_file, validate_handoff
from code_engine.orchestration.models import STAGES, CaseToAtlasRequest, CaseToAtlasResult
from code_engine.orchestration.state_store import OrchestrationStateStore, canonical_bytes, utcnow
from code_engine.orchestration.verification import current_projection, evaluation_counts, verify_case_to_atlas
from code_engine.system_b.adapters import ADAPTER_VERSION
from code_engine.system_b.system_a_sync import sync_system_a

ERROR_CODES = {"base_run":"BASE_RUN_FAILED", "pmcid_repair":"PMCID_REPAIR_FAILED", "fulltext_l1":"FULLTEXT_L1_FAILED",
               "reentry":"REENTRY_FAILED", "handoff":"HANDOFF_VALIDATION_FAILED", "atlas_sync":"ATLAS_SYNC_FAILED",
               "verification":"PROJECTION_VERIFICATION_FAILED"}


class OrchestrationError(RuntimeError):
    def __init__(self, code: str, summary: str, *, stage: str | None = None, resume_from: str | None = None):
        self.code, self.summary, self.stage, self.resume_from = code, summary, stage, resume_from
        super().__init__(f"{code}: {summary}")


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256_file(path) if path.is_file() else "missing"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"{path} must contain an object")
    return value


class CaseToAtlasOrchestrator:
    def _resolve(self, request: CaseToAtlasRequest) -> CaseToAtlasRequest:
        from code_engine.validation.external_api_smoke import load_dotenv
        load_dotenv()
        resolved = request.resolved()
        invalid = sorted(set(resolved.force_stages) - set(STAGES))
        if invalid: raise OrchestrationError("INVALID_FORCE_STAGE", ", ".join(invalid))
        if resolved.stop_after and resolved.stop_after not in STAGES: raise OrchestrationError("INVALID_STOP_STAGE", resolved.stop_after)
        if not resolved.case_profile_path.is_file() or not resolved.search_plan_path.is_file():
            raise OrchestrationError("CASE_PACKAGE_MISSING", f"expected {resolved.case_profile_path} and {resolved.search_plan_path}")
        try:
            profile, plan = _read(resolved.case_profile_path), _read(resolved.search_plan_path)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise OrchestrationError("SEARCH_PLAN_INVALID", str(error)) from error
        if profile.get("case_id") != resolved.case_id or plan.get("case_id") not in {None, resolved.case_id} or not plan.get("frozen"):
            raise OrchestrationError("SEARCH_PLAN_INVALID", "case identity mismatch or search plan is not frozen")
        return resolved

    def orchestration_id(self, request: CaseToAtlasRequest) -> str:
        stable = {"case_id":request.case_id, "case_profile":str(request.case_profile_path.resolve()),
                  "search_plan":str(request.search_plan_path.resolve()), "runs_root":str(request.runs_root.resolve()),
                  "system_b_output_root":str(request.system_b_output_root.resolve()), "database_url":request.database_url}
        return "cta_" + hashlib.sha256(canonical_bytes(stable)).hexdigest()[:20]

    def plan(self, request: CaseToAtlasRequest) -> dict[str, Any]:
        request = self._resolve(request); oid = self.orchestration_id(request); store = OrchestrationStateStore(request.runs_root, oid)
        state = store.read_state() if request.resume else None
        plan = _read(request.search_plan_path)
        current_cases = []
        try: current_cases = sorted(x["case_id"] for x in current_projection(request.system_b_output_root)[2].get("source_manifests", []))
        except (OSError, ValueError, KeyError, json.JSONDecodeError): pass
        stages=[]; invalidated=False
        for index, name in enumerate(STAGES):
            record=(state or {}).get("stages",{}).get(name,{})
            forced = any(STAGES.index(forced) <= index for forced in request.force_stages)
            input_hash=self._input_hash(name,request,state or {})
            reusable=bool(request.resume and not invalidated and not forced and self._record_valid(name,record,input_hash,request))
            if not reusable: invalidated=True
            stages.append({"stage":name,"action":"reuse" if reusable else "run","reason":"valid_completed_stage" if reusable else "forced" if forced else "missing_or_invalid","input_hash":input_hash})
        return {"schema_version":"case_to_atlas_plan_v1","orchestration_id":oid,"case_id":request.case_id,
                "case_profile":str(request.case_profile_path),"frozen_search_plan":str(request.search_plan_path),"dry_run":request.dry_run,
                "stages":stages,"reusable_stages":[x["stage"] for x in stages if x["action"]=="reuse"],
                "invalidated_stages":[x["stage"] for x in stages if x["action"]=="run"],
                "abstract_l1_api_expected":any(x["stage"]=="base_run" and x["action"]=="run" for x in stages) and request.api_enabled,
                "fulltext_l1_api_expected":any(x["stage"]=="fulltext_l1" and x["action"]=="run" for x in stages) and request.api_enabled,
                "handoff_exists":bool((state or {}).get("stages",{}).get("handoff",{}).get("status")=="completed"),
                "ingestion_exists":bool((state or {}).get("stages",{}).get("atlas_sync",{}).get("status")=="completed"),
                "current_projection_case_count":len(current_cases),"current_projection_cases":current_cases,
                "provider":os.getenv("L1_PROVIDER") or None,"model":os.getenv("MODEL_NAME") or None}

    def resume(self, request: CaseToAtlasRequest) -> CaseToAtlasResult:
        return self.run(CaseToAtlasRequest(**{**request.__dict__, "resume": True}))

    def run(self, request: CaseToAtlasRequest) -> CaseToAtlasResult:
        request=self._resolve(request)
        if request.dry_run:
            planned=self.plan(request)
            return CaseToAtlasResult(orchestration_id=planned["orchestration_id"],status="dry_run",case_id=request.case_id,reused_stages=planned["reusable_stages"],verification=planned)
        oid=self.orchestration_id(request);store=OrchestrationStateStore(request.runs_root,oid);existing=store.read_state()
        if existing: state=existing
        else: state=self._new_state(oid,request)
        if not state.get("safety_baseline"): state["safety_baseline"]=evaluation_counts(request.database_url)
        if not state.get("prior_cases"):
            try: state["prior_cases"]=sorted(x["case_id"] for x in current_projection(request.system_b_output_root)[2].get("source_manifests",[]))
            except Exception: state["prior_cases"]=[]
        store.write_request(request.to_dict());store.write_state(state)
        if not existing: store.append_event("planned",orchestration_id=oid,case_id=request.case_id)
        reused=[]; invalidated=not request.resume
        stop_index=STAGES.index(request.stop_after) if request.stop_after else len(STAGES)-1
        for index,name in enumerate(STAGES):
            if index>stop_index: break
            record=state["stages"][name];forced=any(STAGES.index(stage)<=index for stage in request.force_stages)
            input_hash=self._input_hash(name,request,state)
            reusable=bool(not invalidated and not forced and self._record_valid(name,record,input_hash,request))
            if reusable:
                reused.append(name);store.append_event("stage_reused",stage=name,output_run=record.get("output_run"));continue
            invalidated=True
            for downstream in STAGES[index+1:]:
                if state["stages"][downstream].get("status") in {"completed","skipped"}: state["stages"][downstream]["status"]="pending"
            if name=="handoff" and not request.publish_handoff:
                record.update(status="skipped",input_hash=input_hash,completed_at=utcnow(),reason="publication_disabled");store.write_state(state);continue
            if name in {"atlas_sync","verification"} and (not request.atlas_sync or not request.publish_handoff):
                record.update(status="skipped",input_hash=input_hash,completed_at=utcnow(),reason="atlas_sync_disabled");store.write_state(state);continue
            record["attempt"]=int(record.get("attempt") or 0)+1;record.update(status="running",input_hash=input_hash,started_at=utcnow(),error_code=None,error_summary=None)
            if name in {"base_run","pmcid_repair","fulltext_l1","reentry"}:
                if not record.get("output_run") or record.get("previous_input_hash") not in {None,input_hash} or record.get("last_status")=="completed" or (record.get("last_status")=="failed" and name!="base_run"):
                    record["output_run"]=str(self._output_path(request,oid,name,record["attempt"]))
            record["previous_input_hash"]=input_hash;state.update(status="running",current_stage=name);store.write_state(state);store.append_event("stage_started",stage=name,attempt=record["attempt"],output_run=record.get("output_run"))
            try:
                output=self._execute(name,request,state,record)
                record.update(status="completed",completed_at=utcnow(),**output);record["last_status"]="completed"
                store.append_event("sync_completed" if name=="atlas_sync" else "verification_completed" if name=="verification" else "stage_completed",stage=name,output_run=record.get("output_run"),status=output.get("operation_status","completed"))
                store.write_state(state)
            except Exception as error:
                code=getattr(error,"code",ERROR_CODES[name]);record.update(status="failed",failed_at=utcnow(),error_code=code,error_summary=str(error));record["last_status"]="failed";state.update(status="failed",current_stage=name,error_code=code,error_summary=str(error));store.write_state(state);store.append_event("stage_failed",stage=name,error_code=code,error_summary=str(error))
                raise OrchestrationError(code,str(error),stage=name,resume_from=name) from error
        state.update(status="completed" if stop_index==len(STAGES)-1 else "stopped",current_stage=None,completed_at=utcnow());state["reused_stages"]=reused
        result=self._result(request,oid,state,reused);store.write_state(state);store.write_result(result.to_dict());return result

    def verify(self, request: CaseToAtlasRequest) -> dict[str, Any]:
        request=self._resolve(request);state=OrchestrationStateStore(request.runs_root,self.orchestration_id(request)).read_state()
        if not state: raise OrchestrationError("ORCHESTRATION_NOT_FOUND",request.case_id)
        return self._verification(request,state)

    def _new_state(self, oid: str, request: CaseToAtlasRequest) -> dict:
        return {"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":request.case_id,"status":"planned","current_stage":None,"created_at":utcnow(),"stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":evaluation_counts(request.database_url),"prior_cases":[]}

    def _output_path(self, request: CaseToAtlasRequest, oid: str, stage: str, attempt: int) -> Path:
        return request.runs_root / f"{oid}_{request.case_id}_{stage}_v{attempt}"

    def _input_hash(self, stage: str, request: CaseToAtlasRequest, state: dict) -> str:
        provider={"provider":os.getenv("L1_PROVIDER") or "","model":os.getenv("MODEL_NAME") or ""}
        stages=state.get("stages",{})
        if stage=="base_run": material={"profile":_file_hash(request.case_profile_path),"plan":_file_hash(request.search_plan_path),"api":request.api_enabled,"network":request.network_enabled,**provider}
        elif stage=="pmcid_repair": material={"base":self._output_identity(stages.get("base_run",{})),"network":request.network_enabled}
        elif stage=="fulltext_l1": material={"repair":self._output_identity(stages.get("pmcid_repair",{})),"profile":_file_hash(request.case_profile_path),"api":request.api_enabled,"network":request.network_enabled,**provider}
        elif stage=="reentry": material={"base":self._output_identity(stages.get("base_run",{})),"fulltext":self._output_identity(stages.get("fulltext_l1",{})),"schema":"fulltext_reentry_v5"}
        elif stage=="handoff": material={"reentry":self._output_identity(stages.get("reentry",{})),"schema":"atlas_handoff_v1"}
        elif stage=="atlas_sync":
            manifests=sorted((str(path),_file_hash(path)) for path in request.runs_root.glob("*/artifacts/atlas_handoff_manifest.json"));material={"manifests":manifests,"adapter":ADAPTER_VERSION,"output":str(request.system_b_output_root.resolve()),"database":request.database_url}
        else:
            registry=request.system_b_output_root/"current_projection.json";material={"registry":_file_hash(registry),"handoff":self._output_identity(stages.get("handoff",{})),"baseline":state.get("safety_baseline")}
        return _hash(material)

    def _output_identity(self, record: dict) -> dict:
        path=Path(record.get("output_run") or "")
        candidates=[path/"run_state.json",path/"pmcid_repair_manifest.json",path/"fulltext_bridge_replay_manifest.json",path/"fulltext_reentry_manifest.json",Path(record.get("manifest_path") or "")]
        return {"path":str(path),"hash":next((_file_hash(item) for item in candidates if str(item) not in {".",""} and item.is_file()),"missing")}

    def _record_valid(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest) -> bool:
        if record.get("status")!="completed" or record.get("input_hash")!=input_hash: return False
        try:
            if stage=="base_run":
                run=Path(record["output_run"]);state=_read(run/"run_state.json");return state.get("steps",{}).get("fulltext_escalation",{}).get("status")=="completed" and any((run/"artifacts"/name).is_file() for name in ("fulltext_escalation_candidates.jsonl","fulltext_discovery_escalation_candidates.jsonl"))
            if stage=="pmcid_repair": return Path(record["output_run"],"pmcid_repair_manifest.json").is_file()
            if stage=="fulltext_l1": return _read(Path(record["output_run"])/"fulltext_bridge_replay_manifest.json").get("stage_summary",{}).get("status","").startswith("completed")
            if stage=="reentry": return _read(Path(record["output_run"])/"fulltext_reentry_manifest.json").get("status")=="completed"
            if stage=="handoff": validate_handoff(record["manifest_path"],runs_root=request.runs_root);return True
            if stage=="atlas_sync": return record.get("operation_status") in {"completed","no_op"} and (request.system_b_output_root/"current_projection.json").is_file()
            if stage=="verification": return record.get("verification",{}).get("status")=="passed"
        except Exception: return False
        return False

    def _execute(self, name: str, request: CaseToAtlasRequest, state: dict, record: dict) -> dict[str,Any]:
        profile=_read(request.case_profile_path);plan=_read(request.search_plan_path)
        if name=="base_run":
            from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
            from code_engine.workflow.orchestrator import run_workflow
            output=Path(record["output_run"]);resume=output if (output/"run_state.json").is_file() else None
            client=build_l1_client_from_env_or_config(os.getenv("L1_PROVIDER"),os.getenv("MODEL_NAME")) if request.api_enabled else None
            run_state=run_workflow(query=profile["query"],run_dir=output,until="fulltext_escalation",execute=True,api=request.api_enabled,network=request.network_enabled,max_papers=60,diversify_acquisition=True,paper_year_from=plan.get("paper_year_from"),paper_year_to=plan.get("paper_year_to"),temporal_role=(plan.get("paper_year_filter") or {}).get("temporal_role","discovery"),search_plan_file=request.search_plan_path,fail_if_search_plan_drift=True,resume=resume,allow_uncertain_intake=True,l1_mode="abstract_screening",enable_fulltext_escalation=True,l1_llm_client=client,semantic_llm_client=client,seed_triple=plan.get("seed_triple"),allow_compatible_l1_task_reuse=True)
            if run_state.steps["fulltext_escalation"].status!="completed": raise ValueError("base fulltext escalation did not complete")
            return {"api_calls":run_state.api_calls_made,"network_calls":run_state.network_calls_made,"final_status":run_state.final_status}
        if name=="pmcid_repair":
            result=repair_fulltext_candidate_pmcids(source_run=state["stages"]["base_run"]["output_run"],output_run=record["output_run"],network=request.network_enabled)
            return {"result":result,"network_calls":result.get("authoritative_lookup_attempt_count",0),"cache_hits":self._count_true(Path(record["output_run"])/"artifacts/pmcid_enrichment_audit.jsonl","cache_hit")}
        if name=="fulltext_l1":
            policy=profile.get("fulltext_policy") or {}
            result=replay_fulltext_bridge_from_run(case_id=request.case_id,source_run=state["stages"]["pmcid_repair"]["output_run"],output_run=record["output_run"],network=request.network_enabled,api=request.api_enabled,max_papers=int(policy.get("max_papers") or 20))
            summary=result.get("stage_summary",{});return {"result":result,"api_calls":summary.get("fulltext_l1_api_calls",0),"network_calls":result.get("retrieval_attempt_count",0),"cache_hits":summary.get("fulltext_l1_cache_hit_count",0)}
        if name=="reentry":
            result=run_replay(case_id=request.case_id,base_run=Path(state["stages"]["base_run"]["output_run"]),fulltext_run=Path(state["stages"]["fulltext_l1"]["output_run"]),output_root=request.runs_root,output_suffix="case_to_atlas_v5",output_run=Path(record["output_run"]),network=False,api=False,publish_atlas=False)
            return {"result":result,"claim_count":result.get("input_fulltext_claim_count",0)}
        if name=="handoff":
            reentry=Path(state["stages"]["reentry"]["output_run"]);result=publish_atlas_handoff(reentry,runs_root=request.runs_root,lineage={"base_run":state["stages"]["base_run"]["output_run"],"pmcid_repair_run":state["stages"]["pmcid_repair"]["output_run"],"fulltext_l1_run":state["stages"]["fulltext_l1"]["output_run"],"reentry_run":reentry})
            validate_handoff(result["manifest_path"],runs_root=request.runs_root);return {"manifest_path":result["manifest_path"],"manifest_hash":result["manifest_hash"],"operation_status":result["status"]}
        if name=="atlas_sync":
            result=sync_system_a(runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,refresh_current_projection=True)
            if result.get("status") not in {"completed","no_op"} or result.get("rejected"): raise ValueError(json.dumps(result,ensure_ascii=False))
            return {"result":result,"operation_status":result["status"],"projection_id":result.get("current_projection_id")}
        verification=self._verification(request,state)
        second=sync_system_a(runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,refresh_current_projection=True)
        if second.get("status")!="no_op": raise ValueError("second sync was not no-op")
        verification["second_sync_status"]="no_op";return {"verification":verification,"operation_status":"completed"}

    def _verification(self,request,state):
        return verify_case_to_atlas(case_id=request.case_id,reentry_run=Path(state["stages"]["reentry"]["output_run"]),handoff_manifest=Path(state["stages"]["handoff"]["manifest_path"]),runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,safety_baseline=state["safety_baseline"],prior_cases=state["prior_cases"])

    def _count_true(self,path,key):
        if not path.is_file(): return 0
        return sum(json.loads(line).get(key) is True for line in path.read_text().splitlines() if line.strip())

    def _result(self,request,oid,state,reused):
        s=state["stages"];verification=s["verification"].get("verification",{})
        return CaseToAtlasResult(orchestration_id=oid,status=state["status"],case_id=request.case_id,base_run=s["base_run"].get("output_run"),pmcid_repair_run=s["pmcid_repair"].get("output_run"),fulltext_run=s["fulltext_l1"].get("output_run"),reentry_run=s["reentry"].get("output_run"),handoff_manifest=s["handoff"].get("manifest_path"),handoff_status=s["handoff"].get("operation_status"),ingestion_id=verification.get("ingestion_id"),prediction_run_id=verification.get("prediction_run_id"),projection_id=verification.get("projection_id") or s["atlas_sync"].get("projection_id"),current_case_count=verification.get("current_case_count",0),claim_count=verification.get("claim_count",s["reentry"].get("claim_count",0)),dossier_count=verification.get("dossier_count",0),context_row_count=verification.get("context_row_count",0),exploratory_triple_count=verification.get("exploratory_triple_count",0),formal_conflict_count=verification.get("formal_conflict_count",0),api_calls=sum(int(s[x].get("api_calls") or 0) for x in STAGES),network_calls=sum(int(s[x].get("network_calls") or 0) for x in STAGES),cache_hits=sum(int(s[x].get("cache_hits") or 0) for x in STAGES),reused_stages=reused,sync_status=s["atlas_sync"].get("operation_status"),warnings=[] if not verification.get("quarantine_count") else [f"quarantine_count={verification['quarantine_count']}"] ,verification=verification)
