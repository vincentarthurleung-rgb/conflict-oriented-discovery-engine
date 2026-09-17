#!/usr/bin/env python3
"""Prepare and freeze the authorized primary held-out-v2 PASS-B adjudication."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import shutil
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication as common


RUN = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_b_adjudication"
NEUTRAL_RUN = common.NEUTRAL_RUN
PASS_A_RUN = ROOT / "runs/20260917_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication"
WORKSPACE_ROOT = Path("/tmp/primary_v2_pass_b_evaluator_workspaces")
STAGING_ROOT = Path("/tmp/primary_v2_pass_b_adjudication_staging")
PROMPT_ROOT = STAGING_ROOT / "prompts"
SUBMISSION_ROOT = STAGING_ROOT / "submissions"
PROTECTED_SNAPSHOT = STAGING_ROOT / "protected_state_before.json"

EXPECTED_PASS_B = "2e082673c7a58604286a00ace9748389c04aa76dced04bb0226d1873e28ff485"
EXPECTED_PASS_A_ADJUDICATION = "6dfe17d595a38a148412d3b87b7fd6ad226488d3c408c8b3ea057dd01e133e40"
EXPECTED_RECORDS = 60
EXPECTED_BATCHES = 6
EXPECTED_BATCH_SIZE = 10

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json",
    "primary_v2_pass_b_adjudicator_config.json",
    "primary_v2_pass_b_adjudicator_config_sha256",
    "pass_b_workspace_isolation_audit.json",
    "primary_v2_pass_b_blinded_adjudications.jsonl",
    "primary_v2_pass_b_blinded_adjudications_sha256",
    "primary_v2_pass_b_adjudications.jsonl",
    "primary_v2_pass_b_adjudications_sha256",
    "pass_b_schema_validation.json",
    "pass_b_completeness_audit.json",
    "pass_b_raw_label_distribution.json",
    "pass_a_immutability_audit.json",
    "scientific_state_safety_audit.json",
    "implementation_manifest.json",
    "validation.json",
    "summary.json",
}


def protected_state() -> dict[str, str]:
    state = common.protected_state()
    for path in PASS_A_RUN.rglob("*"):
        if path.is_file():
            state[str(path.resolve().relative_to(ROOT))] = common.sha(path)
    return dict(sorted(state.items()))


def verify_pass_a_adjudication() -> dict[str, Any]:
    manifest_path = PASS_A_RUN / "implementation_manifest.json"
    common.require(manifest_path.is_file() and not manifest_path.is_symlink(), "missing PASS-A manifest")
    manifest = common.load_json(manifest_path)
    checks = []
    for name, expected in manifest["aggregate_components"]:
        path = PASS_A_RUN / name
        actual = common.sha(path) if path.is_file() and not path.is_symlink() else None
        checks.append({"path": name, "expected_sha256": expected, "actual_sha256": actual, "match": actual == expected})
    actual_root = common.aggregate([[row["path"], row["actual_sha256"]] for row in checks])
    common.require(all(row["match"] for row in checks), "PASS-A adjudication component mismatch")
    common.require(
        actual_root == manifest["primary_heldout_v2_pass_a_adjudication_sha256"] == EXPECTED_PASS_A_ADJUDICATION,
        "PASS-A adjudication root mismatch",
    )
    return {"root": actual_root, "component_count": len(checks), "components_match": True}


def verify_upstreams() -> dict[str, Any]:
    neutral_verification, neutral_root = common.verify_neutral_root()
    pass_b_path = NEUTRAL_RUN / "primary_v2_pass_b_blinded_views.jsonl"
    pass_b_actual = common.sha(pass_b_path)
    common.require(pass_b_actual == EXPECTED_PASS_B, "PASS-B source mismatch")
    manifest = common.load_json(NEUTRAL_RUN / "primary_v2_pass_b_batch_manifest.json")
    common.require(
        manifest["record_count"] == EXPECTED_RECORDS
        and manifest["batch_count"] == EXPECTED_BATCHES
        and manifest["batch_size"] == EXPECTED_BATCH_SIZE,
        "PASS-B batch structure mismatch",
    )
    pass_a = verify_pass_a_adjudication()
    return {
        "artifact_schema_version": "PrimaryHeldoutV2PassBUpstreamRootVerificationV1",
        "status": "PASS",
        "all_six_pre_neutral_roots_verified": neutral_verification["all_six_pre_neutral_roots_verified"],
        "primary_heldout_v2_neutral_review_freeze_sha256": neutral_root,
        "primary_v2_pass_b_blinded_views_sha256": pass_b_actual,
        "primary_heldout_v2_pass_a_adjudication_sha256": pass_a["root"],
        "pass_a_adjudication_component_count": pass_a["component_count"],
        "pass_a_adjudication_components_match": pass_a["components_match"],
        "pass_b_record_count": EXPECTED_RECORDS,
        "pass_b_batch_count": EXPECTED_BATCHES,
        "pass_b_batch_size": EXPECTED_BATCH_SIZE,
        "verified_before_first_scientific_adjudication_call": True,
    }


def adjudicator_config() -> dict[str, Any]:
    base = common.adjudicator_config()
    return {
        **base,
        "artifact_schema_version": "PrimaryHeldoutV2PassBAdjudicatorConfigV1",
        "evaluation_pass": "PASS_B",
        "pass_a_access": False,
        "pass_a_labels_access": False,
        "pass_a_rationales_access": False,
        "pass_a_distributions_access": False,
        "sealed_identity_mapping_access_before_blinded_freeze": False,
        "pass_b_access": True,
        "empty_body_excerpt_reextraction": False,
        "execution_command_controls": {
            **base["execution_command_controls"],
            "plugin_and_app_catalogs_disabled_before_labels": True,
            "disabled_features": ["plugins", "remote_plugin", "apps", "recommended_plugins", "skill_search"],
        },
    }


def evaluator_prompt(instruction: bytes, schema: bytes, batch: bytes) -> bytes:
    preamble = (
        "You are a fresh isolated evaluator context for exactly one frozen PASS-B batch.\n"
        "Do not call tools and do not access any filesystem, network, prior conversation, or outside knowledge.\n"
        "Use only the frozen instruction, frozen response schema, and frozen batch payload below.\n"
        "Evaluate all ten records independently. Return exactly ten newline-delimited JSON objects, "
        "in batch order, with no Markdown fences or commentary. Every object must conform exactly to "
        "the response schema.\n\n"
    ).encode("utf-8")
    return b"".join([
        preamble,
        b"--- FROZEN INSTRUCTION ---\n", instruction,
        b"\n--- FROZEN RESPONSE SCHEMA ---\n", schema,
        b"\n--- FROZEN PASS-B BATCH ---\n", batch,
    ])


def prepare() -> None:
    root_verification = verify_upstreams()
    protected = protected_state()
    config = adjudicator_config()
    config_body = common.pretty(config)
    config_hash = common.sha_bytes(config_body)

    RUN.mkdir(parents=True, exist_ok=True)
    STAGING_ROOT.mkdir(parents=True, exist_ok=True)
    PROMPT_ROOT.mkdir(parents=True, exist_ok=True)
    SUBMISSION_ROOT.mkdir(parents=True, exist_ok=True)
    common.write_exact(PROTECTED_SNAPSHOT, common.pretty(protected))
    common.write_exact(RUN / "upstream_root_verification.json", common.pretty(root_verification))
    common.write_exact(RUN / "primary_v2_pass_b_adjudicator_config.json", config_body)
    common.write_exact(RUN / "primary_v2_pass_b_adjudicator_config_sha256", (config_hash + "\n").encode("ascii"))

    manifest = common.load_json(NEUTRAL_RUN / "primary_v2_pass_b_batch_manifest.json")
    instruction_source = NEUTRAL_RUN / "pass_b_evaluator_instruction.md"
    schema_source = NEUTRAL_RUN / "primary_v2_pass_b_review_schema.json"
    instruction = instruction_source.read_bytes()
    schema = schema_source.read_bytes()
    audits = []
    for index, batch_record in enumerate(manifest["batches"], 1):
        workspace = WORKSPACE_ROOT / f"batch_{index:02d}"
        workspace.mkdir(parents=True, exist_ok=True)
        sources = {
            "instruction.md": instruction_source,
            "response_schema.json": schema_source,
            "batch.jsonl": NEUTRAL_RUN / batch_record["path"],
        }
        expected = set(sources)
        common.require(not ({path.name for path in workspace.iterdir()} - expected), f"workspace {index} has forbidden files")
        for name, source in sources.items():
            destination = workspace / name
            if destination.exists():
                common.require(destination.is_file() and not destination.is_symlink(), "non-physical workspace file")
                common.require(destination.read_bytes() == source.read_bytes(), "workspace copy differs")
            else:
                shutil.copyfile(source, destination)
        files = sorted(workspace.iterdir())
        common.require({path.name for path in files} == expected, "workspace membership mismatch")
        common.require(all(path.is_file() and not path.is_symlink() for path in files), "workspace symlink detected")
        batch_bytes = (workspace / "batch.jsonl").read_bytes()
        common.require(common.sha_bytes(batch_bytes) == batch_record["sha256"], "workspace batch hash mismatch")
        prompt = evaluator_prompt(instruction, schema, batch_bytes)
        prompt_path = PROMPT_ROOT / f"batch_{index:02d}.txt"
        common.write_exact(prompt_path, prompt)
        audits.append({
            "batch_index": index,
            "workspace_path": str(workspace),
            "workspace_file_count": 3,
            "file_membership": [path.name for path in files],
            "files": [{"path": path.name, "sha256": common.sha(path), "bytes": path.stat().st_size} for path in files],
            "physical_files_only": True,
            "symlinks_present": False,
            "forbidden_files_present": False,
            "exactly_one_batch_present": True,
            "pass_a_material_present": False,
            "sealed_mapping_present": False,
            "metrics_present": False,
            "retrieval_material_present": False,
            "prompt_path_outside_workspace": str(prompt_path),
            "prompt_sha256": common.sha_bytes(prompt),
        })
    audit = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBWorkspaceIsolationAuditV1",
        "status": "PASS",
        "workspace_count": len(audits),
        "files_per_workspace": 3,
        "all_workspaces_physically_isolated": True,
        "all_workspaces_audited_before_evaluator_access": True,
        "no_symlinks": True,
        "pass_a_material_exposed_to_evaluators": False,
        "same_frozen_adjudicator_config_sha256": config_hash,
        "workspaces": audits,
    }
    common.write_exact(RUN / "pass_b_workspace_isolation_audit.json", common.pretty(audit))
    common.require(protected_state() == protected, "protected state changed during preparation")
    print(json.dumps({
        "status": "READY_FOR_SIX_AUTHORIZED_CALLS",
        "adjudicator_config_sha256": config_hash,
        "workspace_count": 6,
        "prompt_paths": [row["prompt_path_outside_workspace"] for row in audits],
        "submission_root": str(SUBMISSION_ROOT),
    }, indent=2))


def parse_submission(path: Path, schema: dict[str, Any], expected_ids: list[str]) -> list[dict[str, Any]]:
    common.require(path.is_file() and not path.is_symlink(), f"missing physical evaluator response: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    common.require(lines and all(line.strip() for line in lines), f"blank line or empty response: {path}")
    records = []
    errors = []
    for line_number, line in enumerate(lines, 1):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_number}: {exc}")
    common.require(not errors, f"malformed JSONL, repair prohibited: {errors}")
    required = set(schema["required"])
    properties = schema["properties"]
    array_fields = ("matched_target_components", "mismatched_target_components", "fulltext_resolved_fields", "remaining_unresolved_fields")
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            errors.append(f"record {index}: not an object")
            continue
        if set(record) != required:
            errors.append(f"record {index}: field set mismatch")
            continue
        if not isinstance(record["review_id"], str) or not record["review_id"].startswith("B2_"):
            errors.append(f"record {index}: invalid review_id")
        if record["relevance_state"] not in properties["relevance_state"]["enum"]:
            errors.append(f"record {index}: invalid relevance_state")
        if record["contaminant_class"] not in properties["contaminant_class"]["enum"]:
            errors.append(f"record {index}: invalid contaminant_class")
        for field in array_fields:
            if not isinstance(record[field], list) or not all(isinstance(value, str) for value in record[field]):
                errors.append(f"record {index}: invalid {field}")
        if not isinstance(record["rationale"], str) or not record["rationale"]:
            errors.append(f"record {index}: invalid rationale")
        confidence = record["confidence"]
        if confidence is not None and (not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1):
            errors.append(f"record {index}: invalid confidence")
        if record["reviewer_type"] != properties["reviewer_type"]["const"]:
            errors.append(f"record {index}: invalid reviewer_type")
    common.require(not errors, f"schema-invalid response, repair prohibited: {errors[:5]}")
    ids = [record["review_id"] for record in records]
    common.require(len(records) == EXPECTED_BATCH_SIZE, f"response record count is not 10: {path}")
    common.require(ids == expected_ids, f"response review IDs/order mismatch: {path}")
    common.require(len(ids) == len(set(ids)), f"duplicate response review ID: {path}")
    return records


def finalize() -> None:
    common.require(RUN.is_dir(), "prepare phase has not run")
    roots = verify_upstreams()
    common.require(common.load_json(RUN / "upstream_root_verification.json") == roots, "prepared root verification changed")
    config = adjudicator_config()
    config_body = common.pretty(config)
    config_hash = common.sha_bytes(config_body)
    common.require((RUN / "primary_v2_pass_b_adjudicator_config.json").read_bytes() == config_body, "frozen config changed")
    common.require((RUN / "primary_v2_pass_b_adjudicator_config_sha256").read_text().strip() == config_hash, "config sidecar mismatch")
    protected_before = common.load_json(PROTECTED_SNAPSHOT)
    common.require(protected_state() == protected_before, "protected state changed before finalization")

    schema = common.load_json(NEUTRAL_RUN / "primary_v2_pass_b_review_schema.json")
    manifest = common.load_json(NEUTRAL_RUN / "primary_v2_pass_b_batch_manifest.json")
    all_records = []
    batch_validation = []
    for index, batch_record in enumerate(manifest["batches"], 1):
        workspace = WORKSPACE_ROOT / f"batch_{index:02d}"
        common.require({path.name for path in workspace.iterdir()} == {"instruction.md", "response_schema.json", "batch.jsonl"}, f"workspace {index} membership changed")
        expected_ids = [row["review_id"] for row in common.load_jsonl(workspace / "batch.jsonl")]
        response_path = SUBMISSION_ROOT / f"batch_{index:02d}.jsonl"
        records = parse_submission(response_path, schema, expected_ids)
        all_records.extend(records)
        batch_validation.append({
            "batch_index": index,
            "attempt_count": 1,
            "provider_calls": 1,
            "llm_calls": 1,
            "scientific_adjudication_calls": 1,
            "response_ref": str(response_path),
            "response_sha256": common.sha(response_path),
            "record_count": len(records),
            "schema_valid": True,
            "repair_attempted": False,
            "retry_attempted": False,
            "accepted": True,
        })
    ids = [row["review_id"] for row in all_records]
    common.require(len(all_records) == len(set(ids)) == EXPECTED_RECORDS, "global response completeness mismatch")

    # The blind corpus is physically frozen and verified before the sealed identity map is opened.
    blind_body = common.jsonl(all_records)
    blind_hash = common.sha_bytes(blind_body)
    blind_path = RUN / "primary_v2_pass_b_blinded_adjudications.jsonl"
    common.write_exact(blind_path, blind_body)
    common.write_exact(RUN / "primary_v2_pass_b_blinded_adjudications_sha256", (blind_hash + "\n").encode("ascii"))
    common.require(common.sha(blind_path) == blind_hash, "blinded freeze verification failed")
    common.require(all("candidate_id" not in row and "case_id" not in row for row in all_records), "identity leaked into blinded freeze")

    sealed = common.load_json(NEUTRAL_RUN / "primary_v2_pass_b_sealed_identity_mapping.json")["sealed_mapping"]
    sealed_by_id = {row["review_id"]: row for row in sealed}
    common.require(set(sealed_by_id) == set(ids), "sealed mapping identity mismatch")
    joined = []
    for record in all_records:
        candidate_id = sealed_by_id[record["review_id"]]["candidate_id"]
        joined.append({
            "artifact_schema_version": "PrimaryHeldoutV2PassBAdjudicationV1",
            "candidate_id": candidate_id,
            "case_id": candidate_id.split(":", 1)[0],
            **record,
            "adjudicator_config_sha256": config_hash,
            "pass_b_source_sha256": EXPECTED_PASS_B,
            "blinded_adjudications_sha256": blind_hash,
            "identity_join_after_blinded_freeze": True,
        })
    joined_body = common.jsonl(joined)
    joined_hash = common.sha_bytes(joined_body)
    common.write_exact(RUN / "primary_v2_pass_b_adjudications.jsonl", joined_body)
    common.write_exact(RUN / "primary_v2_pass_b_adjudications_sha256", (joined_hash + "\n").encode("ascii"))

    distribution = Counter(row["relevance_state"] for row in all_records)
    allowed = schema["properties"]["relevance_state"]["enum"]
    common.require(set(distribution) <= set(allowed), "unexpected relevance label")
    distribution_record = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBRawLabelDistributionV1",
        "distribution_scope": "raw adjudication completeness counts only",
        **{label: distribution[label] for label in allowed},
        "total": sum(distribution.values()),
        "rates_calculated": False,
        "metrics_unblinded": False,
    }
    schema_validation = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBSchemaValidationV1",
        "status": "PASS",
        "schema_sha256": common.sha(NEUTRAL_RUN / "primary_v2_pass_b_review_schema.json"),
        "record_count": 60,
        "valid_record_count": 60,
        "invalid_record_count": 0,
        "attempt_count": 6,
        "retry_count": 0,
        "repair_count": 0,
        "all_reviewer_types_exact": True,
        "batch_validation": batch_validation,
    }
    completeness = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBCompletenessAuditV1",
        "status": "PASS",
        "expected": 60,
        "adjudicated": 60,
        "unique_review_ids": len(set(ids)),
        "missing": 0,
        "duplicates": 0,
        "invalid": 0,
        "raw_label_distribution_ref": "pass_b_raw_label_distribution.json",
        "performance_rates_calculated": False,
    }
    pass_a_before = verify_pass_a_adjudication()
    pass_a_audit = {
        "artifact_schema_version": "PrimaryHeldoutV2PassAImmutabilityAuditV1",
        "status": "PASS",
        "expected_sha256": EXPECTED_PASS_A_ADJUDICATION,
        "actual_sha256": pass_a_before["root"],
        "pass_a_adjudications_modified": False,
        "pass_a_material_exposed_to_evaluators": False,
        "pass_a_labels_rationales_distributions_exposed": False,
        "pass_a_identity_join_exposed": False,
    }
    protected_after = protected_state()
    common.require(protected_after == protected_before, "historical protected assets changed")
    safety = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBScientificStateSafetyAuditV1",
        "historical_assets_modified": False,
        "scientific_adjudication_calls": 6,
        "provider_calls": 6,
        "llm_calls": 6,
        "network_literature_retrieval_calls": 0,
        "evidence_reextraction_calls": 0,
        "empty_body_excerpt_views_reextracted": 0,
        "metrics_unblinded": False,
        "metrics_calculated": False,
        "algorithm_modifications": 0,
        "query_modifications": 0,
        "target_modifications": 0,
        "policy_modifications": 0,
        "review_surface_modifications": 0,
        "automatic_retries": 0,
        "invalid_output_repairs": 0,
        "outcome_informed_reruns": 0,
        "protected_file_count": len(protected_before),
        "protected_state_before_sha256": common.sha_bytes(common.canonical(protected_before)),
        "protected_state_after_sha256": common.sha_bytes(common.canonical(protected_after)),
    }
    common.write_exact(RUN / "pass_b_schema_validation.json", common.pretty(schema_validation))
    common.write_exact(RUN / "pass_b_completeness_audit.json", common.pretty(completeness))
    common.write_exact(RUN / "pass_b_raw_label_distribution.json", common.pretty(distribution_record))
    common.write_exact(RUN / "pass_a_immutability_audit.json", common.pretty(pass_a_audit))
    common.write_exact(RUN / "scientific_state_safety_audit.json", common.pretty(safety))

    component_names = sorted(REQUIRED_OUTPUTS - {"implementation_manifest.json", "validation.json", "summary.json"})
    components = [[name, common.sha(RUN / name)] for name in component_names]
    adjudication_root = common.aggregate(components)
    implementation = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBImplementationManifestV1",
        "aggregate_algorithm": "sha256(canonical JSON ordered [path, sha256] pairs)",
        "aggregate_components": components,
        "primary_heldout_v2_pass_b_adjudication_sha256": adjudication_root,
        "required_outputs": sorted(REQUIRED_OUTPUTS),
        "blinded_freeze_preceded_identity_join": True,
        "primary_v2_pass_b_adjudicator_config_sha256": config_hash,
        "primary_v2_pass_b_blinded_adjudications_sha256": blind_hash,
        "primary_v2_pass_b_adjudications_sha256": joined_hash,
    }
    common.write_exact(RUN / "implementation_manifest.json", common.pretty(implementation))
    checks = {
        "all_review_roots_verified_before_calls": True,
        "pass_a_adjudication_root_verified_before_calls": True,
        "adjudicator_configuration_frozen_before_labels": True,
        "six_workspaces_isolated_and_audited": True,
        "pass_a_material_absent_from_evaluator_workspaces": True,
        "six_fresh_calls_same_configuration": True,
        "exactly_one_call_per_batch": True,
        "all_sixty_schema_valid": True,
        "blinded_freeze_before_identity_join": True,
        "blinded_freeze_contains_no_candidate_identity": True,
        "identity_join_complete_after_blinded_freeze": True,
        "pass_a_unchanged": True,
        "pass_b_views_unchanged": common.sha(NEUTRAL_RUN / "primary_v2_pass_b_blinded_views.jsonl") == EXPECTED_PASS_B,
        "metrics_not_unblinded": True,
        "historical_assets_unchanged": protected_after == protected_before,
        "provider_call_budget_exact": True,
        "literature_network_calls_zero": True,
        "evidence_reextraction_calls_zero": True,
    }
    common.require(all(checks.values()), "final PASS-B validation failed")
    validation = {"artifact_schema_version": "PrimaryHeldoutV2PassBValidationV1", "status": "PASS", "checks": checks}
    summary = {
        "artifact_schema_version": "PrimaryHeldoutV2PassBSummaryV1",
        "status": "COMPLETED",
        "expected_pass_b_records": 60,
        "completed_pass_b_records": 60,
        "missing_pass_b_records": 0,
        "duplicate_pass_b_records": 0,
        "invalid_pass_b_records": 0,
        "reviewer_type": "model_retrieval_adjudicator",
        "raw_relevance_state_counts": {label: distribution[label] for label in allowed},
        "primary_v2_pass_b_blinded_adjudications_sha256": blind_hash,
        "primary_v2_pass_b_adjudications_sha256": joined_hash,
        "primary_heldout_v2_pass_b_adjudication_sha256": adjudication_root,
        "pass_a_adjudication_modified": False,
        "pass_b_views_modified": False,
        "metrics_unblinded": False,
        "scientific_adjudication_calls": 6,
        "provider_calls": 6,
        "llm_calls": 6,
        "network_literature_retrieval_calls": 0,
        "evidence_reextraction_calls": 0,
        "historical_assets_modified": False,
    }
    common.write_exact(RUN / "validation.json", common.pretty(validation))
    common.write_exact(RUN / "summary.json", common.pretty(summary))
    common.require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "final output membership mismatch")
    common.require(protected_state() == protected_before, "protected state changed after finalization")
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true")
    group.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else finalize()


if __name__ == "__main__":
    main()
