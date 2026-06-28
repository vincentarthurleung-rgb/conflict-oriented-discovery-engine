import unittest

from code_engine.graph.abstract_conflict_screening import build_abstract_conflict_candidates


def claim(cid,paper,direction,family="drug_target"):
    return {"claim_id":cid,"paper_id":paper,"source_scope":"abstract","subject_raw":"drug","object_raw":"target","relation_family":family,"polarity_type":"mechanistic","direction":direction}

def obs(cid,status="resolved"):
    return {"claim_id":cid,"observation_id":"O"+cid,"subject_canonical_id":"CHEM:D","object_canonical_id":"GENE:T","subject_canonical_name":"drug","object_canonical_name":"target","normalization_status":status,"allow_high_confidence_graph_use":status=="resolved"}


class AbstractConflictScreeningTests(unittest.TestCase):
    def test_entropy_grouping_dedup_and_exclusions(self):
        claims=[claim("1","P1","inhibit"),claim("1b","P1","inhibit"),claim("2","P2","activate"),claim("3","P3","activate"),claim("4","P4","unknown"),claim("5","P5","inhibit")]
        observations=[obs(item) for item in ("1","1b","2","3","4")]+[obs("5","unresolved")]
        result=build_abstract_conflict_candidates(claims,observations,min_evidence_count=3,min_entropy=.5)
        candidate=result["candidates"][0]
        self.assertEqual(candidate["paper_count"],3)
        self.assertGreater(candidate["abstract_entropy"],.5)
        self.assertEqual(result["summary"]["unknown_direction_count"],1)
        self.assertEqual(result["summary"]["excluded_counts"]["low_confidence_or_unresolved_l2"],1)
        self.assertEqual(len(result["focus_set"]),1)

    def test_relation_family_is_separate(self):
        claims=[claim("1","P1","inhibit"),claim("2","P2","activate","clinical_outcome")]
        result=build_abstract_conflict_candidates(claims,[obs("1"),obs("2")],min_evidence_count=1,min_entropy=0)
        self.assertEqual(len(result["candidates"]),2)


if __name__ == "__main__": unittest.main()
