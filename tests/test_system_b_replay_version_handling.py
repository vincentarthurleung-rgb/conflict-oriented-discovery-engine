import unittest
from code_engine.system_b.batch_ingest import SystemBBatchIngestor
class SystemBReplayVersionTests(unittest.TestCase):
 def test_registry_row_preserves_replay_relationship(self):
  bundle={"manifest":{"is_replay":True,"source_case_version":"v1_zero_claim","replay_from_stage":"l2","source_run":"source"}}
  card={"case_id":"x","case_role":"conflict_enriched","pipeline_status":{"pipeline_complete":True},"evidence_summary":{"core_observation_count":0,"true_graph_conflict_count":0,"formal_hypothesis_count":0,"manual_review_followup_count":0},"validation_summary":{"executed_validators":[],"unavailable_validators":[],"external_validation_status":"skipped","lincs_interpretation":"unavailable","overall_validation_score":None},"fulltext_summary":{"status":"skipped"}}
  quality={"quality_class":"Q","comparison_readiness":"R","system_b_use":"version comparison"};validation={"ready_for_system_b":False,"warnings":[]}
  row=SystemBBatchIngestor._registry_row(bundle,card,quality,validation,"p",PathLike(),"o","l","v2_replay_l2");self.assertTrue(row["is_replay"]);self.assertEqual("v1_zero_claim",row["source_case_version"])
class PathLike:
 def __truediv__(self,other):return str(other)
if __name__=="__main__":unittest.main()
