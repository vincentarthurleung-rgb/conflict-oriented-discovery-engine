# One-command System A → Atlas

The recommended production entry is:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> \
  --api \
  --network
```

It resolves the generated case profile and frozen search plan, runs the abstract base pipeline through candidate selection, performs authoritative PMID→PMCID repair, retrieves PMC OA fulltext, runs Fulltext L1, extracts fulltext claim-centered reasoning traces, consolidates experimental context, performs v5 re-entry, publishes `atlas_handoff_v1`, globally synchronizes all current cases, refreshes Atlas, verifies evaluation-state safety, and confirms a second sync is a no-op.

## Resume and cache behavior

Resume is on by default. Control state is stored under `runs/_orchestration/<orchestration_id>/`; every scientific output directory is passed explicitly between services. Completed stages are reused only when their semantic fingerprint, lineage, required artifacts, provider/model configuration, and terminal manifest still validate. The semantic fingerprint is canonical JSON over scientific inputs and artifact content hashes. It excludes `--api`, `--network`, `--offline`, output directories, attempts, timestamps, orchestration IDs, version suffixes, and projection IDs. The flags only grant permission to call external services when a stage truly needs work. The base workflow retains its finer-grained L1 task cache and run-state resume behavior.

Stage reuse and content cache reuse are separate. Stage reuse skips the whole completed orchestration stage. Content cache reuse is lower level: a forced `fulltext_l1` stage may create a new output directory while still reusing compatible paper/chunk L1 cache entries and making zero provider calls.

An interrupted command can be repeated exactly. A failed Atlas sync resumes at sync without rerunning System A. A failed base run resumes its own `run_state.json`. Failed downstream attempts allocate a new output directory and retain prior artifacts.

`base_run` is the abstract acquisition/L1/L2 and candidate-selection boundary for this one-command DAG. It is not equivalent to the legacy internal `fulltext_escalation` workflow step. In the current DAG, PMC repair, fulltext retrieval/L1, reasoning traces, and context consolidation run as independent downstream stages. A legacy `fulltext_escalation=skipped` or `not_requested` status can be valid when the formal base manifest/card completed and the PMCID-repair candidate artifacts exist.

If an older orchestration marked `base_run` failed only because it expected legacy `fulltext_escalation=completed`, resume validates the existing output run before doing any work. When validation passes, the stage is marked `recovered_existing_output`, the original `stage_failed` event is retained, a `stage_recovered` event is appended, and Abstract L1 is not called again.

Force a stage and all downstream stages with repeatable options:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> --api --network \
  --force-stage fulltext_l1 --force-stage reentry
```

Stable stage names are `base_run`, `pmcid_repair`, `fulltext_l1`, `fulltext_reasoning_trace`, `fulltext_context_consolidation`, `reentry`, `handoff`, `atlas_sync`, and `verification`.

`--force-stage fulltext_l1` forces stage materialization, not cache bypass. A compatible cross-run Fulltext L1 chunk cache may still satisfy all chunks. Cache bypass requires an explicit cache-bypass option if one is added by the service; do not treat `--force-stage` as permission to discard content-addressed cache.

Run reasoning and downstream stages without re-running Fulltext L1:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> \
  --from-stage fulltext_reasoning_trace \
  --to-stage atlas_sync \
  --api \
  --network
```

Rebuild only consolidated context and downstream Atlas outputs offline:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> \
  --from-stage fulltext_context_consolidation \
  --to-stage atlas_sync \
  --offline
```

## Read-only planning

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> --api --network --dry-run
```

Dry-run does not create orchestration files, call the network/model, or write SQLite. It reports resolved package paths and one structured decision per stage: action (`reuse`, `recover`, or `run`), reason, stored/current semantic hash, changed components, output run, and expected API/network calls. For an identical completed command, expected API and network calls must be zero.

Use dry-run to confirm recovery before continuing:

```bash
PYTHONPATH=src python -m code_engine.cli.run_case_to_atlas \
  --case-id <case_id> \
  --api \
  --network \
  --dry-run
```

For a recoverable base output, the plan reports `base_run=recover`, `abstract_l1_api_expected=false`, and `next_stage=pmcid_repair`.

Use `--stop-after <stage>` for controlled development, `--no-atlas-sync` to stop after handoff, or `--no-publish-handoff` to retain only System A outputs. `--no-resume` explicitly invalidates the full chain while retaining historical directories.

Failures return a structured error code and the first stage the identical next command will resume. Do not delete the orchestration directory to recover transient network failures.

If duplicate API calls are suspected, inspect the dry-run stage decisions first, then compare `api_calls`/`network_calls` with `historical_api_calls`/`historical_network_calls` in JSON output. Current command calls must be zero for reused stages; historical counters are retained only for audit.

The Python API used by future Flask/job-scheduler integrations is:

```python
from code_engine.orchestration import CaseToAtlasOrchestrator, CaseToAtlasRequest

result = CaseToAtlasOrchestrator().run(CaseToAtlasRequest(
    case_id="...", api_enabled=True, network_enabled=True,
))
```

Legacy per-stage CLIs remain available only for debugging and forensic replay.
