# Fresh Run Guide

## Start Clean

```bash
python scripts/maintenance/cleanup_legacy_artifacts.py --dry-run
python scripts/maintenance/cleanup_legacy_artifacts.py --apply
python -m unittest discover -s tests
```

The cleanup retains `data/metadata/global_manifest.json`, the literature quality
audit, configs, source, docs, and fixtures. Review the JSON and Markdown audit in
`cleanup_reports/` before an apply run.

## Create A Run Boundary

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "runs/${RUN_ID}"
```

Record the effective domain, prompt profile/version, output schema, model
contract, and config hashes in that directory. The current legacy stage wrappers
still write some intermediate files under `data/`; move or export reviewed run
outputs into `runs/<run_id>/` until every stage supports a run root directly.

## Regenerate Literature And Layers

1. Review `data/metadata/global_manifest.json` and the Stage0 query settings.
2. Run `python scripts/stage0_fetch_pmc.py` and/or
   `python scripts/stage0_5_fetch_abstracts.py` to rebuild the raw download cache.
3. Run the reviewed Stage1 preprocessing wrapper.
4. Compile L1 v2 extraction inputs through Domain Router, Prompt Registry, and
   Prompt Compiler. Do not reuse prompt-v1 outputs as current graph evidence.
5. Run deterministic normalization, conflict, context, hypothesis, validation,
   and reporting stages after inspecting each command with `--help` where
   available.

Preview L1 v2 without API access:

```bash
python -m code_engine.cli.extract \
  --text "Ketamine increased BDNF in mice." \
  --auto-domain --dry-run --no-api
```

The preview reports temperature, profile/schema/policy/model versions, prompt
hash, fingerprint, and cache decision. It performs no extraction. Old L1
without complete fingerprint metadata is not reused in a fresh run.

Preview the complete intake path:

```bash
python -m code_engine.cli.intake \
  --query "氯胺酮抗抑郁机制现在研究到哪了" \
  --dry-run --no-api --no-network
```

Execution requires explicit paired gates: `--execute --network` for NCBI and
`--execute --api` for DeepSeek. Review the saved search plan before acquisition.

Layer 2 uses ResolverCascade by default:

```bash
python scripts/stage4_l2_normalize.py --resolver-cascade --strict-config
```

Do not use `--legacy-synonym-only` for a fresh run. Unknown or ambiguous terms
remain in the L2 audit and are excluded from high-confidence L3 statistics
unless `--include-low-confidence` is explicitly supplied for diagnosis.

Stage0 and L1 can access external services only through explicit paired gates.
Cleanup, tests, and package query commands remain offline
by default and return explicit insufficient-coverage status in a clean workspace.

`--legacy-source` is not part of a fresh run. It exists only for an explicit
compatibility audit and causes query reports to declare `using_legacy_data: true`.
