import unittest

from code_engine.domain.router import default_domain_router
from code_engine.validation.router import DomainAdaptiveValidationRouter


class DomainAdaptiveValidationRouterTests(unittest.TestCase):
    def route(self, domain, relation):
        profile = default_domain_router().resolve(domain)
        return DomainAdaptiveValidationRouter().create_plan(
            {"hypothesis_id": "H1", "seed_pair": "ketamine -> BDNF"},
            profile,
            relation_type=relation,
        ).selected_validators

    def test_relation_routes(self):
        self.assertEqual(self.route("neuropharmacology", "drug_gene_expression")[:2], ["CuratedOmicsValidator", "GEOValidator"])
        self.assertEqual(self.route("drug_target_binding", "drug_target_binding"), ["ChEMBLValidator", "DrugBankValidator", "BindingDBValidator"])
        self.assertEqual(self.route("pathway_biology", "pathway_mechanism"), ["ReactomeValidator", "PathwayValidator"])
        self.assertEqual(self.route("clinical_outcome", "clinical_outcome"), ["ClinicalTrialsValidator", "PubMedClinicalEvidenceValidator"])
        self.assertEqual(self.route("general_biomedical", "unsupported"), ["NullValidator"])


if __name__ == "__main__":
    unittest.main()
