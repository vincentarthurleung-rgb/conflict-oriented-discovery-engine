# Conflict Candidate Qualification v1

Status: Active

L3c sits between Contradiction Signal (L3b) and Context Difference (L4a). It
answers only whether an existing scientific pair has authority to enter the
new L4 pipeline.

Qualification consumes an aligned `ClaimAlignmentRecordV2`, an independently
validated `ContradictionSignalV2`, endpoint claim identities, complete
candidate lineage, and a candidate-generation policy identity. It consumes no
Context Difference, Comparability, Divergence Explanation, or formal decision.

Historical candidate artifacts, IDs, identities, order, and pair membership
remain unchanged. Each candidate gets a scientific-pair identity, a
qualification record, and an authority sidecar. `future_standard` L4 entry is
granted only when qualification is `qualified`.

A valid historical Context Difference can remain a read-only diagnostic. Its
validity does not bypass L3c and does not confer new L4 authority.

The legacy `qualified_for_l4` field means eligibility for L4 entry evaluation
only (`deprecated_ambiguous_name=true`). A separate Context Readiness Gate must
pass before authoritative Difference materialization.

Unqualified Candidates do not receive active L4 Context blocking dependencies,
even when their endpoint Observations appear in the global remediation backlog.
