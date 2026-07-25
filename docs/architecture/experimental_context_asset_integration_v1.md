# Experimental Context Asset Integration v1

Experimental Context is now a first-class, immutable extraction asset beside an
Observation. The asset chain is:

`source/envelope → candidate revision → field evidence + value-state basis →
validated revision → normalization revision → consolidation revision`.

The existing `context_attribution.observation_context` package remains the
owner of scientific schema and validation. The new
`extraction_assets.context` package wraps results, records lineage, inventories
historical artifacts, and computes coverage, remediation plans, and multi-axis
readiness. It has no Provider client and performs no network operation.

Context Difference, Comparability, Divergence Explanation, and Formal Conflict
are downstream reasoning and are prohibited from every Context candidate.
Shared values require an explicit validated experiment scope, an eligible
registry field, source evidence, observation membership, and conflict-free
deterministic propagation. Missing historical scope therefore fails closed.

Historical migration creates sidecars only. A scientifically validated legacy
Context remains `validated_legacy` even when Attempt↔Raw lineage is incomplete;
its provenance and replayability axes record that limitation independently.

