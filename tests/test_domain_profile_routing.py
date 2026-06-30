import unittest

from code_engine.query.intent import parse_research_intent


class DomainProfileRoutingTests(unittest.TestCase):
    def test_query_terms_do_not_implicitly_select_pilot_domain(self):
        intent = parse_research_intent("我想了解当前氯胺酮在抑郁症中的作用")
        self.assertEqual(intent.domain_id, "general_biomedical")

    def test_receptor_blockade_routes_to_binding(self):
        intent = parse_research_intent("ketamine 是否通过 NMDA receptor blockade 发挥作用")
        self.assertEqual(intent.domain_id, "drug_target_binding")
        self.assertEqual(intent.subdomain_id, "receptor_modulation")

    def test_clinical_esketamine_routes_to_clinical_outcome(self):
        intent = parse_research_intent("esketamine 对 treatment-resistant depression 的临床疗效")
        self.assertEqual(intent.domain_id, "clinical_outcome")
        self.assertEqual(intent.validator_profile_id, "clinical_outcome_validation")

    def test_unknown_query_uses_general_profile(self):
        intent = parse_research_intent("请整理这个尚未定义的问题")
        self.assertEqual(intent.domain_id, "general_biomedical")


if __name__ == "__main__":
    unittest.main()
