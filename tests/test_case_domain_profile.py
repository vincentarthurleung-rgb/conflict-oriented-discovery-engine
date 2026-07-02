import unittest

from code_engine.validation.case_routing import CaseDomainProfile


class CaseDomainProfileTests(unittest.TestCase):
    def test_backward_compatible_domain_profile_mapping(self):
        value = CaseDomainProfile.from_domain_profile(
            {"domain_id": "pathway_biology", "key_entity_types": ["pathway"]},
            case_id="generic_case", query="generic pathway question",
        )
        self.assertEqual(value.validation_needs, ["pathway_membership"])
        self.assertEqual(value.case_type, "pathway_biology")


if __name__ == "__main__":
    unittest.main()
