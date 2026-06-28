# Runtime Cleanup Policy

## Purpose

The repository stores research software and minimal reproducibility metadata,
not a permanent literature mirror or historical output dump.

## Download Cache

Raw PMC XML and PubMed abstract files under `data/raw/` are download cache. They
are not committed by default. The retained `data/metadata/global_manifest.json`
records the registered corpus and acquisition query. Stage0 wrappers can rerun
the configured NCBI acquisition and update that manifest.

## Runtime Outputs

Stage1 payloads and processed L1, L1.5, L3, L4, L5, and L6 outputs are runtime
artifacts. Query indexes, knowledge-store caches, generated reports, and logs are
runtime artifacts as well. They are not source code or stable scientific truth.

The old L1 prompt v1 outputs have been intentionally removed from the active
workspace and must not be used as the current knowledge graph input. New L1 v2
runs should be assembled through the Domain Router, Prompt Registry, and Prompt
Compiler once those components are integrated into the extraction execution path.

## Run Isolation

Current experimental outputs should be written beneath `runs/<run_id>/`. A run
directory should contain its effective domain config, prompt/schema versions,
cache metadata, derived graph, reports, and audit trail. Only `runs/.gitkeep` is
committed.

Fixtures and small demos belong in `tests/fixtures/`, `data/fixtures/`, or
`data/demo/`. The global manifest and literature quality audit remain under
`data/metadata/` as minimal reproducibility metadata.

## Safe Cleanup Command

`scripts/maintenance/cleanup_legacy_artifacts.py` inventories first and writes
an audit to `cleanup_reports/`. Its default mode is dry-run. `--apply` removes
known runtime artifacts; `--apply --quarantine` additionally isolates uncertain
legacy artifacts beneath `quarantine/legacy_cleanup_<timestamp>/`.

Cleanup never treats archived data as an implicit fallback. Package loaders
return explicit empty inventory/store/cache states when current runtime data is
missing. See `docs/FRESH_RUN_GUIDE.md` for regeneration order.
