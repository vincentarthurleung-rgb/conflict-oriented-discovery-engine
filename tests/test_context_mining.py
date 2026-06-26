import json
import unittest

from src.pipelines.context_mining import mine_context_mentions


class ContextMiningTests(unittest.TestCase):
    def test_context_mining_requires_span_in_sentence(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "l1_5"
            input_dir.mkdir()
            payload = {
                "asset_id": "P1",
                "chunks_extracted": [
                    {
                        "chunk_index": 0,
                        "raw_samples": [
                            {
                                "causal_tuples": [
                                    {
                                        "subject": "ketamine",
                                        "object": "BDNF",
                                        "relation_sign": 1,
                                        "evidence_sentence": "Acute ketamine increased BDNF in mouse neurons.",
                                        "context": {"species": "mouse", "time": "not in sentence"},
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
            (input_dir / "P1_refined.json").write_text(json.dumps(payload), encoding="utf-8")
            mentions, audit = mine_context_mentions(str(input_dir), "missing_axis_map.json")
            values = {(m["axis"], m["value"]) for m in mentions}
            self.assertIn(("species", "mouse"), values)
            self.assertIn(("treatment_duration", "acute"), values)
            self.assertEqual(audit["rejected_missing_span"], 1)

    def test_hypoxia_normoxia_axis_extraction(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            input_dir = Path(tmp) / "l1_5"
            input_dir.mkdir()
            payload = {
                "asset_id": "P2",
                "chunks_extracted": [
                    {
                        "chunk_index": 0,
                        "raw_samples": [
                            {
                                "causal_tuples": [
                                    {
                                        "subject": "oxygen",
                                        "object": "BDNF",
                                        "relation_sign": -1,
                                        "evidence_sentence": "Hypoxia and normoxia produced different responses.",
                                        "context": {},
                                    }
                                ]
                            }
                        ],
                    }
                ],
            }
            (input_dir / "P2_refined.json").write_text(json.dumps(payload), encoding="utf-8")
            mentions, _ = mine_context_mentions(str(input_dir), "missing_axis_map.json")
            values = {(m["axis"], m["value"]) for m in mentions}
            self.assertIn(("oxygen_condition", "hypoxia"), values)
            self.assertIn(("oxygen_condition", "normoxia"), values)


if __name__ == "__main__":
    unittest.main()
