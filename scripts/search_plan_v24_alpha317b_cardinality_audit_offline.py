#!/usr/bin/env python3
"""Fail-closed alpha3.17b cardinality audit; no adjudication protocol is minted."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UP17 = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17_new_blinded_proposition_pool_preregistration_offline"
UP17A = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17a_new_pool_execution_preflight_offline"
OUT = ROOT / "runs/20260927_search_plan_v24_dev_alpha3_17b_independent_proposition_quality_adjudication_preregistration_offline"
EXPECTED17 = "10bc7cc1f03b0cdf38b4409f624b10697ffef3939053601cfba2dc4ea74cece6"
EXPECTED17A = "a23e549cf9d83714782d4283c823ee94ce569f5f00f820fc2c4e0b9d3ee7248e"
EXPECTED_POOL = "69a63d7ce9f08e8714413247aa4a39478a5eb0acbb39925e3dadeb9b6a45b64b"
EXPECTED_SOURCE = "755702713972012bc062f7cba43eea95708c9a5e75ca5c93e49ef5396f0c00c0"
EXPECTED_BUILDER = "e3e147c5af132e15ab7a9c3612c3d03eaf31a77badea754b86f03a3f9c953fe8"


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def aggregate(directory: Path, excluded: str) -> str:
    pairs = [[path.name, sha(path.read_bytes())] for path in sorted(directory.iterdir())
             if path.is_file() and path.name != excluded]
    return sha(canonical(pairs))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value: object) -> None:
    path = OUT / name
    if path.exists():
        raise RuntimeError(f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def main() -> None:
    if OUT.exists():
        raise RuntimeError("alpha3.17b audit already exists; refusing regeneration")
    assert aggregate(UP17, "search_plan_v24_dev_alpha3_17_sha256") == EXPECTED17
    assert (UP17 / "search_plan_v24_dev_alpha3_17_sha256").read_text().strip() == EXPECTED17
    assert aggregate(UP17A, "search_plan_v24_dev_alpha3_17a_sha256") == EXPECTED17A
    assert (UP17A / "search_plan_v24_dev_alpha3_17a_sha256").read_text().strip() == EXPECTED17A
    assert (UP17 / "new_blinded_proposition_pool_protocol_sha256").read_text().strip() == EXPECTED_POOL
    assert (UP17A / "new_pool_source_acquisition_manifest_sha256").read_text().strip() == EXPECTED_SOURCE
    assert (UP17A / "proposition_builder_protocol_sha256").read_text().strip() == EXPECTED_BUILDER
    original = load(UP17 / "proposition_builder_schema.json")
    narrowed = load(UP17A / "proposition_builder_output_schema.json")
    choice = load(UP17 / "one_proposition_per_source_policy.json")
    source_rule = original["schema"]["properties"]["propositions"]
    request_rule = narrowed["schema"]["properties"]["propositions"]
    assert (source_rule["minItems"], source_rule["maxItems"]) == (0, 3)
    assert (request_rule["minItems"], request_rule["maxItems"]) == (0, 1)
    assert choice["eligible_heldout_propositions_per_source_article_maximum"] == 1
    assert narrowed["alpha3_17a_cardinality_refinement"] == "0..1; alpha3.17 historical 0..3 remains unchanged"
    OUT.mkdir()
    write("alpha3_17_root_verification.json", {"status": "PASS", "expected_sha256": EXPECTED17,
          "actual_sha256": aggregate(UP17, "search_plan_v24_dev_alpha3_17_sha256"),
          "new_pool_protocol_sha256": EXPECTED_POOL})
    write("alpha3_17a_root_verification.json", {"status": "PASS", "expected_sha256": EXPECTED17A,
          "actual_sha256": aggregate(UP17A, "search_plan_v24_dev_alpha3_17a_sha256"),
          "source_acquisition_manifest_sha256": EXPECTED_SOURCE,
          "builder_protocol_sha256": EXPECTED_BUILDER,
          "upstream_validation_status": load(UP17A / "validation.json")["status"]})
    write("builder_cardinality_authority_audit.json", {
        "classification": "UPSTREAM_CONTRACT_INCONSISTENT",
        "alpha3_17_builder_output_cardinality": {"minimum": 0, "maximum": 3,
            "source_file": "proposition_builder_schema.json", "source_sha256": sha((UP17 / "proposition_builder_schema.json").read_bytes())},
        "alpha3_17a_builder_request_cardinality": {"minimum": 0, "maximum": 1,
            "source_file": "proposition_builder_output_schema.json", "source_sha256": sha((UP17A / "proposition_builder_output_schema.json").read_bytes())},
        "alpha3_17_final_per_source_pool_cardinality": {"minimum": 0, "maximum": 1,
            "stage": "after grounding, leakage, quality and duplicate gates; not builder output",
            "source_file": "one_proposition_per_source_policy.json",
            "source_sha256": sha((UP17 / "one_proposition_per_source_policy.json").read_bytes())},
        "materiality": "A valid two- or three-candidate builder response under alpha3.17 is invalid under the frozen alpha3.17a builder request schema; this changes model-visible generation and downstream quality-call payloads.",
        "alpha3_17a_failed_closed": True,
        "resolution_required": "Prospective explicit authority decision on builder output cardinality and a new consistent builder request/schema freeze; do not mutate either upstream artifact.",
        "builder_cardinality_authority_resolved": False,
        "future_quality_call_cardinality_not_frozen": True,
        "quality_protocol_generated": False})
    write("scientific_state_safety_audit.json", {"provider_calls": 0, "llm_calls": 0,
          "network_calls": 0, "retrieval_calls": 0, "quality_adjudication_calls": 0,
          "propositions_generated": 0, "historical_assets_modified": False})
    write("validation.json", {"status": "FAILED_CLOSED",
          "failure_code": "BUILDER_CARDINALITY_CONTRACT_RECONCILIATION_REQUIRED",
          "builder_cardinality_authority_resolved": False,
          "authoritative_builder_candidate_cardinality": "UPSTREAM_CONTRACT_INCONSISTENT",
          "proposition_quality_adjudication_protocol_sha256": None,
          "quality_adjudicator_prompt_frozen": False, "quality_calls_authorized": 0})
    write("summary.json", {"status": "failed", "reason": "BUILDER_CARDINALITY_CONTRACT_RECONCILIATION_REQUIRED",
          "next_stage_recommendation": "RECONCILE_BUILDER_CARDINALITY_BEFORE_QUALITY_PREREGISTRATION",
          "proposition_quality_adjudication_protocol_sha256": None,
          "historical_assets_modified": False})
    root = aggregate(OUT, "search_plan_v24_dev_alpha3_17b_sha256")
    (OUT / "search_plan_v24_dev_alpha3_17b_sha256").write_text(root + "\n", encoding="utf-8")
    assert aggregate(OUT, "search_plan_v24_dev_alpha3_17b_sha256") == root
    print(json.dumps({"status": "failed_closed", "reason": "BUILDER_CARDINALITY_CONTRACT_RECONCILIATION_REQUIRED",
                      "run_root": root, "provider_calls": 0, "network_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
