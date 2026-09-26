"""Read-only checks for the offline packaging of the completed alpha3.12 run."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260925_search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval"
SOURCE = ROOT / "runs/20260925_bounded_lexical_realization_v2_development_retrieval"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def test_root_and_physical_corpus_copies() -> None:
    validation = json.loads((RUN / "validation.json").read_text())
    pairs = validation["aggregate_components"]
    canonical = json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    root = hashlib.sha256(canonical).hexdigest()
    assert root == validation["search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval_sha256"]
    assert root == (RUN / "search_plan_v24_dev_bounded_lexical_realization_v2_full_retrieval_sha256").read_text().strip()
    assert all(_sha(RUN / name) == expected for name, expected in pairs)
    assert not any(path.is_symlink() for path in RUN.rglob("*"))
    for source in (SOURCE / "retrieval_assets").rglob("*"):
        if source.is_file() and source.name != "network_events.json":
            assert _sha(source) == _sha(RUN / source.relative_to(SOURCE))


def test_mapping_and_safety_boundary() -> None:
    mapping = _rows(RUN / "alpha39_alpha311_query_mapping.jsonl")
    queries = _rows(RUN / "query_execution_results.jsonl")
    transitions = json.loads((RUN / "contribution_level_outcome_transition.json").read_text())
    summary = json.loads((RUN / "summary.json").read_text())
    assert len(mapping) == 63
    assert len(queries) == 55
    assert all(row["mapping_state"] == "LEXICALLY_CHANGED_ONLY" for row in mapping)
    assert sum(transitions["transition_counts"].values()) == 63
    assert summary["new_network_requests"] == 0
    assert summary["llm_calls"] == summary["known_pmid_checks"] == summary["historical_label_reads"] == 0
    assert summary["scientific_relevance_unreviewed"] is True
    assert len(list((RUN / "case_selection_manifests").glob("*.json"))) == 8
