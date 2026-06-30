# Preferred Configuration Layout

`configs/` is the repository's single configuration root.

- `domains/`: domain profiles
- `prompts/l1/`: extraction prompts and output contracts
- `normalization/`: entity and context normalization rules
- `validators/`: validator routing and curated/demo registries
- `generated/`: generated configuration proposals requiring review

Missing configuration fails explicitly unless a caller opts into an in-memory
fallback. There is no secondary on-disk configuration tree.

`normalization/entity_registry.json` is the domain-neutral empty default. Curated
entities are enabled only through an explicit registry or pilot profile. The
ketamine dictionary is an explicit pilot fixture under `normalization/fixtures/`.
Production Layer 2 can also use EntityResolutionHub providers.
