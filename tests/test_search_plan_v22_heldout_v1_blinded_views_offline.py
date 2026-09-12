"""Independent blinding, identity, anomaly and deterministic-generation checks."""
from collections import Counter
import copy
import json
import re
import unittest
from unittest.mock import patch

from tools import build_search_plan_v22_heldout_v1_blinded_views_offline as m


class BlindedViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = m.generate()
        cls.packets = m.readl(m.SOURCE / 'frozen_neutral_review_packets.jsonl')

    def test_frozen_roots_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'root mismatch'):
            m.root_check(m.SOURCE, 'heldout_v1_review_corpus_sha256', '0' * 64)
        original = m.sha
        with patch.object(m, 'sha', side_effect=lambda p: '0' * 64 if p.name == 'review_batch_assignment.jsonl' else original(p)):
            with self.assertRaisesRegex(RuntimeError, 'component mismatch'):
                m.generate()

    def test_sensitive_fields_cannot_flow_to_renderer(self):
        p = copy.deepcopy(self.packets[0])
        for field in ['tier', 'metadata_depth', 'pre_acquisition_gate_states', 'adjudication',
                      'query_family_variant_provenance', 'acquisition_quality_prediction']:
            p[field] = 'SENSITIVE_SENTINEL'
        p['publication_identity']['pmcid'] = 'OA_SENTINEL'
        p['deterministic_fulltext_excerpts'] = [{'text': 'FULLTEXT_SENTINEL'}]
        for phase, fields in [('a', m.A_FIELDS), ('b', m.B_FIELDS)]:
            view = m.projection(p, phase)
            text = m.render_packet(view, fields)
            self.assertNotIn('SENSITIVE_SENTINEL', text)
            self.assertEqual('FULLTEXT_SENTINEL' in text, phase == 'b')
            self.assertEqual('OA_SENTINEL' in text, phase == 'b')
            self.assertEqual(view['scientific_target'], p['scientific_target'])
            if phase == 'b':
                self.assertNotIn('retrieval_target', view)
                self.assertNotIn('acquisition_decision:', text)

    def test_exact_membership_order_and_blank_forms(self):
        for phase, kind, fields in [('a', 'acquisition', m.A_FIELDS), ('b', 'relevance', m.B_FIELDS)]:
            all_ids = []
            for n in range(1, 6):
                md = self.out[f'heldout_{kind}_blind_batch_{n:02d}.md'].decode()
                parts = m.sections(md)
                original = m.sections((m.SOURCE / f'heldout_review_batch_{n:02d}.md').read_text())
                self.assertEqual([pid for pid, _ in parts], [pid for pid, _ in original])
                self.assertEqual(len(parts), 14)
                all_ids += [pid for pid, _ in parts]
                for _, body in parts:
                    self.assertEqual(body.rsplit('\nADJUDICATION\n', 1)[1].strip().splitlines(), [f'{f}:' for f in fields])
                    self.assertFalse(re.search(r'^(Tier|Metadata depth|Why acquired|Known plausible fields):', body, re.M))
            self.assertEqual(Counter(all_ids), Counter(p['packet_id'] for p in self.packets))
            blank = [json.loads(line) for line in self.out[f'blank_{kind}_adjudications_all.jsonl'].splitlines()]
            self.assertEqual(len(blank), 70)
            self.assertTrue(all(row[f] is None for row in blank for f in fields))

    def test_frozen_evidence_is_exact(self):
        for phase in ['a', 'b']:
            rows = [json.loads(line) for line in self.out[f'pass_{phase}_packet_manifest.jsonl'].splitlines()]
            for source, row in zip(self.packets, rows):
                v = row['visible_fields']
                self.assertEqual(v['abstract'], source['abstract'])
                self.assertEqual(v['scientific_target'], source['scientific_target'])
                if phase == 'b':
                    self.assertEqual(v['deterministic_fulltext_excerpts'], source['deterministic_fulltext_excerpts'])
                    self.assertEqual(v['fields_expected_to_resolve'], source['fields_expected_to_resolve'])

    def test_anomalies_explain_source_and_rendering(self):
        audit = json.loads(self.out['renderer_provenance_anomaly_audit.json'])
        self.assertEqual(audit['anomaly_counts'], {'duplicate_depth_rendering': 32,
            'missing_depth_rendering': 32, 'repeated_query_family_variant': 5})
        for row in audit['anomalies']:
            self.assertFalse(row['scientific_sample_identity_affected'])
            self.assertTrue(row['source_field_paths'])
            if row['anomaly_type'] == 'repeated_query_family_variant':
                self.assertTrue(row['canonical_source_affected'])
                self.assertTrue(row['upstream_provenance_affected'])
                self.assertEqual(row['duplicate_full_provenance_records'], 0)
            else:
                self.assertFalse(row['canonical_source_affected'])

    def test_aggregate_covers_all_derived_views_and_policy(self):
        freeze = json.loads(self.out['freeze_manifest.json'])
        pairs = [(c['path'], m.digest(self.out[c['path']])) for c in freeze['components']]
        self.assertEqual(m.digest(m.canonical(pairs)), freeze['heldout_v1_blinded_adjudication_views_sha256'])
        self.assertEqual(sum(name.endswith('.md') for name, _ in pairs), 10)
        self.assertIn('blinded_field_policy.json', dict(pairs))
        policy = json.loads(self.out['blinded_field_policy.json'])
        self.assertTrue(policy['fresh_evaluator_sessions_required'])
        self.assertFalse(policy['current_conversation_eligible_as_strictly_blinded_evaluator'])
        self.assertEqual(policy['expected_reviewer_type'], 'model_retrieval_adjudicator')
        self.assertEqual(len(policy['later_import_must_verify']), 3)

    def test_offline_replay_and_historical_integrity(self):
        before = m.protected_state()
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            replay = m.generate()
        self.assertEqual(self.out, replay)
        self.assertEqual(before, m.protected_state())
        summary = json.loads(replay['summary.json'])
        for key in m.ZERO:
            self.assertEqual(summary[key], 0)
        self.assertFalse(summary['heldout_metrics_calculated'])


if __name__ == '__main__':
    unittest.main()
