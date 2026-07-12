from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from code_engine.integration.atlas_handoff import HandoffError, publish_atlas_handoff, validate_handoff
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

    def test_single_manifest_sync_preserves_current_cases(self):
        publish_atlas_handoff(self.run,runs_root=self.root);output=Path(self.tmp.name)/"out"
        sync_system_a(runs_root=self.root,output_root=output,no_database_write=True)
        second=self.root/"run-two";shutil.copytree(self.run,second);(second/"artifacts/atlas_handoff_manifest.json").unlink();(second/"artifacts/ATLAS_READY").unlink()
        source=json.loads((second/"fulltext_reentry_manifest.json").read_text());source["case_id"]="case-two";(second/"fulltext_reentry_manifest.json").write_text(json.dumps(source))
        published=publish_atlas_handoff(second,runs_root=self.root)
        report=sync_system_a(runs_root=self.root,manifest=published["manifest_path"],output_root=output,no_database_write=True)
        self.assertEqual(report["status"],"completed");self.assertEqual(ExplorerAPI(output).summary()["cases"],2)


if __name__ == "__main__": unittest.main()
