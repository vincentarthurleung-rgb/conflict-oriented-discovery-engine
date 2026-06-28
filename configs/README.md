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

`normalization/entity_registry.json` is the preferred local curated biomedical
registry. Its legacy copy exists only for compatibility.
