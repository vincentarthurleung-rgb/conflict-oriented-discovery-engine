# Script Entry Points

Files directly under `scripts/` are legacy CLI wrappers retained for existing
Stage0-8 workflows. Stage numbers and the current Layer0-8 architecture do not
always match; consult `docs/STAGE_LAYER_MAPPING.md` before changing orchestration.

New package-oriented entrypoints are preferred:

```bash
python -m code_engine.cli.query --help
python -m code_engine.cli.validate --help
python -m code_engine.cli.extract --help
python -m code_engine.cli.visualize
```

The API-dependent extraction wrapper does nothing unless `--run-legacy` is
explicitly supplied. Legacy scripts have not been moved in this refactor so old
commands and external automation keep their paths.

Legacy stage wrappers may still use fixed `data/raw/`, `data/interim/`,
`data/processed/`, and `reports/` paths. They do not define the new package
contract and must not be pointed at `artifacts/legacy/` or `quarantine/` as an
implicit source. See `docs/LEGACY_CODE_POLICY.md` and
`docs/FRESH_RUN_GUIDE.md`.

Runtime cleanup is dry-run by default:

```bash
python scripts/maintenance/cleanup_legacy_artifacts.py --dry-run
python scripts/maintenance/cleanup_legacy_artifacts.py --apply
```
