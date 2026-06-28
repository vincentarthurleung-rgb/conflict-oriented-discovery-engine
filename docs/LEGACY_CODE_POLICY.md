# Legacy Code Policy

## Scope

Legacy code is retained only to preserve old imports and reviewed research
commands. New implementation work belongs under `src/code_engine/`; legacy
wrappers must not become a second source of scientific logic.

## Rules

- Keep `scripts/stage*.py` and `src/pipelines/stage*.py` callable while their
  compatibility contract is still used.
- Mark fixed `data/processed/` and `reports/` paths as legacy runtime behavior.
- Treat old field names as compatibility inputs, never as the preferred output
  contract.
- Never load `artifacts/legacy/` or `quarantine/` implicitly. A caller must pass
  an explicit `allow_legacy_source=True` or CLI-equivalent compatibility flag.
- Missing current runtime data produces an empty result plus a status/warning;
  it must not trigger stale legacy reuse.
- Remove a wrapper only after its callers, import path, replacement, and tests
  are documented.

## Classification

1. **Acceptable legacy compatibility**: thin wrappers, re-exports, legacy field
   readers, and report sanitizers covered by tests.
2. **Should migrate later**: stage orchestration that still owns substantial
   logic or fixed output paths.
3. **Dangerous old-data dependency**: code that assumes historical L1-L6 files
   are current evidence. It must not be called by package-default query paths.
4. **Obsolete artifact reference**: old filenames or strong status labels kept
   only to read/sanitize historical output.

See `cleanup_reports/legacy_code_scan.md` for the current inventory.

The query CLI equivalent is `--legacy-source <archived-repository-root>`. It is
intended for compatibility audits only and marks generated reports with
`using_legacy_data: true`.
