import hashlib
import json
from pathlib import Path

from code_engine.search.retrieval_surface_compiler_v2 import serialize_pubmed_query


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_8_conjunctive_rigidity_autopsy_offline"


def load(name):
    return json.loads((RUN / name).read_text())


def rows(name):
    return [json.loads(line) for line in (RUN / name).read_text().splitlines() if line]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def test_all_frozen_ast_queries_round_trip_without_changing_query_text():
    inventory = rows("query_ast_inventory.jsonl")
    burden = rows("mandatory_lexical_burden.jsonl")
    assert len(inventory) == len(burden) == 25
    assert len({row["query_id"] for row in inventory}) == 25
    for row in inventory:
        assert serialize_pubmed_query(row["ast"]) == row["serialized_query"]
        assert hashlib.sha256(row["serialized_query"].encode()).hexdigest() == row["query_sha256"]
        assert row["top_level_and_child_count"] >= 4


def test_translation_audit_covers_all_frozen_successful_responses():
    audit = load("frozen_ncbi_translation_audit.json")
    assert audit["query_count"] == audit["proximity_tags_retained_count"] == 25
    assert audit["warning_or_error_count"] == 0
    assert len(audit["queries"]) == 25
    for row in audit["queries"]:
        assert row["query_count"] == 0
        assert row["classification"].startswith("PROXIMITY_SYNTAX_RETAINED")
        assert row["errors"] is None


def test_ast_compact_nodes_are_distinguished_from_executed_zero_window_clauses():
    compact = load("compact_concept_zero_window_audit.json")
    inventory = rows("query_ast_inventory.jsonl")
    assert compact["ast_node_count"] == 74
    assert compact["independently_serialized_zero_window_operator_count"] == 17
    assert compact["queries_with_one_or_more_executed_zero_window_operators"] == 13
    assert sum(row["effective_zero_window_operator_count"] for row in inventory) == 17
    assert sum(row["compact_concept_count"] for row in inventory) == 74
    assert all(row["serialization_context"] != "UNRESOLVED" for row in compact["nodes"])


def test_diagnosis_is_scoped_and_historical_roots_are_preserved():
    summary = load("summary.json")
    preservation = load("historical_corpus_preservation_audit.json")
    safety = load("scientific_state_safety_audit.json")
    assert summary["protocol_compliance"] == "PASS"
    assert summary["retrieval_surface_v2_candidate_acquisition"] == "EMPTY"
    assert summary["complete_query_count"] == summary["zero_hit_query_count"] == 25
    assert summary["zero_hit_case_count"] == 8
    assert summary["primary_failure_class"] == "MULTIPLE_RETRIEVAL_RIGIDITY_DEFECTS"
    assert summary["next_stage_recommendation"] == "DESIGN_SEARCH_CONSTRAINT_ALLOCATION_V1_OFFLINE"
    assert summary["pubmed_syntax_defect_detected"] is False
    assert preservation["historical_assets_modified"] is False
    for key in ("network_calls", "retrieval_calls", "provider_calls", "llm_calls",
                "query_modifications", "known_pmid_checks", "production_case_specific_rules"):
        assert safety[key] == 0


def test_alpha38_root_recomputes_from_every_component():
    validation = load("validation.json")
    assert validation["status"] == "PASS"
    for name, expected in validation["aggregate_components"]:
        assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == expected
    actual = hashlib.sha256(canonical(validation["aggregate_components"])).hexdigest()
    assert actual == validation["search_plan_v24_dev_alpha3_8_sha256"]
    assert actual == (RUN / "search_plan_v24_dev_alpha3_8_sha256").read_text().strip()
