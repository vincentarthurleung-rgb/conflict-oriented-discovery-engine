import unittest
from pathlib import Path


class StageLayerMappingDocsTests(unittest.TestCase):
    def test_mapping_doc_exists_and_mentions_layers(self):
        path = Path("docs/STAGE_LAYER_MAPPING.md")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        for layer in [f"L{i}" for i in range(9)]:
            self.assertIn(layer, text)
        self.assertIn("legacy wrapper", text)


if __name__ == "__main__":
    unittest.main()
