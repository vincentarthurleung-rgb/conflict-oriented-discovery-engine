"""Offline tests for alpha3.20E blinded semantic-request preregistration."""

import json
from collections import Counter

from scripts import run_search_plan_v24_alpha320e_semantic_adjudication_prereg_offline as e


def test_upstream_authorities_and_exact_candidate_universe(monkeypatch, tmp_path):
    monkeypatch.setattr(e, "OUT", tmp_path / "not_created")
    state = e.preflight()
    assert len(state["retained"]) == 84
    assert len(state["source_groups"]) == 14
    assert Counter(x["raw"]["variant_id_controller_only"] for x in
                   state["retained"]) == {
        e.d.VARIANT_IDS[0]: 42, e.d.VARIANT_IDS[1]: 42}


def test_blinded_build_has_28_separate_groups(monkeypatch, tmp_path):
    monkeypatch.setattr(e, "OUT", tmp_path / "not_created")
    state = e.preflight()
    built = e.build(state, bytes.fromhex("35" * 32))
    assert len(built["requests"]) == len(built["group_map"]) == 28
    assert len(built["candidate_map"]) == 84
    assert len({x["blinded_group_token"] for x in built["group_map"]}) == 28
    assert len({x["blinded_candidate_token"] for x in built["candidate_map"]}) == 84
    assert all(x["byte_equivalent"] for x in built["context_audit"])
    assert Counter(x["private_variant_id"] for x in built["group_map"]) == {
        e.d.VARIANT_IDS[0]: 14, e.d.VARIANT_IDS[1]: 14}
    for row in built["requests"]:
        visible = row["request"]
        payload = json.loads(visible["messages"][1]["content"].split("\n", 1)[1])
        assert set(payload) == {"blinded_group_token", "source_context", "candidates"}
        assert len(payload["candidates"]) == 3
        assert all(set(x) == {"candidate_token", "neutral_proposition",
                              "exact_body_evidence_quote"} for x in payload["candidates"])
        assert "private_variant_id" not in row
        assert "source_record_token" not in row


def test_response_ownership_and_private_freeze(monkeypatch, tmp_path):
    monkeypatch.setattr(e, "OUT", tmp_path / "freeze")
    state = e.preflight()
    seed = bytes.fromhex("63" * 32)
    built = e.build(state, seed)
    result = e.freeze(state, built, seed)
    assert result["status"] == "completed"
    assert result["provider_calls"] == 0
    assert len(e.rows(e.OUT / "semantic_adjudication_request_manifest.jsonl")) == 28
    assert len(e.rows(e.OUT / "semantic_adjudication_universe_manifest.jsonl")) == 84
    assert (e.OUT / "semantic_group_token_mapping_private.jsonl").stat().st_mode & 0o077 == 0
    assert e.d.c.root_hash(e.OUT, e.ROOT_MARKER) == (
        e.OUT / e.ROOT_MARKER).read_text().strip()
    schema = e.response_envelope()["model_owned_payload_schema"]
    assert "schema_version" not in schema["properties"]
    assert "candidate_reviews" in e.SYSTEM_PROMPT
    assert all(name in e.SYSTEM_PROMPT for name in e.CRITERIA)
    assert set(schema["properties"]["candidate_reviews"]["items"]["properties"][
        "criteria"]["required"]) == set(e.CRITERIA)
