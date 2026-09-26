import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from tools.run_bounded_lexical_realization_v2_development_retrieval import RUN, canon


def read(name):
    return json.loads((RUN / name).read_text())


def lines(name):
    return [json.loads(line) for line in (RUN / name).read_text().splitlines() if line]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_full_retrieval_and_corpus_roots_are_complete():
    validation = read("bounded_lexical_realization_v2_development_retrieval_validation.json")
    pairs = validation["aggregate_components"]
    assert all(sha(RUN / name) == value for name, value in pairs)
    root = hashlib.sha256(canon(pairs)).hexdigest()
    assert root == validation["root_sha256"] == (RUN / "bounded_lexical_realization_v2_development_retrieval_sha256").read_text().strip()
    corpus = read("search_constraint_allocation_v1_development_acquisition_corpus_manifest.json")
    assert all(sha(RUN / name) == value for name, value in corpus["aggregate_components"])
    assert hashlib.sha256(canon(corpus["aggregate_components"])).hexdigest() == corpus["corpus_sha256"] == (RUN / "bounded_lexical_realization_v2_acquisition_corpus_sha256").read_text().strip()
    assert not any(path.is_symlink() for path in RUN.rglob("*"))


def test_query_selection_and_network_provenance():
    queries = lines("query_execution_results.jsonl")
    assert len(queries) == 55
    assert sum(len(query["contributions"]) for query in queries) == 63
    assert all(query["transport_status"] == "SUCCESS" for query in queries)
    receipt = read("retrieval_assets/network_events.json")
    assert Counter(event["kind"] for event in receipt["events"]) == {
        "pubmed_search": 56, "pubmed_metadata": 1, "pmc_fulltext": 11,
    }
    assert len(receipt["failures"]) == 3
    assert all(sha(Path(event["snapshot_ref"])) == event["response_sha256"] for event in receipt["events"])
    first_pmc = min(datetime.fromisoformat(event["timestamp_utc"]).timestamp() for event in receipt["events"] if event["kind"] == "pmc_fulltext")
    selections = sorted((RUN / "case_selection_manifests").glob("*.json"))
    assert len(selections) == 8
    assert all(path.stat().st_mtime < first_pmc for path in selections)
    assert (RUN / "selection_freeze_barrier_audit.json").stat().st_mtime < first_pmc
    assert all(json.loads(path.read_text())["selection_count"] <= 10 for path in selections)
    assert sum(json.loads(path.read_text())["selection_count"] for path in selections) == 11


def test_lexical_attribution_and_blinding_boundaries():
    summary = read("bounded_lexical_realization_v2_summary.json")
    assert summary["nonzero_query_count"] == 8
    assert summary["metadata_universe_total"] == 66
    assert summary["successful_fulltext_acquisition_count"] == 11
    assert summary["relevance_adjudications"] == 0
    assert summary["known_pmid_checks"] == summary["historical_label_reads"] == 0
    attribution = lines("lexical_query_attribution.jsonl")
    assert len(attribution) == 55
    assert all(not row["specific_alternative_causal_claim"] for row in attribution)
    assert all(row["authority_classes_present"] for row in attribution)
    assert sum(row["nonzero"] for row in attribution) == 8
