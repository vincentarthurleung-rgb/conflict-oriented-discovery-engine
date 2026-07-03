import unittest
from pathlib import Path


class DashboardDefaultViewTests(unittest.TestCase):
    def test_default_page_uses_placeholder_not_raw_graph(self):
        root = Path("src/code_engine/system_b/dashboard/static")
        html = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "app.js").read_text(encoding="utf-8")
        self.assertIn("Select a case, search an entity, or open KG overview.", html)
        self.assertNotIn("renderTables(registry,comparison,validators,recommendations);await overview()", script)
        self.assertIn("detail='summary'", script)
        self.assertIn("Debug graph may be visually cluttered.", html)
        self.assertIn("label:''", script)


if __name__ == "__main__": unittest.main()
