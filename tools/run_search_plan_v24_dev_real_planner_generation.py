#!/usr/bin/env python3
"""Run exactly eight authorized isolated v2.4-dev planner calls and freeze results."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    PROMPT_VERSION,
    canonical_target_hash,
    planner_cache_key,
    planner_config_hash,
    validate_plan,
)
from code_engine.search.query_compiler_v24_dev import (
    DEFAULT_DEVELOPMENT_BUDGETS,
    compile_validated_plan,
)
from code_engine.search.retrieval_intent_v1 import DIMENSION_ORDER
from code_engine.search.search_term_validator_v1 import USABLE_CLASSES, validate_and_classify_plan_terms
from tools import freeze_search_plan_v24_dev_planner_compiler_implementation_offline as implementation


RUN = ROOT / "runs/20260917_search_plan_v24_dev_real_planner_generation_freeze"
ARCHITECTURE_RUN = implementation.ARCHITECTURE_RUN
IMPLEMENTATION_RUN = implementation.RUN
TARGETS_PATH = implementation.TARGETS_PATH
V23_QUERY_RUN = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_query_freeze_offline"
V23_QUERIES = V23_QUERY_RUN / "primary_heldout_v2_frozen_queries.jsonl"
SCHEMA_SOURCE = ARCHITECTURE_RUN / "proposition_aware_search_plan_v1_schema.json"
INSTRUCTION_SOURCE = IMPLEMENTATION_RUN / "query_planner_prompt_v1.md"

WORKSPACE_ROOT = Path("/tmp/v24_dev_real_planner_workspaces")
STAGING_ROOT = Path("/tmp/v24_dev_real_planner_staging")
PROMPT_ROOT = STAGING_ROOT / "prompts"
RESPONSE_ROOT = STAGING_ROOT / "responses"
EVENT_ROOT = STAGING_ROOT / "events"
EXECUTION_ROOT = STAGING_ROOT / "execution_records"
PROTECTED_SNAPSHOT = STAGING_ROOT / "protected_state_before.json"

EXPECTED_ARCHITECTURE = "ec1ca7facd2f0df67abae27f922a62c4bd859c6011adda30f0cec51f6baf84ea"
EXPECTED_AUTOPSY = "4eddec80c4025e8d247cb28f89ed53c9c4b138e47b8e5e4bfe4e7cbe60b52d27"
EXPECTED_IMPLEMENTATION = "970e11cbac017af2ecde0803e6c47768fcba947211bcb1b37ea00fb5331ef478"
CASES = tuple(f"heldout_v2_{value}" for value in range(101, 109))

REQUIRED_OUTPUTS = {
    "upstream_root_verification.json", "planner_call_manifest.json",
    "planner_workspace_isolation_audit.json", "v24_dev_raw_planner_outputs.jsonl",
    "v24_dev_raw_planner_outputs_sha256", "planner_schema_validation.json",
    "validated_search_terms.jsonl", "search_term_classification_summary.json",
    "retrieval_intent_summary.json", "retrieval_plan_coverage_analysis.json",
    "relation_coverage_analysis.json", "biological_unit_coverage_analysis.json",
    "search_only_expansion_audit.json", "v24_dev_compiled_queries.jsonl",
    "v24_dev_compiled_queries_sha256", "query_provenance_trace.json",
    "v23_v24_structural_coverage_comparison.json", "scientific_state_safety_audit.json",
    "implementation_manifest.json", "validation.json", "summary.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pretty(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(canonical(row) + b"\n" for row in rows)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_bytes())


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_exact(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), f"non-physical existing output: {path}")
        require(path.read_bytes() == body, f"existing output differs: {path}")
        return
    with path.open("xb") as stream:
        stream.write(body)


def write_owned(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.exists() or (path.is_file() and not path.is_symlink()), f"non-physical owned output: {path}")
    path.write_bytes(body)


def aggregate(pairs: list[list[str]]) -> str:
    return digest(canonical(pairs))


def verify_component_root(run: Path, root_field: str, expected_root: str) -> tuple[str, int]:
    validation = load_json(run / "validation.json")
    components = []
    for name, expected in validation["aggregate_components"]:
        actual = sha(run / name)
        require(actual == expected, f"upstream component changed: {run.name}/{name}")
        components.append([name, actual])
    actual_root = aggregate(components)
    require(actual_root == validation[root_field] == expected_root, f"upstream root mismatch: {root_field}")
    return actual_root, len(components)


def verify_upstreams() -> dict[str, Any]:
    lower = implementation.verify_roots()
    require(lower["search_plan_v24_proposition_aware_architecture_sha256"] == EXPECTED_ARCHITECTURE,
            "architecture root mismatch")
    require(lower["search_plan_v24_primary_failure_autopsy_sha256"] == EXPECTED_AUTOPSY,
            "autopsy root mismatch")
    implementation_root, implementation_components = verify_component_root(
        IMPLEMENTATION_RUN,
        "search_plan_v24_dev_planner_compiler_implementation_sha256",
        EXPECTED_IMPLEMENTATION,
    )
    source_audit = load_json(IMPLEMENTATION_RUN / "case_specific_rule_audit.json")
    for record in source_audit["audited_files"]:
        require(sha(ROOT / record["path"]) == record["sha256"], f"implementation source changed: {record['path']}")
    return {
        "artifact_schema_version": "V24DevRealPlannerUpstreamRootVerificationV1",
        "status": "PASS",
        "search_plan_v24_proposition_aware_architecture_sha256": EXPECTED_ARCHITECTURE,
        "search_plan_v24_primary_failure_autopsy_sha256": EXPECTED_AUTOPSY,
        "search_plan_v24_dev_planner_compiler_implementation_sha256": implementation_root,
        "implementation_component_count": implementation_components,
        "implementation_source_hashes_verified": True,
        "verified_before_provider_calls": True,
    }


def protected_state() -> dict[str, str]:
    state = implementation.protected_state()
    for base in (IMPLEMENTATION_RUN, ARCHITECTURE_RUN, V23_QUERY_RUN):
        for path in base.rglob("*"):
            if path.is_file():
                state[str(path.resolve().relative_to(ROOT))] = sha(path)
    for path in implementation.IMPLEMENTATION_FILES:
        state[str(path.resolve().relative_to(ROOT))] = sha(path)
    state[str(INSTRUCTION_SOURCE.resolve().relative_to(ROOT))] = sha(INSTRUCTION_SOURCE)
    state[str(SCHEMA_SOURCE.resolve().relative_to(ROOT))] = sha(SCHEMA_SOURCE)
    state[str(TARGETS_PATH.resolve().relative_to(ROOT))] = sha(TARGETS_PATH)
    return dict(sorted(state.items()))


def planner_config() -> dict[str, Any]:
    local = tomllib.loads(Path("/home/vincent/.codex/config.toml").read_text(encoding="utf-8"))
    require(local.get("model") == "gpt-5.6-sol", "configured model mismatch")
    require(local.get("model_reasoning_effort") == "high", "configured reasoning mismatch")
    require(local.get("service_tier") == "default", "configured service tier mismatch")
    config = DEFAULT_DEVELOPMENT_CONFIG.to_dict()
    require(config["model"] == "gpt-5.6-sol", "frozen development model mismatch")
    require(config["reasoning_effort"] == "high", "frozen development reasoning mismatch")
    require(config["service_tier"] == "default", "frozen development tier mismatch")
    require(config["temperature"] is None and config["temperature_exposed"] is False,
            "temperature boundary mismatch")
    require(config["maximum_attempts"] == 1, "attempt boundary mismatch")
    return {
        **config,
        "provider": "OpenAI",
        "authorized_provider_calls": 8,
        "authorized_llm_calls": 8,
        "calls_per_target": 1,
        "fresh_isolated_context_per_target": True,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "outcome_informed_reruns": 0,
    }


def targets_by_case() -> dict[str, dict[str, Any]]:
    rows = load_jsonl(TARGETS_PATH)
    result = {row["case_id"]: row for row in rows}
    require(tuple(sorted(result)) == CASES, "development target membership mismatch")
    return result


def request_identity(case_id: str, target: dict[str, Any]) -> dict[str, str]:
    request_reference = f"v24_dev_real_planner_generation:{case_id}"
    config_hash = planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG)
    return {
        "request_reference": request_reference,
        "request_sha256": digest(request_reference.encode("utf-8")),
        "target_id": target["scientific_proposition_target_id"],
        "target_sha256": canonical_target_hash(target),
        "planner_config_sha256": config_hash,
        "planner_prompt_template_version": PROMPT_VERSION,
        "planner_cache_key_sha256": planner_cache_key(
            target,
            DEFAULT_DEVELOPMENT_CONFIG,
            prompt_version=PROMPT_VERSION,
            schema_version=PLAN_SCHEMA_VERSION,
        ),
    }


def provider_prompt(instruction: bytes, schema: bytes, target: bytes, identity: dict[str, str]) -> bytes:
    controls = (
        "You are a fresh isolated PROPOSITION_AWARE_QUERY_PLANNER context for exactly one development target.\n"
        "Do not call tools. Do not access files, network, memory, prior conversations, or outside evidence.\n"
        "Use only the frozen instruction, frozen schema, and canonical target below.\n"
        "Return exactly one JSON object and no Markdown or commentary. Do not emit a final PubMed query string.\n"
        "Copy the canonical target payload byte-semantically without adding or deleting fields.\n"
        "Use the following deterministic serialization identities exactly; they are mechanical hashes of the allowed inputs, not scientific evidence:\n"
        + json.dumps(identity, sort_keys=True, ensure_ascii=False)
        + "\nEnsure every blueprint has all eleven coverage rows in the exact order shown by the frozen schema/instruction.\n\n"
    ).encode("utf-8")
    return b"".join([
        controls,
        b"--- FROZEN PLANNER INSTRUCTION ---\n", instruction,
        b"\n--- FROZEN PROPOSITION-AWARE SEARCH PLAN SCHEMA ---\n", schema,
        b"\n--- CANONICAL SCIENTIFIC PROPOSITION TARGET ---\n", target,
    ])


def prepare() -> None:
    roots = verify_upstreams()
    protected = protected_state()
    config = planner_config()
    targets = targets_by_case()
    require(not RUN.exists() or not any(RUN.iterdir()), "real planner run already contains files")
    RUN.mkdir(parents=True, exist_ok=True)
    for base in (WORKSPACE_ROOT, STAGING_ROOT, PROMPT_ROOT, RESPONSE_ROOT, EVENT_ROOT, EXECUTION_ROOT):
        base.mkdir(parents=True, exist_ok=True)
    write_exact(PROTECTED_SNAPSHOT, pretty(protected))
    write_exact(RUN / "upstream_root_verification.json", pretty(roots))
    instruction = INSTRUCTION_SOURCE.read_bytes()
    schema = SCHEMA_SOURCE.read_bytes()
    workspaces = []
    calls = []
    for index, case_id in enumerate(CASES, 1):
        workspace = WORKSPACE_ROOT / case_id
        workspace.mkdir(parents=True, exist_ok=True)
        target_body = pretty(targets[case_id])
        expected = {"canonical_target.json", "planner_instruction.md", "proposition_aware_search_plan_v1_schema.json"}
        require(not ({path.name for path in workspace.iterdir()} - expected), f"forbidden existing workspace file: {case_id}")
        copies = {
            "canonical_target.json": target_body,
            "planner_instruction.md": instruction,
            "proposition_aware_search_plan_v1_schema.json": schema,
        }
        for name, body in copies.items():
            write_exact(workspace / name, body)
        files = sorted(workspace.iterdir())
        require({path.name for path in files} == expected, f"workspace membership mismatch: {case_id}")
        require(all(path.is_file() and not path.is_symlink() for path in files), "workspace must use physical files")
        identity = request_identity(case_id, targets[case_id])
        prompt = provider_prompt(instruction, schema, target_body, identity)
        prompt_path = PROMPT_ROOT / f"{case_id}.txt"
        write_exact(prompt_path, prompt)
        response_path = RESPONSE_ROOT / f"{case_id}.json"
        event_path = EVENT_ROOT / f"{case_id}.jsonl"
        execution_path = EXECUTION_ROOT / f"{case_id}.json"
        workspaces.append({
            "case_id": case_id,
            "workspace_path": str(workspace),
            "file_membership": sorted(expected),
            "files": [{"path": path.name, "sha256": sha(path), "bytes": path.stat().st_size} for path in files],
            "physical_files_only": True,
            "symlinks_present": False,
            "historical_results_present": False,
            "PASS_A_present": False,
            "PASS_B_present": False,
            "PMIDs_present": False,
            "metrics_present": False,
            "candidate_material_present": False,
            "prompt_path_outside_workspace": str(prompt_path),
            "prompt_sha256": digest(prompt),
        })
        calls.append({
            "call_index": index,
            "case_id": case_id,
            "provider": "OpenAI",
            "model": "gpt-5.6-sol",
            "reasoning_effort": "high",
            "service_tier": "default",
            "temperature_exposed": False,
            "temperature_override": None,
            "maximum_attempts": 1,
            "automatic_retry": False,
            "manual_repair": False,
            "fresh_isolated_context": True,
            "workspace_path": str(workspace),
            "prompt_path": str(prompt_path),
            "prompt_sha256": digest(prompt),
            "response_path": str(response_path),
            "event_path": str(event_path),
            "execution_record_path": str(execution_path),
            **identity,
            "schema_sha256": sha(SCHEMA_SOURCE),
            "status": "PREPARED_NOT_CALLED",
        })
    audit = {
        "artifact_schema_version": "V24DevPlannerWorkspaceIsolationAuditV1",
        "status": "PASS",
        "workspace_count": 8,
        "files_per_workspace": 3,
        "all_physical_and_isolated": True,
        "allowed_input_categories_only": True,
        "workspaces": workspaces,
    }
    manifest = {
        "artifact_schema_version": "V24DevPlannerCallManifestV1",
        "status": "PREPARED_FOR_EXACTLY_EIGHT_CALLS",
        "configuration": config,
        "planner_config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
        "frozen_prompt_sha256": sha(INSTRUCTION_SOURCE),
        "frozen_schema_sha256": sha(SCHEMA_SOURCE),
        "expected_calls": 8,
        "calls": calls,
    }
    write_exact(RUN / "planner_workspace_isolation_audit.json", pretty(audit))
    write_exact(RUN / "planner_call_manifest.json", pretty(manifest))
    require(protected_state() == protected, "protected state changed during preparation")
    print(json.dumps({"status": "READY_FOR_EXACTLY_EIGHT_CALLS", "cases": list(CASES)}, indent=2))


DISABLED_FEATURES = (
    "apps", "plugins", "remote_plugin", "recommended_plugins", "skill_search", "memories",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use",
    "image_generation", "standalone_web_search", "shell_tool", "unified_exec", "unified_exec_tty",
)


def execute_one(case_id: str) -> None:
    require(case_id in CASES, "unauthorized development case")
    verify_upstreams()
    require(load_json(PROTECTED_SNAPSHOT) == protected_state(), "protected state changed before provider call")
    manifest = load_json(RUN / "planner_call_manifest.json")
    call = next(row for row in manifest["calls"] if row["case_id"] == case_id)
    execution_path = Path(call["execution_record_path"])
    require(not execution_path.exists(), f"provider call already attempted for {case_id}; retry prohibited")
    require(not Path(call["response_path"]).exists(), f"response already exists for {case_id}; retry prohibited")
    workspace = Path(call["workspace_path"])
    require({path.name for path in workspace.iterdir()} == {
        "canonical_target.json", "planner_instruction.md", "proposition_aware_search_plan_v1_schema.json"
    }, "workspace membership changed")
    command = [
        "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
        "--model", "gpt-5.6-sol",
        "--config", 'model_reasoning_effort="high"',
        "--config", 'service_tier="default"',
        "--sandbox", "read-only", "--cd", str(workspace), "--skip-git-repo-check",
        "--output-schema", str(workspace / "proposition_aware_search_plan_v1_schema.json"),
        "--output-last-message", call["response_path"], "--json",
    ]
    for feature in DISABLED_FEATURES:
        command.extend(["--disable", feature])
    command.append("-")
    completed = subprocess.run(
        command,
        input=Path(call["prompt_path"]).read_bytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=900,
    )
    write_exact(Path(call["event_path"]), completed.stdout)
    stderr_path = EVENT_ROOT / f"{case_id}.stderr.txt"
    write_exact(stderr_path, completed.stderr)
    response_path = Path(call["response_path"])
    record = {
        "artifact_schema_version": "V24DevPlannerCallExecutionRecordV1",
        "case_id": case_id,
        "attempt_count": 1,
        "provider_calls": 1,
        "llm_calls": 1,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "return_code": completed.returncode,
        "response_present": response_path.is_file(),
        "response_sha256": sha(response_path) if response_path.is_file() else None,
        "event_stream_sha256": sha(Path(call["event_path"])),
        "stderr_sha256": sha(stderr_path),
        "accepted_for_raw_freeze": completed.returncode == 0 and response_path.is_file(),
    }
    write_exact(execution_path, pretty(record))
    require(record["accepted_for_raw_freeze"], f"provider call failed closed for {case_id}: rc={completed.returncode}")
    print(json.dumps(record, indent=2))


def _legacy_coverage(target: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, int]:
    counts = {dimension: 0 for dimension in DIMENSION_ORDER}
    contexts = target.get("context_qualifier_dimensions") or {}
    lookup: dict[str, str] = {}
    for key, dimension in (
        ("biological_unit", "biological_unit"), ("therapy", "therapy"),
        ("disease_context", "disease"), ("genotype_context", "genotype"),
        ("treatment_context", "nested_treatment"),
    ):
        for value in contexts.get(key, []):
            lookup[str(value).casefold()] = dimension
    if target.get("therapy"):
        lookup[str(target["therapy"]).casefold()] = "therapy"
    field_map = {
        "subject": "subject", "object": "object_measurement_target",
        "relation_family": "relation", "measurement_property_endpoint": "endpoint_property",
        "required_evidence_mode": "evidence_mode",
    }
    for query in queries:
        represented = set()
        for annotation in query.get("term_annotations", []):
            field = annotation.get("target_field")
            if field in field_map:
                represented.add(field_map[field])
            elif field == "context_qualifiers":
                term = str(annotation.get("term") or "").casefold()
                if term in lookup:
                    represented.add(lookup[term])
        for dimension in represented:
            counts[dimension] += 1
    return counts


def finalize() -> None:
    roots = verify_upstreams()
    require(load_json(RUN / "upstream_root_verification.json") == roots, "prepared roots changed")
    protected_before = load_json(PROTECTED_SNAPSHOT)
    require(protected_state() == protected_before, "protected state changed before raw freeze")
    manifest = load_json(RUN / "planner_call_manifest.json")
    targets = targets_by_case()
    executions = {}
    for case_id in CASES:
        record = load_json(EXECUTION_ROOT / f"{case_id}.json")
        require(record["attempt_count"] == record["provider_calls"] == record["llm_calls"] == 1,
                f"provider accounting mismatch: {case_id}")
        require(record["accepted_for_raw_freeze"], f"failed provider call: {case_id}")
        executions[case_id] = record
    require(sum(row["provider_calls"] for row in executions.values()) == 8, "provider call total mismatch")

    raw_rows = []
    parse_errors = []
    for call in manifest["calls"]:
        case_id = call["case_id"]
        raw_text = Path(call["response_path"]).read_text(encoding="utf-8")
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            parsed = None
            parse_errors.append({"case_id": case_id, "error": str(exc)})
        raw_rows.append({
            "artifact_schema_version": "V24DevRawPlannerOutputV1",
            "case_id": case_id,
            "development_case_status": "SEEN_DEVELOPMENT_ONLY",
            "provider_request_metadata": {
                key: call[key] for key in (
                    "call_index", "provider", "model", "reasoning_effort", "service_tier",
                    "temperature_exposed", "temperature_override", "maximum_attempts",
                    "automatic_retry", "manual_repair", "fresh_isolated_context", "prompt_sha256",
                    "target_sha256", "planner_config_sha256", "schema_sha256",
                )
            },
            "raw_provider_response": raw_text,
            "structured_parsed_response": parsed,
            "raw_response_sha256": digest(raw_text.encode("utf-8")),
            "provider_event_stream_sha256": executions[case_id]["event_stream_sha256"],
        })
    raw_body = jsonl(raw_rows)
    raw_root = digest(raw_body)
    write_exact(RUN / "v24_dev_raw_planner_outputs.jsonl", raw_body)
    write_exact(RUN / "v24_dev_raw_planner_outputs_sha256", (raw_root + "\n").encode("ascii"))
    require(sha(RUN / "v24_dev_raw_planner_outputs.jsonl") == raw_root, "raw planner freeze verification failed")

    schema_results = []
    valid_plans = {}
    for call, row in zip(manifest["calls"], raw_rows):
        errors = []
        plan = row["structured_parsed_response"]
        if plan is None:
            errors.append("raw provider response is not JSON")
        else:
            try:
                validate_plan(plan, expected_target=targets[row["case_id"]])
            except Exception as exc:  # frozen output: report, never repair
                errors.append(f"{type(exc).__name__}: {exc}")
            identity = request_identity(row["case_id"], targets[row["case_id"]])
            expected_fields = {
                "target_id": identity["target_id"],
                "planner_config_sha256": identity["planner_config_sha256"],
                "planner_prompt_template_version": identity["planner_prompt_template_version"],
                "planner_cache_key_sha256": identity["planner_cache_key_sha256"],
            }
            for field, expected in expected_fields.items():
                if plan.get(field) != expected:
                    errors.append(f"{field} mismatch")
            if plan.get("request_provenance") != {
                "request_sha256": identity["request_sha256"],
                "preserved_request_reference": identity["request_reference"],
            }:
                errors.append("request_provenance mismatch")
        schema_results.append({
            "case_id": row["case_id"], "schema_valid": not errors,
            "errors": errors, "repair_attempted": False, "rerun_attempted": False,
        })
        if not errors:
            valid_plans[row["case_id"]] = plan
    schema_validation = {
        "artifact_schema_version": "V24DevPlannerSchemaValidationV1",
        "raw_planner_outputs_sha256": raw_root,
        "expected_outputs": 8,
        "parsed_outputs": sum(row["structured_parsed_response"] is not None for row in raw_rows),
        "schema_valid_outputs": len(valid_plans),
        "schema_failures": sum(not row["schema_valid"] for row in schema_results),
        "fail_closed": True,
        "results": schema_results,
    }
    write_exact(RUN / "planner_schema_validation.json", pretty(schema_validation))
    require(not parse_errors and len(valid_plans) == 8,
            f"planner schema validation failed closed: {schema_results}")

    validated = {}
    term_rows = []
    class_counts = Counter()
    search_only = []
    for case_id in CASES:
        raw_plan = valid_plans[case_id]
        result = validate_and_classify_plan_terms(raw_plan, authorities={"records": []})
        validated[case_id] = result
        audit_by_id = {row["item_id"]: row for row in result["validation_receipt"]["classification_audit"]}
        for intent in result["validated_plan"]["retrieval_intents"]:
            for concept in intent["search_concepts"]:
                for term in concept["proposed_terms"]:
                    audit = audit_by_id[term["term_id"]]
                    row = {
                        "case_id": case_id,
                        "target_id": result["validated_plan"]["target_id"],
                        "intent_id": intent["intent_id"],
                        "intent_type": intent["intent_type"],
                        "concept_id": concept["concept_id"],
                        "concept_type": concept["concept_type"],
                        "term_id": term["term_id"],
                        "term": term["term"],
                        "proposal_source": term["proposal_source"],
                        "assigned_class": term["proposal_class"],
                        "authority_reference": term["authority_reference"],
                        "planner_rationale": intent["scientific_rationale"],
                        "validation_provenance": audit["reason"],
                        "canonical_identity_changed": False,
                    }
                    term_rows.append(row)
                    class_counts[term["proposal_class"]] += 1
                    if term["proposal_class"] == "SEARCH_ONLY_EXPANSION":
                        search_only.append(row)
    term_body = jsonl(term_rows)
    write_exact(RUN / "validated_search_terms.jsonl", term_body)
    class_summary = {
        "artifact_schema_version": "V24DevSearchTermClassificationSummaryV1",
        "term_count": len(term_rows),
        "classification_distribution": {
            name: class_counts[name] for name in (
                "AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED"
            )
        },
        "llm_authority_assertions_overriding_deterministic_authority": 0,
        "search_only_identity_promotions": 0,
    }
    write_exact(RUN / "search_term_classification_summary.json", pretty(class_summary))
    search_audit = {
        "artifact_schema_version": "V24DevSearchOnlyExpansionAuditV1",
        "search_only_expansion_count": len(search_only),
        "search_only_identity_promotions": 0,
        "canonical_identity_unchanged_all_cases": True,
        "terms": search_only,
    }
    write_exact(RUN / "search_only_expansion_audit.json", pretty(search_audit))

    intent_cases = {}
    coverage_rows = []
    for case_id in CASES:
        plan = validated[case_id]["validated_plan"]
        intent_cases[case_id] = [{
            "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
            "applicability": intent["applicability"],
            "applicability_rationale": intent["applicability_rationale"],
            "semantic_applicability_valid": True,
        } for intent in plan["retrieval_intents"]]
        for intent in plan["retrieval_intents"]:
            for blueprint in intent["candidate_query_blueprints"]:
                coverage_rows.append({
                    "case_id": case_id, "target_id": plan["target_id"],
                    "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
                    "blueprint_id": blueprint["blueprint_id"],
                    "relation_representation_state": blueprint["relation_representation_state"],
                    "dimension_coverage": blueprint["dimension_coverage"],
                })
    intent_summary = {
        "artifact_schema_version": "V24DevRetrievalIntentSummaryV1",
        "cases": intent_cases,
        "intent_type_distribution": dict(sorted(Counter(
            row["intent_type"] for rows in intent_cases.values() for row in rows if row["applicability"] == "APPLICABLE"
        ).items())),
        "semantic_applicability_errors": 0,
        "plans_edited_from_intent_audit": 0,
    }
    write_exact(RUN / "retrieval_intent_summary.json", pretty(intent_summary))
    coverage_analysis = {
        "artifact_schema_version": "V24DevRetrievalPlanCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_COVERAGE_NOT_RETRIEVAL_PERFORMANCE",
        "blueprint_count": len(coverage_rows),
        "dimensions": list(DIMENSION_ORDER),
        "coverage_records": coverage_rows,
        "state_distribution": {
            dimension: dict(sorted(Counter(
                next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == dimension)
                for row in coverage_rows
            ).items())) for dimension in DIMENSION_ORDER
        },
    }
    write_exact(RUN / "retrieval_plan_coverage_analysis.json", pretty(coverage_analysis))

    applicable_relation = [row for row in coverage_rows if next(
        item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "relation"
    ) != "NOT_APPLICABLE"]
    relation_represented = sum(row["relation_representation_state"] == "REPRESENTED" for row in applicable_relation)
    relation_under = sum(row["relation_representation_state"] == "RELATION_UNDERREPRESENTED" for row in applicable_relation)
    relation_invalid = sum(
        next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "relation")
        in {"OMITTED", "UNDERREPRESENTED"}
        and row["relation_representation_state"] != "RELATION_UNDERREPRESENTED"
        for row in applicable_relation
    )
    relation_analysis = {
        "artifact_schema_version": "V24DevRelationCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_COVERAGE_NOT_RETRIEVAL_PERFORMANCE",
        "relation_applicable_blueprints": len(applicable_relation),
        "relation_represented_blueprints": relation_represented,
        "relation_underrepresented_blueprints": relation_under,
        "relation_omitted_invalid_blueprints": relation_invalid,
        "relation_coverage_fraction": {
            "n": relation_represented, "N": len(applicable_relation),
            "fraction": relation_represented / len(applicable_relation) if applicable_relation else None,
        },
    }
    write_exact(RUN / "relation_coverage_analysis.json", pretty(relation_analysis))

    biological_cases = {}
    for case_id in CASES:
        rows = [row for row in coverage_rows if row["case_id"] == case_id]
        states = [next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == "biological_unit") for row in rows]
        if "REPRESENTED" in states:
            state = "REPRESENTED"
        elif "UNDERREPRESENTED" in states:
            state = "UNDERREPRESENTED"
        elif "OMITTED" in states:
            state = "OMITTED"
        else:
            state = "NOT_APPLICABLE"
        terms = sorted({
            term["term"] for intent in validated[case_id]["validated_plan"]["retrieval_intents"]
            for concept in intent["search_concepts"] if concept["concept_type"] == "biological_unit"
            for term in concept["proposed_terms"] if term["proposal_class"] in USABLE_CLASSES
        })
        biological_cases[case_id] = {"aggregate_state": state, "blueprint_states": states, "surviving_terms": terms}
    biological_analysis = {
        "artifact_schema_version": "V24DevBiologicalUnitCoverageAnalysisV1",
        "analysis_role": "DEVELOPMENT_STRUCTURAL_DIAGNOSTIC",
        "cases": biological_cases,
    }
    write_exact(RUN / "biological_unit_coverage_analysis.json", pretty(biological_analysis))

    compiled_rows = []
    compilation_counts = {}
    for case_id in CASES:
        result = validated[case_id]
        compilation = compile_validated_plan(
            result["validated_plan"], result["validation_receipt"], budgets=DEFAULT_DEVELOPMENT_BUDGETS
        )
        compilation_counts[case_id] = compilation["compiled_query_count"]
        for query in compilation["compiled_queries"]:
            compiled_rows.append({"case_id": case_id, "development_only": True, **query})
    compiled_body = jsonl(compiled_rows)
    compiled_root = digest(compiled_body)
    write_exact(RUN / "v24_dev_compiled_queries.jsonl", compiled_body)
    write_exact(RUN / "v24_dev_compiled_queries_sha256", (compiled_root + "\n").encode("ascii"))
    require(sha(RUN / "v24_dev_compiled_queries.jsonl") == compiled_root, "compiled query freeze mismatch")
    provenance_trace = {
        "artifact_schema_version": "V24DevQueryProvenanceTraceV1",
        "query_count": len(compiled_rows),
        "all_terms_provenanced": all(
            {"term_id", "term", "proposal_source", "proposal_class", "authority_reference"} <= set(term)
            for query in compiled_rows for group in query["ordered_term_groups"] for term in group["terms"]
        ),
        "all_queries_hash_bound": all(query["query_id"] == "v24q:" + query["query_sha256"] for query in compiled_rows),
        "traces": [{
            "case_id": query["case_id"], "target_id": query["target_id"], "query_id": query["query_id"],
            "source_routes": query["source_routes"], "ordered_term_groups": query["ordered_term_groups"],
            "provenance": query["provenance"], "query_sha256": query["query_sha256"],
        } for query in compiled_rows],
    }
    write_exact(RUN / "query_provenance_trace.json", pretty(provenance_trace))

    v23_queries = load_jsonl(V23_QUERIES)
    comparison_cases = {}
    for case_id in CASES:
        old = [row for row in v23_queries if row["case_id"] == case_id]
        old_counts = _legacy_coverage(targets[case_id], old)
        new = [row for row in coverage_rows if row["case_id"] == case_id]
        new_counts = {
            dimension: sum(
                next(item["coverage_state"] for item in row["dimension_coverage"] if item["dimension"] == dimension) == "REPRESENTED"
                for row in new
            ) for dimension in DIMENSION_ORDER
        }
        comparison_cases[case_id] = {
            "v23_query_count": len(old), "v24_blueprint_count": len(new),
            "v23_represented_query_counts": old_counts,
            "v24_represented_blueprint_counts": new_counts,
            "structural_count_difference_v24_minus_v23": {
                dimension: new_counts[dimension] - old_counts[dimension] for dimension in DIMENSION_ORDER
            },
        }
    comparison = {
        "artifact_schema_version": "V23V24StructuralCoverageComparisonV1",
        "comparison_role": "DEVELOPMENT_STRUCTURAL_ONLY_NO_RETRIEVAL_OUTCOMES",
        "performance_claims_made": False,
        "dimensions_emphasized": [
            "relation", "biological_unit", "endpoint_property", "therapy", "disease", "genotype",
            "nested_treatment", "direction", "evidence_mode",
        ],
        "cases": comparison_cases,
    }
    write_exact(RUN / "v23_v24_structural_coverage_comparison.json", pretty(comparison))

    finalized_calls = []
    for call in manifest["calls"]:
        execution = executions[call["case_id"]]
        finalized_calls.append({**call, **execution, "status": "COMPLETED_ACCEPTED_RAW_FREEZE"})
    final_manifest = {
        **manifest,
        "status": "COMPLETED_EXACTLY_EIGHT_CALLS",
        "actual_provider_calls": 8,
        "actual_llm_calls": 8,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "calls": finalized_calls,
    }
    write_owned(RUN / "planner_call_manifest.json", pretty(final_manifest))

    protected_after = protected_state()
    require(protected_after == protected_before, "protected v2.3/v2.4 implementation assets changed")
    safety = {
        "artifact_schema_version": "V24DevRealPlannerScientificStateSafetyAuditV1",
        "development_cases_only": True,
        "development_case_count": 8,
        "fresh_validation_cases_selected": False,
        "provider_calls": 8, "llm_calls": 8,
        "automatic_retries": 0, "manual_repairs": 0, "outcome_informed_reruns": 0,
        "retrieval_calls": 0, "literature_network_calls": 0, "candidate_records_seen": 0,
        "hit_counts_inspected": False, "oa_availability_inspected": False,
        "known_direct_paper_recovery_tested": False,
        "v23_assets_modified": False,
        "planner_implementation_modified_during_generation": False,
        "protected_state_before_sha256": digest(canonical(protected_before)),
        "protected_state_after_sha256": digest(canonical(protected_after)),
    }
    write_exact(RUN / "scientific_state_safety_audit.json", pretty(safety))

    component_names = sorted(REQUIRED_OUTPUTS - {"implementation_manifest.json", "validation.json", "summary.json"})
    components = [[name, sha(RUN / name)] for name in component_names]
    run_root = aggregate(components)
    implementation_manifest = {
        "artifact_schema_version": "V24DevRealPlannerImplementationManifestV1",
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_compiled_queries_sha256": compiled_root,
    }
    validation = {
        "artifact_schema_version": "V24DevRealPlannerGenerationValidationV1",
        "status": "PASS",
        "checks": {
            "three_upstream_roots_verified": roots["status"] == "PASS",
            "exact_development_case_membership": set(valid_plans) == set(CASES),
            "exactly_eight_provider_calls": safety["provider_calls"] == 8,
            "exactly_eight_llm_calls": safety["llm_calls"] == 8,
            "raw_outputs_frozen_before_validation": True,
            "all_plans_schema_valid": schema_validation["schema_failures"] == 0,
            "search_only_identity_promotions_zero": class_summary["search_only_identity_promotions"] == 0,
            "relation_omitted_invalid_zero": relation_invalid == 0,
            "query_provenance_complete": provenance_trace["all_terms_provenanced"],
            "compiled_queries_frozen_not_executed": True,
            "retrieval_boundary_preserved": safety["retrieval_calls"] == safety["candidate_records_seen"] == 0,
            "v23_assets_unchanged": protected_after == protected_before,
        },
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
    }
    require(all(validation["checks"].values()), "final validation failed")
    summary = {
        "artifact_schema_version": "V24DevRealPlannerGenerationSummaryV1",
        "status": "COMPLETED",
        "development_case_count": 8,
        "planner_outputs_expected": 8,
        "planner_outputs_frozen": len(raw_rows),
        "planner_schema_failures": schema_validation["schema_failures"],
        "provider_calls": 8, "llm_calls": 8,
        "automatic_retries": 0, "manual_repairs": 0,
        "compiled_query_count": len(compiled_rows),
        "compiled_query_counts_by_case": compilation_counts,
        "relation_applicable_blueprints": len(applicable_relation),
        "relation_represented_blueprints": relation_represented,
        "relation_underrepresented_blueprints": relation_under,
        "relation_omitted_invalid_blueprints": relation_invalid,
        "search_only_expansion_count": len(search_only),
        "search_only_identity_promotions": 0,
        "retrieval_calls": 0, "literature_network_calls": 0, "candidate_records_seen": 0,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_compiled_queries_sha256": compiled_root,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
        "v23_assets_modified": False,
    }
    write_exact(RUN / "implementation_manifest.json", pretty(implementation_manifest))
    write_exact(RUN / "validation.json", pretty(validation))
    write_exact(RUN / "summary.json", pretty(summary))
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "required run membership mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


def freeze_failure() -> None:
    """Freeze the first-call provider rejection without retrying or continuing."""
    roots = verify_upstreams()
    require(load_json(RUN / "upstream_root_verification.json") == roots, "prepared roots changed")
    protected_before = load_json(PROTECTED_SNAPSHOT)
    require(protected_state() == protected_before, "protected state changed before failure freeze")
    manifest = load_json(RUN / "planner_call_manifest.json")
    attempted = sorted(EXECUTION_ROOT.glob("*.json"))
    require([path.stem for path in attempted] == ["heldout_v2_101"],
            "failure freeze requires exactly the single recorded first attempt")
    execution = load_json(attempted[0])
    require(execution["attempt_count"] == 1 and not execution["accepted_for_raw_freeze"],
            "expected one failed-closed attempt")
    event_path = EVENT_ROOT / "heldout_v2_101.jsonl"
    event_lines = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines() if line]
    error_events = [row for row in event_lines if row.get("type") == "error"]
    require(len(error_events) == 1, "expected one provider error event")
    provider_error = json.loads(error_events[0]["message"])
    require(provider_error.get("error", {}).get("code") == "invalid_json_schema",
            "unexpected provider failure type")

    raw_rows = [{
        "artifact_schema_version": "V24DevRawPlannerFailureV1",
        "case_id": "heldout_v2_101",
        "development_case_status": "SEEN_DEVELOPMENT_ONLY",
        "provider_request_attempted": True,
        "model_inference_completed": False,
        "raw_provider_response": None,
        "structured_parsed_response": None,
        "provider_error": provider_error,
        "provider_event_stream_sha256": sha(event_path),
        "response_present": False,
    }]
    raw_body = jsonl(raw_rows)
    raw_root = digest(raw_body)
    write_exact(RUN / "v24_dev_raw_planner_outputs.jsonl", raw_body)
    write_exact(RUN / "v24_dev_raw_planner_outputs_sha256", (raw_root + "\n").encode("ascii"))
    schema_results = [{
        "case_id": "heldout_v2_101",
        "schema_valid": False,
        "failure_stage": "PROVIDER_RESPONSE_FORMAT_SCHEMA_VALIDATION_BEFORE_MODEL_INFERENCE",
        "error_code": "invalid_json_schema",
        "error": provider_error["error"]["message"],
        "repair_attempted": False,
        "rerun_attempted": False,
    }] + [{
        "case_id": case_id,
        "schema_valid": None,
        "failure_stage": "NOT_CALLED_AFTER_FAIL_CLOSED",
        "errors": [],
        "repair_attempted": False,
        "rerun_attempted": False,
    } for case_id in CASES[1:]]
    schema_validation = {
        "artifact_schema_version": "V24DevPlannerSchemaValidationV1",
        "status": "FAILED_CLOSED",
        "raw_planner_outputs_sha256": raw_root,
        "expected_outputs": 8,
        "planner_outputs_present": 0,
        "schema_valid_outputs": 0,
        "schema_failures": 1,
        "not_called_after_fail_closed": 7,
        "fail_closed": True,
        "results": schema_results,
    }
    write_exact(RUN / "planner_schema_validation.json", pretty(schema_validation))

    finalized_calls = []
    for call in manifest["calls"]:
        if call["case_id"] == "heldout_v2_101":
            finalized_calls.append({
                **call,
                **execution,
                "model_inference_calls": 0,
                "status": "FAILED_CLOSED_PROVIDER_SCHEMA_REJECTION",
            })
        else:
            finalized_calls.append({**call, "status": "NOT_CALLED_AFTER_FAIL_CLOSED"})
    final_manifest = {
        **manifest,
        "status": "FAILED_CLOSED_AFTER_FIRST_PROVIDER_REQUEST",
        "actual_provider_request_attempts": 1,
        "actual_llm_call_attempts": 1,
        "actual_model_inference_calls": 0,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "calls": finalized_calls,
    }
    write_owned(RUN / "planner_call_manifest.json", pretty(final_manifest))

    protected_after = protected_state()
    require(protected_after == protected_before, "protected assets changed during failed run")
    safety = {
        "artifact_schema_version": "V24DevRealPlannerScientificStateSafetyAuditV1",
        "status": "FAILED_CLOSED",
        "development_cases_only": True,
        "development_case_count": 8,
        "provider_request_attempts": 1,
        "llm_call_attempts": 1,
        "model_inference_calls": 0,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "outcome_informed_reruns": 0,
        "remaining_provider_calls_after_fail_closed": 0,
        "retrieval_calls": 0,
        "literature_network_calls": 0,
        "candidate_records_seen": 0,
        "hit_counts_inspected": False,
        "oa_availability_inspected": False,
        "known_direct_paper_recovery_tested": False,
        "v23_assets_modified": False,
        "planner_implementation_modified_during_generation": False,
        "frozen_schema_modified": False,
        "protected_state_before_sha256": digest(canonical(protected_before)),
        "protected_state_after_sha256": digest(canonical(protected_after)),
    }
    write_owned(RUN / "scientific_state_safety_audit.json", pretty(safety))

    missing_due_failure = sorted(REQUIRED_OUTPUTS - {
        "upstream_root_verification.json", "planner_call_manifest.json",
        "planner_workspace_isolation_audit.json", "v24_dev_raw_planner_outputs.jsonl",
        "v24_dev_raw_planner_outputs_sha256", "planner_schema_validation.json",
        "scientific_state_safety_audit.json", "implementation_manifest.json",
        "validation.json", "summary.json",
    })
    component_names = sorted({
        "upstream_root_verification.json", "planner_call_manifest.json",
        "planner_workspace_isolation_audit.json", "v24_dev_raw_planner_outputs.jsonl",
        "v24_dev_raw_planner_outputs_sha256", "planner_schema_validation.json",
        "scientific_state_safety_audit.json",
    })
    components = [[name, sha(RUN / name)] for name in component_names]
    run_root = aggregate(components)
    implementation_manifest = {
        "artifact_schema_version": "V24DevRealPlannerImplementationManifestV1",
        "status": "FAILED_CLOSED",
        "aggregate_components": components,
        "missing_outputs_due_fail_closed": missing_due_failure,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_compiled_queries_sha256": None,
    }
    validation = {
        "artifact_schema_version": "V24DevRealPlannerGenerationValidationV1",
        "status": "FAILED_CLOSED",
        "failure_code": "PROVIDER_REJECTED_FROZEN_SCHEMA_BEFORE_MODEL_INFERENCE",
        "checks": {
            "three_upstream_roots_verified": True,
            "exactly_eight_provider_calls": False,
            "exactly_eight_llm_calls": False,
            "all_plans_schema_valid": False,
            "no_retry_or_repair": True,
            "retrieval_boundary_preserved": True,
            "v23_assets_unchanged": True,
        },
        "aggregate_components": components,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
    }
    summary = {
        "artifact_schema_version": "V24DevRealPlannerGenerationSummaryV1",
        "status": "FAILED_CLOSED",
        "failure_code": "PROVIDER_REJECTED_FROZEN_SCHEMA_BEFORE_MODEL_INFERENCE",
        "development_case_count": 8,
        "planner_outputs_expected": 8,
        "planner_outputs_frozen": 0,
        "planner_schema_failures": 1,
        "provider_request_attempts": 1,
        "llm_calls": 1,
        "model_inference_calls": 0,
        "automatic_retries": 0,
        "manual_repairs": 0,
        "compiled_query_count": 0,
        "relation_applicable_blueprints": 0,
        "relation_represented_blueprints": 0,
        "relation_underrepresented_blueprints": 0,
        "relation_omitted_invalid_blueprints": 0,
        "search_only_expansion_count": 0,
        "search_only_identity_promotions": 0,
        "retrieval_calls": 0,
        "literature_network_calls": 0,
        "candidate_records_seen": 0,
        "v24_dev_raw_planner_outputs_sha256": raw_root,
        "v24_dev_compiled_queries_sha256": None,
        "search_plan_v24_dev_real_planner_generation_sha256": run_root,
        "v23_assets_modified": False,
    }
    write_owned(RUN / "implementation_manifest.json", pretty(implementation_manifest))
    write_owned(RUN / "validation.json", pretty(validation))
    write_owned(RUN / "summary.json", pretty(summary))
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("prepare")
    execute = subparsers.add_parser("execute-one")
    execute.add_argument("case_id", choices=CASES)
    subparsers.add_parser("finalize")
    subparsers.add_parser("freeze-failure")
    args = parser.parse_args()
    if args.command == "prepare":
        prepare()
    elif args.command == "execute-one":
        execute_one(args.case_id)
    elif args.command == "finalize":
        finalize()
    else:
        freeze_failure()


if __name__ == "__main__":
    main()
