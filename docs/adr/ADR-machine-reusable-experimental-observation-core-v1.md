# ADR: Machine-reusable Experimental Observation Core v1

Status: Accepted

## Decision

Factor, measurement, result, and their explicit references are the minimum
machine-reusable experimental skeleton. Context cannot replace that skeleton.
Experimental observations and non-experimental claims are counted separately.
Formal experimental records require a measurement and an observed result;
every result references a measurement, and comparative results reference a
comparator or baseline. Factor cardinality is governed by observation type.

Historical repair is immutable and offline-first. Explicit existing structures
may produce new revisions; absent structure remains unresolved and may produce
only a deduplicated Provider re-extraction plan. The LLM remains limited to
natural-language candidate structuring.

## Not accepted

This decision authorizes no Provider execution, automatic re-extraction,
conflict conclusion, Comparability, Divergence Explanation, ebd5 adjudication,
dataset release, Atlas activation, active-pointer change, or scientific-state
mutation.

