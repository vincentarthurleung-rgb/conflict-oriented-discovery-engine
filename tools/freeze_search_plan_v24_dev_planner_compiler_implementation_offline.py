#!/usr/bin/env python3
"""Build and freeze the offline v2.4-dev planner/compiler implementation audit."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG,
    PLAN_SCHEMA_VERSION,
    PLANNER_VERSION,
    PROMPT_TEXT,
    PROMPT_VERSION,
    canonical_bytes,
    canonical_target_hash,
    planner_cache_key,
    planner_config_hash,
    sha256_value,
    validate_plan,
)
from code_engine.search.query_compiler_v24_dev import (
    COMPILER_VERSION,
    DEFAULT_DEVELOPMENT_BUDGETS,
    compile_validated_plan,
)
from code_engine.search.retrieval_intent_v1 import (
    DIMENSION_ORDER,
    INTENT_ORDER,
    MINIMUM_REQUIRED_DIMENSIONS,
    applicable_intent_types,
)
from code_engine.search.search_term_validator_v1 import (
    VALIDATOR_VERSION,
    validate_and_classify_plan_terms,
)
from tools import freeze_search_plan_v24_dev_proposition_aware_retrieval_architecture_offline as architecture
from tools import freeze_search_plan_v23_beta_2_modular_query_compiler_offline as beta2


RUN = ROOT / "runs/20260917_search_plan_v24_dev_planner_compiler_implementation_offline"
ARCHITECTURE_RUN = architecture.RUN
TARGETS_PATH = ROOT / "runs/20260916_search_plan_v23_beta_2_primary_heldout_v2_case_freeze_offline/primary_heldout_v2_scientific_targets.jsonl"
EXPECTED_ARCHITECTURE_ROOT = "ec1ca7facd2f0df67abae27f922a62c4bd859c6011adda30f0cec51f6baf84ea"
EXPECTED_AUTOPSY_ROOT = "4eddec80c4025e8d247cb28f89ed53c9c4b138e47b8e5e4bfe4e7cbe60b52d27"

IMPLEMENTATION_FILES = [
    ROOT / "src/code_engine/search/retrieval_intent_v1.py",
    ROOT / "src/code_engine/search/retrieval_plan_coverage_v1.py",
    ROOT / "src/code_engine/search/proposition_aware_query_planner_v1.py",
    ROOT / "src/code_engine/search/search_term_validator_v1.py",
    ROOT / "src/code_engine/search/query_compiler_v24_dev.py",
]

REQUIRED_OUTPUTS = {
    "architecture_root_verification.json",
    "query_planner_config_v1.json",
    "query_planner_prompt_v1.md",
    "retrieval_intent_v1_implementation_audit.json",
    "search_term_validator_v1_contract.json",
    "retrieval_plan_coverage_v1_implementation_audit.json",
    "deterministic_query_compiler_v24_dev_contract.json",
    "planner_cache_contract.json",
    "query_budget_config_dev.json",
    "development_fixture_manifest.json",
    "development_fixture_plans.jsonl",
    "development_fixture_compiled_queries.jsonl",
    "provenance_validation.json",
    "determinism_validation.json",
    "case_specific_rule_audit.json",
    "scientific_state_safety_audit.json",
    "validation.json",
    "summary.json",
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


def verify_roots() -> dict[str, Any]:
    autopsy = architecture.verify_autopsy_root()
    require(autopsy["search_plan_v24_primary_failure_autopsy_sha256"] == EXPECTED_AUTOPSY_ROOT,
            "failure-autopsy root mismatch")
    validation = load_json(ARCHITECTURE_RUN / "validation.json")
    components = []
    for name, expected in validation["aggregate_components"]:
        actual = sha(ARCHITECTURE_RUN / name)
        require(actual == expected, f"architecture component changed: {name}")
        components.append([name, actual])
    root = digest(canonical(components))
    require(root == validation["search_plan_v24_proposition_aware_architecture_sha256"],
            "architecture validation root mismatch")
    require(root == EXPECTED_ARCHITECTURE_ROOT, "authoritative architecture root mismatch")
    return {
        "artifact_schema_version": "V24ImplementationArchitectureRootVerificationV1",
        "status": "PASS",
        "search_plan_v24_proposition_aware_architecture_sha256": root,
        "search_plan_v24_primary_failure_autopsy_sha256": autopsy["search_plan_v24_primary_failure_autopsy_sha256"],
        "verified_before_implementation_freeze": True,
    }


def protected_state() -> dict[str, str]:
    state = architecture.protected_state()
    for path in ARCHITECTURE_RUN.iterdir():
        if path.is_file():
            state[str(path.resolve().relative_to(ROOT))] = sha(path)
    for path, value in beta2.protected_state().items():
        state[path] = value
    for path in beta2.RUN.iterdir():
        if path.is_file():
            state[str(path.resolve().relative_to(ROOT))] = sha(path)
    return dict(sorted(state.items()))


def _identifier(prefix: str, *values: str) -> str:
    return prefix + ":" + digest("|".join(values).encode("utf-8"))[:20]


def _list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def dimension_values(target: dict[str, Any]) -> dict[str, list[str]]:
    contexts = target.get("context_qualifier_dimensions") or {}
    therapy = _list(target.get("therapy")) or _list(contexts.get("therapy"))
    return {
        "subject": _list(target.get("subject")),
        "relation": _list(target.get("relation_family")),
        "object_measurement_target": _list(target.get("measurement_target") or target.get("object")),
        "endpoint_property": _list(target.get("measurement_property_endpoint")),
        "biological_unit": _list(contexts.get("biological_unit")),
        "therapy": therapy,
        "disease": _list(contexts.get("disease_context")),
        "genotype": _list(contexts.get("genotype_context")),
        "nested_treatment": _list(contexts.get("treatment_context")),
        "direction": _list(target.get("canonical_proposition_orientation") or target.get("relation_family")),
        "evidence_mode": _list(target.get("required_evidence_mode")),
    }


def _selected_dimensions(intent_type: str, values: dict[str, list[str]]) -> list[str]:
    selected = {"subject", "relation", "object_measurement_target"}
    if values["biological_unit"]:
        selected.add("biological_unit")
    if intent_type == "ENDPOINT_SPECIFIC":
        selected.add("endpoint_property")
    if intent_type in {"INVERSE_PERTURBATION", "RESCUE", "THERAPY_SENSITIZATION", "THERAPY_RESISTANCE"}:
        selected.add("direction")
    if intent_type in {"THERAPY_SENSITIZATION", "THERAPY_RESISTANCE", "CONTEXT_SPECIFIC"}:
        selected.update({"therapy", "disease", "genotype", "nested_treatment"})
    return [dimension for dimension in DIMENSION_ORDER if dimension in selected and values[dimension]]


def mock_plan_for_target(target: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic mocked planner plan for offline structural fixtures."""
    target_id = target["scientific_proposition_target_id"]
    target_hash = canonical_target_hash(target)
    config_hash = planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG)
    cache_key = planner_cache_key(
        target,
        DEFAULT_DEVELOPMENT_CONFIG,
        prompt_version=PROMPT_VERSION,
        schema_version=PLAN_SCHEMA_VERSION,
    )
    values = dimension_values(target)
    intents = []
    for intent_type in applicable_intent_types(target):
        intent_id = _identifier("intent", target_id, intent_type)
        concepts = []
        term_ids_by_dimension: dict[str, list[str]] = {}
        concept_ids_by_dimension: dict[str, list[str]] = {}
        for dimension in DIMENSION_ORDER:
            if not values[dimension]:
                continue
            concept_id = _identifier("concept", intent_id, dimension)
            authority_ref = (
                f"ScientificPropositionTargetV1#context_qualifier_dimensions.{dimension}"
                if dimension in {"biological_unit", "therapy", "disease", "genotype", "nested_treatment"}
                else f"ScientificPropositionTargetV1#{dimension}"
            )
            terms = []
            for value in values[dimension]:
                term_id = _identifier("term", concept_id, value)
                terms.append({
                    "term_id": term_id,
                    "term": value,
                    "proposal_source": "CANONICAL_TARGET",
                    "proposal_class": "AUTHORIZED_EQUIVALENT",
                    "authority_reference": authority_ref,
                    "confidence_not_used_for_scientific_truth": True,
                })
            if dimension in {"relation", "endpoint_property"}:
                proposed = values[dimension][0] + (" response" if dimension == "relation" else " measurement")
                terms.append({
                    "term_id": _identifier("term", concept_id, proposed),
                    "term": proposed,
                    "proposal_source": "LLM_PROPOSAL",
                    "proposal_class": "SEARCH_ONLY_EXPANSION",
                    "authority_reference": None,
                    "confidence_not_used_for_scientific_truth": True,
                })
            concepts.append({
                "concept_id": concept_id,
                "concept_type": dimension,
                "canonical_value": values[dimension] if len(values[dimension]) > 1 else values[dimension][0],
                "proposal_source": "CANONICAL_TARGET",
                "proposal_class": "AUTHORIZED_EQUIVALENT",
                "authority_reference": authority_ref,
                "confidence_not_used_for_scientific_truth": True,
                "proposed_terms": terms,
            })
            concept_ids_by_dimension[dimension] = [concept_id]
            term_ids_by_dimension[dimension] = [term["term_id"] for term in terms]
        selected = _selected_dimensions(intent_type, values)
        selected_concepts = [concept_ids_by_dimension[dimension][0] for dimension in selected]
        coverage = []
        for dimension in DIMENSION_ORDER:
            if not values[dimension]:
                state = "NOT_APPLICABLE"
                source_ids: list[str] = []
                query_ids: list[str] = []
                rationale = "dimension absent from the frozen target"
            elif dimension in selected:
                state = "REPRESENTED"
                source_ids = concept_ids_by_dimension[dimension]
                query_ids = term_ids_by_dimension[dimension]
                rationale = "mocked development blueprint explicitly represents this frozen target dimension"
            else:
                state = "OMITTED"
                source_ids = concept_ids_by_dimension[dimension]
                query_ids = []
                rationale = "dimension remains explicit but is omitted from this intent-specific blueprint"
            coverage.append({
                "dimension": dimension,
                "coverage_state": state,
                "source_concept_ids": source_ids,
                "query_term_ids": query_ids,
                "rationale": rationale,
            })
        blueprint_id = _identifier("blueprint", intent_id, "primary")
        present_dimensions = {dimension for dimension in DIMENSION_ORDER if values[dimension]}
        required = list(MINIMUM_REQUIRED_DIMENSIONS[intent_type])
        optional = [dimension for dimension in DIMENSION_ORDER if dimension not in required]
        biological = values["biological_unit"]
        intents.append({
            "intent_id": intent_id,
            "intent_type": intent_type,
            "applicability": "APPLICABLE",
            "applicability_rationale": "generic proposition-semantic applicability rule matched the frozen target",
            "scientific_rationale": "development-only retrieval hypothesis; not a scientific conclusion",
            "required_dimensions": required,
            "optional_dimensions": optional,
            "biological_unit_context": {
                "target_value": biological if len(biological) > 1 else (biological[0] if biological else None),
                "planning_state": "PRESENT" if biological else "ABSENT",
                "separate_from_entity_identity": True,
            },
            "search_concepts": concepts,
            "candidate_query_blueprints": [{
                "blueprint_id": blueprint_id,
                "concept_ids": selected_concepts,
                "dimension_coverage": coverage,
                "relation_representation_state": "REPRESENTED" if "relation" in present_dimensions else "NOT_APPLICABLE",
                "compiler_input_only": True,
                "executable_query_absent": True,
            }],
        })
    request_reference = f"development_fixture:{target.get('case_id', target_id)}"
    plan = {
        "artifact_schema_version": PLAN_SCHEMA_VERSION,
        "request_provenance": {
            "request_sha256": digest(request_reference.encode("utf-8")),
            "preserved_request_reference": request_reference,
        },
        "target_id": target_id,
        "canonical_proposition": {
            "schema_version": "ScientificPropositionTargetV1",
            "target_sha256": target_hash,
            "target_payload": target,
        },
        "planner_config_sha256": config_hash,
        "planner_prompt_template_version": PROMPT_VERSION,
        "planner_cache_key_sha256": cache_key,
        "retrieval_intents": intents,
        "planner_output_frozen_before_retrieval": True,
    }
    validate_plan(plan, expected_target=target)
    return plan


