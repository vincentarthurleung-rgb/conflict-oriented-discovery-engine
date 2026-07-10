import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests


class AtlasGlobalSearchTests(unittest.TestCase):
    def test_search_groups_cases_dossiers_entities_papers_and_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            api=ExplorerAPI(root,root/"missing")
            _,data=api.dispatch("/api/search",{"q":["A"]})
            self.assertIn("cases",data);self.assertIn("dossiers",data);self.assertIn("entities",data);self.assertIn("papers",data);self.assertIn("paths",data)
            self.assertTrue(data["dossiers"])
            self.assertTrue(data["entities"])

    def test_empty_search_is_grouped_empty_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);KnowledgeExplorerTests().fixture(root)
            data=ExplorerAPI(root,root/"missing").dispatch("/api/search",{"q":[""]})[1]
            self.assertEqual(set(data),{"cases","dossiers","entities","papers","paths"})


if __name__=="__main__":
    unittest.main()
