import unittest

from code_engine.system_b.annotation_schemas import SchemaValidationError, get_schema, schema_for_item_type, validate_annotation_payload


class AtlasAnnotationSchemaRegistryTests(unittest.TestCase):
    def test_schema_hash_and_item_type_projection(self):
        schema = schema_for_item_type("weak_candidate")
        self.assertEqual(schema.schema_id, "conflict_pair_v1")
        self.assertEqual(len(schema.sha256), 64)
        form = schema.form_definition()
        self.assertEqual(form["schema_id"], "conflict_pair_v1")
        self.assertTrue(form["frozen"])

    def test_validation_rejects_unknown_and_bad_allowed_value(self):
        schema = get_schema("conflict_pair_v1")
        with self.assertRaises(SchemaValidationError) as ctx:
            validate_annotation_payload(schema, {"final_label": "VALID", "unexpected": "x"})
        self.assertEqual(ctx.exception.field_errors["unexpected"], "unknown_field")
        payload = {
            "same_normalized_pair": True,
            "same_relation_family": True,
            "same_outcome_definition": True,
            "same_experimental_level": True,
            "context_comparable": False,
            "sign_a": "positive",
            "sign_b": "negative",
            "true_conflict": False,
            "non_conflict_reason": "different_context_non_comparable",
            "information_sufficient": True,
        }
        checked = validate_annotation_payload(schema, payload)
        self.assertEqual(checked["non_conflict_reason"], "different_context_non_comparable")
        payload["non_conflict_reason"] = "opposite_sign_auto_conflict"
        with self.assertRaises(SchemaValidationError):
            validate_annotation_payload(schema, payload)


if __name__ == "__main__":
    unittest.main()
