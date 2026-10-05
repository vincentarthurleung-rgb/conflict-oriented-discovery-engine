"""Offline preflight and invariants for the full blinded E1R replication."""

from pathlib import Path

from scripts import run_search_plan_v24_alpha320e1r_full_blinded_semantic_replication_prereg_offline as r


def test_response_envelope_v2_preserves_scientific_payload_schema() -> None:
    old = r.obj(r.e.OUT /
        "development_semantic_adjudication_response_envelope_v1.json")
    new = r.envelope_v2()
    assert new["model_owned_payload_schema"] == old["model_owned_payload_schema"]
    assert new["serialization_contract"]["trailing_commas_allowed"] is False
    assert new["provider_native_json_schema_mode_activated"] is False


def test_parser_rejects_malformed_response_without_repair() -> None:
    schema = r.envelope_v2()["model_owned_payload_schema"]
    parsed, validity, _ = r.validate_replication_response(
        '{"candidate_reviews":[],}', "stop", ["a", "b", "c"], schema)
    assert parsed is None
    assert validity["reason"] == "SEMANTIC_RESPONSE_MALFORMED_JSON"


def test_new_blinded_universe_matches_frozen_science(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(r, "OUT", tmp_path / "not-created")
    state = r.preflight()
    built = r.build(state, bytes(range(32)))
    assert len(built["request_rows"]) == 28
    assert len(built["candidate_mapping"]) == 84
    assert len(built["context_rows"]) == 14
    assert all(row["exactly_matches_one_e_group"] for row in
               built["equivalence_rows"])
    assert all(row["differs_from_e1_candidate_order"] for row in
               built["permutations"])
    assert not ({row["blinded_group_token"] for row in built["request_rows"]}
                & state["old_group_tokens"])
    assert not ({row["blinded_candidate_token"] for row in
                 built["candidate_mapping"]} & state["old_candidate_tokens"])
    assert all(row["request"]["response_format"] == {"type": "json_object"}
               for row in built["request_rows"])
