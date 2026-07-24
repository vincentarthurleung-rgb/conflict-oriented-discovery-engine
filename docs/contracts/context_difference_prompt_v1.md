# Context Difference Prompt Contract v1

Status: **Future, inactive**

The prompt may receive only a validated Conflict Candidate, two validated
Observation Context artifacts, endpoint identities, context identities, and a
factor Registry identity.

It may output factor ID, `same`/`different`/`missing_a`/`missing_b`/
`missing_both`, A/B values, endpoint anchor IDs, comparison rationale, and
missing-information text.

It must not output `comparability_effect`, effect-assessment status,
none/minor/major/blocking, pair comparability, formal-conflict eligibility,
confirmed conflict, explanatory severity, or an adjudication decision. This
contract is not called by the v1 offline architecture-split run.
