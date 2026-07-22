# System A Sync Operations

Start with the single orchestrator's offline reuse/plan mode:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> --offline --reuse-only --dry-run
```

`--api --network` can incur provider cost. A non-dry-run Atlas sync changes the
active projection and is a high-risk operation requiring explicit authorization,
backup, completeness checks, and staging validation.

The manual sync commands below are historical recovery/developer diagnostics.
In the current checkout their CLI import fails because of a circular import, so
they are not verified operational commands. Do not bypass the failure by calling
internal activation functions or editing registry JSON. See
`docs/atlas_operations.md`.

The importer performs discover → ready/manifest validation → path/hash/count verification → v5 adaptation → temporary projection → projection validation → one database transaction → immutable-directory finalize → atomic current-registry switch. A failure before the last step cannot change `current_projection.json`; a rejected source receives a structured report under `quarantine/`.

Ingestion identity is `(source_run_id, manifest_hash, adapter_version)`. The same identity is a no-op. Projection identity is content based over the selected source manifest hashes and adapter version; `generated_at`, temporary directories, database row IDs, and execution attempts must not create a new projection. A new adapter version may create a new projection; a new System A run creates new ingestion and prediction provenance without deleting its predecessor. SQLite stores only ingestion and artifact metadata. Evidence and claims stay in versioned files.

The one-command orchestrator treats Atlas sync as a semantic no-op when the current handoff manifest content and adapter version match the current projection. Repeating the same command must not create duplicate source ingestions, duplicate prediction runs, or a new projection directory, and it must preserve all other current cases plus Review Items, assignments, annotations, Gold, and metrics.

When checking a repeated case run after an API cost anomaly, prefer:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas --case-id <case_id> --reuse-only --json
```

This mode validates local handoff/projection no-op state without refreshing Atlas from a newly executed System A run. If Atlas sync cannot be proven reusable, it fails closed instead of creating a new ingestion or projection.

```bash
# Preview all ready runs
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once --dry-run

# HIGH RISK / currently unverified: synchronizes and activates new runs
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once

# HIGH RISK / currently unverified: synchronizes and activates one manifest
PYTHONPATH=src python -m code_engine.cli.system_b_sync_system_a --manifest runs/RUN/artifacts/atlas_handoff_manifest.json --runs-root runs --database-url sqlite:///data/code_atlas.db --output-root system_b_outputs/system_a_sync --once

# Inspect quarantine
find system_b_outputs/system_a_sync/quarantine -type f -name '*.json' -print
```

Before migration, run `atlas_db_backup`; then
`python -m code_engine.cli.atlas_db_migrate --revision head` and
`atlas_db_check`. Recovery consists of retaining the failed/quarantined source,
correcting the source or adapter, and rerunning. Never delete old projections.

When historical duplicate projections exist for the same logical case request, keep them as immutable audit records. The current registry should remain on the latest valid projection unless an operator explicitly performs a scientific rollback.

Interrupted fall-through outputs should also be retained. State reconciliation records them as abandoned/interrupted and restores the current validated output; it does not delete old run directories, old handoffs, old projections, or evaluation state.

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
