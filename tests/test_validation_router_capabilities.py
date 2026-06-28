import unittest

from code_engine.schemas.validation import ValidationQuestion
from code_engine.validation.registry import ValidatorRegistry
from code_engine.validation.router import route_validation_questions


class ValidationRouterCapabilityTests(unittest.TestCase):
    def test_capability_routes_and_null_fallback(self):
        registry=ValidatorRegistry().register_defaults()
        expected={
            "expression_direction_check":{"CuratedOmicsValidator","GEOValidator","LINCSValidator"},
            "cancer_dependency_check":{"DepMapValidator","LINCSValidator","OpenTargetsValidator"},
            "binding_activity_check":{"ChEMBLValidator","BindingDBValidator","DrugBankValidator"},
            "pathway_membership_check":{"ReactomeValidator"},
            "protein_interaction_check":{"STRINGValidator","UniProtValidator"},
            "clinical_context_check":{"ClinicalTrialsValidator","PubMedClinicalEvidenceValidator","OpenTargetsValidator"},
        }
        for index,(intent,names) in enumerate(expected.items()):
            q=ValidationQuestion(question_id=f"Q{index}",anchor_id=f"A{index}",validator_intent=intent,entities=[{"canonical_id":"X","entity_type":"gene"}])
            routed={item.validator_name for item in route_validation_questions([q],registry,max_validators_per_question=6)}
            self.assertTrue(names.issubset(routed),intent)
        unknown=ValidationQuestion(question_id="QX",anchor_id="AX",validator_intent="unknown_intent",entities=[{"canonical_id":"X"}])
        self.assertEqual(route_validation_questions([unknown],registry)[0].validator_name,"NullValidator")


if __name__ == "__main__": unittest.main()
