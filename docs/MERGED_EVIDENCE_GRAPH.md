# Merged Evidence Graph

The merged evidence graph is a run-level reasoning layer. It does not create one isolated graph per paper: normalized observations from all papers in the current run are converted to provenance-bearing `EvidenceEdge` records and grouped by canonical subject, object, relation family, and polarity type.

## EvidenceEdge and RelationEvidenceBundle

An `EvidenceEdge` states that one paper provides one directional observation about a canonical relation. It retains paper identity, DOI, title, journal, year, evidence span, context, scope, tier, and links to upstream claims or evidence where available.

A `RelationEvidenceBundle` merges all evidence edges for the same canonical relation. Paper-level direction votes are deduplicated. Multiple directions from one paper become `mixed` and produce a warning. Unknown directions are retained as incomplete evidence but excluded from entropy.

## Graph conflict reasoning

Every bundle receives a deterministic reasoning trace. With at least two papers, two directions, and entropy at least 0.55, it becomes a `graph_conflict_candidate`. One direction across enough papers is `graph_uncontested_relation`; fewer papers are `graph_insufficient_evidence`. Different context-specific dominant directions add `context_partition_candidate`, not a resolution verdict.

This layer complements `abstract_conflict_screening`; it does not replace that existing logic. An alignment artifact reports matched, graph-only, and existing-only candidates.

## Timeline and hypotheses

Existing temporal windows and timeline evidence items attach to matching graph conflicts through stable conflict keys. Hypotheses are retained as nodes and attached using linked conflict/evidence/observation IDs or the canonical relation key. Neither timeline nor validation results delete or alter hypotheses. Validation artifacts may be exported as nodes but never influence bundle conflict reasoning.

## Operational boundary

The module performs local deterministic transformations only. It imports no LLM, API, network, remote validation, graph database, or visualization dependency. A graph-derived conflict is an auditable evidence candidate, not proof that a conflict is solved or that a hypothesis is true.

This responds to the graph-construction requirement as:

```text
cross-paper observations
→ EvidenceEdge
→ one canonical RelationEvidenceBundle
→ GraphConflictCandidate plus reasoning trace
→ attached timeline and hypotheses
```

Persistent, stale, and later-explanation statuses remain temporal evidence descriptions requiring human review.
