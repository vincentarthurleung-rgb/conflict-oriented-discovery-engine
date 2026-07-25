# L4 Context Readiness Gate v1

Status: Active

The gate separates Candidate qualification from permission to materialize or
accept an authoritative Context Difference:

`Candidate Qualification → Context Readiness Entry → Difference
Materialization/Validation → Difference Authority → L4b`.

Both endpoint contexts must independently pass strict schema validation,
validator/audit validation, identity recomputation, provenance completeness,
immutable source hashing, and observation/claim binding. `ready` authorizes
only the next materialization stage; it does not assert that a Difference
exists or is valid.

Missing or invalid context creates a requirement sidecar only. This run
authorizes no provider, network, download, automatic recovery, or historical
payload mutation.

Remediation ownership is Observation-level. Entry receives reference-only
dependency bindings; it does not own or duplicate remediation tasks.
