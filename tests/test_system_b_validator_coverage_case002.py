import unittest
from code_engine.system_b.batch_ingest import SystemBBatchIngestor
class SystemBCoverageTests(unittest.TestCase):
 def test_executed_skipped_and_unavailable(self):
  row=SystemBBatchIngestor._validator_row({"case_id":"fixture","executed_validators":["reactome"],"skipped_validators":["enrichr"],"unavailable_validators":["chembl"],"selected_validators":[]})
  self.assertEqual("executed",row["reactome"]);self.assertEqual("skipped",row["enrichr"]);self.assertEqual("recommended_unavailable",row["chembl"])
if __name__=="__main__":unittest.main()
