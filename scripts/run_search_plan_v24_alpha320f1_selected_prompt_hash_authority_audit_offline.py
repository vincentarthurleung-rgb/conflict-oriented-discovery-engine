#!/usr/bin/env python3
"""Audit frozen Builder V4 selected-prompt hash authority without mutation."""

from __future__ import annotations

import hashlib
import json
import os
import re
from itertools import zip_longest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
B = RUNS / "20261002_search_plan_v24_dev_alpha3_20b_proposition_abstraction_prompt_freeze_offline"
F = RUNS / "20261004_search_plan_v24_dev_alpha3_20f_final_builder_v4_contract_freeze_offline"
OUT = RUNS / "20261005_search_plan_v24_dev_alpha3_20f1_selected_prompt_hash_authority_audit_offline"
ROOT_MARKER = "search_plan_v24_dev_alpha3_20f1_sha256"
B_ROOT = "0c5e11b5e53acda51250fca80a544e39fda06c40e9ac2bff138d96ae7cf42e2d"
F_ROOT = "cc76b168c80634510168a759815dbf7ab905d5e67292b3393a6b9c6a537847c6"
PROMPT_SHA = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f7f06e88a48722be213454d7592"
REPORTED_MALFORMED_SHA = "6af5b7f3cd8b23cc65e4ee9c3e85eb955d760f706e88a48722be213454d7592"
CONTRACT_SHA = "53b50a78694b6ed53369347fa8ade3675fd9d28395735b3607f2e3329871436e"
BUNDLE_SHA = "c9fd917fd44aab8e70face99f3bc1a2630d7177462dbdb09a73fe03821c69158"
CLOSURE_SHA = "8b960305a6d6f1811a4d576d9b116a5cc478e15f412f0780dcba3608cd4b54d3"
CLASS_REPORT_ONLY = "ALPHA3_20F_REPORT_ONLY_HASH_TRANSCRIPTION_ERROR"
CLASS_METADATA_DEFECT = "ALPHA3_20F_NONSCIENTIFIC_HASH_METADATA_DEFECT"
CLASS_BYTE_MISMATCH = "ALPHA3_20F_SELECTED_PROMPT_BYTE_MISMATCH"
CLASS_UNRESOLVED = "ALPHA3_20F_HASH_AUTHORITY_UNRESOLVED"
NEXT_READY = "PREREGISTER_NEXT_FRESH_PRIMARY_ATTEMPT_WITH_FROZEN_BUILDER_V4"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest(path: Path) -> str:
    return sha(path.read_bytes())


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def root_hash(directory: Path, marker: str) -> str:
    require(not any(p.is_symlink() for p in directory.rglob("*")),
            "FROZEN_SYMLINK_FORBIDDEN")
    files = sorted(p for p in directory.rglob("*") if p.is_file()
                   and p.name != marker)
    return sha(canonical([[str(p.relative_to(directory)), digest(p)]
                          for p in files]))


def read_json(path: Path) -> dict:
    return json.loads(path.read_bytes())


def file_ref(path: Path, role: str, stage: str) -> dict:
    return {"artifact_role": role, "artifact_path": str(path.relative_to(ROOT)),
            "sha256": digest(path), "authority_source_stage": stage,
            "immutable_frozen": True}


def put(name: str, value: object) -> str:
    raw = canonical(value) + b"\n"
    with (OUT / name).open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    return sha(raw)


def marker(name: str, value: str) -> None:
    with (OUT / name).open("xb") as handle:
        handle.write((value + "\n").encode("ascii"))
        handle.flush()
        os.fsync(handle.fileno())


def verify_root(directory: Path, marker_name: str, expected: str) -> bool:
    return ((directory / marker_name).read_text(encoding="ascii").strip()
            == expected and root_hash(directory, marker_name) == expected)


def first_mismatch(left: bytes, right: bytes) -> int | None:
    return next((index for index, pair in enumerate(zip_longest(left, right))
                 if pair[0] != pair[1]), None)


