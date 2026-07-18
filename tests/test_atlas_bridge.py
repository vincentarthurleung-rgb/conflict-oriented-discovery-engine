from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from code_engine.integration.atlas_handoff import ABSTRACT_L2_PROFILE, HandoffError, publish_atlas_handoff, validate_handoff
from code_engine.system_b.adapters.fulltext_reentry_v5 import FulltextReentryV5Adapter
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.system_a_sync import sync_system_a


class AtlasBridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name) / "runs"; self.run = self.root / "run-one"; artifacts = self.run / "artifacts"; artifacts.mkdir(parents=True)
        base = {"claim_id":"c1","evidence_lane":"seed_neighborhood_mechanism","subject":"A","predicate":"activates","object":"B","relation_class":"causal_regulation","seed_distance":"direct","exploratory_graph_eligible":True,"conflict_eligible":False,"polarity_resolution_status":"resolved","evidence_sentence":"A activates B.","pmid":"1","context":{"species":"human"},"core_gate_passed":False,"core_gate_failures":[],"claim_identity_hash":"x","duplicate_match_basis":[],"dedup_action":"preserve"}
        lanes={"fulltext_core_seed_observations.jsonl":[],"fulltext_seed_neighborhood_observations.jsonl":[base],"fulltext_reviewable_relations.jsonl":[],"fulltext_off_seed_relations.jsonl":[]}
        for name,rows in lanes.items():(artifacts/name).write_text("".join(json.dumps(x)+"\n" for x in rows))
        (artifacts/"l35_fulltext_l1_claims.jsonl").write_text(json.dumps(base)+"\n")
        (artifacts/"fulltext_reentry_audit.jsonl").write_text(json.dumps(base)+"\n")
        self.source={"schema_version":"fulltext_reentry_replay_manifest_v1","case_id":"case-one","status":"completed","network_used":False,"api_used":False,"created_at":"2026-01-01T00:00:00+00:00","input_fulltext_claim_count":1,"core_seed_relation_count":0,"seed_neighborhood_mechanism_count":1,"reviewable_context_relation_count":0,"off_seed_relation_count":0,"exploratory_graph_eligible_count":1,"conflict_eligible_count":0}
        (self.run/"fulltext_reentry_manifest.json").write_text(json.dumps(self.source))

    def tearDown(self): self.tmp.cleanup()

    def test_atomic_publish_validate_and_noop(self):
        before=hashlib.sha256((self.run/"artifacts/l35_fulltext_l1_claims.jsonl").read_bytes()).hexdigest()
        first=publish_atlas_handoff(self.run,runs_root=self.root);second=publish_atlas_handoff(self.run,runs_root=self.root)
        self.assertEqual(first["status"],"published");self.assertEqual(second["status"],"no_op")
        self.assertEqual(before,hashlib.sha256((self.run/"artifacts/l35_fulltext_l1_claims.jsonl").read_bytes()).hexdigest())
        validated=validate_handoff(first["manifest_path"],runs_root=self.root);self.assertEqual(validated["manifest"]["counts"]["input_fulltext_claim_count"],1)
        marker=json.loads((self.run/"artifacts/ATLAS_READY").read_text());self.assertEqual(marker["manifest_sha256"],validated["manifest_hash"])

    def test_incomplete_missing_and_accounting_rejected(self):
        self.source["status"]="partial";(self.run/"fulltext_reentry_manifest.json").write_text(json.dumps(self.source))
        with self.assertRaises(HandoffError):publish_atlas_handoff(self.run,runs_root=self.root)
        self.source["status"]="completed";(self.run/"fulltext_reentry_manifest.json").write_text(json.dumps(self.source));(self.run/"artifacts/fulltext_off_seed_relations.jsonl").unlink()
        with self.assertRaises(HandoffError):publish_atlas_handoff(self.run,runs_root=self.root)

    def test_path_and_hash_validation(self):
        published=publish_atlas_handoff(self.run,runs_root=self.root);path=Path(published["manifest_path"]);manifest=json.loads(path.read_text());manifest["artifacts"]["input_fulltext_claims"]["relative_path"]="../secret";path.write_text(json.dumps(manifest))
        with self.assertRaises(HandoffError):validate_handoff(path,runs_root=self.root)
        publish_atlas_handoff(self.run,runs_root=self.root);(self.run/"artifacts/l35_fulltext_l1_claims.jsonl").write_text("{}\n")
        with self.assertRaises(HandoffError):validate_handoff(path,runs_root=self.root)

    def test_adapter_separates_views_and_missing_context(self):
        published=publish_atlas_handoff(self.run,runs_root=self.root);validated=validate_handoff(published["manifest_path"],runs_root=self.root)
        projected=FulltextReentryV5Adapter().project(validated,prediction_run_id="pred")
        self.assertEqual(len(projected["dossier_evidence"]),1);self.assertEqual(len(projected["exploratory_triples"]),1);self.assertEqual(projected["conflict_predictions"],[])
        self.assertIsNone(projected["context_rows"][0]["dose"]);self.assertTrue(all(x.get("entity_type")!="evidence" for x in projected["display"]["display_entities_v2"]))

    def test_sync_registry_and_explorer_reload_source(self):
        publish_atlas_handoff(self.run,runs_root=self.root);output=Path(self.tmp.name)/"out"
        report=sync_system_a(runs_root=self.root,output_root=output,no_database_write=True)
        self.assertEqual(report["status"],"completed");api=ExplorerAPI(output);self.assertEqual(api.summary()["cases"],1);self.assertEqual(api.dossiers.list({})["total"],1)
        active=api.dispatch("/api/active-projections")[1]
        self.assertEqual(active["items"][0]["case_id"],"case-one")
        self.assertEqual(active["items"][0]["active_projection_id"],report["current_projection_id"])
        second=sync_system_a(runs_root=self.root,output_root=output,no_database_write=True)
        self.assertEqual(second["status"],"no_op")
        self.assertEqual(second["atlas_activation_status"],"active")

    def test_single_manifest_sync_preserves_current_cases(self):
        publish_atlas_handoff(self.run,runs_root=self.root);output=Path(self.tmp.name)/"out"
        sync_system_a(runs_root=self.root,output_root=output,no_database_write=True)
        second=self.root/"run-two";shutil.copytree(self.run,second);(second/"artifacts/atlas_handoff_manifest.json").unlink();(second/"artifacts/ATLAS_READY").unlink()
        source=json.loads((second/"fulltext_reentry_manifest.json").read_text());source["case_id"]="case-two";(second/"fulltext_reentry_manifest.json").write_text(json.dumps(source))
        published=publish_atlas_handoff(second,runs_root=self.root)
        report=sync_system_a(runs_root=self.root,manifest=published["manifest_path"],output_root=output,no_database_write=True)
        self.assertEqual(report["status"],"completed");self.assertEqual(ExplorerAPI(output).summary()["cases"],2)


