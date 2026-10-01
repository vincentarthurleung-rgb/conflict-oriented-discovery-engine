"""No-provider regression checks for the prospective BODY-only Builder V3."""
import json

import pytest

from scripts import search_plan_v24_alpha318b1_audit_grounding_contract_offline as audit
from scripts import search_plan_v24_alpha318b_post_builder_prechecks as checks


@pytest.fixture(autouse=True)
def isolate_preregistration_output_guard(tmp_path, monkeypatch):
    # Read-only preflight checks remain testable after the real freeze exists.
    monkeypatch.setattr(audit, "OUT", tmp_path / "not-created")


def test_authority_and_structural_observation_are_frozen():
    state = audit.preflight()
    assert state["fields"] == {"abstract": 70}
    assert state["body_contract"]["prospective_post_validation_body_only_rule"]
    assert state["document_contract"]["body_only_candidate_grounding"]
    assert state["amendment"]["required_additional_instruction"] not in state["template_v2"]


def test_synthetic_cases_cover_required_a_through_j():
    state = audit.preflight()
    cases, result = audit.synthetic_cases(state["schema_v2"], audit.v3_schema(state["schema_v2"]))
    assert result == {"synthetic_case_count": 12, "passed": 12, "failed": 0,
                      "all_pass": True, "model_calls": 0}
    assert {case["case"][0] for case in cases} == set("ABCDEFGHIJ")
    assert all(case["pass"] for case in cases)


def test_v2_abstract_output_is_historical_not_implicitly_upgraded():
    state = audit.preflight()
    schema_v2 = state["schema_v2"]
    schema_v3 = audit.v3_schema(schema_v2)
    token = "src_" + "a" * 64
    candidate = {"actor_or_intervention": "synthetic intervention", "action": "treatment",
        "relation_direction": "DECREASES", "response_or_endpoint": "synthetic endpoint",
        "biological_unit": "cultured cells", "species": None,
        "intrinsic_conditioning": None, "intrinsic_therapy_context": None,
        "intrinsic_disease_or_genotype_context": None,
        "neutral_proposition": "Synthetic intervention decreases synthetic endpoint.",
        "construction_evidence_span": {"source_field": "abstract",
            "exact_text": "Synthetic text.", "start_offset": 0, "end_offset": 15}}
    raw = json.dumps({"source_record_token": token, "candidates": [candidate]}).encode()
    assert checks.validate_builder_response(raw, token, schema_v2)["candidates"]
    with pytest.raises(ValueError, match="BUILDER_SCHEMA_ENUM"):
        checks.validate_builder_response(raw, token, schema_v3)
    assert schema_v2["properties"]["candidates"]["items"]["properties"][
        "construction_evidence_span"]["properties"]["source_field"]["enum"] == ["abstract", "body"]


def test_exact_28_v3_requests_only_change_grounding_interface():
    built = audit.build()
    assert len(built["requests"]) == len(built["deltas"]) == 28
    assert all(row["document_sha256_unchanged"] and row["scientific_task_text_unchanged"]
               and row["grounding_instruction_added_only"] and
               row["schema_changed_only_source_field_enum_to_body"]
               for row in built["deltas"])
    original = built["audit"]["frozen"]["requests"][0]["request"]
    amended = built["requests"][0]["request"]
    assert amended["messages"][0]["content"].startswith(original["messages"][0]["content"])
    assert amended["messages"][1]["content"].split("Output schema: ", 1)[0] == (
        original["messages"][1]["content"].split("Output schema: ", 1)[0])
    assert {key: value for key, value in amended.items() if key != "messages"} == {
        key: value for key, value in original.items() if key != "messages"}
