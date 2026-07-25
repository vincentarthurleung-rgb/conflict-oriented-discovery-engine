# Conflict Adjudication Orchestration v1

## v2 semantic-boundary refinement

Claim Alignment v2 consumes direction-neutral Proposition Core views and explicit Granularity Bridge assessments. Contradiction Signal v2 separately consumes Result views and binds the v2 alignment identity. Structural contradiction validity is not formal eligibility: historical candidates are retained under `legacy_preserved`, and no signal may bypass the alignment gate. Context Difference remains independently valid; comparability and divergence explanation remain pending L4b policy.

Status: **Active staging architecture**

```text
L2.5 Observation Context
  → L3a Claim Alignment
  → L3b Contradiction Signal / Candidate
  → L4a Context Difference
  → L4b ┬ Factor Comparability
        └ Factor Divergence Explanation
  → L4c Pair-level Conflict Adjudication
```

Claim Alignment establishes whether endpoints express sufficiently close
proposition types. It is not comparability. Contradiction Signal establishes a
direction/result disagreement; it is not formal conflict.

L4b has two parallel authorities. Comparability asks whether a difference
limits comparison. Divergence Explanation asks whether the difference explains
the observed disagreement. Neither branch imports or deterministically maps
the other.

`factor_attribution_bundle_v1` aggregates identities and completion states
only. It computes no maximum severity, vote, score, threshold, or automatic
pair class.

L4c binds alignment, contradiction, preserved candidate, validated difference,
both attribution branch identities, and gate policy. Missing alignment,
signal, difference, or attribution fails closed. Staging authority cannot
confirm formal conflict.

Historical candidates remain byte-for-byte unchanged and are connected through
sidecar migration bindings. Historical Context Difference v1 remains unchanged
and receives a separate alignment/signal binding. Legacy pair attribution is
read-only and non-authoritative.
