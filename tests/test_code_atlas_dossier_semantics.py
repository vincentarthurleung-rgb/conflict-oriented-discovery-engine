import tempfile
import unittest
from pathlib import Path

from code_engine.system_b.explorer.dossier_projection import dossier_id_for, legacy_dossier_id_for
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from tests.test_system_b_knowledge_explorer import KnowledgeExplorerTests, write_jsonl


class AtlasDossierSemanticsTests(unittest.TestCase):
    def test_dossier_id_uses_unambiguous_payload_and_legacy_alias(self):
        triple = {"subject_id": "a|b", "relation_normalized": "promotes", "object_id": "c"}
        other = {"subject_id": "a", "relation_normalized": "b|promotes", "object_id": "c"}
        self.assertNotEqual(dossier_id_for(triple), dossier_id_for(other))
        self.assertEqual(len(dossier_id_for(triple)), len("dos_") + 20)
        self.assertEqual(len(legacy_dossier_id_for(triple)), len("dos_") + 16)

    def test_direction_and_relation_are_not_overmerged_and_audit_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            KnowledgeExplorerTests().fixture(root)
            triples = [
                {"triple_id": "t1", "subject_id": "e1", "subject_display_label": "A", "relation_normalized": "promotes", "object_id": "e2", "object_display_label": "B", "direction": "positive", "evidence_count": 1, "fulltext_evidence_count": 1, "case_ids": ["case"], "display_priority_score_v2": .9},
                {"triple_id": "t2", "subject_id": "e1", "subject_display_label": "A", "relation_normalized": "promotes", "object_id": "e2", "object_display_label": "B", "direction": "negative", "evidence_count": 1, "fulltext_evidence_count": 0, "case_ids": ["case"], "display_priority_score_v2": .8},
                {"triple_id": "t3", "subject_id": "e1", "subject_display_label": "A", "relation_normalized": "associated_with", "object_id": "e2", "object_display_label": "B", "evidence_count": 1, "fulltext_evidence_count": 0, "case_ids": ["case"], "display_priority_score_v2": .7},
            ]
            write_jsonl(root / "display_triples_v2.jsonl", triples)
            write_jsonl(root / "triple_evidence_links.jsonl", [
                {"triple_id": "t1", "case_id": "case", "source_scope": "fulltext", "evidence_sentence": "A promotes B."},
                {"triple_id": "t2", "case_id": "case", "source_scope": "abstract", "evidence_sentence": "A suppresses B."},
                {"triple_id": "t3", "case_id": "case", "source_scope": "abstract", "evidence_sentence": "A is associated with B."},
            ])
            api = ExplorerAPI(root, root / "missing")
            self.assertNotEqual(api.dossiers.resolve("t1"), api.dossiers.resolve("t2"))
            self.assertNotEqual(api.dossiers.resolve("t1"), api.dossiers.resolve("t3"))
            audit = api.dispatch("/api/dossiers/audit")[1]
            self.assertEqual(audit["dossier_count"], 3)
            self.assertIn("possible_fragmentation_count", audit)


if __name__ == "__main__":
    unittest.main()
