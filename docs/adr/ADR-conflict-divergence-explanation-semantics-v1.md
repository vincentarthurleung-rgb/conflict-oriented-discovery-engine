# ADR: Conflict Divergence Explanation Semantics v1

- Status: **Proposed**
- Runtime activation: **false**

## Context

Context difference, comparability impact, and explanatory effect answer
different scientific questions. Treating them as one enum would silently turn
experimental variation into a conflict decision.

## Proposal

Represent epistemic assessment status separately from explanatory effect.
Pending and insufficient-information states retain a null effect. Assessed
effects require versioned policy or complete adjudication provenance.

## Non-decisions

This ADR does not define factor-specific rules, map comparability severity to
explanation, aggregate multiple factors, adjudicate ebd5, or activate a formal
gate. `not_explanatory`, `potentially_explanatory`, and
`sufficiently_explanatory` remain proposed semantics.
