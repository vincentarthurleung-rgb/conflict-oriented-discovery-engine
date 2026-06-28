# Artifact Policy

This repository currently includes both source code and research run artifacts. Do not delete existing user data casually. Use this policy for future cleanup and commits.

## Source Files

These are source-controlled engineering assets:

- `src/`
- `scripts/`
- `tests/`
- `config/`
- `configs/`
- `docs/`
- `README.md`

## Runtime Artifacts

These are generated or cache-like outputs:

- `data/raw/`
- `data/interim/`
- `data/processed/`
- `data/index/`
- `data/query/`
- `reports/`
- `logs/`
- `runs/`
- `artifacts/`
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
source code or as the starting point for package review.

## Large Files To Keep Out Of Source Control

Avoid committing:

- full PMC dumps
- full LINCS matrices
- large processed outputs
- large raw LLM response caches
- run-specific reports

## Recommended Ignore Policy

The `.gitignore` documents generated output boundaries. If a demo fixture is needed, put it under `data/fixtures/` or `data/demo/` and add a short README explaining its purpose.

The ignore policy intentionally does not ignore `tests/fixtures/`, `data/demo/`,
or `data/fixtures/` when those directories contain small reviewable examples.

Query-layer indexes and reports are reproducible local runtime artifacts. The
inventory, knowledge-store cache, LLM cache index, coverage reports, ingestion
plans, and query answers remain on disk for reuse but are ignored by default.

## Regeneration And Commit Boundary

Raw literature is a regenerable download cache. The retained global manifest
captures the registered corpus and acquisition query; reviewed Stage0 scripts
can rerun NCBI acquisition and update the cache. Raw XML and abstract files are
not committed.

Processed payloads, extracted tuples, refined contexts, conflict graphs,
hypotheses, validation outputs, query indexes, and reports are not source code.
New experiments should write under `runs/<run_id>/` so prompt, schema, config,
and output versions remain isolated.

Committed data should be limited to `tests/fixtures/`, optional `data/demo/` or
`data/fixtures/`, and minimal files under `data/metadata/`. Historical runtime
outputs may be archived externally but should not return to the active source
tree. See `docs/CLEANUP_POLICY.md`.

v4.2 EvidenceRecord, MechanismEdge, probabilistic conflict, and hypothesis
hyperedge examples used by tests belong in `tests/fixtures/`. Generated graph
states, dry-lab plans, heuristic policy rankings, and reports belong under
`runs/<run_id>/`, not in source-controlled `data/processed/`.

The safe maintenance command is
`python scripts/maintenance/cleanup_legacy_artifacts.py --dry-run`. Review its
`cleanup_reports/` audit before applying deletion. `quarantine/` is archival
storage and is never searched by current loaders unless legacy-source access is
explicitly enabled.
