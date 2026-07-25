# Claim Alignment Dimension Taxonomy v2

Status: Accepted

The versioned role taxonomy assigns dimensions to `proposition_core`, `contradiction_dimension`, `context_dimension`, `granularity_bridge`, or `unresolved`. Assignment status is separately recorded as `assigned`, `conditional`, `unresolved`, or `unsupported`.

Alignment v2 is pairwise. `aligned` requires all required core dimensions to match and every identity-affecting granularity bridge to be exact or authorized by explicit policy. A core mismatch is `unaligned`; missing required core information is `insufficient_information`; unresolved non-exact granularity is at most `partially_aligned`.

Direction, sign, and polarity never participate in proposition-core identity. Measurement method, assay, dose, duration, species, and ordinary temporal/intervention conditions are context and do not block alignment by default. Historical `aligned_claim_group_v1` remains read-only; its group-count metric is retained only as a deprecated ambiguous metric.
