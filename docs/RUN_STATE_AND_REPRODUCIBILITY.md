# RunState and Reproducibility

Each run is isolated under `runs/<run_id>/`:

```text
run_state.json
run_report.md
final_report.md
artifacts/
logs/
```

RunState records configuration, DomainProfile identifiers, per-step inputs and outputs, summaries, warnings, errors, API/network call counts, aggregate counts, current/failed step, and final status. It is atomically saved after every step transition. Failures are persisted and then re-raised so the traceback remains visible.

`--resume` loads this state and starts at the next unfinished step. Planned/blocked dry-run work can be reconsidered when resuming with `--execute`. API and network permissions are reset to disabled unless explicitly supplied again. Legacy and quarantine artifacts are excluded unless `--allow-legacy` is explicit; any global data path produced by a lower-level executor is recorded in RunState.

Run IDs use `YYYYMMDD_HHMMSS_<query-slug>`. `planned` describes a completed dry-run plan, `partial` describes an intentionally stopped or input-blocked execution, `completed` describes a completed execution, and `failed` identifies an exception-bearing run.
