"""Focused integrity checks for alpha3.15 interpretation-only artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_15_harmonized_results_interpretation_offline"


def load(name: str) -> dict:
    return json.loads((RUN / name).read_text(encoding="utf-8"))


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_root_and_protocol_deviation_preserved() -> None:
    pairs = [[path.name, sha(path)] for path in sorted(RUN.iterdir())
             if path.is_file() and path.name != "search_plan_v24_dev_alpha3_15_sha256"]
    assert digest(pairs) == (RUN / "search_plan_v24_dev_alpha3_15_sha256").read_text().strip()
    assert load("validation.json")["status"] == "PASS"
    assert load("validation.json")["alpha3_14e_protocol_status_preserved"] == "FAILED_PROTOCOL_CHRONOLOGY"
    impact = load("chronology_deviation_scientific_impact_audit.json")
    assert impact["classification"] == "PROTOCOL_DEVIATION_NO_IDENTIFIED_SCIENTIFIC_CONTENT_IMPACT"
    assert impact["run_protocol_pass"] is False
    assert impact["rerun_for_chronology_alone_recommended"] is False


def test_denominators_categories_and_reviewer_transition() -> None:
    lexical = load("lexical_v2_relevance_distribution.json")
    historical = load("harmonized_v23_relevance_distribution.json")
    assert lexical["denominator"] == 11
    assert historical["denominator"] == 60
    assert [(row["category"], row["count"]) for row in lexical["categories"] if row["count"]] == [
        ("WRONG_ENDPOINT", 1), ("WRONG_ENTITY", 10)]
    assert sum(row["count"] for row in historical["categories"]) == 60
    assert next(row["count"] for row in historical["categories"] if row["category"] == "DIRECTLY_RELEVANT") == 1
    transition = load("original_vs_harmonized_v23_transition_matrix.json")
    assert (transition["same_label_count"], transition["different_label_count"]) == (24, 36)
    assert (transition["DIRECT_to_non_DIRECT"], transition["non_DIRECT_to_DIRECT"]) == (1, 0)


def test_case_coverage_and_unreviewed_boundary() -> None:
    cases = load("lexical_v2_case_level_analysis.json")["cases"]
    assert len(cases) == 8
    assert sum(case["metadata_count"] for case in cases) == 66
    assert sum(case["reviewed_count"] for case in cases) == 11
    assert sum(case["review_status"] == "NO_REVIEW_UNITS_FROM_RETRIEVAL" for case in cases) == 6
    assert next(case for case in cases if case["case_id"] == "heldout_v2_104")["metadata_count"] == 18
    bottleneck = load("retrieval_selection_bottleneck_analysis.json")
    assert (bottleneck["raw_pmcid_present"], bottleneck["tier_a_or_b_with_pmcid_eligible"]) == (28, 21)
    assert bottleneck["unreviewed_metadata_candidates"] == 55
    assert bottleneck["unreviewed_candidates_assigned_scientific_labels"] is False
    assert load("scientific_state_safety_audit.json")["provider_calls"] == 0
    assert load("summary.json")["next_stage_recommendation"] == "FREEZE_ARCHITECTURE_AND_TEST_FRESH_HELDOUT"

