import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests

class AtlasGlobalGraphTests(unittest.TestCase):
    def test_overview_limits_display_entity_nodes_and_downranks_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing-review")
            status,data=api.dispatch("/api/graph/overview",{"limit_nodes":["1"],"limit_edges":["10"]})
            self.assertEqual(status,200);self.assertLessEqual(len(data["nodes"]),1);self.assertLessEqual(len(data["edges"]),10)
            self.assertTrue(all(x["node_kind"]=="display_entity" for x in data["nodes"]))
            labels={x["label"].lower() for x in data["nodes"]}
            self.assertNotIn("reactome",labels);self.assertNotIn("pmc8027606",labels);self.assertNotIn("a promotes b.",labels)
            filters=api.dispatch("/api/graph/filters")[1];self.assertIn("case",filters["cases"]);self.assertIn("gene",filters["entity_types"])

    def test_neighborhood_respects_depth_and_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing-review")
            data=api.dispatch("/api/graph/neighborhood/e1",{"depth":["1"],"limit":["2"]})[1]
            self.assertEqual(data["center"],"e1");self.assertLessEqual(len(data["nodes"]),2);self.assertLessEqual(data["summary"]["depth"],1)

    def test_default_ui_projection_is_case_overview(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing-review")
            status,data=api.dispatch("/api/graph/case-overview")
            self.assertEqual(status,200)
            self.assertEqual(data["projection"],"case_overview")
            self.assertEqual(data["summary"]["case_count"],1)
            self.assertEqual(data["items"][0]["case_id"],"case")
            self.assertIn("top_relations",data["items"][0])

    def test_path_uses_existing_display_chains(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing-review")
            data=api.dispatch("/api/graph/path",{"source":["A"],"target":["B"],"max_depth":["2"]})[1]
            self.assertEqual(data["total"],1);self.assertEqual(data["items"][0]["chain_id"],"c1");self.assertEqual(data["items"][0]["triple_ids"],["t1"])

if __name__=="__main__":unittest.main()
