from __future__ import annotations

import json
import shutil
from pathlib import Path

from code_engine.integration.atlas_handoff import ABSTRACT_L2_PROFILE, publish_atlas_handoff
from code_engine.integration.atlas_publish import publish_completed_scientific_run
from code_engine.system_b.explorer.explorer_api import ExplorerAPI
from code_engine.system_b.system_a_sync import sync_system_a


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _abstract_run(root: Path, run_name: str, case_id: str, subject: str = "TP53") -> Path:
    run = root / run_name
    artifacts = run / "artifacts"
    artifacts.mkdir(parents=True)
    row = {
        "schema_version": "l2_core_graph_observation_v1",
        "observation_id": f"obs-{run_name}",
        "claim_id": f"claim-{run_name}",
        "subject": subject,
        "subject_canonical_id": f"gene:{subject}",
        "subject_canonical_name": subject,
        "subject_entity_type": "gene",
        "formal_relation": "inhibits",
        "relation_family": "causal_regulation",
        "object": "apoptosis",
        "object_canonical_id": "process:apoptosis",
        "object_canonical_name": "apoptosis",
        "object_entity_type": "process",
        "direction": "negative",
        "formal_core_graph_eligible": True,
        "graph_observation_eligible": True,
        "conflict_eligible": False,
        "evidence_sentence": f"{subject} inhibits apoptosis.",
        "pmid": run_name,
        "context": {"species": "human"},
    }
    for name, value in {
        "case_domain_profile.json": {"schema_version": "case_domain_profile_v1", "case_id": case_id},
        "search_plan.json": {"schema_version": "search_plan_v1", "query": case_id},
        "replay_manifest.json": {"schema_version": "replay_manifest_v1", "case_id": case_id, "scientific_status": "completed", "final_status": "completed", "created_at": f"2026-01-01T00:00:0{len(run_name) % 9}+00:00", "current_run_calls": {"abstract_l1_provider_calls": 0, "abstract_retrieval_http_calls": 0, "entity_network_calls": {}, "l2_entity_llm_cleaner_calls": 0}},
        "replay_terminal_state_audit.json": {"schema_version": "replay_terminal_state_audit_v1", "final_status": "completed", "completed_at": f"2026-01-01T00:00:0{len(run_name) % 9}+00:00"},
        "l2_abstract_summary.json": {"schema_version": "l2_abstract_summary_v1", "retained_observations": 1},
        "graph_conflict_summary.json": {"schema_version": "graph_conflict_summary_v1", "true_graph_conflict_count": 0},
        "hypothesis_summary.json": {"schema_version": "hypothesis_summary_v1", "formal_hypothesis_count": 0},
        "l2_abstract_observations.json": [row],
    }.items():
        (artifacts / name).write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    for name, rows in {
        "abstract_l1_claims.jsonl": [{"schema_version": "abstract_l1_claim_v1", "claim_id": row["claim_id"], "pmid": run_name, "claim_text": row["evidence_sentence"]}],
        "l2_core_graph_observations.jsonl": [row],
        "l2_graph_observations.jsonl": [row],
        "core_graph_gate_audit.jsonl": [{"schema_version": "core_graph_gate_audit_v1", "observation_id": row["observation_id"], "eligible": True, "reason": "eligible_and_emitted"}],
        "merged_evidence_graph_edges.jsonl": [{"schema_version": "merged_evidence_graph_edge_v1", "edge_id": f"edge-{run_name}"}],
        "merged_evidence_graph_nodes.jsonl": [{"schema_version": "merged_evidence_graph_node_v1", "node_id": f"gene:{subject}"}],
        "graph_conflict_candidates.jsonl": [],
    }.items():
        _jsonl(artifacts / name, rows)
    return run


