# Domain-Adaptive Validation

## Plan, Execute, Aggregate

The validation layer is split into three responsibilities:

1. `DomainAdaptiveValidationRouter` creates a `ValidationPlan` only.
2. Registered validator plugins return individual `ValidationResult` objects.
3. `ValidationResultAggregator` deterministically computes the overall status.

The router never marks a hypothesis as supported. Relations select appropriate
modalities: expression routes to CuratedOmics/GEO/pathway plugins, binding to
ChEMBL/DrugBank/BindingDB, pathway mechanisms to Reactome/pathway plugins,
protein interactions to STRING/Reactome, and clinical outcomes to clinical
trial and PubMed clinical-evidence plugins. Unsupported relations route to
`NullValidator`.

## Coverage Semantics

The normalized statuses are `supported`, `contradicted`, `mixed`,
`no_coverage`, `not_applicable`, `external_index_not_configured`,
`insufficient_quality`, and `error`. Missing local external indexes produce a
structured `external_index_not_configured` result rather than an exception or
a success. Aggregation maps results containing only missing/no coverage to
overall `no_coverage`.

Legacy CuratedOmics status strings remain readable and map to the normalized
status vocabulary. CuratedOmics uses a small curated/demo local registry; it is
one plugin and is not full LINCS validation.

## Current Plugin State

`CuratedOmicsValidator` and `NullValidator` retain their legacy dictionary
interfaces while also accepting `ValidationQuestion`. GEO, DrugBank, ChEMBL,
BindingDB, Reactome, pathway, STRING, ClinicalTrials, and PubMed clinical
validators are local-index-aware skeletons. They do not call external services.

Preview a plan and local coverage state without external calls:

```bash
python -m code_engine.cli.validate_hypothesis \
  --hypothesis-file path/to/hypotheses.json \
  --domain neuropharmacology \
  --relation-type drug_gene_expression \
  --dry-run
```
