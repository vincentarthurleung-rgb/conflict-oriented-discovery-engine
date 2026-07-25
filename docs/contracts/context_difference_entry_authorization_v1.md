# Context Difference Entry Authorization v1

This strict contract binds Candidate Qualification and its authority sidecar to
two endpoint Context authority audits. `ready` requires a qualified Candidate
and two authoritative, endpoint-bound Contexts. Every other state requires
`ready_for_authoritative_context_difference=false`.

The legacy `qualified_for_l4` name means only “qualified for L4 entry
evaluation”; it is an ambiguous compatibility name and never directly
authorizes Context Difference creation.

