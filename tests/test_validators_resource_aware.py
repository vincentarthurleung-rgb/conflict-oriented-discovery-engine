import unittest
from pathlib import Path

from code_engine.schemas.validation import ValidationExecutionContext, ValidationQueryPlan, ValidationQuestion
from code_engine.validation.registry import ValidatorRegistry


class FailingProvider:
    def stream(self, plan): raise RuntimeError("provider failed")


class ResourceAwareValidatorTests(unittest.TestCase):
    def test_missing_indexes_are_structured(self):
        registry=ValidatorRegistry().register_defaults()
        cases=(
            ("ChEMBLValidator","drug_target_binding","drug_target_binding","binding_activity_check"),
            ("BindingDBValidator","drug_target_binding","drug_target_binding","binding_activity_check"),
            ("DrugBankValidator","drug_target_binding","drug_target_binding","binding_activity_check"),
            ("GEOValidator","neuropharmacology","drug_gene_expression","expression_direction_check"),
            ("ReactomeValidator","pathway_biology","pathway_mechanism","pathway_membership_check"),
            ("STRINGValidator","protein_interaction","protein_interaction","protein_interaction_check"),
        )
        for name,domain,relation,intent in cases:
            question=ValidationQuestion(question_id="Q",domain_id=domain,relation_type=relation,validator_intent=intent,entities=[{"canonical_id":"X"}])
            self.assertEqual(registry.validate(name,question).validation_status,"external_index_not_configured")

    def test_fake_local_index_streams_and_remote_is_not_implicit(self):
        fixture=Path(__file__).parent/"fixtures/validation_indexes/chembl"
        plan=ValidationQueryPlan(query_plan_id="P",anchor_id="A",validator_name="ChEMBLValidator",query_type="binding_activity_check",query_entities=[{"canonical_id":"CHEM:SIROLIMUS"},{"canonical_id":"GENE:MTOR"}],execution_mode="local_index",index_name="chembl",query_context={"index_path":str(fixture/"records.jsonl"),"index_type":"jsonl","schema_path":str(fixture/"schema.json"),"manifest_path":str(fixture/"manifest.json")},status="allowed",max_records=5)
        validator=ValidatorRegistry().register_defaults().create("ChEMBLValidator")
        self.assertEqual(len(list(validator.stream_evidence(plan,ValidationExecutionContext()))),1)
        remote=plan.model_copy(update={"execution_mode":"remote_api"})
        self.assertEqual(list(validator.stream_evidence(remote,ValidationExecutionContext(network_enabled=False))),[])


if __name__ == "__main__": unittest.main()
