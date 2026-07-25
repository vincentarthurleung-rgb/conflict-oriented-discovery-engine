# Context Pipeline Layer Separation v1

Status: **Active architecture; staging runtime**

The context pipeline separates observational facts from pairwise scientific
judgment:

```text
L2 normalized claim
  → L2.5 Observation Context
  → L3 Conflict Candidate Discovery
  → L4a Context Difference
  → L4b Conflict Comparability
  → L4c Formal Conflict Judgment
```

The separation remains valid. The Accepted
`ADR-conflict-adjudication-orchestration-v1` extends and refines its
orchestration: L3 is now Claim Alignment followed by Contradiction Signal, L4b
contains parallel Comparability and Divergence Explanation branches, and L4c
is unified pair-level adjudication. This extension does not delete or alter the
historical architecture decision.

## Responsibilities and authority

L2.5 describes one observation's experimental conditions. Provider output may
suggest explicit facts and local-chain components. Deterministic code owns
schema validation, spans, anchors, Registry/Composition enforcement,
normalization, inference, identity, and provenance. Pair IDs, difference
statuses, effects, comparability, adjudication, and formal-conflict fields are
forbidden.

L3 preserves high-recall candidates even when context is partial or
unavailable. Candidate identity binds endpoint claims, canonical edge,
disagreement signal, and generation policy; it never binds a future effect or
formal decision.

L4a compares two validated Observation Context artifacts. It owns only
same/different/missing facts, endpoint values and anchors, rationale, and
provenance. It does not determine importance, severity, comparability, or
formal eligibility.

L4b consumes a validated candidate and validated Context Difference. Only an
activated versioned policy or provenance-complete adjudication may yield a
scientifically validated assessment. The proposed Model B effect contract is
not active.

L4c is fail-closed. Formal confirmation requires matching, validated upstream
identities through L4b. The v1 implementation is staging-only and cannot alter
Formal v3 authority.

## Dependency direction

Observation Context imports no pairwise layer. Context Difference may import
Candidate Qualification and Observation Context schemas. Only a qualified
Candidate may create future-standard L4 authority; historical Difference
artifacts can remain diagnostic. Comparability may import Difference.
Candidate qualification first enters the independent Context Readiness Gate;
it never directly authorizes Difference creation.
Formal Judgment may import all validated upstream artifacts. Legacy readers and
adapters are read-only and are never runtime authority.

## Legacy projection

The `context_pair_attribution_v3_to_context_difference_v1_adapter` copies only
factor ID, status, A/B values, A/B anchors, and rationale/provenance. Legacy
effect, explanatory strength, pair comparability, confidence, primary factors,
and reasoning summary are retained only in
`legacy_non_authoritative_comparability_fields`. The adapter never changes
status/value/anchor, fills missing data, or converts legacy validation failure
into success. The entire projected Context Difference must independently pass
Schema v1, validator v1, Registry, endpoint, anchor, and source-context checks.

## Runtime and artifact boundary

The architecture-split run writes independent L2.5, L3, L4a, L4b, and staging
L4c artifacts. It performs no Provider/API/network/download operation, reads no
credential, creates no handoff, and changes no production pointer or historical
artifact.
