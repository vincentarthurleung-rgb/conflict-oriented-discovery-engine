"""Generic tests for ScientificTargetQueryBindingV1.

Fixtures are synthetic and intentionally contain no primary or retired held-out
case identifiers.
"""

from __future__ import annotations

import unittest

from code_engine.search.scientific_target_query_binding_v1 import (
    EMPTY_AUTHORIZED,
    RESOLVED,
    UNRESOLVED_REQUIRED,
    QueryBindingAuthorityError,
    QueryBindingUnresolvedError,
    bind_scientific_target,
    to_legacy_v22_compiler_inputs,
)
from tools.generate_search_plan_v2_multicase_stress_test_offline import make_queries


def target(**overrides):
    value = {
        "artifact_schema_version": "ScientificPropositionTargetV1",
        "scientific_proposition_target_id": "synthetic:target:v1",
        "subject": "X kinase",
        "relation_family": "stimulates",
        "object": "Y activity",
        "measurement_target": "Y activity",
        "measurement_property_endpoint": "activation",
        "context_qualifiers": ["model cells"],
    }
    value.update(overrides)
    return value


def authorities(*, entity=True, relation=True, endpoint=True, broader=True):
    return {
        "entity_alias_records": ([{
            "canonical_id": "ENTITY:X_KINASE",
            "canonical_name": "X kinase",
            "aliases": ["XK", "X enzyme"],
            "source_authority": "synthetic frozen entity registry",
            "authorization_status": "AUTHORIZED",
        }] if entity else []),
        "relation_alias_groups": ([{
            "canonical_id": "RELATION:STIMULATION",
            "terms": ["stimulates", "activates"],
            "source_authority": "synthetic frozen relation registry",
            "authorization_status": "AUTHORIZED",
        }] if relation else []),
        "endpoint_alias_groups": ([{
            "canonical_id": "ENDPOINT:RELEASE_SECRETION",
            "terms": ["release", "secretion"],
            "source_authority": "synthetic frozen endpoint registry",
            "authorization_status": "AUTHORIZED",
        }] if endpoint else []),
        "broader_concept_relations": ([{
            "canonical_id": "BROADER:Y_SIGNALING",
            "narrower_terms": ["Y activity", "activation"],
            "broader_term": "Y signaling",
            "source_authority": "synthetic frozen hierarchy registry",
            "authorization_status": "AUTHORIZED",
        }] if broader else []),
    }


def bind(value=None, auth=None):
    return bind_scientific_target(
        value or target(), auth if auth is not None else authorities(),
        target_source_hash="0" * 64,
    )


class ScientificTargetQueryBindingV1Tests(unittest.TestCase):
    def test_subject_literal_only_is_resolved_without_alias_invention(self):
        result = bind(auth=authorities(entity=False, relation=False, endpoint=False, broader=False))
        field = result["fields"]["subject_terms"]
        self.assertEqual(field["resolution_state"], RESOLVED)
        self.assertEqual([term["term"] for term in field["terms"]], ["X kinase"])

    def test_canonical_subject_alias_available(self):
        terms = bind()["fields"]["authorized_aliases"]["terms"]
        self.assertEqual({term["term"] for term in terms}, {"XK", "X enzyme"})

    def test_no_subject_alias_available(self):
        result = bind(auth=authorities(entity=False))
        self.assertEqual(
            result["fields"]["authorized_aliases"]["resolution_state"],
            UNRESOLVED_REQUIRED,
        )

    def test_relation_aliases_available(self):
        terms = bind()["fields"]["relation_terms"]["terms"]
        self.assertEqual({term["term"] for term in terms}, {"stimulates", "activates"})

    def test_relation_alias_unavailable_keeps_target_literal(self):
        terms = bind(auth=authorities(relation=False))["fields"]["relation_terms"]["terms"]
        self.assertEqual([term["term"] for term in terms], ["stimulates"])

    def test_endpoint_measurement_aliases_available(self):
        value = target(object="cargo release", measurement_target="release",
                       measurement_property_endpoint="release")
        terms = bind(value, authorities())["fields"]["measurement_terms"]["terms"]
        self.assertIn("secretion", {term["term"] for term in terms})

    def test_endpoint_alias_unavailable_keeps_target_literals(self):
        result = bind(auth=authorities(endpoint=False))
        terms = result["fields"]["measurement_terms"]["terms"]
        self.assertEqual({term["term"] for term in terms}, {"Y activity", "activation"})

    def test_authorized_broader_relation(self):
        terms = bind()["fields"]["broader_terms"]["terms"]
        self.assertEqual([term["term"] for term in terms], ["Y signaling"])
        self.assertEqual(terms[0]["provenance_kind"], "AUTHORIZED_BROADER_CONCEPT")

    def test_no_authorized_broader_relation(self):
        result = bind(auth=authorities(broader=False))
        self.assertEqual(result["fields"]["broader_terms"]["resolution_state"],
                         UNRESOLVED_REQUIRED)

    def test_multiple_aliases_have_deterministic_order(self):
        first = bind()["fields"]["authorized_aliases"]["terms"]
        second = bind()["fields"]["authorized_aliases"]["terms"]
        self.assertEqual(first, second)
        self.assertEqual([term["normalized_term"] for term in first],
                         sorted(term["normalized_term"] for term in first))

    def test_duplicate_alias_normalization(self):
        auth = authorities()
        auth["entity_alias_records"][0]["aliases"] = ["X-K", "x k"]
        terms = bind(auth=auth)["fields"]["authorized_aliases"]["terms"]
        self.assertEqual(len(terms), 1)

    def test_unauthorized_alias_rejected(self):
        auth = authorities()
        auth["entity_alias_records"][0]["authorization_status"] = "UNAUTHORIZED"
        with self.assertRaises(QueryBindingAuthorityError):
            bind(auth=auth)

    def test_unresolved_required_field_fails_before_compiler(self):
        value = target()
        result = bind(value, authorities(broader=False))
        with self.assertRaises(QueryBindingUnresolvedError):
            to_legacy_v22_compiler_inputs(value, result, source_ref="synthetic#target")

    def test_family_f_provenance_is_authorized(self):
        field = bind()["fields"]["authorized_aliases"]
        self.assertEqual(field["resolution_state"], RESOLVED)
        self.assertTrue(field["terms"])
        self.assertTrue(all(term["authorization_status"] == "AUTHORIZED" for term in field["terms"]))
        self.assertTrue(all(term["provenance_kind"] in {
            "CANONICAL_ENTITY_ALIAS", "CANONICAL_ENDPOINT_ALIAS"
        } for term in field["terms"]))

    def test_deterministic_repeated_binding(self):
        self.assertEqual(bind(), bind())

    def test_existing_v22_compiler_behavior_preserved(self):
        value = target()
        result = bind(value, authorities())
        compiler_target, compiler_spec, source_ref = to_legacy_v22_compiler_inputs(
            value, result, source_ref="synthetic#target",
        )
        through_adapter = make_queries("synthetic_case", compiler_target, compiler_spec, source_ref)
        direct = make_queries("synthetic_case", compiler_target, dict(compiler_spec), source_ref)
        self.assertEqual(through_adapter, direct)
        self.assertEqual([family["family_code"] for family in through_adapter], list("ABCDEF"))
        self.assertEqual(result["fields"]["unverified_terms"]["resolution_state"], EMPTY_AUTHORIZED)


if __name__ == "__main__":
    unittest.main()
