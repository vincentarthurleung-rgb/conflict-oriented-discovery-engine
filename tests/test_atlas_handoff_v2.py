from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from code_engine.integration.atlas_handoff import (
    HANDOFF_SCHEMA_VERSION,
    LEGACY_HANDOFF_SCHEMA_VERSION,
    HandoffError,
    canonical_json,
    publish_atlas_handoff,
    validate_handoff,
)
from code_engine.system_b.evaluation.claim_sampling import create_pilot_sample, evaluation_readiness
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.system_a_sync import sync_system_a


def _jsonl(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _run(root: Path, *, reasoning=True, context=True) -> Path:
    run = root / "run"
    artifacts = run / "artifacts"
    row = {"claim_id": "c1", "evidence_lane": "seed_neighborhood_mechanism", "subject": "A", "predicate": "activates", "object": "B", "relation_class": "causal_regulation", "exploratory_graph_eligible": True, "conflict_eligible": False, "polarity_resolution_status": "resolved", "claim_identity_hash": "identity", "chunk_hash": "chunk", "pmid": "1", "section_type": "results"}
    for name, rows in {
        "fulltext_core_seed_observations.jsonl": [], "fulltext_seed_neighborhood_observations.jsonl": [row],
        "fulltext_reviewable_relations.jsonl": [], "fulltext_off_seed_relations.jsonl": [],
        "l35_fulltext_l1_claims.jsonl": [row], "fulltext_reentry_audit.jsonl": [row],
    }.items():
        _jsonl(artifacts / name, rows)
    if reasoning:
        _jsonl(artifacts / "fulltext_reasoning_traces.jsonl", [{"schema_version": "fulltext_reasoning_trace_v1", "claim_id": "c1", "trace_status": "unsupported_by_retrieved_passages", "reasoning_steps": [], "missing_links": [{"reason": "reasoning_extractor_not_executed"}]}])
    if context:
        _jsonl(artifacts / "fulltext_context_consolidations.jsonl", [{"schema_version": "fulltext_context_consolidation_v1", "claim_id": "c1", "consolidated_context": {"species": ["mouse"], "dose": []}, "field_provenance": {"species": [{"source": "claim"}]}}])
    (run / "fulltext_reentry_manifest.json").write_text(json.dumps({"case_id": "case", "status": "completed", "network_used": False, "api_used": False, "input_fulltext_claim_count": 1, "core_seed_relation_count": 0, "seed_neighborhood_mechanism_count": 1, "reviewable_context_relation_count": 0, "off_seed_relation_count": 0, "exploratory_graph_eligible_count": 1, "conflict_eligible_count": 0}), encoding="utf-8")
    return run


def test_v1_v2_capability_effectiveness_and_legacy_domain(tmp_path):
    root = tmp_path / "runs"; root.mkdir(); run = _run(root)
    v1 = publish_atlas_handoff(run, runs_root=root, schema_version=LEGACY_HANDOFF_SCHEMA_VERSION)
    assert validate_handoff(v1["manifest_path"], runs_root=root)["manifest"]["schema_version"] == LEGACY_HANDOFF_SCHEMA_VERSION
    Path(v1["manifest_path"]).unlink(); (run / "artifacts/ATLAS_READY").unlink()
    v2 = publish_atlas_handoff(run, runs_root=root)
    assert v2["manifest"]["schema_version"] == HANDOFF_SCHEMA_VERSION
    assert v2["manifest"]["domain_classification"]["status"] == "legacy_unknown"
    assert v2["manifest"]["capabilities"]["reasoning_trace"]["status"] == "produced_but_unusable"
    assert v2["manifest"]["capabilities"]["reasoning_trace"]["usable_record_count"] == 0
    assert v2["manifest"]["capabilities"]["context_consolidation"]["status"] == "available"


def test_v2_identity_ignores_generated_at_and_output_path(tmp_path):
    root = tmp_path / "runs"; root.mkdir(); run = _run(root)
    published = publish_atlas_handoff(run, runs_root=root)
    path = Path(published["manifest_path"])
    first = validate_handoff(path, runs_root=root)
    manifest = json.loads(path.read_text()); manifest["generated_at"] = "2099-01-01T00:00:00Z"
    path.write_bytes(canonical_json(manifest))
    (path.parent / "ATLAS_READY").write_bytes(canonical_json({"schema_version": HANDOFF_SCHEMA_VERSION, "manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    second = validate_handoff(path, runs_root=root)
    assert first["manifest_hash"] != second["manifest_hash"]
    assert first["identity_hash"] == second["identity_hash"]
    outputs = [tmp_path / "one", tmp_path / "two"]
    reports = [sync_system_a(runs_root=root, output_root=output, no_database_write=True) for output in outputs]
    assert reports[0]["current_projection_id"] == reports[1]["current_projection_id"]


def test_failed_refresh_does_not_switch_current_projection(tmp_path):
    root = tmp_path / "runs"; root.mkdir(); run = _run(root)
    published = publish_atlas_handoff(run, runs_root=root)
    output = tmp_path / "output"
    sync_system_a(runs_root=root, output_root=output, no_database_write=True)
    registry = (output / "current_projection.json").read_bytes()
    manifest_path = Path(published["manifest_path"])
    manifest = json.loads(manifest_path.read_text()); manifest["generated_at"] = "corrupt-without-ready-update"
    manifest_path.write_bytes(canonical_json(manifest))
    with pytest.raises(HandoffError, match="current_projection_source_missing"):
        sync_system_a(runs_root=root, output_root=output, no_database_write=True)
    assert (output / "current_projection.json").read_bytes() == registry
    failure = json.loads(next((output / "sync_audit").glob("failed_*.json")).read_text())
    assert failure["error_code"] == "current_projection_source_missing"


def test_conditional_sampling_is_reproducible_and_blocks_f1():
    rows = [{"source_unit_id": f"su{i}", "paper_id": f"p{i//2}", "case_id": "c", "domain_snapshot": {"domain_id": "d"}, "source_scope": "fulltext", "section_type": "results", "text_hash": f"h{i}"} for i in range(10)]
    first = create_pilot_sample(rows, sample_size=4, random_seed=17)
    second = create_pilot_sample(list(reversed(rows)), sample_size=4, random_seed=17)
    assert [row["source_unit_id"] for row in first["units"]] == [row["source_unit_id"] for row in second["units"]]
    assert all(row["inclusion_probability"] == .4 and row["sampling_weight"] == 2.5 for row in first["units"])
    readiness = evaluation_readiness(rows)
    assert readiness["frame_scope"] == "selected_for_l1_extraction"
    assert readiness["claim_recall"]["status"] == "needs_exhaustive_gold"
    assert readiness["claim_f1"]["value"] is None


def test_domain_api_uses_projection_metadata_without_case_name_inference(tmp_path):
    root = tmp_path
    for name in ("display_entities_v2.jsonl", "display_triples_v2.jsonl", "display_chains_v2.jsonl", "case_focused_triples.jsonl", "case_focused_chains.jsonl", "triple_evidence_links.jsonl"):
        _jsonl(root / name, [])
    (root / "case_metadata.json").write_text(json.dumps({"items": [{"case_id": "case_without_keywords", "domain_classification": {"primary_domain_id": "recorded_domain", "primary_domain_label": "Recorded", "status": "classified"}, "capabilities": {}}]}))
    api = ExplorerAPI(root)
    domains = api.dispatch("/api/domains")[1]
    assert domains["items"][0]["domain_id"] == "recorded_domain"
    assert api.dispatch("/api/domains/recorded_domain/cases")[1]["items"][0]["case_id"] == "case_without_keywords"


def test_owner_can_create_idempotent_conditional_claim_sample(tmp_path):
    root = tmp_path / "projection"; root.mkdir()
    for name in ("display_entities_v2.jsonl", "display_triples_v2.jsonl", "display_chains_v2.jsonl", "case_focused_triples.jsonl", "case_focused_chains.jsonl", "triple_evidence_links.jsonl"):
        _jsonl(root / name, [])
    rows = [{"source_unit_id": f"su{i}", "paper_id": f"p{i}", "case_id": "case", "domain_snapshot": {"domain_id": "pathway_biology"}, "source_scope": "fulltext", "section_type": "results", "text_hash": f"h{i}"} for i in range(6)]
    _jsonl(root / "evaluation_staging/source_text_unit_frame.jsonl", rows)
    api = ExplorerAPI(root)
    body = {"sample_size": 3, "random_seed": 7, "domain_ids": ["pathway_biology"]}
    status, created = api.dispatch("/api/owner/claim-evaluation/pilot-samples", method="POST", body=body)
    assert status == 201 and created["creation_status"] == "created"
    status, repeated = api.dispatch("/api/owner/claim-evaluation/pilot-samples", method="POST", body=body)
    assert status == 201 and repeated["creation_status"] == "no_op"
    assert repeated["batch_id"] == created["batch_id"]
    assert repeated["conditional_only"] is True
