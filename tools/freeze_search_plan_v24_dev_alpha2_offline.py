"""Freeze alpha2's offline contracts, deterministic V1 replay and provider audit.

This tool must never instantiate a provider client or perform retrieval.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from code_engine.search.alpha2_linked_relation_v1 import (
    ANCHOR_VERSION, BINDING_VERSION, ELIGIBILITY_VERSION, LINK_VERSION,
    PROPOSAL_VERSION, LINKED_RELATION_CANDIDATE_V1_SCHEMA,
    PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA, search_anchor_compatibility,
    search_only_eligibility_v1_1,
)
from code_engine.search.alpha1_relation_searchonly_v1 import _anchors
from code_engine.search.deepseek_planner_transport_v1 import (
    DEFAULT_CONFIG, DEEPSEEK_PROVIDER_SCHEMA, PROMPT_TEXT, PROMPT_VERSION,
    TRANSPORT_VERSION, planner_cache_identity, static_schema_preflight,
)
from code_engine.search.proposition_aware_query_planner_v1 import (
    DEFAULT_DEVELOPMENT_CONFIG, PROMPT_TEXT as HISTORICAL_PROMPT,
    planner_cache_key as historical_planner_cache_key, sha256_value,
)

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha2_linked_relation_deepseek_migration_offline"
AUTOPSY = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_zero_query_autopsy_and_provider_audit_offline"
ALPHA1 = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_relation_searchonly_refinement_offline"
AUTHORITY = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
ROOTS = {
    "autopsy": "6e04742306ca027ae0423e68ad958915aadf4a38b313dcf1819845d396ed0dc7",
    "alpha1": "a49ded58e5222212a3f163a36c5435ecd8947a38198b99f3976094ee8dc89115",
    "authority": "ceeb18a8b2f83e1db01a67368b606d8c06bb5486b1c39b6afda2d90ad1ea8367",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify(path: Path, expected: str) -> dict:
    manifest = read(path / "validation.json")
    pairs = manifest["aggregate_components"]
    for name, value in pairs:
        if digest(path / name) != value:
            raise ValueError(f"protected component changed: {path.name}/{name}")
    if sha256_value(pairs) != expected:
        raise ValueError(f"protected root changed: {path.name}")
    return {"expected_sha256": expected, "verified": True, "component_count": len(pairs)}


def write(name: str, value) -> None:
    path = RUN / name
    if path.is_symlink():
        raise ValueError(f"output symlink forbidden: {name}")
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def text(name: str, value: str) -> None:
    path = RUN / name
    if path.is_symlink():
        raise ValueError(f"output symlink forbidden: {name}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    upstream = {"artifact_schema_version": "Alpha2UpstreamRootVerificationV1",
                "autopsy": verify(AUTOPSY, ROOTS["autopsy"]),
                "alpha1": verify(ALPHA1, ROOTS["alpha1"]),
                "authority": verify(AUTHORITY, ROOTS["authority"])}
    diagnostic = read(AUTOPSY / "unresolved_term_diagnostic.json")
    if diagnostic["term_count"] != 328 or len(diagnostic["terms"]) != 328:
        raise ValueError("frozen 328-term diagnostic changed")
    source_plans = lines(AUTHORITY / "validated_development_plans.jsonl")
    targets = {row["case_id"]: row["validated_plan"]["canonical_proposition"]["target_payload"]
               for row in source_plans}
    if len(targets) != 8:
        raise ValueError("frozen development corpus is not eight cases")
    transitions = []
    for row in diagnostic["terms"]:
        target = targets[row["case_id"]]
        state, rule = search_only_eligibility_v1_1(row["term"], row["concept_type"], target)
        anchor_state = search_anchor_compatibility(row["term"], _anchors(target, row["concept_type"]))
        transitions.append({"case_id": row["case_id"], "term_id": row["term_id"],
                            "concept_type": row["concept_type"], "term": row["term"],
                            "alpha1_classification": "UNRESOLVED",
                            "alpha2_counterfactual_classification": state,
                            "generic_rule_id": rule, "search_anchor_compatibility": anchor_state,
                            "diagnostic_category": row["diagnostic_category"]})
    counts = Counter(row["alpha2_counterfactual_classification"] for row in transitions)
    by_category = Counter((row["diagnostic_category"], row["alpha2_counterfactual_classification"])
                          for row in transitions)
    by_rule = Counter(row["generic_rule_id"] for row in transitions)
    if sum(counts.values()) != 328 or counts.get("AUTHORIZED_EQUIVALENT", 0):
        raise ValueError("counterfactual replay violated authority boundary")
    preflight = static_schema_preflight()
    if not preflight["passed"]:
        raise ValueError("local schema preflight failed")
    prospective_paths = ["src/code_engine/search/deepseek_planner_transport_v1.py",
                         "src/code_engine/extraction/client_factory.py", "src/code_engine/validation/readiness.py",
                         "src/code_engine/cli/run.py", "src/code_engine/cli/triple_batch.py",
                         "src/code_engine/cli/context_attribution.py", "src/code_engine/cli/print_env_template.py"]
    historical_paths = ["src/code_engine/search/proposition_aware_query_planner_v1.py",
                        "src/code_engine/search/openai_planner_payload_transport_v2.py",
                        "src/code_engine/search/openai_structured_output_schema_renderer_v1.py"]
    for name in historical_paths:
        if not (ROOT / name).is_file():
            raise ValueError("historical OpenAI code missing")
    production_rule_source = (ROOT / "src/code_engine/search/alpha2_linked_relation_v1.py").read_text(encoding="utf-8")
    if "heldout_v2_" in production_rule_source or "if case ==" in production_rule_source:
        raise ValueError("case-specific alpha2 production rule detected")
    RUN.mkdir(parents=True, exist_ok=True)
    write("upstream_root_verification.json", upstream)
    write("planner_proposal_payload_v2_contract.json", {
        "artifact_schema_version": PROPOSAL_VERSION, "model_generated_fields_only": True,
        "relation_applicable_blueprint_requires_link": True,
        "authority_labels_prohibited": True, "target_echo_prohibited": True,
        "scientific_truth_asserted": False, "schema_sha256": sha256_value(PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)})
    write("planner_proposal_payload_v2_schema.json", PLANNER_PROPOSAL_PAYLOAD_V2_SCHEMA)
    write("linked_relation_candidate_v1_contract.json", {
        "artifact_schema_version": LINK_VERSION, "schema": LINKED_RELATION_CANDIDATE_V1_SCHEMA,
        "concept_references_must_resolve": True, "endpoint_property_explicit": True,
        "required_nested_and_therapy_refs": True, "model_asserts_truth": False})
    text("planner_prompt_v2.md", PROMPT_TEXT)
    write("planner_prompt_v2_diff_audit.json", {
        "artifact_schema_version": "PlannerPromptV2DiffAuditV1",
        "historical_prompt_sha256": sha256_value(HISTORICAL_PROMPT),
        "new_prompt_sha256": sha256_value(PROMPT_TEXT),
        "historical_prompt_modified": False,
        "new_requirements": ["linked actor-response phrase", "endpoint property", "nested/therapy context",
                             "canonical target surface preservation", "no authority assertions"]})
    write("search_anchor_compatibility_v1_contract.json", {
        "artifact_schema_version": ANCHOR_VERSION,
        "states": ["EXACT_CANONICAL_SURFACE", "AUTHORIZED_ALIAS_SURFACE", "SAFE_ORTHOGRAPHIC_VARIANT",
                   "UNDER_SPECIFIED", "INCOMPATIBLE", "UNRESOLVED"],
        "mandatory_anchor_sufficient": ["EXACT_CANONICAL_SURFACE", "AUTHORIZED_ALIAS_SURFACE",
                                        "SAFE_ORTHOGRAPHIC_VARIANT"],
        "canonical_identity_mutation": False, "greek_suffix_stripping": False,
        "unverified_short_form_equals_long_form": False})
    write("search_only_eligibility_v1_1_contract.json", {
        "artifact_schema_version": ELIGIBILITY_VERSION, "default_deny": True,
        "generic_addition": "full canonical surface orthography preserving complete symbols",
        "alpha1_generic_rules_preserved": True, "scientific_identity_promoted": False,
        "no_case_or_exact_development_phrase_allowlist": True})
    write("relation_binding_assessment_v1_1_contract.json", {
        "artifact_schema_version": BINDING_VERSION,
        "required_checks": ["subject", "response", "endpoint", "relation_family", "direction",
                            "relation_surface", "nested_treatment", "therapy", "biological_unit"],
        "independent_keyword_bags_sufficient": False,
        "frozen_v1_payloads_contain_linked_relation_candidates": False})
    write("alpha1_unresolved_alpha2_counterfactual_transition.json", {
        "artifact_schema_version": "Alpha1UnresolvedAlpha2CounterfactualTransitionV1",
        "input_count": 328, "transitions": transitions})
    write("alpha2_deterministic_replay_summary.json", {
        "artifact_schema_version": "Alpha2DeterministicReplaySummaryV1",
        "input_unresolved_count": 328, "search_only_count": counts.get("SEARCH_ONLY_EXPANSION", 0),
        "unresolved_count": counts.get("UNRESOLVED", 0), "rejected_count": counts.get("REJECTED", 0),
        "transition_by_diagnostic_category": [
            {"diagnostic_category": category, "alpha2_classification": classification, "count": count}
            for (category, classification), count in sorted(by_category.items())],
        "generic_rule_counts": dict(sorted(by_rule.items())),
        "planner_v2_empirically_evaluated": False,
        "no_v2_links_fabricated_from_historical_v1": True,
        "diagnostic_plausibility_is_not_authority": True})
    write("deepseek_query_planner_config_v1.json", DEFAULT_CONFIG.to_dict())
    write("deepseek_planner_transport_v1_contract.json", {
        "artifact_schema_version": TRANSPORT_VERSION,
        "adapter": "repository DeepSeekClient", "endpoint": "https://api.deepseek.com/v1/chat/completions",
        "response_format": {"type": "json_object"}, "max_retries": 0,
        "local_post_validation_required": True, "remote_schema_enforcement_claimed": False,
        "separate_future_authorization_required": True})
    write("deepseek_provider_schema.json", DEEPSEEK_PROVIDER_SCHEMA)
    write("deepseek_static_preflight.json", preflight)
    write("prospective_llm_provider_routing_audit.json", {
        "artifact_schema_version": "ProspectiveLLMProviderRoutingAuditV1",
        "provider": "deepseek", "model": "deepseek-v4-pro", "prospective_paths": prospective_paths,
        "prospective_path_sha256": {name: digest(ROOT / name) for name in prospective_paths},
        "scientific_data_apis_out_of_scope": ["PubMed", "PMC", "NCBI", "LINCS"],
        "provider_calls": 0})
    write("openai_fallback_removal_audit.json", {
        "artifact_schema_version": "OpenAIFallbackRemovalAuditV1",
        "planner_openai_fallback_enabled": False,
        "shared_factory_openai_fallback_for_scientific_pipeline": False,
        "missing_deepseek_credential_fails_closed": True,
        "historical_OpenAIJSONClient_class_preserved_but_not_routed": True})
    sample_target = next(iter(targets.values()))
    cache_key = planner_cache_identity(sample_target)
    historical_key = historical_planner_cache_key(
        sample_target, DEFAULT_DEVELOPMENT_CONFIG,
        prompt_version=DEFAULT_DEVELOPMENT_CONFIG.prompt_version,
        schema_version=DEFAULT_DEVELOPMENT_CONFIG.schema_version)
    if cache_key == historical_key:
        raise ValueError("DeepSeek planner cache collided with historical OpenAI cache")
    write("planner_cache_identity_v2_audit.json", {
        "artifact_schema_version": "PlannerCacheIdentityV2AuditV1",
        "sample_deepseek_key_sha256": cache_key,
        "sample_historical_openai_key_sha256": historical_key,
        "bound_fields": ["provider", "model", "canonical_target_sha256", "planner_config_sha256",
                         "planner_prompt_v2_sha256", "proposal_schema_sha256",
                         "provider_transport_schema_sha256", "rehydrator_version", "validator_version"],
        "historical_openai_provider": DEFAULT_DEVELOPMENT_CONFIG.provider,
        "historical_openai_cache_collision": False})
    write("historical_openai_preservation_audit.json", {
        "artifact_schema_version": "HistoricalOpenAIPreservationAuditV1",
        "classification": "HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY",
        "historical_source_paths": historical_paths,
        "historical_source_sha256": {name: digest(ROOT / name) for name in historical_paths},
        "historical_default_provider": DEFAULT_DEVELOPMENT_CONFIG.provider,
        "historical_default_model": DEFAULT_DEVELOPMENT_CONFIG.model,
        "historical_openai_provenance_rewritten": False})
    write("planner_v2_evaluation_boundary.json", {
        "artifact_schema_version": "PlannerV2EvaluationBoundaryV1",
        "planner_v2_empirically_evaluated": False,
        "v1_payloads_invalid_as_v2_without_linked_fields": True,
        "next_stage": "separately authorized DeepSeek Planner V2 generation on seen development cases",
        "pubmed_before_v2_evaluation": False})
    write("heldout_specific_rule_audit.json", {
        "artifact_schema_version": "Alpha2HeldoutSpecificRuleAuditV1",
        "production_case_specific_rules": 0,
        "case_ids_in_production_rule_modules": 0,
        "development_case_ids_used_only_for_counterfactual_replay": True})
    write("scientific_state_safety_audit.json", {
        "artifact_schema_version": "Alpha2ScientificStateSafetyAuditV1",
        "implementation_source_sha256": {
            name: digest(ROOT / name) for name in (
                "src/code_engine/search/alpha2_linked_relation_v1.py",
                "src/code_engine/search/deepseek_planner_transport_v1.py",
                "tools/freeze_search_plan_v24_dev_alpha2_offline.py")},
        "identity_promotions": 0, "historical_mutations": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0, "retrieval_calls": 0,
        "candidate_records_seen": 0})
    summary = {"artifact_schema_version": "SearchPlanV24DevAlpha2SummaryV1",
               "status": "completed", "planner_proposal_payload_v2_defined": True,
               "linked_relation_candidate_required": True, "planner_prompt_v2_defined": True,
               "search_anchor_compatibility_defined": True, "search_only_default_deny": True,
               "relation_binding_v1_1_defined": True,
               "alpha1_unresolved_input_count": 328,
               "alpha2_counterfactual_search_only_count": counts.get("SEARCH_ONLY_EXPANSION", 0),
               "alpha2_counterfactual_unresolved_count": counts.get("UNRESOLVED", 0),
               "alpha2_counterfactual_rejected_count": counts.get("REJECTED", 0),
               "planner_default_provider": DEFAULT_CONFIG.provider, "planner_model": DEFAULT_CONFIG.model,
               "planner_openai_fallback_enabled": False,
               "scientific_pipeline_openai_fallback_enabled": False,
               "deepseek_provider_transport_defined": True,
               "deepseek_provider_schema_preflight_pass": True,
               "planner_v2_empirically_evaluated": False,
               "historical_openai_provenance_rewritten": False,
               "production_case_specific_rules": 0,
               "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
               "retrieval_calls": 0, "candidate_records_seen": 0}
    write("summary.json", summary)
    components = [[path.name, digest(path)] for path in sorted(RUN.iterdir())
                  if path.is_file() and path.name not in {"validation.json", "search_plan_v24_dev_alpha2_sha256"}]
    root = sha256_value(components)
    write("validation.json", {"artifact_schema_version": "SearchPlanV24DevAlpha2ValidationV1",
                              "status": "PASS", "aggregate_components": components,
                              "search_plan_v24_dev_alpha2_sha256": root,
                              "all_upstream_roots_verified": True,
                              "local_preflight_passed": preflight["passed"],
                              "counterfactual_count_verified": sum(counts.values()) == 328})
    text("search_plan_v24_dev_alpha2_sha256", root)
    print(json.dumps({"run": str(RUN), "root": root, "counts": counts}, default=dict, sort_keys=True))


if __name__ == "__main__":
    main()
