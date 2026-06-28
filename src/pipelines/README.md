# Legacy Pipeline Compatibility

Files named `stage*.py` preserve old orchestration and filesystem contracts.
They are compatibility entrypoints, not the preferred package boundary.

New deterministic modules live under `src/code_engine/`. Several stage files
still contain substantive orchestration and fixed `data/processed/` paths; see
`docs/LEGACY_CODE_POLICY.md` before changing or invoking them. A clean workspace
does not silently load archived data from `artifacts/legacy/` or `quarantine/`.
