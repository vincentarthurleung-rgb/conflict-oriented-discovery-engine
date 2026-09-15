"""Synthetic, case-agnostic tests for the v2.3-beta.2 modular compiler."""

from __future__ import annotations

import unittest

from code_engine.search.query_compiler_v23_beta2 import (
    compile_family_a,
    compile_modular_queries,
)
from code_engine.search.scientific_target_query_binding_v1 import QueryBindingAuthorityError
from code_engine.search.scientific_target_query_binding_v1_1 import (
    BINDING_VERSION,
    bind_scientific_target_v1_1,
)


def target(**overrides):
    value = {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "synthetic:target:v1",
        "subject": "synthetic regulator",
        "relation_family": "stimulates",
        "object": "target activity",
        "measurement_target": "target activity",
        "measurement_property_endpoint": "activation",
        "context_qualifiers": ["synthetic model"],
    }
    value.update(overrides)
    return value


def authorities(*, aliases=False, broader=False, relation=False, endpoint=False):
    return {
        "entity_alias_records": ([{
            "canonical_id": "SYNTHETIC:REGULATOR",
            "canonical_name": "synthetic regulator",
            "aliases": ["SRX", "synthetic factor"],
            "source_authority": "synthetic frozen entity authority",
            "authorization_status": "AUTHORIZED",
        }] if aliases else []),
        "broader_concept_relations": ([{
            "canonical_id": "SYNTHETIC:BROADER",
            "narrower_terms": ["target activity", "activation"],
            "broader_term": "target signaling",
            "source_authority": "synthetic frozen hierarchy authority",
            "authorization_status": "AUTHORIZED",
        }] if broader else []),
        "relation_alias_groups": ([{
            "canonical_id": "SYNTHETIC:RELATION",
            "terms": ["stimulates", "activates"],
            "source_authority": "synthetic frozen relation authority",
            "authorization_status": "AUTHORIZED",
        }] if relation else []),
        "endpoint_alias_groups": ([{
            "canonical_id": "SYNTHETIC:ENDPOINT",
            "terms": ["count", "number"],
            "source_authority": "synthetic frozen endpoint authority",
            "authorization_status": "AUTHORIZED",
        }] if endpoint else []),
    }


def compile_target(value=None, authority=None):
    value = value or target()
    binding = bind_scientific_target_v1_1(
        value, authority if authority is not None else authorities(),
        target_source_hash="0" * 64,
    )
    return binding, compile_modular_queries("synthetic_case", binding, source_ref="synthetic#target")


def slot(compilation, family_id):
    return next(item for item in compilation["family_slots"] if item["family_id"] == family_id)


