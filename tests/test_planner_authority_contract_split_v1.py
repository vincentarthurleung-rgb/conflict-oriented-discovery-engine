"""Authority-boundary regression tests for Search Plan v2.4 development."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from code_engine.search.openai_planner_payload_transport_v2 import static_provider_compatibility_preflight
from code_engine.search.planner_authority_contract_split_v1 import (
    AUTHORITY_SPLIT_VALIDATOR_VERSION,
    CLASSIFICATIONS,
    FORBIDDEN_MODEL_AUTHORITY_FIELDS,
    PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA,
    VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA,
    AuthoritySplitContractError,
    assemble_validated_plan,
    authority_split_cache_key,
    deterministic_coverage,
    project_frozen_provider_payload,
    validate_planner_proposal,
    validate_proposal_terms,
)
from code_engine.search.proposition_aware_query_planner_v1 import sha256_value
from code_engine.search.query_compiler_v24_dev import QueryCompilerV24Error
from code_engine.search.query_compiler_v24_dev_validated_v1 import (
    compile_validated_proposition_aware_plan,
)
from tools import run_search_plan_v24_dev_real_planner_generation as base


ROOT = Path(__file__).resolve().parents[1]
FAILED_RUN = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v3"


def all_keys(value):
    result = set()
    if isinstance(value, dict):
        result.update(value)
        for child in value.values():
            result.update(all_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(all_keys(child))
    return result


class PlannerAuthorityContractSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_rows = base.load_jsonl(FAILED_RUN / "v24_dev_raw_planner_outputs.jsonl")
        cls.targets = base.targets_by_case()
        manifest = base.load_json(FAILED_RUN / "planner_call_manifest.json")
        cls.manifest = manifest
        cls.calls = {row["case_id"]: row for row in manifest["calls"]}

    def projected(self, index=0):
        row = self.raw_rows[index]
        return row["case_id"], project_frozen_provider_payload(row["structured_parsed_payload"])

    def validated_plan(self, index=0):
        case_id, proposal = self.projected(index)
        target = self.targets[case_id]
        call = self.calls[case_id]
        receipts = validate_proposal_terms(proposal, target=target)
        coverage = deterministic_coverage(proposal, receipts, target=target)
        cache_key = authority_split_cache_key(
            target_sha256=call["target_sha256"],
            planner_config_sha256=call["planner_config_sha256"],
            prompt_sha256=call["frozen_planner_prompt_sha256"],
            proposal_schema_sha256=sha256_value(PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA),
            validated_plan_schema_sha256=sha256_value(VALIDATED_PROPOSITION_AWARE_SEARCH_PLAN_V1_SCHEMA),
        )
        return assemble_validated_plan(
            proposal, receipts, coverage, target=target,
            request_reference=call["request_reference"],
            planner_config_sha256=call["planner_config_sha256"],
            planner_prompt_template_version=self.manifest["configuration"]["prompt_version"],
            planner_cache_key_sha256=cache_key,
        )

    def test_01_model_contract_has_no_authority_reference(self):
        self.assertNotIn("authority_reference", all_keys(PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA))

    def test_02_model_contract_has_no_authoritative_proposal_class(self):
        self.assertNotIn("proposal_class", all_keys(PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA))

    def test_03_extra_authority_field_is_rejected(self):
        case_id, proposal = self.projected()
        proposal["retrieval_intents"][0]["search_concepts"][0]["proposed_terms"][0][
            "authority_reference"] = "model:self-asserted"
        with self.assertRaises(AuthoritySplitContractError):
            validate_planner_proposal(proposal, target=self.targets[case_id])

    def test_04_validator_alone_assigns_all_authority_fields(self):
        case_id, proposal = self.projected()
        self.assertFalse(all_keys(proposal) & FORBIDDEN_MODEL_AUTHORITY_FIELDS)
        receipts = validate_proposal_terms(proposal, target=self.targets[case_id])
        self.assertTrue(receipts)
        self.assertTrue(all(row["validator_version"] == AUTHORITY_SPLIT_VALIDATOR_VERSION for row in receipts))
        self.assertTrue(all(row["deterministic_classification"] in CLASSIFICATIONS for row in receipts))
        self.assertTrue(all("authority_reference" in row and "validation_reason" in row for row in receipts))
        authorized = [row for row in receipts if row["deterministic_classification"] == "AUTHORIZED_EQUIVALENT"]
        search_only = [row for row in receipts if row["deterministic_classification"] == "SEARCH_ONLY_EXPANSION"]
        self.assertTrue(authorized)
        self.assertTrue(search_only)
        self.assertTrue(all(row["authority_reference"] for row in authorized))
        self.assertTrue(all(row["authority_reference"] is None for row in search_only))

    def test_05_validator_classification_set_is_four_state(self):
        self.assertEqual(set(CLASSIFICATIONS), {
            "AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED",
        })
        case_id, base_proposal = self.projected()
        target = self.targets[case_id]
        subject = next(
            concept for intent in base_proposal["retrieval_intents"]
            for concept in intent["search_concepts"] if concept["concept_type"] == "subject"
        )
        term_id = subject["proposed_terms"][0]["term_id"]
        observed = {}
        for label, value in {
            "authorized": target["subject"],
            "search_only": "novel retrieval vocabulary",
            "unresolved": "???",
            "rejected": "EGF AND ERK",
        }.items():
            proposal = deepcopy(base_proposal)
            selected = next(
                concept for intent in proposal["retrieval_intents"]
                for concept in intent["search_concepts"] if concept["concept_id"] == subject["concept_id"]
            )
            selected["proposed_terms"][0]["term"] = value
            receipt = next(
                row for row in validate_proposal_terms(proposal, target=target)
                if row["term_id"] == term_id
            )
            observed[label] = receipt["deterministic_classification"]
        self.assertEqual(observed, {
            "authorized": "AUTHORIZED_EQUIVALENT",
            "search_only": "SEARCH_ONLY_EXPANSION",
            "unresolved": "UNRESOLVED",
            "rejected": "REJECTED",
        })

    def test_06_search_only_never_changes_canonical_identity(self):
        plan = self.validated_plan()
        expected = self.targets[self.raw_rows[0]["case_id"]]
        self.assertEqual(plan["canonical_proposition"]["target_payload"], expected)
        self.assertEqual(plan["canonical_proposition"]["target_sha256"], sha256_value(expected))

    def test_07_compiler_rejects_raw_proposal(self):
        _, proposal = self.projected()
        with self.assertRaisesRegex(QueryCompilerV24Error, "ValidatedPropositionAwareSearchPlanV1"):
            compile_validated_proposition_aware_plan(proposal)

    def test_08_compiler_accepts_validated_plan(self):
        output = compile_validated_proposition_aware_plan(self.validated_plan())
        self.assertGreater(output["compiled_query_count"], 0)
        self.assertFalse(output["compiler_can_read_unvalidated_llm_output"])
        self.assertFalse(output["compiler_can_read_model_authority_claim"])

    def test_09_frozen_eight_payload_projection_is_deterministic(self):
        first = [project_frozen_provider_payload(row["structured_parsed_payload"]) for row in self.raw_rows]
        second = [project_frozen_provider_payload(row["structured_parsed_payload"]) for row in self.raw_rows]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)

    def test_10_target_and_request_identity_are_immutable(self):
        plan = self.validated_plan(7)
        case_id = self.raw_rows[7]["case_id"]
        call = self.calls[case_id]
        self.assertEqual(plan["target_id"], self.targets[case_id]["scientific_proposition_target_id"])
        self.assertEqual(plan["request_provenance"]["preserved_request_reference"], call["request_reference"])

    def test_11_provider_schema_static_preflight_passes(self):
        report = static_provider_compatibility_preflight(PLANNER_PROPOSAL_PAYLOAD_V1_SCHEMA)
        self.assertEqual(report["status"], "PASS")
        self.assertFalse(report["preflight_is_provider_acceptance_proof"])

    def test_12_no_case_specific_authority_rule(self):
        source = (ROOT / "src/code_engine/search/planner_authority_contract_split_v1.py").read_text()
        self.assertNotIn("heldout_v2_", source)
        self.assertNotIn("PMID", source)


if __name__ == "__main__":
    unittest.main()