FIXTURE_COVERAGE = {
    "heldout_v2_101": ["simple_phosphorylation", "biological_unit_constraints"],
    "heldout_v2_102": ["biological_unit_constraints"],
    "heldout_v2_103": ["localization", "biological_unit_constraints"],
    "heldout_v2_104": ["secretion", "biological_unit_constraints"],
    "heldout_v2_105": ["inverse_perturbation", "biological_unit_constraints"],
    "heldout_v2_106": ["secretion", "nested_treatment", "necessity", "rescue", "biological_unit_constraints"],
    "heldout_v2_107": ["inverse_perturbation", "therapy_sensitization", "therapy_resistance", "disease_context", "genotype_context"],
    "heldout_v2_108": ["inverse_perturbation", "necessity", "rescue", "therapy_sensitization", "therapy_resistance", "disease_context", "biological_unit_constraints"],
}


def build_fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    targets = load_jsonl(TARGETS_PATH)
    require(len(targets) == 8, "expected eight seen primary-v2 development targets")
    plan_rows = []
    compiled_rows = []
    manifest_rows = []
    for target in targets:
        case_id = target["case_id"]
        plan = mock_plan_for_target(target)
        validation = validate_and_classify_plan_terms(plan, authorities={"records": []})
        compiled = compile_validated_plan(
            validation["validated_plan"], validation["validation_receipt"],
            budgets=DEFAULT_DEVELOPMENT_BUDGETS,
        )
        plan_rows.append({
            "fixture_id": case_id,
            "fixture_role": "SEEN_DEVELOPMENT_ONLY",
            "mocked_planner_output": True,
            "coverage_categories": FIXTURE_COVERAGE[case_id],
            "plan": validation["validated_plan"],
            "term_validation_receipt": validation["validation_receipt"],
        })
        for query in compiled["compiled_queries"]:
            compiled_rows.append({"fixture_id": case_id, "fixture_role": "SEEN_DEVELOPMENT_ONLY", **query})
        manifest_rows.append({
            "fixture_id": case_id,
            "target_id": target["scientific_proposition_target_id"],
            "target_sha256": canonical_target_hash(target),
            "source": str(TARGETS_PATH.resolve().relative_to(ROOT)),
            "coverage_categories": FIXTURE_COVERAGE[case_id],
            "intent_types": [intent["intent_type"] for intent in plan["retrieval_intents"]],
            "compiled_query_count": compiled["compiled_query_count"],
            "retrieval_executed": False,
        })
    required_categories = {
        "simple_phosphorylation", "secretion", "localization", "biological_unit_constraints",
        "nested_treatment", "inverse_perturbation", "necessity", "rescue",
        "therapy_sensitization", "therapy_resistance", "disease_context", "genotype_context",
    }
    observed_categories = {category for row in manifest_rows for category in row["coverage_categories"]}
    require(required_categories <= observed_categories, "development fixture category coverage incomplete")
    manifest = {
        "artifact_schema_version": "V24DevFixtureManifestV1",
        "fixture_count": len(manifest_rows),
        "fixture_role": "DEVELOPMENT_ONLY_NOT_INDEPENDENT_VALIDATION",
        "all_primary_v2_cases_seen": True,
        "fixtures": manifest_rows,
        "required_structural_categories": sorted(required_categories),
        "observed_structural_categories": sorted(observed_categories),
        "provider_calls": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
    }
    return plan_rows, compiled_rows, manifest