def _fulltext_run(root: Path, run_name: str, case_id: str) -> Path:
    run = root / run_name
    artifacts = run / "artifacts"
    artifacts.mkdir(parents=True)
    row = {"claim_id": f"c-{run_name}", "evidence_lane": "seed_neighborhood_mechanism", "subject": "A", "predicate": "activates", "object": "B", "relation_class": "causal_regulation", "exploratory_graph_eligible": True, "conflict_eligible": False, "polarity_resolution_status": "resolved", "claim_identity_hash": run_name, "chunk_hash": run_name, "pmid": run_name, "evidence_sentence": "A activates B."}
    for name, rows in {
        "fulltext_core_seed_observations.jsonl": [],
        "fulltext_seed_neighborhood_observations.jsonl": [row],
        "fulltext_reviewable_relations.jsonl": [],
        "fulltext_off_seed_relations.jsonl": [],
        "l35_fulltext_l1_claims.jsonl": [row],
        "fulltext_reentry_audit.jsonl": [row],
    }.items():
        _jsonl(artifacts / name, rows)
    (run / "fulltext_reentry_manifest.json").write_text(json.dumps({"case_id": case_id, "status": "completed", "network_used": False, "api_used": False, "created_at": "2026-01-01T00:00:00+00:00", "input_fulltext_claim_count": 1, "core_seed_relation_count": 0, "seed_neighborhood_mechanism_count": 1, "reviewable_context_relation_count": 0, "off_seed_relation_count": 0, "exploratory_graph_eligible_count": 1, "conflict_eligible_count": 0}), encoding="utf-8")
    return run


def _source_hashes(output: Path) -> dict[str, tuple[str, str, str]]:
    current = json.loads((output / "current_projection.json").read_text())
    manifest = json.loads((output / current["projection_relative_path"] / "projection_manifest.json").read_text())
    return {row["case_id"]: (row["manifest_hash"], row["source_run_id"], row["handoff_profile"]) for row in manifest["source_manifests"]}


def test_publish_completed_run_updates_one_case_and_preserves_aggregate_sources(tmp_path):
    runs = tmp_path / "runs"
    output = tmp_path / "atlas"
    a = _abstract_run(runs, "run-a1", "case-a", "AAA")
    b1 = _abstract_run(runs, "run-b1", "case-b", "BBB")
    c = _abstract_run(runs, "run-c1", "case-c", "CCC")
    for run in (a, b1, c):
        publish_atlas_handoff(run, runs_root=runs, handoff_profile=ABSTRACT_L2_PROFILE)
    first = sync_system_a(runs_root=runs, output_root=output, no_database_write=True)
    before = _source_hashes(output)
    b2 = _abstract_run(runs, "run-b2", "case-b", "B2B")
    result = publish_completed_scientific_run(b2, atlas_config={"runs_root": runs, "output_root": output}, publication_source="replay_case_from_stage")
    after = _source_hashes(output)
    assert result["atlas_sync_status"] == "completed"
    assert result["projection_id"] != first["current_projection_id"]
    assert after["case-b"][0] != before["case-b"][0]
    assert after["case-a"] == before["case-a"]
    assert after["case-c"] == before["case-c"]
    assert ExplorerAPI(output).dispatch("/api/case/case-b")[1]["case_content_hash"] == result["case_content_hash"]
    repeated = publish_completed_scientific_run(b2, atlas_config={"runs_root": runs, "output_root": output}, publication_source="replay_case_from_stage")
    assert repeated["sync_status"] == "no_op"
    assert repeated["projection_id"] == result["projection_id"]


def test_fulltext_active_case_is_not_downgraded_by_abstract_handoff(tmp_path):
    runs = tmp_path / "runs"
    output = tmp_path / "atlas"
    fulltext = _fulltext_run(runs, "fulltext-a", "case-a")
    abstract_b = _abstract_run(runs, "run-b1", "case-b", "BBB")
    for run, profile in ((fulltext, None), (abstract_b, ABSTRACT_L2_PROFILE)):
        kwargs = {"runs_root": runs}
        if profile:
            kwargs["handoff_profile"] = profile
        publish_atlas_handoff(run, **kwargs)
    sync_system_a(runs_root=runs, output_root=output, no_database_write=True)
    before = _source_hashes(output)
    abstract_a = _abstract_run(runs, "run-a-abstract", "case-a", "AAA")
    result = publish_completed_scientific_run(abstract_a, atlas_config={"runs_root": runs, "output_root": output}, publication_source="replay_case_from_stage")
    after = _source_hashes(output)
    assert result["sync_status"] == "no_op"
    assert after["case-a"] == before["case-a"]
    assert after["case-a"][2] == "fulltext_reentry"


def test_publication_skips_when_atlas_not_configured(tmp_path):
    run = _abstract_run(tmp_path / "runs", "run-a1", "case-a", "AAA")
    result = publish_completed_scientific_run(run, atlas_config={}, publication_source="replay_case_from_stage")
    assert result["atlas_sync_status"] == "skipped"
    assert result["atlas_sync_reason"] == "atlas_not_configured"
