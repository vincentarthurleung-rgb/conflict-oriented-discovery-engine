"""Read-only alpha1 coverage autopsy and prospective model-provider inventory.

No provider, literature, compiler, validator, or planner entry point is called.
Only new diagnostic artifacts under RUN are written.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from code_engine.search.proposition_aware_query_planner_v1 import sha256_value

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_zero_query_autopsy_and_provider_audit_offline"
ALPHA1 = ROOT / "runs/20260920_search_plan_v24_dev_alpha1_relation_searchonly_refinement_offline"
AUTH = ROOT / "runs/20260918_search_plan_v24_dev_planner_authority_contract_split_offline"
SEMANTIC = ROOT / "runs/20260918_search_plan_v24_dev_planner_semantic_quality_audit_offline"
RAW = ROOT / "runs/20260918_search_plan_v24_dev_real_planner_generation_v3/v24_dev_raw_planner_outputs.jsonl"
ROOTS = {
    "alpha1": "a49ded58e5222212a3f163a36c5435ecd8947a38198b99f3976094ee8dc89115",
    "authority": "ceeb18a8b2f83e1db01a67368b606d8c06bb5486b1c39b6afda2d90ad1ea8367",
    "semantic": "9504e1b6fdc5005eaf67f5306322cd7374ae6528213fed7663947ad804dd1b64",
}
RAW_SHA = "9b5e7f5e7b22aff42a1e6179b62a2f0ad2ecebf09c8104bb9f3e9117546c45f1"
STAGES = (
    "PLANNER_DID_NOT_PROPOSE", "PLANNER_PROPOSED_BUT_VALIDATOR_WITHHELD",
    "VALIDATED_BUT_EVENT_FRAME_FAILED", "EVENT_FRAME_VALID_BUT_COMPILER_BLOCKED",
)
CAUSES = (
    "PLANNER_RELATION_CONCEPT_MISSING", "PLANNER_DIRECTION_CONCEPT_MISSING",
    "PLANNER_RESPONSE_ROLE_MISSING", "VALID_RELATION_TERM_BECAME_UNRESOLVED",
    "VALID_ENDPOINT_TERM_BECAME_UNRESOLVED", "VALID_CONTEXT_TERM_BECAME_UNRESOLVED",
    "RELATION_LEXICON_COVERAGE_GAP", "ENDPOINT_LEXICON_COVERAGE_GAP",
    "EVENT_FRAME_ROLE_MAPPING_FAILURE", "RELATION_BINDING_TOO_STRICT",
    "BIOLOGICAL_UNIT_ELIGIBILITY_GAP", "NESTED_TREATMENT_BINDING_GAP",
    "THERAPY_RESPONSE_BINDING_GAP", "COMPILER_MINIMUM_REQUIREMENT_FAILURE",
    "GENUINELY_INSUFFICIENT_PLANNER_PROPOSAL", "OTHER",
)


def require(ok: bool, why: str) -> None:
    if not ok:
        raise ValueError(why)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def lines(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write(name: str, value) -> None:
    path = RUN / name
    require(not path.is_symlink(), f"output symlink: {name}")
    body = (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(body)


def write_lines(name: str, values) -> None:
    path = RUN / name
    require(not path.is_symlink(), f"output symlink: {name}")
    body = b"".join(json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n" for row in values)
    path.write_bytes(body)


def write_text(name: str, value: str) -> None:
    path = RUN / name
    require(not path.is_symlink(), f"output symlink: {name}")
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def verify_root(path: Path, expected: str) -> dict:
    manifest = load(path / "validation.json")
    pairs = manifest["aggregate_components"]
    for name, expected_file_sha in pairs:
        require(sha(path / name) == expected_file_sha, f"protected component changed: {path.name}/{name}")
    require(sha256_value(pairs) == expected, f"protected aggregate changed: {path.name}")
    return {"root_sha256": expected, "component_count": len(pairs), "component_hashes_verified": True}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).casefold().replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")).strip()


def frozen_signature(intents: list[dict]) -> list:
    return [(intent["intent_id"],
             [(b["blueprint_id"], tuple(b["concept_ids"])) for b in intent["candidate_query_blueprints"]],
             [(c["concept_id"], c["concept_type"],
               [(t["term_id"], t["term"]) for t in c["proposed_terms"]]) for c in intent["search_concepts"]])
            for intent in intents]


def raw_relation_candidate(term: str, target: dict) -> dict:
    """Diagnostic lexical evidence only; this does not authorize a query term."""
    phrase = " " + normalize(term) + " "
    subject = [normalize(x) for x in str(target["subject"]).split(" / ")]
    response = [normalize(x) for x in str(target["object"]).split(" / ")]
    exact_response = any(x and f" {x} " in phrase for x in response)
    # A stripped terminal Greek descriptor is a *diagnostic* possible match,
    # never scientific equivalence or a search-only permission.
    abbreviated_response = any(
        len(x.split()) == 2 and x.split()[-1] in {"alpha", "beta", "gamma"}
        and f" {x.split()[0]} " in phrase for x in response
    )
    operator = bool(re.search(r"\b(?:increas\w*|decreas\w*|reduc\w*|suppress\w*|inhibit\w*|enhanc\w*|rescu\w*|revers\w*|restor\w*|sensitiz\w*)\b", phrase))
    return {"subject_present": any(x and f" {x} " in phrase for x in subject),
            "response_exact": exact_response, "response_abbreviation_candidate": abbreviated_response,
            "relation_operator_present": operator,
            "diagnostically_linked": any(x and f" {x} " in phrase for x in subject)
            and (exact_response or abbreviated_response) and operator}


def term_diagnostic(receipt: dict, prior: dict | None) -> tuple[str, str]:
    cat = (prior or {}).get("semantic_audit_category", "NOT_PRIOR_SEARCH_ONLY")
    rule = receipt["eligibility_rule_id"]
    dimension = receipt["concept_type"]
    if cat == "OVERBROAD": return "CORRECTLY_WITHHELD_OVERBROAD", "prior diagnostic overbroad category"
    if cat == "SEMANTIC_DRIFT" or rule == "MECHANISTIC_PROXY_REQUIRES_EXPLICIT_AUTHORITY":
        return "CORRECTLY_WITHHELD_ENTITY_SUBSTITUTION", "different entity or component route lacks identity authority"
    if cat == "BROADER_BUT_TARGET_RELATED":
        return "CORRECTLY_WITHHELD_CONTEXT_BROADENING", "broader biological unit is not a lexical variant"
    if cat == "SAFE_LEXICAL_VARIANT":
        return "PLAUSIBLE_LEXICAL_VARIANT_MISSING_GENERIC_RULE", "previous diagnostic lexical category; not promoted"
    if cat == "RELATION_PARAPHRASE":
        return "PLAUSIBLE_RELATION_PARAPHRASE_MISSING_LEXICON", "prior diagnostic relation category; not promoted"
    if cat == "ENDPOINT_PARAPHRASE":
        return "PLAUSIBLE_ENDPOINT_PARAPHRASE_MISSING_LEXICON", "prior diagnostic endpoint category; not promoted"
    if cat == "CONTEXT_VARIANT" and dimension == "biological_unit":
        return "PLAUSIBLE_BIOLOGICAL_UNIT_VARIANT_MISSING_GENERIC_AUTHORITY", "prior context variant; compatibility unverified"
    if cat == "CONTEXT_VARIANT":
        return "PLAUSIBLE_CONTEXT_VARIANT_MISSING_GENERIC_AUTHORITY", "prior context variant; compatibility unverified"
    return "OTHER_UNRESOLVED", "no safe generic conclusion from frozen offline evidence"


def inventory_entry(path: str, callsite: str, classification: str, role: str, *, kind: str = "execution_boundary") -> dict:
    require((ROOT / path).is_file(), f"provider inventory path missing: {path}")
    return {"path": path, "callsite": callsite, "classification": classification,
            "role": role, "kind": kind, "static_source_only": True}


def provider_inventory() -> tuple[list[dict], dict, dict, dict, dict]:
    e = inventory_entry
    entries = [
        e("src/code_engine/search/proposition_aware_query_planner_v1.py", "DEFAULT_DEVELOPMENT_CONFIG + PropositionAwareQueryPlannerV1.plan", "OPENAI_REQUIRES_MIGRATION", "prospective planner defaults to OpenAI gpt-5.6-sol; injected call only"),
        e("src/code_engine/extraction/client_factory.py", "OpenAIJSONClient.extract_json_result + OpenAI-key fallback", "OPENAI_REQUIRES_MIGRATION", "active optional OpenAI L1/L2 transport route"),
        e("src/code_engine/extraction/deepseek_client.py", "DeepSeekClient.extract_json_result", "DEEPSEEK_ALREADY", "direct DeepSeek JSON HTTP transport"),
        e("src/code_engine/extraction/l1_extractor.py", "extract_l1_claims", "DEEPSEEK_ALREADY", "default L1 model and deferred DeepSeek client"),
        e("src/code_engine/fulltext/failed_block_recovery.py", "recover_failed_blocks", "DEEPSEEK_ALREADY", "pinned deepseek-v4-pro recovery"),
        e("src/code_engine/fulltext/fulltext_l1_v2_smoke.py", "execute_v2_smoke", "DEEPSEEK_ALREADY", "pinned DeepSeek provider smoke"),
        e("src/code_engine/fulltext/fulltext_l1_v3_smoke.py", "execute_v3_smoke", "DEEPSEEK_ALREADY", "pinned DeepSeek provider smoke"),
        e("src/code_engine/encoder/scientific_encoder.py", "create_default_scientific_encoder_client", "DEEPSEEK_ALREADY", "default DeepSeek client construction"),
        e("src/code_engine/cli/intake.py", "active_llm construction", "DEEPSEEK_ALREADY", "semantic intake CLI default DeepSeek client"),
        e("src/code_engine/extraction/abstract_screening.py", "screen_abstracts client.extract_json", "PROVIDER_AGNOSTIC", "injected L1 client"),
        e("src/code_engine/extraction/progressive_l1.py", "progressive extraction client.extract_json", "PROVIDER_AGNOSTIC", "injected L1 client"),
        e("src/code_engine/fulltext/fulltext_l1_extractor.py", "extract_fulltext_claims client.extract_json", "PROVIDER_AGNOSTIC", "injected fulltext L1 client"),
        e("src/code_engine/fulltext/fulltext_l1_v2.py", "extract_v2 blocks via client", "PROVIDER_AGNOSTIC", "provider/model included in cache identity"),
        e("src/code_engine/context_attribution/runner.py", "provider extraction and comparison", "PROVIDER_AGNOSTIC", "uses shared provider settings; accepts OpenAI and DeepSeek"),
        e("src/code_engine/context_attribution/recovery_execution.py", "targeted provider recovery", "PROVIDER_AGNOSTIC", "execution identity accepts provider/model"),
        e("src/code_engine/normalization/llm_entity_cleaner.py", "EntityCleaner client.extract_json", "PROVIDER_AGNOSTIC", "L2 client injected through shared factory"),
        e("src/code_engine/normalization/providers/llm_proposer.py", "LLMCandidateProposerProvider.propose", "PROVIDER_AGNOSTIC", "injected proposer client"),
        e("src/code_engine/encoder/semantic_intake.py", "run_semantic_intake client.extract_json", "PROVIDER_AGNOSTIC", "injected or default client"),
        e("src/code_engine/encoder/repair.py", "repair_json_response client.extract_json", "PROVIDER_AGNOSTIC", "injected client; repair call path"),
        e("src/code_engine/query/search_planner.py", "LLM search query planner client.extract_json", "PROVIDER_AGNOSTIC", "injected client"),
        e("src/code_engine/search/semantic_search_intent.py", "semantic search intent client.extract_json", "PROVIDER_AGNOSTIC", "injected client"),
        e("src/code_engine/fulltext/reasoning_trace.py", "claim reasoning client.extract_json", "PROVIDER_AGNOSTIC", "injected client"),
        e("tools/run_search_plan_v24_dev_real_planner_generation.py", "codex exec gpt-5.6-sol", "HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY", "frozen development planner-generation execution"),
        e("tools/run_search_plan_v24_dev_real_planner_generation_v2.py", "codex exec gpt-5.6-sol", "HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY", "frozen failed compatibility execution"),
        e("tools/run_search_plan_v24_dev_real_planner_generation_v3.py", "codex exec gpt-5.6-sol", "HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY", "frozen real planner corpus execution"),
    ]
    external = [
        ("src/code_engine/acquisition/literature_search.py", "PubMed ESearch/EFetch"),
        ("src/code_engine/fulltext/pmc_id_resolver.py", "PMC ID conversion"),
        ("src/code_engine/fulltext/pmc_oa_client.py", "PMC OA service"),
        ("src/code_engine/fulltext/pmc_oa_downloader.py", "PMC OA download"),
        ("src/code_engine/search/case002_plan_review.py", "NCBI query plan review"),
        ("src/code_engine/validation/external_api_smoke.py", "NCBI external API smoke"),
        ("src/code_engine/validation/pubmed_post_cutoff_validator.py", "PubMed validation"),
        ("src/code_engine/validation/production_v1_common.py", "generic scientific data API transport"),
        ("src/code_engine/validation/reactome_validator.py", "Reactome validation"),
        ("src/code_engine/validation/enrichr_validator.py", "Enrichr validation"),
        ("src/code_engine/normalization/clients/http.py", "external entity-provider HTTP transport"),
        ("src/code_engine/normalization/clients/mygene_client.py", "MyGene identity lookup"),
        ("src/code_engine/normalization/clients/ols_client.py", "OLS ontology lookup"),
        ("src/code_engine/normalization/clients/pubchem_client.py", "PubChem identity lookup"),
        ("src/code_engine/normalization/clients/uniprot_client.py", "UniProt identity lookup"),
        ("src/code_engine/normalization/clients/chembl_client.py", "ChEMBL identity lookup"),
        ("tools/generate_proposition_driven_targeted_network_discovery_smoke_v1.py", "historical PubMed/PMC smoke"),
        ("tools/run_search_plan_v21_retrieval_calibration_pilot_v1.py", "historical PubMed retrieval"),
        ("tools/run_search_plan_v22_depth180_supplemental_oa_acquisition_v1.py", "historical PMC OA acquisition"),
        ("tools/run_search_plan_v22_heldout_v1_network_retrieval.py", "historical PubMed retrieval"),
        ("tools/run_search_plan_v22_recall_tail_probe_v1.py", "historical PubMed retrieval"),
        ("tools/run_search_plan_v22_recall_tail_probe_v2_depth180.py", "historical PubMed retrieval"),
        ("tools/run_search_plan_v23_beta_2_primary_heldout_v2_network_retrieval.py", "historical PubMed/PMC retrieval"),
    ]
    entries.extend(e(path, role, "NON_LLM_EXTERNAL_API", role) for path, role in external)
    counts = Counter(x["classification"] for x in entries)
    test_fixture_files = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("*.py")
        if p.name != "test_v24_alpha1_zero_query_provider_audit_offline.py"
        and re.search(r"OpenAI|openai|gpt-5\.6-sol|gpt-4\.1-mini", p.read_text(encoding="utf-8")))
    nonexecuting_skeletons = sorted(str(p.relative_to(ROOT)) for p in
        (ROOT / "src/code_engine/validation/clients").glob("*_client.py"))
    inventory = {"artifact_schema_version": "V24Alpha1LLMProviderCallsiteInventoryV1",
        "scope": "static source inventory of scientific model execution boundaries and literature API modules",
        "classification_counts": dict(counts), "entries": entries,
        "tests_or_fixtures_with_openai_names": test_fixture_files,
        "nonexecuting_external_api_request_plan_skeletons": nonexecuting_skeletons,
        "prompt_and_configuration_surfaces": ["src/code_engine/search/proposition_aware_query_planner_v1.py",
            "src/code_engine/search/openai_planner_payload_transport_v2.py",
            "src/code_engine/search/openai_structured_output_schema_renderer_v1.py",
            "src/code_engine/extraction/policy.py", "src/code_engine/extraction/client_factory.py",
            ".env.example", "runs/20260918_search_plan_v24_dev_real_planner_generation_v3"],
        "provider_calls_made_for_audit": 0, "api_keys_read_or_persisted": False,
        "openai_production_callsites_requiring_migration": counts["OPENAI_REQUIRES_MIGRATION"],
        "historical_frozen_openai_callsites": counts["HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY"],
        "non_llm_external_api_callsites": counts["NON_LLM_EXTERNAL_API"]}
    config = {"artifact_schema_version": "V24Alpha1DeepSeekProviderConfigurationAuditV1",
        "existing_deepseek_provider_abstraction_found": True,
        "existing_default_l1_provider": "deepseek", "existing_default_l1_model_name": "deepseek-v4-pro",
        "planner_default_provider": "OpenAI", "planner_default_model": "gpt-5.6-sol",
        "canonical_deepseek_planner_model_configured": False,
        "deepseek_endpoint_in_source": "https://api.deepseek.com/v1/chat/completions",
        "base_url_configuration_mechanism": "fixed DeepSeekClient.endpoint; no DeepSeek base-URL env override found",
        "environment_variable_names": ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "L1_PROVIDER", "MODEL_NAME",
            "L2_ENTITY_CLEANER_PROVIDER", "L2_ENTITY_CLEANER_MODEL", "FULLTEXT_L1_V2_THINKING_MODE",
            "L1_CONNECT_TIMEOUT_SECONDS", "L1_READ_TIMEOUT_SECONDS", "L1_MAX_RETRIES"],
        "l1_sampling": {"temperature": 0.0, "top_p": 1.0, "default_max_retries": 2},
        "deepseek_client": {"default_thinking_mode": "provider_default", "default_max_retries": 2,
            "response_format": "json_object"},
        "fulltext_l1_v2": {"default_thinking_mode": "disabled", "max_tokens": 32768,
            "cache_identity_fields": ["provider", "model", "thinking_mode", "max_tokens", "config_hash"]},
        "environment_example": {"L1_PROVIDER": "unset", "MODEL_NAME": "unset", "L1_MAX_RETRIES": 1},
        "configuration_conflicts": [
            "Planner V1 still pins OpenAI while L1 default is DeepSeek; no prospective DeepSeek planner config exists.",
            "Shared L1 settings default to DeepSeek, but client factory falls back to OpenAI when only OPENAI_API_KEY exists.",
            "Retry and thinking defaults differ across general client, fulltext v2, and environment example; preserve workload-specific intent rather than silently choosing one."],
        "model_name_is_repository_config_not_external_verification": True,
        "secret_values_inspected": False}
    plan = {"artifact_schema_version": "V24Alpha1OpenAIToDeepSeekMigrationPlanV1",
        "implementation_deferred": True, "prospective_policy": "DEEPSEEK_ONLY_FOR_PROJECT_LLM_CALLS",
        "steps": [
            {"step": 1, "scope": "Versioned prospective planner", "files": ["src/code_engine/search/proposition_aware_query_planner_v1.py", "src/code_engine/search/openai_planner_payload_transport_v2.py", "src/code_engine/search/openai_structured_output_schema_renderer_v1.py"], "action": "Add a new DeepSeek planner config and provider-compatible payload transport/preflight; retain frozen V1 defaults, prompts and old outputs as historical evidence. Do not assume OpenAI Structured Outputs schema compatibility."},
            {"step": 2, "scope": "Shared L1/L2 provider policy", "files": ["src/code_engine/extraction/client_factory.py", "src/code_engine/extraction/policy.py", "src/code_engine/validation/readiness.py", "src/code_engine/context_attribution/identities.py", "src/code_engine/context_attribution/runner.py", "src/code_engine/context_attribution/recovery_execution.py"], "action": "Make future model execution fail closed unless explicitly DeepSeek; remove implicit OpenAI-key fallback from future runs while preserving historical replays."},
            {"step": 3, "scope": "Execution entry points and configuration", "files": ["src/code_engine/cli/run.py", "src/code_engine/cli/triple_batch.py", "src/code_engine/cli/context_attribution.py", "src/code_engine/cli/print_env_template.py", "src/code_engine/normalization/llm_entity_cleaner.py", ".env.example"], "action": "Route prospective planner, L1, context attribution and optional L2 cleaner to approved DeepSeek configuration; keep NCBI_API_KEY and literature API paths unchanged."},
            {"step": 4, "scope": "Identity and regression tests", "files": ["tests/test_cli_l1_client_wiring.py", "tests/test_openai_planner_payload_transport_v2.py", "tests/test_openai_structured_output_schema_renderer_v1.py", "src/code_engine/query/prompt_compatibility.py", "src/code_engine/extraction/llm_cache.py", "src/code_engine/fulltext/fulltext_l1_v2.py"], "action": "Add prospective DeepSeek policy and transport tests; preserve frozen OpenAI compatibility fixtures; verify provider/model/prompt/schema/thinking cache separation and no historical cache reuse."},
        ],
        "compatibility_gates_before_any_future_provider_call": ["Select a repository-approved DeepSeek planner model; none is currently pinned for planner role.", "Validate provider request and JSON schema transport offline.", "Keep one-attempt fail-closed scientific post-validation.", "Obtain separate authorization for any paid/provider execution."],
        "excluded": ["No current model calls", "No provider implementation in this run", "No edits to frozen OpenAI artifacts", "No PubMed/PMC/NCBI provider migration"]}
    historical = {"artifact_schema_version": "V24Alpha1HistoricalProviderProvenanceAuditV1",
        "historical_provider_provenance_rewritten": False,
        "frozen_openai_execution_sources": [x["path"] for x in entries if x["classification"] == "HISTORICAL_FROZEN_OPENAI_DO_NOT_MODIFY"],
        "additional_frozen_evaluator_configuration": "tools/run_search_plan_v23_beta_2_primary_heldout_v2_pass_a_adjudication.py",
        "preservation_rule": "Historical OpenAI gpt-5.6-sol records and configuration checks remain truthful and unchanged; migration is prospective."}
    return entries, inventory, config, plan, historical


def main() -> None:
    require(not RUN.is_symlink(), "output run path is symlink")
    upstream = {"artifact_schema_version": "V24Alpha1AutopsyUpstreamVerificationV1",
        "alpha1": verify_root(ALPHA1, ROOTS["alpha1"]),
        "authority": verify_root(AUTH, ROOTS["authority"]),
        "semantic": verify_root(SEMANTIC, ROOTS["semantic"]),
        "raw_planner_corpus_sha256": sha(RAW), "status": "PASS"}
    require(upstream["raw_planner_corpus_sha256"] == RAW_SHA, "raw planner corpus changed")
    protected = [RAW, AUTH / "validated_development_plans.jsonl", SEMANTIC / "search_only_expansion_semantic_audit.json",
        ALPHA1 / "alpha1_validated_search_terms.jsonl", ALPHA1 / "relation_binding_analysis.json",
        ALPHA1 / "alpha1_compiled_queries.jsonl", ROOT / "src/code_engine/search/alpha1_relation_searchonly_v1.py",
        ROOT / "src/code_engine/search/proposition_aware_query_planner_v1.py",
        ROOT / "src/code_engine/extraction/client_factory.py"]
    before = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    RUN.mkdir(parents=True, exist_ok=True)
    write("upstream_root_verification.json", upstream)
    plans = {row["case_id"]: row["validated_plan"] for row in lines(AUTH / "validated_development_plans.jsonl")}
    raw = {row["case_id"]: row for row in lines(RAW)}
    projection = {row["case_id"]: row for row in lines(AUTH / "frozen_provider_payload_projection.jsonl")}
    require(len(plans) == len(raw) == len(projection) == 8 and plans.keys() == raw.keys() == projection.keys(), "eight-case identity mismatch")
    for case, plan in plans.items():
        sig = frozen_signature(plan["planner_proposal_payload"]["retrieval_intents"])
        require(sig == frozen_signature(raw[case]["structured_parsed_payload"]["retrieval_intents"]), f"raw-to-plan term/blueprint drift: {case}")
        require(sig == frozen_signature(projection[case]["planner_proposal_payload"]["retrieval_intents"]), f"projection-to-plan drift: {case}")
    terms = lines(ALPHA1 / "alpha1_validated_search_terms.jsonl")
    bindings = load(ALPHA1 / "relation_binding_analysis.json")["assessments"]
    events = load(ALPHA1 / "relation_event_frame_analysis.json")["frames"]
    validated = {row["case_id"]: row for row in lines(ALPHA1 / "alpha1_validated_development_plans.jsonl")}
    prior_rows = load(SEMANTIC / "search_only_expansion_semantic_audit.json")["terms"]
    prior = {(row["case_id"], row["term_id"]): row for row in prior_rows}
    receipts = {(row["case_id"], row["term_id"]): row for row in terms}
    event_by = {(row["case_id"], row["blueprint_id"]): row for row in events}
    require(len(terms) == 574 and Counter(t["final_authority_classification"] for t in terms)["UNRESOLVED"] == 328, "alpha1 term distribution changed")
    nonexec = [row for row in bindings if row["compiler_action"] != "COMPILE"]
    require(len(nonexec) == 17, "non-executable blueprint count changed")

    decomposition = []
    for assessment in nonexec:
        case, bid = assessment["case_id"], assessment["blueprint_id"]
        plan = plans[case]
        target = plan["canonical_proposition"]["target_payload"]
        intent = next(i for i in plan["planner_proposal_payload"]["retrieval_intents"] if i["intent_id"] == assessment["intent_id"])
        blueprint = next(b for b in intent["candidate_query_blueprints"] if b["blueprint_id"] == bid)
        concepts = [c for c in intent["search_concepts"] if c["concept_id"] in blueprint["concept_ids"]]
        by_dimension = defaultdict(list)
        for concept in concepts:
            for proposal in concept["proposed_terms"]:
                receipt = receipts[case, proposal["term_id"]]
                by_dimension[concept["concept_type"]].append({"concept_id": concept["concept_id"],
                    "term_id": proposal["term_id"], "term": proposal["term"],
                    "old_classification": next(r["deterministic_classification"] for r in plan["term_validation_receipts"] if r["term_id"] == proposal["term_id"]),
                    "alpha1_classification": receipt["final_authority_classification"],
                    "eligibility_rule_id": receipt["eligibility_rule_id"],
                    "receipt_sha256": receipt["receipt_sha256"]})
        role_terms = by_dimension["relation"] + by_dimension["direction"]
        raw_linked = [{"term_id": t["term_id"], "term": t["term"], **raw_relation_candidate(t["term"], target)}
                      for t in role_terms if raw_relation_candidate(t["term"], target)["diagnostically_linked"]]
        linked_withheld = [t for t in raw_linked if receipts[case, t["term_id"]]["final_authority_classification"] == "UNRESOLVED"]
        mechanistic = any(t["eligibility_rule_id"] == "MECHANISTIC_PROXY_REQUIRES_EXPLICIT_AUTHORITY" for t in role_terms)
        if linked_withheld:
            first_stage = STAGES[1]
        elif assessment["subject_side_searchable"] and assessment["response_side_searchable"] and assessment["direction_searchable"]:
            first_stage = STAGES[0]
        else:
            first_stage = STAGES[0]
        if mechanistic:
            binding_review = "probable_true_underrepresentation"
        elif linked_withheld:
            binding_review = "uncertain"
        elif all(assessment[k] for k in ("subject_side_searchable", "response_side_searchable", "direction_searchable")):
            binding_review = "probable_binding_false_negative"
        else:
            binding_review = "probable_true_underrepresentation"
        causes = ["COMPILER_MINIMUM_REQUIREMENT_FAILURE"]
        if linked_withheld and not mechanistic: causes.insert(0, "VALID_RELATION_TERM_BECAME_UNRESOLVED")
        elif assessment["direction_searchable"]: causes.insert(0, "RELATION_BINDING_TOO_STRICT")
        else: causes.insert(0, "GENUINELY_INSUFFICIENT_PLANNER_PROPOSAL")
        if mechanistic:
            causes.append("OTHER")
        if by_dimension["endpoint_property"] and not any(x["alpha1_classification"] in
            {"AUTHORIZED_EQUIVALENT", "SEARCH_ONLY_EXPANSION"} for x in by_dimension["endpoint_property"]):
            causes.append("VALID_ENDPOINT_TERM_BECAME_UNRESOLVED")
        if not assessment["nested_treatment_bound"]:
            causes.append("VALID_CONTEXT_TERM_BECAME_UNRESOLVED")
        require(set(causes) <= set(CAUSES), "unknown failure cause")
        event = event_by[case, bid]
        decomposition.append({
            "case_id": case, "intent_id": intent["intent_id"], "intent_type": intent["intent_type"],
            "blueprint_id": bid, "first_loss_stage": first_stage,
            "stage_chain": ["FROZEN_RAW_LLM_PROPOSAL", "PlannerProposalPayloadV1", "SearchTermValidationReceiptV1_1",
                            "RelationEventFrameV1", "RelationBindingAssessmentV1", "RetrievalPlanCoverageV1_1",
                            "NON_EXECUTABLE_RELATION_UNDERREPRESENTED"],
            "raw_response_sha256": raw[case]["raw_response_sha256"],
            "planner_proposal_sha256": projection[case]["planner_proposal_sha256"],
            "alpha1_receipts_sha256": validated[case]["alpha1_term_receipt_sha256"],
            "event_frame_semantic_roles": event["semantic_roles"],
            "event_frame_polarity_or_direction": event["polarity_or_direction"],
            "relation_binding_state": assessment["state"],
            "binding_predicates": {k: assessment[k] for k in (
                "subject_side_searchable", "response_side_searchable", "direction_searchable",
                "explicit_cross_role_phrase", "therapy_response_bound", "nested_treatment_bound",
                "dynamic_endpoint_bound")},
            "alpha1_dimension_coverage": next(x["dimension_coverage"] for x in validated[case]["coverage_v1_1"] if x["blueprint_id"] == bid),
            "raw_relation_expression_candidates": raw_linked,
            "linked_relation_terms_withheld": linked_withheld,
            "proposed_terms_by_dimension": dict(by_dimension),
            "failure_causes": sorted(set(causes)),
            "secondary_causes": sorted(set(causes) - {"VALID_RELATION_TERM_BECAME_UNRESOLVED" if linked_withheld and not mechanistic else "RELATION_BINDING_TOO_STRICT" if assessment["direction_searchable"] else "GENUINELY_INSUFFICIENT_PLANNER_PROPOSAL"}),
            "relation_binding_false_negative_review": binding_review,
            "deterministic_post_planner_false_negative": bool(linked_withheld and not mechanistic),
            "diagnostic_not_rule_change": True,
        })
    write_lines("alpha1_nonexecutable_blueprint_decomposition.jsonl", decomposition)
    first_counts = Counter(x["first_loss_stage"] for x in decomposition)
    case_counts = Counter(x["case_id"] for x in decomposition)
    zero_query_cases = {case for case, row in validated.items() if not row["compiled_query_ids"]}
    require(len(zero_query_cases) == 5, "zero-query case count changed")
    stage = {"artifact_schema_version": "V24Alpha1StageAttributionSummaryV1",
        "nonexecuted_blueprint_count": len(decomposition), "first_stage_counts": dict(first_counts),
        "nonexecuted_case_counts": dict(case_counts),
        "zero_query_case_counts": {case: case_counts[case] for case in sorted(zero_query_cases)},
        "planner_missing_relation_count": first_counts["PLANNER_DID_NOT_PROPOSE"],
        "validator_withheld_critical_term_count": first_counts["PLANNER_PROPOSED_BUT_VALIDATOR_WITHHELD"],
        "event_frame_binding_failure_count": first_counts["VALIDATED_BUT_EVENT_FRAME_FAILED"],
        "compiler_requirement_failure_count": first_counts["EVENT_FRAME_VALID_BUT_COMPILER_BLOCKED"],
        "downstream_compiler_blocks": len(decomposition),
        "deterministic_post_planner_false_negative_count": sum(x["deterministic_post_planner_false_negative"] for x in decomposition),
        "attribution_note": "First loss counts are exclusive; secondary causes and possible alternate role-composition interpretations may overlap."}
    require(sum(first_counts.values()) == 17, "first-stage decomposition does not cover 17")
    write("alpha1_stage_attribution_summary.json", stage)

    unresolved = []
    for receipt in terms:
        if receipt["final_authority_classification"] != "UNRESOLVED":
            continue
        old = prior.get((receipt["case_id"], receipt["term_id"]))
        category, basis = term_diagnostic(receipt, old)
        unresolved.append({"case_id": receipt["case_id"], "term_id": receipt["term_id"],
            "term": receipt["term"], "concept_type": receipt["concept_type"],
            "alpha1_classification_unchanged": "UNRESOLVED",
            "diagnostic_category": category, "diagnostic_basis": basis,
            "prior_semantic_category": (old or {}).get("semantic_audit_category"),
            "eligibility_rule_id": receipt["eligibility_rule_id"],
            "diagnostic_not_executable_authority": True})
    require(len(unresolved) == 328, "not 328 unresolved terms")
    diag_dist = Counter(x["diagnostic_category"] for x in unresolved)
    correctly = sum(v for k, v in diag_dist.items() if k.startswith("CORRECTLY_WITHHELD"))
    plausible = sum(v for k, v in diag_dist.items() if k.startswith("PLAUSIBLE"))
    write("unresolved_term_diagnostic.json", {"artifact_schema_version": "V24Alpha1UnresolvedTermDiagnosticV1",
        "term_count": len(unresolved), "diagnostic_only": True, "terms": unresolved})
    write("unresolved_term_diagnostic_summary.json", {"artifact_schema_version": "V24Alpha1UnresolvedTermDiagnosticSummaryV1",
        "alpha1_unresolved_term_count": len(unresolved), "category_counts": dict(diag_dist),
        "plausible_missing_generic_eligibility_count": plausible,
        "correctly_withheld_term_count": correctly,
        "other_unresolved_term_count": diag_dist["OTHER_UNRESOLVED"],
        "plausible_does_not_mean_authorized": True})

    case_targets = {
        "heldout_v2_101": "EGF increases ERK1/2 phosphorylation in epidermal keratinocytes",
        "heldout_v2_102": "IFN-gamma increases cell-surface HLA-DR expression in monocytes",
        "heldout_v2_103": "Wnt3a increases nuclear beta-catenin accumulation in intestinal epithelial cells",
        "heldout_v2_104": "IL-1beta increases PGE2 secretion from articular chondrocytes",
        "heldout_v2_106": "IL-10 suppresses LPS-induced TNF-alpha secretion in macrophages",
    }
    for case, title in case_targets.items():
        entries = [x for x in decomposition if x["case_id"] == case]
        text = [f"# {case} zero-query autopsy", "", f"Frozen target: {title}.", "",
            f"Frozen raw-to-projection-to-validated-plan term/blueprint signature: verified byte-stable semantic fields. Alpha1 executable queries: 0; non-executable blueprints: {len(entries)}.", "",
            "| Intent / blueprint | First loss stage | Binding state | Raw linked phrases | Critical withheld terms |",
            "|---|---|---|---:|---:|"]
        for x in entries:
            text.append(f"| `{x['intent_id']}` / `{x['blueprint_id']}` | {x['first_loss_stage']} | {x['relation_binding_state']} | {len(x['raw_relation_expression_candidates'])} | {len(x['linked_relation_terms_withheld'])} |")
        text.extend(["", "## Evidence by blueprint", ""])
        for x in entries:
            text.extend([f"### {x['blueprint_id']}", "",
                f"First loss: `{x['first_loss_stage']}`. Binding predicates: `{json.dumps(x['binding_predicates'], sort_keys=True)}`.", "",
                f"Failure causes: {', '.join(x['failure_causes'])}. Relation-binding review: `{x['relation_binding_false_negative_review']}`.", ""])
            for dimension in ("subject", "relation", "direction", "object_measurement_target", "endpoint_property", "nested_treatment", "biological_unit"):
                rows = x["proposed_terms_by_dimension"].get(dimension, [])
                if rows:
                    details = "; ".join(f"{r['term']} [{r['alpha1_classification']}]" for r in rows)
                    text.append(f"- {dimension}: {details}")
            text.append("")
        if case == "heldout_v2_106":
            text.extend(["The frozen planner supplied subject, LPS conditioning, TNF secretion and linked directional phrases. Alpha1 exact response-anchor checking does not recognize the abbreviated `TNF` mention in those phrases as the target's `TNF-alpha`; this is a diagnostic candidate false negative, not authority to equate them. Nested-treatment binding itself is true in all four assessments.", "", "Flag: `DETERMINISTIC_POST_PLANNER_FALSE_NEGATIVE`. Do not repair in this audit.", ""])
        elif case == "heldout_v2_103":
            text.extend(["Nuclear localization/accumulation endpoint terms survive, so endpoint semantics are not simply lost into generic Wnt language. The direct blueprint retains a standalone increase relation; endpoint/context blueprints have no eligible directional term. None proposes an explicit Wnt3a-to-beta-catenin directional phrase.", ""])
        elif case == "heldout_v2_104":
            text.extend(["PGE2 and secretion/extracellular-release terms survive; the generic secretion lexicon is adequate for the retained endpoint. The missing executable element is cross-role relation expression, not PGE2 identity or secretion.", ""])
        else:
            text.extend(["Core actor, response and endpoint concepts survive separately. No frozen relation/direction term explicitly binds actor to response. Whether validated role composition could safely substitute for a full phrase is an unresolved generic relation-binding question, not permission to loosen alpha1 here.", ""])
        write_text("case_" + case.rsplit("_", 1)[-1] + "_zero_query_autopsy.md", "\n".join(text))

    positives = []
    for case in ("heldout_v2_105", "heldout_v2_107", "heldout_v2_108"):
        current = [x for x in bindings if x["case_id"] == case and x["compiler_action"] == "COMPILE"]
        positives.append({"case_id": case, "compiled_query_count": len(current),
            "bound_blueprint_ids": [x["blueprint_id"] for x in current],
            "all_have_subject_response_direction_and_cross_role_phrase": all(all(x[k] for k in (
                "subject_side_searchable", "response_side_searchable", "direction_searchable", "explicit_cross_role_phrase")) for x in current),
            "therapy_response_bound": all(x["therapy_response_bound"] for x in current),
            "dynamic_endpoint_bound": all(x["dynamic_endpoint_bound"] for x in current),
            "development_structural_control_only": True})
    write("positive_case_control_analysis.json", {"artifact_schema_version": "V24Alpha1PositiveCaseControlAnalysisV1",
        "controls": positives, "total_compiled_queries": sum(x["compiled_query_count"] for x in positives),
        "no_retrieval_or_relevance_inference": True})
    reviews = Counter(x["relation_binding_false_negative_review"] for x in decomposition)
    write("relation_binding_false_negative_audit.json", {"artifact_schema_version": "V24Alpha1RelationBindingFalseNegativeAuditV1",
        "review_counts": dict(reviews), "probable_binding_false_negative_count": reviews["probable_binding_false_negative"],
        "probable_true_underrepresentation_count": reviews["probable_true_underrepresentation"],
        "uncertain_count": reviews["uncertain"],
        "caveat": "Probable false negatives assume separately validated blueprint roles may form an event; alpha1 currently requires an eligible cross-role phrase. No rule changes are made.",
        "blueprints": [{"case_id": x["case_id"], "blueprint_id": x["blueprint_id"],
            "review": x["relation_binding_false_negative_review"],
            "first_loss_stage": x["first_loss_stage"]} for x in decomposition]})
    critical = [x for x in decomposition if x["linked_relation_terms_withheld"]]
    write("search_only_eligibility_false_negative_audit.json", {"artifact_schema_version": "V24Alpha1SearchOnlyEligibilityFalseNegativeAuditV1",
        "nonexecutable_blueprints_with_critical_search_only_to_unresolved": len(critical),
        "probable_deterministic_false_negative_blueprint_count": sum(x["deterministic_post_planner_false_negative"] for x in critical),
        "correctly_withheld_mechanistic_blueprint_count": sum(any(t["eligibility_rule_id"] == "MECHANISTIC_PROXY_REQUIRES_EXPLICIT_AUTHORITY" for t in x["proposed_terms_by_dimension"].get("relation", [])) for x in critical),
        "blueprints": [{"case_id": x["case_id"], "blueprint_id": x["blueprint_id"],
            "withheld_term_ids": [t["term_id"] for t in x["linked_relation_terms_withheld"]],
            "diagnostic_generic_gap": "response-name Greek-suffix abbreviation handling requires separate authority" if x["deterministic_post_planner_false_negative"] else "mechanistic component substitution requires explicit identity authority",
            "classification_unchanged": True} for x in critical]})
    recommendation = "PLANNER_AND_DETERMINISTIC_REFINEMENT_NEEDED"
    write("next_component_recommendation.json", {"artifact_schema_version": "V24Alpha1NextComponentRecommendationV1",
        "recommendation": recommendation,
        "basis": ["Twelve blueprints lack a frozen explicit actor-to-response relation phrase.",
            "Four blueprints retain diagnostic linked language but alpha1 withholds it; deterministic response-anchor eligibility warrants generic investigation.",
            "One mechanistic proxy blueprint is appropriately blocked without identity authority.",
            "No PubMed performance or PASS-B relevance labels informed this decision."],
        "no_algorithm_change_this_run": True})

    entries, inventory, config, migration, historical = provider_inventory()
    write("llm_provider_callsite_inventory.json", inventory)
    write("deepseek_provider_configuration_audit.json", config)
    write("openai_to_deepseek_migration_plan.json", migration)
    write("historical_provider_provenance_audit.json", historical)
    write("heldout_specific_rule_audit.json", {"artifact_schema_version": "V24Alpha1AutopsyHeldoutSpecificRuleAuditV1",
        "production_case_specific_rules": 0,
        "case_specific_diagnostic_reports_only": sorted(case_targets),
        "production_algorithms_or_lexicons_modified": False,
        "prior_semantic_labels_used_only_as_diagnostics": True})
    after = {str(path.relative_to(ROOT)): sha(path) for path in protected}
    require(before == after, "historical scientific or provider source changed")
    write("scientific_state_safety_audit.json", {"artifact_schema_version": "V24Alpha1AutopsyScientificStateSafetyAuditV1",
        "historical_assets_modified": False, "protected_hashes_before": before, "protected_hashes_after": after,
        "production_algorithm_changes": 0, "provider_configuration_changes": 0,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0})
    summary = {"artifact_schema_version": "V24Alpha1ZeroQueryAutopsySummaryV1", "status": "COMPLETED",
        "nonexecuted_blueprint_count": len(decomposition), "zero_query_case_count": len(zero_query_cases),
        "planner_missing_relation_count": stage["planner_missing_relation_count"],
        "validator_withheld_critical_term_count": stage["validator_withheld_critical_term_count"],
        "event_frame_binding_failure_count": stage["event_frame_binding_failure_count"],
        "compiler_requirement_failure_count": stage["compiler_requirement_failure_count"],
        "probable_relation_binding_false_negative_count": reviews["probable_binding_false_negative"],
        "probable_true_relation_underrepresentation_count": reviews["probable_true_underrepresentation"],
        "uncertain_relation_binding_count": reviews["uncertain"],
        "alpha1_unresolved_term_count": len(unresolved),
        "plausible_missing_generic_eligibility_count": plausible,
        "correctly_withheld_term_count": correctly,
        "next_component_recommendation": recommendation,
        "project_default_llm_provider_policy": "DEEPSEEK",
        "deepseek_existing_configuration_found": True,
        "openai_production_callsites_requiring_migration": inventory["openai_production_callsites_requiring_migration"],
        "historical_frozen_openai_callsites": inventory["historical_frozen_openai_callsites"],
        "non_llm_external_api_callsites": inventory["non_llm_external_api_callsites"],
        "historical_provider_provenance_rewritten": False,
        "provider_calls": 0, "llm_calls": 0, "network_calls": 0,
        "retrieval_calls": 0, "candidate_records_seen": 0,
        "production_case_specific_rules": 0, "historical_assets_modified": False}
    write("summary.json", summary)
    components = [[p.name, sha(p)] for p in sorted(RUN.iterdir()) if p.is_file() and p.name not in
                  {"validation.json", "search_plan_v24_alpha1_zero_query_autopsy_sha256"}]
    root = sha256_value(components)
    write("validation.json", {"artifact_schema_version": "V24Alpha1ZeroQueryAutopsyValidationV1",
        "status": "PASS", "aggregate_components": components,
        "search_plan_v24_alpha1_zero_query_autopsy_sha256": root,
        "checks": {"three_upstream_roots_verified": True, "eight_raw_proposal_signatures_preserved": True,
            "seventeen_blueprints_attributed": True, "328_unresolved_terms_diagnosed": True,
            "no_algorithm_or_provider_changes": True, "historical_assets_unchanged": True,
            "zero_provider_llm_network_retrieval": True}})
    write_text("search_plan_v24_alpha1_zero_query_autopsy_sha256", root)
    print(json.dumps({"run": str(RUN), "root": root, "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
