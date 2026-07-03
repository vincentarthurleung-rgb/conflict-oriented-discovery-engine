import unittest

from code_engine.graph.fulltext_conflict_confirmation import confirm_conflicts_with_fulltext_evidence
from code_engine.fulltext.conflict_confirmation import confirm_fulltext_conflicts


def candidate(cid="C1"):
    return {"candidate_id":cid,"abstract_entropy":1.0,"fulltext_available_paper_count":2,"fulltext_unavailable_paper_count":0}

def evidence(eid,direction,context=None):
    return {"evidence_id":eid,"paper_id":"P"+eid,"source_scope":"full_text","direction":direction,"context_slots":context or {},"linked_conflict_candidate_ids":["C1"]}


class FulltextConflictConfirmationTests(unittest.TestCase):
    def test_confirmation_statuses(self):
        confirmed=confirm_conflicts_with_fulltext_evidence([candidate()],[evidence("1","activate"),evidence("2","inhibit")],[],2)
        self.assertEqual(confirmed["confirmations"][0]["confirmation_status"],"confirmed_conflict")
        contextual=confirm_conflicts_with_fulltext_evidence([candidate()],[evidence("1","activate",{"species":"mouse"}),evidence("2","inhibit",{"species":"human"})],[],2)
        self.assertEqual(contextual["confirmations"][0]["confirmation_status"],"context_resolved_conflict")
        false_signal=confirm_conflicts_with_fulltext_evidence([candidate()],[evidence("1","activate"),evidence("2","activate")],[],2)
        self.assertEqual(false_signal["confirmations"][0]["confirmation_status"],"false_conflict_due_to_abstract_loss")
        insufficient=confirm_conflicts_with_fulltext_evidence([candidate()],[],[],2)
        item=insufficient["confirmations"][0]
        self.assertEqual(item["confirmation_status"],"insufficient_fulltext_coverage")
        self.assertIn("no_fulltext_evidence_not_a_contradiction",item["warnings"])

    def test_oa_unavailable_is_not_refutation_and_opposing_claims_support(self):
        candidates=[{"candidate_id":"c","paper_ids":["p1","p2"]}]
        unavailable=confirm_fulltext_conflicts(candidates,[],[{"paper_id":"p1","full_text_status":"unavailable"}])
        self.assertEqual(unavailable["confirmations"][0]["full_text_confirmation_status"],"full_text_unavailable")
        self.assertFalse(unavailable["confirmations"][0]["no_oa_is_negative_evidence"])
        claims=[{"claim_id":"a","polarity":"positive","linked_conflict_candidate_ids":["c"]},{"claim_id":"b","polarity":"negative","linked_conflict_candidate_ids":["c"]}]
        self.assertEqual(confirm_fulltext_conflicts(candidates,claims,[])["confirmations"][0]["full_text_confirmation_status"],"full_text_supported")


if __name__ == "__main__": unittest.main()
