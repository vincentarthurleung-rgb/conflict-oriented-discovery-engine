import json
import tempfile
import unittest
from pathlib import Path

from code_engine.acquisition.literature_search import execute_acquisition_plan
from code_engine.query.intent import parse_research_intent
from code_engine.query.search_planner import build_literature_search_plan


class FakeLiteratureClient:
    def __init__(self): self.calls = 0
    def search(self, query, source, max_results, year_from=None, year_to=None):
        self.calls += 1
        return [{"paper_id": "PMC1", "pmcid": "PMC1", "title": "Existing"}, {"paper_id": "PMC2", "pmcid": "PMC2", "title": "New"}]
    def fetch(self, record, source):
        self.calls += 1
        return f"<article><p>{record['title']}</p></article>"


class DynamicStage0AcquisitionTests(unittest.TestCase):
    def test_no_network_makes_zero_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = FakeLiteratureClient()
            plan = build_literature_search_plan(parse_research_intent("ketamine depression"))
            report = execute_acquisition_plan(plan, repository_root=tmp, execute=True, network=False, client=client)
            self.assertEqual(client.calls, 0)
            self.assertEqual(report["network_calls_made"], 0)

    def test_execute_deduplicates_manifest_and_writes_new_raw(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "data/metadata/global_manifest.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"papers": {"PMC1": {"pmcid": "PMC1", "title": "Existing"}}}), encoding="utf-8")
            client = FakeLiteratureClient()
            plan = build_literature_search_plan(parse_research_intent("ketamine depression"))
            plan.pmc_queries = [plan.pubmed_queries[0].model_copy(update={"source": "pmc"})]
            plan.pubmed_queries = []
            report = execute_acquisition_plan(plan, repository_root=root, execute=True, network=True, source="pmc", client=client)
            self.assertEqual([item["paper_id"] for item in report["reused_papers"]], ["PMC1"])
            self.assertTrue((root / "data/raw/xml/PMC2.xml").exists())
            saved = json.loads(manifest.read_text())
            self.assertIn("PMC2", saved["papers"])


if __name__ == "__main__": unittest.main()
