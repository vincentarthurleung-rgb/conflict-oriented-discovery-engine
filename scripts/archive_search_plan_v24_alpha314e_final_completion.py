#!/usr/bin/env python3
"""Fail-closed archival export of the already-completed alpha3.14e review.

No provider or network code is present. This cannot retroactively satisfy a
post-Batch-3 request-freeze requirement absent from the executed continuation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_harmonized_review_continuation"
TARGET = ROOT / "runs/20260926_search_plan_v24_dev_alpha3_14e_final_harmonized_review_completion"
ORIGINAL_INVALID = ROOT / "runs/20260925_search_plan_v24_dev_alpha3_14b_harmonized_review_continuation/raw_responses/pass_b_batch_03.json"
EXPECTED_SOURCE_ROOT = "ea98ff71885dc098cd745a53c0c53e6603023b354dc18aa8ee2539e496310bed"
EXPECTED_BLINDED_ROOT = "677fb451105feebf091b675149d487b691bbb81ca1eab04fe3bf4e24a2bd23c3"
EXPECTED_RESULTS_ROOT = "5624bbf8c106689a27a883cc43273cb14882f7180f4ceae443eb0183f822413d"
EXPECTED_ROOTS = {
    "alpha3_14d": "f9d78f0b430c4bd9bc143bc8b094125ad32d83bdfd0e58c51eb07d1f6c1bcb36",
    "pass_b_output_contract_v2": "15b3cea65d65793a060614705ebc3b0c2cf340fd888fda03cef0b1acf6fe8ea9",
    "protocol_v4": "778a07b4a8ee6f171ce7459156b844319867d9dc1c1843f6f7c92429facc6fa1",
    "autopsy_alpha3_14c": "78095a25aa4c60a0c2eb96ce888a1e7cb4b0132c40d0f7bf9eb0d33a676fc8b1",
    "failed_alpha3_14b": "0d9595e7d1b0a27b14133dc4c79ed9ea911c5564b25a9f716ef78acb3b8ba5e8",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl(path: Path) -> list[Any]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write(path: Path, value: Any) -> None:
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(canonical(value) + b"\n")


def write_lines(path: Path, values: list[Any]) -> None:
    require(not path.exists(), f"refusing overwrite: {path}")
    path.write_bytes(b"".join(canonical(value) + b"\n" for value in values))


def copy(source: Path, name: str) -> None:
    require(source.is_file() and not source.is_symlink(), f"unsafe source: {source}")
    target = TARGET / name
    require(not target.exists(), f"refusing overwrite: {target}")
    shutil.copyfile(source, target)
    require(sha(source) == sha(target), f"copy mismatch: {name}")


def verify_manifest(name: str, root_name: str, expected: str) -> None:
    manifest = load(SOURCE / name)
    pairs = manifest["aggregate_components"]
    require(all(sha(SOURCE / relative) == checksum for relative, checksum in pairs), f"component drift: {name}")
    require(digest(pairs) == expected == (SOURCE / root_name).read_text().strip(), f"root drift: {name}")


def preflight() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    require(not TARGET.exists(), "target exists; never overwrite an archive")
    verify_manifest("harmonized_deepseek_blinded_adjudication_corpus_manifest.json",
                    "harmonized_deepseek_blinded_adjudication_corpus_sha256", EXPECTED_BLINDED_ROOT)
    verify_manifest("harmonized_deepseek_review_results_manifest.json",
                    "harmonized_deepseek_review_results_sha256", EXPECTED_RESULTS_ROOT)
    paths = [path for path in sorted(SOURCE.rglob("*")) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14e_sha256"]
    pairs = [[str(path.relative_to(SOURCE)), sha(path)] for path in paths]
    require(digest(pairs) == EXPECTED_SOURCE_ROOT == (SOURCE / "search_plan_v24_dev_alpha3_14e_sha256").read_text().strip(), "source run root drift")
    roots = load(SOURCE / "preflight_roots.json")
    require(roots["status"] == "PASS" and roots["verified_before_provider_access"] is True, "old root preflight failed")
    require(all(roots["roots"][key] == value for key, value in EXPECTED_ROOTS.items()), "authoritative root mismatch")
    accounting = load(SOURCE / "model_call_accounting.json")
    require(accounting["historical_inference_events"] == 11 and accounting["new_inference_events"] == 6, "inference count drift")
    require(accounting["valid_final_batch_adjudications"] == 16 and accounting["invalid_superseded_inference_events"] == 1, "validity accounting drift")
    gate = load(SOURCE / "gate/replacement_batch3_validation.json")
    require(gate["status"] == "VALID" and gate["identity_binding_valid"] and gate["full_schema_valid"], "Batch 3 gate drift")
    require(sha(ORIGINAL_INVALID) == load(SOURCE / "invalid_superseded_inference_preservation_audit.json")["old_batch3_raw_sha256"], "old invalid response drift")
    manifest = jsonl(SOURCE / "six_request_manifest.jsonl")
    requests = jsonl(SOURCE / "frozen_requests.jsonl")
    require([row["batch_index"] for row in manifest] == list(range(3, 9)), "manifest sequence drift")
    require([row["batch_index"] for row in requests] == list(range(3, 9)), "request sequence drift")
    require(all(digest(request["request"]) == row["new_request_sha256"] for row, request in zip(manifest, requests)), "request hash drift")
    require(sha(SOURCE / "six_request_manifest.jsonl") == (SOURCE / "six_request_manifest_sha256").read_text().strip(), "manifest freeze drift")
    barrier = load(SOURCE / "unblinding_barrier_audit.json")
    require(barrier["blinded_adjudication_freeze_verified"] and barrier["all_component_hashes_verified_before_map_open"], "unblinding barrier drift")
    require(barrier["arm_map_accessed_before_blinded_freeze"] is False and barrier["metrics_computed_before_blinded_freeze"] is False, "early unblinding")
    return manifest, requests


def main() -> None:
    manifest, requests = preflight()
    TARGET.mkdir()
    write(TARGET / "upstream_root_verification.json", {
        "status": "PASS", "verified_before_original_provider_access": True,
        "roots": EXPECTED_ROOTS, "source_continuation_run_sha256": EXPECTED_SOURCE_ROOT,
        "source_blinded_corpus_sha256": EXPECTED_BLINDED_ROOT,
        "source_results_sha256": EXPECTED_RESULTS_ROOT,
        "archive_created_after_all_inferences": True,
    })
    write(TARGET / "prior_inference_preservation_audit.json", {
        "prior_provider_inference_events": 11, "valid_batches_before_continuation": 10,
        "original_invalid_batch3_inference_events": 1, "never_inferred_batches_before_continuation": [4, 5, 6, 7, 8],
        "old_invalid_raw_sha256": sha(ORIGINAL_INVALID),
        "old_invalid_scientific_fields_not_inspected_or_compared": True,
        "historical_inventory_snapshot": load(SOURCE / "historical_preservation_snapshot.json"),
    })
    scientific_version = "alpha3.13_frozen_harmonized_scientific_rubric"
    serialization = [
        {"pass": "PASS_B", "batch_index": index, "scientific_protocol_version": scientific_version,
         "scientific_prompt_sha256": manifest[0]["scientific_prompt_sha256"],
         "serialization_contract_version": "original_alpha3.13_contract" if index <= 2 else "PassBOutputContractV2",
         "source": "frozen_original_valid_output" if index == 1 else "alpha3.14b_valid_output" if index == 2 else "alpha3.14e_valid_output"}
        for index in range(1, 9)
    ]
    write(TARGET / "serialization_contract_version_manifest.json", {
        "pass_b_batches": serialization,
        "original_scientific_rubric_unchanged": True,
        "output_contract_v2_sha256": EXPECTED_ROOTS["pass_b_output_contract_v2"],
    })
    write(TARGET / "batch3_replacement_preflight.json", {
        "review_unit_count": len(manifest[0]["ordered_review_unit_ids"]),
        "ordered_review_unit_ids": manifest[0]["ordered_review_unit_ids"],
        "evidence_packet_sha256": manifest[0]["evidence_packet_sha256"],
        "scientific_prompt_sha256": manifest[0]["scientific_prompt_sha256"],
        "original_prompt_sha256": manifest[0]["original_prompt_sha256"],
        "revised_prompt_sha256": manifest[0]["revised_prompt_sha256"],
        "provider_config": {key: requests[0]["request"][key] for key in ("model", "thinking", "reasoning_effort", "response_format")},
        "provider_config_sha256": digest({key: requests[0]["request"][key] for key in ("model", "thinking", "reasoning_effort", "response_format")}),
        "output_contract_v2_sha256": EXPECTED_ROOTS["pass_b_output_contract_v2"],
        "review_protocol_v4_sha256": EXPECTED_ROOTS["protocol_v4"],
        "same_frozen_scientific_prompt_and_evidence": True,
        "archival_export_after_execution": True,
    })
    write(TARGET / "pass_b_batch3_replacement_request.json", requests[0])
    copy(SOURCE / "raw_responses/pass_b_batch_03.json", "pass_b_batch3_replacement_raw_response.json")
    copy(SOURCE / "transport/pass_b_batch_03.json", "pass_b_batch3_replacement_transport_provenance.json")
    copy(SOURCE / "validated/pass_b_batch_03.json", "pass_b_batch3_replacement_parsed_output.json")
    write(TARGET / "pass_b_batch3_replacement_validation.json", {
        "gate": load(SOURCE / "gate/replacement_batch3_validation.json"),
        "identity": load(SOURCE / "identity/pass_b_batch_03.json"),
        "parsed_output_sha256": sha(SOURCE / "validated/pass_b_batch_03.json"),
        "raw_response_sha256": sha(SOURCE / "raw_responses/pass_b_batch_03.json"),
    })
    write(TARGET / "batch3_supersession_audit.json", {
        **load(SOURCE / "invalid_superseded_inference_preservation_audit.json"),
        "replacement_status": "VALID_ADJUDICATION_INSTANCE",
    })
    copy(SOURCE / "gate/replacement_batch3_validation.json", "batch3_sequential_gate.json")
    write(TARGET / "remaining_five_batch_derivation.json", {
        "batch_identities": [4, 5, 6, 7, 8], "never_inferred_before_authorized_continuation": True,
        "executed_only_after_valid_batch3_gate": True,
        "strict_post_gate_request_derivation_satisfied": False,
        "reason": "All six requests were rendered and frozen together before replacement Batch 3 inference.",
        "source_six_request_manifest_sha256": sha(SOURCE / "six_request_manifest.jsonl"),
    })
    remaining_manifest = [
        {"batch_index": row["batch_index"], "original_prefrozen_manifest_row": row,
         "request": request["request"], "chronology": "FROZEN_BEFORE_REPLACEMENT_BATCH3_GATE"}
        for row, request in zip(manifest[1:], requests[1:])
    ]
    write_lines(TARGET / "remaining_five_request_manifest.jsonl", remaining_manifest)
    (TARGET / "remaining_five_request_manifest_sha256").write_text(
        sha(TARGET / "remaining_five_request_manifest.jsonl") + "\n", encoding="utf-8"
    )
    write_lines(TARGET / "remaining_pass_b_raw_responses.jsonl", [
        {"batch_index": index, "raw_response": load(SOURCE / f"raw_responses/pass_b_batch_{index:02d}.json"),
         "source_sha256": sha(SOURCE / f"raw_responses/pass_b_batch_{index:02d}.json")}
        for index in range(4, 9)
    ])
    write_lines(TARGET / "remaining_pass_b_transport_provenance.jsonl", [
        {"batch_index": index, "transport": load(SOURCE / f"transport/pass_b_batch_{index:02d}.json"),
         "source_sha256": sha(SOURCE / f"transport/pass_b_batch_{index:02d}.json")}
        for index in range(4, 9)
    ])
    write_lines(TARGET / "remaining_pass_b_parsed_outputs.jsonl", [
        {"batch_index": index, "parsed_output": load(SOURCE / f"validated/pass_b_batch_{index:02d}.json"),
         "source_sha256": sha(SOURCE / f"validated/pass_b_batch_{index:02d}.json")}
        for index in range(4, 9)
    ])
    write_lines(TARGET / "remaining_pass_b_validation.jsonl", [
        {"batch_index": index, "identity": load(SOURCE / f"identity/pass_b_batch_{index:02d}.json"),
         "source_sha256": sha(SOURCE / f"identity/pass_b_batch_{index:02d}.json")}
        for index in range(4, 9)
    ])
    write(TARGET / "complete_pass_b_summary.json", {
        "valid_batches": 8, "valid_review_units": 71, "pass_a_valid_batches": 8,
        "pass_a_valid_review_units": 71, "replacement_batch3_valid": True,
    })
    write(TARGET / "complete_model_inference_accounting.json", {
        **load(SOURCE / "model_call_accounting.json"),
        "replacement_batch3_call_count": 1,
        "remaining_never_inferred_calls": 5,
        "new_calls_in_this_archival_turn": 0,
        "authorized_continuation_calls_already_completed": 6,
    })
    for name in (
        "complete_blinded_review_unit_results.jsonl", "blinded_adjudication_freeze_audit.json",
        "harmonized_deepseek_blinded_adjudication_corpus_sha256", "unblinding_barrier_audit.json",
        "harmonized_arm_results.jsonl", "harmonized_v23_metrics.json",
        "harmonized_lexical_v2_metrics.json", "original_v23_vs_harmonized_v23_comparison.json",
        "harmonized_v23_vs_lexical_v2_comparison.json", "evidence_availability_limitation_audit.json",
        "case_coverage_summary.json", "historical_original_review_preservation_audit.json",
        "search_state_immutability_audit.json", "scientific_state_safety_audit.json",
    ):
        copy(SOURCE / name, name)
    write(TARGET / "harmonized_deepseek_blinded_adjudication_corpus_manifest.json", {
        "source_run": str(SOURCE.relative_to(ROOT)),
        "source_manifest_sha256": sha(SOURCE / "harmonized_deepseek_blinded_adjudication_corpus_manifest.json"),
        "verified_source_root_sha256": EXPECTED_BLINDED_ROOT,
        "archive_is_not_the_original_blinded_freeze_location": True,
    })
    write(TARGET / "post_failure_protocol_amendment_disclosure.json", {
        "ReviewResponseIdentityBindingV2": "Introduced after the first order-validation failure; not part of the original alpha3.13 preregistration.",
        "PassBOutputContractV2": "Introduced after the Batch 3 enum/schema failure; not part of the original alpha3.13 preregistration.",
        "post_failure_identity_binding_amendment_disclosed": True,
        "post_failure_output_contract_amendment_disclosed": True,
        "additional_archival_chronology_disclosure": "The executed alpha3.14e continuation froze all six outgoing requests before the replacement Batch 3 call, not remaining five after its validation.",
    })
    write(TARGET / "validation.json", {
        "status": "FAILED_PROTOCOL_CHRONOLOGY",
        "scientific_review_outputs_valid": True,
        "source_blinded_freeze_valid": True,
        "source_unblinding_barrier_valid": True,
        "source_metrics_validated": True,
        "strict_post_gate_request_derivation_satisfied": False,
        "fabricated_request_freeze_timestamps": False,
        "new_provider_calls_during_archive": 0,
    })
    source_summary = load(SOURCE / "summary.json")
    write(TARGET / "summary.json", {
        "status": "failed", "reason": "The stricter requested post-gate derivation/freeze ordering cannot be satisfied retrospectively.",
        "source_continuation_status": source_summary["status"],
        "source_continuation_run_sha256": EXPECTED_SOURCE_ROOT,
        "source_blinded_corpus_sha256": EXPECTED_BLINDED_ROOT,
        "source_results_sha256": EXPECTED_RESULTS_ROOT,
        "new_deepseek_calls_in_this_archival_turn": 0,
        "new_deepseek_calls_in_completed_continuation": 6,
        "cumulative_provider_inference_events": 17,
        "planned_scientific_batch_identities": 16,
        "valid_final_adjudication_batches": 16,
        "invalid_superseded_inference_events": 1,
        "reinferred_batch_identities": 1,
        "pass_a_valid_units": 71,
        "pass_b_valid_units": 71,
        "harmonized_v23_direct_count": source_summary["historical_v23_direct_n"],
        "harmonized_v23_direct_rate": source_summary["historical_v23_direct_rate"],
        "harmonized_lexical_v2_direct_count": source_summary["lexical_v2_direct_n"],
        "harmonized_lexical_v2_direct_rate": source_summary["lexical_v2_direct_rate"],
        "next_stage_recommendation": "PROTOCOL_CHRONOLOGY_REVIEW_REQUIRED",
    })
    result_names = (
        "harmonized_deepseek_blinded_adjudication_corpus_manifest.json",
        "harmonized_deepseek_blinded_adjudication_corpus_sha256",
        "unblinding_barrier_audit.json", "harmonized_arm_results.jsonl",
        "harmonized_v23_metrics.json", "harmonized_lexical_v2_metrics.json",
        "original_v23_vs_harmonized_v23_comparison.json",
        "harmonized_v23_vs_lexical_v2_comparison.json",
        "evidence_availability_limitation_audit.json", "case_coverage_summary.json",
        "post_failure_protocol_amendment_disclosure.json",
        "historical_original_review_preservation_audit.json",
        "search_state_immutability_audit.json", "scientific_state_safety_audit.json",
        "validation.json", "summary.json",
    )
    result_pairs = [[name, sha(TARGET / name)] for name in sorted(result_names)]
    write(TARGET / "harmonized_deepseek_review_results_manifest.json", {
        "aggregate_components": result_pairs,
        "harmonized_deepseek_review_results_sha256": digest(result_pairs),
        "is_archival_export_not_original_results_root": True,
    })
    (TARGET / "harmonized_deepseek_review_results_sha256").write_text(digest(result_pairs) + "\n", encoding="utf-8")
    all_paths = [path for path in sorted(TARGET.iterdir()) if path.is_file() and path.name != "search_plan_v24_dev_alpha3_14e_sha256"]
    root_pairs = [[path.name, sha(path)] for path in all_paths]
    root = digest(root_pairs)
    (TARGET / "search_plan_v24_dev_alpha3_14e_sha256").write_text(root + "\n", encoding="utf-8")
    require(all(sha(TARGET / name) == checksum for name, checksum in root_pairs), "archive component drift")
    require(digest(root_pairs) == (TARGET / "search_plan_v24_dev_alpha3_14e_sha256").read_text().strip(), "archive root drift")
    print(json.dumps({"status": "failed_protocol_chronology", "archive_root": root,
                      "source_blinded_root": EXPECTED_BLINDED_ROOT, "source_results_root": EXPECTED_RESULTS_ROOT,
                      "new_provider_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
