# System A Sync Operations

For normal case execution, use the single orchestrated command:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas --case-id <case_id> --api --network
```

The manual sync commands below are recovery and developer diagnostics. The one-command service always performs a global ready-handoff sync so adding one case cannot replace the current projection with a single-case projection.

The importer performs discover → ready/manifest validation → path/hash/count verification → v5 adaptation → temporary projection → projection validation → one database transaction → immutable-directory finalize → atomic current-registry switch. A failure before the last step cannot change `current_projection.json`; a rejected source receives a structured report under `quarantine/`.

Ingestion identity is `(source_run_id, manifest_hash, adapter_version)`. The same identity is a no-op. Projection identity is content based over the selected source manifest hashes and adapter version; `generated_at`, temporary directories, database row IDs, and execution attempts must not create a new projection. A new adapter version may create a new projection; a new System A run creates new ingestion and prediction provenance without deleting its predecessor. SQLite stores only ingestion and artifact metadata. Evidence and claims stay in versioned files.

The one-command orchestrator treats Atlas sync as a semantic no-op when the current handoff manifest content and adapter version match the current projection. Repeating the same command must not create duplicate source ingestions, duplicate prediction runs, or a new projection directory, and it must preserve all other current cases plus Review Items, assignments, annotations, Gold, and metrics.

```bash
# Preview all ready runs
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once --dry-run

# Synchronize all new runs
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once

# Synchronize one manifest
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --manifest runs/RUN/artifacts/atlas_handoff_manifest.json --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once

# Inspect quarantine
find system_b_outputs/system_a_sync/quarantine -type f -name '*.json' -print
```

Before migration, run `atlas_db_backup`; then `atlas_db_migrate upgrade` (or Alembic under the repository's normal policy) and `atlas_db_check`. Recovery consists of retaining the failed/quarantined source, correcting the source or adapter, and rerunning. Never delete old projections.

When historical duplicate projections exist for the same logical case request, keep them as immutable audit records. The current registry should remain on the latest valid projection unless an operator explicitly performs a scientific rollback.

Batch backfill first freezes references and validation results without copying evidence bodies:

```bash
PYTHONPATH=src python -m code_engine.cli.atlas_publish_handoff --batch-id batch11_20260710_203635 --runs-root runs --backfill --offline --dry-run
PYTHONPATH=src python -m code_engine.cli.atlas_publish_handoff --batch-id batch11_20260710_203635 --runs-root runs --backfill --offline
```

The 2026-07-12 checkout used for the first backfill did not contain the two specified Wnt source runs. It therefore froze Wnt as `missing` and published 10 verified cases; operators must restore the original Wnt artifacts and rerun rather than synthesize its lineage or hashes.

Atlas can follow the registry and refresh on mtime change:

```bash
PYTHONPATH=src python -m code_engine.cli.system_b_serve_knowledge_explorer --projection-registry system_b_outputs/system_a_sync --database-url sqlite:///data/code_atlas.db --require-database --require-auth
```
