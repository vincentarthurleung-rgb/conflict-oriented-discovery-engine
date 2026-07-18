from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from code_engine.cli.run_case_to_atlas import main as cli_main
from code_engine.integration.atlas_handoff import sha256_file
from code_engine.orchestration.case_to_atlas import CaseToAtlasOrchestrator, OrchestrationError, validate_base_run_for_downstream
from code_engine.orchestration.models import CaseToAtlasRequest, STAGES


class FakeOrchestrator(CaseToAtlasOrchestrator):
    def __init__(self, fail_stage=None): self.calls=[];self.fail_stage=fail_stage
    def _record_valid(self,stage,record,input_hash,request): return record.get("status")=="completed" and record.get("input_hash")==input_hash
    def _execute(self,name,request,state,record):
        self.calls.append(name)
        if name==self.fail_stage: raise ValueError("injected failure")
        if name=="handoff": return {"manifest_path":str(request.runs_root/"fake_manifest.json"),"operation_status":"published"}
        if name=="atlas_sync": return {"operation_status":"completed","projection_id":"projection_test"}
        if name=="verification": return {"verification":{"status":"passed","projection_id":"projection_test","current_case_count":11,"claim_count":1,"dossier_count":1,"context_row_count":1,"exploratory_triple_count":1,"formal_conflict_count":0},"operation_status":"completed"}
        return {"api_calls":1 if name in {"base_run","fulltext_l1"} else 0,"network_calls":1 if name in {"base_run","pmcid_repair","fulltext_l1"} else 0}


class ArtifactOrchestrator(CaseToAtlasOrchestrator):
    def __init__(self): self.calls=[]
    def _execute(self,name,request,state,record):
        self.calls.append(name)
        if name != "base_run": raise AssertionError(name)
        write_valid_base_run(Path(record["output_run"]), request, legacy_status="completed")
        return {"api_calls":0,"network_calls":0}


def write_valid_base_run(run: Path, request: CaseToAtlasRequest, *, legacy_status="skipped", manifest_status="completed", case_id=None, plan_hash=None, include_candidates=True):
    artifacts=run/"artifacts";artifacts.mkdir(parents=True,exist_ok=True)
    profile=json.loads(Path(request.case_profile_path).read_text())
    run_state={"query":profile["query"],"final_status":"partial","steps":{"fulltext_escalation":{"status":legacy_status}}}
    (run/"run_state.json").write_text(json.dumps(run_state))
    manifest={"status":manifest_status,"case_id":case_id or request.case_id,"input_hash":None,"run_dir":str(run)}
    (run/"triple_run_manifest.json").write_text(json.dumps(manifest))
    (run/"triple_card.json").write_text(json.dumps({"status":manifest_status}))
    (artifacts/"search_plan_replay.json").write_text(json.dumps({"frozen_plan_hash":plan_hash or sha256_file(Path(request.search_plan_path))}))
    (artifacts/"abstract_l1_claims.jsonl").write_text('{"claim_id":"a1"}\n')
    (artifacts/"abstract_l1_summary.json").write_text(json.dumps({"abstract_claim_count":1}))
    (artifacts/"l2_abstract_observations.json").write_text(json.dumps([{"observation_id":"o1"}]))
    (artifacts/"l2_abstract_summary.json").write_text(json.dumps({"retained_observation_count":1}))
    if include_candidates:
        (artifacts/"fulltext_escalation_candidates.jsonl").write_text('{"pmid":"1","title":"Paper"}\n')
        (artifacts/"fulltext_escalation_plan.json").write_text(json.dumps({"selected":[{"pmid":"1","title":"Paper"}]}))


class CaseToAtlasOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);package=self.root/"configs/generated_cases/case_one";package.mkdir(parents=True)
        self.profile=package/"case_profile.json";self.plan=package/"search_plan.frozen.json"
        self.profile.write_text(json.dumps({"case_id":"case_one","query":"A affects B","fulltext_policy":{"max_papers":2}}))
        self.plan.write_text(json.dumps({"case_id":"case_one","frozen":True,"seed_triple":{},"paper_year_from":2000,"paper_year_to":2020}))
        self.request=CaseToAtlasRequest(case_id="case_one",case_profile_path=self.profile,search_plan_path=self.plan,runs_root=self.root/"runs",system_b_output_root=self.root/"out",database_url=f"sqlite:///{self.root/'atlas.db'}")
        # Avoid requiring a migrated DB in orchestration-control unit tests.
        self.baseline_patch=patch("code_engine.orchestration.case_to_atlas.evaluation_counts",return_value={"review_items":459,"assignments":60,"annotations":0,"gold":0,"metrics":0});self.baseline_patch.start()

    def tearDown(self): self.baseline_patch.stop();self.tmp.cleanup()

    def test_dry_run_is_read_only_and_resolves_package(self):
        request=CaseToAtlasRequest(**{**self.request.__dict__,"dry_run":True});result=FakeOrchestrator().run(request)
        self.assertEqual(result.status,"dry_run");self.assertEqual(result.verification["case_profile"],str(self.profile));self.assertFalse((self.root/"runs/_orchestration").exists())

    def test_missing_package_fails_cleanly(self):
        with self.assertRaises(OrchestrationError) as caught:FakeOrchestrator().plan(CaseToAtlasRequest(case_id="missing",case_profile_path=self.root/"x",search_plan_path=self.root/"y",runs_root=self.root/"runs"))
        self.assertEqual(caught.exception.code,"CASE_PACKAGE_MISSING")

    def test_stage_order_and_second_run_reuses_all(self):
        first=FakeOrchestrator();result=first.run(self.request);self.assertEqual(first.calls,list(STAGES));self.assertEqual(result.status,"completed")
        second=FakeOrchestrator();result=second.run(self.request);self.assertEqual(second.calls,[]);self.assertEqual(result.reused_stages,list(STAGES))
        self.assertEqual(result.api_calls,0)
        self.assertEqual(result.network_calls,0)
        self.assertGreater(result.historical_api_calls,0)
        self.assertTrue(all(row["runner_called"] is False for row in result.stage_execution.values()))

    def test_reuse_only_reuse_is_terminal_no_attempt_or_stage_started(self):
        FakeOrchestrator().run(self.request)
        oid=FakeOrchestrator().orchestration_id(self.request.resolved());root=self.root/"runs/_orchestration"/oid
        before_state=json.loads((root/"orchestration_state.json").read_text())
        before_attempts={name:row.get("attempt") for name,row in before_state["stages"].items()}
        before_events=(root/"orchestration_events.jsonl").read_text()
        runner=FakeOrchestrator()
        result=runner.run(CaseToAtlasRequest(**{**self.request.__dict__,"reuse_only":True,"api_enabled":True,"network_enabled":True}))
        after_state=json.loads((root/"orchestration_state.json").read_text())
        after_events=(root/"orchestration_events.jsonl").read_text()
        self.assertEqual(runner.calls,[])
        self.assertEqual({name:row.get("attempt") for name,row in after_state["stages"].items()}, before_attempts)
        self.assertNotIn('"stage_started"', after_events[len(before_events):])
        self.assertEqual(result.api_calls,0)
        self.assertEqual(result.network_calls,0)

    def test_reuse_only_missing_stage_fails_closed(self):
        runner=FakeOrchestrator()
        with self.assertRaises(OrchestrationError) as caught:
            runner.run(CaseToAtlasRequest(**{**self.request.__dict__,"reuse_only":True,"api_enabled":True,"network_enabled":True}))
        self.assertEqual(caught.exception.code,"REUSE_ONLY_STAGE_INVALID")
        self.assertEqual(runner.calls,[])

    def test_reuse_only_force_stage_conflict(self):
        with self.assertRaises(OrchestrationError) as caught:
            FakeOrchestrator().run(CaseToAtlasRequest(**{**self.request.__dict__,"reuse_only":True,"force_stages":frozenset({"fulltext_l1"})}))
        self.assertEqual(caught.exception.code,"REUSE_ONLY_FORCE_STAGE_CONFLICT")

    def test_permission_flags_do_not_change_semantic_fingerprint(self):
        orch=CaseToAtlasOrchestrator()
        offline=CaseToAtlasRequest(**{**self.request.__dict__,"api_enabled":False,"network_enabled":False}).resolved()
        online=CaseToAtlasRequest(**{**self.request.__dict__,"api_enabled":True,"network_enabled":True}).resolved()
        self.assertEqual(orch._input_hash("base_run",offline,{"stages":{}}),orch._input_hash("base_run",online,{"stages":{}}))

    def test_entity_llm_cleaner_changes_base_run_fingerprint(self):
        orch=CaseToAtlasOrchestrator()
        disabled=CaseToAtlasRequest(**{**self.request.__dict__,"entity_llm_cleaner_enabled":False}).resolved()
        enabled=CaseToAtlasRequest(**{**self.request.__dict__,"entity_llm_cleaner_enabled":True}).resolved()
        self.assertNotEqual(orch._input_hash("base_run",disabled,{"stages":{}}),orch._input_hash("base_run",enabled,{"stages":{}}))

    def test_base_run_injects_entity_cleaner_client_without_api_flag(self):
        orch=CaseToAtlasOrchestrator()
        request=CaseToAtlasRequest(**{**self.request.__dict__,"network_enabled":True,"api_enabled":False,"entity_llm_cleaner_enabled":True}).resolved()
        state={"stages":{}}
        record={"output_run":str(orch._output_path(request, orch.orchestration_id(request), "base_run", 1))}
        client=object()

        def fake_workflow(**kwargs):
            self.assertFalse(kwargs["api"])
            self.assertTrue(kwargs["entity_llm_cleaner"])
            self.assertIs(kwargs["entity_llm_client"], client)
            write_valid_base_run(Path(record["output_run"]), request, legacy_status="completed")
            return SimpleNamespace(api_calls_made=0, network_calls_made=0, final_status="completed")

        with patch("code_engine.extraction.client_factory.diagnose_entity_cleaner_provider", return_value={"provider_available":True}), \
             patch("code_engine.extraction.client_factory.build_entity_cleaner_client_from_config", return_value=client), \
             patch("code_engine.workflow.orchestrator.run_workflow", side_effect=fake_workflow):
            result=orch._execute("base_run",request,state,record)

        self.assertEqual(result["api_calls"],0)

    def test_output_path_attempt_and_timestamp_do_not_change_output_identity(self):
        orch=CaseToAtlasOrchestrator()
        one=self.root/"runs/a_fulltext_l1_v1";two=self.root/"runs/b_fulltext_l1_v2"
        for run in (one,two):
            (run/"artifacts").mkdir(parents=True)
            (run/"fulltext_bridge_replay_manifest.json").write_text(json.dumps({"stage_summary":{"status":"completed"}}))
            (run/"artifacts/l35_fulltext_l1_claims.jsonl").write_text('{"claim_id":"c1"}\n')
        first=orch._output_identity({"output_run":str(one),"attempt":1,"started_at":"2026-01-01"})
        second=orch._output_identity({"output_run":str(two),"attempt":2,"started_at":"2026-02-01"})
        self.assertEqual(first,second)

    def test_force_stage_invalidates_downstream_only(self):
        FakeOrchestrator().run(self.request);forced=CaseToAtlasRequest(**{**self.request.__dict__,"force_stages":frozenset({"reentry"})});runner=FakeOrchestrator();runner.run(forced)
        self.assertEqual(runner.calls,list(STAGES[STAGES.index("reentry"):]))

    def test_search_plan_change_invalidates_everything(self):
        FakeOrchestrator().run(self.request);payload=json.loads(self.plan.read_text());payload["paper_year_to"]=2021;self.plan.write_text(json.dumps(payload));runner=FakeOrchestrator();runner.run(self.request)
        self.assertEqual(runner.calls,list(STAGES))

    def test_scientific_prompt_config_change_invalidates_paid_stages(self):
        first={"abstract_l1":"a","fulltext_l1":"b","reentry":"c","fulltext_reasoning_trace":"d","fulltext_context_consolidation":"e"};second={**first,"abstract_l1":"changed"}
        with patch.object(CaseToAtlasOrchestrator,"_scientific_config",return_value=first): FakeOrchestrator().run(self.request)
        runner=FakeOrchestrator()
        with patch.object(CaseToAtlasOrchestrator,"_scientific_config",return_value=second): runner.run(self.request)
        self.assertEqual(runner.calls,list(STAGES))

    def test_modified_completed_artifact_is_not_reused(self):
        request=CaseToAtlasRequest(**{**self.request.__dict__,"stop_after":"base_run"})
        first=ArtifactOrchestrator();first.run(request)
        oid=first.orchestration_id(request.resolved());state=json.loads((self.root/"runs/_orchestration"/oid/"orchestration_state.json").read_text())
        run=Path(state["stages"]["base_run"]["output_run"])
        (run/"artifacts/fulltext_escalation_candidates.jsonl").write_text('{"pmid":"tampered"}\n')
        resumed=ArtifactOrchestrator();resumed.run(request)
        self.assertEqual(resumed.calls,["base_run"])

    def test_base_validation_accepts_skipped_legacy_with_required_artifacts(self):
        run=self.root/"runs"/f"{FakeOrchestrator().orchestration_id(self.request.resolved())}_case_one_base_run_v1"
        write_valid_base_run(run,self.request,legacy_status="skipped")
        result=validate_base_run_for_downstream(run,request=self.request.resolved(),orchestration_id=FakeOrchestrator().orchestration_id(self.request.resolved()))
        self.assertTrue(result.valid,result.to_dict())

    def test_base_validation_accepts_not_requested_legacy_with_required_artifacts(self):
        run=self.root/"runs"/f"{FakeOrchestrator().orchestration_id(self.request.resolved())}_case_one_base_run_v1"
        write_valid_base_run(run,self.request,legacy_status="not_requested")
        result=validate_base_run_for_downstream(run,request=self.request.resolved(),orchestration_id=FakeOrchestrator().orchestration_id(self.request.resolved()))
        self.assertTrue(result.valid,result.to_dict())

    def test_base_validation_rejects_failed_manifest_missing_candidates_and_fingerprint(self):
        oid=FakeOrchestrator().orchestration_id(self.request.resolved())
        failed=self.root/"runs"/f"{oid}_case_one_base_run_v1";write_valid_base_run(failed,self.request,legacy_status="failed",manifest_status="failed",include_candidates=False)
        self.assertFalse(validate_base_run_for_downstream(failed,request=self.request.resolved(),orchestration_id=oid).valid)
        missing=self.root/"runs"/f"{oid}_case_one_base_run_v2";write_valid_base_run(missing,self.request,include_candidates=False)
        self.assertEqual(validate_base_run_for_downstream(missing,request=self.request.resolved(),orchestration_id=oid).code,"BASE_RUN_ARTIFACT_MISSING")
        mismatch=self.root/"runs"/f"{oid}_case_one_base_run_v3";write_valid_base_run(mismatch,self.request,plan_hash="wrong")
        self.assertEqual(validate_base_run_for_downstream(mismatch,request=self.request.resolved(),orchestration_id=oid).code,"BASE_RUN_FINGERPRINT_MISMATCH")

    def test_failed_base_stage_recovers_existing_output_without_rerun(self):
        oid=FakeOrchestrator().orchestration_id(self.request.resolved())
        store_root=self.root/"runs/_orchestration"/oid;store_root.mkdir(parents=True)
        run=self.root/"runs"/f"{oid}_case_one_base_run_v2";write_valid_base_run(run,self.request,legacy_status="skipped")
        state={"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":"case_one","status":"failed","current_stage":"base_run","error_code":"BASE_RUN_FAILED","error_summary":"base fulltext escalation did not complete","stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":{"review_items":0,"assignments":0,"annotations":0,"gold":0,"metrics":0},"prior_cases":[]}
        input_hash=FakeOrchestrator()._input_hash("base_run",self.request.resolved(),state)
        state["stages"]["base_run"].update(status="failed",attempt=3,input_hash=input_hash,previous_input_hash=input_hash,last_status="failed",output_run=str(run),error_code="BASE_RUN_FAILED")
        (store_root/"orchestration_state.json").write_text(json.dumps(state))
        (store_root/"orchestration_events.jsonl").write_text(json.dumps({"event":"stage_failed","stage":"base_run"})+"\n")
        runner=FakeOrchestrator();runner.run(CaseToAtlasRequest(**{**self.request.__dict__,"stop_after":"base_run"}))
        self.assertEqual(runner.calls,[])
        self.assertFalse((self.root/"runs"/f"{oid}_case_one_base_run_v4").exists())
        new_state=json.loads((store_root/"orchestration_state.json").read_text())
        self.assertEqual(new_state["stages"]["base_run"]["completion_mode"],"recovered_existing_output")
        events=(store_root/"orchestration_events.jsonl").read_text()
        self.assertIn("stage_failed",events);self.assertIn("stage_recovered",events);self.assertIn("stage_reused",events)

    def test_reconciles_interrupted_base_run_v4_without_runner_or_v5(self):
        oid=FakeOrchestrator().orchestration_id(self.request.resolved())
        store_root=self.root/"runs/_orchestration"/oid;store_root.mkdir(parents=True)
        valid=self.root/"runs"/f"{oid}_case_one_base_run_v2";write_valid_base_run(valid,self.request,legacy_status="skipped")
        interrupted=self.root/"runs"/f"{oid}_case_one_base_run_v4";(interrupted/"artifacts").mkdir(parents=True)
        (interrupted/"run_state.json").write_text(json.dumps({"query":"A affects B","final_status":"running","steps":{"abstract_l1":{"status":"running"}}}))
        state={"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":"case_one","status":"running","current_stage":"base_run","completed_at":"2026-01-01T00:00:00+00:00","stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":{"review_items":0,"assignments":0,"annotations":0,"gold":0,"metrics":0},"prior_cases":[]}
        input_hash=FakeOrchestrator()._input_hash("base_run",self.request.resolved(),state)
        state["stages"]["base_run"].update(status="running",attempt=4,input_hash=input_hash,previous_input_hash=input_hash,last_status="completed",output_run=str(interrupted),completed_at="2026-01-01T00:00:00+00:00",completion_mode="recovered_existing_output")
        (store_root/"orchestration_state.json").write_text(json.dumps(state))
        (store_root/"orchestration_events.jsonl").write_text(json.dumps({"event":"stage_started","stage":"base_run","attempt":4,"output_run":str(interrupted)})+"\n")
        runner=ArtifactOrchestrator()
        result=runner.run(CaseToAtlasRequest(**{**self.request.__dict__,"reuse_only":True,"stop_after":"base_run"}))
        self.assertEqual(runner.calls,[])
        new_state=json.loads((store_root/"orchestration_state.json").read_text())
        self.assertEqual(new_state["stages"]["base_run"]["status"],"completed")
        self.assertEqual(new_state["stages"]["base_run"]["output_run"],str(valid))
        self.assertTrue((interrupted/"run_state.json").is_file())
        self.assertFalse((self.root/"runs"/f"{oid}_case_one_base_run_v5").exists())
        self.assertIn(str(interrupted),result.abandoned_outputs)
        events=(store_root/"orchestration_events.jsonl").read_text()
        self.assertIn("reuse_fallthrough_output_abandoned",events)

    def test_invalid_mixed_state_fails_closed(self):
        oid=FakeOrchestrator().orchestration_id(self.request.resolved())
        store_root=self.root/"runs/_orchestration"/oid;store_root.mkdir(parents=True)
        state={"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":"case_one","status":"running","current_stage":"pmcid_repair","stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":{"review_items":0,"assignments":0,"annotations":0,"gold":0,"metrics":0},"prior_cases":[]}
        state["stages"]["pmcid_repair"].update(status="running",attempt=2,completion_mode="recovered_existing_output",completed_at="2026-01-01T00:00:00+00:00")
        (store_root/"orchestration_state.json").write_text(json.dumps(state))
        with self.assertRaises(OrchestrationError) as caught:
            FakeOrchestrator().run(CaseToAtlasRequest(**{**self.request.__dict__,"reuse_only":True}))
        self.assertEqual(caught.exception.code,"ORCHESTRATION_STATE_INVARIANT_VIOLATION")

    def test_force_base_stage_still_reruns(self):
        oid=FakeOrchestrator().orchestration_id(self.request.resolved())
        store_root=self.root/"runs/_orchestration"/oid;store_root.mkdir(parents=True)
        run=self.root/"runs"/f"{oid}_case_one_base_run_v2";write_valid_base_run(run,self.request,legacy_status="skipped")
        state={"schema_version":"case_to_atlas_orchestration_v1","orchestration_id":oid,"case_id":"case_one","status":"failed","current_stage":"base_run","stages":{name:{"status":"pending","attempt":0} for name in STAGES},"safety_baseline":{"review_items":0,"assignments":0,"annotations":0,"gold":0,"metrics":0},"prior_cases":[]}
        input_hash=FakeOrchestrator()._input_hash("base_run",self.request.resolved(),state)
        state["stages"]["base_run"].update(status="failed",attempt=3,input_hash=input_hash,previous_input_hash=input_hash,last_status="failed",output_run=str(run))
        (store_root/"orchestration_state.json").write_text(json.dumps(state))
        runner=FakeOrchestrator();runner.run(CaseToAtlasRequest(**{**self.request.__dict__,"force_stages":frozenset({"base_run"}),"stop_after":"base_run"}))
        self.assertEqual(runner.calls,["base_run"])

    def test_sync_failure_does_not_repeat_system_a(self):
        failing=FakeOrchestrator("atlas_sync")
        with self.assertRaises(OrchestrationError):failing.run(self.request)
        resumed=FakeOrchestrator();resumed.run(self.request);self.assertEqual(resumed.calls,["atlas_sync","verification"])

    def test_handoff_failure_stops_before_sync(self):
        failing=FakeOrchestrator("handoff")
        with self.assertRaises(OrchestrationError):failing.run(self.request)
        self.assertNotIn("atlas_sync",failing.calls)

    def test_state_atomic_and_events_append_only(self):
        FakeOrchestrator().run(self.request);oid=FakeOrchestrator().orchestration_id(self.request.resolved());root=self.root/"runs/_orchestration"/oid
        self.assertTrue((root/"orchestration_state.json").is_file());self.assertFalse(list(root.glob("*.tmp")))
        before=(root/"orchestration_events.jsonl").read_text();FakeOrchestrator().run(self.request);after=(root/"orchestration_events.jsonl").read_text();self.assertTrue(after.startswith(before));self.assertGreater(len(after),len(before))

    def test_stop_after(self):
        request=CaseToAtlasRequest(**{**self.request.__dict__,"stop_after":"fulltext_l1"});runner=FakeOrchestrator();result=runner.run(request);self.assertEqual(runner.calls,list(STAGES[:3]));self.assertEqual(result.status,"stopped")

    def test_cli_missing_case_exit_code(self):
        self.assertEqual(cli_main(["--case-id","absent","--case-profile",str(self.root/"x"),"--search-plan-file",str(self.root/"y"),"--json"]),2)


if __name__=="__main__":unittest.main()
