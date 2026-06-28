# Package Architecture

## Package Boundary

The primary Python package is `code_engine`, implemented under
`src/code_engine/`. New application code should import `code_engine.*`.
`pyproject.toml` defines a standard `src`-layout package. The small root-level
`code_engine/__init__.py` is only a source-checkout bootstrap so package CLI
commands work before an editable install; it contains no domain implementation.

The package boundaries are:

- `common`: paths, JSON I/O, hashing, logging, and non-scientific constants
- `schemas`: stable data contracts grouped by responsibility
- `config`: strict section validation and audited path compatibility
- `domain`: future domain routing and prompt selection contracts
- `acquisition` and `preprocessing`: literature and payload boundaries
- `extraction`: API-dependent extraction adapters and LLM cache metadata
- `normalization` and `graph`: deterministic entity, conflict, and context logic
- `hypothesis` and `validation`: candidate search and validation boundaries
- `query`: offline coverage, planning, and answer assembly
- `reporting`, `evaluation`, and `visualization`: output-facing boundaries
- `cli`: package-oriented command entrypoints

## Compatibility Layer

`src.schemas`, `src.config`, `src.validators`, `src.reporting`, `src.query`,
`src.storage`, and migrated modules under `src.pipelines` are compatibility
wrappers. They re-export the corresponding `code_engine` implementations.
Legacy `src/pipelines/stage*.py` files remain in place because their stage names
and side effects are part of existing research workflows.

Files under `scripts/` are legacy CLI wrappers. The preferred entrypoint style is:

```bash
python -m code_engine.cli.query --help
python -m code_engine.cli.validate --help
python -m code_engine.cli.extract --help
python -m code_engine.cli.visualize
```

## Configuration Boundary

`configs/` is the preferred configuration root. It separates domain profiles,
prompts, normalization rules, validator registries, and generated proposals.
`config/schemas/` remains a legacy path. When a preferred config is absent and
the loader resolves a legacy equivalent, it writes a `legacy_config_path` event
to `reports/config_fallback_audit.json`.

## Runtime Boundary

`data/`, `reports/`, `logs/`, `runs/`, and `artifacts/` are runtime-oriented.
Historical artifacts may remain for reproducibility, but they are not the entry
point for source review. Start code review at `src/code_engine/`, then inspect
compatibility wrappers only when tracing an old stage command.

This remains research software. Package boundaries, import stability, and CLI
ownership are clearer, but the project is not production-ready.

Package-owned runtime loaders are clean-workspace safe: absent inventory,
knowledge-store, and LLM-cache files produce explicit empty objects with status
and warnings. They do not search `artifacts/legacy/` or `quarantine/` unless a
caller explicitly enables legacy-source access.
