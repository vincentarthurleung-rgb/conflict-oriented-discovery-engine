from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    ProviderSchemaPreflightError,
    ProviderSchemaRenderError,
    ScientificSchemaValidationError,
    planner_cache_key_with_provider_schema,
    preflight_provider_schema,
    render_provider_schema,
    require_provider_schema_preflight,
    sha256_value,
    validate_scientific_instance,
)
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as implementation


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = implementation.ARCHITECTURE_RUN / "proposition_aware_search_plan_v1_schema.json"
TARGET_PATH = implementation.TARGETS_PATH
TARGET_POINTER = "#/properties/canonical_proposition/properties/target_payload"


class OpenAIStructuredOutputSchemaRendererV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scientific = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.target = json.loads(TARGET_PATH.read_text(encoding="utf-8").splitlines()[0])
        cls.provider, cls.audit = render_provider_schema(
            cls.scientific, exact_object_bindings={TARGET_POINTER: cls.target}
        )

    def test_const_only_regression_fails_local_preflight(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["artifact_schema_version"],
            "properties": {"artifact_schema_version": {"const": "PropositionAwareSearchPlanV1"}},
        }
        report = preflight_provider_schema(schema)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["const_nodes_missing_explicit_type"], 1)
        with self.assertRaises(ProviderSchemaPreflightError):
            require_provider_schema_preflight(schema)

    def test_rendered_const_has_explicit_same_type_and_value(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["artifact_schema_version"],
            "properties": {"artifact_schema_version": {"const": "PropositionAwareSearchPlanV1"}},
        }
        rendered, _ = render_provider_schema(schema)
        node = rendered["properties"]["artifact_schema_version"]
        self.assertEqual(node, {"const": "PropositionAwareSearchPlanV1", "type": "string"})
        self.assertEqual(require_provider_schema_preflight(rendered)["status"], "PASS")

    def test_string_integer_boolean_const_fixtures(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["s", "i", "b"],
            "properties": {"s": {"const": "x"}, "i": {"const": 3}, "b": {"const": True}},
        }
        rendered, _ = render_provider_schema(schema)
        self.assertEqual(rendered["properties"]["s"]["type"], "string")
        self.assertEqual(rendered["properties"]["i"]["type"], "integer")
        self.assertEqual(rendered["properties"]["b"]["type"], "boolean")
        require_provider_schema_preflight(rendered)

    def test_nested_array_enum_nullable_and_required_fixture(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["nested", "items", "nullable"],
            "properties": {
                "nested": {
                    "type": "object", "additionalProperties": False,
                    "required": ["state"],
                    "properties": {"state": {"type": "string", "enum": ["A", "B"]}},
                },
                "items": {"type": "array", "items": {"type": "integer"}},
                "nullable": {"type": ["string", "null"]},
            },
        }
        rendered, _ = render_provider_schema(schema)
        report = require_provider_schema_preflight(rendered)
        self.assertEqual(report["objects_missing_additional_properties_false"], 0)
        self.assertEqual(report["object_properties_missing_required_membership"], 0)
        self.assertFalse(report["root_anyof_present"])

    def test_refs_and_defs_fixture(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["value"],
            "properties": {"value": {"$ref": "#/$defs/value"}},
            "$defs": {"value": {"type": "string", "enum": ["x", "y"]}},
        }
        rendered, _ = render_provider_schema(schema)
        self.assertEqual(require_provider_schema_preflight(rendered)["status"], "PASS")

    def test_all_real_const_nodes_gain_compatible_type(self):
        def const_nodes(value):
            if isinstance(value, dict):
                if "const" in value:
                    yield value
                for child in value.values():
                    yield from const_nodes(child)
            elif isinstance(value, list):
                for child in value:
                    yield from const_nodes(child)

        scientific_nodes = list(const_nodes(self.scientific))
        provider_nodes = list(const_nodes(self.provider))
        self.assertGreaterEqual(len(scientific_nodes), 7)
        self.assertTrue(any("type" not in node for node in scientific_nodes))
        self.assertTrue(all("type" in node for node in provider_nodes))
        self.assertEqual(require_provider_schema_preflight(self.provider)["const_nodes_missing_explicit_type"], 0)

    def test_real_provider_schema_passes_complete_preflight(self):
        report = require_provider_schema_preflight(self.provider)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["unsupported_keyword_occurrences"], 0)
        self.assertLessEqual(report["maximum_nesting_depth"], 10)
        self.assertLessEqual(report["total_object_properties"], 5000)

    def test_exact_target_binding_is_closed_and_semantics_preserving(self):
        node = self.provider["properties"]["canonical_proposition"]["properties"]["target_payload"]
        self.assertEqual(node["type"], "object")
        self.assertEqual(node["const"], self.target)
        self.assertFalse(node["additionalProperties"])
        self.assertEqual(set(node["required"]), set(self.target))
        self.assertTrue(any(row["transformation"] == "BIND_OPEN_OBJECT_TO_REQUEST_EXACT_VALUE" for row in self.audit))

    def test_frozen_scientific_post_validation_retains_delegated_constraints(self):
        plans, _, _ = implementation.build_fixtures()
        plan = deepcopy(plans[0]["plan"])
        plan["canonical_proposition"]["target_payload"] = self.target
        plan["canonical_proposition"]["target_sha256"] = sha256_value(self.target)
        validate_scientific_instance(plan, self.scientific)
        invalid = deepcopy(plan)
        invalid["planner_prompt_template_version"] = ""
        with self.assertRaisesRegex(ScientificSchemaValidationError, "minLength"):
            validate_scientific_instance(invalid, self.scientific)
        invalid = deepcopy(plan)
        invalid["retrieval_intents"][0]["required_dimensions"].append(
            invalid["retrieval_intents"][0]["required_dimensions"][0]
        )
        with self.assertRaisesRegex(ScientificSchemaValidationError, "uniqueItems"):
            validate_scientific_instance(invalid, self.scientific)

    def test_provider_schema_hash_participates_in_new_cache_identity(self):
        base = "a" * 64
        first = planner_cache_key_with_provider_schema(
            base_planner_cache_key=base, provider_schema_sha256=sha256_value(self.provider)
        )
        changed = deepcopy(self.provider)
        changed["description"] = "semantically inert but transport identity changing"
        second = planner_cache_key_with_provider_schema(
            base_planner_cache_key=base, provider_schema_sha256=sha256_value(changed)
        )
        self.assertNotEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{64}$")

    def test_scientific_schema_file_is_not_modified(self):
        expected = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
        render_provider_schema(self.scientific, exact_object_bindings={TARGET_POINTER: self.target})
        self.assertEqual(hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest(), expected)

    def test_untranslatable_format_constraint_fails_closed(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["value"],
            "properties": {"value": {"type": "string", "format": "email"}},
        }
        with self.assertRaisesRegex(ProviderSchemaRenderError, "cannot preserve"):
            render_provider_schema(schema)

    def test_delegated_numeric_and_collection_assertions_remain_enforced(self):
        schema = {
            "type": "object", "additionalProperties": False,
            "required": ["number", "values"],
            "properties": {
                "number": {"type": "integer", "minimum": 2, "maximum": 4},
                "values": {
                    "type": "array", "items": {"type": "string"},
                    "contains": {"const": "required"}, "minContains": 1,
                },
            },
        }
        rendered, _ = render_provider_schema(schema)
        require_provider_schema_preflight(rendered)
        validate_scientific_instance({"number": 3, "values": ["required"]}, schema)
        with self.assertRaisesRegex(ScientificSchemaValidationError, "minimum"):
            validate_scientific_instance({"number": 1, "values": ["required"]}, schema)
        with self.assertRaisesRegex(ScientificSchemaValidationError, "contains"):
            validate_scientific_instance({"number": 3, "values": ["other"]}, schema)


if __name__ == "__main__":
    unittest.main()
