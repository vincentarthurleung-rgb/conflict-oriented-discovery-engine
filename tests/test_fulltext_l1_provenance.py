import unittest
from code_engine.fulltext.l1_extraction import extract_fulltext_claims
class L1ProvenanceTests(unittest.TestCase):
 def test_claim_has_separate_scope_and_provenance(self):
  paper={"pmid":"1","pmcid":"PMC1","abstract_observation_ids":["o1"]}; article={"sections":[{"section_title":"Results","text":"A increases B."}]}
  claims=extract_fulltext_claims(paper,article,extractor=lambda text,ctx:[{"relation":"increases","polarity":"positive","evidence_sentence":text}])
  self.assertEqual(claims[0]["source_scope"],"full_text"); self.assertTrue(claims[0]["chunk_hash"]); self.assertEqual(claims[0]["pmcid"],"PMC1")
