"""Offline tests for the beta.2 fresh primary held-out-v2 case freeze."""

import ast
from collections import Counter
import unittest

from tools import freeze_search_plan_v23_beta_2_primary_heldout_v2_cases_offline as freeze


class PrimaryHeldoutV2CaseFreezeTests(unittest.TestCase):
    def setUp(self):
        self.targets = freeze.build_targets()
        self.cases = freeze.build_cases(self.targets)

    def test_exact_case_ids_order_and_uniqueness(self):
        target_ids = [row["case_id"] for row in self.targets]
        case_ids = [row["case_id"] for row in self.cases["cases"]]
        self.assertEqual(target_ids, freeze.CASE_IDS)
        self.assertEqual(case_ids, freeze.CASE_IDS)
        self.assertEqual(len(set(target_ids)), 8)
        self.assertTrue(set(target_ids).isdisjoint(freeze.RETIRED_IDS))

    def test_required_difficulty_and_domain_structure(self):
        case_rows = self.cases["cases"]
        self.assertEqual(
            Counter(row["ambiguity_tier"] for row in case_rows),
            {"LOW": 2, "MEDIUM": 2, "HIGH": 4},
        )
        self.assertEqual(
            Counter(row["domain"] for row in case_rows),
            {"non_oncology": 6, "oncology": 2},
        )

    def test_scientific_targets_are_complete_and_frozen(self):
        required = {
            "subject",
            "relation_family",
            "measurement_target",
            "measurement_property_endpoint",
            "context_qualifiers",
            "context_qualifier_dimensions",
            "required_evidence_mode",
            "acceptable_endpoint_evidence",
            "insufficient_evidence",
            "scientific_boundaries",
            "primary_proposition_meaning",
        }
        for row in self.targets:
            self.assertTrue(row["frozen"])
            self.assertTrue(all(row[field] for field in required))
            self.assertFalse(row["retrieval_membership_grants_compatibility"])

    def test_high_difficulty_context_and_endpoint_boundaries(self):
        by_id = {row["case_id"]: row for row in self.targets}
        self.assertIn("dynamic", by_id["heldout_v2_105"]["measurement_property_endpoint"])
        self.assertEqual(
            by_id["heldout_v2_106"]["context_qualifier_dimensions"]["treatment_context"],
            ["LPS stimulation"],
        )
        self.assertEqual(by_id["heldout_v2_107"]["therapy"], "trametinib")
        self.assertEqual(
            by_id["heldout_v2_107"]["context_qualifier_dimensions"]["genotype_context"],
            ["KRAS-mutant"],
        )
        self.assertEqual(by_id["heldout_v2_108"]["therapy"], "temozolomide")

    def test_exact_nonoverlap_against_both_prior_sets(self):
        v1 = freeze.nonoverlap_audit(
            self.targets,
            freeze.HELDOUT_V1_TARGETS,
            schema="TestHeldoutV1Audit",
            prior_label="heldout_v1",
        )
        retired = freeze.nonoverlap_audit(
            self.targets,
            freeze.RETIRED_V2_TARGETS,
            schema="TestRetiredV2Audit",
            prior_label="retired_v2",
        )
        for audit in (v1, retired):
            self.assertEqual(audit["status"], "PASS")
            self.assertEqual(audit["exact_proposition_overlap"], 0)
            self.assertEqual(audit["exact_subject_relation_endpoint_triple_overlap"], 0)

    def test_generator_has_no_query_layer_imports_or_calls(self):
        source = freeze.Path(freeze.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
            elif isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name):
                    called.add(function.id)
                elif isinstance(function, ast.Attribute):
                    called.add(function.attr)
        forbidden_modules = {
            "code_engine.search.scientific_target_query_binding_v1_1",
            "code_engine.search.query_family_applicability_v1",
            "code_engine.search.query_compiler_v23_beta2",
        }
        forbidden_calls = {
            "ScientificTargetQueryBindingV1_1",
            "QueryFamilyApplicabilityV1",
            "SearchPlanQueryCompilerV23Beta2",
            "compile",
            "compile_target",
        }
        self.assertTrue(imported.isdisjoint(forbidden_modules))
        self.assertTrue(called.isdisjoint(forbidden_calls))

    def test_case_construction_is_deterministic(self):
        self.assertEqual(self.targets, freeze.build_targets())
        self.assertEqual(self.cases, freeze.build_cases(freeze.build_targets()))


if __name__ == "__main__":
    unittest.main()
