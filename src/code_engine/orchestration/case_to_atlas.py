"""Reusable one-command System A -> Atlas orchestration service."""
from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from code_engine.cli.fulltext_bridge_replay import replay_fulltext_bridge_from_run
from code_engine.cli.fulltext_reentry_replay import run_replay
from code_engine.cli.repair_fulltext_candidate_pmcids import repair_fulltext_candidate_pmcids
from code_engine.fulltext.candidate_bridge import SOURCE_FILES as FULLTEXT_CANDIDATE_SOURCE_FILES
from code_engine.fulltext.reasoning_trace import (
    CONTEXT_RULE_VERSION,
    EXTRACTOR_CODE_VERSION,
    PROMPT_VERSION,
    RETRIEVAL_CONFIG_VERSION,
    run_fulltext_context_consolidation_stage,
    run_fulltext_reasoning_trace_stage,
)
from code_engine.integration.atlas_handoff import publish_atlas_handoff, sha256_file, validate_handoff
from code_engine.orchestration.models import STAGES, CaseToAtlasRequest, CaseToAtlasResult
from code_engine.orchestration.state_store import OrchestrationStateStore, canonical_bytes, utcnow
from code_engine.orchestration.verification import current_projection, evaluation_counts, verify_case_to_atlas
from code_engine.system_b.adapters import ADAPTER_VERSION
from code_engine.system_b.system_a_sync import sync_system_a

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

ERROR_CODES = {"base_run":"BASE_RUN_FAILED", "pmcid_repair":"PMCID_REPAIR_FAILED", "fulltext_l1":"FULLTEXT_L1_FAILED",
               "fulltext_reasoning_trace":"FULLTEXT_REASONING_TRACE_FAILED", "fulltext_context_consolidation":"FULLTEXT_CONTEXT_CONSOLIDATION_FAILED",
               "reentry":"REENTRY_FAILED", "handoff":"HANDOFF_VALIDATION_FAILED", "atlas_sync":"ATLAS_SYNC_FAILED",
               "verification":"PROJECTION_VERIFICATION_FAILED"}
SEMANTIC_FINGERPRINT_SCHEMA = "stage_semantic_v2"


class OrchestrationError(RuntimeError):
    def __init__(self, code: str, summary: str, *, stage: str | None = None, resume_from: str | None = None):
        self.code, self.summary, self.stage, self.resume_from = code, summary, stage, resume_from
        super().__init__(f"{code}: {summary}")


@dataclass
class BaseRunValidationResult:
    status: str
    code: str | None = None
    summary: str | None = None
    artifact_count: int = 0
    validated_at: str | None = None
    legacy_fulltext_escalation_status: str | None = None
    manifest_status: str | None = None
    run_state_final_status: str | None = None
    candidate_artifacts: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return self.status == "valid"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StageFingerprint:
    stage: str
    material: dict[str, Any]
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage, "sha256": self.sha256, "material": self.material}


@dataclass
class StageReuseDecision:
    stage: str
    action: str
    reason: str
    stored_input_hash: str | None
    current_input_hash: str
    output_run: str | None = None
    changed_components: dict[str, Any] = field(default_factory=dict)
    validated_artifacts: int = 0
    expected_api_calls: int = 0
    expected_network_calls: int = 0
    projection_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExecutionPolicy:
    allow_api: bool
    allow_network: bool
    reuse_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"reuse_only": self.reuse_only, "api_allowed": self.allow_api, "network_allowed": self.allow_network}


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _file_hash(path: Path) -> str:
    return sha256_file(path) if path.is_file() else "missing"


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"{path} must contain an object")
    return value


def _read_json_any(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl_valid(path: Path) -> tuple[bool, int]:
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                return False, count
            count += 1
    return True, count


def _invalid_base(code: str, summary: str, *, artifacts: list[str] | None = None, legacy_status: str | None = None,
                  manifest_status: str | None = None, run_state_status: str | None = None) -> BaseRunValidationResult:
    return BaseRunValidationResult(status="invalid", code=code, summary=summary, artifact_count=len(artifacts or []),
                                   validated_at=utcnow(), legacy_fulltext_escalation_status=legacy_status,
                                   manifest_status=manifest_status, run_state_final_status=run_state_status,
                                   artifacts=artifacts or [])


def validate_base_run_for_downstream(
    base_run_path: str | Path,
    *,
    request: CaseToAtlasRequest | None = None,
    expected_input_hash: str | None = None,
    orchestration_id: str | None = None,
) -> BaseRunValidationResult:
    """Validate that a base run is complete enough for pmcid_repair and later stages.

    The legacy workflow step named ``fulltext_escalation`` is audit context only.
    The decision is based on the formal triple manifest/card, parseable artifacts,
    lineage, and the candidate inputs actually consumed by PMCID repair.
    """
    run = Path(base_run_path)
    if not run.is_dir():
        return _invalid_base("BASE_RUN_OUTPUT_MISSING", f"base run directory missing: {run}")
    if any(run.glob("**/*.tmp")):
        return _invalid_base("BASE_RUN_OUTPUT_STILL_WRITING", f"temporary files remain under {run}")
    if request:
        root = request.runs_root.resolve()
        resolved = run.resolve()
        if resolved != root and root not in resolved.parents:
            return _invalid_base("BASE_RUN_OUTPUT_FOREIGN", f"base run outside runs root: {run}")
        if orchestration_id and not run.name.startswith(f"{orchestration_id}_{request.case_id}_base_run_"):
            return _invalid_base("BASE_RUN_OUTPUT_FOREIGN", f"base run does not belong to orchestration/case: {run.name}")

    artifacts_dir = run / "artifacts"
    parsed: list[str] = []
    try:
        run_state = _read(run / "run_state.json"); parsed.append("run_state.json")
        manifest = _read(run / "triple_run_manifest.json"); parsed.append("triple_run_manifest.json")
        card = _read(run / "triple_card.json"); parsed.append("triple_card.json")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", str(error), artifacts=parsed)

    legacy_status = str((run_state.get("steps", {}).get("fulltext_escalation") or {}).get("status") or "")
    manifest_status = str(manifest.get("status") or "")
    card_status = str(card.get("status") or "")
    run_state_status = str(run_state.get("final_status") or "")
    if manifest_status not in {"completed", "completed_with_warnings"} or card_status not in {"completed", "completed_with_warnings"}:
        return _invalid_base("BASE_RUN_MANIFEST_INCOMPLETE", f"manifest={manifest_status}, card={card_status}",
                             artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)
    if run_state_status not in {"completed", "completed_with_warnings", "partial"}:
        return _invalid_base("BASE_RUN_MANIFEST_INCOMPLETE", f"run_state final_status={run_state_status}",
                             artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)
    if request:
        if manifest.get("case_id") and manifest.get("case_id") != request.case_id:
            return _invalid_base("BASE_RUN_CASE_MISMATCH", f"manifest case_id={manifest.get('case_id')}",
                                 artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                                 run_state_status=run_state_status)
        if request.case_id not in run.name:
            return _invalid_base("BASE_RUN_CASE_MISMATCH", f"run name does not contain case_id={request.case_id}",
                                 artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                                 run_state_status=run_state_status)
        profile = _read(request.case_profile_path)
        if str(run_state.get("query") or "") != str(profile.get("query") or ""):
            return _invalid_base("BASE_RUN_FINGERPRINT_MISMATCH", "run_state query does not match case profile",
                                 artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                                 run_state_status=run_state_status)
        replay = _read(artifacts_dir / "search_plan_replay.json")
        parsed.append("artifacts/search_plan_replay.json")
        frozen_hash = replay.get("frozen_plan_hash")
        if frozen_hash and frozen_hash != _file_hash(request.search_plan_path):
            return _invalid_base("BASE_RUN_FINGERPRINT_MISMATCH", "search plan hash mismatch",
                                 artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                                 run_state_status=run_state_status)
    if expected_input_hash and manifest.get("input_hash") is not None and manifest.get("input_hash") != expected_input_hash:
        return _invalid_base("BASE_RUN_FINGERPRINT_MISMATCH", "manifest input_hash mismatch",
                             artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)

    required_json = (
        "artifacts/abstract_l1_summary.json",
        "artifacts/l2_abstract_observations.json",
        "artifacts/l2_abstract_summary.json",
    )
    required_jsonl = ("artifacts/abstract_l1_claims.jsonl",)
    try:
        for rel in required_json:
            path = run / rel
            if not path.is_file() or path.stat().st_size <= 0:
                return _invalid_base("BASE_RUN_ARTIFACT_MISSING", rel, artifacts=parsed,
                                     legacy_status=legacy_status, manifest_status=manifest_status,
                                     run_state_status=run_state_status)
            _read_json_any(path); parsed.append(rel)
        for rel in required_jsonl:
            path = run / rel
            if not path.is_file():
                return _invalid_base("BASE_RUN_ARTIFACT_MISSING", rel, artifacts=parsed,
                                     legacy_status=legacy_status, manifest_status=manifest_status,
                                     run_state_status=run_state_status)
            valid, _ = _jsonl_valid(path)
            if not valid:
                return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", rel, artifacts=parsed,
                                     legacy_status=legacy_status, manifest_status=manifest_status,
                                     run_state_status=run_state_status)
            parsed.append(rel)
    except (OSError, json.JSONDecodeError) as error:
        return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", str(error), artifacts=parsed,
                             legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)

    candidate_artifacts: list[str] = []
    try:
        for name in FULLTEXT_CANDIDATE_SOURCE_FILES:
            path = artifacts_dir / name
            if path.is_file():
                valid, _ = _jsonl_valid(path)
                if not valid:
                    return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", name, artifacts=parsed,
                                         legacy_status=legacy_status, manifest_status=manifest_status,
                                         run_state_status=run_state_status)
                candidate_artifacts.append(f"artifacts/{name}")
        plan_path = artifacts_dir / "fulltext_escalation_plan.json"
        if plan_path.is_file():
            plan = _read(plan_path)
            if not isinstance(plan.get("selected", []), list):
                return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", "fulltext_escalation_plan.selected is not a list",
                                     artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                                     run_state_status=run_state_status)
            candidate_artifacts.append("artifacts/fulltext_escalation_plan.json")
    except (OSError, json.JSONDecodeError, ValueError) as error:
        return _invalid_base("BASE_RUN_OUTPUT_CORRUPT", str(error), artifacts=parsed,
                             legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)
    if not candidate_artifacts:
        return _invalid_base("BASE_RUN_ARTIFACT_MISSING", "no PMCID repair candidate artifact found",
                             artifacts=parsed, legacy_status=legacy_status, manifest_status=manifest_status,
                             run_state_status=run_state_status)

    return BaseRunValidationResult(status="valid", artifact_count=len(parsed) + len(candidate_artifacts),
                                   validated_at=utcnow(), legacy_fulltext_escalation_status=legacy_status,
                                   manifest_status=manifest_status, run_state_final_status=run_state_status,
                                   candidate_artifacts=sorted(set(candidate_artifacts)),
                                   artifacts=parsed)


