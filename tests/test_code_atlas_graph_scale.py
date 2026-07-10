import json
import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import write_jsonl


class AtlasGraphScaleTests(unittest.TestCase):
    def test_overview_keeps_case_quota_under_edge_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entities = []
            triples = []
            evidence = []
            case_triples = []
            for case_index in range(3):
                case_id = f"case_{case_index}"
                for i in range(8):
                    s = f"e{case_index}_{i}_s"
                    o = f"e{case_index}_{i}_o"
                    entities.extend([
                        {"entity_id": s, "display_label": s, "label": s, "entity_type": "gene", "degree": 1, "evidence_count": 1, "display_priority_score": 1, "source_case_ids": [case_id]},
                        {"entity_id": o, "display_label": o, "label": o, "entity_type": "biological_process", "degree": 1, "evidence_count": 1, "display_priority_score": 1, "source_case_ids": [case_id]},
                    ])
                    tid = f"t{case_index}_{i}"
                    triples.append({"triple_id": tid, "subject_id": s, "subject_display_label": s, "relation_normalized": "promotes", "object_id": o, "object_display_label": o, "evidence_count": 1, "fulltext_evidence_count": 1, "case_ids": [case_id], "display_priority_score_v2": 100 - i})
                    evidence.append({"triple_id": tid, "case_id": case_id, "evidence_sentence": f"{s} promotes {o}."})
                    case_triples.append({"case_id": case_id, "triple_id": tid, "subject_label": s, "relation_normalized": "promotes", "object_label": o, "case_display_rank": i})
            for name, rows in (
                ("display_entities_v2.jsonl", entities),
                ("display_triples_v2.jsonl", triples),
                ("case_focused_triples.jsonl", case_triples),
                ("triple_evidence_links.jsonl", evidence),
            ):
                write_jsonl(root / name, rows)
            write_jsonl(root / "display_chains_v2.jsonl", [])
            write_jsonl(root / "case_focused_chains.jsonl", [])
            write_jsonl(root / "validator_annotations.jsonl", [])
            write_jsonl(root / "conflict_lens_records.jsonl", [])
            data = ExplorerAPI(root, root / "missing").dispatch("/api/graph/overview", {"limit_nodes": ["60"], "limit_edges": ["9"]})[1]
            visible_cases = {case for edge in data["edges"] for case in edge["case_ids"]}
            self.assertEqual(visible_cases, {"case_0", "case_1", "case_2"})
            self.assertLessEqual(len(data["edges"]), 9)


if __name__ == "__main__":
    unittest.main()
