import json
import unittest

from src.schemas import ScientificTriple, validate_json_list


class SchemaTests(unittest.TestCase):
    def test_scientific_triple_schema_accepts_directional_sign(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "triples.json"
            payload = [
                {
                    "triple_id": "t1",
                    "paper_id": "p1",
                    "chunk_id": "c1",
                    "source": "llm",
                    "relation_sign": 1,
                    "target": "BDNF",
                    "evidence_sentence": "Ketamine increases BDNF.",
                }
            ]
            path.write_text(json.dumps(payload), encoding="utf-8")
            records = validate_json_list(path, ScientificTriple)
            self.assertEqual(records[0].target, "BDNF")


if __name__ == "__main__":
    unittest.main()
