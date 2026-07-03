import unittest

from code_engine.system_b.kg.kg_frontend import frontend_assets


class KGFrontendAssetTests(unittest.TestCase):
    def test_cytoscape_static_assets_exist(self):
        assets = frontend_assets(); self.assertTrue(all(path.is_file() for path in assets))
        html = assets[0].read_text(encoding="utf-8"); js = assets[1].read_text(encoding="utf-8")
        self.assertIn("cytoscape", html.lower()); self.assertIn("/api/entity/search", js)
        self.assertIn("/api/triple/search", js); self.assertIn("/api/path", js)


if __name__ == "__main__": unittest.main()