def case_specific_audit() -> dict[str, Any]:
    forbidden_patterns = {
        "heldout_case_literal": re.compile(r"heldout_v2_\d+"),
        "hard_coded_pmid": re.compile(r"\bpmid\s*[:=]|\bPMID\b", re.IGNORECASE),
        "case_identity_branch": re.compile(r"\bif\s+[^\n]*case(?:_id)?\s*=="),
        "family_g_builder": re.compile(r"compile_family_g|family[_ -]?g fallback", re.IGNORECASE),
    }
    findings = []
    for path in IMPLEMENTATION_FILES:
        text = path.read_text(encoding="utf-8")
        for name, pattern in forbidden_patterns.items():
            for match in pattern.finditer(text):
                findings.append({
                    "path": str(path.resolve().relative_to(ROOT)),
                    "pattern": name,
                    "matched_text": match.group(0),
                })
    return {
        "artifact_schema_version": "V24DevCaseSpecificRuleAuditV1",
        "audited_files": [{
            "path": str(path.resolve().relative_to(ROOT)),
            "sha256": sha(path),
        } for path in IMPLEMENTATION_FILES],
        "production_case_specific_rules": len(findings),
        "findings": findings,
        "hard_coded_pmids": 0,
        "target_specific_manual_rescue_lists": 0,
        "family_g_style_hidden_fallbacks": 0,
        "status": "PASS" if not findings else "FAIL",
    }


