# L2 Entity Resolution Cleanup Audit

Generated before the EntityResolutionHub migration.

## Old registry references

- `normalization/registry.py` defines `DEFAULT_REGISTRY_PATH` as `configs/normalization/entity_registry.json` and falls back to `config/schemas/entity_registry.json`.
- `normalization/resolver.py`, `graph/ontology_alignment.py`, `cli/normalize.py`, and `pipelines/stage5_shannon_matrix.py` consume that default.
- Resolver integration tests construct `LocalBiomedicalRegistry` directly and therefore require a compatibility wrapper.
- `config/loader.py` retains the separate legacy schema path for legacy pipeline configuration.
- `configs/README.md`, `BIOMEDICAL_ENTITY_NORMALIZATION.md`, `CODE_REVIEW_GUIDE.md`, and `TECHNICAL_DESIGN_HANDBOOK.md` describe the pilot file as a general registry and require correction.

## TYPE_RULES references

- `TYPE_RULES` is defined and consumed only inside `normalization/entity_type.py`.
- `resolver.py` calls `classify_entity_type`; no production caller imports `TYPE_RULES` directly.
- It is safe to remove `TYPE_RULES` after `classify_entity_type` becomes a compatibility adapter over generic candidate inference.

## Legacy and dead boundaries

- `llm_candidate_proposer.py` is used by resolver tests and must remain as a compatibility wrapper until callers migrate to the provider interface.
- `LocalBiomedicalRegistry.lookup` is actively used by tests, CLI, legacy Stage5, and ResolverCascade. Keep it as a local-curated compatibility/provider adapter.
- Domain-specific registry files under `configs/normalization/registries/` are referenced conditionally but do not currently exist. ResolverCascade must stop treating their absence as a fallback to a production general dictionary.
- The builtin two-entity demo registry is test/demo fallback data and must not become the Hub default.

## Files safe to remove

- No referenced Python module is safe to remove before compatibility adapters land.
- The production role of `configs/normalization/entity_registry.json` is safe to remove after its content is migrated to a pilot fixture and the default path changes.
- Legacy stage scripts are not removal candidates.

## Files to keep as fixtures or wrappers

- Migrate the ketamine registry content to `configs/normalization/fixtures/ketamine_pilot_registry.json`.
- Keep `registry.py`, `resolver.py`, `normalizer.py`, `entity_type.py`, and `llm_candidate_proposer.py` as public compatibility surfaces.
- Keep existing registry test fixtures created in temporary directories.

## Migration notes

1. Introduce CandidateProvider, EntityResolutionHub, deterministic adjudicator, audit, and cache contracts.
2. Make ResolverCascade delegate to the Hub while preserving NormalizationDecision fields.
3. Change the default curated source to no registry; pilot data must be explicitly configured.
4. Convert CLI and workflow flags into Hub request guards; external and LLM providers remain doubly gated.
5. Keep unresolved/ambiguous/LLM-only candidates out of high-confidence graph use.

## Implemented cleanup outcome

- Migrated the pilot dictionary to `configs/normalization/fixtures/ketamine_pilot_registry.json`; the old path is now a zero-entity compatibility stub.
- Removed the implicit legacy-schema fallback and the hardcoded builtin demo registry. Pilot fallback requires explicit `allow_fallback` or an explicit fixture path.
- Removed `TYPE_RULES`; generic weak type inference now returns scored candidates.
- ResolverCascade, the main ontology adapter, workflow L2, and normalize CLI now use EntityResolutionHub by default.
- Legacy Stage5 accepts an explicit curated path but defaults to EntityResolutionHub.
- Kept LocalBiomedicalRegistry and the old LLM proposer module as compatibility adapters because tests and public imports still use them.
- Removed pilot-specific reference examples from the production normalization audit.