class AbstractL2AtlasBridgeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/"runs";self.run=self.root/"abstract-run";artifacts=self.run/"artifacts";artifacts.mkdir(parents=True)
        row={
            "schema_version":"l2_core_graph_observation_v1","observation_id":"obs-1","claim_id":"claim-1",
            "subject":"TP53","subject_canonical_id":"gene:TP53","subject_canonical_name":"TP53","subject_entity_type":"gene",
            "formal_relation":"inhibits","relation_family":"causal_regulation",
            "object":"apoptosis","object_canonical_id":"process:apoptosis","object_canonical_name":"apoptosis","object_entity_type":"process",
            "direction":"negative","formal_core_graph_eligible":True,"graph_observation_eligible":True,"conflict_eligible":False,
            "evidence_sentence":"TP53 inhibits apoptosis in this abstract fixture.","pmid":"123","context":{"species":"human"},
        }
        json_files={
            "case_domain_profile.json":{"schema_version":"case_domain_profile_v1","case_id":"abstract-case"},
            "search_plan.json":{"schema_version":"search_plan_v1","query":"tp53 apoptosis"},
            "replay_manifest.json":{"schema_version":"replay_manifest_v1","case_id":"abstract-case","scientific_status":"completed","final_status":"completed","created_at":"2026-01-01T00:00:00+00:00","entity_network_lookup_enabled":True,"entity_llm_cleaner_calls_made":0},
            "replay_terminal_state_audit.json":{"schema_version":"replay_terminal_state_audit_v1","final_status":"completed","completed_at":"2026-01-01T00:00:00+00:00"},
            "l2_abstract_summary.json":{"schema_version":"l2_abstract_summary_v1","retained_observations":1},
            "graph_conflict_summary.json":{"schema_version":"graph_conflict_summary_v1","true_graph_conflict_count":0},
            "hypothesis_summary.json":{"schema_version":"hypothesis_summary_v1","formal_hypothesis_count":0},
            "l2_abstract_observations.json":[row],
        }
        jsonl_files={
            "abstract_l1_claims.jsonl":[{"schema_version":"abstract_l1_claim_v1","claim_id":"claim-1","pmid":"123","claim_text":"TP53 inhibits apoptosis."}],
            "l2_core_graph_observations.jsonl":[row],
            "l2_graph_observations.jsonl":[row],
            "core_graph_gate_audit.jsonl":[{"schema_version":"core_graph_gate_audit_v1","observation_id":"obs-1","eligible":True,"reason":"eligible_and_emitted"}],
            "merged_evidence_graph_edges.jsonl":[{"schema_version":"merged_evidence_graph_edge_v1","edge_id":"edge-1"}],
            "merged_evidence_graph_nodes.jsonl":[{"schema_version":"merged_evidence_graph_node_v1","node_id":"gene:TP53"}],
            "graph_conflict_candidates.jsonl":[],
        }
        for name,value in json_files.items():
            (artifacts/name).write_text(json.dumps(value,sort_keys=True))
        for name,rows in jsonl_files.items():
            (artifacts/name).write_text("".join(json.dumps(row,sort_keys=True)+"\n" for row in rows))

    def tearDown(self): self.tmp.cleanup()

    def test_abstract_l2_publish_validate_sync_and_noop(self):
        published=publish_atlas_handoff(self.run,runs_root=self.root,handoff_profile=ABSTRACT_L2_PROFILE)
        manifest=published["manifest"]
        self.assertEqual(manifest["handoff_profile"],ABSTRACT_L2_PROFILE)
        self.assertEqual(manifest["compatibility"]["evidence_scope"],"abstract_only")
        self.assertEqual(manifest["scientific_summary"]["formal_core_observation_count"],1)
        validated=validate_handoff(published["manifest_path"],runs_root=self.root)
        self.assertEqual(validated["manifest"]["content_hash"],manifest["content_hash"])
        output=Path(self.tmp.name)/"out"
        report=sync_system_a(runs_root=self.root,manifest=published["manifest_path"],output_root=output,no_database_write=True)
        self.assertEqual(report["status"],"completed")
        active=ExplorerAPI(output).dispatch("/api/active-projections")[1]["items"][0]
        self.assertEqual(active["handoff_profile"],ABSTRACT_L2_PROFILE)
        self.assertEqual(active["evidence_scope"],"abstract_only")
        case=ExplorerAPI(output).dispatch("/api/cases")[1]["items"][0]
        self.assertEqual(case["handoff_profile"],ABSTRACT_L2_PROFILE)
        self.assertEqual(case["evidence_scope"],"abstract_only")
        second=sync_system_a(runs_root=self.root,manifest=published["manifest_path"],output_root=output,no_database_write=True)
        self.assertEqual(second["status"],"no_op")
        self.assertEqual(second["current_projection_id"],report["current_projection_id"])

    def test_abstract_l2_missing_required_and_hash_mismatch_rejected(self):
        (self.run/"artifacts/l2_core_graph_observations.jsonl").unlink()
        with self.assertRaises(HandoffError):
            publish_atlas_handoff(self.run,runs_root=self.root,handoff_profile=ABSTRACT_L2_PROFILE)
        (self.run/"artifacts/l2_core_graph_observations.jsonl").write_text(json.dumps({"observation_id":"obs-1"})+"\n")
        published=publish_atlas_handoff(self.run,runs_root=self.root,handoff_profile=ABSTRACT_L2_PROFILE)
        (self.run/"artifacts/l2_core_graph_observations.jsonl").write_text(json.dumps({"observation_id":"changed"})+"\n")
        with self.assertRaises(HandoffError):
            validate_handoff(published["manifest_path"],runs_root=self.root)


if __name__ == "__main__": unittest.main()
