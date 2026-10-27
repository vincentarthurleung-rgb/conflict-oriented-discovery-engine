"""Bounded completion dependencies, separate from exact provider-request identity.

This is an explicit maintenance list for PilotCaseExecutor, not a repository
snapshot or an activation of the dormant L4/L5 paths. Hashes grant no authority.
"""
from importlib.metadata import version
from pathlib import Path
import platform

from code_engine.discovery.ai_review_shadow import content_hash, file_hash

VERSION = "pilot_effective_dependencies_v1"
DEFAULT_REVIEW_PROMPT = "runs/20261017_code_ai_first_scientific_review_shadow_seen_offline/review_prompt_v1.txt"

# Paths are explicit, bounded, and grouped by the effective caller they affect.
DEPENDENCIES = {
    "executor_and_product": (
        "orchestration/pilot_dependencies.py", "acquisition/pilot_corpus.py", "orchestration/pilot_runtime.py", "orchestration/pilot_case.py",
        "orchestration/pilot_backend.py", "orchestration/pilot_linkage.py", "orchestration/pilot_inclusion.py", "orchestration/pilot_budget.py",
        "orchestration/pilot_model_cache.py", "orchestration/pilot_delivery.py", "orchestration/component_probe.py",
        "orchestration/pilot_dataset.py", "orchestration/pilot_replay.py",
        "discovery/pilot_acceptance.py", "system_b/annotation_schemas/registry.py",
        "system_b/annotation_schemas/definitions/ai_provisional_case_attempt_v2.json",
    ),
    "intake_routing_windows": (
        "query/intake.py", "query/search_planner.py", "search/search_plan_replay.py", "search/planner_authority_contract_split_v1.py", "query/intent.py", "encoder/semantic_intake.py",
        "encoder/fallback.py", "encoder/semantic_verifier.py",
        "encoder/models.py", "schemas/models.py", "domain/models.py", "domain/router.py",
        "domain/prompt_registry.py", "domain/extraction_routing.py",
        "fulltext/source_windows.py", "fulltext/evidence_anchors.py",
    ),
    "construction": (
        "construction/handoff_adapter.py", "construction/builder_quality_bridge.py",
        "construction/builder_quality_bridge_v2.py",
        "extraction/polarity.py", "schemas/l1_extraction.py",
        "normalization/composite_endpoints.py",
    ),
    "v3_parser_hydration": (
        "fulltext/fulltext_l1_v2.py", "fulltext/fulltext_l1_extractor.py",
        "fulltext/fulltext_l1_draft_hydration_v3.py", "fulltext/fulltext_observation_v3.py",
        "schemas/fulltext_observation.py", "schemas/fulltext_observation_draft.py",
        "fulltext/experimental_semantics_registry.py",
        "fulltext/registries/experimental_semantics_registry_v1.json",
        "extraction/l1_budget.py",
    ),
    "core_and_candidate_contracts": tuple("extraction_assets/experimental_core/" + x + ".py" for x in (
        "assembly", "adapters", "models", "factors", "identities", "type_policy",
        "linkage", "linkage_completeness", "comparison_semantics", "comparator_linkage",
        "integrity", "projection", "readiness_v2", "linkage_candidates",
        "source_resolution_models", "source_envelope", "measurement_method", "repair_v1",
    )),
    "projection_and_semantics": (
        "fulltext/experimental_projection_handoff.py", "fulltext/evidence_projection.py",
        "fulltext/reentry.py", "fulltext/profiles.py", "schemas/evidence_chain.py",
        "normalization/experimental_admission.py", "normalization/core_eligibility.py",
        "normalization/intervention_semantics.py", "normalization/formal_relations.py",
        "normalization/endpoint_accessors.py", "normalization/adjudicator.py",
        "normalization/candidates.py", "normalization/resolver.py", "normalization/hub.py",
        "normalization/lexical.py", "normalization/models.py", "normalization/entity_type.py",
        "normalization/registry.py", "normalization/cache.py",
        "normalization/providers/local_curated.py", "normalization/providers/local_cache.py",
        "normalization/providers/null.py",
    ),
    "review_shadow_alignment_context": (
        "discovery/ai_review_shadow.py", "discovery/lanes.py",
        "system_b/persistence/services/pilot_review_display.py",
    ),
}
REPOSITORY_DEPENDENCIES = (
    "configs/normalization/entity_registry.json",
    "scripts/search_plan_v24_alpha318b_post_builder_prechecks.py",
    "scripts/search_plan_v24_alpha318a1_source_contracts.py",
    "src/code_engine/system_b/explorer/static/app.js",
    "scripts/search_plan_v24_alpha317c_reconcile_builder_offline.py",
    "scripts/search_plan_v24_alpha320a_v4_localizer.py",
)


def effective_dependencies(repository, *, review_prompt=None, contracts=(), pricing=None,
                           annotation_pins=None, catalog_fingerprint=None, fixture=False):
    root = Path(repository).resolve()
    files = {}
    for group, paths in DEPENDENCIES.items():
        files[group] = {p: file_hash(root / "src/code_engine" / p) for p in paths}
    files["repository_contracts"] = {p: file_hash(root / p) for p in REPOSITORY_DEPENDENCIES}
    effective_prompt = Path(review_prompt) if review_prompt else root / DEFAULT_REVIEW_PROMPT
    bindings = {"review_prompt": {"path": str(effective_prompt.resolve()), "sha256": file_hash(effective_prompt)},
                "frozen_construction_contracts": {str(Path(p).resolve()): file_hash(Path(p)) for p in contracts}}
    # Pinned native annotations are still inputs; check actual bytes at the
    # completed-package fast path, not only when the reuse branch is reached.
    for source, pins in (annotation_pins or {}).items():
        for kind, pin in pins.items():
            actual = file_hash(Path(pin["path"]))
            if actual != pin["sha256"]:
                raise ValueError("explicit_native_annotation_hash_drift")
            bindings[source + ":" + kind] = {"path": pin["path"], "sha256": actual}
    value = {"schema_version": VERSION, "files": files, "input_bindings": bindings,
             "provider_model_settings": pricing or {}, "catalog_sha256": catalog_fingerprint,
             "fixture": fixture, "runtime": {"python": platform.python_version(),
                 **{p: version(p) for p in ("pydantic", "httpx")}},
             "scope": "current PilotCaseExecutor derivation; versioned candidate linkage integrated; no materialization authority",
             "raw_provider_cache_policy": "provider endpoint + exact canonical request bytes + fixture namespace; no derived dependencies"}
    return {**value, "sha256": content_hash(value)}
