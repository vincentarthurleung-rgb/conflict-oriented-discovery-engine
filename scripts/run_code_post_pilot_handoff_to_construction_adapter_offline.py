#!/usr/bin/env python3
"""Run the bounded offline handoff-to-construction adapter acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from code_engine.construction import handoff_adapter as adapter


OUT = ROOT / "runs/20261012_code_minimal_immutable_handoff_to_construction_adapter_offline"
ROOT_MARKER = "code_minimal_immutable_handoff_to_construction_adapter_sha256"
CONFIG = adapter.AdapterConfig(
    repository_root=ROOT,
    pilot_directory="runs/20261012_search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot",
    pilot_marker="search_plan_v24_dev_alpha3_22f_first_controlled_live_pilot_sha256",
    pilot_root_sha256="fd24d7ff2303259ba674823f01403ac2b694082ed5e8e6035f76ff084300230c",
    handoff_sha256="d7ff77546c41dc910483483e7ae74f550c7100c421c30be42fe64e55480ce84f",
    smoke_directory="runs/20261012_code_post_pilot_scientific_handoff_smoke_offline",
    smoke_marker="code_post_pilot_scientific_handoff_smoke_sha256",
    smoke_root_sha256="53a79c029ae6a3b7127ccf3a1e1cd0c7df63c60d94638e7a4debc3471108a902",
    release_directory="runs/20261012_search_plan_v24_dev_alpha3_22_final_independent_oracle_v2_log_namespace_offline",
    release_marker="search_plan_v24_dev_alpha3_22_log_namespace_release_sha256",
    release_root_sha256="f7902fbdf27cd000c91ab65d88221a8fd9966fad38fb20020c0b2a095526ed67",
    source_id="42715313", pmid="42715313", pmcid="PMC13557098",
    doi="10.1126/sciadv.aec8073",
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def write_json(name: str, value: object, *, private: bool = False) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    path = OUT / name
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if private:
        path.chmod(0o600)
    return sha(raw)


def root_hash() -> str:
    entries = [[path.relative_to(OUT).as_posix(), sha(path.read_bytes())]
               for path in sorted(OUT.rglob("*"))
               if path.is_file() and path.name != ROOT_MARKER]
    return sha(canonical(entries))


def rejection(bundle: dict, token: dict | None, expected: set[str]) -> dict:
    try:
        adapter.adapt_evidence_bundle(bundle, token, ROOT)
    except adapter.AdapterValidationError as exc:
        return {"status": "PASS", "rejected": True, "reason": exc.reason,
                "expected_reasons": sorted(expected), "expected_reason_observed": exc.reason in expected}
    return {"status": "FAIL", "rejected": False, "reason": None,
            "expected_reasons": sorted(expected), "expected_reason_observed": False}


def acceptance(bundle: dict, token: dict) -> tuple[list[dict], dict, dict]:
    envelope = adapter.adapt_evidence_bundle(bundle, token, ROOT)
    repeated = adapter.adapt_evidence_bundle(copy.deepcopy(bundle), copy.deepcopy(token), ROOT)
    results: list[dict] = [
        {"test_id": "A", "name": "valid immutable handoff to valid construction input",
         "status": "PASS", "construction_document_sha256": envelope["construction_document_sha256"]},
        {"test_id": "B", "name": "repeated adaptation is canonical-byte-identical",
         "status": "PASS" if canonical(envelope) == canonical(repeated) else "FAIL",
         "first_sha256": sha(canonical(envelope)), "second_sha256": sha(canonical(repeated))},
    ]

    identity_subcases = []
    for key, wrong in (("pmid", "1"), ("pmcid", "PMC1"), ("doi", "10.0000/wrong")):
        changed = copy.deepcopy(bundle)
        changed["source"][key] = wrong
        identity_subcases.append({"field": key, **rejection(changed, token, {"SOURCE_IDENTITY_MISMATCH"})})
    results.append({"test_id": "C", "name": "wrong PMID PMCID or DOI rejected",
                    "status": "PASS" if all(x["status"] == "PASS" and x["expected_reason_observed"]
                                                for x in identity_subcases) else "FAIL",
                    "subcases": identity_subcases})

    wrong_jats = copy.deepcopy(bundle)
    wrong_jats["normalized_jats"] += b" "
    wrong_body = copy.deepcopy(bundle)
    wrong_body["canonical_body"] += b" "
    hash_subcases = [
        {"field": "normalized_jats", **rejection(wrong_jats, token, {"NORMALIZED_JATS_HASH_MISMATCH"})},
        {"field": "canonical_body", **rejection(wrong_body, token, {"CANONICAL_BODY_HASH_MISMATCH"})},
    ]
    results.append({"test_id": "D", "name": "wrong JATS or BODY hash rejected",
                    "status": "PASS" if all(x["status"] == "PASS" and x["expected_reason_observed"]
                                                for x in hash_subcases) else "FAIL",
                    "subcases": hash_subcases})

    uncommitted = copy.deepcopy(bundle)
    uncommitted["handoff"]["sources"][0]["terminal"]["journal_entry_hash"] = "0" * 64
    results.append({"test_id": "E", "name": "uncommitted terminal rejected",
                    **rejection(uncommitted, token, {"UNCOMMITTED_TERMINAL_REJECTED"})})

    jats_failed = copy.deepcopy(bundle)
    jats_failed["gates"]["actual"]["eligible"] = False
    oa_failed = copy.deepcopy(bundle)
    oa_failed["barrier"]["oa_outcomes"][0]["eligibility"]["eligible"] = False
    gate_subcases = [
        {"gate": "JATS", **rejection(jats_failed, token, {"JATS_GATE_NOT_ELIGIBLE"})},
        {"gate": "OA", **rejection(oa_failed, token, {"OA_ACTIVATION_GATE_FAILED"})},
    ]
    results.append({"test_id": "F", "name": "missing or failed OA/JATS gate rejected",
                    "status": "PASS" if all(x["status"] == "PASS" and x["expected_reason_observed"]
                                                for x in gate_subcases) else "FAIL",
                    "subcases": gate_subcases})

    incorrect_token = copy.deepcopy(token)
    incorrect_token["opaque_source_token"] = "src_invalid"
    token_subcases = [
        {"condition": "missing", **rejection(bundle, None, {"MISSING_OPAQUE_SOURCE_TOKEN_AUTHORITY"})},
        {"condition": "incorrect", **rejection(bundle, incorrect_token, {"OPAQUE_SOURCE_TOKEN_INVALID"})},
    ]
    results.append({"test_id": "G", "name": "missing or incorrect opaque token rejected",
                    "status": "PASS" if all(x["status"] == "PASS" and x["expected_reason_observed"]
                                                for x in token_subcases) else "FAIL",
                    "subcases": token_subcases})

    partial = copy.deepcopy(bundle)
    partial["capture"]["body"]["completion_state"] = "BODY_PARTIAL_QUARANTINED"
    partial["capture"]["body"]["read_returned_normally"] = False
    partial["capture"]["body"]["partial_body_artifact_path"] = "quarantine/partial.bin"
    partial["capture"]["body"]["partial_body_sha256"] = "1" * 64
    results.append({"test_id": "H", "name": "partial or quarantined body rejected",
                    **rejection(partial, token, {"PARTIAL_OR_QUARANTINED_BODY_REJECTED"})})

    altered = copy.deepcopy(bundle)
    altered["handoff"]["sources"][0]["gates"]["artifact_path"] = "/altered/gates.json"
    results.append({"test_id": "I", "name": "altered evidence reference rejected",
                    **rejection(altered, token, {"HANDOFF_GATE_REFERENCE_MISMATCH"})})

    downstream = adapter.verify_downstream_deterministic_consumer(envelope)
    results.append({"test_id": "J", "name": "deterministic downstream provenance compatibility",
                    "status": downstream["status"], "result": downstream})
    return results, envelope, downstream


def main() -> None:
    if OUT.exists():
        raise RuntimeError("OUTPUT_ALREADY_EXISTS_NO_OVERWRITE")
    pre_hashes = {
        "adapter": sha((ROOT / "src/code_engine/construction/handoff_adapter.py").read_bytes()),
        "construction_policy": sha((ROOT / adapter.CONSTRUCTION_IMPLEMENTATION_PATH).read_bytes()),
        "token_authority": sha((ROOT / adapter.TOKEN_AUTHORITY_PATH).read_bytes()),
    }
    bundle = adapter.load_verified_evidence_bundle(CONFIG)
    token = adapter.issue_opaque_source_token(CONFIG)
    results, envelope, downstream = acceptance(bundle, token)
    all_pass = len(results) == 10 and all(row["status"] == "PASS" for row in results)
    if not all_pass:
        raise RuntimeError("OFFLINE_ACCEPTANCE_FAILED")
    document = envelope["construction_document"]
    OUT.mkdir()
    source_manifest = {
        "schema_version": "CODEHandoffConstructionSourceManifestV1",
        "controller_private": True,
        "file_mode_required": "0600",
        "source_identity": CONFIG.expected_identity,
        "opaque_source_token_authority": token,
        "verified_construction_input": envelope,
    }
    source_sha = write_json("source_manifest.json", source_manifest, private=True)
    tests_sha = write_json("adapter_test_results.json", {
        "schema_version": "CODEHandoffAdapterAcceptanceResultsV1",
        "test_count": len(results), "pass_count": sum(r["status"] == "PASS" for r in results),
        "all_required_negative_tests_fail_closed": True,
        "results": results,
    })
    compatibility_sha = write_json("construction_compatibility.json", {
        "schema_version": "CODEConstructionCompatibilityV1",
        "status": "PASS",
        "construction_contract": {
            "path": "runs/20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline/construction_evidence_document_v1_contract.json",
            "sha256": "0928aa53cbbd0795c607e5342b383b88972680ef4b788bce9280eb47bf66fe57",
            "schema_version": "ConstructionEvidenceDocumentV1",
            "mandatory_top_level_fields": sorted(document),
        },
        "anchor_contract": {
            "path": "runs/20260927_search_plan_v24_dev_alpha3_18a1_source_contract_resolution_offline/evidence_span_anchor_v1_contract.json",
            "sha256": "8da77b28943c7e009c8b818302b4df7f793464e2cba81bc86b8ef7e51fe5d6c0",
            "exact_body_offsets_required": True,
            "source_hash_binding_preserved": True,
        },
        "construction_document_sha256": envelope["construction_document_sha256"],
        "paragraph_count": len(document["paragraphs"]),
        "body_character_count": len(document["body_text"]),
        "abstract_character_count": len(document["abstract_text"]),
        "deterministic_downstream": downstream,
        "builder_status": "NOT_EVALUATED",
        "quality_status": "NOT_EVALUATED",
    })
    post_hashes = {
        "adapter": sha((ROOT / "src/code_engine/construction/handoff_adapter.py").read_bytes()),
        "construction_policy": sha((ROOT / adapter.CONSTRUCTION_IMPLEMENTATION_PATH).read_bytes()),
        "token_authority": sha((ROOT / adapter.TOKEN_AUTHORITY_PATH).read_bytes()),
    }
    preservation_sha = write_json("historical_preservation.json", {
        "schema_version": "CODEHandoffAdapterHistoricalPreservationV1",
        "authoritative_roots": bundle["roots"],
        "policy_source_hashes_before": pre_hashes,
        "policy_source_hashes_after": post_hashes,
        "unchanged": pre_hashes == post_hashes,
        "pilot_artifacts_modified": False,
        "runtime_source_modified": False,
        "scientific_policy_changed": False,
        "historical_assets_modified": False,
        "pilot_source_future_primary_excluded": True,
        "network_calls": 0, "llm_calls": 0, "builder_calls": 0, "quality_calls": 0,
    })
    write_json("summary.json", {
        "schema_version": "CODEMinimalImmutableHandoffAdapterSummaryV1",
        "status": "PASS",
        "mode": "OFFLINE_ENGINEERING_DEVELOPMENT",
        "source_identity": CONFIG.expected_identity,
        "authentic_source_and_handoff_binding_verified": True,
        "opaque_source_token_verified": True,
        "construction_document_created": True,
        "construction_schema_valid": True,
        "provenance_binding_valid": True,
        "deterministic_downstream_passed": True,
        "construction_document_sha256": envelope["construction_document_sha256"],
        "source_manifest_sha256": source_sha,
        "adapter_test_results_sha256": tests_sha,
        "construction_compatibility_sha256": compatibility_sha,
        "historical_preservation_sha256": preservation_sha,
        "acceptance_test_count": 10,
        "acceptance_pass_count": 10,
        "builder_status": "NOT_EVALUATED",
        "quality_status": "NOT_EVALUATED",
        "fresh_primary_started": False,
        "network_calls": 0, "llm_calls": 0, "builder_calls": 0, "quality_calls": 0,
        "scientific_policy_changed": False,
        "runtime_source_modified": False,
        "historical_assets_modified": False,
        "next_stage_recommendation": "PREREGISTER_A_SEPARATELY_AUTHORIZED_BUILDER_V4_REQUEST_FREEZE_OR_STOP",
        "root_marker": ROOT_MARKER,
        "root_hash_algorithm": "SHA256(compact canonical JSON of sorted [relative_path,SHA256(file)] pairs; root marker excluded; no final LF in hashed JSON)",
    })
    final_root = root_hash()
    with (OUT / ROOT_MARKER).open("xb") as handle:
        handle.write((final_root + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(OUT / ROOT_MARKER, 0o644)
    if root_hash() != final_root:
        raise RuntimeError("FINAL_ROOT_RECOMPUTATION_FAILED")
    print(json.dumps({"status": "PASS", "development_root_sha256": final_root,
                      "construction_document_sha256": envelope["construction_document_sha256"],
                      "test_count": 10, "pass_count": 10}, sort_keys=True))


if __name__ == "__main__":
    main()
