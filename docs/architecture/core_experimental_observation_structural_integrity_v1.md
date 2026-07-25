# Core Experimental Observation Structural Integrity v1

Status: implemented as an immutable offline sidecar.

The reusable unit is an experiment-scoped factor → measurement → observed-result
graph backed by evidence, context identity, and provenance. A claim plus an
evidence sentence is not that graph. Context describes the circumstances of an
experiment but cannot substitute for what changed, what was measured, or what
was observed.

The `extraction_assets.experimental_core` package reads explicit structure from
historical L1, validated, fulltext-v3, projection, evidence-chain, extraction,
forensic, and context assets. It never imports a Provider client, conflict
candidate, Context Difference, Comparability, or Divergence Explanation layer.
Recovery emits new revisions and never mutates historical payloads.

The offline orchestration order is: inventory, stage trace, first-loss
diagnosis, explicit deterministic migration, reference and atomicity audit,
structural integrity gate, machine-reuse candidate gate, then deduplicated
remediation planning. Every external-execution authorization is false.

Observation type controls factor cardinality. Interventional experiments need
an active factor; observational comparisons need explicit groups/comparison;
descriptive measurements may be factor-exempt only through the policy.
Measurements and results remain mandatory for every formal experimental type.

