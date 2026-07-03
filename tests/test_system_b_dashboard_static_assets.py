import unittest
from pathlib import Path


class DashboardStaticAssetTests(unittest.TestCase):
    def test_frontend_assets_and_dependencies(self):
        root = Path("src/code_engine/system_b/dashboard/static")
        html, js, css = (root / name for name in ("index.html", "app.js", "style.css"))
        self.assertTrue(all(path.is_file() for path in (html, js, css)))
        markup = html.read_text(encoding="utf-8")
        self.assertIn("/app.js", markup); self.assertIn("/style.css", markup)
        self.assertIn("cytoscape", markup.lower())
        script = js.read_text(encoding="utf-8")
        for endpoint in ("/api/dashboard/summary", "/api/dashboard/cases", "/api/triple/search", "/api/path"):
            self.assertIn(endpoint, script)


if __name__ == "__main__": unittest.main()
