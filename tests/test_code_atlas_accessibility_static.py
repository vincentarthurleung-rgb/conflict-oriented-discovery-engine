import unittest
from pathlib import Path

STATIC=Path("src/code_engine/system_b/explorer/static")


class AtlasAccessibilityStaticTests(unittest.TestCase):
    def test_focus_labels_aria_live_and_graph_list_alternative(self):
        html=(STATIC/"index.html").read_text(encoding="utf-8")
        js=(STATIC/"app.js").read_text(encoding="utf-8")
        css=(STATIC/"style.css").read_text(encoding="utf-8")+(STATIC/"design_tokens.css").read_text(encoding="utf-8")
        self.assertIn("aria-label=\"Global search\"",html)
        self.assertIn(":focus-visible",css)
        self.assertIn("aria-live",js)
        self.assertIn("graph-list-alt",js)
        self.assertIn("列表替代视图",js)
        self.assertIn("cell-label",js)
        self.assertIn("data-diff",js)


if __name__=="__main__":
    unittest.main()
