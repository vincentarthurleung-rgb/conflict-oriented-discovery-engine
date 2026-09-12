"""PASS A import checks: no labels are adjudicated or grouped by outcome."""
import copy
import json
import unittest
from unittest.mock import patch
from tools import freeze_search_plan_v22_heldout_v1_pass_a_offline as m


class PassAFreezeTests(unittest.TestCase):
    def setUp(self):
        self.rows = m.parse_submission(m.INPUT.read_bytes())
        self.ids = [r['packet_id'] for r in m.readl(m.SOURCE / 'frozen_neutral_review_packets.jsonl')]

    def test_verbatim_parsing_and_order(self):
        rows = m.validate_records(self.rows, self.ids)
        self.assertEqual([r['packet_id'] for r in rows], self.ids)
        self.assertEqual({r['packet_id']: r for r in rows}, {r['packet_id']: r for r in self.rows})
        sample = b'packet_id: id\nacquisition_decision: JUSTIFIED\nrationale:  Unchanged: punctuation  \nconfidence: high\nreviewer_type: model_retrieval_adjudicator\n'
        self.assertEqual(m.parse_submission(sample)[0]['rationale'], ' Unchanged: punctuation  ')

    def test_reject_incomplete_unknown_and_duplicate_fields(self):
        for raw in [b'packet_id: id\n', b'unknown: x\n', b'packet_id: id\npacket_id: id\n']:
            with self.assertRaises(RuntimeError):
                m.parse_submission(raw)

    def test_reject_missing_extra_duplicate_ids(self):
        for rows in [self.rows[:-1], self.rows + [self.rows[0]], self.rows[:-1] + [self.rows[0]]]:
            with self.assertRaises(RuntimeError):
                m.validate_records(rows, self.ids)
        rows = copy.deepcopy(self.rows)
        rows[0]['packet_id'] = 'not-in-frozen-set'
        with self.assertRaises(RuntimeError):
            m.validate_records(rows, self.ids)

    def test_reject_invalid_labels_confidence_reviewer_without_repair(self):
        for field, value in [('confidence', 'HIGH'), ('confidence', 0.9),
                             ('acquisition_decision', 'JUSTIFIED '), ('reviewer_type', 'human'), ('rationale', '')]:
            rows = copy.deepcopy(self.rows)
            rows[0][field] = value
            with self.assertRaises(RuntimeError):
                m.validate_records(rows, self.ids)
            self.assertEqual(rows[0][field], value)

    def test_root_mismatch_stops_before_parsing(self):
        with patch.object(m, 'root_check', side_effect=RuntimeError('root mismatch')):
            with patch.object(m, 'parse_submission') as parser:
                with self.assertRaises(RuntimeError):
                    m.generate()
                parser.assert_not_called()

    def test_offline_replay_corpus_hash_and_artifact_integrity(self):
        before = m.protected()
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            first, second = m.generate(), m.generate()
        self.assertEqual(first, second)
        self.assertEqual(before, m.protected())
        actual = [json.loads(x) for x in first['pass_a_acquisition_adjudications.jsonl'].splitlines()]
        self.assertEqual(actual, m.validate_records(self.rows, self.ids))
        freeze = json.loads(first['freeze_manifest.json'])
        self.assertEqual(freeze['heldout_v1_pass_a_acquisition_adjudications_sha256'],
                         m.digest(first['pass_a_acquisition_adjudications.jsonl']))
        self.assertEqual(len(freeze['future_import_required_hashes']), 4)
        validation = json.loads(first['validation.json'])
        self.assertTrue(all(validation['checks'].values()))
        for name, expected in validation['artifact_hashes'].items():
            self.assertEqual(m.digest(first[name]), expected)
        summary = json.loads(first['summary.json'])
        for key in m.ZERO:
            self.assertEqual(summary[key], 0)
        self.assertFalse(summary['heldout_metrics_calculated'])
        self.assertFalse(summary['decision_distribution_reported'])


if __name__ == '__main__':
    unittest.main()