def json_leaves(value: object, pointer: str = "", parent: dict | None = None):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from json_leaves(child, pointer + "/" + key, value)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from json_leaves(child, pointer + "/" + str(index), parent)
    else:
        yield pointer, value, parent or {}


def audit_references() -> dict:
    references, hash_fields, inspected = [], [], []
    prompt_roles = {"selected_v1_prompt_source", "final_selected_prompt",
                    "selected_v1_full_prompt"}
    for path in sorted(F.iterdir()):
        if not path.is_file() or path.name == "final_selected_builder_v4_prompt.txt":
            continue
        inspected.append(path.name)
        if path.suffix == ".json":
            leaves = json_leaves(read_json(path))
        elif path.name.endswith("_sha256"):
            leaves = [("/value", path.read_text(encoding="ascii").strip(), {})]
        else:
            continue
        for pointer, value, parent in leaves:
            if not isinstance(value, str):
                continue
            key = pointer.rsplit("/", 1)[-1]
            hash_field = (key == "sha256" or key.endswith("_sha256")
                          or "/component_sha256_by_role/" in pointer
                          or path.name.endswith("_sha256"))
            if not hash_field:
                continue
            row = {"artifact_path": str(path.relative_to(ROOT)),
                   "json_pointer": pointer, "stored_value": value,
                   "length": len(value),
                   "valid_lowercase_sha256_syntax": bool(HEX64.fullmatch(value))}
            hash_fields.append(row)
            selected = (value in (PROMPT_SHA, REPORTED_MALFORMED_SHA)
                        or key in ("final_selected_builder_v4_prompt_sha256",
                                   "expected_selected_prompt_sha256",
                                   "selected_v1_full_prompt")
                        or parent.get("artifact_role") in prompt_roles
                        or path.name == "final_selected_builder_v4_prompt_sha256")
            if selected:
                references.append({**row,
                    "equals_authoritative_prompt_digest": value == PROMPT_SHA,
                    "equals_reported_malformed_digest":
                        value == REPORTED_MALFORMED_SHA})
    return {"scope": "all alpha3.20F JSON hash fields and SHA-256 marker files",
            "inspected_files": inspected,
            "selected_prompt_hash_references": references,
            "stored_hash_reference_count": len(references),
            "malformed_stored_hash_reference_count": sum(
                not row["valid_lowercase_sha256_syntax"] for row in references),
            "incorrect_valid_length_hash_reference_count": sum(
                row["valid_lowercase_sha256_syntax"]
                and not row["equals_authoritative_prompt_digest"]
                for row in references),
            "hash_fields": hash_fields,
            "hash_field_count": len(hash_fields),
            "malformed_hash_fields": [row for row in hash_fields
                                      if not row["valid_lowercase_sha256_syntax"]]}


def binding_state(entries: list[dict], expected_path: Path) -> str:
    if len(entries) != 1:
        return "AMBIGUOUS_BINDING"
    entry = entries[0]
    if entry.get("artifact_path") != str(expected_path.relative_to(ROOT)):
        return "INCORRECT_PROMPT_BINDING"
    stored = entry.get("sha256")
    if not isinstance(stored, str) or not HEX64.fullmatch(stored):
        return "MALFORMED_HASH_BINDING"
    if stored != PROMPT_SHA or digest(expected_path) != stored:
        return "INCORRECT_PROMPT_BINDING"
    return "SAFE_EXACT_BINDING"


