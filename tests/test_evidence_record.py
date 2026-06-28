import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from code_engine.schemas.evidence import EvidenceRecord, build_minimal_evidence_record


FIXTURE = json.loads((Path(__file__).parent / "fixtures/v42_minimal.json").read_text())


class EvidenceRecordTests(unittest.TestCase):
    def test_grounded_record(self):
        record = EvidenceRecord.model_validate(FIXTURE["evidence"])
        self.assertEqual(record.claim_role, "supports_edge")

    def test_ungrounded_high_confidence_is_rejected(self):
        with self.assertRaises(ValidationError):
            EvidenceRecord(evidence_id="e", paper_id="p", confidence=0.9)

    def test_legacy_sentence_builds_minimal_record(self):
        record = build_minimal_evidence_record({"source_asset": "p", "evidence_sentence": "A activates B."})
        self.assertEqual(record.quote, "A activates B.")


if __name__ == "__main__": unittest.main()
