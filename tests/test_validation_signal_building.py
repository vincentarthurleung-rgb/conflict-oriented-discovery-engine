import unittest

from code_engine.schemas.validation import ExternalEvidenceRecord, ValidationExecutionContext
from code_engine.validation.registry import ValidatorRegistry


def evidence(validator,source,signal_direction="increase",expected="increase"):
    return ExternalEvidenceRecord(evidence_id="E",validator_name=validator,source_database=source,query_plan_id="P",anchor_id="A",evidence_type="test",direction=signal_direction,score=.9,context={"expected_direction":expected})


class ValidationSignalBuildingTests(unittest.TestCase):
    def setUp(self): self.registry=ValidatorRegistry().register_defaults(); self.context=ValidationExecutionContext()

    def signal(self,name,item): return next(self.registry.create(name).build_signals([item],self.context))

    def test_domain_signal_semantics(self):
        self.assertEqual(self.signal("GEOValidator",evidence("GEOValidator","GEO")).signal_type,"expression_support")
        self.assertEqual(self.signal("GEOValidator",evidence("GEOValidator","GEO","decrease")).signal_type,"expression_contradiction")
        self.assertEqual(self.signal("ChEMBLValidator",evidence("ChEMBLValidator","ChEMBL")).signal_type,"binding_support")
        self.assertIsNone(self.signal("BindingDBValidator",evidence("BindingDBValidator","BindingDB")).supports_hypothesis)
        self.assertEqual(self.signal("ReactomeValidator",evidence("ReactomeValidator","Reactome")).signal_type,"pathway_membership_support")
        self.assertEqual(self.signal("STRINGValidator",evidence("STRINGValidator","STRING")).signal_type,"protein_interaction_support")
        clinical=self.signal("ClinicalTrialsValidator",evidence("ClinicalTrialsValidator","ClinicalTrials"))
        self.assertEqual(clinical.signal_type,"trial_existence_signal"); self.assertIsNone(clinical.supports_hypothesis)
        depmap=self.signal("DepMapValidator",evidence("DepMapValidator","DepMap"))
        self.assertEqual(depmap.signal_type,"cancer_dependency_context")


if __name__ == "__main__": unittest.main()
