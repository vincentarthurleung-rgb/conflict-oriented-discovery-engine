import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from code_engine.acquisition.manifest import load_artifact_inventory
from code_engine.extraction.llm_cache import load_llm_cache_index
from code_engine.graph.knowledge_store import load_knowledge_store
from code_engine.query.answer import assemble_query_answer
from code_engine.query.coverage import analyze_coverage
from code_engine.query.cli import main as query_main
from code_engine.query.parser import parse_research_query
from code_engine.query.planner import plan_incremental_ingestion


class CleanWorkspaceTests(unittest.TestCase):
    def test_missing_runtime_loaders_return_explicit_empty_states_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = load_artifact_inventory(repository_root=root)
            store = load_knowledge_store(repository_root=root)
            cache = load_llm_cache_index(root / "data/index/llm_cache_index.json")

            self.assertEqual(inventory["papers"], [])
            self.assertEqual(inventory["runtime_data_status"], "missing_empty_inventory")
            self.assertEqual(store["triples"], [])
            self.assertEqual(store["knowledge_store_status"], "missing_empty_store")
            self.assertEqual(cache["entries"], {})
            self.assertEqual(cache["cache_status"], "missing_empty_cache")
            self.assertFalse((root / "data/index").exists())

    def test_empty_workspace_query_is_insufficient_and_reports_runtime_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            query = parse_research_query("ketamine -> BDNF")
            coverage = analyze_coverage(query, repository_root=root, write_outputs=True)
            plan = plan_incremental_ingestion(
                query, coverage, repository_root=root, write_outputs=False
            )
            answer = assemble_query_answer(
                query, coverage, plan, repository_root=root, write_outputs=True
            )

            self.assertEqual(coverage.verdict, "Insufficient_Run_New_Corpus_Search")
            self.assertEqual(coverage.runtime_data_status, "missing_empty_inventory")
            self.assertEqual(coverage.knowledge_store_status, "missing_empty_store")
            self.assertFalse(coverage.using_legacy_data)
            self.assertEqual(coverage.available_layers, [])
            self.assertEqual(plan.runtime_data_status, "missing_empty_inventory")
            self.assertFalse(answer.using_legacy_data)

            payload = json.loads(
                (root / f"data/query/coverage_{query.query_id}.json").read_text(encoding="utf-8")
            )
            self.assertEqual(payload["knowledge_store_status"], "missing_empty_store")
            self.assertFalse(payload["using_legacy_data"])

    def test_legacy_sources_require_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_store = root / "quarantine/old/data/index/knowledge_store.json"
            legacy_store.parent.mkdir(parents=True)
            legacy_store.write_text(json.dumps({"triples": [], "pairs": {}}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_knowledge_store(legacy_store)
            loaded = load_knowledge_store(legacy_store, allow_legacy_source=True)
            self.assertTrue(loaded["using_legacy_data"])

            legacy_cache = root / "artifacts/legacy/llm_cache_index.json"
            legacy_cache.parent.mkdir(parents=True)
            legacy_cache.write_text(json.dumps({"entries": {}}), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_llm_cache_index(legacy_cache)

    def test_query_cli_marks_explicit_legacy_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "quarantine/legacy_run"
            graph_path = legacy / "data/processed/l3/integrated_shannon_graph.json"
            graph_path.parent.mkdir(parents=True)
            graph_path.write_text(
                json.dumps([
                    {
                        "subject": "KETAMINE",
                        "object": "BDNF",
                        "whitebox_traceability": [
                            {"triple_id": "legacy-t1", "relation_sign": 1}
                        ],
                    }
                ]),
                encoding="utf-8",
            )
            output = io.StringIO()
            with redirect_stdout(output):
                result = query_main([
                    "--query", "ketamine -> BDNF",
                    "--mode", "coverage",
                    "--repository-root", str(root),
                    "--legacy-source", str(legacy),
                ])
            self.assertEqual(result, 0)
            self.assertTrue(json.loads(output.getvalue())["using_legacy_data"])


if __name__ == "__main__":
    unittest.main()