class CaseToAtlasOrchestrator:
    def _resolve(self, request: CaseToAtlasRequest) -> CaseToAtlasRequest:
        from code_engine.validation.external_api_smoke import load_dotenv
        load_dotenv()
        resolved = request.resolved()
        if resolved.reuse_only and resolved.force_stages:
            raise OrchestrationError("REUSE_ONLY_FORCE_STAGE_CONFLICT", "--reuse-only cannot be combined with --force-stage")
        invalid = sorted(set(resolved.force_stages) - set(STAGES))
        if invalid: raise OrchestrationError("INVALID_FORCE_STAGE", ", ".join(invalid))
        if resolved.stop_after and resolved.stop_after not in STAGES: raise OrchestrationError("INVALID_STOP_STAGE", resolved.stop_after)
        if resolved.from_stage and resolved.from_stage not in STAGES: raise OrchestrationError("INVALID_FROM_STAGE", resolved.from_stage)
        if resolved.to_stage and resolved.to_stage not in STAGES: raise OrchestrationError("INVALID_TO_STAGE", resolved.to_stage)
        if resolved.from_stage and resolved.to_stage and STAGES.index(resolved.from_stage) > STAGES.index(resolved.to_stage):
            raise OrchestrationError("INVALID_STAGE_RANGE", f"{resolved.from_stage}>{resolved.to_stage}")
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
        reconciliation = self._reconcile_state(request, state, store, dry_run=True) if state else {"reconciled": False, "abandoned_outputs": []}
        state = reconciliation.get("state") or state
        current_cases = []
        try: current_cases = sorted(x["case_id"] for x in current_projection(request.system_b_output_root)[2].get("source_manifests", []))
        except (OSError, ValueError, KeyError, json.JSONDecodeError): pass
        stages = self._build_stage_plan(request, state or {}, oid)
        next_stage = next((x["stage"] for x in stages if x["action"]=="run"), None)
        base_record=(state or {}).get("stages",{}).get("base_run",{})
        return {"schema_version":"case_to_atlas_plan_v1","orchestration_id":oid,"case_id":request.case_id,
                "case_profile":str(request.case_profile_path),"frozen_search_plan":str(request.search_plan_path),"dry_run":request.dry_run,
                "stages":stages,"reusable_stages":[x["stage"] for x in stages if x["action"] in {"reuse","recover"}],
                "invalidated_stages":[x["stage"] for x in stages if x["action"]=="run"],
                "next_stage":next_stage,
                "execution_policy": self._execution_policy(request).to_dict(),
                "reconciled_state": bool(reconciliation.get("reconciled")),
                "abandoned_outputs": reconciliation.get("abandoned_outputs", []),
                "base_run_recovery": {"action": next((x["action"] for x in stages if x["stage"]=="base_run"), None), "output_run": base_record.get("output_run")},
                "expected_api_calls":sum(int(x.get("expected_api_calls") or 0) for x in stages),
                "expected_network_calls":sum(int(x.get("expected_network_calls") or 0) for x in stages),
                "abstract_l1_api_expected":any(x["stage"]=="base_run" and x["action"]=="run" for x in stages) and request.api_enabled,
                "fulltext_l1_api_expected":any(x["stage"]=="fulltext_l1" and x["action"]=="run" for x in stages) and request.api_enabled,
                "reasoning_api_expected":any(x["stage"]=="fulltext_reasoning_trace" and x["action"]=="run" for x in stages) and request.api_enabled and request.network_enabled,
                "reasoning_cache_hits":(state or {}).get("stages",{}).get("fulltext_reasoning_trace",{}).get("cache_hits",0),
                "context_consolidation_rebuild_expected":any(x["stage"]=="fulltext_context_consolidation" and x["action"]=="run" for x in stages),
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
            return CaseToAtlasResult(orchestration_id=planned["orchestration_id"],status="dry_run",case_id=request.case_id,reused_stages=planned["reusable_stages"],verification=planned,execution_policy=planned["execution_policy"],reconciled_state=planned.get("reconciled_state",False),abandoned_outputs=planned.get("abandoned_outputs",[]))
        oid=self.orchestration_id(request);store=OrchestrationStateStore(request.runs_root,oid);existing=store.read_state()
        if existing: state=self._migrate_state(existing)
        else: state=self._new_state(oid,request)
        reconciliation = self._reconcile_state(request, state, store, dry_run=False) if existing else {"reconciled": False, "abandoned_outputs": []}
        state = reconciliation.get("state") or state
        self._validate_state_invariants(state)
        if not state.get("safety_baseline"): state["safety_baseline"]=evaluation_counts(request.database_url)
        if not state.get("prior_cases"):
            try: state["prior_cases"]=sorted(x["case_id"] for x in current_projection(request.system_b_output_root)[2].get("source_manifests",[]))
            except Exception: state["prior_cases"]=[]
        store.write_request(request.to_dict());store.write_state(state)
        if not existing: store.append_event("planned",orchestration_id=oid,case_id=request.case_id)
        stage_plan = self._build_stage_plan(request, state, oid)
        if request.reuse_only:
            run_stage = next((item for item in stage_plan if item["action"] == "run"), None)
            if run_stage:
                raise OrchestrationError("REUSE_ONLY_STAGE_INVALID", f"{run_stage['stage']} cannot be reused: {run_stage.get('reason')}", stage=run_stage["stage"], resume_from=run_stage["stage"])
        reused=[]; stage_execution={}
        current_api_calls = current_network_calls = current_cache_hits = 0
        from_index=STAGES.index(request.from_stage) if request.from_stage else 0
        stop_index=STAGES.index(request.to_stage or request.stop_after) if (request.to_stage or request.stop_after) else len(STAGES)-1
        for index,name in enumerate(STAGES):
            if index>stop_index: break
            record=state["stages"][name]
            item=stage_plan[index]
            input_hash=item["input_hash"]
            if index < from_index:
                if item["action"] not in {"reuse","recover"}:
                    raise OrchestrationError("FROM_STAGE_PRECONDITION_MISSING", f"{name} is required before {request.from_stage}", stage=name, resume_from=name)
            if item["action"] in {"reuse","recover","no_op","skip"}:
                self._apply_existing_stage_action(name, item, record, input_hash, request, oid, state, store)
                reused.append(name);stage_execution[name]={"action":item["action"],"output_run":record.get("output_run") or record.get("manifest_path"),"runner_called":False}
                continue
            input_hash=self._input_hash(name,request,state)
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
            elif name in {"fulltext_reasoning_trace","fulltext_context_consolidation"}:
                record["output_run"]=state["stages"]["fulltext_l1"].get("output_run")
            record["previous_input_hash"]=input_hash;state.update(status="running",current_stage=name);store.write_state(state);store.append_event("stage_started",stage=name,attempt=record["attempt"],output_run=record.get("output_run"))
            try:
                stage_execution[name]={"action":"run","output_run":record.get("output_run"),"runner_called":True}
                output=self._execute(name,request,state,record)
                record.update(status="completed",completed_at=utcnow(),**output);record["last_status"]="completed"
                record["artifact_hash"] = self._artifact_hash(name, record, request)
                record["semantic_input_hash"] = input_hash
                record["semantic_fingerprint_schema"] = SEMANTIC_FINGERPRINT_SCHEMA
                current_api_calls += int(output.get("api_calls") or 0)
                current_network_calls += int(output.get("network_calls") or 0)
                current_cache_hits += int(output.get("cache_hits") or 0)
                store.append_event("sync_completed" if name=="atlas_sync" else "verification_completed" if name=="verification" else "stage_completed",stage=name,output_run=record.get("output_run"),status=output.get("operation_status","completed"))
                store.write_state(state)
            except Exception as error:
                code=getattr(error,"code",ERROR_CODES[name]);record.update(status="failed",failed_at=utcnow(),error_code=code,error_summary=str(error));record["last_status"]="failed";state.update(status="failed",current_stage=name,error_code=code,error_summary=str(error));store.write_state(state);store.append_event("stage_failed",stage=name,error_code=code,error_summary=str(error))
                raise OrchestrationError(code,str(error),stage=name,resume_from=name) from error
        state.update(status="completed" if stop_index==len(STAGES)-1 else "stopped",current_stage=None,completed_at=utcnow(),error_code=None,error_summary=None);state["reused_stages"]=reused
        state["last_command_calls"]={"api_calls":current_api_calls,"network_calls":current_network_calls,"cache_hits":current_cache_hits}
        state["last_stage_execution"]=stage_execution
        state["last_reconciliation"]={"reconciled":bool(reconciliation.get("reconciled")),"abandoned_outputs":reconciliation.get("abandoned_outputs",[])}
        result=self._result(request,oid,state,reused);store.write_state(state);store.write_result(result.to_dict());return result

    def verify(self, request: CaseToAtlasRequest) -> dict[str, Any]:
        request=self._resolve(request);state=OrchestrationStateStore(request.runs_root,self.orchestration_id(request)).read_state()
        if not state: raise OrchestrationError("ORCHESTRATION_NOT_FOUND",request.case_id)
        return self._verification(request,state)

    def _new_state(self, oid: str, request: CaseToAtlasRequest) -> dict:
        return {"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":request.case_id,"status":"planned","current_stage":None,"created_at":utcnow(),"stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":evaluation_counts(request.database_url),"prior_cases":[]}

    def _migrate_state(self, state: dict) -> dict:
        stages = state.setdefault("stages", {})
        for name in STAGES:
            stages.setdefault(name, {"status": "pending", "attempt": 0})
        return state

    def _execution_policy(self, request: CaseToAtlasRequest) -> ExecutionPolicy:
        return ExecutionPolicy(allow_api=bool(request.api_enabled and not request.reuse_only),
                               allow_network=bool(request.network_enabled and not request.reuse_only),
                               reuse_only=bool(request.reuse_only))

    def _build_stage_plan(self, request: CaseToAtlasRequest, state: dict, oid: str) -> list[dict[str, Any]]:
        stages=[]; invalidated=not request.resume
        from_index=STAGES.index(request.from_stage) if request.from_stage else 0
        to_index=STAGES.index(request.to_stage or request.stop_after) if (request.to_stage or request.stop_after) else len(STAGES)-1
        for index, name in enumerate(STAGES):
            record=(state or {}).get("stages",{}).get(name,{})
            forced = any(STAGES.index(forced) <= index for forced in request.force_stages)
            input_hash=self._input_hash(name,request,state or {})
            decision = self._reuse_decision(name, record, input_hash, request, forced=forced)
            reusable=bool(request.resume and not invalidated and not forced and self._record_valid(name,record,input_hash,request))
            recoverable=bool(request.resume and not invalidated and not forced and self._record_recoverable(name,record,input_hash,request,oid))
            if index < from_index:
                action = "reuse" if reusable else "recover" if recoverable else "precondition_missing"
                reason = "before_from_stage"
            elif index > to_index:
                action = "skip"
                reason = "after_to_stage"
            else:
                if not reusable and not recoverable:
                    invalidated=True
                action = "reuse" if reusable else "recover" if recoverable else "run"
                reason = decision.reason if reusable else "recoverable_existing_output" if recoverable else "forced" if forced else decision.reason
            expected_api = 0 if action in {"reuse", "recover", "skip", "precondition_missing", "no_op"} else int(name in {"base_run", "fulltext_l1"} and request.api_enabled)
            expected_network = 0 if action in {"reuse", "recover", "skip", "precondition_missing", "no_op"} else int(name in {"base_run", "pmcid_repair", "fulltext_l1"} and request.network_enabled)
            item = decision.to_dict()
            item.update({"action": action, "reason": reason, "input_hash": input_hash,
                         "expected_api_calls": expected_api, "expected_network_calls": expected_network})
            stages.append(item)
        return stages

    def _validate_state_invariants(self, state: dict) -> None:
        for stage, record in (state.get("stages") or {}).items():
            if record.get("status") == "running" and record.get("completion_mode") in {"recovered_existing_output", "reused_existing_output"}:
                raise OrchestrationError("ORCHESTRATION_STATE_INVARIANT_VIOLATION",
                                         f"{stage} is running with completion_mode={record.get('completion_mode')}",
                                         stage=stage, resume_from=stage)
            if record.get("status") == "running" and record.get("completed_at"):
                raise OrchestrationError("ORCHESTRATION_STATE_INVARIANT_VIOLATION",
                                         f"{stage} is running with completed_at={record.get('completed_at')}",
                                         stage=stage, resume_from=stage)

    def _reconcile_state(self, request: CaseToAtlasRequest, state: dict | None, store: OrchestrationStateStore, *, dry_run: bool) -> dict[str, Any]:
        if not state:
            return {"state": state, "reconciled": False, "abandoned_outputs": []}
        working = deepcopy(state)
        stages = working.setdefault("stages", {})
        base = stages.get("base_run", {})
        abandoned: list[str] = []
        reconciled = False
        if base.get("status") == "running" and base.get("output_run"):
            current_output = Path(base["output_run"])
            current_validation = validate_base_run_for_downstream(current_output, request=request, expected_input_hash=base.get("input_hash"), orchestration_id=self.orchestration_id(request))
            mixed_completion = bool(base.get("completion_mode") in {"recovered_existing_output", "reused_existing_output"} or base.get("completed_at"))
            if mixed_completion and not current_validation.valid:
                candidate = self._latest_valid_base_run(request, exclude={str(current_output)})
                if candidate is None:
                    return {"state": working, "reconciled": False, "abandoned_outputs": []}
                validation = validate_base_run_for_downstream(candidate, request=request, expected_input_hash=None, orchestration_id=self.orchestration_id(request))
                item = {"attempt": base.get("attempt"), "output_run": str(current_output), "reason": "reuse_fallthrough_control_flow_bug", "status": "interrupted"}
                attempts = list(base.get("abandoned_attempts") or [])
                if not any(x.get("output_run") == item["output_run"] for x in attempts):
                    attempts.append(item)
                base.update(status="completed", output_run=str(candidate), completion_mode="recovered_existing_output",
                            recovery_reason="reuse_fallthrough_control_flow_bug_reconciled", validation=validation.to_dict(),
                            error_code=None, error_summary=None, final_status="recovered_existing_output",
                            abandoned_attempts=attempts, semantic_input_hash=self._input_hash("base_run", request, working),
                            semantic_fingerprint_schema=SEMANTIC_FINGERPRINT_SCHEMA)
                base["last_status"]="completed"
                base["artifact_hash"]=self._artifact_hash("base_run", base, request)
                base.pop("started_at", None)
                abandoned.append(str(current_output))
                reconciled = True
        for name in STAGES:
            record = stages.get(name, {})
            if record.get("status") == "pending" and record.get("last_status") == "completed" and self._stage_artifacts_valid(name, record, request):
                record["status"] = "completed"
                record["semantic_input_hash"] = self._input_hash(name, request, working)
                record["semantic_fingerprint_schema"] = SEMANTIC_FINGERPRINT_SCHEMA
                record["artifact_hash"] = self._artifact_hash(name, record, request)
                record["error_code"] = None
                record["error_summary"] = None
                reconciled = True
        if reconciled:
            working.update(status="completed", current_stage=None, error_code=None, error_summary=None)
            if not dry_run:
                store.write_state(working)
                for output in abandoned:
                    store.append_event("stage_interrupted_reconciled", stage="base_run", output_run=output,
                                       reason="reuse_fallthrough_control_flow_bug")
                    store.append_event("reuse_fallthrough_output_abandoned", stage="base_run", output_run=output)
                store.append_event("orchestration_state_reconciled", reason="reuse_fallthrough_control_flow_bug",
                                   abandoned_outputs=abandoned)
        return {"state": working, "reconciled": reconciled, "abandoned_outputs": abandoned}

    def _latest_valid_base_run(self, request: CaseToAtlasRequest, *, exclude: set[str]) -> Path | None:
        oid = self.orchestration_id(request)
        candidates = sorted(request.runs_root.glob(f"{oid}_{request.case_id}_base_run_v*"), key=lambda p: p.name, reverse=True)
        for candidate in candidates:
            if str(candidate) in exclude or str(candidate.resolve()) in exclude:
                continue
            if validate_base_run_for_downstream(candidate, request=request, expected_input_hash=None, orchestration_id=oid).valid:
                return candidate
        return None

    def _apply_existing_stage_action(self, stage: str, item: dict[str, Any], record: dict, input_hash: str, request: CaseToAtlasRequest, oid: str, state: dict, store: OrchestrationStateStore) -> None:
        before_attempt = record.get("attempt")
        before_output = record.get("output_run")
        if item["action"] == "recover":
            self._recover_record(stage, record, input_hash, request, oid, state, store)
            store.append_event("stage_reused", stage=stage, output_run=record.get("output_run"), mode="recovered_existing_output")
        elif item["action"] in {"reuse", "no_op", "skip"}:
            if item["action"] != "skip":
                self._upgrade_reuse_metadata(stage, record, input_hash, request, state, store)
                record["status"] = "completed"
                record["last_status"] = "completed"
                record["error_code"] = None
                record["error_summary"] = None
                store.write_state(state)
                store.append_event("stage_reused", stage=stage, output_run=record.get("output_run"), action=item["action"], reason=item.get("reason"))
        if record.get("attempt") != before_attempt:
            raise OrchestrationError("ORCHESTRATION_STATE_INVARIANT_VIOLATION", f"{stage} reuse changed attempt", stage=stage, resume_from=stage)
        if before_output is not None and record.get("output_run") != before_output:
            raise OrchestrationError("ORCHESTRATION_STATE_INVARIANT_VIOLATION", f"{stage} reuse changed output_run", stage=stage, resume_from=stage)

    def _output_path(self, request: CaseToAtlasRequest, oid: str, stage: str, attempt: int) -> Path:
        return request.runs_root / f"{oid}_{request.case_id}_{stage}_v{attempt}"

    def _input_hash(self, stage: str, request: CaseToAtlasRequest, state: dict) -> str:
        return self._stage_fingerprint(stage, request, state).sha256

    def _stage_fingerprint(self, stage: str, request: CaseToAtlasRequest, state: dict) -> StageFingerprint:
        provider={"provider":os.getenv("L1_PROVIDER") or "","model":os.getenv("MODEL_NAME") or ""}
        scientific_config = self._scientific_config()
        stages=state.get("stages",{})
        if stage=="base_run": material={"case_id":request.case_id,"case_profile_sha256":_file_hash(request.case_profile_path),"search_plan_sha256":_file_hash(request.search_plan_path),"abstract_l1_config":scientific_config["abstract_l1"],**provider}
        elif stage=="pmcid_repair": material={"case_id":request.case_id,"base":self._output_identity(stages.get("base_run",{})),"pmcid_repair_schema":"pmcid_repair_v1"}
        elif stage=="fulltext_l1": material={"case_id":request.case_id,"repair":self._output_identity(stages.get("pmcid_repair",{})),"case_profile_sha256":_file_hash(request.case_profile_path),"fulltext_l1_config":scientific_config["fulltext_l1"],"chunker_config_hash":_hash({"max_sections_per_paper":12,"max_chunks_per_paper":24,"max_chars_per_chunk":6000,"max_total_chunks":200}),**provider}
        elif stage=="fulltext_reasoning_trace": material={"case_id":request.case_id,"fulltext":self._output_identity(stages.get("fulltext_l1",{})),"reasoning_config":scientific_config.get("fulltext_reasoning_trace","legacy_missing_reasoning_config"),**provider}
        elif stage=="fulltext_context_consolidation": material={"case_id":request.case_id,"fulltext":self._output_identity(stages.get("fulltext_l1",{})),"reasoning":self._output_identity(stages.get("fulltext_reasoning_trace",{})),"context_rules":scientific_config.get("fulltext_context_consolidation","legacy_missing_context_config")}
        elif stage=="reentry": material={"case_id":request.case_id,"base":self._output_identity(stages.get("base_run",{})),"fulltext":self._output_identity(stages.get("fulltext_l1",{})),"context":self._output_identity(stages.get("fulltext_context_consolidation",{})),"schema":"fulltext_reentry_v5","reentry_config":scientific_config["reentry"]}
        elif stage=="handoff": material={"case_id":request.case_id,"reentry":self._output_identity(stages.get("reentry",{})),"schema":"atlas_handoff_v1","reasoning_optional":scientific_config.get("fulltext_context_consolidation","legacy_missing_context_config")}
        elif stage=="atlas_sync":
            handoff=stages.get("handoff",{})
            manifest=Path(handoff.get("manifest_path") or "")
            material={"case_id":request.case_id,"handoff_manifest":self._logical_file_identity("atlas_handoff_manifest", manifest),"adapter":ADAPTER_VERSION}
        else:
            registry=request.system_b_output_root/"current_projection.json";material={"registry":_file_hash(registry),"handoff":self._output_identity(stages.get("handoff",{})),"baseline":state.get("safety_baseline")}
        material = {"stage": stage, **material}
        return StageFingerprint(stage=stage, material=material, sha256=_hash(material))

    def _legacy_input_hash(self, stage: str, request: CaseToAtlasRequest, state: dict) -> str:
        provider={"provider":os.getenv("L1_PROVIDER") or "","model":os.getenv("MODEL_NAME") or ""}
        scientific_config = self._scientific_config()
        stages=state.get("stages",{})
        if stage=="base_run": material={"profile":_file_hash(request.case_profile_path),"plan":_file_hash(request.search_plan_path),"api":request.api_enabled,"network":request.network_enabled,"abstract_l1_config":scientific_config["abstract_l1"],**provider}
        elif stage=="pmcid_repair": material={"base":self._legacy_output_identity(stages.get("base_run",{})),"network":request.network_enabled}
        elif stage=="fulltext_l1": material={"repair":self._legacy_output_identity(stages.get("pmcid_repair",{})),"profile":_file_hash(request.case_profile_path),"api":request.api_enabled,"network":request.network_enabled,"fulltext_l1_config":scientific_config["fulltext_l1"],**provider}
        elif stage=="fulltext_reasoning_trace": material={"fulltext":self._legacy_output_identity(stages.get("fulltext_l1",{})),"api":request.api_enabled,"network":request.network_enabled,"reasoning_config":scientific_config.get("fulltext_reasoning_trace","legacy_missing_reasoning_config"),**provider}
        elif stage=="fulltext_context_consolidation": material={"fulltext":self._legacy_output_identity(stages.get("fulltext_l1",{})),"reasoning":self._legacy_output_identity(stages.get("fulltext_reasoning_trace",{})),"context_rules":scientific_config.get("fulltext_context_consolidation","legacy_missing_context_config")}
        elif stage=="reentry": material={"base":self._legacy_output_identity(stages.get("base_run",{})),"fulltext":self._legacy_output_identity(stages.get("fulltext_l1",{})),"context":self._legacy_output_identity(stages.get("fulltext_context_consolidation",{})),"schema":"fulltext_reentry_v5","reentry_config":scientific_config["reentry"]}
        elif stage=="handoff": material={"reentry":self._legacy_output_identity(stages.get("reentry",{})),"schema":"atlas_handoff_v1","reasoning_optional":scientific_config.get("fulltext_context_consolidation","legacy_missing_context_config")}
        elif stage=="atlas_sync":
            manifests=sorted((str(path),_file_hash(path)) for path in request.runs_root.glob("*/artifacts/atlas_handoff_manifest.json"));material={"manifests":manifests,"adapter":ADAPTER_VERSION,"output":str(request.system_b_output_root.resolve()),"database":request.database_url}
        else:
            registry=request.system_b_output_root/"current_projection.json";material={"registry":_file_hash(registry),"handoff":self._legacy_output_identity(stages.get("handoff",{})),"baseline":state.get("safety_baseline")}
        return _hash(material)

    def _scientific_config(self) -> dict[str, str]:
        """Fingerprint prompt/schema/code inputs that control paid scientific stages."""
        prompt_root = REPOSITORY_ROOT / "configs" / "prompts" / "l1"
        prompt_files = sorted(path for path in prompt_root.rglob("*") if path.is_file())
        prompt_hashes = [(str(path.relative_to(REPOSITORY_ROOT)), _file_hash(path)) for path in prompt_files]
        return {
            "abstract_l1": _hash({"prompt_files": prompt_hashes}),
            "fulltext_l1": _hash({
                "prompt_version": __import__(
                    "code_engine.fulltext.fulltext_l1_extractor", fromlist=["PROMPT_VERSION"]
                ).PROMPT_VERSION,
                "extractor_version": __import__(
                    "code_engine.fulltext.fulltext_l1_extractor", fromlist=["EXTRACTOR_VERSION"]
                ).EXTRACTOR_VERSION,
                "chunker_version": __import__(
                    "code_engine.fulltext.fulltext_l1_extractor", fromlist=["CHUNKER_VERSION"]
                ).CHUNKER_VERSION,
                "response_schema": _file_hash(REPOSITORY_ROOT / "configs/prompts/l1/output_schema_v2.json"),
            }),
            "reentry": _hash({
                "reentry": _file_hash(REPOSITORY_ROOT / "src/code_engine/fulltext/reentry.py"),
                "adapter": _file_hash(REPOSITORY_ROOT / "src/code_engine/system_b/adapters/fulltext_reentry_v5.py"),
            }),
            "fulltext_reasoning_trace": _hash({
                "prompt_version": PROMPT_VERSION,
                "retrieval_config_version": RETRIEVAL_CONFIG_VERSION,
                "extractor_code_version": EXTRACTOR_CODE_VERSION,
                "module": _file_hash(REPOSITORY_ROOT / "src/code_engine/fulltext/reasoning_trace.py"),
            }),
            "fulltext_context_consolidation": _hash({
                "context_rule_version": CONTEXT_RULE_VERSION,
                "module": _file_hash(REPOSITORY_ROOT / "src/code_engine/fulltext/reasoning_trace.py"),
            }),
        }

    def _artifact_hash(self, stage: str, record: dict, request: CaseToAtlasRequest) -> str:
        run = Path(record.get("output_run") or "")
        paths: list[Path]
        if stage == "base_run":
            paths = [run / "run_state.json", run / "triple_run_manifest.json", run / "triple_card.json",
                     run / "artifacts/abstract_l1_claims.jsonl", run / "artifacts/abstract_l1_summary.json",
                     run / "artifacts/l2_abstract_observations.json", run / "artifacts/l2_abstract_summary.json"] + [
                run / "artifacts" / name for name in (*FULLTEXT_CANDIDATE_SOURCE_FILES, "fulltext_escalation_plan.json")
                if (run / "artifacts" / name).is_file()
            ]
        elif stage == "pmcid_repair":
            paths = [run / "pmcid_repair_manifest.json", run / "artifacts/pmcid_enrichment_audit.jsonl"]
        elif stage == "fulltext_l1":
            paths = [run / "fulltext_bridge_replay_manifest.json", run / "artifacts/l35_fulltext_l1_claims.jsonl", run / "artifacts/l35_fulltext_l1_summary.json"]
        elif stage == "fulltext_reasoning_trace":
            paths = [
                run / "artifacts/fulltext_claim_passage_index.jsonl",
                run / "artifacts/fulltext_reasoning_traces.jsonl",
                run / "artifacts/fulltext_reasoning_trace_summary.json",
                run / "artifacts/experimental_evidence_chains.jsonl",
                run / "artifacts/claim_evidence_links.jsonl",
                run / "artifacts/experimental_evidence_chain_summary.json",
            ]
        elif stage == "fulltext_context_consolidation":
            paths = [run / "artifacts/fulltext_context_consolidations.jsonl", run / "artifacts/fulltext_context_consolidation_summary.json"]
        elif stage == "reentry":
            paths = [run / "fulltext_reentry_manifest.json"]
        elif stage == "handoff":
            paths = [Path(record.get("manifest_path") or ""), Path(record.get("manifest_path") or "").with_name("ATLAS_READY")]
        elif stage == "atlas_sync":
            registry = request.system_b_output_root / "current_projection.json"
            paths = [registry]
            try:
                _, projection_root, _ = current_projection(request.system_b_output_root)
                paths.append(projection_root / "projection_manifest.json")
            except Exception:
                paths.append(request.system_b_output_root / "missing_projection_manifest.json")
        else:
            return _hash(record.get("verification") or {})
        return _hash([self._logical_file_identity(path.name, path) for path in paths])

    def _output_identity(self, record: dict) -> dict:
        path=Path(record.get("output_run") or "")
        candidates=[
            ("run_state", path/"run_state.json"),
            ("pmcid_repair_manifest", path/"pmcid_repair_manifest.json"),
            ("fulltext_bridge_replay_manifest", path/"fulltext_bridge_replay_manifest.json"),
            ("fulltext_l1_claims", path/"artifacts/l35_fulltext_l1_claims.jsonl"),
            ("reasoning_summary", path/"artifacts/fulltext_reasoning_trace_summary.json"),
            ("reasoning_traces", path/"artifacts/fulltext_reasoning_traces.jsonl"),
            ("experimental_evidence_chains", path/"artifacts/experimental_evidence_chains.jsonl"),
            ("claim_evidence_links", path/"artifacts/claim_evidence_links.jsonl"),
            ("experimental_evidence_chain_summary", path/"artifacts/experimental_evidence_chain_summary.json"),
            ("context_summary", path/"artifacts/fulltext_context_consolidation_summary.json"),
            ("context_rows", path/"artifacts/fulltext_context_consolidations.jsonl"),
            ("fulltext_reentry_manifest", path/"fulltext_reentry_manifest.json"),
            ("atlas_handoff_manifest", Path(record.get("manifest_path") or "")),
        ]
        return {"artifacts":[self._logical_file_identity(name, item) for name,item in candidates if str(item) not in {".",""} and item.is_file()]}

    def _legacy_output_identity(self, record: dict) -> dict:
        path=Path(record.get("output_run") or "")
        candidates=[path/"run_state.json",path/"pmcid_repair_manifest.json",path/"fulltext_bridge_replay_manifest.json",path/"artifacts/fulltext_reasoning_trace_summary.json",path/"artifacts/fulltext_context_consolidation_summary.json",path/"fulltext_reentry_manifest.json",Path(record.get("manifest_path") or "")]
        return {"path":str(path),"hash":next((_file_hash(item) for item in candidates if str(item) not in {".",""} and item.is_file()),"missing")}

    def _logical_file_identity(self, logical_name: str, path: Path) -> dict[str, Any]:
        return {"logical_name": logical_name, "sha256": _file_hash(path), "size_bytes": path.stat().st_size if path.is_file() else None}

    def _record_valid(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest) -> bool:
        if record.get("status")!="completed": return False
        state_context = self._state_from_record_context(stage, record, request)
        legacy_hash = None
        try:
            legacy_hash = self._legacy_input_hash(stage, request, state_context)
        except Exception:
            pass
        stored_hashes = {record.get("semantic_input_hash"), record.get("input_hash")}
        stored_hashes.add(legacy_hash)
        if stage != "base_run" and record.get("semantic_fingerprint_schema") != SEMANTIC_FINGERPRINT_SCHEMA and self._stage_artifacts_valid(stage, record, request):
            return True
        if input_hash not in stored_hashes: return False
        legacy_match = bool(record.get("input_hash") == legacy_hash and not record.get("semantic_input_hash"))
        if record.get("artifact_hash") and record.get("artifact_hash") != self._artifact_hash(stage, record, request) and not legacy_match: return False
        return self._stage_artifacts_valid(stage, record, request)

    def _stage_artifacts_valid(self, stage: str, record: dict, request: CaseToAtlasRequest) -> bool:
        try:
            if stage=="base_run":
                return validate_base_run_for_downstream(record["output_run"], request=request, expected_input_hash=record.get("input_hash"), orchestration_id=self.orchestration_id(request)).valid
            if stage=="pmcid_repair": return Path(record["output_run"],"pmcid_repair_manifest.json").is_file()
            if stage=="fulltext_l1":
                summary=_read(Path(record["output_run"])/"fulltext_bridge_replay_manifest.json").get("stage_summary",{})
                l1_summary=_read(Path(record["output_run"])/"artifacts/l35_fulltext_l1_summary.json")
                return str(summary.get("status") or l1_summary.get("fulltext_l1_status") or "").startswith("completed") or str(l1_summary.get("fulltext_l1_status") or "").startswith("completed")
            if stage=="fulltext_reasoning_trace":
                summary=_read(Path(record["output_run"])/"artifacts/fulltext_reasoning_trace_summary.json")
                chain_summary=_read(Path(record["output_run"])/"artifacts/experimental_evidence_chain_summary.json")
                return bool(summary.get("status_accounting_valid", True)) and "evidence_chain_count" in chain_summary and (Path(record["output_run"])/"artifacts/claim_evidence_links.jsonl").is_file()
            if stage=="fulltext_context_consolidation":
                summary=_read(Path(record["output_run"])/"artifacts/fulltext_context_consolidation_summary.json")
                return "consolidation_count" in summary and "claim_evidence_link_status" in summary
            if stage=="reentry": return _read(Path(record["output_run"])/"fulltext_reentry_manifest.json").get("status")=="completed"
            if stage=="handoff": validate_handoff(record["manifest_path"],runs_root=request.runs_root);return True
            if stage=="atlas_sync":
                current_projection(request.system_b_output_root)
                return record.get("operation_status") in {"completed","no_op"}
            if stage=="verification": return record.get("verification",{}).get("status")=="passed"
        except Exception: return False
        return False

    def _state_from_record_context(self, stage: str, record: dict, request: CaseToAtlasRequest) -> dict:
        # Best-effort legacy compatibility for tests that call _record_valid directly.
        oid = self.orchestration_id(request)
        state = OrchestrationStateStore(request.runs_root, oid).read_state() or {"stages": {}}
        state.setdefault("stages", {}).setdefault(stage, record)
        return state

    def _reuse_decision(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest, *, forced: bool = False) -> StageReuseDecision:
        stored = record.get("semantic_input_hash") or record.get("input_hash")
        output_run = record.get("output_run") or record.get("manifest_path")
        if forced:
            return StageReuseDecision(stage, "rerun", "forced", stored, input_hash, output_run=output_run,
                                      changed_components={"force_stage": {"previous": False, "current": True}})
        if record.get("status") != "completed":
            return StageReuseDecision(stage, "rerun", "stage_not_completed", stored, input_hash, output_run=output_run)
        valid_artifacts = self._stage_artifacts_valid(stage, record, request)
        if not valid_artifacts:
            return StageReuseDecision(stage, "rerun", "required_artifact_missing_or_invalid", stored, input_hash, output_run=output_run)
        if stage != "base_run" and record.get("semantic_fingerprint_schema") != SEMANTIC_FINGERPRINT_SCHEMA:
            return StageReuseDecision(stage, "reuse", "completed_artifacts_valid_semantic_schema_backfill", stored, input_hash,
                                      output_run=output_run, validated_artifacts=1, projection_id=record.get("projection_id"))
        legacy = self._legacy_input_hash(stage, request, OrchestrationStateStore(request.runs_root, self.orchestration_id(request)).read_state() or {"stages": {}})
        legacy_match = bool(record.get("input_hash") == legacy and not record.get("semantic_input_hash"))
        if record.get("artifact_hash") and record.get("artifact_hash") != self._artifact_hash(stage, record, request) and not legacy_match:
            return StageReuseDecision(stage, "rerun", "artifact_hash_changed", stored, input_hash, output_run=output_run,
                                      changed_components={"artifact_hash": {"previous": record.get("artifact_hash"), "current": self._artifact_hash(stage, record, request)}})
        if input_hash in {record.get("semantic_input_hash"), record.get("input_hash")}:
            reason = "semantic_fingerprint_match" if record.get("semantic_input_hash") == input_hash or record.get("input_hash") == input_hash else "legacy_input_hash_match"
            return StageReuseDecision(stage, "reuse", reason, stored, input_hash, output_run=output_run, validated_artifacts=1,
                                      projection_id=record.get("projection_id"))
        if record.get("input_hash") == legacy:
            return StageReuseDecision(stage, "reuse", "legacy_input_hash_matches_current_semantics", record.get("input_hash"), input_hash,
                                      output_run=output_run, validated_artifacts=1, projection_id=record.get("projection_id"))
        return StageReuseDecision(stage, "rerun", "semantic_fingerprint_changed", stored, input_hash, output_run=output_run,
                                  changed_components={"semantic_input_hash": {"previous": stored, "current": input_hash}})

    def _upgrade_reuse_metadata(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest, state: dict, store: OrchestrationStateStore) -> None:
        if record.get("semantic_input_hash") == input_hash and record.get("input_hash") == input_hash:
            return
        legacy = record.get("input_hash")
        record["legacy_input_hash"] = legacy
        record["semantic_input_hash"] = input_hash
        record["semantic_fingerprint_schema"] = SEMANTIC_FINGERPRINT_SCHEMA
        record["input_hash"] = input_hash
        record["artifact_hash"] = self._artifact_hash(stage, record, request)
        store.write_state(state)
        store.append_event("stage_reuse_metadata_upgraded", stage=stage, legacy_input_hash=legacy,
                           semantic_input_hash=input_hash, output_run=record.get("output_run"))

    def _record_recoverable(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest, oid: str) -> bool:
        if stage != "base_run" or record.get("status") != "failed" or not record.get("output_run"):
            return False
        if record.get("previous_input_hash") not in {None, input_hash} and record.get("input_hash") != input_hash:
            return False
        return validate_base_run_for_downstream(record["output_run"], request=request, expected_input_hash=input_hash, orchestration_id=oid).valid

    def _recover_record(self, stage: str, record: dict, input_hash: str, request: CaseToAtlasRequest, oid: str, state: dict, store: OrchestrationStateStore) -> None:
        validation = validate_base_run_for_downstream(record["output_run"], request=request, expected_input_hash=input_hash, orchestration_id=oid)
        if not validation.valid:
            raise OrchestrationError(validation.code or "BASE_RUN_RECOVERY_FAILED", validation.summary or "base run recovery validation failed", stage=stage, resume_from=stage)
        record.update(status="completed", input_hash=input_hash, completed_at=utcnow(), completion_mode="recovered_existing_output",
                      recovery_reason="legacy_fulltext_escalation_completion_check_fixed", validation=validation.to_dict(),
                      api_calls=0, network_calls=0, final_status="recovered_existing_output", error_code=None, error_summary=None)
        record["last_status"]="completed"
        record["artifact_hash"]=self._artifact_hash(stage, record, request)
        state.update(error_code=None, error_summary=None)
        store.write_state(state)
        store.append_event("stage_recovered", stage=stage, output_run=record.get("output_run"),
                           reason="legacy_fulltext_escalation_completion_check_fixed",
                           validation=validation.to_dict())

    def _execute(self, name: str, request: CaseToAtlasRequest, state: dict, record: dict) -> dict[str,Any]:
        if request.reuse_only:
            raise OrchestrationError("REUSE_ONLY_STAGE_INVALID", f"reuse-only forbids executing {name}", stage=name, resume_from=name)
        profile=_read(request.case_profile_path);plan=_read(request.search_plan_path)
        if name=="base_run":
            from code_engine.extraction.client_factory import build_l1_client_from_env_or_config
            from code_engine.workflow.orchestrator import run_workflow
            output=Path(record["output_run"]);resume=output if (output/"run_state.json").is_file() else None
            client=build_l1_client_from_env_or_config(os.getenv("L1_PROVIDER"),os.getenv("MODEL_NAME")) if request.api_enabled else None
            run_state=run_workflow(query=profile["query"],run_dir=output,until="fulltext_escalation",execute=True,api=request.api_enabled,network=request.network_enabled,max_papers=60,diversify_acquisition=True,paper_year_from=plan.get("paper_year_from"),paper_year_to=plan.get("paper_year_to"),temporal_role=(plan.get("paper_year_filter") or {}).get("temporal_role","discovery"),search_plan_file=request.search_plan_path,fail_if_search_plan_drift=True,resume=resume,allow_uncertain_intake=True,l1_mode="abstract_screening",enable_fulltext_escalation=True,l1_llm_client=client,semantic_llm_client=client,seed_triple=plan.get("seed_triple"),allow_compatible_l1_task_reuse=True)
            validation=validate_base_run_for_downstream(output, request=request, expected_input_hash=record.get("input_hash"), orchestration_id=self.orchestration_id(request))
            if not validation.valid:
                raise OrchestrationError(validation.code or "BASE_RUN_VALIDATION_FAILED", validation.summary or "base run validation failed", stage=name, resume_from=name)
            return {"api_calls":run_state.api_calls_made,"network_calls":run_state.network_calls_made,"final_status":run_state.final_status,"validation":validation.to_dict()}
        if name=="pmcid_repair":
            result=repair_fulltext_candidate_pmcids(source_run=state["stages"]["base_run"]["output_run"],output_run=record["output_run"],network=request.network_enabled)
            return {"result":result,"network_calls":result.get("authoritative_lookup_attempt_count",0),"cache_hits":self._count_true(Path(record["output_run"])/"artifacts/pmcid_enrichment_audit.jsonl","cache_hit")}
        if name=="fulltext_l1":
            policy=profile.get("fulltext_policy") or {}
            result=replay_fulltext_bridge_from_run(case_id=request.case_id,source_run=state["stages"]["pmcid_repair"]["output_run"],output_run=record["output_run"],network=request.network_enabled,api=request.api_enabled,max_papers=int(policy.get("max_papers") or 20))
            summary=result.get("stage_summary",{});return {"result":result,"api_calls":summary.get("fulltext_l1_api_calls",0),"network_calls":result.get("retrieval_attempt_count",0),"cache_hits":summary.get("fulltext_l1_cache_hit_count",0)}
        if name=="fulltext_reasoning_trace":
            summary=run_fulltext_reasoning_trace_stage(record["output_run"],case_id=request.case_id,api_enabled=request.api_enabled,network_enabled=request.network_enabled,dry_run=False,force=name in request.force_stages)
            if not summary.get("status_accounting_valid", True): raise ValueError("reasoning trace status accounting failed")
            return {"summary":summary,"api_calls":summary.get("api_call_count",0),"cache_hits":summary.get("cache_hit_count",0)}
        if name=="fulltext_context_consolidation":
            summary=run_fulltext_context_consolidation_stage(record["output_run"],case_id=request.case_id)
            return {"summary":summary,"api_calls":0,"cache_hits":0}
        if name=="reentry":
            result=run_replay(case_id=request.case_id,base_run=Path(state["stages"]["base_run"]["output_run"]),fulltext_run=Path(state["stages"]["fulltext_l1"]["output_run"]),output_root=request.runs_root,output_suffix="case_to_atlas_v5",output_run=Path(record["output_run"]),network=False,api=False,publish_atlas=False)
            return {"result":result,"claim_count":result.get("input_fulltext_claim_count",0)}
        if name=="handoff":
            reentry=Path(state["stages"]["reentry"]["output_run"]);result=publish_atlas_handoff(reentry,runs_root=request.runs_root,lineage={"base_run":state["stages"]["base_run"]["output_run"],"pmcid_repair_run":state["stages"]["pmcid_repair"]["output_run"],"fulltext_l1_run":state["stages"]["fulltext_l1"]["output_run"],"reentry_run":reentry})
            validate_handoff(result["manifest_path"],runs_root=request.runs_root);return {"manifest_path":result["manifest_path"],"manifest_hash":result["manifest_hash"],"operation_status":result["status"]}
        if name=="atlas_sync":
            result=sync_system_a(runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,refresh_current_projection=True,manifest=state["stages"]["handoff"].get("manifest_path"))
            if result.get("status") not in {"completed","no_op"} or result.get("rejected"): raise ValueError(json.dumps(result,ensure_ascii=False))
            return {"result":result,"operation_status":result["status"],"projection_id":result.get("current_projection_id")}
        verification=self._verification(request,state)
        second=sync_system_a(runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,refresh_current_projection=True,manifest=state["stages"]["handoff"].get("manifest_path"))
        if second.get("status")!="no_op": raise ValueError("second sync was not no-op")
        verification["second_sync_status"]="no_op";return {"verification":verification,"operation_status":"completed"}

    def _verification(self,request,state):
        return verify_case_to_atlas(case_id=request.case_id,reentry_run=Path(state["stages"]["reentry"]["output_run"]),handoff_manifest=Path(state["stages"]["handoff"]["manifest_path"]),runs_root=request.runs_root,database_url=request.database_url,output_root=request.system_b_output_root,safety_baseline=state["safety_baseline"],prior_cases=state["prior_cases"])

    def _count_true(self,path,key):
        if not path.is_file(): return 0
        return sum(json.loads(line).get(key) is True for line in path.read_text().splitlines() if line.strip())

    def _result(self,request,oid,state,reused):
        s=state["stages"];verification=s["verification"].get("verification",{})
        current=state.get("last_command_calls") or {}
        stage_counts={name:{"api_calls":int(s[name].get("api_calls") or 0),
                            "network_calls":int(s[name].get("network_calls") or 0),
                            "cache_hits":int(s[name].get("cache_hits") or 0)} for name in STAGES}
        reconciliation=state.get("last_reconciliation") or {}
        return CaseToAtlasResult(orchestration_id=oid,status=state["status"],case_id=request.case_id,base_run=s["base_run"].get("output_run"),pmcid_repair_run=s["pmcid_repair"].get("output_run"),fulltext_run=s["fulltext_l1"].get("output_run"),reentry_run=s["reentry"].get("output_run"),handoff_manifest=s["handoff"].get("manifest_path"),handoff_status=s["handoff"].get("operation_status"),ingestion_id=verification.get("ingestion_id"),prediction_run_id=verification.get("prediction_run_id"),projection_id=verification.get("projection_id") or s["atlas_sync"].get("projection_id"),current_case_count=verification.get("current_case_count",0),claim_count=verification.get("claim_count",s["reentry"].get("claim_count",0)),dossier_count=verification.get("dossier_count",0),context_row_count=verification.get("context_row_count",0),exploratory_triple_count=verification.get("exploratory_triple_count",0),formal_conflict_count=verification.get("formal_conflict_count",0),api_calls=int(current.get("api_calls") or 0),network_calls=int(current.get("network_calls") or 0),cache_hits=int(current.get("cache_hits") or 0),historical_api_calls=sum(v["api_calls"] for v in stage_counts.values()),historical_network_calls=sum(v["network_calls"] for v in stage_counts.values()),historical_cache_hits=sum(v["cache_hits"] for v in stage_counts.values()),stage_call_counts=stage_counts,reused_stages=reused,sync_status=s["atlas_sync"].get("operation_status"),warnings=[] if not verification.get("quarantine_count") else [f"quarantine_count={verification['quarantine_count']}"] ,verification=verification,execution_policy=self._execution_policy(request).to_dict(),reconciled_state=bool(reconciliation.get("reconciled")),abandoned_outputs=list(reconciliation.get("abandoned_outputs") or []),stage_execution=state.get("last_stage_execution") or {})
