"""Focused tests for the v2.4-dev proposition-aware planner/compiler."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    PROMPT_VERSION,
    PlannerProviderAuthorizationRequired,
    PlannerValidationError,
    PropositionAwareQueryPlannerV1,
    QueryPlannerConfigV1,
    immutable_cache_write,
    planner_cache_key,
    validate_plan,
)
from code_engine.search.query_compiler_v24_dev import (
    DEFAULT_DEVELOPMENT_BUDGETS,
    QueryBudgetConfigDev,
    QueryBudgetExceeded,
    compile_validated_plan,
)
from code_engine.search.retrieval_plan_coverage_v1 import RetrievalCoverageError
from code_engine.search.search_term_validator_v1 import validate_and_classify_plan_terms
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as freeze


class V24DevPlannerCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.targets = freeze.load_jsonl(freeze.TARGETS_PATH)

    def plan(self, index=0):
        return freeze.mock_plan_for_target(deepcopy(self.targets[index]))

    def validated(self, plan):
        return validate_and_classify_plan_terms(plan, authorities={"records": []})

    def compile(self, plan, budgets=DEFAULT_DEVELOPMENT_BUDGETS):
        value = self.validated(plan)
        return compile_validated_plan(value["validated_plan"], value["validation_receipt"], budgets=budgets)

    def test_01_uncached_planner_requires_explicit_provider_authorization(self):
        planner = PropositionAwareQueryPlannerV1()
        with self.assertRaises(PlannerProviderAuthorizationRequired):
            planner.plan(self.targets[0], request_reference="development:test")

    def test_02_planner_cannot_directly_establish_authority(self):
        plan = self.plan()
        llm_term = next(
            term for intent in plan["retrieval_intents"] for concept in intent["search_concepts"]
            for term in concept["proposed_terms"] if term["proposal_source"] == "LLM_PROPOSAL"
        )
        llm_term["proposal_class"] = "AUTHORIZED_EQUIVALENT"
        llm_term["authority_reference"] = "llm:self-asserted"
        result = self.validated(plan)
        classified = next(
            term for intent in result["validated_plan"]["retrieval_intents"] for concept in intent["search_concepts"]
            for term in concept["proposed_terms"] if term["term_id"] == llm_term["term_id"]
        )
        self.assertEqual(classified["proposal_class"], "SEARCH_ONLY_EXPANSION")
        self.assertIsNone(classified["authority_reference"])

    def test_03_search_only_expansion_never_changes_canonical_identity(self):
        plan = self.plan()
        before = json.dumps(plan["canonical_proposition"], sort_keys=True, separators=(",", ":"))
        result = self.validated(plan)
        after = json.dumps(result["validated_plan"]["canonical_proposition"], sort_keys=True, separators=(",", ":"))
        self.assertEqual(before, after)
        self.assertTrue(result["validation_receipt"]["canonical_identity_unchanged"])

    def test_03b_generic_deterministic_authority_can_authorize_exact_term(self):
        plan = self.plan()
        concept = next(
            concept for intent in plan["retrieval_intents"] for concept in intent["search_concepts"]
            if any(term["proposal_source"] == "LLM_PROPOSAL" for term in concept["proposed_terms"])
        )
        term = next(term for term in concept["proposed_terms"] if term["proposal_source"] == "LLM_PROPOSAL")
        result = validate_and_classify_plan_terms(plan, authorities={"records": [{
            "concept_type": concept["concept_type"],
            "terms": [term["term"]],
            "authority_reference": "generic:test-authority:v1",
        }]})
        classified = next(
            item for intent in result["validated_plan"]["retrieval_intents"]
            for item_concept in intent["search_concepts"] for item in item_concept["proposed_terms"]
            if item["term_id"] == term["term_id"]
        )
        self.assertEqual(classified["proposal_class"], "AUTHORIZED_EQUIVALENT")
        self.assertEqual(classified["authority_reference"], "generic:test-authority:v1")

    def test_04_unresolved_term_cannot_enter_query(self):
        plan = self.plan()
        term = next(
            term for intent in plan["retrieval_intents"] for concept in intent["search_concepts"]
            for term in concept["proposed_terms"] if term["proposal_source"] == "LLM_PROPOSAL"
        )
        term["proposal_class"] = "UNRESOLVED"
        term["authority_reference"] = None
        output = self.compile(plan)
        emitted_ids = {
            item["term_id"] for query in output["compiled_queries"]
            for group in query["ordered_term_groups"] for item in group["terms"]
        }
        self.assertNotIn(term["term_id"], emitted_ids)

    def test_05_rejected_term_never_enters_query(self):
        plan = self.plan()
        term = next(
            term for intent in plan["retrieval_intents"] for concept in intent["search_concepts"]
            for term in concept["proposed_terms"] if term["proposal_source"] == "LLM_PROPOSAL"
        )
        term["proposal_class"] = "REJECTED"
        term["authority_reference"] = None
        output = self.compile(plan)
        emitted_ids = {
            item["term_id"] for query in output["compiled_queries"]
            for group in query["ordered_term_groups"] for item in group["terms"]
        }
        self.assertNotIn(term["term_id"], emitted_ids)

    def test_06_relation_omission_must_be_explicit(self):
        plan = self.plan()
        blueprint = plan["retrieval_intents"][0]["candidate_query_blueprints"][0]
        relation = next(row for row in blueprint["dimension_coverage"] if row["dimension"] == "relation")
        relation["coverage_state"] = "OMITTED"
        relation["query_term_ids"] = []
        with self.assertRaises(RetrievalCoverageError):
            validate_plan(plan)

    def test_07_explicit_relation_underrepresentation_compiles_with_marker(self):
        plan = self.plan()
        intent = plan["retrieval_intents"][0]
        blueprint = intent["candidate_query_blueprints"][0]
        relation = next(row for row in blueprint["dimension_coverage"] if row["dimension"] == "relation")
        relation_concepts = set(relation["source_concept_ids"])
        relation["coverage_state"] = "OMITTED"
        relation["query_term_ids"] = []
        blueprint["concept_ids"] = [item for item in blueprint["concept_ids"] if item not in relation_concepts]
        blueprint["relation_representation_state"] = "RELATION_UNDERREPRESENTED"
        output = self.compile(plan)
        matching = [
            route for row in output["compiled_queries"] for route in row["source_routes"]
            if route["intent_id"] == intent["intent_id"]
        ]
        self.assertEqual(matching[0]["relation_representation_state"], "RELATION_UNDERREPRESENTED")

    def test_08_biological_unit_dimension_is_independent(self):
        plan = self.plan()
        blueprint = plan["retrieval_intents"][0]["candidate_query_blueprints"][0]
        subject = next(row for row in blueprint["dimension_coverage"] if row["dimension"] == "subject")
        unit = next(row for row in blueprint["dimension_coverage"] if row["dimension"] == "biological_unit")
        unit["source_concept_ids"] = list(subject["source_concept_ids"])
        with self.assertRaises(RetrievalCoverageError):
            validate_plan(plan)

    def test_09_compiler_is_byte_deterministic_and_order_stable(self):
        plan = self.plan(7)
        first = self.compile(plan)
        second = self.compile(deepcopy(plan))
        self.assertEqual(first, second)
        self.assertEqual(
            [row["query_id"] for row in first["compiled_queries"]],
            [row["query_id"] for row in second["compiled_queries"]],
        )

    def test_10_identical_plan_has_identical_query_hashes(self):
        plan = self.plan(4)
        first = self.compile(plan)
        second = self.compile(plan)
        self.assertEqual(
            [row["query_sha256"] for row in first["compiled_queries"]],
            [row["query_sha256"] for row in second["compiled_queries"]],
        )

    def test_11_case_specific_rule_audit_is_zero(self):
        audit = freeze.case_specific_audit()
        self.assertEqual(audit["status"], "PASS")
        self.assertEqual(audit["production_case_specific_rules"], 0)
        self.assertEqual(audit["hard_coded_pmids"], 0)

    def test_12_no_family_g_or_hidden_fallback(self):
        output = self.compile(self.plan())
        self.assertFalse(output["family_g_emitted"])
        self.assertFalse(output["hidden_fallback_used"])

    def test_13_query_budget_enforcement_is_deterministic(self):
        plan = self.plan(7)
        budget = QueryBudgetConfigDev(
            max_intents_per_target=1,
            max_blueprints_per_intent=2,
            max_queries_per_target=12,
            max_search_only_terms_per_concept=2,
        )
        for _ in range(2):
            with self.assertRaisesRegex(QueryBudgetExceeded, "max_intents_per_target exceeded"):
                self.compile(plan, budgets=budget)

    def test_14_cache_key_changes_with_config_prompt_and_schema(self):
        target = self.targets[0]
        base = planner_cache_key(target, DEFAULT_DEVELOPMENT_CONFIG, prompt_version=PROMPT_VERSION, schema_version=PLAN_SCHEMA_VERSION)
        changed_config = QueryPlannerConfigV1(
            **{**DEFAULT_DEVELOPMENT_CONFIG.__dict__, "reasoning_effort": "medium"}
        )
        self.assertNotEqual(base, planner_cache_key(target, changed_config, prompt_version=PROMPT_VERSION, schema_version=PLAN_SCHEMA_VERSION))
        self.assertNotEqual(base, planner_cache_key(target, DEFAULT_DEVELOPMENT_CONFIG, prompt_version="changed", schema_version=PLAN_SCHEMA_VERSION))
        self.assertNotEqual(base, planner_cache_key(target, DEFAULT_DEVELOPMENT_CONFIG, prompt_version=PROMPT_VERSION, schema_version="changed"))

    def test_15_cache_artifacts_are_immutable(self):
        plan = self.plan()
        key = plan["planner_cache_key_sha256"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"{key}.json"
            immutable_cache_write(path, key, plan)
            immutable_cache_write(path, key, plan)
            changed = deepcopy(plan)
            changed["request_provenance"]["preserved_request_reference"] = "changed"
            with self.assertRaises(PlannerValidationError):
                immutable_cache_write(path, key, changed)

    def test_16_no_retrieval_code_is_executed(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            plan_rows, queries, manifest = freeze.build_fixtures()
        self.assertEqual(len(plan_rows), 8)
        self.assertGreater(len(queries), 0)
        self.assertEqual(manifest["retrieval_calls"], 0)
        self.assertEqual(manifest["candidate_records_seen"], 0)

    def test_17_strict_schema_rejects_unknown_fields(self):
        plan = self.plan()
        plan["executable_query"] = "forbidden"
        with self.assertRaises(PlannerValidationError):
            validate_plan(plan)

    def test_18_frozen_roots_and_v23_assets_verify(self):
        roots = freeze.verify_roots()
        self.assertEqual(roots["status"], "PASS")
        self.assertEqual(roots["search_plan_v24_proposition_aware_architecture_sha256"], freeze.EXPECTED_ARCHITECTURE_ROOT)
        safety = freeze.load_json(freeze.RUN / "scientific_state_safety_audit.json")
        self.assertFalse(safety["v23_assets_modified"])
        self.assertEqual(safety["protected_state_before_sha256"], safety["protected_state_after_sha256"])

    def test_19_output_membership_and_implementation_root(self):
        self.assertEqual({path.name for path in freeze.RUN.iterdir()}, freeze.REQUIRED_OUTPUTS)
        validation = freeze.load_json(freeze.RUN / "validation.json")
        pairs = []
        for name, expected in validation["aggregate_components"]:
            actual = freeze.sha(freeze.RUN / name)
            self.assertEqual(actual, expected)
            pairs.append([name, actual])
        root = hashlib.sha256(freeze.canonical(pairs)).hexdigest()
        self.assertEqual(root, validation["search_plan_v24_dev_planner_compiler_implementation_sha256"])
        audit = freeze.load_json(freeze.RUN / "case_specific_rule_audit.json")
        for record in audit["audited_files"]:
            self.assertEqual(freeze.sha(freeze.ROOT / record["path"]), record["sha256"])


if __name__ == "__main__":
    unittest.main()
