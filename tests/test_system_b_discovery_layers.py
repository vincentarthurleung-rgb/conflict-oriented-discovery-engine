import json,tempfile,unittest
from pathlib import Path
from code_engine.system_b.bundle_loader import CaseBundleLoader
from code_engine.system_b.case_card import CaseCardBuilder

class SystemBDiscoveryLayerTests(unittest.TestCase):
 def test_layers_are_loaded_and_labeled_separately(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);manifest={"case_id":"generic","case_type":"conflict_enriched","reviewable_graph_observation_count":1,"weak_conflict_candidate_count":1}
   for name,value in {"case_bundle_manifest.json":manifest,"pipeline_stage_summary.json":{},"validator_selection_report.json":{},"graph_conflict_summary.json":{},"hypothesis_summary.json":{},"l7_external_validation_summary.json":{}}.items():(root/name).write_text(json.dumps(value))
   (root/"l2_reviewable_graph_observations.jsonl").write_text(json.dumps({"observation_id":"R","requires_review":True})+"\n")
   (root/"weak_conflict_candidates.jsonl").write_text(json.dumps({"candidate_id":"W","strict_conflict":False})+"\n")
   loaded=CaseBundleLoader(root).load();card=CaseCardBuilder().build(loaded)
   self.assertEqual(len(card["discovery_layers"]["reviewable_graph_observations"]),1)
   self.assertEqual(len(card["discovery_layers"]["weak_conflict_candidates"]),1)
   self.assertEqual(card["discovery_layers"]["labels"]["weak"],"weak_requires_manual_review")
   self.assertEqual(card["discovery_layers"]["labels"]["low_priority_context"],"hidden_by_default")
