# Artifact Policy

This repository currently includes both source code and research run artifacts. Do not delete existing user data casually. Use this policy for future cleanup and commits.

## Source Files

These are source-controlled engineering assets:

- `src/`
- `scripts/`
- `tests/`
- `config/`
- `docs/`
- `README.md`

## Runtime Artifacts

These are generated or cache-like outputs:

- `data/raw/`
- `data/interim/`
- `data/processed/`
- `reports/`
- `logs/`
- `__pycache__/`
- `.cache/`

## Small Demo Artifacts

Small artifacts may be retained when they are explicitly curated for smoke tests or documentation:

- curated mini omics index
- tiny fixture data
- demo examples under `data/fixtures/` or `data/demo/`
- test fixtures under `tests/fixtures/`

Fixture data is source-controlled when it is small, deterministic, and needed
for behavior tests. Current historical run outputs under `data/` and `reports/`
are research artifacts; they are useful for review but should not be treated as
source code.

## Large Files To Keep Out Of Source Control

Avoid committing:

- full PMC dumps
- full LINCS matrices
- large processed outputs
- large raw LLM response caches
- run-specific reports

## Recommended Ignore Policy

The `.gitignore` documents generated output boundaries. If a demo fixture is needed, put it under `data/fixtures/` or `data/demo/` and add a short README explaining its purpose.

The ignore policy intentionally does not ignore `tests/fixtures/`.
