"""Fail-closed cardinality audit for alpha3.17b."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17b_independent_proposition_quality_adjudication_preregistration_offline"


def _load(name: str) -> dict:
    return json.loads((RUN / name).read_text())


def test_conflict_is_not_silently_resolved() -> None:
    audit = _load("builder_cardinality_authority_audit.json")
    assert audit["classification"] == "UPSTREAM_CONTRACT_INCONSISTENT"
    assert audit["alpha3_17_builder_output_cardinality"]["minimum"] == 0
    assert audit["alpha3_17_builder_output_cardinality"]["maximum"] == 3
    assert audit["alpha3_17a_builder_request_cardinality"]["maximum"] == 1
    assert audit["alpha3_17_final_per_source_pool_cardinality"]["stage"].startswith("after grounding")
    assert _load("validation.json")["failure_code"] == "BUILDER_CARDINALITY_CONTRACT_RECONCILIATION_REQUIRED"
    assert _load("summary.json")["proposition_quality_adjudication_protocol_sha256"] is None


def test_failed_run_root_and_zero_calls() -> None:
    names = sorted(p.name for p in RUN.iterdir() if p.is_file() and p.name != "search_plan_v24_dev_alpha3_17b_sha256")
    pairs = [[name, hashlib.sha256((RUN / name).read_bytes()).hexdigest()] for name in names]
    actual = hashlib.sha256(json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    assert actual == (RUN / "search_plan_v24_dev_alpha3_17b_sha256").read_text().strip()
    safety = _load("scientific_state_safety_audit.json")
    assert all(safety[key] == 0 for key in ("provider_calls", "llm_calls", "network_calls", "retrieval_calls", "quality_adjudication_calls"))
