# Preferred Configuration Layout

`configs/` is the package-oriented configuration root. Files under
`config/schemas/` remain available for legacy stage entrypoints.

- `domains/`: domain profiles
- `prompts/l1/`: extraction prompts and output contracts
- `normalization/`: entity and context normalization rules
- `validators/`: validator routing and curated/demo registries
- `generated/`: generated configuration proposals requiring review

Falling back from a preferred path to `config/schemas/` is recorded in
`reports/config_fallback_audit.json`.

`normalization/entity_registry.json` is a zero-entity compatibility stub, not a
production registry. The ketamine dictionary is an explicit pilot fixture under
`normalization/fixtures/`. Production Layer 2 uses EntityResolutionHub providers.
