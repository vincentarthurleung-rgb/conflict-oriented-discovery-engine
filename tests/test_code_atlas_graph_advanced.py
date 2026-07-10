import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


class AtlasGraphAdvancedTests(unittest.TestCase):
    def test_graph_advanced_ui_hooks_exist(self):
        js=Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
        for text in ("Compare Mode","renderGraphCompare","Story Mode","saveGraphStory","graph-list-alt","Minimap"):
            self.assertIn(text,js)

    def test_graph_nodes_are_display_entities_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            data=ExplorerAPI(root,root/"missing").dispatch("/api/graph/overview",{"limit_nodes":["20"],"limit_edges":["20"]})[1]
            self.assertTrue(all(x["node_kind"]=="display_entity" for x in data["nodes"]))
            labels={x["label"].casefold() for x in data["nodes"]}
            self.assertNotIn("reactome",labels)
            self.assertNotIn("a promotes b.",labels)


if __name__=="__main__":
    unittest.main()
