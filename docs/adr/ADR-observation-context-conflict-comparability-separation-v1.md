# ADR: Observation Context and Conflict Comparability Separation v1

- Status: **Accepted**
- Decision date: **2026-07-25**
- Scope: context pipeline architecture and staging runtime boundaries

## Context

The legacy context-attribution package combined single-observation extraction,
deterministic component/inference handling, pairwise difference facts,
comparability effects, pair comparability, human-adjudication design, and
formal-conflict eligibility. That made a failure in proposed effect semantics
indistinguishable from a failure to model the underlying context difference.

## Decision

Place Observation Context after L2 normalization at L2.5. Keep high-recall
candidate discovery at L3. Place factual pair comparison at L4a, scientific
comparability assessment at L4b, and fail-closed formal judgment at L4c.

Effect is not part of Observation Context or Context Difference. A formal
conflict must consume a validated Conflict Comparability artifact with matching
upstream identities. Missing context never deletes a candidate, but missing or
unvalidated context/difference/comparability blocks formal confirmation.

## Consequences

Each layer has an independent schema, validator, identity, provenance, and
artifact. Identity drift invalidates downstream reuse. Legacy mixed artifacts
remain readable through adapters but cannot become new runtime authority.

The Conflict Comparability Effect Semantic Contract v1 and Model B remain
**Proposed**, inactive, and separate from this Accepted architecture decision.
This ADR neither adjudicates any existing pair nor changes Formal v3 results.
