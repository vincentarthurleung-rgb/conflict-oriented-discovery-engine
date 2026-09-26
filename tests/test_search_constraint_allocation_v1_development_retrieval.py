import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_constraint_allocation_v1_development_retrieval"
PREREG = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_10_search_constraint_allocation_retrieval_preregistration_offline"


def load(name):
    return json.loads((RUN / name).read_text())


def rows(name):
    return [json.loads(line) for line in (RUN / name).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def test_all_frozen_queries_executed_once_with_original_bytes_and_contributions():
    manifest = json.loads((PREREG / "search_constraint_allocation_v1_development_execution_manifest.json").read_text())
    results = rows("query_execution_results.jsonl")
    pages = rows("query_execution_provenance.jsonl")
    events = load("retrieval_assets/network_events.json")
    assert len(results) == 55
    assert len({r["executed_query_id"] for r in results}) == 55
    assert all(r["transport_status"] == "SUCCESS" for r in results)
    assert [(r["case_id"], r["query_text"], r["query_sha256"]) for r in results] == [
        (r["case_id"], r["exact_query_text"], r["query_sha256"]) for r in manifest["exact_queries"]]
    assert sum(len(r["contributions"]) for r in results) == 63
    assert len(pages) == 55
    assert Counter(e["kind"] for e in events["events"]) == {"pubmed_search": 55, "pubmed_metadata": 1, "pmc_fulltext": 1}
    assert all(e["retry_count"] <= 3 for e in events["events"])
    assert len(events["failures"]) == 3


def test_selection_barrier_and_fulltext_policy():
    barrier = load("selection_freeze_barrier_audit.json")
    events = load("retrieval_assets/network_events.json")["events"]
    first_pmc = min(datetime.fromisoformat(e["timestamp_utc"]).timestamp() for e in events if e["kind"] == "pmc_fulltext")
    assert barrier["selection_freeze_barrier_pass"] is True
    assert len(barrier["case_manifest_components"]) == 8
    for name, expected in barrier["case_manifest_components"]:
        path = RUN / name
        assert sha(path) == expected
        assert path.stat().st_mtime < first_pmc
        assert len(json.loads(path.read_text())["ordered_selections"]) <= 10
    assert (RUN / "selection_freeze_barrier_audit.json").stat().st_mtime < first_pmc
    results = rows("fulltext_acquisition_results.jsonl")
    assert len(results) == 1
    assert results[0]["acquisition_status"] == "SUCCESS"
    assert results[0]["xml_valid"] and results[0]["article_structure_valid"] and results[0]["publication_identity_valid"]
    assert not results[0]["replacement_performed"]


def test_complete_corpus_and_run_hashes_validate_without_relevance_labels():
    corpus = load("search_constraint_allocation_v1_development_acquisition_corpus_manifest.json")
    validation = load("validation.json")
    assert validation["status"] == "PASS"
    assert all(sha(RUN / name) == value for name, value in corpus["aggregate_components"])
    assert digest(corpus["aggregate_components"]) == (RUN / "search_constraint_allocation_v1_development_acquisition_corpus_sha256").read_text().strip()
    assert all(sha(RUN / name) == value for name, value in validation["aggregate_components"])
    assert digest(validation["aggregate_components"]) == (RUN / "search_constraint_allocation_v1_development_retrieval_sha256").read_text().strip()
    assert load("summary.json")["relevance_adjudications"] == 0
    assert load("historical_label_blinding_audit.json")["historical_label_reads"] == 0
    assert load("known_paper_blindness_audit.json")["known_pmid_checks"] == 0
