import hashlib
import json
from pathlib import Path

from code_engine.context_attribution.conflict_candidate.targeted_network_discovery_v1_candidate import (
    ProviderExtractionCandidateV1,
    contains_all_groups_v1,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260827_proposition_driven_targeted_network_discovery_smoke_v1"
ART = RUN / "artifacts"
PROTOCOL = ROOT / "runs/20260826_proposition_driven_targeted_expansion_protocol_v1_offline/artifacts"
ORDER = [
    "future_proposition_target_v1:45b8c00ad24ef8f5",
    "future_proposition_target_v1:84faa47f886bfd88",
    "future_proposition_target_v1:4257c6640102256b",
    "future_proposition_target_v1:64f78bb753d6c662",
]


def read_json(name):
    return json.loads((ART / name).read_text())


def read_rows(name):
    return [json.loads(line) for line in (ART / name).read_text().splitlines() if line]


def test_frozen_specification_is_hash_bound_and_target_order_is_exact():
    baseline = read_json("baseline.json")
    assert baseline["target_order"] == ORDER
    assert baseline["frozen_specification_sha256"] == hashlib.sha256(
        (PROTOCOL / "targeted_retrieval_specifications_v1.jsonl").read_bytes()
    ).hexdigest()


def test_executed_query_is_direction_neutral_and_preserved():
    queries = read_rows("executed_retrieval_queries.jsonl")
    assert len(queries) == 1
    assert queries[0]["target_id"] == ORDER[0]
    assert queries[0]["primary_direction_terms_used"] == []
    assert not any(term in queries[0]["exact_query"].casefold() for term in ("contradictory", "opposite", "conflicting", "controversial"))
    raw = ROOT / queries[0]["raw_asset"]
    assert raw.is_file()
    assert hashlib.sha256(raw.read_bytes()).hexdigest() == queries[0]["raw_sha256"]


def test_budget_accounting_stays_below_every_ceiling():
    accounting = read_json("retrieval_budget_accounting.json")
    metrics = accounting["metrics"]
    assert metrics["metadata_candidates_inspected"] == 9 <= 48
    assert metrics["abstracts_inspected"] == 6 <= 24
    assert metrics["fulltexts_downloaded"] == 1 <= 8
    assert accounting["budget_exceeded"] is False
    for row in read_rows("target_execution_ledger.jsonl"):
        assert row["metadata_inspected"] <= 12
        assert row["abstracts_inspected"] <= 6
        assert row["fulltexts_acquired"] <= 2


def test_publication_independence_is_checked_before_recommendation():
    audits = {row["candidate_id"]: row for row in read_rows("publication_independence_audit.jsonl")}
    candidates = read_rows("provider_extraction_candidates_v1.jsonl")
    assert len(candidates) == 1
    candidate_id = f"pubmed:{candidates[0]['publication_identity']['pmid']}"
    assert audits[candidate_id]["independence_state"] == "independent_publication"
    assert audits[candidate_id]["checked_before_extraction_recommendation"] is True
    assert candidates[0]["publication_independence_state"] == "independent_publication"


def test_abstract_screen_is_retrieval_only_and_direction_blind():
    rows = read_rows("abstract_proposition_screen.jsonl")
    assert len(rows) == 6
    assert all(row["screen_state"] == "possible_same_proposition" for row in rows)
    assert all(row["formal_alignment_inferred"] is False for row in rows)
    assert all(row["direction_used_for_admission"] is False for row in rows)


def test_fulltext_snapshot_is_preserved_and_hash_valid():
    acquisitions = read_rows("fulltext_acquisition_inventory.jsonl")
    assert len(acquisitions) == 1
    row = acquisitions[0]
    assert row["downloaded"] is True
    assert row["availability"] == "usable_pmc_fulltext"
    snapshot = ROOT / row["fulltext_snapshot"]
    assert snapshot.is_file()
    assert hashlib.sha256(snapshot.read_bytes()).hexdigest() == row["fulltext_sha256"]
    assert row["pmid"] == "37744426"
    assert row["pmcid"] == "PMC10515557"


def test_local_fulltext_screen_does_not_adjudicate_direction():
    rows = read_rows("fulltext_proposition_screen.jsonl")
    assert len(rows) == 1
    assert rows[0]["screen_state"] == "fulltext_possible_but_requires_extraction"
    assert rows[0]["deterministic_local_screen_only"] is True
    assert rows[0]["direction_evaluated"] is False
    assert rows[0]["provider_called"] is False


def test_provider_candidate_is_strict_cache_miss_and_unauthorized():
    candidate = ProviderExtractionCandidateV1.model_validate(read_rows("provider_extraction_candidates_v1.jsonl")[0])
    assert candidate.cache_state == "miss_no_sufficient_matching_extraction"
    assert candidate.duplicate_state == "not_known_duplicate"
    assert candidate.estimated_provider_call_count == 1
    assert candidate.retry_count == 0
    assert candidate.execution_authorized is False
    assert candidate.provider_executed is False


def test_provider_plan_has_one_call_zero_retry_and_cache_prerequisite():
    plan = read_json("provider_extraction_smoke_plan.json")
    assert plan["candidate_count"] == plan["planned_provider_calls"] == 1
    assert plan["maximum_attempts_per_source"] == 1
    assert plan["retry_count"] == 0
    assert plan["cache_prerequisite"]
    assert plan["execution_authorized"] is False
    assert plan["provider_calls_executed"] == plan["llm_calls_executed"] == 0


def test_early_stop_preserves_unspent_target_budgets():
    ledger = read_rows("target_execution_ledger.jsonl")
    assert [row["target_id"] for row in ledger] == ORDER
    assert ledger[0]["stop_reason"] == "strong_provider_extraction_candidate_found"
    assert all(row["stop_reason"] == "global_early_stop_provider_smoke_informative" for row in ledger[1:])
    assert all(row["budget_consumed"] == {"abstract": 0, "fulltext": 0, "metadata": 0} for row in ledger[1:])


def test_decision_does_not_infer_a_scientific_answer():
    decision = read_json("discovery_smoke_decision.json")
    assert decision["decision"] == "PROVIDER_EXTRACTION_SMOKE_JUSTIFIED"
    assert decision["scientific_answer_inferred"] is False
    assert decision["contradiction_adjudicated"] is False
    assert decision["provider_execution_authorized"] is False


def test_network_receipt_has_only_four_allowed_calls_and_no_provider():
    receipt = json.loads((RUN / "retrieval_assets/execution_receipt.json").read_text())
    assert receipt["authorized_by_user"] is True
    assert [event["kind"] for event in receipt["events"]] == ["metadata_search", "metadata_summary", "abstract_fetch", "fulltext_download"]
    assert receipt["provider_calls"] == receipt["llm_calls"] == 0
    assert all("api_key" not in event["url"].casefold() for event in receipt["events"])


def test_historical_state_is_unchanged():
    safety = read_json("scientific_state_safety_audit.json")
    assert safety["historical_assets_modified"] is False
    assert safety["candidate_pairs_modified"] is False
    assert safety["formal_v3_modified"] is False
    assert safety["historical_candidate_count_after"] == 11
    assert safety["formal_conflict_count_after"] == 0
    assert safety["entity_integrity_claims_blocked"] == 241
    assert safety["entity_integrity_signals_blocked"] == 2
    assert safety["pi3k"] == {"f389_state": "manual_scientific_review", "signal_40f_state": "historically_blocked"}


def test_manifest_hashes_every_artifact_and_retrieval_asset():
    manifest = read_json("manifest.json")
    assert manifest["all_required_artifacts_present"] is True
    assert manifest["required_artifact_count"] == 17
    for row in manifest["artifacts_and_retrieval_assets"]:
        path = ROOT / row["relative_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row["sha256"]


def test_exact_surface_helper_requires_each_semantic_group():
    assert contains_all_groups_v1("TRIB3 overall survival association", [["TRIB3"], ["overall survival"], ["association"]])
    assert not contains_all_groups_v1("TRIB3 survival association", [["TRIB3"], ["overall survival"], ["association"]])
