from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/search_plan_v24_alpha314d_pass_b_output_contract_offline.py"
SPEC = importlib.util.spec_from_file_location("alpha314d_output_contract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_eight_synthetic_schema_and_identity_cases() -> None:
    schema = MODULE.load(MODULE.SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    cases = MODULE.synthetic_cases(schema)
    assert len(cases) == 8
    for case in cases:
        result = MODULE.validate_batch({"records": case["records"]}, case["expected_ids"], schema)
        assert result["valid"] is case["expected_valid"], case["case_id"]
    by_name = {case["case_id"]: case for case in cases}
    for name in ("INVALID_RELEVANCE_ENUM", "CONTAMINANT_VALUE_IN_RELEVANCE_STATE",
                 "RELEVANCE_VALUE_IN_CONTAMINANT_CLASS"):
        case = by_name[name]
        result = MODULE.validate_batch({"records": case["records"]}, case["expected_ids"], schema)
        assert result["schema_failure_count"] == 1
        assert any(failure["failure"] == "ENUM" for failure in result["failures"])
    for name in ("DUPLICATE_ID", "MISSING_ID", "EXTRA_ID"):
        case = by_name[name]
        result = MODULE.validate_batch({"records": case["records"]}, case["expected_ids"], schema)
        assert result["identity_valid"] is False
    ordered = by_name["OUT_OF_ORDER_VALID_IDS"]
    result = MODULE.validate_batch({"records": ordered["records"]}, ordered["expected_ids"], schema)
    assert result["valid"] is True
    assert result["provider_returned_order_matches_request_order"] is False
    assert [record["review_unit_id"] for record in result["canonical_records"]] == ordered["expected_ids"]


def test_frozen_contract_preserves_scientific_prompt_and_taxonomy() -> None:
    root = MODULE.RUN
    contract = MODULE.load(root / "pass_b_output_contract_v2.json")
    matrix = MODULE.load(root / "field_enum_domain_matrix.json")
    scientific = MODULE.load(root / "scientific_prompt_immutability_audit.json")
    assert scientific["scientific_prompt_hash_before"] == scientific["scientific_prompt_hash_after"]
    assert scientific["scientific_prompt_byte_identical"] is True
    assert matrix["exact_domain_intersection"] == []
    assert contract["provider_response_format"] == {"type": "json_object"}
    assert MODULE.sha(root / "pass_b_output_contract_v2.json") == (root / "pass_b_output_contract_v2_sha256").read_text().strip()
    source_schema = MODULE.load(MODULE.SOURCE / "neutral_review_output_schema.json")["PASS_B"]
    properties = source_schema["properties"]["records"]["items"]["properties"]
    by_field = {row["field_name"]: row for row in matrix["field_enum_domains"]}
    for field in ("relevance_state", "contaminant_class"):
        assert by_field[field]["exact_allowed_enum_values"] == properties[field]["enum"]


def test_frozen_roots_and_zero_call_firewall() -> None:
    root = MODULE.RUN
    protocol = MODULE.load(root / "harmonized_review_protocol_v4_manifest.json")
    assert MODULE.digest(protocol["aggregate_components"]) == (root / "harmonized_review_protocol_v4_sha256").read_text().strip()
    pairs = [[path.name, MODULE.sha(path)] for path in sorted(root.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14d_sha256"]
    assert MODULE.digest(pairs) == (root / "search_plan_v24_dev_alpha3_14d_sha256").read_text().strip()
    assert MODULE.load(root / "validation.json")["status"] == "PASS"
    assert MODULE.load(root / "arm_firewall_audit.json")["arm_map_accessed"] is False
    assert MODULE.load(root / "metrics_nonexecution_audit.json")["metrics_computed"] is False
    assert MODULE.load(root / "scientific_state_safety_audit.json")["deepseek_calls"] == 0
