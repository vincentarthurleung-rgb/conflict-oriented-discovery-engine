# Evaluation Staging Import

Every immutable projection includes claim, conflict-pair, and context candidate pools plus a sampling summary. Stable source keys combine prediction run, case, source artifact hash, claim/pair identity, schema ID, and schema version. Rebuilding the same projection deduplicates by that key.

Synchronization never creates Review Items, assignments, annotations, adjudications, Gold, or metric runs. Import is a separate owner-controlled action and defaults to preview:

```bash
PYTHONPATH=src python -m code_engine.cli.system_b_import_evaluation_staging \
  --staging-root system_b_outputs/system_a_sync/projections/PROJECTION/evaluation_staging \
  --project-id PILOT_PROJECT_ID --split pilot --sampling-plan all

# After reviewing the preview
PYTHONPATH=src python -m code_engine.cli.system_b_import_evaluation_staging \
  --staging-root system_b_outputs/system_a_sync/projections/PROJECTION/evaluation_staging \
  --project-id PILOT_PROJECT_ID --split pilot --sampling-plan all --apply
```

Normal imports require the target project's existing namespace to be `pilot`. Production needs the explicit `--allow-production` flag and operational readiness review. Imports create new stable `stg_...` Review Item IDs only and never overwrite an existing item or create assignments. Pilot and production metrics remain isolated by the existing project namespace.
