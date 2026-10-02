"""Read-only regression checks for the frozen alpha3.20B request preregistration."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
MASTER = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_20_post_alpha3_19_development_master_preregistration_offline"
V3 = ROOT / "runs/20261001_search_plan_v24_dev_alpha3_18b1_grounding_contract_consistency_audit_offline/builder_output_schema_v3.json"
A20 = ROOT / "runs/20261002_search_plan_v24_dev_alpha3_20a_evidence_reference_v4_offline_validation"


def lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_full_v4_schema_changes_only_evidence_fragment():
    historical = json.loads(V3.read_text())["schema"]
    expected = copy.deepcopy(historical)
    fragment = json.loads((A20 / "builder_output_schema_v4_evidence_fragment.json").read_text())[
        "model_generated_candidate_evidence_schema"]["properties"]["construction_evidence_span"]
    expected["properties"]["candidates"]["items"]["properties"][
        "construction_evidence_span"] = fragment
    actual = json.loads((OUT / "builder_output_schema_v4.json").read_text())["schema"]
    assert actual == expected
    assert actual["properties"]["candidates"]["minItems"] == 0
    assert actual["properties"]["candidates"]["maxItems"] == 3
    assert set(fragment["properties"]) == {"exact_text"}
    assert fragment["required"] == ["exact_text"]


def test_42_source_major_requests_and_variant_difference_firewall():
    variants = json.loads((MASTER / "bounded_prompt_variant_policy.json").read_text())["variants"]
    combined = lines(OUT / "alpha3_20c_combined_request_manifest.jsonl")
    assert len(combined) == 42
    assert [row["execution_ordinal"] for row in combined] == list(range(1, 43))
    for source_index in range(14):
        triplet = combined[source_index * 3:source_index * 3 + 3]
        assert [row["variant_index"] for row in triplet] == [1, 2, 3]
        assert len({row["private_source_token"] for row in triplet}) == 1
        assert len({row["request"]["messages"][1]["content"] for row in triplet}) == 1
        assert len({row["scientific_source_input_sha256"] for row in triplet}) == 1
        normalized = []
        for row, variant in zip(triplet, variants, strict=True):
            request = copy.deepcopy(row["request"])
            assert request["model"] == "deepseek-flash"
            assert request["thinking"] == {"type": "enabled"}
            assert request["reasoning_effort"] == "high"
            assert not any(key in request for key in ("temperature", "top_p", "max_tokens"))
            system = request["messages"][0]["content"]
            instruction = variant["abstraction_instruction"]
            assert system.count(instruction) == 1
            request["messages"][0]["content"] = system.replace(instruction, "<VARIANT>")
            normalized.append(request)
        assert normalized[0] == normalized[1] == normalized[2]


def test_hashes_and_zero_call_freeze():
    validation = json.loads((OUT / "validation.json").read_text())
    assert validation["variant_request_confound_count"] == 0
    assert validation["planned_development_builder_calls"] == 42
    assert validation["builder_calls"] == validation["provider_calls"] == 0
    for stem in ("builder_grounding_contract_v4", "builder_output_schema_v4",
                 "prompt_variant_1", "prompt_variant_2", "prompt_variant_3"):
        suffix = ".txt" if stem.startswith("prompt_") else ".json"
        actual = hashlib.sha256((OUT / (stem + ("_full_template" if suffix == ".txt" else "")
                                       + suffix)).read_bytes()).hexdigest()
        assert actual == (OUT / (stem + "_sha256")).read_text().strip()
    actual = hashlib.sha256((OUT / "alpha3_20c_combined_request_manifest.jsonl").read_bytes()).hexdigest()
    assert actual == (OUT / "alpha3_20c_combined_request_manifest_sha256").read_text().strip()
