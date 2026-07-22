import copy
import hashlib
import json

from code_engine.fulltext import fulltext_l1_v3_offline_rehydrate as offline
from code_engine.schemas.fulltext_observation_draft import fulltext_l1_draft_prompt_examples


def _legacy_reference(reference):
    return {"text": reference.get("model_selected_excerpt_raw"),
            "evidence_anchor_ids": reference["evidence_anchor_ids"],
            "span_type": reference["span_type"]}


def _legacy_payload(block_id, *, kind):
    _, payload = fulltext_l1_draft_prompt_examples()
    if kind == "empty":
        return {"schema_version": offline.LEGACY_DRAFT_SCHEMA_VERSION, "experimental_observations": []}
    row = payload["experimental_observations"][0]
    for reference in [*row["evidence_references"], row["observation"]["evidence"],
                      row["measurement"]["evidence"], row["interventions"][0]["evidence"]]:
        reference["evidence_anchor_ids"] = [f"{block_id}:S0001"]
        reference["model_selected_excerpt_raw"] = "slightly rewritten excerpt"
    if kind == "multi":
        row["interventions"].append(copy.deepcopy(row["interventions"][0]))
        row["interventions"][1]["role_raw"] = "secondary"
        row["combination_mode_raw"] = "concurrent"
    elif kind == "reviewable":
        row["interventions"][0]["intervention_type_raw"] = "novel activation mode"
    elif kind == "mixed":
        row["candidate_relation"]["lexical_direction_raw"] = "mixed"
        row["observation"]["lexical_direction_raw"] = "mixed"
    legacy = copy.deepcopy(payload)
    legacy["schema_version"] = offline.LEGACY_DRAFT_SCHEMA_VERSION
    old = legacy["experimental_observations"][0]
    old["evidence_texts"] = [_legacy_reference(x) for x in old.pop("evidence_references")]
    old["observation"]["evidence_text"] = _legacy_reference(old["observation"].pop("evidence"))
    old["measurement"]["evidence_text"] = _legacy_reference(old["measurement"].pop("evidence"))
    old["interpretation_evidence_text"] = old.pop("interpretation_evidence")
    for intervention in old["interventions"]:
        evidence = intervention.pop("evidence")
        intervention["evidence_text"] = _legacy_reference(evidence) if evidence else None
    return legacy


def test_five_shape_offline_rehydrate_is_zero_call_idempotent_and_preserves_raw(tmp_path, monkeypatch):
    run = tmp_path / "run"; artifacts = run / "artifacts"
    cache = artifacts / "cache/fulltext_l1_v3_provider_smoke"; cache.mkdir(parents=True)
    (artifacts / "fulltext_l1_v2_summary.json").write_text(json.dumps({"publication_allowed": False}))
    kinds = ["single", "multi", "reviewable", "empty", "mixed"]
    results = []
    inventory = {}
    raw_hashes = {}
    for (block_id, role), kind in zip(offline.LEGACY_FROZEN_SELECTION, kinds):
        key = hashlib.sha256(block_id.encode()).hexdigest()
        payload = _legacy_payload(block_id, kind=kind)
        raw = json.dumps(payload)
        raw_path = cache / f"{key}.raw_response.txt"
        draft_path = cache / f"{key}.draft.json"
        raw_path.write_text(raw); draft_path.write_text(json.dumps(payload))
        raw_hashes[block_id] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        results.append({"block_id": block_id, "selection_role": role, "cache_identity": key})
        inventory[block_id] = {
            "block": {"block_id": block_id, "text": "CURRENT_RESULTS: Authoritative source sentence.",
                      "chunk_hash": f"hash-{block_id}", "section": {"section_title": "Results"}},
            "paper": {"paper_id": block_id, "pmcid": block_id.split("_")[0]},
            "source_fulltext_hash": f"source-{block_id}", "article_path": "article_text.json",
        }
    (artifacts / "fulltext_l1_v3_provider_smoke_results.json").write_text(json.dumps({
        "origin": "native_prompt_v6_formal_v3_provider_output", "results": results,
    }))
    (artifacts / "fulltext_l1_v3_provider_smoke_preflight.json").write_text(json.dumps({
        "prompt_version": offline.LEGACY_PROMPT_VERSION,
        "draft_schema_version": offline.LEGACY_DRAFT_SCHEMA_VERSION,
    }))
    monkeypatch.setattr(offline, "_resolve_inventory", lambda _run: (inventory, {}))
    first = offline.offline_rehydrate(run)
    artifact_hash = hashlib.sha256((artifacts / offline.SUMMARY_ARTIFACT).read_bytes()).hexdigest()
    second = offline.offline_rehydrate(run)
    assert first == second
    assert hashlib.sha256((artifacts / offline.SUMMARY_ARTIFACT).read_bytes()).hexdigest() == artifact_hash
    assert first["scanned_blocks"] == first["draft_valid_blocks"] == 5
    assert first["raw_observation_count"] == first["formal_valid_observation_count"] == 4
    assert first["formal_complete_blocks"] == 5 and first["formal_rejected_count"] == 0
    assert first["anchor_excerpt_mismatch_count"] > 0
    assert first["api_calls"] == first["network_calls"] == first["downloads"] == 0
    assert first["all_formal_evidence_from_registry"] is True
    assert first["scientific_input_complete"] is False and first["publication_allowed"] is False
    for block_id, _ in offline.LEGACY_FROZEN_SELECTION:
        key = hashlib.sha256(block_id.encode()).hexdigest()
        assert hashlib.sha256((cache / f"{key}.raw_response.txt").read_bytes()).hexdigest() == raw_hashes[block_id]
