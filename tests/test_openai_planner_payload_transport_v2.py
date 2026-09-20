from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from code_engine.search.openai_planner_payload_transport_v2 import (
    DETERMINISTIC_REQUEST_ECHO_FIELDS,
    MODEL_GENERATED_FIELDS,
    PlannerPayloadTransportError,
    REHYDRATOR_VERSION,
    audit_deterministic_request_echo_fields,
    planner_transport_cache_key,
    rehydrate_planner_output,
    render_provider_payload_schema,
    static_provider_compatibility_preflight,
    validate_provider_payload,
)
from code_engine.search.openai_structured_output_schema_renderer_v1 import (
    validate_scientific_instance,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    canonical_target_hash,
    planner_config_hash,
    validate_plan,
)
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as implementation


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = implementation.ARCHITECTURE_RUN / "proposition_aware_search_plan_v1_schema.json"
PROMPT_PATH = implementation.RUN / "query_planner_prompt_v1.md"


class OpenAIPlannerPayloadTransportV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scientific_schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.provider_schema, cls.audit = render_provider_payload_schema(cls.scientific_schema)
        cls.fixtures, _, _ = implementation.build_fixtures()
        cls.prompt_sha256 = hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest()
        cls.scientific_schema_sha256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()

    def rehydrate(self, fixture_index=0):
        row = self.fixtures[fixture_index]
        plan = row["plan"]
        target = plan["canonical_proposition"]["target_payload"]
        payload = {"retrieval_intents": deepcopy(plan["retrieval_intents"])}
        request_reference = f"transport-v2-fixture:{target['case_id']}"
        result = rehydrate_planner_output(
            payload,
            canonical_target=target,
            request_reference=request_reference,
            planner_config=DEFAULT_DEVELOPMENT_CONFIG,
            prompt_sha256=self.prompt_sha256,
            scientific_schema_sha256=self.scientific_schema_sha256,
            provider_payload_schema=self.provider_schema,
        )
        return result, target, payload, request_reference

    def test_root_projection_contains_only_model_generated_payload(self):
        self.assertEqual(set(self.provider_schema["properties"]), set(MODEL_GENERATED_FIELDS))
        self.assertEqual(self.provider_schema["required"], list(MODEL_GENERATED_FIELDS))
        self.assertFalse(self.provider_schema["additionalProperties"])
        fields = audit_deterministic_request_echo_fields(self.scientific_schema)
        self.assertEqual(tuple(fields["deterministic_request_echo_fields"]), DETERMINISTIC_REQUEST_ECHO_FIELDS)
        self.assertEqual(fields["model_generated_fields"], ["retrieval_intents"])

    def test_provider_projection_contains_no_const(self):
        def collect(value):
            if isinstance(value, dict):
                if "const" in value:
                    yield value["const"]
                for child in value.values():
                    yield from collect(child)
            elif isinstance(value, list):
                for child in value:
                    yield from collect(child)
        self.assertEqual(list(collect(self.provider_schema)), [])
        preflight = static_provider_compatibility_preflight(self.provider_schema)
        self.assertEqual(preflight["status"], "PASS")
        self.assertEqual(preflight["provider_schema_object_const_count"], 0)
        self.assertEqual(preflight["provider_schema_array_const_count"], 0)

    def test_primitive_const_regression_is_detected_and_projection_uses_enum(self):
        broken = {
            "type": "object", "additionalProperties": False,
            "required": ["fixed"], "properties": {"fixed": {"const": True}},
        }
        report = static_provider_compatibility_preflight(broken)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["provider_schema_primitive_const_count"], 1)
        enum_nodes = []
        def walk(value):
            if isinstance(value, dict):
                if value.get("enum") == [True]:
                    enum_nodes.append(value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.provider_schema)
        self.assertGreaterEqual(len(enum_nodes), 5)
        self.assertTrue(all(node.get("type") == "boolean" for node in enum_nodes))

    def test_object_and_array_const_regression_fails_locally(self):
        broken = {
            "type": "object", "additionalProperties": False,
            "required": ["object_value", "array_value"],
            "properties": {
                "object_value": {"type": "object", "const": {"x": 1}, "properties": {},
                                 "required": [], "additionalProperties": False},
                "array_value": {"type": "array", "const": [1], "items": {"type": "integer"}},
            },
        }
        report = static_provider_compatibility_preflight(broken)
        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(report["provider_schema_object_const_count"], 1)
        self.assertEqual(report["provider_schema_array_const_count"], 1)

    def test_all_eight_fixtures_rehydrate_and_pass_unchanged_scientific_validation(self):
        for index in range(8):
            with self.subTest(index=index):
                result, target, _, _ = self.rehydrate(index)
                validate_scientific_instance(result, self.scientific_schema)
                validate_plan(result, expected_target=target)
                self.assertEqual(result["canonical_proposition"]["target_payload"], target)
                self.assertEqual(result["canonical_proposition"]["target_sha256"], canonical_target_hash(target))
                self.assertEqual(result["target_id"], target["scientific_proposition_target_id"])

    def test_rehydrated_object_matches_independently_constructed_expected_object(self):
        result, target, payload, request_reference = self.rehydrate()
        expected = {
            "artifact_schema_version": PLAN_SCHEMA_VERSION,
            "request_provenance": {
                "request_sha256": hashlib.sha256(request_reference.encode("utf-8")).hexdigest(),
                "preserved_request_reference": request_reference,
            },
            "target_id": target["scientific_proposition_target_id"],
            "canonical_proposition": {
                "schema_version": "ScientificPropositionTargetV1",
                "target_sha256": canonical_target_hash(target),
                "target_payload": target,
            },
            "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
            "planner_prompt_template_version": DEFAULT_DEVELOPMENT_CONFIG.prompt_version,
            "planner_cache_key_sha256": result["planner_cache_key_sha256"],
            "retrieval_intents": payload["retrieval_intents"],
            "planner_output_frozen_before_retrieval": True,
        }
        self.assertEqual(result, expected)

    def test_injection_of_each_deterministic_field_fails_payload_validation(self):
        _, _, payload, _ = self.rehydrate()
        for field in DETERMINISTIC_REQUEST_ECHO_FIELDS:
            with self.subTest(field=field):
                malicious = deepcopy(payload)
                malicious[field] = "attacker-controlled"
                with self.assertRaisesRegex(PlannerPayloadTransportError, "additional properties"):
                    validate_provider_payload(malicious, self.provider_schema)

    def test_nested_hidden_echo_field_fails_payload_validation(self):
        _, _, payload, _ = self.rehydrate()
        malicious = deepcopy(payload)
        malicious["retrieval_intents"][0]["target_id"] = "injected"
        with self.assertRaisesRegex(PlannerPayloadTransportError, "additional properties"):
            validate_provider_payload(malicious, self.provider_schema)

    def test_rehydrator_copies_target_and_payload(self):
        result, target, payload, _ = self.rehydrate()
        target["subject"] = "mutated-after-rehydration"
        payload["retrieval_intents"].clear()
        self.assertNotEqual(result["canonical_proposition"]["target_payload"]["subject"], target["subject"])
        self.assertTrue(result["retrieval_intents"])

    def test_scientific_postvalidation_still_rejects_delegated_constraint(self):
        result, _, _, _ = self.rehydrate()
        result["retrieval_intents"] = []
        with self.assertRaisesRegex(Exception, "minItems"):
            validate_scientific_instance(result, self.scientific_schema)

    def test_cache_identity_binds_all_transport_inputs_and_rehydrator(self):
        values = {
            "canonical_target_sha256": "1" * 64,
            "planner_config_sha256": "2" * 64,
            "prompt_sha256": "3" * 64,
            "scientific_schema_sha256": "4" * 64,
            "provider_projection_schema_sha256": "5" * 64,
            "rehydrator_version": REHYDRATOR_VERSION,
        }
        baseline = planner_transport_cache_key(**values)
        for key in values:
            changed = dict(values)
            changed[key] = ("6" * 64) if key.endswith("sha256") else "changed-rehydrator"
            with self.subTest(key=key):
                self.assertNotEqual(baseline, planner_transport_cache_key(**changed))

    def test_renderer_has_no_case_specific_branch(self):
        source = (ROOT / "src/code_engine/search/openai_planner_payload_transport_v2.py").read_text(encoding="utf-8")
        for case_id in range(101, 109):
            self.assertNotIn(f"heldout_v2_{case_id}", source)


if __name__ == "__main__":
    unittest.main()
