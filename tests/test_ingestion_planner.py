import unittest

from src.query.models import CoverageReport
from src.query.parser import parse_research_query
from src.query.planner import plan_incremental_ingestion


class IngestionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.query = parse_research_query("ketamine -> BDNF")
        self.coverage = CoverageReport(
            query_id=self.query.query_id,
            normalized_subject="KETAMINE",
            normalized_object="BDNF",
            verdict="Partial_Coverage_Delta_Update_Recommended",
        )
        self.inventory = {
            "papers": [
                {
                    "paper_id": "p1",
                    "title": "Ketamine BDNF",
                    "stage1_payload_available": True,
                    "l1_extracted": False,
                    "l1_5_refined": False,
                    "chunk_count": 4,
                }
            ],
            "duplicate_groups": [],
        }

    def test_dry_run_and_search_queries(self):
        plan = plan_incremental_ingestion(
            self.query, self.coverage, inventory=self.inventory, write_outputs=False
        )
        self.assertTrue(plan.dry_run)
        self.assertEqual(plan.estimated_api_calls, 4)
        self.assertIn("KETAMINE BDNF", plan.search_queries)

    def test_budget_over_limit(self):
        plan = plan_incremental_ingestion(
            self.query,
            self.coverage,
            budget={"max_api_calls": 2},
            inventory=self.inventory,
            write_outputs=False,
        )
        self.assertEqual(plan.budget_status, "over_budget")


if __name__ == "__main__":
    unittest.main()
