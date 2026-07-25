# Experimental Observation Structural Integrity v1

The gate is observation-type-aware and fail-closed. A complete record needs a
validated type, policy-compliant factors, at least one measurement and result,
valid result-to-measurement references, required comparative references, core
evidence, traceable provenance, unique local IDs, and no dangling references.

`structurally_complete_with_limitations` permits non-core metadata gaps and
unresolved normalization. It never permits an empty measurement/result or a
result without a measurement reference.

