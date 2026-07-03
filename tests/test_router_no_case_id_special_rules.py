import json
import tempfile
import unittest
from pathlib import Path

from code_engine.validation.case_routing import CaseDomainProfile, route_case_validators


class RouterGeneralizationTests(unittest.TestCase):
    def test_same_tags_route_same_regardless_of_case_id(self):
        base = {"query": "compound target disease", "case_type": "conflict_enriched", "domain_tags": ["pathway_mechanism"], "entity_types": ["gene"], "validation_needs": ["pathway_membership", "gene_set_enrichment"]}
        decisions = []
        for case_id in ("alpha", "beta"):
            profile = CaseDomainProfile(case_id=case_id, **base)
            decisions.append(route_case_validators(profile)["recommended_but_unavailable"])
        self.assertEqual(decisions[0], decisions[1])
        self.assertIn("reactome", decisions[0])
        self.assertIn("enrichr", decisions[0])


if __name__ == "__main__":
    unittest.main()
