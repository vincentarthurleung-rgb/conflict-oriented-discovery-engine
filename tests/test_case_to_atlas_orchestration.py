from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from code_engine.cli.run_case_to_atlas import main as cli_main
from code_engine.orchestration.case_to_atlas import CaseToAtlasOrchestrator, OrchestrationError
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

    def test_force_stage_invalidates_downstream_only(self):
        FakeOrchestrator().run(self.request);forced=CaseToAtlasRequest(**{**self.request.__dict__,"force_stages":frozenset({"reentry"})});runner=FakeOrchestrator();runner.run(forced)
        self.assertEqual(runner.calls,list(STAGES[3:]))

    def test_search_plan_change_invalidates_everything(self):
        FakeOrchestrator().run(self.request);payload=json.loads(self.plan.read_text());payload["paper_year_to"]=2021;self.plan.write_text(json.dumps(payload));runner=FakeOrchestrator();runner.run(self.request)
        self.assertEqual(runner.calls,list(STAGES))

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
