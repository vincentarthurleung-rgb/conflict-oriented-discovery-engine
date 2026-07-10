import unittest
from pathlib import Path


class AtlasLibraryMinimalTests(unittest.TestCase):
    def test_library_stores_minimal_reference_schema(self):
        js = Path("src/code_engine/system_b/explorer/static/app.js").read_text(encoding="utf-8")
        fn = js.split("function normalizeLibraryItem", 1)[1].split("function saveLibraryItem", 1)[0]
        for text in ("object_type", "stable_id", "display_title", "view_params", "saved_at"):
            self.assertIn(text, fn)
        for forbidden in ("source_file", "source_line", "raw JSON", "csrf_token", "password"):
            self.assertNotIn(forbidden, fn)


if __name__ == "__main__":
    unittest.main()
