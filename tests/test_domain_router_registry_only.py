import unittest

from code_engine.domain.router import default_domain_router


class DomainRouterRegistryTests(unittest.TestCase):
    def test_registry_operations(self):
        router = default_domain_router()
        self.assertEqual(router.get_or_default("neuropharmacology").domain_id, "neuropharmacology")
        self.assertEqual(router.get_or_default("invalid").domain_id, "general_biomedical")
        self.assertTrue(router.validate_domain_id("clinical_outcome"))
        self.assertIn("general_biomedical", {item["domain_id"] for item in router.profile_summaries()})

    def test_primary_resolution_does_not_classify_text(self):
        self.assertIsNone(default_domain_router().resolve("ketamine depression"))


if __name__ == "__main__": unittest.main()
