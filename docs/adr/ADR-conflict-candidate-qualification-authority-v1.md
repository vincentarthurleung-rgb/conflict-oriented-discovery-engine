# ADR: Conflict Candidate Qualification Authority v1

Status: Accepted

## Decision

Contradiction Signal scientific validity and Candidate downstream authority
are separate. L3c Candidate Qualification consumes signal validity; legacy
Candidate authority must never determine that validity in reverse.

Historical Candidate identity and scientific pair membership are preserved.
New authority is expressed only by qualification and authority sidecars.
Future standard L4 creation requires a qualified Candidate. Existing L4
artifacts may remain read-only diagnostics but do not automatically become new
authority. Qualification is an L4 entry gate, not a formal conflict decision.

## Out of scope

This decision establishes no Granularity Bridge mapping, Comparability
severity, Divergence Explanation policy, ebd5 scientific adjudication, or
Formal conflict decision.