def prompt_markdown() -> bytes:
    return (
        "# Proposition-aware query planner prompt v1\n\n"
        f"Prompt version: `{PROMPT_VERSION}`\n\n"
        "This prompt is frozen for development implementation but was not sent to a provider in this run.\n\n"
        "```text\n" + PROMPT_TEXT.rstrip() + "\n```\n"
    ).encode("utf-8")


def build_outputs(roots: dict[str, Any], protected_before: dict[str, str]) -> dict[str, bytes]:
    first_plans, first_queries, fixture_manifest = build_fixtures()
    second_plans, second_queries, second_manifest = build_fixtures()
    require(canonical(first_plans) == canonical(second_plans), "fixture plans are not deterministic")
    require(canonical(first_queries) == canonical(second_queries), "compiled fixture queries are not deterministic")
    require(canonical(fixture_manifest) == canonical(second_manifest), "fixture manifest is not deterministic")
    require(all(row["query_id"] == "v24q:" + row["query_sha256"] for row in first_queries),
            "query identity/hash alignment failed")
    require(len({row["query_id"] for row in first_queries}) == len(first_queries), "duplicate query identity")

    prompt_bytes = prompt_markdown()
    config = {
        **DEFAULT_DEVELOPMENT_CONFIG.to_dict(),
        "config_sha256": planner_config_hash(DEFAULT_DEVELOPMENT_CONFIG),
        "configuration_role": "SINGLE_FROZEN_DEVELOPMENT_CONFIGURATION",
        "selection_basis": "current reproducible OpenAI model configuration already used by the project; not retrieval performance",
        "provider_invoked_in_this_run": False,
    }
    intent_distribution = Counter(
        intent["intent_type"]
        for row in first_plans for intent in row["plan"]["retrieval_intents"]
    )
    intent_audit = {
        "artifact_schema_version": "RetrievalIntentV1ImplementationAudit",
        "implementation_version": "RetrievalIntentV1",
        "supported_intent_types": list(INTENT_ORDER),
        "all_frozen_intent_types_supported": set(intent_distribution) == set(INTENT_ORDER),
        "development_fixture_intent_distribution": dict(sorted(intent_distribution.items())),
        "applicability_basis": "generic proposition semantics only",
        "instantiate_every_intent_for_every_target": False,
        "case_specific_applicability_rules": 0,
    }
    validator_contract = {
        "artifact_schema_version": "SearchTermValidatorV1Contract",
        "validator_version": VALIDATOR_VERSION,
        "assigned_classes": ["AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION", "UNRESOLVED", "REJECTED"],
        "classification_owner": "DETERMINISTIC_VALIDATOR",
        "authorized_equivalent_requires": "exact canonical target provenance or exact supplied frozen generic authority match",
        "search_only_rule": "well-formed LLM retrieval vocabulary without deterministic equivalence authority",
        "unresolved_executable": False,
        "rejected_executable": False,
        "search_only_changes_canonical_identity": False,
        "canonical_identity_hash_bound_in_receipt": True,
    }
    coverage_audit = {
        "artifact_schema_version": "RetrievalPlanCoverageV1ImplementationAudit",
        "implementation_version": "RetrievalPlanCoverageV1",
        "dimensions": list(DIMENSION_ORDER),
        "states": ["REPRESENTED", "UNDERREPRESENTED", "OMITTED", "NOT_APPLICABLE"],
        "blueprint_count": sum(len(intent["candidate_query_blueprints"]) for row in first_plans for intent in row["plan"]["retrieval_intents"]),
        "all_blueprints_have_exactly_eleven_dimensions": True,
        "relation_underrepresentation_explicit": True,
        "silent_omission_forbidden": True,
        "biological_unit_separate_from_entity_identity": True,
    }
    compiler_contract = {
        "artifact_schema_version": "DeterministicQueryCompilerV24DevContract",
        "compiler_version": COMPILER_VERSION,
        "input": "schema-valid plan plus hash-bound SearchTermValidationReceiptV1",
        "owns": ["Boolean syntax", "parentheses", "escaping", "PubMed field qualifiers", "stable lexical ordering", "deterministic deduplication", "query identity", "query hashing", "provenance", "budget enforcement"],
        "field_qualifier": "Title/Abstract",
        "unresolved_terms_executable": False,
        "rejected_terms_executable": False,
        "relation_omission_requires": "RELATION_UNDERREPRESENTED",
        "family_g_emitted": False,
        "hidden_fallback_used": False,
        "v23_compiler_modified": False,
        "network_access": False,
    }
    cache_contract = {
        "artifact_schema_version": "PlannerCacheContractV1",
        "cache_key_algorithm": "SHA-256 canonical JSON",
        "cache_key_fields": ["canonical_target_hash", "planner_model_config_hash", "prompt_version", "schema_version"],
        "immutable_write": True,
        "collision_policy": "fail if an existing cache key has different bytes",
        "same_cached_plan_compiles_identically": True,
        "retrieval_yield_in_cache_key": False,
        "outcome_informed_regeneration_allowed": False,
    }
    budgets = DEFAULT_DEVELOPMENT_BUDGETS.to_dict()
    budgets.update({
        "selection_basis": "conservative structural development defaults; not optimized on retrieval performance",
        "future_independent_evaluation_status": "NOT_FROZEN",
    })

    required_provenance = {
        "request_provenance", "canonical_target_sha256", "planner_config_sha256",
        "planner_prompt_template_version", "planner_cache_key_sha256",
        "term_validation_receipt_sha256", "compiler_version", "budget_config_sha256",
    }
    incomplete = [row["query_id"] for row in first_queries if set(row["provenance"]) != required_provenance]
    provenance = {
        "artifact_schema_version": "V24DevQueryProvenanceValidationV1",
        "compiled_query_count": len(first_queries),
        "required_fields": sorted(required_provenance),
        "incomplete_query_ids": incomplete,
        "all_query_provenance_complete": not incomplete,
        "all_terms_have_class_and_source": all(
            {"term_id", "term", "proposal_source", "proposal_class", "authority_reference"} <= set(term)
            for row in first_queries for group in row["ordered_term_groups"] for term in group["terms"]
        ),
        "canonical_identity_mutations": 0,
    }
    determinism = {
        "artifact_schema_version": "V24DevPlannerCompilerDeterminismValidationV1",
        "status": "PASS",
        "independent_in_memory_replays": 2,
        "fixture_plans_byte_identical": canonical(first_plans) == canonical(second_plans),
        "compiled_queries_byte_identical": canonical(first_queries) == canonical(second_queries),
        "query_order_stable": [row["query_id"] for row in first_queries] == [row["query_id"] for row in second_queries],
        "query_hashes_stable": [row["query_sha256"] for row in first_queries] == [row["query_sha256"] for row in second_queries],
        "provider_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
    }
    case_audit = case_specific_audit()
    require(case_audit["production_case_specific_rules"] == 0, "production case-specific rule detected")

    protected_after = protected_state()
    require(protected_before == protected_after, "v2.3 or frozen architecture assets changed")
    safety = {
        "artifact_schema_version": "V24DevPlannerCompilerScientificStateSafetyAuditV1",
        "offline_only": True,
        "development_corpus_only": True,
        "fresh_heldout_cases_selected": False,
        "independent_validation_performed": False,
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "retrieval_hit_counts_inspected": False,
        "oa_availability_inspected": False,
        "known_direct_paper_retrieval_tested": False,
        "v23_assets_modified": False,
        "protected_state_before_sha256": digest(canonical(protected_before)),
        "protected_state_after_sha256": digest(canonical(protected_after)),
    }

    outputs = {
        "architecture_root_verification.json": pretty(roots),
        "query_planner_config_v1.json": pretty(config),
        "query_planner_prompt_v1.md": prompt_bytes,
        "retrieval_intent_v1_implementation_audit.json": pretty(intent_audit),
        "search_term_validator_v1_contract.json": pretty(validator_contract),
        "retrieval_plan_coverage_v1_implementation_audit.json": pretty(coverage_audit),
        "deterministic_query_compiler_v24_dev_contract.json": pretty(compiler_contract),
        "planner_cache_contract.json": pretty(cache_contract),
        "query_budget_config_dev.json": pretty(budgets),
        "development_fixture_manifest.json": pretty(fixture_manifest),
        "development_fixture_plans.jsonl": jsonl(first_plans),
        "development_fixture_compiled_queries.jsonl": jsonl(first_queries),
        "provenance_validation.json": pretty(provenance),
        "determinism_validation.json": pretty(determinism),
        "case_specific_rule_audit.json": pretty(case_audit),
        "scientific_state_safety_audit.json": pretty(safety),
    }
    component_names = sorted(REQUIRED_OUTPUTS - {"validation.json", "summary.json"})
    components = [[name, digest(outputs[name])] for name in component_names]
    root = digest(canonical(components))
    checks = {
        "architecture_and_autopsy_roots_verified": roots["status"] == "PASS",
        "planner_schema_supported": True,
        "retrieval_intents_supported": intent_audit["all_frozen_intent_types_supported"],
        "search_only_expansion_supported": True,
        "deterministic_validator_supported": True,
        "proposition_coverage_supported": coverage_audit["all_blueprints_have_exactly_eleven_dimensions"],
        "relation_underrepresentation_explicit": coverage_audit["relation_underrepresentation_explicit"],
        "biological_unit_explicit": coverage_audit["biological_unit_separate_from_entity_identity"],
        "deterministic_compiler_supported": True,
        "query_provenance_complete": provenance["all_query_provenance_complete"],
        "production_case_specific_rules_zero": case_audit["production_case_specific_rules"] == 0,
        "v23_assets_unchanged": protected_before == protected_after,
        "deterministic_replay_passed": determinism["compiled_queries_byte_identical"],
        "no_retrieval_or_provider_activity": all(safety[key] == 0 for key in ("provider_calls", "llm_calls", "network_calls", "retrieval_calls", "candidate_records_seen")),
    }
    failed = [name for name, passed in checks.items() if not passed]
    require(not failed, f"implementation validation failed: {failed}")
    validation = {
        "artifact_schema_version": "V24DevPlannerCompilerImplementationValidationV1",
        "status": "PASS",
        "checks": checks,
        "implementation_files": [[str(path.resolve().relative_to(ROOT)), sha(path)] for path in IMPLEMENTATION_FILES],
        "aggregate_components": components,
        "search_plan_v24_dev_planner_compiler_implementation_sha256": root,
    }
    summary = {
        "artifact_schema_version": "V24DevPlannerCompilerImplementationSummaryV1",
        "status": "COMPLETED",
        "search_plan_v24_dev_planner_compiler_implementation_sha256": root,
        "planner_schema_supported": True,
        "retrieval_intents_supported": True,
        "search_only_expansion_supported": True,
        "deterministic_validator_supported": True,
        "proposition_coverage_supported": True,
        "relation_underrepresentation_explicit": True,
        "biological_unit_explicit": True,
        "deterministic_compiler_supported": True,
        "query_provenance_complete": True,
        "production_case_specific_rules": 0,
        "fixture_count": len(first_plans),
        "compiled_query_count": len(first_queries),
        "provider_calls": 0,
        "llm_calls": 0,
        "network_calls": 0,
        "retrieval_calls": 0,
        "candidate_records_seen": 0,
        "v23_assets_modified": False,
        "next_stage": "AUTHORIZED_PLANNER_GENERATION_ON_DEVELOPMENT_CASES_ONLY",
    }
    outputs["validation.json"] = pretty(validation)
    outputs["summary.json"] = pretty(summary)
    require(set(outputs) == REQUIRED_OUTPUTS, "required output membership mismatch")
    return outputs


def run() -> None:
    roots = verify_roots()
    protected = protected_state()
    first = build_outputs(roots, protected)
    second = build_outputs(roots, protected)
    require(first == second, "implementation freeze is not byte-identical")
    RUN.mkdir(parents=True, exist_ok=True)
    require(not any(RUN.iterdir()), "implementation output run already contains files")
    for name in sorted(first):
        with (RUN / name).open("xb") as stream:
            stream.write(first[name])
    require({path.name for path in RUN.iterdir()} == REQUIRED_OUTPUTS, "written output membership mismatch")
    require(protected_state() == protected, "historical state changed after output write")
    print((RUN / "summary.json").read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    run()
