"""Fail-closed checks for alpha3.18A's offline source-execution authority audit."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_18a_source_acquisition_execution_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"


def _load(name: str):
    return json.loads((RUN / name).read_text())


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_frozen_queries_verified_without_rewrite() -> None:
    audit = _load("source_query_freeze_verification.json")
    raw = (UP17A / "exact_source_queries.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert audit["status"] == "PASS"
    assert audit["query_count"] == len(rows) == 6
    assert audit["query_byte_changes"] == audit["query_hash_changes"] == 0
    assert audit["source_query_file_sha256"] == _sha(raw)
    assert audit["per_query_sha256"] == [[row["stratum_id"], row["query_sha256"]] for row in rows]


def test_unresolved_authority_prevents_execution_manifest() -> None:
    assert _load("construction_oa_eligibility_contract.json")["status"] == "UNRESOLVED"
    assert not _load("construction_oa_eligibility_contract.json")["pmc_filter_is_final_oa_proof"]
    assert _load("source_type_mechanical_eligibility_contract.json")["status"] == "UNRESOLVED"
    document = _load("construction_evidence_document_v1_contract.json")
    assert document["status"] == "UNRESOLVED"
    assert document["title_private_in_acquisition_policy"]
    assert document["title_present_in_frozen_builder_prompt"]
    assert not document["reference_section_policy_frozen"]
    assert not (RUN / "alpha3_18a_source_acquisition_execution_manifest.json").exists()
    assert not (RUN / "alpha3_18a_source_acquisition_execution_manifest_sha256").exists()
    assert _load("summary.json")["alpha3_18a_source_acquisition_execution_manifest_sha256"] is None
    assert _load("validation.json")["failure_code"] == "CONSTRUCTION_OA_ELIGIBILITY_RULE_UNRESOLVED"


def test_failed_run_hash_and_zero_calls() -> None:
    names = sorted(path.name for path in RUN.iterdir() if path.is_file() and path.name != "search_plan_v24_dev_alpha3_18a_prereg_sha256")
    pairs = [[name, _sha((RUN / name).read_bytes())] for name in names]
    expected = _sha(json.dumps(pairs, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode())
    assert expected == (RUN / "search_plan_v24_dev_alpha3_18a_prereg_sha256").read_text().strip()
    safety = _load("scientific_state_safety_audit.json")
    assert all(safety[key] == 0 for key in ("network_calls", "retrieval_calls", "provider_calls", "llm_calls",
                                         "builder_calls", "quality_calls", "propositions_generated"))