class QueryCompilerV23Beta2Tests(unittest.TestCase):
    def test_01_literal_only_core_family_a_is_independent(self):
        binding, _ = compile_target()
        minimal = {
            "fields": {
                "subject_terms": binding["fields"]["subject_terms"],
                "object_terms": binding["fields"]["object_terms"],
            },
            "binding_version": BINDING_VERSION,
        }
        query = compile_family_a("synthetic_case", minimal, "synthetic#target")
        self.assertEqual(query["query_string"], '"synthetic regulator" AND "target activity"')

    def test_02_no_broader_keeps_a_and_marks_b_not_applicable(self):
        _, result = compile_target()
        self.assertIsNotNone(slot(result, "A")["compiled_query"])
        self.assertEqual(slot(result, "B")["applicability"], "NOT_APPLICABLE")

    def test_03_authorized_broader_makes_b_applicable(self):
        _, result = compile_target(authority=authorities(broader=True))
        self.assertEqual(slot(result, "B")["applicability"], "APPLICABLE")
        self.assertEqual(slot(result, "B")["compiled_query"]["query_string"],
                         '"synthetic regulator" AND "target signaling"')

    def test_04_relation_literal_without_alias_compiles_c(self):
        _, result = compile_target()
        self.assertEqual(slot(result, "C")["applicability"], "APPLICABLE")
        self.assertIn('"stimulates"', slot(result, "C")["compiled_query"]["query_string"])

    def test_05_relation_aliases_have_deterministic_binding_order(self):
        first, result = compile_target(authority=authorities(relation=True))
        second, _ = compile_target(authority=authorities(relation=True))
        self.assertEqual(first["fields"]["relation_terms"], second["fields"]["relation_terms"])
        self.assertEqual(first["fields"]["relation_terms"]["value"][0]["term"], "stimulates")
        self.assertEqual(slot(result, "C")["applicability"], "APPLICABLE")

    def test_06_measurement_literal_without_alias_compiles_d(self):
        _, result = compile_target()
        self.assertEqual(slot(result, "D")["applicability"], "APPLICABLE")
        self.assertIn('"activation"', slot(result, "D")["compiled_query"]["query_string"])

    def test_07_measurement_aliases_are_deterministic(self):
        value = target(object="observations", measurement_target="count",
                       measurement_property_endpoint="count")
        first, result = compile_target(value, authorities(endpoint=True))
        second, _ = compile_target(value, authorities(endpoint=True))
        self.assertEqual(first["fields"]["measurement_terms"], second["fields"]["measurement_terms"])
        self.assertIn("number", {item["term"] for item in first["fields"]["measurement_terms"]["value"]})
        self.assertEqual(slot(result, "D")["applicability"], "APPLICABLE")

    def test_08_context_absent_marks_e_not_applicable(self):
        _, result = compile_target(target(context_qualifiers=[]))
        self.assertEqual(slot(result, "E")["applicability"], "NOT_APPLICABLE")
        self.assertIsNone(slot(result, "E")["compiled_query"])

    def test_09_authorized_context_literal_compiles_e(self):
        _, result = compile_target()
        self.assertEqual(slot(result, "E")["applicability"], "APPLICABLE")
        self.assertIn('"synthetic model"', slot(result, "E")["compiled_query"]["query_string"])

    def test_10_no_alias_marks_f_not_applicable(self):
        _, result = compile_target()
        self.assertEqual(slot(result, "F")["applicability"], "NOT_APPLICABLE")
        self.assertIsNone(slot(result, "F")["compiled_query"])

    def test_11_authorized_alias_compiles_f(self):
        _, result = compile_target(authority=authorities(aliases=True))
        self.assertEqual(slot(result, "F")["applicability"], "APPLICABLE")
        self.assertTrue(slot(result, "F")["compiled_query"]["term_provenance"])

    def test_12_missing_subject_invalidates_core(self):
        _, result = compile_target(target(subject=""))
        self.assertEqual(slot(result, "A")["applicability"], "INVALID_REQUIRED_INPUT")
        self.assertEqual(result["case_compilation_status"], "INVALID_CORE_BINDING")

    def test_13_missing_object_invalidates_core(self):
        _, result = compile_target(target(object=""))
        self.assertEqual(slot(result, "A")["applicability"], "INVALID_REQUIRED_INPUT")
        self.assertEqual(result["case_compilation_status"], "INVALID_CORE_BINDING")

    def test_14_unauthorized_alias_is_rejected(self):
        authority = authorities(aliases=True)
        authority["entity_alias_records"][0]["authorization_status"] = "UNAUTHORIZED"
        with self.assertRaises(QueryBindingAuthorityError):
            compile_target(authority=authority)

    def test_15_unverified_fallback_never_reaches_f(self):
        binding, result = compile_target(target(unverified_terms=["invented fallback"]))
        self.assertEqual(binding["rejected_unverified_term_count"], 1)
        self.assertEqual(slot(result, "F")["applicability"], "NOT_APPLICABLE")
        self.assertFalse(result["unverified_lexical_fallback_used"])

    def test_16_family_g_never_substitutes_for_f(self):
        _, result = compile_target()
        self.assertFalse(result["family_g_emitted"])
        self.assertNotIn("G", [item["family_id"] for item in result["family_slots"]])

    def test_17_six_family_slots_always_emitted(self):
        _, result = compile_target(target(subject="", object="", relation_family=""))
        self.assertEqual(result["family_slot_count"], 6)

    def test_18_optional_absence_does_not_invalidate_case(self):
        _, result = compile_target(target(context_qualifiers=[]))
        self.assertEqual(result["case_compilation_status"], "VALID")
        self.assertGreaterEqual(result["executable_query_count"], 1)

    def test_19_family_order_is_a_through_f(self):
        _, result = compile_target(authority=authorities(aliases=True, broader=True))
        self.assertEqual([item["family_id"] for item in result["family_slots"]], list("ABCDEF"))

    def test_20_repeated_compilation_is_deterministic(self):
        first = compile_target(authority=authorities(aliases=True, broader=True, relation=True))[1]
        second = compile_target(authority=authorities(aliases=True, broader=True, relation=True))[1]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
