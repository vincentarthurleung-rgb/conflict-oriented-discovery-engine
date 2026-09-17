"""Tests for the offline v2.4-dev proposition-aware architecture freeze."""

import hashlib
import json
import unittest
from unittest.mock import patch

from tools import freeze_search_plan_v24_dev_proposition_aware_retrieval_architecture_offline as freeze


class PropositionAwareArchitectureFreezeTests(unittest.TestCase):
    @staticmethod
    def load(name):
        return json.loads((freeze.RUN / name).read_bytes())

    def test_authoritative_autopsy_root_verifies(self):
        authority = freeze.verify_autopsy_root()
        self.assertEqual(authority["status"], "PASS")
        self.assertEqual(authority["search_plan_v24_primary_failure_autopsy_sha256"], freeze.EXPECTED_AUTOPSY_ROOT)
        self.assertEqual((authority["source_record_count"], authority["source_direct_count"]), (60, 2))

    def test_replay_is_byte_identical_and_offline(self):
        authority = freeze.verify_autopsy_root()
        protected = freeze.protected_state()
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            first = freeze.build_outputs(authority, protected)
            second = freeze.build_outputs(authority, protected)
        self.assertEqual(first, second)
        self.assertEqual(set(first), freeze.REQUIRED_OUTPUTS)
        self.assertEqual(protected, freeze.protected_state())

    def test_proposal_classes_enforce_search_only_boundary(self):
        contract = self.load("search_term_proposal_classification_contract.json")
        self.assertEqual(set(contract["classes"]), set(freeze.PROPOSAL_CLASSES))
        search_only = contract["classes"]["SEARCH_ONLY_EXPANSION"]
        self.assertTrue(search_only["executable_query_use"])
        self.assertFalse(search_only["identity_sensitive_matching"])
        self.assertFalse(search_only["scientific_equivalence_granted"])
        self.assertIn("entity_identity_resolved", contract["search_only_expansion_must_not_set"])

    def test_intents_are_semantics_dependent_and_unit_context_is_separate(self):
        contract = self.load("retrieval_intent_v1_contract.json")
        self.assertEqual(set(contract["intent_types"]), set(freeze.INTENT_TYPES))
        self.assertEqual(contract["intent_instantiation_rule"], "SEMANTICS_DEPENDENT_NOT_ALL_INTENTS_REQUIRED")
        self.assertTrue(contract["biological_unit_context"]["carried_separately_from_subject_and_object_identity"])
        self.assertTrue(contract["fixed_legacy_family_start_forbidden"])

    def test_coverage_is_complete_and_relation_drop_is_explicit(self):
        coverage = self.load("retrieval_plan_coverage_v1_contract.json")
        self.assertEqual(coverage["dimensions"], freeze.DIMENSIONS)
        self.assertEqual(len(coverage["dimensions"]), 11)
        relation = coverage["relation_requirement"]
        self.assertTrue(relation["representation_attempt_mandatory_when_applicable"])
        self.assertTrue(relation["silent_relation_drop_forbidden"])
        self.assertEqual(relation["underrepresented_provenance_marker"], "RELATION_UNDERREPRESENTED")

    def test_search_plan_schema_is_strict_and_has_no_executable_query_field(self):
        schema = self.load("proposition_aware_search_plan_v1_schema.json")
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("request_provenance", schema["required"])
        intent = schema["properties"]["retrieval_intents"]["items"]
        concept = intent["properties"]["search_concepts"]["items"]
        self.assertTrue({"proposal_source", "proposal_class", "authority_reference"} <= set(concept["required"]))
        blueprint = intent["properties"]["candidate_query_blueprints"]["items"]
        self.assertEqual(blueprint["properties"]["executable_query_absent"], {"const": True})
        self.assertNotIn("executable_query", blueprint["properties"])
        self.assertEqual(blueprint["properties"]["dimension_coverage"]["minItems"], 11)

    def test_planner_config_requires_frozen_identity_but_does_not_instantiate_it(self):
        config = self.load("query_planner_config_v1_contract.json")
        required = config["required_frozen_fields"]
        self.assertTrue({"model_identity", "reasoning_setting", "temperature", "prompt_template_version",
                         "schema_version", "max_attempts", "repair_policy"} <= set(required))
        self.assertEqual(config["runtime_configuration_status"], "NOT_INSTANTIATED_IN_ARCHITECTURE_ONLY_RUN")
        self.assertEqual(config["query_budget_values_in_this_run"], "UNSET_PENDING_RETROSPECTIVE_DEVELOPMENT_ANALYSIS")
        self.assertFalse(config["numerical_query_budgets_frozen_in_this_run"])

    def test_compiler_boundary_and_p0_p1_p2_roles_are_nonimplementation(self):
        compiler = self.load("deterministic_query_compiler_requirements.json")
        self.assertEqual(compiler["implementation_status"], "NOT_IMPLEMENTED")
        self.assertIn("Boolean syntax", compiler["compiler_owns"])
        self.assertIn("compile UNRESOLVED or REJECTED terms", compiler["compiler_must_not"])
        modules = self.load("p0_p1_p2_future_role_audit.json")
        self.assertTrue(modules["not_primary_retrieval_generators"])
        self.assertFalse(modules["existing_blocking_semantics_preserved_by_default"])
        self.assertFalse(modules["module_changes_in_this_run"])

    def test_future_validation_excludes_all_seen_case_sets(self):
        boundary = self.load("future_validation_boundary.json")
        self.assertEqual(
            boundary["development_only_corpora"],
            ["heldout-v1", "retired initial heldout-v2", "primary heldout-v2 cases 101-108"],
        )
        self.assertTrue(boundary["future_independent_validation_requires_fresh_cases"])
        self.assertFalse(boundary["fresh_cases_selected_in_this_run"])

    def test_aggregate_root_and_machine_status(self):
        validation = self.load("validation.json")
        self.assertEqual(validation["status"], "PASS")
        self.assertTrue(all(validation["checks"].values()))
        pairs = []
        for name, expected in validation["aggregate_components"]:
            actual = freeze.sha(freeze.RUN / name)
            self.assertEqual(actual, expected)
            pairs.append([name, actual])
        root = hashlib.sha256(freeze.canonical(pairs)).hexdigest()
        self.assertEqual(root, validation["search_plan_v24_proposition_aware_architecture_sha256"])
        summary = self.load("summary.json")
        self.assertEqual(root, summary["search_plan_v24_proposition_aware_architecture_sha256"])
        self.assertFalse(summary["v24_query_planner_implemented"])
        self.assertFalse(summary["v24_query_compiler_implemented"])
        self.assertFalse(summary["v24_retrieval_started"])
        self.assertEqual((summary["network_calls"], summary["provider_calls"], summary["llm_calls"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
