# Biomedical Entity Normalization

## L2 Resolver Cascade Is Now The Default Mainline Normalizer

Layer 2 observations are produced by `ResolverCascade.resolve_entity()` by
default. Canonical ID/name, entity type, semantic level, biological relations,
decision status, confidence, resolver, match type, warnings, and graph-use
permission are carried into Layer 3.

The previous synonym-map/uppercase path remains available only through the
explicit `--legacy-synonym-only` compatibility flag. Without the diagnostic
`--include-low-confidence` flag, ambiguous and `unresolved_fallback`
observations remain in the L2 audit but are excluded from high-confidence
conflict entropy and Type I/II/III statistics.

Layer 3 groups by subject/object canonical IDs when present and falls back to
legacy normalized names for old records. This keeps receptor complexes separate
from gene subunits and metabolites separate from parent compounds.

## Resolver Boundary

Layer 2 uses a deterministic resolver cascade by default:

```text
raw term
  -> lexical normalization
  -> local curated registry lookup
  -> entity-type classification
  -> exact/alias/lexical/fuzzy candidates
  -> deterministic resolved, ambiguous, or unresolved decision
```

The current registry is a local curated MVP for the ketamine pilot. It does not
provide comprehensive external ontology coverage. Future work includes online
resolvers, ontology-backed identifier mapping, and human review of registry
patches.

## Identity Versus Biological Relation

The resolver does not treat biological relationships as equality merges:

- GluA1 is `same_as` GRIA1 at the alias-identity level; GRIA1 is `subunit_of` the AMPA receptor complex.
- GluN2B is an alias of GRIN2B; GRIN2B is `subunit_of` the NMDA receptor complex.
- Norketamine is `metabolite_of` ketamine.
- Ketamine hydrochloride is `salt_form_of` ketamine.
- Forced swim test `measures` depression-like behavior.

Receptor complexes, genes, metabolites, parent compounds, phenotypes, diseases,
assays, pathways, regions, and contexts retain separate canonical IDs and types.

## Confidence And Audit

Exact local-registry decisions may be used by the high-confidence graph. Fuzzy
or duplicate-alias candidates are ambiguous and require review. Unknown terms
retain an uppercase traceability label with status `unresolved_fallback`,
confidence at most `0.35`, and `allow_high_confidence_graph_use=false`.
Uppercase fallback is no longer treated as high-quality normalization.

Every decision records the canonical ID/name, type, semantic level, relations,
resolver, match type, candidates, reason, confidence, graph-use permission, and
warnings. Layer 2 writes JSON and Markdown audits.

The audit includes raw-term, resolved, ambiguous, unresolved, invalid,
high-confidence usable, and low-confidence excluded counts; top unresolved and
ambiguous terms; dangerous warning counts; and four reference examples.

## Optional Candidate Suggestions

The LLM candidate proposer is disabled by default and contains no API client.
When explicitly exercised as a dry-run stub, it returns only unvalidated
candidates marked `requires_deterministic_validation`. Suggestions cannot write
final graph decisions or bypass the registry resolver.
