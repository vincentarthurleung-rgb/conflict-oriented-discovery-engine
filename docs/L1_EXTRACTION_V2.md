# L1 Extraction v2

## Deterministic Default

L1 v2 uses `temperature=0.0`, `top_p=1.0`, and two retries by default. Sampling
temperature no longer increases with chunk index. The old schedule exists only
behind `--experimental-temperature-schedule` and is excluded from normal runs.

The package CLI is offline by default:

```bash
python -m code_engine.cli.extract \
  --text "Ketamine increased BDNF in mice." \
  --auto-domain --dry-run --no-api
```

It selects a domain/profile, compiles a prompt, computes metadata and cache
identity, and reports what would be extracted. DeepSeek is called only when both
`--execute --api` are present and a key is available.

## Domain And Prompt Profiles

`general_biomedical` is the default. With `--auto-domain`, supported ketamine,
depression, BDNF, NMDA, AMPA, and mTOR terms select `neuropharmacology`. The
neuropharmacology profile includes species, sex, age, disease model, brain
region, cell type, treatment, dose, route, duration, post-treatment time,
readout, behavioral assay, clinical outcome, genotype, oxygen, and localization.

Prompt compilation records domain ID, profile ID/version, compiled prompt hash,
output schema version, and extraction policy version.

## Fingerprint And Reuse

The strict L1 fingerprint contains paper ID, chunk ID/hash, domain ID, prompt
profile ID/version, output schema and extraction policy versions, model name,
and model family. Every field participates in the cache key. Model-name changes
are incompatible unless same-family reuse is explicitly enabled in planning.

Historical L1 without complete fingerprint metadata is incompatible by default;
`--allow-legacy-l1-reuse` is an explicit audit-marked exception.

## Output Contract

`L1ExtractedClaim` carries entity/relation fields, evidence sentence and quote,
statement/evidence type, confidence, negation/speculation, entity/relation/context
spans, context slots, warnings, and complete extraction metadata. Missing
evidence sentences cap confidence at `0.6`; speculative claims cannot remain
direct experimental results.

Converters preserve these fields in `EvidenceRecord` and emit the legacy causal
tuple shape consumed by current L1.5/L2. Legacy tuples can be adapted to L1 v2,
but receive a provenance warning. Entity IDs are assigned later by L2, so
MechanismEdge construction remains a post-normalization operation.