def preflight() -> dict:
    require(not OUT.exists(), "ALPHA320F1_OUTPUT_ALREADY_EXISTS")
    require(verify_root(F, "search_plan_v24_dev_alpha3_20f_sha256", F_ROOT),
            "ALPHA320F_ROOT_MISMATCH")
    require(verify_root(B, "search_plan_v24_dev_alpha3_20b_sha256", B_ROOT),
            "ALPHA320B_ROOT_MISMATCH")
    for path, expected in (
        (B / "prompt_variant_1_sha256", PROMPT_SHA),
        (F / "search_plan_builder_v4_final_contract.json", CONTRACT_SHA),
        (F / "builder_v4_reproducibility_bundle.json", BUNDLE_SHA),
        (F / "alpha3_20_development_closure_manifest.json", CLOSURE_SHA),
    ):
        actual = (path.read_text(encoding="ascii").strip()
                  if path.name.endswith("_sha256") else digest(path))
        require(actual == expected, "AUTHORITY_COMPONENT_MISMATCH:" + path.name)
    return {"b_prompt_bytes": (B / "prompt_variant_1_full_template.txt").read_bytes(),
            "f_prompt_bytes": (F / "final_selected_builder_v4_prompt.txt").read_bytes()}


def run() -> dict:
    state = preflight()
    b_bytes, f_bytes = state["b_prompt_bytes"], state["f_prompt_bytes"]
    b_sha, f_sha = sha(b_bytes), sha(f_bytes)
    byte_equal = b_bytes == f_bytes
    inventory = audit_references()
    contract = read_json(F / "search_plan_builder_v4_final_contract.json")
    bundle = read_json(F / "builder_v4_reproducibility_bundle.json")
    closure = read_json(F / "alpha3_20_development_closure_manifest.json")
    prompt_path = F / "final_selected_builder_v4_prompt.txt"
    contract_entries = [item for item in contract["components"]
                        if item.get("artifact_role") == "selected_v1_full_prompt"]
    contract_state = binding_state(contract_entries, prompt_path)
    bundle_entries = [bundle.get("selected_prompt", {})]
    bundle_state = binding_state(bundle_entries, prompt_path)
    bundle_map_sha = bundle.get("component_sha256_by_role", {}).get(
        "selected_v1_full_prompt")
    bundle_contract = bundle.get("final_contract", {})
    if (bundle_state == "SAFE_EXACT_BINDING"
        and (bundle_map_sha != PROMPT_SHA
             or bundle_contract.get("sha256") != CONTRACT_SHA
             or bundle_contract.get("artifact_path") !=
                str((F / "search_plan_builder_v4_final_contract.json").relative_to(ROOT)))):
        bundle_state = "INCORRECT_PROMPT_BINDING"
    if not byte_equal:
        classification = CLASS_BYTE_MISMATCH
    elif b_sha != PROMPT_SHA or f_sha != PROMPT_SHA:
        classification = CLASS_UNRESOLVED
    elif (inventory["malformed_stored_hash_reference_count"]
          or inventory["incorrect_valid_length_hash_reference_count"]
          or inventory["malformed_hash_fields"]
          or contract_state != "SAFE_EXACT_BINDING"
          or bundle_state != "SAFE_EXACT_BINDING"):
        classification = CLASS_METADATA_DEFECT
    else:
        classification = CLASS_REPORT_ONLY
    correction = classification == CLASS_METADATA_DEFECT
    ready = classification == CLASS_REPORT_ONLY
    next_stage = {
        CLASS_REPORT_ONLY: NEXT_READY,
        CLASS_METADATA_DEFECT:
            "FREEZE_ALPHA3_20F2_NONSCIENTIFIC_CONTRACT_AUTHORITY_CORRECTION",
        CLASS_BYTE_MISMATCH:
            "AUDIT_ALPHA3_20F_SELECTED_PROMPT_PROVENANCE_OFFLINE",
        CLASS_UNRESOLVED:
            "AUDIT_ALPHA3_20F_CONTRACT_AUTHORITY_PRECEDENCE_OFFLINE",
    }[classification]
    OUT.mkdir()
    put("alpha3_20f_root_verification.json", {"root_sha256": F_ROOT,
        "stored_marker_matches": True, "recalculated_root_matches": True,
        "verified": True})
    put("alpha3_20b_root_verification.json", {"root_sha256": B_ROOT,
        "stored_marker_matches": True, "recalculated_root_matches": True,
        "verified": True})
    put("alpha3_20b_v1_prompt_byte_hash_audit.json", {
        "prompt": file_ref(B / "prompt_variant_1_full_template.txt",
                           "authoritative_v1_prompt", "alpha3.20B"),
        "file_size_bytes": len(b_bytes), "actual_sha256": b_sha,
        "matches_authoritative_expected_sha256": b_sha == PROMPT_SHA,
        "stored_b_prompt_sha256_marker_matches":
            (B / "prompt_variant_1_sha256").read_text().strip() == b_sha})
    put("alpha3_20f_selected_prompt_byte_hash_audit.json", {
        "prompt": file_ref(prompt_path, "final_selected_prompt", "alpha3.20F"),
        "file_size_bytes": len(f_bytes), "actual_sha256": f_sha,
        "matches_authoritative_expected_sha256": f_sha == PROMPT_SHA})
    put("selected_prompt_direct_byte_comparison.json", {
        "alpha3_20b_v1_size_bytes": len(b_bytes),
        "alpha3_20f_final_size_bytes": len(f_bytes),
        "alpha3_20b_v1_sha256": b_sha,
        "alpha3_20f_final_sha256": f_sha,
        "byte_identical": byte_equal,
        "first_mismatch_offset": first_mismatch(b_bytes, f_bytes)})
    put("alpha3_20f_selected_prompt_hash_reference_inventory.json", {
        key: value for key, value in inventory.items() if key != "hash_fields"})
    put("alpha3_20f_hash_syntax_audit.json", {
        "hash_field_count": inventory["hash_field_count"],
        "malformed_hash_field_count": len(inventory["malformed_hash_fields"]),
        "malformed_hash_fields": inventory["malformed_hash_fields"],
        "required_syntax": "exactly 64 lowercase hexadecimal characters",
        "reported_outside_repository_hash_length": len(REPORTED_MALFORMED_SHA),
        "reported_outside_repository_hash_valid_syntax":
            bool(HEX64.fullmatch(REPORTED_MALFORMED_SHA))})
    put("final_composite_contract_prompt_binding_audit.json", {
        "contract": file_ref(F / "search_plan_builder_v4_final_contract.json",
                             "final_composite_contract", "alpha3.20F"),
        "selected_prompt_component_count": len(contract_entries),
        "selected_prompt_components": contract_entries,
        "binding_state": contract_state})
    put("reproducibility_bundle_prompt_binding_audit.json", {
        "bundle": file_ref(F / "builder_v4_reproducibility_bundle.json",
                           "prospective_reproducibility_bundle", "alpha3.20F"),
        "selected_prompt_binding": bundle_entries[0],
        "selected_prompt_component_hash": bundle_map_sha,
        "final_contract_binding": bundle_contract,
        "binding_state": bundle_state})
    put("closure_manifest_prompt_hash_audit.json", {
        "closure_manifest": file_ref(F /
            "alpha3_20_development_closure_manifest.json",
            "development_closure_manifest", "alpha3.20F"),
        "selected_prompt_sha256_field_present":
            any("prompt" in pointer and "sha256" in pointer
                for pointer, _, _ in json_leaves(closure)),
        "final_composite_contract_sha256_matches":
            closure.get("final_builder_v4_contract_sha256") == CONTRACT_SHA,
        "final_bundle_sha256_matches":
            closure.get("final_reproducibility_bundle_sha256") == BUNDLE_SHA,
        "reporting_only_field_distinguished_from_runtime_binding": True})
    put("selected_prompt_hash_authority_classification.json", {
        "classification": classification,
        "classification_is_exclusive": True,
        "reported_malformed_hash": REPORTED_MALFORMED_SHA,
        "reported_malformed_hash_length": len(REPORTED_MALFORMED_SHA),
        "reported_malformed_hash_origin": "prior response text, not frozen repository artifact",
        "on_disk_selected_prompt_hashes_all_correct":
            inventory["malformed_stored_hash_reference_count"] == 0
            and inventory["incorrect_valid_length_hash_reference_count"] == 0,
        "selected_prompt_scientific_bytes_valid":
            byte_equal and b_sha == f_sha == PROMPT_SHA,
        "contract_correction_required": correction})
    put("selected_prompt_authoritative_binding.json", {
        "selected_prompt_authoritative_sha256":
            PROMPT_SHA if byte_equal and b_sha == f_sha == PROMPT_SHA else None,
        "alpha3_20b_v1_prompt": file_ref(B /
            "prompt_variant_1_full_template.txt", "authoritative_v1_prompt",
            "alpha3.20B"),
        "alpha3_20f_selected_prompt": file_ref(prompt_path,
            "final_selected_prompt", "alpha3.20F"),
        "alpha3_20b_root_sha256": B_ROOT,
        "alpha3_20f_root_sha256": F_ROOT,
        "byte_identical": byte_equal,
        "future_consumption_rule":
            "verify alpha3.20F root and selected prompt exact SHA-256 before use"})
    if correction:
        put("prospective_builder_v4_hash_authority_correction_draft.json", {
            "scope": "non-scientific authority metadata only",
            "selected_prompt_path": str(prompt_path.relative_to(ROOT)),
            "actual_sha256": f_sha, "alpha3_20b_v1_sha256": b_sha,
            "alpha3_20f_root_sha256": F_ROOT,
            "future_consumption_rule":
                "use verified byte-derived SHA-256; do not mutate alpha3.20F"})
    put("fresh_primary_readiness_audit.json", {
        "builder_v4_contract_ready_for_fresh_attempt": ready,
        "fresh_primary_attempt_started": False,
        "new_queries_or_requests_created": False,
        "next_stage_recommendation": next_stage})
    put("historical_preservation_audit.json", {
        "alpha3_20b_root_unchanged": verify_root(B,
            "search_plan_v24_dev_alpha3_20b_sha256", B_ROOT),
        "alpha3_20f_root_unchanged": verify_root(F,
            "search_plan_v24_dev_alpha3_20f_sha256", F_ROOT),
        "historical_assets_modified": False})
    put("scientific_state_safety_audit.json", {
        "scientific_policy_changed": False,
        "selected_variant_changed": False,
        "prompt_bytes_modified": False,
        "builder_v4_changed": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0})
    validation = {"status": "completed",
        "alpha3_20f1_classification": classification,
        "alpha3_20f_root_verified": True,
        "alpha3_20b_root_verified": True,
        "alpha3_20b_v1_prompt_actual_sha256": b_sha,
        "alpha3_20f_selected_prompt_actual_sha256": f_sha,
        "selected_prompt_byte_identical": byte_equal,
        "expected_authoritative_v1_sha256": PROMPT_SHA,
        "stored_hash_reference_count": inventory["stored_hash_reference_count"],
        "malformed_stored_hash_reference_count":
            inventory["malformed_stored_hash_reference_count"],
        "incorrect_valid_length_hash_reference_count":
            inventory["incorrect_valid_length_hash_reference_count"],
        "composite_contract_prompt_binding_state": contract_state,
        "reproducibility_bundle_prompt_binding_state": bundle_state,
        "alpha3_20f_final_contract_scientific_authority_valid": ready,
        "alpha3_20f_contract_correction_required": correction,
        "builder_v4_contract_ready_for_fresh_attempt": ready,
        "selected_prompt_authoritative_sha256":
            PROMPT_SHA if byte_equal and b_sha == f_sha == PROMPT_SHA else None,
        "scientific_policy_changed": False,
        "selected_variant_changed": False,
        "prompt_bytes_modified": False,
        "historical_assets_modified": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "next_stage_recommendation": next_stage}
    put("validation.json", validation)
    put("summary.json", {"status": "completed",
        "classification": classification,
        "selected_prompt_byte_identical": byte_equal,
        "builder_v4_contract_ready_for_fresh_attempt": ready,
        "next_stage_recommendation": next_stage})
    root = root_hash(OUT, ROOT_MARKER)
    marker(ROOT_MARKER, root)
    return {**validation, ROOT_MARKER: root}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
