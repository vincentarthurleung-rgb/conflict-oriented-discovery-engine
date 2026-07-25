# Conflict Candidate Qualification v1 contract

`conflict_candidate_qualification_v1` is strict (`extra=forbid`) and binds the
legacy candidate, ordered observations and endpoint claims, proposition cores,
Alignment v2, Contradiction Signal v2, generation policy, contract, validator,
scientific pair, source lineage, and provenance.

The deterministic statuses are `qualified`, `legacy_preserved`,
`blocked_alignment`, `blocked_signal`, `insufficient_information`, and
`rejected`. Qualified requires aligned proposition cores and a validated,
structurally/schema/validator-valid, provenance-complete signal.
`qualified_for_l4` is true only for `qualified`; rejected records require error
codes.

Qualification does not produce comparability, explanation, severity,
adjudication, or formal conflict.

