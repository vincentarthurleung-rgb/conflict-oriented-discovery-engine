"""Exact merge, order, root, replay, and metrics-embargo checks."""
import copy
import json
import unittest
from unittest.mock import patch
from tools import freeze_search_plan_v22_heldout_v1_primary_results_offline as m

class PrimaryResultsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.p=m.readl(m.CORPUS/'frozen_neutral_review_packets.jsonl')
  cls.a=m.readl(m.PASS_A/'pass_a_acquisition_adjudications.jsonl')
  cls.b=m.readl(m.PASS_B/'pass_b_relevance_adjudications.jsonl')

 def test_identity_is_fail_closed(self):
  self.assertTrue(m.identities(self.p,self.a,self.b)['pass_a_packet_identity_bijection'])
  for a,b in [(self.a[:-1],self.b),(self.a+[self.a[0]],self.b),(self.a,self.b[:-1]+[self.b[0]])]:
   with self.assertRaises(RuntimeError): m.identities(self.p,a,b)

 def test_record_preserves_each_input(self):
  r=m.merge_record(self.p[0],self.a[0],self.b[0])
  self.assertEqual(r['frozen_gate_states'],self.p[0]['pre_acquisition_gate_states'])
  self.assertEqual(r['scientific_target'],self.p[0]['scientific_target'])
  self.assertEqual(r['retrieval_target'],self.p[0]['retrieval_target'])
  self.assertEqual(r['pass_a'],{k:self.a[0][k] for k in m.A_FIELDS})
  self.assertEqual(r['pass_b'],{k:self.b[0][k] for k in m.B_FIELDS})

 def test_root_failure_precedes_merge_reads(self):
  with patch.object(m,'aggregate_root',side_effect=RuntimeError('root mismatch')):
   with patch.object(m,'readl') as reader:
    with self.assertRaises(RuntimeError): m.generate()
    reader.assert_not_called()

 def test_replay_hash_order_and_metrics_embargo(self):
  before=m.protected()
  with patch('socket.socket',side_effect=AssertionError('network forbidden')):
   first,second=m.generate(),m.generate()
  self.assertEqual(first,second);self.assertEqual(before,m.protected())
  merged=m.readl_bytes(first['heldout_v1_primary_results.jsonl'])
  self.assertEqual([r['packet_id'] for r in merged],[r['packet_id'] for r in self.p])
  freeze=json.loads(first['freeze_manifest.json'])
  self.assertEqual(freeze['heldout_v1_primary_results_sha256'],m.digest(first['heldout_v1_primary_results.jsonl']))
  self.assertEqual(len(freeze['future_metrics_required_hashes']),6)
  summary=json.loads(first['summary.json'])
  self.assertFalse(summary['heldout_metrics_calculated']);self.assertFalse(summary['performance_distribution_reported'])
  self.assertFalse(summary['heuristics_evaluated'])
  self.assertTrue(all(v==0 for k,v in summary.items() if k in m.ZERO_CALLS))
  validation=json.loads(first['validation.json']);self.assertTrue(all(validation['checks'].values()))

 def test_changed_label_is_not_silently_repaired(self):
  changed=copy.deepcopy(self.b[0]);changed['rationale']+=' changed'
  r=m.merge_record(self.p[0],self.a[0],changed)
  self.assertEqual(r['pass_b']['rationale'],changed['rationale'])

if __name__=='__main__': unittest.main()
